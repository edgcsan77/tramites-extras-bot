import html
from urllib.parse import quote
from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.models import (
    AuthorizedGroup,
    BotControl,
    BotRechargeLog,
    CfeRequest,
    ProviderSetting,
    RenapoRequest,
)
from app.multibot import new_panel_token, normalize_instance
from app.services.evolution_admin import connect_instance, connection_state, create_instance, set_webhook
from app.panel_theme import (
    badge_html,
    page_html,
)

router = APIRouter()


def _admin(token: str = Query(default='')) -> str:
    if not token or token != settings.ADMIN_PANEL_TOKEN:
        raise HTTPException(403, 'No autorizado')
    return token


def _e(v): return html.escape(str(v if v is not None else ''), quote=True)
def _go(path, token): return RedirectResponse(f'{path}?token={quote(token)}', status_code=303)


@router.get(
    "/panel/bots",
    response_class=HTMLResponse,
)
def bots_panel(
    token: str = Depends(_admin),
    db: Session = Depends(get_db),
):
    bots = list(
        db.scalars(
            select(BotControl)
            .order_by(
                BotControl.created_at.desc()
            )
        ).all()
    )

    rows = []

    total_bots = len(bots)
    active_bots = 0
    blocked_bots = 0
    connected_bots = 0

    for bot in bots:
        try:
            state = connection_state(
                bot.instance_name
            )
        except Exception:
            state = "unknown"

        state = str(
            state or "unknown"
        ).strip().lower()

        if state == "open":
            connected_bots += 1
            state_badge = badge_html(
                "CONECTADO",
                "success",
            )
        elif state in {
            "close",
            "closed",
        }:
            state_badge = badge_html(
                "DESCONECTADO",
                "danger",
            )
        else:
            state_badge = badge_html(
                state.upper(),
                "muted",
            )

        if bot.is_blocked:
            blocked_bots += 1
            control_badge = badge_html(
                "BLOQUEADO",
                "danger",
            )
        else:
            active_bots += 1
            control_badge = badge_html(
                "ACTIVO",
                "success",
            )

        if bot.limit_total == 0:
            limit_text = "Ilimitado"
            available_text = "Ilimitado"
        else:
            limit_text = str(
                bot.limit_total
            )

            available_text = str(
                max(
                    0,
                    bot.limit_total
                    - bot.used_total,
                )
            )

        rows.append(
            f"""
            <tr>
              <td>
                <strong>
                  {_e(bot.display_name)}
                </strong>

                <div class="small">
                  Creado:
                  {_e(bot.created_at)}
                </div>
              </td>

              <td>
                <code>
                  {_e(bot.instance_name)}
                </code>
              </td>

              <td>
                {state_badge}
              </td>

              <td>
                <strong>
                  {bot.used_total}
                </strong>

                <div class="small">
                  Límite:
                  {_e(limit_text)}
                </div>

                <div class="small">
                  Disponible:
                  {_e(available_text)}
                </div>
              </td>

              <td>
                {control_badge}
              </td>

              <td>
                <div class="actions">
                  <a
                    class="btn btn-info btn-sm"
                    href="/panel/instance/{_e(bot.instance_name)}/qr?token={_e(token)}"
                  >
                    QR
                  </a>

                  <a
                    class="btn btn-primary btn-sm"
                    href="/botpanel/{_e(bot.panel_token)}"
                    target="_blank"
                  >
                    Mini panel
                  </a>

                  <form
                    method="post"
                    action="/panel/instance/{_e(bot.instance_name)}/toggle?token={_e(token)}"
                    class="inline-form"
                  >
                    <button
                      class="btn btn-sm {
                          'btn-success'
                          if bot.is_blocked
                          else 'btn-danger'
                      }"
                      type="submit"
                    >
                      {
                          'Desbloquear'
                          if bot.is_blocked
                          else 'Bloquear'
                      }
                    </button>
                  </form>

                  <form
                    method="post"
                    action="/panel/instance/{_e(bot.instance_name)}/recharge?token={_e(token)}"
                    class="inline-form"
                  >
                    <input
                      name="amount"
                      type="number"
                      min="1"
                      placeholder="Cantidad"
                      required
                    >

                    <button
                      class="btn btn-success btn-sm"
                      type="submit"
                    >
                      Recargar
                    </button>
                  </form>
                </div>
              </td>
            </tr>
            """
        )

    rows_html = (
        "".join(rows)
        if rows
        else (
            '<tr>'
            '<td colspan="6" class="empty">'
            'No hay bots registrados.'
            '</td>'
            '</tr>'
        )
    )

    body = f"""
    <section class="cards">
      <div class="card info">
        <span class="label">
          Bots registrados
        </span>

        <span class="value">
          {total_bots}
        </span>
      </div>

      <div class="card success">
        <span class="label">
          Bots activos
        </span>

        <span class="value">
          {active_bots}
        </span>
      </div>

      <div class="card danger">
        <span class="label">
          Bots bloqueados
        </span>

        <span class="value">
          {blocked_bots}
        </span>
      </div>

      <div class="card success">
        <span class="label">
          WhatsApp conectados
        </span>

        <span class="value">
          {connected_bots}
        </span>
      </div>
    </section>

    <section class="box">
      <div class="head">
        <div>
          <strong>
            Crear bot e instancia
          </strong>

          <div class="small">
            Crea la instancia de Evolution
            y genera su mini panel.
          </div>
        </div>
      </div>

      <div class="content">
        <form
          method="post"
          action="/panel/bots/create?token={_e(token)}"
          class="form-grid cols-3"
        >
          <div class="field">
            <label>
              Nombre visible
            </label>

            <input
              name="display_name"
              placeholder="Gestoría Cliente"
              required
            >
          </div>

          <div class="field">
            <label>
              Nombre de instancia
            </label>

            <input
              name="instance_name"
              placeholder="tramitesextrascliente"
              required
            >
          </div>

          <div class="field">
            <label>
              Límite inicial
            </label>

            <input
              name="limit_total"
              type="number"
              min="0"
              value="0"
            >
          </div>

          <div>
            <button
              class="btn btn-success"
              type="submit"
            >
              Crear bot
            </button>
          </div>
        </form>
      </div>
    </section>

    <section class="box">
      <div class="head">
        <strong>
          Bots y mini paneles
        </strong>

        <span class="small">
          Estado, consumo, QR y controles.
        </span>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Instancia</th>
              <th>WhatsApp</th>
              <th>Uso</th>
              <th>Control</th>
              <th>Acciones</th>
            </tr>
          </thead>

          <tbody>
            {rows_html}
          </tbody>
        </table>
      </div>
    </section>
    """

    actions = f"""
    <a
      class="btn btn-light"
      href="/panel?token={_e(token)}"
    >
      Panel principal
    </a>

    <a
      class="btn btn-light"
      href="/panel/providers?token={_e(token)}"
    >
      Proveedores
    </a>
    """

    return HTMLResponse(
        page_html(
            title="Bots Trámites Extras",
            hero_title=(
                "Bots y mini paneles"
            ),
            hero_subtitle=(
                "Control de instancias, "
                "límites y accesos independientes."
            ),
            hero_actions=actions,
            body=body,
        )
    )


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


