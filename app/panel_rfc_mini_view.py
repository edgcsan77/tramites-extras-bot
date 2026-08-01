import html
from datetime import timezone
from zoneinfo import ZoneInfo


def _e(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def _fmt_dt(value):
    if not value:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo("America/Monterrey")).strftime("%Y-%m-%d %H:%M:%S")


def render_mini_panel(*, panel_token, bot, view, date_from, date_to, summary, groups, recent,
                      period_summaries, group_period_counts, recharge_logs):
    cl = int(getattr(bot, "cfe_limit", 0) or 0)
    cu = int(getattr(bot, "cfe_used", 0) or 0)
    rl = int(getattr(bot, "renapo_limit", 0) or 0)
    ru = int(getattr(bot, "renapo_used", 0) or 0)
    ca = "∞" if cl == 0 else max(0, cl - cu)
    ra = "∞" if rl == 0 else max(0, rl - ru)
    title = _e(getattr(bot, "display_name", "Bot"))
    blocked = bool(getattr(bot, "is_blocked", False))
    blocked_groups = sum(1 for g in groups if bool(getattr(g, "is_blocked", False)))
    active_bags = sum(1 for g in groups if int(getattr(g, "cfe_limit", 0) or 0) > 0 or int(getattr(g, "renapo_limit", 0) or 0) > 0)

    rows = []
    for g in groups:
        jid = str(getattr(g, "group_jid", "") or "")
        gblocked = bool(getattr(g, "is_blocked", False))
        gl_cfe = int(getattr(g, "cfe_limit", 0) or 0)
        gu_cfe = int(getattr(g, "cfe_used", 0) or 0)
        gl_ren = int(getattr(g, "renapo_limit", 0) or 0)
        gu_ren = int(getattr(g, "renapo_used", 0) or 0)
        rows.append(f'''
        <tr>
          <td><strong>{_e(getattr(g,"custom_name",None) or jid)}</strong><div class="small mono">{_e(jid)}</div></td>
          <td>{group_period_counts.get("day",{}).get(jid,0)}</td>
          <td>{group_period_counts.get("30d",{}).get(jid,0)}</td>
          <td>{group_period_counts.get("month",{}).get(jid,0)}</td>
          <td>{group_period_counts.get("prev_month",{}).get(jid,0)}</td>
          <td><strong>CFE:</strong> {gu_cfe}/{gl_cfe or "∞"}<br><strong>RENAPO:</strong> {gu_ren}/{gl_ren or "∞"}</td>
          <td><span class="badge {'badge-danger' if gblocked else 'badge-success'}">{'BLOQUEADO' if gblocked else 'ACTIVO'}</span></td>
          <td><div class="request-links"><a href="/botpanel/{_e(panel_token)}?view=day">Hoy</a><a class="green" href="/botpanel/{_e(panel_token)}?view=30d">30 días</a><a href="/botpanel/{_e(panel_token)}?view=month">Mes actual</a><a class="green" href="/botpanel/{_e(panel_token)}?view=prev_month">Mes anterior</a></div></td>
          <td><form method="post" action="/botpanel/{_e(panel_token)}/group/{_e(jid)}/rename" class="rename-form"><input name="custom_name" value="{_e(getattr(g,'custom_name',None) or '')}" placeholder="Nuevo nombre"><button class="btn btn-blue">Guardar</button></form></td>
          <td><form method="post" action="/botpanel/{_e(panel_token)}/group/{_e(jid)}/toggle"><button class="btn {'btn-green' if gblocked else 'btn-red'}">{'Desbloquear' if gblocked else 'Bloquear'}</button></form><form method="post" action="/botpanel/{_e(panel_token)}/group/{_e(jid)}/hide"><button class="btn btn-soft">Ocultar</button></form></td>
        </tr>''')

    recharge_rows = []
    for log in recharge_logs:
        available = "∞" if int(getattr(log, "new_limit", 0) or 0) == 0 else max(0, int(log.new_limit or 0)-int(log.used_at_recharge or 0))
        recharge_rows.append(f'''<tr><td>{_fmt_dt(getattr(log,"created_at",None))}</td><td><strong class="plus">+{int(getattr(log,"amount",0) or 0)}</strong></td><td>{_e(getattr(log,"product", ""))}</td><td>{int(getattr(log,"previous_limit",0) or 0)}</td><td>{int(getattr(log,"new_limit",0) or 0)}</td><td>{int(getattr(log,"used_at_recharge",0) or 0)}</td><td>{available}</td><td>mini panel</td></tr>''')

    recent_rows = "".join(
        f'<tr>'
        f'<td>{_e(r.get("module"))}</td>'
        f'<td class="mono">{_e(r.get("identifier"))}</td>'
        f'<td>{_e(r.get("status"))}</td>'
        f'<td>'
        f'<strong>{_e(r.get("group_name") or r.get("group_jid"))}</strong>'
        f'<div class="small mono">{_e(r.get("group_jid"))}</div>'
        f'</td>'
        f'<td>{_e(r.get("created_at"))}</td>'
        f'<td>{_e(r.get("error"))}</td>'
        f'</tr>'
        for r in recent
    )
    css = r'''
    :root{--bg:#f4f6f8;--card:#fff;--text:#111827;--muted:#64748b;--line:#dfe5ec;--navy:#111c30;--navy2:#34445a;--green:#137333;--red:#c61c1c;--blue:#2458d8;--shadow:0 7px 22px rgba(15,23,42,.07)}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);font-family:Arial,sans-serif;color:var(--text)}.wrap{max-width:1400px;margin:auto;padding:16px}.hero{background:linear-gradient(135deg,#111c30,#34445a);color:#fff;border-radius:18px;padding:22px;margin-bottom:16px}.hero h1{margin:0 0 8px;font-size:2rem}.hero p{margin:0}.cards{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin-bottom:16px}.cards.bags{grid-template-columns:repeat(6,minmax(0,1fr))}.card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:16px;min-height:104px}.label{font-size:.82rem;color:var(--muted);margin-bottom:10px}.value{font-size:1.85rem;font-weight:900}.state-value{font-size:1.35rem;font-weight:900}.box{background:#fff;border:1px solid var(--line);border-radius:16px;overflow:hidden;margin-bottom:16px}.head{padding:16px 18px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:12px;align-items:center}.head .helper{font-size:.8rem;color:var(--muted)}.content{padding:16px}.control-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.btn{border:0;border-radius:10px;padding:10px 14px;font-weight:800;cursor:pointer}.btn-red{background:var(--red);color:#fff}.btn-green{background:var(--green);color:#fff}.btn-blue{background:var(--blue);color:#fff}.btn-soft{background:#e5e7eb;color:#111827}.badge{display:inline-flex;padding:4px 10px;border-radius:999px;font-size:.75rem;font-weight:900}.badge-success{background:#dcfce7;color:#166534}.badge-danger{background:#fee2e2;color:#b91c1c}.add-form{display:grid;grid-template-columns:1.2fr 1.2fr auto;gap:10px}.add-form input,.rename-form input,textarea{width:100%;border:1px solid #cfd8e3;border-radius:10px;padding:11px;font:inherit}.broadcast textarea{min-height:120px;resize:vertical}.broadcast-actions{display:flex;gap:10px;margin-top:10px}.history-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.history-card{display:block;text-decoration:none;color:inherit;border-radius:15px;padding:16px;border:1px solid}.history-card.blue{background:#eff6ff;border-color:#bfdbfe}.history-card.green{background:#ecfdf5;border-color:#bbf7d0}.history-card.purple{background:#faf5ff;border-color:#e9d5ff}.history-card.orange{background:#fff7ed;border-color:#fed7aa}.history-card .k{font-size:.78rem;font-weight:900}.history-card h3{font-size:1.35rem;margin:8px 0}.small{font-size:.78rem;color:var(--muted)}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;min-width:1320px}th{background:#0f172a;color:#fff;padding:12px;text-align:left}td{padding:12px;border-bottom:1px solid var(--line);vertical-align:top}.mono{font-family:Consolas,monospace}.request-links{display:grid;gap:5px}.request-links a{display:inline-block;width:max-content;color:#fff;background:#2458d8;border-radius:8px;padding:5px 9px;text-decoration:none;font-size:.75rem;font-weight:800}.request-links a.green{background:#137333}.rename-form{display:flex;gap:8px}.plus{color:#087522}.top-actions{display:flex;gap:8px;flex-wrap:wrap}.top-actions a{color:#fff;text-decoration:none;background:#405069;border-radius:10px;padding:9px 13px;font-weight:800}.active-link{background:#fff!important;color:#111827!important}
    @media(max-width:1000px){.cards,.cards.bags{grid-template-columns:repeat(3,1fr)}.history-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:650px){.cards,.cards.bags,.history-grid,.add-form{grid-template-columns:1fr}.hero h1{font-size:1.5rem}}
    '''

    return f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Mini Panel {title}</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head><body><div class="wrap">
    <section class="hero"><h1>Mini Panel · {title}</h1><p>Gestión independiente de grupos, bolsas y entregas del bot {title}.</p></section>
    <section class="cards">
      <div class="card"><div class="label">Entregadas hoy</div><div class="value">{period_summaries['day'].get('done',0)}</div></div>
      <div class="card"><div class="label">Entregadas 30 días</div><div class="value">{period_summaries['30d'].get('done',0)}</div></div>
      <div class="card"><div class="label">Grupos</div><div class="value">{len(groups)}</div></div>
      <div class="card"><div class="label">Grupos bloqueados</div><div class="value">{blocked_groups}</div></div>
      <div class="card"><div class="label">Bolsas activas</div><div class="value">{active_bags}</div></div>
      <div class="card"><div class="label">Estado del bot</div><div class="state-value">{'APAGADO' if blocked else 'PRENDIDO'}</div><span class="badge {'badge-danger' if blocked else 'badge-success'}">{'BOT APAGADO' if blocked else 'BOT PRENDIDO'}</span></div>
    </section>
    <section class="cards bags">
      <div class="card"><div class="label">CFE límite</div><div class="value">{cl or '∞'}</div></div><div class="card"><div class="label">CFE usados</div><div class="value">{cu}</div></div><div class="card"><div class="label">CFE disponibles</div><div class="value">{ca}</div></div>
      <div class="card"><div class="label">RENAPO límite</div><div class="value">{rl or '∞'}</div></div><div class="card"><div class="label">RENAPO usados</div><div class="value">{ru}</div></div><div class="card"><div class="label">RENAPO disponibles</div><div class="value">{ra}</div></div>
    </section>
    <section class="box"><div class="head"><strong>Control del bot</strong><span class="helper">Apaga o prende temporalmente este bot sin cerrar sesión de WhatsApp.</span></div><div class="content control-row"><span>Estado actual:</span><span class="badge {'badge-danger' if blocked else 'badge-success'}">{'BOT APAGADO' if blocked else 'BOT PRENDIDO'}</span><form method="post" action="/botpanel/{_e(panel_token)}/bot/toggle"><button class="btn {'btn-green' if blocked else 'btn-red'}">{'Prender bot' if blocked else 'Apagar bot'}</button></form></div></section>
    <section class="box"><div class="head"><strong>Agregar grupo manualmente</strong><span class="helper">Registra un grupo para este bot y asígnale nombre visible.</span></div><div class="content"><form method="post" action="/botpanel/{_e(panel_token)}/group/add" class="add-form"><input name="group_jid" placeholder="120363000000000000@g.us" required><input name="custom_name" placeholder="Nombre visible del grupo"><button class="btn btn-blue">Agregar grupo</button></form></div></section>
    <section class="box broadcast"><div class="head"><strong>Mensajes masivos</strong><span class="helper">Enviar mensaje libre solo a grupos de {title}.</span></div><div class="content"><textarea id="broadcastText" placeholder="Escribe aquí el mensaje que deseas enviar..."></textarea><div class="broadcast-actions"><button class="btn btn-green" type="button" onclick="alert('La difusión de Extras todavía no está conectada.')">Enviar mensaje libre</button><button class="btn btn-soft" type="button" onclick="document.getElementById('broadcastText').value=''">Limpiar</button></div></div></section>
    <section class="box"><div class="head"><div><strong>Historial y evidencias</strong><div class="small">Consulta entregas, errores y movimientos de todos los grupos de {title}.</div></div><span class="badge badge-success">Mini panel</span></div><div class="content"><div class="history-grid"><a class="history-card blue" href="/botpanel/{_e(panel_token)}?view=day"><div class="k">HOY</div><h3>Historial diario</h3><div class="small">Entregas realizadas hoy</div></a><a class="history-card green" href="/botpanel/{_e(panel_token)}?view=30d"><div class="k">30 DÍAS</div><h3>Último mes</h3><div class="small">Entregas de todos los grupos</div></a><a class="history-card purple" href="/botpanel/{_e(panel_token)}?view=month"><div class="k">MES ACTUAL</div><h3>Corte mensual</h3><div class="small">Movimientos del mes</div></a><a class="history-card orange" href="/botpanel/{_e(panel_token)}?view=prev_month"><div class="k">MES ANTERIOR</div><h3>Histórico</h3><div class="small">Consulta el corte pasado</div></a></div></div></section>
    <section class="box"><div class="head"><strong>Grupos del bot</strong><span class="helper">Bloquea, renombra y administra bolsas CFE/RENAPO.</span></div><div class="table-wrap"><table><thead><tr><th>Grupo</th><th>Hoy</th><th>30 días</th><th>Mes actual</th><th>Mes anterior</th><th>Bolsas</th><th>Estado</th><th>Solicitudes</th><th>Renombrar</th><th>Acciones</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan="10">Sin grupos.</td></tr>'}</tbody></table></div></section>
    <section class="box"><div class="head"><strong>Historial de recargas</strong><span class="helper">Últimas 30 recargas aplicadas.</span></div><div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Recarga</th><th>Producto</th><th>Límite anterior</th><th>Nuevo límite</th><th>Usadas</th><th>Disponibles</th><th>Origen</th></tr></thead><tbody>{''.join(recharge_rows) or '<tr><td colspan="8">Sin recargas.</td></tr>'}</tbody></table></div></section>
    <section class="box"><div class="head"><strong>Historial del periodo</strong></div><div class="table-wrap"><table><thead><tr><th>Módulo</th><th>Dato</th><th>Estado</th><th>Grupo</th><th>Fecha</th><th>Error</th></tr></thead><tbody>{recent_rows or '<tr><td colspan="6">Sin movimientos.</td></tr>'}</tbody></table></div></section>
    </div></body></html>'''
