import html


def _e(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def render_main_panel(
    *,
    token,
    view,
    date_from,
    date_to,
    summary,
    groups,
    recent,
    providers,
    provider_stats,
    queue_rows,
    evolution_rows,
):
    provider_cards = []

    for p in providers:
        active = bool(
            getattr(
                p,
                "is_enabled",
                False,
            )
        )

        provider_name = str(
            getattr(
                p,
                "provider_name",
                "",
            )
            or ""
        ).strip()

        stats = (
            provider_stats.get(
                provider_name,
                {},
            )
        )

        total = int(
            stats.get(
                "total",
                0,
            )
            or 0
        )

        done = int(
            stats.get(
                "done",
                0,
            )
            or 0
        )

        pending = int(
            stats.get(
                "pending",
                0,
            )
            or 0
        )

        errors = int(
            stats.get(
                "errors",
                0,
            )
            or 0
        )

        no_record = int(
            stats.get(
                "no_record",
                0,
            )
            or 0
        )

        deregistered = int(
            stats.get(
                "deregistered",
                0,
            )
            or 0
        )

        provider_cards.append(
            f'<div class="provider-card">'

            f'<div class="provider-name">'
            f'{_e(getattr(p, "display_name", "Proveedor"))}'
            f'</div>'

            f'<div class="helper">'
            f'Código: {_e(provider_name)}'
            f'</div>'

            f'<div class="helper">'
            f'Prioridad: {_e(getattr(p, "priority", ""))}'
            f'</div>'

            f'<div class="provider-count-grid">'

            f'<div class="provider-count-box">'
            f'<span>Solicitudes</span>'
            f'<strong>{total}</strong>'
            f'</div>'

            f'<div class="provider-count-box">'
            f'<span>Entregadas</span>'
            f'<strong>{done}</strong>'
            f'</div>'

            f'<div class="provider-count-box">'
            f'<span>Pendientes</span>'
            f'<strong>{pending}</strong>'
            f'</div>'

            f'<div class="provider-count-box">'
            f'<span>Errores</span>'
            f'<strong>{errors}</strong>'
            f'</div>'

            f'</div>'

            f'<div class="helper provider-secondary-counts">'
            f'Sin recibo: {no_record}'
            f' · Dados de baja: {deregistered}'
            f'</div>'

            f'<div class="status-panel">'

            f'<strong style="color:'
            f'{"#86efac" if active else "#fca5a5"}'
            f'">'

            f'{"ACTIVO" if active else "INACTIVO"}'

            f'</strong>'
            f'</div>'

            f'<form method="post" '
            f'action="/panel/providers/'
            f'{getattr(p, "id", "")}'
            f'/toggle?token={_e(token)}">'

            f'<button class="btn '
            f'{"btn-danger" if active else "btn-success"}">'

            f'{"Desactivar" if active else "Activar"}'

            f'</button>'
            f'</form>'

            f'</div>'
        )
    if not provider_cards:
        provider_cards.append('<div class="provider-card"><div class="provider-name">Sin proveedores</div><div class="helper">Agrega Proveedores desde el panel de proveedores.</div></div>')

    group_rows = []
    for g in groups:
        blocked = bool(g.get("blocked"))
        cl, cu = int(g.get("cfe_limit") or 0), int(g.get("cfe_used") or 0)
        rl, ru = int(g.get("renapo_limit") or 0), int(g.get("renapo_used") or 0)
        group_rows.append(
            f'<tr><td><strong>{_e(g.get("group_name"))}</strong><div class="small mono">{_e(g.get("group_jid"))}</div><div class="small">{_e(g.get("owner_instance"))}</div></td>'
            f'<td>{g.get("total",0)}</td><td>{g.get("done",0)}</td><td>{g.get("cfe",0)}</td><td>{g.get("renapo",0)}</td>'
            f'<td>{cu}/{cl or "∞"}<div class="small">Disponible: {"∞" if cl == 0 else max(0, cl-cu)}</div></td>'
            f'<td>{ru}/{rl or "∞"}<div class="small">Disponible: {"∞" if rl == 0 else max(0, rl-ru)}</div></td>'
            f'<td><span class="badge {"badge-danger" if blocked else "badge-success"}">{"BLOQUEADO" if blocked else "ACTIVO"}</span></td>'
            f'<td>{_e(g.get("last_update") or "")}</td>'
            f'<td><div class="actions-row"><a class="btn btn-primary" href="/panel/group-detail?token={_e(token)}&group_jid={_e(g.get("group_jid"))}&view={_e(view)}">Solicitudes</a>'
            f'<form method="post" action="/panel/group/{_e(g.get("group_jid"))}/toggle?token={_e(token)}"><button class="btn {"btn-success" if blocked else "btn-danger"}">{"Desbloquear" if blocked else "Bloquear"}</button></form></div></td></tr>'
        )

    recent_rows = []
    for r in recent:
        status = (r.get("status") or "").upper()
        cls = "badge-success" if status == "DONE" else "badge-danger" if status == "ERROR" else "badge-warning"
        recent_rows.append(
            f'<tr>'
            f'<td>{_e(r.get("module"))}</td>'
            f'<td>{_e(r.get("id"))}</td>'
            f'<td class="mono">{_e(r.get("identifier"))}</td>'
            f'<td><span class="badge {cls}">{_e(status)}</span></td>'
            f'<td>'
            f'<strong>{_e(r.get("group_name") or r.get("group_jid"))}</strong>'
            f'<div class="small mono">{_e(r.get("group_jid"))}</div>'
            f'</td>'
            f'<td>{_e(r.get("instance"))}</td>'
            f'<td>{_e(r.get("created_at"))}</td>'
            f'<td class="small">{_e(r.get("error"))}</td>'
            f'</tr>'
        )

    qrows = ''.join(f'<tr><td>{_e(q.get("name"))}</td><td>{_e(q.get("queued","-"))}</td><td>{_e(q.get("started","-"))}</td><td>{_e(q.get("failed","-"))}</td><td>{_e(q.get("finished","-"))}</td></tr>' for q in queue_rows)
    erows = ''.join(f'<tr><td>{_e(x.get("instance_name"))}</td><td><span class="badge {"badge-success" if x.get("state") == "open" else "badge-danger"}">{_e(x.get("state","unknown")).upper()}</span></td><td>{_e(x.get("role"))}</td></tr>' for x in evolution_rows)

    css = r'''
:root{--bg:#f4f6f8;--card:#fff;--text:#1f2937;--muted:#6b7280;--line:#e5e7eb;--primary:#334155;--primary-dark:#1e293b;--success:#166534;--warning:#a16207;--danger:#991b1b;--shadow:0 8px 24px rgba(15,23,42,.07);--radius:18px}*{box-sizing:border-box}body{margin:0;font-family:Arial,sans-serif;background:var(--bg);color:var(--text)}.wrap{max-width:1500px;margin:auto;padding:16px}.hero{background:linear-gradient(135deg,#1f2937 0%,#334155 55%,#475569 100%);color:#fff;border-radius:24px;padding:22px;margin-bottom:18px;box-shadow:var(--shadow)}.hero-top{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap}.hero h1{margin:0 0 8px;font-size:1.9rem}.hero-sub{color:rgba(255,255,255,.88)}.toolbar{margin-top:16px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}.toolbar-divider{width:2px;height:34px;background:rgba(255,255,255,.55);margin:0 8px;border-radius:999px}.tool-link{text-decoration:none;padding:10px 16px;border-radius:12px;background:rgba(255,255,255,.10);color:#fff;font-weight:700;border:1px solid rgba(255,255,255,.14)}.tool-link-active{background:#fff;color:var(--primary-dark);border-color:#fff}.grid-hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.35fr);gap:16px;margin-top:18px;align-items:stretch}.glass{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.10);border-radius:20px;padding:18px;backdrop-filter:blur(8px)}.section-title{margin:0 0 14px;font-size:1rem;font-weight:800}.provider-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr));gap:12px}.provider-card{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);border-radius:16px;padding:14px}.provider-name{font-weight:800;margin-bottom:10px}.provider-count-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:14px}.provider-count-box{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.10);border-radius:12px;padding:10px}.provider-count-box span{display:block;color:rgba(255,255,255,.76);font-size:.72rem;margin-bottom:5px}.provider-count-box strong{display:block;color:#fff;font-size:1.25rem}.provider-secondary-counts{margin-top:10px}.helper{color:rgba(255,255,255,.82);font-size:.86rem;line-height:1.45}.status-panel{margin:14px 0;padding:12px;border-radius:14px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.10)}.broadcast-header{display:flex;justify-content:space-between;gap:16px;align-items:end;flex-wrap:wrap}.broadcast-select,.textarea{width:100%;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.08);color:#fff;border-radius:12px;padding:11px 12px;font:inherit}.broadcast-select option{color:#111827;background:#fff}.broadcast-buttons{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:16px}.textarea{background:#fff;color:#111827;min-height:130px;margin-top:12px}.box{background:#fff;border-radius:18px;box-shadow:var(--shadow);overflow:hidden;margin-bottom:16px;border:1px solid #eef2f7}.head{padding:16px 18px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;background:#fafbfc}.manual-group-form{display:grid;grid-template-columns:minmax(260px,1.2fr) minmax(260px,1.2fr) minmax(180px,.7fr) minmax(180px,.7fr);gap:10px;padding:16px;align-items:end}.manual-group-form .field{display:flex;flex-direction:column;gap:7px}.manual-group-form label{color:var(--muted);font-size:.84rem;font-weight:700}.manual-group-form input,.manual-group-form select{width:100%;min-height:44px;padding:11px 12px;border:1px solid #d1d5db;border-radius:12px;background:#fff;color:var(--text);font:inherit}.manual-group-action{display:flex}.manual-group-action .btn{width:100%;min-height:44px}.filters{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;padding:16px}.filters input,.filters select{width:100%;padding:11px 12px;border:1px solid #d1d5db;border-radius:12px;font:inherit;background:#fff}.cards{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin-bottom:16px}.card{background:#fff;border-radius:18px;padding:16px;box-shadow:var(--shadow);border:1px solid var(--line);position:relative}.card::before{content:"";position:absolute;top:0;left:0;right:0;height:4px;border-radius:18px 18px 0 0;background:#cbd5e1}.label{color:var(--muted);font-size:.88rem;margin-bottom:8px;font-weight:700;text-transform:uppercase}.value{font-size:1.9rem;font-weight:800}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;min-width:1100px}th,td{padding:12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:#1f2937;color:#fff;position:sticky;top:0}.small{color:var(--muted);font-size:.84rem}.mono{font-family:Consolas,monospace}.actions-row{display:flex;flex-wrap:wrap;gap:8px}.btn{border:0;border-radius:12px;padding:10px 14px;font-weight:800;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;justify-content:center}.btn-primary{background:var(--primary);color:#fff}.btn-success{background:var(--success);color:#fff}.btn-danger{background:var(--danger);color:#fff}.btn-warning{background:var(--warning);color:#fff}.badge{display:inline-flex;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700}.badge-success{background:#dcfce7;color:#166534}.badge-warning{background:#fff7ed;color:#c2410c}.badge-danger{background:#fef2f2;color:#b91c1c}@media(max-width:1100px){.grid-hero{grid-template-columns:1fr}.cards{grid-template-columns:repeat(2,1fr)}.filters{grid-template-columns:repeat(2,1fr)}.manual-group-form{grid-template-columns:repeat(2,1fr)}}@media(max-width:640px){.cards,.filters,.broadcast-buttons,.manual-group-form{grid-template-columns:1fr}.toolbar-divider{width:100%;height:1px;margin:3px 0}}
'''
    selected_day = (
        "selected"
        if view == "day"
        else ""
    )

    selected_30d = (
        "selected"
        if view == "30d"
        else ""
    )

    selected_month = (
        "selected"
        if view == "month"
        else ""
    )

    selected_prev_month = (
        "selected"
        if view == "prev_month"
        else ""
    )

    selected_custom = (
        "selected"
        if view == "custom"
        else ""
    )

    active_view = str(
        view
        or "day"
    ).strip().lower()

    def period_link_class(
        target_view: str,
    ) -> str:
        if active_view == target_view:
            return (
                "tool-link "
                "tool-link-active"
            )

        return "tool-link"

    return f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Panel Trámites Extras</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head><body><div class="wrap">
<section class="hero"><div class="hero-top"><div><h1>Panel de Trámites Extras</h1><div class="hero-sub">CFE, IMSS y RENAPO · America/Monterrey</div></div><div class="toolbar">     <a         class="{period_link_class('day')}"         href="/panel?token={_e(token)}&view=day"     >         Hoy     </a>      <a         class="{period_link_class('30d')}"         href="/panel?token={_e(token)}&view=30d"     >         30 días     </a>      <a         class="{period_link_class('month')}"         href="/panel?token={_e(token)}&view=month"     >         Mes actual     </a>      <a         class="{period_link_class('prev_month')}"         href="/panel?token={_e(token)}&view=prev_month"     >         Mes anterior     </a>      <span         class="toolbar-divider"         aria-hidden="true"     ></span>      <a         class="tool-link"         href="/panel/bots?token={_e(token)}"     >         Bots / mini paneles     </a>      <a         class="tool-link"         href="/panel/providers?token={_e(token)}"     >         Proveedores     </a> </div></div><div class="grid-hero"><div class="glass"><div class="section-title">Proveedores</div><div class="provider-grid">{''.join(provider_cards)}</div></div><div class="glass">   <form     method="post"     action="/panel/broadcast?token={_e(token)}"     class="broadcast-form"     onsubmit="return confirmMainBroadcast(this)"   >     <div class="broadcast-header">       <div>         <div class="section-title">           Mensajes masivos         </div>          <div class="helper">           Se enviará desde tramitesextras           únicamente a sus grupos activos.         </div>       </div>        <div style="min-width:240px">         <label class="helper">           Enviar a         </label>          <select           class="broadcast-select"           disabled         >           <option>             Grupos de tramitesextras           </option>         </select>       </div>     </div>      <div class="broadcast-buttons">       <button         class="btn btn-success"         type="button"         onclick="setMainBroadcastMessage(           '✅ El servicio se encuentra activo y funcionando con normalidad.'         )"       >         Servicio activo       </button>        <button         class="btn btn-warning"         type="button"         onclick="setMainBroadcastMessage(           '✅ El servicio ha sido restablecido y ya se encuentra disponible.'         )"       >         Servicio restablecido       </button>        <button         class="btn btn-danger"         type="button"         onclick="setMainBroadcastMessage(           '⚠️ El servicio se encuentra temporalmente suspendido. Avisaremos cuando sea restablecido.'         )"       >         Servicio suspendido       </button>     </div>      <textarea       id="mainBroadcastText"       class="textarea"       name="message"       maxlength="3500"       placeholder="Escribe aquí el mensaje que deseas enviar..."       required     ></textarea>      <button       class="btn btn-primary"       style="margin-top:10px"       type="submit"     >       Enviar mensaje     </button>   </form> </div></div></section>
<div class="cards"><div class="card"><div class="label">Solicitudes</div><div class="value">{summary.get('total',0)}</div></div><div class="card"><div class="label">Entregadas</div><div class="value">{summary.get('done',0)}</div></div><div class="card"><div class="label">CFE</div><div class="value">{summary.get('cfe_done',0)}</div></div><div class="card"><div class="label">RENAPO</div><div class="value">{summary.get('renapo_done',0)}</div></div><div class="card"><div class="label">Errores</div><div class="value">{summary.get('errors',0)}</div></div></div>
<section class="box">
  <div class="head">
    <strong>
      Agregar grupo manualmente
    </strong>

    <span class="small">
      Registra un grupo cliente para la instancia tramitesextras.
    </span>
  </div>

  <form
    method="post"
    action="/panel/groups/add?token={_e(token)}"
    class="manual-group-form"
  >
    <div class="field">
      <label>
        Group JID
      </label>

      <input
        type="text"
        name="group_jid"
        placeholder="1203634XXXXXXXXXXX@g.us"
        autocomplete="off"
        required
      >
    </div>

    <div class="field">
      <label>
        Nombre del grupo
      </label>

      <input
        type="text"
        name="custom_name"
        placeholder="Nombre del grupo"
        autocomplete="off"
      >
    </div>

    <div class="field">
      <label>
        Categoría
      </label>

      <select name="category">
        <option value="CFE">
          CFE
        </option>

        <option value="RENAPO">
          RENAPO
        </option>

        <option value="IMSS">
          IMSS
        </option>

        <option value="MULTI">
          Multi
        </option>

        <option value="PRUEBAS">
          Pruebas
        </option>

        <option
          value="Otro"
          selected
        >
          Otro
        </option>
      </select>
    </div>

    <div class="manual-group-action">
      <button
        type="submit"
        class="btn btn-primary"
      >
        Agregar grupo
      </button>
    </div>
  </form>
</section>
<section class="box"><div class="head"><strong>Filtros</strong><span class="small">Zona horaria: America/Monterrey</span></div><form method="get" class="filters"><input type="hidden" name="token" value="{_e(token)}"><select name="view"><option value="day" {selected_day}>Hoy</option><option value="30d" {selected_30d}>30 días</option><option value="month" {selected_month}>Mes actual</option><option value="prev_month" {selected_prev_month}>Mes anterior</option><option value="custom" {selected_custom}>Personalizado</option></select><input type="date" name="date_from" value="{_e(date_from)}"><input type="date" name="date_to" value="{_e(date_to)}"><input value="Todos los grupos" disabled><button class="btn btn-primary">Aplicar</button></form></section>
<section class="box"><div class="head"><strong>Resumen por grupo cliente</strong><span class="small">{len(groups)} grupos</span></div><div class="table-wrap"><table><thead><tr><th>Grupo</th><th>Total</th><th>Entregadas</th><th>CFE</th><th>RENAPO</th><th>Bolsa CFE</th><th>Bolsa RENAPO</th><th>Estado</th><th>Actualización</th><th>Acciones</th></tr></thead><tbody>{''.join(group_rows) or '<tr><td colspan="10">Sin grupos.</td></tr>'}</tbody></table></div></section>
<section class="box"><div class="head"><strong>Solicitudes recientes</strong></div><div class="table-wrap"><table><thead><tr><th>Módulo</th><th>ID</th><th>Dato</th><th>Estado</th><th>Grupo</th><th>Instancia</th><th>Creado</th><th>Error</th></tr></thead><tbody>{''.join(recent_rows) or '<tr><td colspan="8">Sin solicitudes.</td></tr>'}</tbody></table></div></section>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px"><section class="box"><div class="head"><strong>Colas RQ</strong></div><div class="table-wrap"><table style="min-width:600px"><thead><tr><th>Cola</th><th>En cola</th><th>Activos</th><th>Fallidos</th><th>Finalizados</th></tr></thead><tbody>{qrows}</tbody></table></div></section><section class="box"><div class="head"><strong>Instancias Evolution</strong></div><div class="table-wrap"><table style="min-width:500px"><thead><tr><th>Instancia</th><th>Estado</th><th>Rol</th></tr></thead><tbody>{erows}</tbody></table></div></section></div>
</div>
<script>
function setMainBroadcastMessage(message) {{
    const textarea = document.getElementById(
        "mainBroadcastText"
    );

    if (!textarea) {{
        return;
    }}

    textarea.value = message;
    textarea.focus();
}}

function confirmMainBroadcast(form) {{
    const textarea = form.querySelector(
        'textarea[name="message"]'
    );

    const message = (
        textarea?.value
        || ""
    ).trim();

    if (!message) {{
        alert(
            "Escribe un mensaje antes de enviarlo."
        );

        return false;
    }}

    return window.confirm(
        "¿Enviar este mensaje a todos los grupos activos de tramitesextras?"
    );
}}
</script>
</body>
</html>'''
