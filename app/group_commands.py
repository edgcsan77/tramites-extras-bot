from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import AuthorizedGroup, BotControl
from app.multibot import provider_by_group
from app.services.evolution import send_text
from app.webhook_utils import (
    get_from_me,
    get_instance,
    get_participant,
    get_participant_alt,
    get_remote_jid,
    get_text,
)


def _normalize_command(text: str) -> str:
    value = str(text or "").strip().split(maxsplit=1)[0].lower()

    # También admite:
    # /addgroup@NombreDelBot
    # /groupid@NombreDelBot
    return value.split("@", 1)[0]


def _instance_is_usable(
    db,
    instance: str,
) -> tuple[bool, str]:
    if not instance:
        return (
            False,
            "La instancia del webhook llegó vacía.",
        )

    if (
        instance == settings.MAIN_INSTANCE
        or instance
        in settings.cfe_client_instances
    ):
        return True, ""

    bot = db.scalar(
        select(BotControl).where(
            BotControl.instance_name
            == instance
        )
    )

    if not bot:
        return (
            False,
            (
                f"La instancia {instance} "
                "no está registrada en el panel."
            ),
        )

    if not bot.is_active:
        return (
            False,
            (
                f"La instancia {instance} "
                "está desactivada."
            ),
        )

    if bot.is_blocked:
        return (
            False,
            (
                f"La instancia {instance} "
                "está bloqueada."
            ),
        )

    return True, ""


def process_group_command(
    payload: dict,
) -> dict:
    """
    Procesa /groupid y /addgroup antes
    del flujo normal de solicitudes CFE.
    """

    remote_jid = get_remote_jid(
        payload
    )

    if not remote_jid.endswith(
        "@g.us"
    ):
        return {
            "ok": True,
            "ignored": "not_group_command",
        }

    command = _normalize_command(
        get_text(payload)
    )

    if command not in {
        "/groupid",
        "/addgroup",
    }:
        return {
            "ok": True,
            "ignored": "not_group_command",
        }

    instance = get_instance(
        payload
    )

    if command == "/groupid":
        with SessionLocal() as db:
            row = db.scalar(
                select(
                    AuthorizedGroup
                ).where(
                    AuthorizedGroup.group_jid
                    == remote_jid
                )
            )

            if row:
                status = (
                    "BLOQUEADO"
                    if row.is_blocked
                    else "AUTORIZADO"
                )

                owner = (
                    row.owner_instance
                    or "—"
                )
            else:
                status = (
                    "NO AUTORIZADO"
                )
                owner = "—"

        send_text(
            remote_jid,
            (
                "🆔 DATOS DEL GRUPO\n"
                f"Grupo JID: {remote_jid}\n"
                "Instancia receptora: "
                f"{instance or '—'}\n"
                f"Estado: {status}\n"
                "Instancia autorizada: "
                f"{owner}"
            ),
            instance,
        )

        return {
            "ok": True,
            "command": "groupid",
            "group_jid": remote_jid,
            "instance": instance,
        }

    if not get_from_me(payload):
        send_text(
            remote_jid,
            (
                "⛔ /addgroup solo puede ejecutarlo "
                "el número conectado a esta instancia."
            ),
            instance,
        )
    
        return {
            "ok": True,
            "command": "addgroup",
            "authorized": False,
            "reason": "not_instance_owner",
        }

    with SessionLocal() as db:
        usable, error = (
            _instance_is_usable(
                db,
                instance,
            )
        )

        if not usable:
            send_text(
                remote_jid,
                f"⛔ {error}",
                instance,
            )

            return {
                "ok": True,
                "command": "addgroup",
                "authorized": False,
                "reason": error,
            }

        provider = provider_by_group(
            db,
            remote_jid,
        )

        if provider:
            send_text(
                remote_jid,
                (
                    "⛔ Este JID está configurado "
                    "como grupo proveedor y no "
                    "puede autorizarse como "
                    "grupo cliente."
                ),
                instance,
            )

            return {
                "ok": True,
                "command": "addgroup",
                "authorized": False,
                "reason": "provider_group",
            }

        row = db.scalar(
            select(
                AuthorizedGroup
            ).where(
                AuthorizedGroup.group_jid
                == remote_jid
            )
        )

        if (
            row
            and row.owner_instance
            != instance
        ):
            send_text(
                remote_jid,
                (
                    "⛔ Este grupo ya pertenece "
                    "a otra instancia.\n"
                    f"Grupo JID: {remote_jid}\n"
                    "Instancia registrada: "
                    f"{row.owner_instance}\n"
                    "Instancia actual: "
                    f"{instance}"
                ),
                instance,
            )

            return {
                "ok": True,
                "command": "addgroup",
                "authorized": False,
                "reason":
                    "group_owned_by_other_instance",
            }

        if row:
            row.is_blocked = False
            row.is_hidden = False

            result = (
                "ya estaba autorizado y "
                "quedó habilitado nuevamente"
            )

        else:
            db.add(
                AuthorizedGroup(
                    group_jid=remote_jid,
                    owner_instance=instance,
                )
            )

            result = (
                "quedó autorizado "
                "correctamente"
            )

        db.commit()

    send_text(
        remote_jid,
        (
            f"✅ El grupo {result}.\n"
            f"Grupo JID: {remote_jid}\n"
            "Instancia autorizada: "
            f"{instance}"
        ),
        instance,
    )

    return {
        "ok": True,
        "command": "addgroup",
        "authorized": True,
        "group_jid": remote_jid,
        "instance": instance,
    }
