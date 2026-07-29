import html
from urllib.parse import quote
from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.models import AuthorizedGroup, BotControl, BotRechargeLog, CfeRequest, ProviderSetting
from app.multibot import new_panel_token, normalize_instance
from app.services.evolution_admin import connect_instance, connection_state, create_instance, set_webhook

router = APIRouter()


def _admin(token: str = Query(default='')) -> str:
    if not token or token != settings.ADMIN_PANEL_TOKEN:
        raise HTTPException(403, 'No autorizado')
    return token


def _e(v): return html.escape(str(v if v is not None else ''), quote=True)
def _go(path, token): return RedirectResponse(f'{path}?token={quote(token)}', status_code=303)


@router.get('/panel/bots', response_class=HTMLResponse)
def bots_panel(token: str = Depends(_admin), db: Session = Depends(get_db)):
    bots = list(db.scalars(select(BotControl).order_by(BotControl.created_at.desc())).all())
    rows = []
    for b in bots:
        try: state = connection_state(b.instance_name)
        except Exception: state = 'unknown'
        available = '∞' if b.limit_total == 0 else max(0, b.limit_total - b.used_total)
        rows.append(f'''<tr><td>{_e(b.display_name)}</td><td><code>{_e(b.instance_name)}</code></td><td>{state}</td><td>{b.used_total}/{b.limit_total or '∞'} ({available})</td><td>{'BLOQUEADO' if b.is_blocked else 'ACTIVO'}</td><td><a href="/panel/instance/{_e(b.instance_name)}/qr?token={_e(token)}">QR</a> · <a href="/botpanel/{_e(b.panel_token)}">Mini panel</a><form method="post" action="/panel/instance/{_e(b.instance_name)}/toggle?token={_e(token)}" style="display:inline"><button>Bloquear/desbloquear</button></form><form method="post" action="/panel/instance/{_e(b.instance_name)}/recharge?token={_e(token)}" style="display:inline"><input name="amount" type="number" min="1" style="width:80px"><button>Recargar</button></form></td></tr>''')
    return HTMLResponse(f'''<!doctype html><meta charset="utf-8"><title>Bots Extras</title><style>body{{font-family:Arial;margin:24px;background:#f4f6f8}}.box{{background:white;padding:18px;border-radius:14px;margin-bottom:18px}}input{{padding:9px;margin:4px}}button{{padding:8px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #ddd;text-align:left}}</style><h1>Bots / mini paneles</h1><p><a href="/panel?token={_e(token)}">← Panel principal</a> · <a href="/panel/providers?token={_e(token)}">Proveedores</a></p><div class="box"><form method="post" action="/panel/bots/create?token={_e(token)}"><input name="display_name" placeholder="Nombre visible" required><input name="instance_name" placeholder="tramitesextrascliente" required><input name="limit_total" type="number" min="0" value="0"><button>Crear bot e instancia</button></form></div><div class="box"><table><tr><th>Nombre</th><th>Instancia</th><th>Estado</th><th>Uso</th><th>Control</th><th>Acciones</th></tr>{''.join(rows)}</table></div>''')


@router.post('/panel/bots/create')
def create_bot(display_name: str = Form(...), instance_name: str = Form(...), limit_total: int = Form(0), token: str = Depends(_admin), db: Session = Depends(get_db)):
    instance_name = normalize_instance(instance_name)
    if db.scalar(select(BotControl).where(BotControl.instance_name == instance_name)):
        raise HTTPException(409, 'La instancia ya está registrada')
    create_instance(instance_name)
    set_webhook(instance_name)
    db.add(BotControl(instance_name=instance_name, display_name=display_name.strip() or instance_name, panel_token=new_panel_token(), limit_total=max(0, limit_total)))
    db.commit()
    return _go('/panel/bots', token)


@router.get('/panel/instance/{instance_name}/qr', response_class=HTMLResponse)
def qr(instance_name: str, token: str = Depends(_admin)):
    data = connect_instance(instance_name)
    code = data.get('base64') or data.get('code') or data.get('qrcode', {}).get('base64') or ''
    image = f'<img style="max-width:420px" src="{_e(code)}">' if str(code).startswith('data:image') else f'<pre>{_e(data)}</pre>'
    return HTMLResponse(f'<meta charset="utf-8"><h1>QR {_e(instance_name)}</h1>{image}<p><a href="/panel/bots?token={_e(token)}">Volver</a></p>')


@router.post('/panel/instance/{instance_name}/toggle')
def toggle(instance_name: str, token: str = Depends(_admin), db: Session = Depends(get_db)):
    bot = db.scalar(select(BotControl).where(BotControl.instance_name == instance_name))
    if not bot: raise HTTPException(404, 'Bot no encontrado')
    bot.is_blocked = not bot.is_blocked; db.commit(); return _go('/panel/bots', token)


