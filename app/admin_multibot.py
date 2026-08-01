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
from app.panel_rfc_mini_view import render_mini_panel

from app.panel_theme import (
    badge_html,
    page_html,
)
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.panel_data import (
    bot_panel_data,
    fmt_dt,
    period_bounds,
)
from app.models import ProductRechargeLog

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

        cfe_limit = int(
            bot.cfe_limit or 0
        )
        
        cfe_used = int(
            bot.cfe_used or 0
        )
        
        renapo_limit = int(
            bot.renapo_limit or 0
        )
        
        renapo_used = int(
            bot.renapo_used or 0
        )
        
        cfe_limit_text = (
            "Ilimitado"
            if cfe_limit == 0
            else str(cfe_limit)
        )
        
        cfe_available_text = (
            "Ilimitado"
            if cfe_limit == 0
            else str(
                max(
                    0,
                    cfe_limit - cfe_used,
                )
            )
        )
        
        renapo_limit_text = (
            "Ilimitado"
            if renapo_limit == 0
            else str(renapo_limit)
        )
        
        renapo_available_text = (
            "Ilimitado"
            if renapo_limit == 0
            else str(
                max(
                    0,
                    renapo_limit - renapo_used,
                )
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
                  CFE: {cfe_used}
                </strong>
            
                <div class="small">
                  Límite CFE:
                  {_e(cfe_limit_text)}
                </div>
            
                <div class="small">
                  Disponible CFE:
                  {_e(cfe_available_text)}
                </div>
            
                <div
                  class="small"
                  style="margin-top:8px"
                >
                  <strong>
                    RENAPO: {renapo_used}
                  </strong>
                </div>
            
                <div class="small">
                  Límite RENAPO:
                  {_e(renapo_limit_text)}
                </div>
            
                <div class="small">
                  Disponible RENAPO:
                  {_e(renapo_available_text)}
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
                    <select
                      name="product"
                      required
                    >
                      <option value="CFE">
                        CFE
                      </option>
                
                      <option value="RENAPO">
                        RENAPO
                      </option>
                    </select>
                
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


@router.post(
    "/panel/instance/{instance_name}/recharge"
)
def recharge(
    instance_name: str,
    product: str = Form(...),
    amount: int = Form(...),
    token: str = Depends(_admin),
    db: Session = Depends(get_db),
):
    bot = db.scalar(
        select(
            BotControl
        ).where(
            BotControl.instance_name
            == instance_name
        ).with_for_update()
    )

    if not bot:
        raise HTTPException(
            404,
            "Bot no encontrado",
        )

    if amount <= 0:
        raise HTTPException(
            400,
            "Monto inválido",
        )

    product = (
        product
        or ""
    ).strip().upper()

    if product == "CFE":
        previous_limit = int(
            bot.cfe_limit or 0
        )

        used_at_recharge = int(
            bot.cfe_used or 0
        )

        bot.cfe_limit = (
            previous_limit
            + amount
        )

        new_limit = int(
            bot.cfe_limit
        )

    elif product == "RENAPO":
        previous_limit = int(
            bot.renapo_limit or 0
        )

        used_at_recharge = int(
            bot.renapo_used or 0
        )

        bot.renapo_limit = (
            previous_limit
            + amount
        )

        new_limit = int(
            bot.renapo_limit
        )

    else:
        raise HTTPException(
            400,
            "Producto inválido",
        )

    db.add(
        ProductRechargeLog(
            owner_type="BOT",
            owner_key=bot.instance_name,
            product=product,
            amount=amount,
            previous_limit=previous_limit,
            new_limit=new_limit,
            used_at_recharge=used_at_recharge,
            note="Recarga desde panel principal",
        )
    )

    db.commit()

    return _go(
        "/panel/bots",
        token,
    )


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
            title="Proveedores",
            hero_title="Proveedores",
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


@router.post(
    "/botpanel/{panel_token}/bot/toggle"
)
def mini_toggle_bot(
    panel_token: str,
    db: Session = Depends(get_db),
):
    bot = db.scalar(
        select(
            BotControl
        ).where(
            BotControl.panel_token
            == panel_token
        )
    )

    if not bot:
        raise HTTPException(
            404,
            "Bot no encontrado",
        )

    bot.is_blocked = (
        not bot.is_blocked
    )

    db.commit()

    return RedirectResponse(
        f"/botpanel/{panel_token}",
        status_code=303,
    )


@router.post(
    "/botpanel/{panel_token}/group/add"
)
def mini_add_group(
    panel_token: str,
    group_jid: str = Form(...),
    custom_name: str = Form(""),
    db: Session = Depends(get_db),
):
    bot = db.scalar(
        select(
            BotControl
        ).where(
            BotControl.panel_token
            == panel_token,

            BotControl.is_active
            .is_(True),
        )
    )

    if not bot:
        raise HTTPException(
            404,
            "Bot no encontrado",
        )

    group_jid = group_jid.strip()

    if not group_jid.endswith(
        "@g.us"
    ):
        raise HTTPException(
            400,
            "group_jid inválido",
        )

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
            != bot.instance_name
        ):
            raise HTTPException(
                409,
                "El grupo pertenece a otra instancia",
            )

        existing.is_hidden = False
        existing.custom_name = (
            custom_name.strip()
            or existing.custom_name
        )

    else:
        db.add(
            AuthorizedGroup(
                group_jid=group_jid,
                owner_instance=
                    bot.instance_name,
                custom_name=
                    custom_name.strip()
                    or None,
            )
        )

    db.commit()

    return RedirectResponse(
        f"/botpanel/{panel_token}",
        status_code=303,
    )


@router.post(
    "/botpanel/{panel_token}/group/"
    "{group_jid}/rename"
)
def mini_rename_group(
    panel_token: str,
    group_jid: str,
    custom_name: str = Form(...),
    db: Session = Depends(get_db),
):
    bot = db.scalar(
        select(
            BotControl
        ).where(
            BotControl.panel_token
            == panel_token
        )
    )

    if not bot:
        raise HTTPException(
            404,
            "Bot no encontrado",
        )

    group = db.scalar(
        select(
            AuthorizedGroup
        ).where(
            AuthorizedGroup.group_jid
            == group_jid,

            AuthorizedGroup.owner_instance
            == bot.instance_name,
        )
    )

    if not group:
        raise HTTPException(
            404,
            "Grupo no encontrado",
        )

    group.custom_name = (
        custom_name.strip()
        or None
    )

    db.commit()

    return RedirectResponse(
        f"/botpanel/{panel_token}",
        status_code=303,
    )


@router.post(
    "/botpanel/{panel_token}/group/"
    "{group_jid}/toggle"
)
def mini_toggle_group(
    panel_token: str,
    group_jid: str,
    db: Session = Depends(get_db),
):
    bot = db.scalar(
        select(
            BotControl
        ).where(
            BotControl.panel_token
            == panel_token
        )
    )

    if not bot:
        raise HTTPException(
            404,
            "Bot no encontrado",
        )

    group = db.scalar(
        select(
            AuthorizedGroup
        ).where(
            AuthorizedGroup.group_jid
            == group_jid,

            AuthorizedGroup.owner_instance
            == bot.instance_name,
        )
    )

    if not group:
        raise HTTPException(
            404,
            "Grupo no encontrado",
        )

    group.is_blocked = (
        not group.is_blocked
    )

    db.commit()

    return RedirectResponse(
        f"/botpanel/{panel_token}",
        status_code=303,
    )


@router.post(
    "/botpanel/{panel_token}/group/"
    "{group_jid}/hide"
)
def mini_hide_group(
    panel_token: str,
    group_jid: str,
    db: Session = Depends(get_db),
):
    bot = db.scalar(
        select(
            BotControl
        ).where(
            BotControl.panel_token
            == panel_token
        )
    )

    if not bot:
        raise HTTPException(
            404,
            "Bot no encontrado",
        )

    group = db.scalar(
        select(
            AuthorizedGroup
        ).where(
            AuthorizedGroup.group_jid
            == group_jid,

            AuthorizedGroup.owner_instance
            == bot.instance_name,
        )
    )

    if not group:
        raise HTTPException(
            404,
            "Grupo no encontrado",
        )

    group.is_hidden = True
    db.commit()

    return RedirectResponse(
        f"/botpanel/{panel_token}",
        status_code=303,
    )


@router.post(
    "/botpanel/{panel_token}/recharge/"
    "{product}"
)
def mini_recharge_product(
    panel_token: str,
    product: str,
    amount: int = Form(...),
    db: Session = Depends(get_db),
):
    bot = db.scalar(
        select(
            BotControl
        ).where(
            BotControl.panel_token
            == panel_token
        ).with_for_update()
    )

    if not bot:
        raise HTTPException(
            404,
            "Bot no encontrado",
        )

    if amount <= 0:
        raise HTTPException(
            400,
            "Cantidad inválida",
        )

    product = (
        product
        or ""
    ).strip().upper()

    if product == "CFE":
        previous = int(
            bot.cfe_limit or 0
        )

        bot.cfe_limit = (
            previous
            + amount
        )

        new_limit = bot.cfe_limit
        used = int(
            bot.cfe_used or 0
        )

    elif product == "RENAPO":
        previous = int(
            bot.renapo_limit or 0
        )

        bot.renapo_limit = (
            previous
            + amount
        )

        new_limit = bot.renapo_limit
        used = int(
            bot.renapo_used or 0
        )

    else:
        raise HTTPException(
            400,
            "Producto inválido",
        )

    db.add(
        ProductRechargeLog(
            owner_type="BOT",
            owner_key=
                bot.instance_name,
            product=product,
            amount=amount,
            previous_limit=previous,
            new_limit=new_limit,
            used_at_recharge=used,
        )
    )

    db.commit()

    return RedirectResponse(
        f"/botpanel/{panel_token}",
        status_code=303,
    )




def _mini_done_counts_by_group(db: Session, instance_name: str, start, end) -> dict[str, int]:
    counts: dict[str, int] = {}
    for model in (CfeRequest, RenapoRequest):
        rows = db.execute(
            select(model.client_group_jid, func.count())
            .where(
                model.client_instance == instance_name,
                model.created_at >= start,
                model.created_at < end,
                model.status == "DONE",
            )
            .group_by(model.client_group_jid)
        ).all()
        for group_jid, count in rows:
            key = str(group_jid or "").strip()
            if key:
                counts[key] = counts.get(key, 0) + int(count or 0)
    return counts

@router.get(
    "/botpanel/{panel_token}",
    response_class=HTMLResponse,
)
def mini_panel(
    panel_token: str,
    view: str = "day",
    date_from: str = "",
    date_to: str = "",
    db: Session = Depends(get_db),
):
    bot = db.scalar(select(BotControl).where(BotControl.panel_token == panel_token, BotControl.is_active.is_(True)))
    if not bot:
        raise HTTPException(404, "Mini panel no encontrado")
    time_min, time_max, view = period_bounds(view, date_from, date_to)
    data = bot_panel_data(db, bot.instance_name, time_min, time_max)

    day_min, day_max, _ = period_bounds("day")
    d30_min, d30_max, _ = period_bounds("30d")
    month_min, month_max, _ = period_bounds("month")
    prev_min, prev_max, _ = period_bounds("prev_month")

    day_data = bot_panel_data(db, bot.instance_name, day_min, day_max)
    d30_data = bot_panel_data(db, bot.instance_name, d30_min, d30_max)
    month_data = bot_panel_data(db, bot.instance_name, month_min, month_max)
    prev_data = bot_panel_data(db, bot.instance_name, prev_min, prev_max)

    group_period_counts = {
        "day": _mini_done_counts_by_group(db, bot.instance_name, day_min, day_max),
        "30d": _mini_done_counts_by_group(db, bot.instance_name, d30_min, d30_max),
        "month": _mini_done_counts_by_group(db, bot.instance_name, month_min, month_max),
        "prev_month": _mini_done_counts_by_group(db, bot.instance_name, prev_min, prev_max),
    }

    recharge_logs = list(
        db.scalars(
            select(ProductRechargeLog)
            .where(ProductRechargeLog.owner_key == bot.instance_name)
            .order_by(ProductRechargeLog.created_at.desc())
            .limit(30)
        ).all()
    )

    return HTMLResponse(render_mini_panel(
        panel_token=panel_token, bot=bot, view=view, date_from=date_from, date_to=date_to,
        summary=data["summary"], groups=data["groups"], recent=data["recent"],
        period_summaries={
            "day": day_data["summary"],
            "30d": d30_data["summary"],
            "month": month_data["summary"],
            "prev_month": prev_data["summary"],
        },
        group_period_counts=group_period_counts,
        recharge_logs=recharge_logs,
    ))
