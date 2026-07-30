import html
import secrets

from collections import (
    Counter,
    defaultdict,
)

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from zoneinfo import ZoneInfo

import requests

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
)

from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)

from rq import Queue

from sqlalchemy import (
    func,
    select,
)

from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db

from app.models import (
    AuthorizedGroup,
    CfeRequest,
    ProductRechargeLog,
    RenapoRequest,
)

from app.panel_data import (
    fmt_dt,
    main_panel_data,
    period_bounds,
)

from app.panel_theme import (
    badge_html,
    page_html,
    panel_css,
)

from app.queue import (
    cfe_queue,
    redis_conn,
    renapo_queue,
)


router = APIRouter()

PANEL_TZ = ZoneInfo(
    "America/Monterrey"
)


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _valid_token(value: str | None) -> bool:
    expected = (settings.ADMIN_PANEL_TOKEN or "").strip()
    supplied = (value or "").strip()
    return bool(expected and supplied and secrets.compare_digest(supplied, expected))


def require_panel_token(
    request: Request,
    token: str = Query(default=""),
) -> str:
    supplied = token or request.headers.get("x-panel-token", "")
    if not _valid_token(supplied):
        raise HTTPException(status_code=403, detail="No autorizado")
    return supplied


def _queue_info(queue: Queue) -> dict:
    try:
        return {
            "name": queue.name,
            "queued": queue.count,
            "started": queue.started_job_registry.count,
            "failed": queue.failed_job_registry.count,
            "finished": queue.finished_job_registry.count,
            "deferred": queue.deferred_job_registry.count,
            "scheduled": queue.scheduled_job_registry.count,
        }
    except Exception as exc:
        return {"name": queue.name, "error": str(exc)}