@router.get(
    "/panel/instance/{instance_name}/qr",
    response_class=HTMLResponse,
)
def qr(
    instance_name: str,
    token: str = Depends(_admin),
):
    data = connect_instance(
        instance_name
    )

    code = (
        data.get("base64")
        or data.get("code")
        or (
            data.get("qrcode", {})
            or {}
        ).get("base64")
        or ""
    )

    if str(code).startswith(
        "data:image"
    ):
        qr_content = f"""
        <div class="qr-box">
          <img
            src="{_e(code)}"
            alt="Código QR"
          >

          <p class="small">
            Escanea el código desde
            WhatsApp para vincular
            la instancia.
          </p>
        </div>
        """
    else:
        qr_content = f"""
        <div class="empty">
          No se recibió una imagen QR.

          <pre class="mono">
            {_e(data)}
          </pre>
        </div>
        """

    body = f"""
    <section class="box">
      <div class="head">
        <strong>
          Vinculación de WhatsApp
        </strong>

        <span class="small">
          Instancia:
          {_e(instance_name)}
        </span>
      </div>

      <div class="content">
        {qr_content}
      </div>
    </section>
    """

    actions = f"""
    <a
      class="btn btn-light"
      href="/panel/bots?token={_e(token)}"
    >
      Volver a bots
    </a>
    """

    return HTMLResponse(
        page_html(
            title=(
                f"QR {instance_name}"
            ),
            hero_title=(
                "Conectar instancia"
            ),
            hero_subtitle=(
                instance_name
            ),
            hero_actions=actions,
            body=body,
        )
    )


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


