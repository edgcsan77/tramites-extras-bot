import html
import json
import secrets
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from redis import Redis
from rq import Queue
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import CfeRequest, RenapoRequest
from app.queue import cfe_queue, renapo_queue, redis_conn
from app.panel_theme import panel_css

router = APIRouter()
PANEL_TZ = ZoneInfo("America/Monterrey")


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


def _period_bounds(view: str, date_from: str = "", date_to: str = ""):
    now = datetime.now(PANEL_TZ)
    view = (view or "day").lower().strip()

    if view == "custom" and date_from:
        start = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=PANEL_TZ)
        end_src = date_to or date_from
        end = datetime.strptime(end_src, "%Y-%m-%d").replace(tzinfo=PANEL_TZ) + timedelta(days=1)
    elif view == "30d":
        start = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    elif view == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    elif view == "prev_month":
        end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        prev = end - timedelta(days=1)
        start = prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        view = "day"
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

    return start.astimezone(timezone.utc), end.astimezone(timezone.utc), view


def _fmt_dt(value) -> str:
    if not value:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(PANEL_TZ).strftime("%Y-%m-%d %H:%M:%S")


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


@router.get("/panel", response_class=HTMLResponse)
def panel_home(
    token: str = Depends(require_panel_token),
    view: str = "day",
    date_from: str = "",
    date_to: str = "",
    group_jid: str = "",
    status: str = "",
    module: str = "all",
    db: Session = Depends(get_db),
):
    time_min, time_max, view = _period_bounds(view, date_from, date_to)

    cfe_q = select(CfeRequest).where(
        CfeRequest.created_at >= time_min,
        CfeRequest.created_at < time_max,
    )
    if group_jid:
        cfe_q = cfe_q.where(CfeRequest.client_group_jid.ilike(f"%{group_jid.strip()}%"))
    if status:
        cfe_q = cfe_q.where(CfeRequest.status == status)
    cfe_rows = list(db.scalars(cfe_q.order_by(CfeRequest.created_at.desc())).all()) if module in {"all", "cfe"} else []

    renapo_q = select(RenapoRequest).where(
        RenapoRequest.created_at >= time_min,
        RenapoRequest.created_at < time_max,
    )
    if group_jid:
        renapo_q = renapo_q.where(RenapoRequest.client_group_jid.ilike(f"%{group_jid.strip()}%"))
    if status:
        renapo_q = renapo_q.where(RenapoRequest.status == status)
    renapo_rows = list(db.scalars(renapo_q.order_by(RenapoRequest.created_at.desc())).all()) if module in {"all", "renapo"} else []

    all_statuses = Counter([r.status for r in cfe_rows] + [r.status for r in renapo_rows])
    total = len(cfe_rows) + len(renapo_rows)
    done = all_statuses.get("DONE", 0)
    pending = sum(all_statuses.get(x, 0) for x in ("QUEUED", "PROCESSING", "WAITING_PROVIDER"))
    errors = all_statuses.get("ERROR", 0)
    no_record = all_statuses.get("NO_RECORD", 0)

    group_counts = Counter([r.client_group_jid for r in cfe_rows] + [r.client_group_jid for r in renapo_rows])
    recent = []
    for row in cfe_rows[:25]:
        recent.append((row.created_at, "CFE", row.id, row.service_number, row.status, row.client_group_jid, row.client_instance, row.requester_name, row.error_message))
    for row in renapo_rows[:25]:
        recent.append((row.created_at, "RENAPO", row.id, row.curp, row.status, row.client_group_jid, row.client_instance, "", row.error_message))
    recent.sort(key=lambda x: x[0] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    recent = recent[:30]

    cfe_queue_data = _queue_info(cfe_queue)
    renapo_queue_data = _queue_info(renapo_queue)
    instances = sorted((set(settings.cfe_client_instances) | {settings.provider_transport_instance}) - {''})

    query_base = f"token={_esc(token)}"
    period_buttons = (
        f'<a class="btn btn-green" '
        f'href="/panel/bots?token={_esc(token)}">'
        f'Bots / mini paneles</a> '
    
        f'<a class="btn btn-green" '
        f'href="/panel/providers?token={_esc(token)}">'
        f'Proveedores</a> '
        + " ".join([
            f'<a class="btn light" '
            f'href="/panel?{query_base}&view=day">'
            f'Hoy</a>',
    
            f'<a class="btn light" '
            f'href="/panel?{query_base}&view=30d">'
            f'30 días</a>',
    
            f'<a class="btn light" '
            f'href="/panel?{query_base}&view=month">'
            f'Mes actual</a>',
    
            f'<a class="btn light" '
            f'href="/panel?{query_base}&view=prev_month">'
            f'Mes anterior</a>',
        ])
    )

    groups_html = "".join(
        f"<tr><td class='mono'>{_esc(gid)}</td><td>{count}</td><td><a class='btn' href='/panel/group-detail?token={_esc(token)}&group_jid={_esc(gid)}&view={_esc(view)}'>Ver detalle</a></td></tr>"
        for gid, count in group_counts.most_common()
    ) or "<tr><td colspan='3'>Sin grupos en este periodo.</td></tr>"

    recent_html = "".join(
        f"<tr><td>{_esc(module_name)}</td><td>{rid}</td><td class='mono'>{_esc(identifier)}</td><td>{_status_badge(st)}</td><td class='mono'>{_esc(gid)}</td><td>{_esc(inst)}</td><td>{_esc(requester)}</td><td>{_fmt_dt(created)}</td><td class='small'>{_esc(error or '')}</td></tr>"
        for created, module_name, rid, identifier, st, gid, inst, requester, error in recent
    ) or "<tr><td colspan='9'>Sin solicitudes.</td></tr>"

    queue_html = "".join(
        f"<tr><td>{_esc(q.get('name'))}</td><td>{q.get('queued','-')}</td><td>{q.get('started','-')}</td><td>{q.get('failed','-')}</td><td>{q.get('finished','-')}</td><td class='small'>{_esc(q.get('error',''))}</td></tr>"
        for q in (cfe_queue_data, renapo_queue_data)
    )

    instance_html = "".join(
        f"<tr><td>{_esc(inst)}</td><td>{_status_badge(_evolution_state(inst))}</td><td>{'Transporte a proveedores' if inst == settings.provider_transport_instance else 'Cliente'}</td></tr>"
        for inst in instances
    )

    return HTMLResponse(f"""
    <!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Panel Trámites Extras</title><style>{_base_css()}</style></head>
    <body><div class="wrap">
      <section class="hero"><div class="hero-row"><div><h1>Panel Trámites Extras</h1><div class="subtitle">CFE y RENAPO · estructura visual basada en RFC Grupo 02</div></div><div>{period_buttons}</div></div>
        <div class="nav"><a class="btn" href="/docs">API</a><a class="btn" href="/health">Salud</a><a class="btn" href="/panel?{query_base}">Actualizar</a></div>
      </section>

      <section class="grid">
        <div class="stat"><span class="label">Solicitudes</span><strong>{total}</strong></div>
        <div class="stat"><span class="label">Entregadas</span><strong>{done}</strong></div>
        <div class="stat"><span class="label">Pendientes</span><strong>{pending}</strong></div>
        <div class="stat"><span class="label">Sin recibo</span><strong>{no_record}</strong></div>
        <div class="stat"><span class="label">Errores</span><strong>{errors}</strong></div>
      </section>

      <section class="box"><div class="head"><h3>Filtros</h3><span class="small">Zona horaria: America/Monterrey</span></div><div class="content">
        <form class="filters" method="get" action="/panel">
          <input type="hidden" name="token" value="{_esc(token)}">
          <select name="view"><option value="day" {'selected' if view=='day' else ''}>Hoy</option><option value="30d" {'selected' if view=='30d' else ''}>30 días</option><option value="month" {'selected' if view=='month' else ''}>Mes actual</option><option value="prev_month" {'selected' if view=='prev_month' else ''}>Mes anterior</option><option value="custom" {'selected' if view=='custom' else ''}>Personalizado</option></select>
          <input type="date" name="date_from" value="{_esc(date_from)}"><input type="date" name="date_to" value="{_esc(date_to)}">
          <input name="group_jid" placeholder="Grupo JID" value="{_esc(group_jid)}">
          <select name="module"><option value="all" {'selected' if module=='all' else ''}>Todos</option><option value="cfe" {'selected' if module=='cfe' else ''}>CFE</option><option value="renapo" {'selected' if module=='renapo' else ''}>RENAPO</option></select>
          <select name="status"><option value="">Todos los estados</option>{''.join(f'<option value="{_esc(s)}" {"selected" if status==s else ""}>{_esc(s)}</option>' for s in ['DONE','WAITING_PROVIDER','QUEUED','NO_RECORD','ERROR','DISABLED'])}</select>
          <button class="btn" type="submit">Aplicar</button>
        </form>
      </div></section>

      <div class="two">
        <section class="box"><div class="head"><h3>Colas RQ</h3></div><div class="table-wrap"><table><thead><tr><th>Cola</th><th>En cola</th><th>Activos</th><th>Fallidos</th><th>Finalizados</th><th>Error</th></tr></thead><tbody>{queue_html}</tbody></table></div></section>
        <section class="box"><div class="head"><h3>Instancias Evolution</h3></div><div class="table-wrap"><table><thead><tr><th>Instancia</th><th>Estado</th><th>Rol</th></tr></thead><tbody>{instance_html}</tbody></table></div></section>
      </div>

      <section class="box"><div class="head"><h3>Conteo por grupo</h3><span class="small">{len(group_counts)} grupos</span></div><div class="table-wrap"><table><thead><tr><th>Grupo</th><th>Solicitudes</th><th>Acción</th></tr></thead><tbody>{groups_html}</tbody></table></div></section>

      <section class="box"><div class="head"><h3>Solicitudes recientes</h3><span class="small">Máximo 30 registros</span></div><div class="table-wrap"><table><thead><tr><th>Módulo</th><th>ID</th><th>Dato</th><th>Estado</th><th>Grupo</th><th>Instancia</th><th>Solicitante</th><th>Creado</th><th>Error</th></tr></thead><tbody>{recent_html}</tbody></table></div></section>
    </div></body></html>
    """)


@router.get("/panel/group-detail", response_class=HTMLResponse)
def panel_group_detail(
    group_jid: str,
    token: str = Depends(require_panel_token),
    view: str = "month",
    date_from: str = "",
    date_to: str = "",
    db: Session = Depends(get_db),
):
    time_min, time_max, view = _period_bounds(view, date_from, date_to)
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
        day = _fmt_dt(r.created_at)[:10]
        daily[day]["total"] += 1; daily[day][r.status] += 1; daily[day]["cfe"] += 1
        movements.append((r.created_at, "CFE", r.id, r.service_number, r.status, r.client_instance, r.error_message))
    for r in renapo_rows:
        day = _fmt_dt(r.created_at)[:10]
        daily[day]["total"] += 1; daily[day][r.status] += 1; daily[day]["renapo"] += 1
        movements.append((r.created_at, "RENAPO", r.id, r.curp, r.status, r.client_instance, r.error_message))
    movements.sort(key=lambda x: x[0] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    daily_html = "".join(
        f"<tr><td>{_esc(day)}</td><td>{data['total']}</td><td>{data['cfe']}</td><td>{data['renapo']}</td><td>{data['DONE']}</td><td>{data['NO_RECORD']}</td><td>{data['ERROR']}</td></tr>"
        for day, data in sorted(daily.items())
    ) or "<tr><td colspan='7'>Sin movimientos.</td></tr>"
    move_html = "".join(
        f"<tr><td>{_esc(mod)}</td><td>{rid}</td><td class='mono'>{_esc(identifier)}</td><td>{_status_badge(st)}</td><td>{_esc(inst)}</td><td>{_fmt_dt(created)}</td><td class='small'>{_esc(error or '')}</td></tr>"
        for created, mod, rid, identifier, st, inst, error in movements
    ) or "<tr><td colspan='7'>Sin movimientos.</td></tr>"

    return HTMLResponse(f"""
    <!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Detalle de grupo</title><style>{_base_css()}</style></head><body><div class="wrap">
      <section class="hero"><a class="btn light" href="/panel?token={_esc(token)}&view={_esc(view)}">← Volver</a><h1 style="margin-top:14px">Detalle del grupo</h1><div class="subtitle mono">{_esc(group_jid)}</div></section>
      <section class="grid"><div class="stat"><span class="label">Total</span><strong>{len(movements)}</strong></div><div class="stat"><span class="label">CFE</span><strong>{len(cfe_rows)}</strong></div><div class="stat"><span class="label">RENAPO</span><strong>{len(renapo_rows)}</strong></div><div class="stat"><span class="label">Entregadas</span><strong>{sum(1 for x in movements if x[4]=='DONE')}</strong></div><div class="stat"><span class="label">Errores</span><strong>{sum(1 for x in movements if x[4]=='ERROR')}</strong></div></section>
      <section class="box"><div class="head"><h3>Corte diario</h3></div><div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Total</th><th>CFE</th><th>RENAPO</th><th>DONE</th><th>Sin registro</th><th>Error</th></tr></thead><tbody>{daily_html}</tbody></table></div></section>
      <section class="box"><div class="head"><h3>Movimientos</h3></div><div class="table-wrap"><table><thead><tr><th>Módulo</th><th>ID</th><th>Dato</th><th>Estado</th><th>Instancia</th><th>Creado</th><th>Error</th></tr></thead><tbody>{move_html}</tbody></table></div></section>
    </div></body></html>
    """)


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