def _evolution_state(instance_name: str) -> str:
    if not instance_name:
        return "unknown"
    cache_key = f"extras:panel:evolution:{instance_name}"
    try:
        cached = redis_conn.get(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    try:
        url = f"{settings.EVOLUTION_BASE_URL.rstrip('/')}/instance/connectionState/{instance_name}"
        response = requests.get(
            url,
            headers={"apikey": settings.EVOLUTION_API_KEY},
            timeout=3,
        )
        data = response.json() if response.content else {}
        state = (
            data.get("instance", {}).get("state")
            or data.get("state")
            or data.get("connectionState")
            or "unknown"
        )
        state = str(state).lower()
    except Exception:
        state = "unknown"

    try:
        redis_conn.setex(cache_key, 30, state)
    except Exception:
        pass
    return state


def _status_badge(status: str) -> str:
    status = (status or "SIN ESTADO").upper()
    css = {
        "DONE": "ok",
        "NO_RECORD": "warn",
        "ERROR": "bad",
        "QUEUED": "info",
        "WAITING_PROVIDER": "info",
        "PROCESSING": "info",
        "DISABLED": "muted",
    }.get(status, "muted")
    return f'<span class="badge {css}">{_esc(status)}</span>'


def _base_css() -> str:
    return panel_css()


@router.get("/", include_in_schema=False)
def root(token: str = ""):
    target = "/panel"
    if token:
        target += f"?token={token}"
    return HTMLResponse(
        f'<meta http-equiv="refresh" content="0; url={_esc(target)}">'
        f'<a href="{_esc(target)}">Abrir panel</a>',
        status_code=200,
    )


@router.get(
    "/panel",
    response_class=HTMLResponse,
)
def panel_home(
    token: str = Depends(
        require_panel_token
    ),
    view: str = "day",
    date_from: str = "",
    date_to: str = "",
    db: Session = Depends(get_db),
):
    time_min, time_max, view = (
        period_bounds(
            view,
            date_from,
            date_to,
        )
    )

    data = main_panel_data(
        db,
        time_min,
        time_max,
    )

    summary = data["summary"]
    groups = data["groups"]
    recent = data["recent"]

    group_rows = []

    for row in groups:
        cfe_available = (
            max(
                0,
                row["cfe_limit"]
                - row["cfe_used"],
            )
            if row["cfe_limit"] > 0
            else "∞"
        )

        renapo_available = (
            max(
                0,
                row["renapo_limit"]
                - row["renapo_used"],
            )
            if row["renapo_limit"] > 0
            else "∞"
        )

        group_rows.append(
            f"""
            <tr>
              <td>
                <strong>
                  {html.escape(
                      row["group_name"]
                  )}
                </strong>

                <div class="small mono">
                  {html.escape(
                      row["group_jid"]
                  )}
                </div>

                <div class="small">
                  Instancia:
                  {html.escape(
                      row["owner_instance"]
                  )}
                </div>
              </td>

              <td class="right">
                {row["total"]}
              </td>

              <td class="right">
                {row["done"]}
              </td>

              <td>
                CFE:
                {row["cfe_used"]}
                /
                {
                    row["cfe_limit"]
                    or "∞"
                }

                <div class="small">
                  Disponible:
                  {cfe_available}
                </div>
              </td>

              <td>
                RENAPO:
                {row["renapo_used"]}
                /
                {
                    row["renapo_limit"]
                    or "∞"
                }

                <div class="small">
                  Disponible:
                  {renapo_available}
                </div>
              </td>

              <td>
                {
                    badge_html(
                        "BLOQUEADO",
                        "danger",
                    )
                    if row["blocked"]
                    else badge_html(
                        "ACTIVO",
                        "success",
                    )
                }
              </td>

              <td>
                {fmt_dt(
                    row["last_update"]
                )}
              </td>

              <td>
                <div class="btn-row">
                  <a
                    class="btn btn-info btn-sm"
                    href="/panel/group-detail?token={html.escape(token)}&group_jid={html.escape(row['group_jid'])}&view={html.escape(view)}"
                  >
                    Solicitudes
                  </a>

                  <form
                    method="post"
                    action="/panel/group/{html.escape(row['group_jid'])}/toggle?token={html.escape(token)}"
                    class="inline-form"
                  >
                    <button
                      class="btn btn-sm {
                          'btn-success'
                          if row['blocked']
                          else 'btn-danger'
                      }"
                    >
                      {
                          'Desbloquear'
                          if row['blocked']
                          else 'Bloquear'
                      }
                    </button>
                  </form>
                </div>
              </td>
            </tr>
            """
        )

    recent_rows = []

    for row in recent:
        recent_rows.append(
            f"""
            <tr>
              <td>
                {html.escape(
                    row["module"]
                )}
              </td>

              <td>
                {row["id"]}
              </td>

              <td class="mono">
                {html.escape(
                    row["identifier"]
                )}
              </td>

              <td>
                {badge_html(
                    row["status"],
                    (
                        "success"
                        if row["status"]
                        == "DONE"
                        else "warning"
                        if row["status"]
                        in {
                            "QUEUED",
                            "PROCESSING",
                            "WAITING_PROVIDER",
                            "NO_RECORD",
                        }
                        else "danger"
                        if row["status"]
                        == "ERROR"
                        else "muted"
                    ),
                )}
              </td>

              <td class="mono">
                {html.escape(
                    row["group_jid"]
                )}
              </td>

              <td>
                {html.escape(
                    row["instance"]
                )}
              </td>

              <td>
                {html.escape(
                    row["requester"]
                )}
              </td>

              <td>
                {fmt_dt(
                    row["created_at"]
                )}
              </td>

              <td class="small">
                {html.escape(
                    row["error"]
                )}
              </td>
            </tr>
            """
        )

    cfe_queue_data = _queue_info(
        cfe_queue
    )

    renapo_queue_data = _queue_info(
        renapo_queue
    )

    hero_actions = f"""
    <a
      class="btn btn-light"
      href="/panel/bots?token={html.escape(token)}"
    >
      Bots / mini paneles
    </a>

    <a
      class="btn btn-light"
      href="/panel/providers?token={html.escape(token)}"
    >
      Proveedores
    </a>

    <a
      class="btn btn-light"
      href="/panel?token={html.escape(token)}"
    >
      Actualizar
    </a>
    """

    body = f"""
    <section class="grid-hero">
      <div class="glass">
        <span class="label">
          Solicitudes
        </span>
        <span class="value">
          {summary["total"]}
        </span>
      </div>

      <div class="glass">
        <span class="label">
          Entregadas
        </span>
        <span class="value">
          {summary["done"]}
        </span>
      </div>

      <div class="glass">
        <span class="label">
          CFE
        </span>
        <span class="value">
          {summary["cfe_done"]}
        </span>
      </div>

      <div class="glass">
        <span class="label">
          RENAPO
        </span>
        <span class="value">
          {summary["renapo_done"]}
        </span>
      </div>
    </section>

    <section class="cards">
      <div class="card warning">
        <span class="label">
          Pendientes
        </span>
        <span class="value">
          {summary["pending"]}
        </span>
      </div>

      <div class="card warning">
        <span class="label">
          Sin resultado
        </span>
        <span class="value">
          {summary["no_record"]}
        </span>
      </div>

      <div class="card danger">
        <span class="label">
          Errores
        </span>
        <span class="value">
          {summary["errors"]}
        </span>
      </div>

      <div class="card info">
        <span class="label">
          Grupos
        </span>
        <span class="value">
          {len(groups)}
        </span>
      </div>
    </section>

    <section class="box">
      <div
        class="head collapsible-head open"
        onclick="toggleSection(
          'filtersBody',
          this
        )"
      >
        <strong>
          <span class="collapse-icon">
            ▼
          </span>
          Filtros
        </strong>
      </div>

      <div
        id="filtersBody"
        class="collapsible-body open"
      >
        <div class="content">
          <form
            method="get"
            action="/panel"
            class="filters"
          >
            <input
              type="hidden"
              name="token"
              value="{html.escape(token)}"
            >

            <div class="field">
              <label>Periodo</label>
              <select name="view">
                <option value="day">
                  Hoy
                </option>
                <option value="30d">
                  Últimos 30 días
                </option>
                <option value="month">
                  Mes actual
                </option>
                <option value="prev_month">
                  Mes anterior
                </option>
                <option value="custom">
                  Personalizado
                </option>
              </select>
            </div>

            <div class="field">
              <label>Desde</label>
              <input
                type="date"
                name="date_from"
                value="{html.escape(date_from)}"
              >
            </div>

            <div class="field">
              <label>Hasta</label>
              <input
                type="date"
                name="date_to"
                value="{html.escape(date_to)}"
              >
            </div>

            <button class="btn">
              Aplicar
            </button>
          </form>
        </div>
      </div>
    </section>

    <section class="box">
      <div
        class="head collapsible-head open"
        onclick="toggleSection(
          'groupsBody',
          this
        )"
      >
        <strong>
          <span class="collapse-icon">
            ▼
          </span>
          Resumen por grupo cliente
        </strong>

        <span class="small">
          {len(groups)} grupos
        </span>
      </div>

      <div
        id="groupsBody"
        class="collapsible-body open"
      >
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Grupo</th>
                <th>Total</th>
                <th>HECHO</th>
                <th>Bolsa CFE</th>
                <th>Bolsa RENAPO</th>
                <th>Estado</th>
                <th>Actualización</th>
                <th>Acciones</th>
              </tr>
            </thead>

            <tbody>
              {
                "".join(group_rows)
                or (
                    '<tr>'
                    '<td colspan="8" '
                    'class="empty">'
                    'Sin grupos.'
                    '</td>'
                    '</tr>'
                )
              }
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="box">
      <div
        class="head collapsible-head open"
        onclick="toggleSection(
          'recentBody',
          this
        )"
      >
        <strong>
          <span class="collapse-icon">
            ▼
          </span>
          Solicitudes recientes
        </strong>
      </div>

      <div
        id="recentBody"
        class="collapsible-body open"
      >
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Módulo</th>
                <th>ID</th>
                <th>Dato</th>
                <th>Estado</th>
                <th>Grupo</th>
                <th>Instancia</th>
                <th>Solicitante</th>
                <th>Creado</th>
                <th>Error</th>
              </tr>
            </thead>

            <tbody>
              {
                "".join(recent_rows)
                or (
                    '<tr>'
                    '<td colspan="9" '
                    'class="empty">'
                    'Sin solicitudes.'
                    '</td>'
                    '</tr>'
                )
              }
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="two">
      <section class="box">
        <div class="head">
          <strong>Colas RQ</strong>
        </div>

        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Cola</th>
                <th>En cola</th>
                <th>Activos</th>
                <th>Fallidos</th>
              </tr>
            </thead>

            <tbody>
              <tr>
                <td>
                  {html.escape(
                      cfe_queue_data["name"]
                  )}
                </td>
                <td>
                  {cfe_queue_data.get(
                      "queued",
                      "-"
                  )}
                </td>
                <td>
                  {cfe_queue_data.get(
                      "started",
                      "-"
                  )}
                </td>
                <td>
                  {cfe_queue_data.get(
                      "failed",
                      "-"
                  )}
                </td>
              </tr>

              <tr>
                <td>
                  {html.escape(
                      renapo_queue_data["name"]
                  )}
                </td>
                <td>
                  {renapo_queue_data.get(
                      "queued",
                      "-"
                  )}
                </td>
                <td>
                  {renapo_queue_data.get(
                      "started",
                      "-"
                  )}
                </td>
                <td>
                  {renapo_queue_data.get(
                      "failed",
                      "-"
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>
    """

    return HTMLResponse(
        page_html(
            title="Panel Trámites Extras",
            hero_title=(
                "Panel Trámites Extras"
            ),
            hero_subtitle=(
                "CFE y RENAPO · "
                "control principal"
            ),
            hero_actions=hero_actions,
            body=body,
        )
    )


def _redirect_panel(token: str):
    return RedirectResponse(
        url=f"/panel?token={token}",
        status_code=303,
    )


@router.post(
    "/panel/group/{group_jid}/toggle"
)
def toggle_group(
    group_jid: str,
    token: str = Depends(
        require_panel_token
    ),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(
            AuthorizedGroup
        ).where(
            AuthorizedGroup.group_jid
            == group_jid
        )
    )

    if not row:
        raise HTTPException(
            404,
            "Grupo no encontrado",
        )

    row.is_blocked = (
        not row.is_blocked
    )

    db.commit()

    return _redirect_panel(token)


@router.post(
    "/panel/group/{group_jid}/rename"
)
def rename_group(
    group_jid: str,
    custom_name: str = Form(...),
    token: str = Depends(
        require_panel_token
    ),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(
            AuthorizedGroup
        ).where(
            AuthorizedGroup.group_jid
            == group_jid
        )
    )

    if not row:
        raise HTTPException(
            404,
            "Grupo no encontrado",
        )

    row.custom_name = (
        custom_name.strip()
        or None
    )

    db.commit()

    return _redirect_panel(token)


@router.post(
    "/panel/group/{group_jid}/hide"
)
def hide_group(
    group_jid: str,
    token: str = Depends(
        require_panel_token
    ),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(
            AuthorizedGroup
        ).where(
            AuthorizedGroup.group_jid
            == group_jid
        )
    )

    if not row:
        raise HTTPException(
            404,
            "Grupo no encontrado",
        )

    row.hidden_in_main = True
    db.commit()

    return _redirect_panel(token)


@router.get("/panel/group-detail", response_class=HTMLResponse)
def panel_group_detail(
    group_jid: str,
    token: str = Depends(require_panel_token),
    view: str = "month",
    date_from: str = "",
    date_to: str = "",
    db: Session = Depends(get_db),
):
    time_min, time_max, view = period_bounds(
        view,
        date_from,
        date_to,
    )
    cfe_rows = list(db.scalars(select(CfeRequest).where(
        CfeRequest.client_group_jid == group_jid,
        CfeRequest.created_at >= time_min,
        CfeRequest.created_at < time_max,
    ).order_by(CfeRequest.created_at.asc())).all())
    renapo_rows = list(db.scalars(select(RenapoRequest).where(
        RenapoRequest.client_group_jid == group_jid,
        RenapoRequest.created_at >= time_min,
        RenapoRequest.created_at < time_max,
    ).order_by(RenapoRequest.created_at.asc())).all())

    daily = defaultdict(lambda: Counter())
    movements = []
    for r in cfe_rows:
        day = fmt_dt(r.created_at)[:10]
        daily[day]["total"] += 1; daily[day][r.status] += 1; daily[day]["cfe"] += 1
        movements.append((r.created_at, "CFE", r.id, r.service_number, r.status, r.client_instance, r.error_message))
    for r in renapo_rows:
        day = fmt_dt(r.created_at)[:10]
        daily[day]["total"] += 1; daily[day][r.status] += 1; daily[day]["renapo"] += 1
        movements.append((r.created_at, "RENAPO", r.id, r.curp, r.status, r.client_instance, r.error_message))
    movements.sort(key=lambda x: x[0] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    daily_html = "".join(
        f"<tr><td>{_esc(day)}</td><td>{data['total']}</td><td>{data['cfe']}</td><td>{data['renapo']}</td><td>{data['DONE']}</td><td>{data['NO_RECORD']}</td><td>{data['ERROR']}</td></tr>"
        for day, data in sorted(daily.items())
    ) or "<tr><td colspan='7'>Sin movimientos.</td></tr>"
    move_html = "".join(
        f"<tr><td>{_esc(mod)}</td><td>{rid}</td><td class='mono'>{_esc(identifier)}</td><td>{_status_badge(st)}</td><td>{_esc(inst)}</td><td>{fmt_dt(created)}</td><td class='small'>{_esc(error or '')}</td></tr>"
        for created, mod, rid, identifier, st, inst, error in movements
    ) or "<tr><td colspan='7'>Sin movimientos.</td></tr>"

    body = f"""
    <section class="cards">
      <div class="card info">
        <span class="label">
          Total
        </span>

        <span class="value">
          {len(movements)}
        </span>
      </div>

      <div class="card">
        <span class="label">
          CFE
        </span>

        <span class="value">
          {len(cfe_rows)}
        </span>
      </div>

      <div class="card">
        <span class="label">
          RENAPO
        </span>

        <span class="value">
          {len(renapo_rows)}
        </span>
      </div>

      <div class="card success">
        <span class="label">
          Entregadas
        </span>

        <span class="value">
          {
            sum(
                1
                for item in movements
                if item[4] == "DONE"
            )
          }
        </span>
      </div>

      <div class="card danger">
        <span class="label">
          Errores
        </span>

        <span class="value">
          {
            sum(
                1
                for item in movements
                if item[4] == "ERROR"
            )
          }
        </span>
      </div>
    </section>

    <section class="box">
      <div
        class="head collapsible-head open"
        onclick="toggleSection(
          'dailyBody',
          this
        )"
      >
        <strong>
          <span class="collapse-icon">
            ▼
          </span>

          Corte diario
        </strong>
      </div>

      <div
        id="dailyBody"
        class="collapsible-body open"
      >
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Total</th>
                <th>CFE</th>
                <th>RENAPO</th>
                <th>DONE</th>
                <th>Sin registro</th>
                <th>Error</th>
              </tr>
            </thead>

            <tbody>
              {daily_html}
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="box">
      <div
        class="head collapsible-head open"
        onclick="toggleSection(
          'movementsBody',
          this
        )"
      >
        <strong>
          <span class="collapse-icon">
            ▼
          </span>

          Movimientos
        </strong>
      </div>

      <div
        id="movementsBody"
        class="collapsible-body open"
      >
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Módulo</th>
                <th>ID</th>
                <th>Dato</th>
                <th>Estado</th>
                <th>Instancia</th>
                <th>Creado</th>
                <th>Error</th>
              </tr>
            </thead>

            <tbody>
              {move_html}
            </tbody>
          </table>
        </div>
      </div>
    </section>
    """

    hero_actions = f"""
    <a
      class="btn btn-light"
      href="/panel?token={_esc(token)}&view={_esc(view)}"
    >
      ← Volver al panel
    </a>
    """

    return HTMLResponse(
        page_html(
            title="Detalle de grupo",
            hero_title="Detalle del grupo",
            hero_subtitle=group_jid,
            hero_actions=hero_actions,
            body=body,
        )
    )


@router.get("/panel/api/summary")
def panel_api_summary(
    token: str = Depends(require_panel_token),
    db: Session = Depends(get_db),
):
    cfe = dict(db.execute(select(CfeRequest.status, func.count(CfeRequest.id)).group_by(CfeRequest.status)).all())
    renapo = dict(db.execute(select(RenapoRequest.status, func.count(RenapoRequest.id)).group_by(RenapoRequest.status)).all())
    return {
        "ok": True,
        "cfe": cfe,
        "renapo": renapo,
        "queues": [_queue_info(cfe_queue), _queue_info(renapo_queue)],
    }