@router.get(
    "/panel/providers",
    response_class=HTMLResponse,
)
def providers_panel(
    token: str = Depends(_admin),
    db: Session = Depends(get_db),
):
    providers = list(
        db.scalars(
            select(ProviderSetting)
            .order_by(
                ProviderSetting.priority,
                ProviderSetting.id,
            )
        ).all()
    )

    enabled_count = sum(
        1
        for provider in providers
        if provider.is_enabled
    )

    disabled_count = (
        len(providers)
        - enabled_count
    )

    rows = []

    for provider in providers:
        status_badge = badge_html(
            (
                "ACTIVO"
                if provider.is_enabled
                else "DESACTIVADO"
            ),
            (
                "success"
                if provider.is_enabled
                else "danger"
            ),
        )

        rows.append(
            f"""
            <tr>
              <td>
                <strong>
                  {_e(provider.display_name)}
                </strong>
              </td>

              <td>
                <code>
                  {_e(provider.provider_name)}
                </code>
              </td>

              <td>
                <code>
                  {_e(provider.group_jid)}
                </code>
              </td>

              <td>
                {provider.priority}
              </td>

              <td>
                {status_badge}
              </td>

              <td>
                <form
                  method="post"
                  action="/panel/providers/{provider.id}/toggle?token={_e(token)}"
                  class="inline-form"
                >
                  <button
                    class="btn btn-sm {
                        'btn-danger'
                        if provider.is_enabled
                        else 'btn-success'
                    }"
                    type="submit"
                  >
                    {
                        'Desactivar'
                        if provider.is_enabled
                        else 'Activar'
                    }
                  </button>
                </form>
              </td>
            </tr>
            """
        )

    rows_html = (
        "".join(rows)
        if rows
        else (
            '<tr>'
            '<td colspan="6" class="empty">'
            'No hay proveedores registrados.'
            '</td>'
            '</tr>'
        )
    )

    body = f"""
    <section class="cards">
      <div class="card info">
        <span class="label">
          Proveedores
        </span>

        <span class="value">
          {len(providers)}
        </span>
      </div>

      <div class="card success">
        <span class="label">
          Activos
        </span>

        <span class="value">
          {enabled_count}
        </span>
      </div>

      <div class="card danger">
        <span class="label">
          Desactivados
        </span>

        <span class="value">
          {disabled_count}
        </span>
      </div>
    </section>

    <section class="box">
      <div class="head">
        <div>
          <strong>
            Agregar proveedor CFE
          </strong>

          <div class="small">
            El proveedor es un grupo;
            no crea una instancia nueva.
          </div>
        </div>
      </div>

      <div class="content">
        <form
          method="post"
          action="/panel/providers/create?token={_e(token)}"
          class="form-grid cols-5"
        >
          <div class="field">
            <label>
              Nombre visible
            </label>

            <input
              name="display_name"
              placeholder="Proveedor CFE 1"
              required
            >
          </div>

          <div class="field">
            <label>
              Clave
            </label>

            <input
              name="provider_name"
              placeholder="proveedor_cfe_1"
              required
            >
          </div>

          <div class="field">
            <label>
              Grupo proveedor
            </label>

            <input
              name="group_jid"
              placeholder="120363...@g.us"
              required
            >
          </div>

          <div class="field">
            <label>
              Prioridad
            </label>

            <input
              name="priority"
              type="number"
              value="100"
            >
          </div>

          <div>
            <button
              class="btn btn-success"
              type="submit"
            >
              Agregar
            </button>
          </div>
        </form>
      </div>
    </section>

    <section class="box">
      <div class="head">
        <strong>
          Proveedores configurados
        </strong>

        <span class="small">
          Ordenados por prioridad.
        </span>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Clave</th>
              <th>Grupo</th>
              <th>Prioridad</th>
              <th>Estado</th>
              <th>Acción</th>
            </tr>
          </thead>

          <tbody>
            {rows_html}
          </tbody>
        </table>
      </div>
    </section>
    """

    actions = f"""
    <a
      class="btn btn-light"
      href="/panel?token={_e(token)}"
    >
      Panel principal
    </a>

    <a
      class="btn btn-light"
      href="/panel/bots?token={_e(token)}"
    >
      Bots
    </a>
    """

    return HTMLResponse(
        page_html(
            title="Proveedores CFE",
            hero_title="Proveedores CFE",
            hero_subtitle=(
                "Control de grupos proveedores "
                "y prioridades de atención."
            ),
            hero_actions=actions,
            body=body,
        )
    )


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


