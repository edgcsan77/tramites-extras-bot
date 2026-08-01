import html
import secrets

from urllib.parse import quote

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

from app.broadcast_jobs import (
    send_instance_broadcast_job,
)

from app.config import settings
from app.db import get_db

from app.models import (
    AuthorizedGroup,
    CfeRequest,
    ProductRechargeLog,
    ProviderSetting,
    RenapoRequest,
)

from app.panel_data import (
    fmt_dt,
    main_panel_data,
    period_bounds,
)

from app.panel_rfc_main_view import render_main_panel

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
    group_view: str = "all",
    db: Session = Depends(get_db),
):
    time_min, time_max, view = period_bounds(
        view,
        date_from,
        date_to,
    )
    
    data = main_panel_data(
        db,
        time_min,
        time_max,
    )
    
    group_view = str(
        group_view
        or "all"
    ).strip().lower()

    if group_view not in {
        "all",
        "activity",
    }:
        group_view = "all"

    all_groups = list(
        data.get(
            "groups",
            [],
        )
    )

    if group_view == "activity":
        visible_groups = [
            group
            for group in all_groups
            if int(
                group.get(
                    "total",
                    0,
                )
                or 0
            ) > 0
        ]

    else:
        visible_groups = (
            all_groups
        )
    providers = list(db.scalars(select(ProviderSetting).order_by(ProviderSetting.priority, ProviderSetting.id)).all())
    instance_name = getattr(settings, "TRANSPORT_INSTANCE", None) or getattr(settings, "EVOLUTION_INSTANCE", None) or "tramitesextras"
    return HTMLResponse(
        render_main_panel(
            token=token,
            view=view,
            date_from=date_from,
            date_to=date_to,
            group_view=group_view,
            summary=data["summary"],
            groups=visible_groups,
            recent=data["recent"],
            providers=providers,
            provider_stats=data["providers"],
            queue_rows=[
                _queue_info(cfe_queue),
                _queue_info(renapo_queue),
            ],
            evolution_rows=[
                {
                    "instance_name": instance_name,
                    "state": _evolution_state(
                        instance_name
                    ),
                    "role": "Transporte a proveedores",
                }
            ],
        )
    )


@router.post(
    "/panel/groups/add"
)
def add_group_from_main_panel(
    group_jid: str = Form(...),
    custom_name: str = Form(""),
    category: str = Form("Otro"),
    token: str = Depends(
        require_panel_token
    ),
    db: Session = Depends(get_db),
):
    """
    Agrega o actualiza manualmente un grupo
    de la instancia principal tramitesextras.
    """

    group_jid = str(
        group_jid
        or ""
    ).strip()

    custom_name = str(
        custom_name
        or ""
    ).strip()

    category = str(
        category
        or "Otro"
    ).strip()

    if not group_jid.endswith(
        "@g.us"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "El Group JID debe terminar "
                "en @g.us."
            ),
        )

    valid_categories = {
        "CFE",
        "RENAPO",
        "IMSS",
        "MULTI",
        "PRUEBAS",
        "Otro",
    }

    if category not in valid_categories:
        category = "Otro"

    existing = db.scalar(
        select(
            AuthorizedGroup
        ).where(
            AuthorizedGroup.group_jid
            == group_jid
        )
    )

    if existing:
        if (
            existing.owner_instance
            != "tramitesextras"
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Este grupo ya pertenece "
                    "a la instancia "
                    f"{existing.owner_instance}."
                ),
            )

        if custom_name:
            existing.custom_name = (
                custom_name
            )

        existing.category = category
        existing.is_hidden = False
        existing.hidden_in_main = False
        existing.is_blocked = False

    else:
        db.add(
            AuthorizedGroup(
                group_jid=group_jid,
                owner_instance=
                    "tramitesextras",
                custom_name=(
                    custom_name
                    or None
                ),
                category=category,
                is_hidden=False,
                hidden_in_main=False,
                is_blocked=False,
            )
        )

    db.commit()

    return RedirectResponse(
        url=(
            "/panel"
            f"?token={quote(token)}"
            "&view=30d"
        ),
        status_code=303,
    )


@router.post(
    "/panel/broadcast"
)
def main_panel_broadcast(
    message: str = Form(...),
    token: str = Depends(
        require_panel_token
    ),
):
    """
    Encola un mensaje masivo para los grupos
    pertenecientes a tramitesextras.
    """

    message = str(
        message
        or ""
    ).strip()

    if not message:
        raise HTTPException(
            status_code=400,
            detail=(
                "Escribe el mensaje "
                "que deseas enviar."
            ),
        )

    if len(message) > 3500:
        raise HTTPException(
            status_code=400,
            detail=(
                "El mensaje no puede superar "
                "3500 caracteres."
            ),
        )

    job = cfe_queue.enqueue(
        send_instance_broadcast_job,
        kwargs={
            "instance_name":
                "tramitesextras",

            "message":
                message,
        },
        job_timeout=900,
        result_ttl=86400,
        failure_ttl=86400,
    )

    print(
        "EXTRAS_MAIN_BROADCAST_ENQUEUED",
        {
            "job_id":
                job.id,

            "instance":
                "tramitesextras",

            "message_length":
                len(message),
        },
        flush=True,
    )

    return RedirectResponse(
        url=(
            "/panel"
            f"?token={quote(token)}"
            "&view=day"
            "&broadcast=queued"
        ),
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