@router.post('/panel/instance/{instance_name}/recharge')
def recharge(instance_name: str, amount: int = Form(...), token: str = Depends(_admin), db: Session = Depends(get_db)):
    bot = db.scalar(select(BotControl).where(BotControl.instance_name == instance_name).with_for_update())
    if not bot: raise HTTPException(404, 'Bot no encontrado')
    if amount <= 0: raise HTTPException(400, 'Monto inválido')
    previous = bot.limit_total; bot.limit_total += amount
    db.add(BotRechargeLog(instance_name=instance_name, amount=amount, previous_limit=previous, new_limit=bot.limit_total, used_at_recharge=bot.used_total))
    db.commit(); return _go('/panel/bots', token)


@router.get('/panel/providers', response_class=HTMLResponse)
def providers_panel(token: str = Depends(_admin), db: Session = Depends(get_db)):
    providers = list(db.scalars(select(ProviderSetting).order_by(ProviderSetting.priority, ProviderSetting.id)).all())
    rows=''.join(f'''<tr><td>{_e(p.display_name)}</td><td>{_e(p.provider_name)}</td><td><code>{_e(p.group_jid)}</code></td><td>{p.priority}</td><td>{'ON' if p.is_enabled else 'OFF'}</td><td><form method="post" action="/panel/providers/{p.id}/toggle?token={_e(token)}"><button>ON/OFF</button></form></td></tr>''' for p in providers)
    return HTMLResponse(f'''<!doctype html><meta charset="utf-8"><style>body{{font-family:Arial;margin:24px}}input{{padding:9px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #ddd;text-align:left}}</style><h1>Proveedores CFE</h1><p>Los proveedores son grupos/configuraciones; aquí no se crean instancias.</p><p><a href="/panel/bots?token={_e(token)}">← Bots</a></p><form method="post" action="/panel/providers/create?token={_e(token)}"><input name="display_name" placeholder="Nombre visible" required><input name="provider_name" placeholder="clave_proveedor" required><input name="group_jid" placeholder="1203...@g.us" required><input name="priority" type="number" value="100"><button>Agregar proveedor</button></form><table><tr><th>Nombre</th><th>Clave</th><th>Grupo</th><th>Prioridad</th><th>Estado</th><th>Acción</th></tr>{rows}</table>''')


@router.post('/panel/providers/create')
def create_provider(display_name: str = Form(...), provider_name: str = Form(...), group_jid: str = Form(...), priority: int = Form(100), token: str = Depends(_admin), db: Session = Depends(get_db)):
    provider_name = normalize_instance(provider_name)
    group_jid = group_jid.strip()
    if not group_jid.endswith('@g.us'): raise HTTPException(400, 'group_jid inválido')
    db.add(ProviderSetting(provider_name=provider_name, display_name=display_name.strip(), group_jid=group_jid, priority=priority, module='CFE'))
    db.commit(); return _go('/panel/providers', token)


@router.post('/panel/providers/{provider_id}/toggle')
def toggle_provider(provider_id: int, token: str = Depends(_admin), db: Session = Depends(get_db)):
    p = db.get(ProviderSetting, provider_id)
    if not p: raise HTTPException(404, 'Proveedor no encontrado')
    p.is_enabled = not p.is_enabled; db.commit(); return _go('/panel/providers', token)


@router.get('/botpanel/{panel_token}', response_class=HTMLResponse)
def mini_panel(panel_token: str, db: Session = Depends(get_db)):
    bot = db.scalar(select(BotControl).where(BotControl.panel_token == panel_token, BotControl.is_active.is_(True)))
    if not bot: raise HTTPException(404, 'Mini panel no encontrado')
    groups = list(db.scalars(select(AuthorizedGroup).where(AuthorizedGroup.owner_instance == bot.instance_name, AuthorizedGroup.is_hidden.is_(False)).order_by(AuthorizedGroup.created_at.desc())).all())
    counts = dict(db.execute(select(CfeRequest.status, func.count()).where(CfeRequest.client_instance == bot.instance_name).group_by(CfeRequest.status)).all())
    available = 'Ilimitado' if bot.limit_total == 0 else str(max(0, bot.limit_total - bot.used_total))
    group_rows=''.join(f'<tr><td>{_e(g.custom_name or "")}</td><td><code>{_e(g.group_jid)}</code></td><td>{"Bloqueado" if g.is_blocked else "Activo"}</td></tr>' for g in groups)
    return HTMLResponse(f'''<!doctype html><meta charset="utf-8"><style>body{{font-family:Arial;margin:24px;background:#f4f6f8}}.box{{background:white;padding:18px;border-radius:14px;margin:12px 0}}table{{width:100%;border-collapse:collapse}}td,th{{padding:9px;border-bottom:1px solid #ddd}}</style><h1>{_e(bot.display_name)}</h1><div class="box">Instancia: <code>{_e(bot.instance_name)}</code><br>Usados: {bot.used_total}<br>Disponibles: {available}<br>Estado: {'BLOQUEADO' if bot.is_blocked else 'ACTIVO'}</div><div class="box"><h2>Solicitudes</h2><pre>{_e(counts)}</pre></div><div class="box"><h2>Grupos</h2><table><tr><th>Nombre</th><th>JID</th><th>Estado</th></tr>{group_rows}</table></div>''')