@router.get(
    "/botpanel/{panel_token}",
    response_class=HTMLResponse,
)
def mini_panel(
    panel_token: str,
    db: Session = Depends(get_db),
):
    bot = db.scalar(
        select(BotControl)
        .where(
            BotControl.panel_token
            == panel_token,

            BotControl.is_active
            .is_(True),
        )
    )

    if not bot:
        raise HTTPException(
            404,
            "Mini panel no encontrado",
        )

    groups = list(
        db.scalars(
            select(AuthorizedGroup)
            .where(
                AuthorizedGroup.owner_instance
                == bot.instance_name,

                AuthorizedGroup.is_hidden
                .is_(False),
            )
            .order_by(
                AuthorizedGroup.created_at.desc()
            )
        ).all()
    )

    cfe_counts = dict(
        db.execute(
            select(
                CfeRequest.status,
                func.count(),
            )
            .where(
                CfeRequest.client_instance
                == bot.instance_name
            )
            .group_by(
                CfeRequest.status
            )
        ).all()
    )

    renapo_counts = dict(
        db.execute(
            select(
                RenapoRequest.status,
                func.count(),
            )
            .where(
                RenapoRequest.client_instance
                == bot.instance_name
            )
            .group_by(
                RenapoRequest.status
            )
        ).all()
    )

    all_status_names = (
        set(cfe_counts)
        | set(renapo_counts)
    )

    counts = {
        status: (
            int(
                cfe_counts.get(status, 0)
                or 0
            )
            + int(
                renapo_counts.get(status, 0)
                or 0
            )
        )
        for status in all_status_names
    }

    total_requests = sum(
        int(value or 0)
        for value in counts.values()
    )

    done = int(
        counts.get("DONE", 0)
        or 0
    )

    pending = sum(
        int(
            counts.get(status, 0)
            or 0
        )
        for status in {
            "QUEUED",
            "PROCESSING",
            "WAITING_PROVIDER",
        }
    )

    no_record = int(
        counts.get("NO_RECORD", 0)
        or 0
    )

    errors = int(
        counts.get("ERROR", 0)
        or 0
    )

    blocked_groups = sum(
        1
        for group in groups
        if group.is_blocked
    )

    if bot.limit_total == 0:
        limit_text = "Ilimitado"
        available_text = "Ilimitado"
    else:
        limit_text = str(
            bot.limit_total
        )

        available_text = str(
            max(
                0,
                bot.limit_total
                - bot.used_total,
            )
        )

    bot_status_badge = badge_html(
        (
            "BOT BLOQUEADO"
            if bot.is_blocked
            else "BOT ACTIVO"
        ),
        (
            "danger"
            if bot.is_blocked
            else "success"
        ),
    )

    group_rows = []

    for group in groups:
        group_status = badge_html(
            (
                "BLOQUEADO"
                if group.is_blocked
                else "ACTIVO"
            ),
            (
                "danger"
                if group.is_blocked
                else "success"
            ),
        )

        group_rows.append(
            f"""
            <tr>
              <td>
                <strong>
                  {_e(
                      group.custom_name
                      or "Sin nombre"
                  )}
                </strong>
              </td>

              <td>
                <code>
                  {_e(group.group_jid)}
                </code>
              </td>

              <td>
                {group_status}
              </td>

              <td>
                {_e(group.created_at)}
              </td>
            </tr>
            """
        )

    groups_html = (
        "".join(group_rows)
        if group_rows
        else (
            '<tr>'
            '<td colspan="4" class="empty">'
            'Este bot todavía no tiene grupos.'
            '</td>'
            '</tr>'
        )
    )

    body = f"""
    <section class="cards">
      <div class="card info">
        <span class="label">
          Solicitudes
        </span>

        <span class="value">
          {total_requests}
        </span>
      </div>

      <div class="card success">
        <span class="label">
          Entregadas
        </span>

        <span class="value">
          {done}
        </span>
      </div>

      <div class="card warning">
        <span class="label">
          Pendientes
        </span>

        <span class="value">
          {pending}
        </span>
      </div>

      <div class="card warning">
        <span class="label">
          Sin recibo
        </span>

        <span class="value">
          {no_record}
        </span>
      </div>

      <div class="card danger">
        <span class="label">
          Errores
        </span>

        <span class="value">
          {errors}
        </span>
      </div>
    </section>

    <section class="cards">
      <div class="card">
        <span class="label">
          Límite
        </span>

        <span class="value">
          {_e(limit_text)}
        </span>
      </div>

      <div class="card">
        <span class="label">
          Usados
        </span>

        <span class="value">
          {bot.used_total}
        </span>
      </div>

      <div class="card success">
        <span class="label">
          Disponibles
        </span>

        <span class="value">
          {_e(available_text)}
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

      <div class="card danger">
        <span class="label">
          Grupos bloqueados
        </span>

        <span class="value">
          {blocked_groups}
        </span>
      </div>
    </section>

    <section class="box">
      <div class="head">
        <div>
          <strong>
            Estado del bot
          </strong>

          <div class="small">
            Instancia:
            {_e(bot.instance_name)}
          </div>
        </div>

        {bot_status_badge}
      </div>

      <div class="content">
        <div class="two">
          <div>
            <div class="small">
              Nombre
            </div>

            <strong>
              {_e(bot.display_name)}
            </strong>
          </div>

          <div>
            <div class="small">
              Identificador de instancia
            </div>

            <code>
              {_e(bot.instance_name)}
            </code>
          </div>
        </div>
      </div>
    </section>

    <section class="box">
      <div class="head">
        <strong>
          Grupos administrados
        </strong>

        <span class="small">
          Solo grupos pertenecientes
          a esta instancia.
        </span>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Group JID</th>
              <th>Estado</th>
              <th>Registrado</th>
            </tr>
          </thead>

          <tbody>
            {groups_html}
          </tbody>
        </table>
      </div>
    </section>
    """

    return HTMLResponse(
        page_html(
            title=(
                f"Mini Panel "
                f"{bot.display_name}"
            ),
            hero_title=(
                f"Mini Panel · "
                f"{bot.display_name}"
            ),
            hero_subtitle=(
                "Gestión y estadísticas "
                "independientes del bot."
            ),
            hero_actions=bot_status_badge,
            body=body,
        )
    )
