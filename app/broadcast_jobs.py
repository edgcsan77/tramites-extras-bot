import time

from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuthorizedGroup
from app.services.evolution import send_text


def send_instance_broadcast_job(
    *,
    instance_name: str,
    message: str,
) -> dict:
    """
    Envía un mensaje desde una instancia Evolution
    a todos sus grupos cliente autorizados y activos.
    """

    instance_name = str(
        instance_name
        or ""
    ).strip()

    message = str(
        message
        or ""
    ).strip()

    if not instance_name:
        raise ValueError(
            "BROADCAST_INSTANCE_EMPTY"
        )

    if not message:
        raise ValueError(
            "BROADCAST_MESSAGE_EMPTY"
        )

    if len(message) > 3500:
        raise ValueError(
            "BROADCAST_MESSAGE_TOO_LONG"
        )

    with SessionLocal() as db:
        groups = list(
            db.scalars(
                select(
                    AuthorizedGroup
                ).where(
                    AuthorizedGroup.owner_instance
                    == instance_name,

                    AuthorizedGroup.is_blocked
                    .is_(False),
                ).order_by(
                    AuthorizedGroup.created_at.asc()
                )
            ).all()
        )

    sent: list[str] = []
    failed: list[dict] = []

    for index, group in enumerate(
        groups,
        start=1,
    ):
        group_jid = str(
            group.group_jid
            or ""
        ).strip()

        if not group_jid.endswith(
            "@g.us"
        ):
            failed.append({
                "group_jid":
                    group_jid,

                "error":
                    "INVALID_GROUP_JID",
            })

            continue

        try:
            send_text(
                group_jid,
                message,
                instance_name,
            )

            sent.append(
                group_jid
            )

            print(
                "EXTRAS_BROADCAST_SENT",
                {
                    "instance":
                        instance_name,

                    "group_jid":
                        group_jid,

                    "index":
                        index,

                    "total":
                        len(groups),
                },
                flush=True,
            )

        except Exception as exc:
            failed.append({
                "group_jid":
                    group_jid,

                "error":
                    str(exc),
            })

            print(
                "EXTRAS_BROADCAST_FAILED",
                {
                    "instance":
                        instance_name,

                    "group_jid":
                        group_jid,

                    "error":
                        str(exc),
                },
                flush=True,
            )

        # Evita disparar todos los mensajes
        # simultáneamente contra Evolution.
        if index < len(groups):
            time.sleep(
                0.6
            )

    result = {
        "ok":
            not failed,

        "instance":
            instance_name,

        "total_groups":
            len(groups),

        "sent":
            len(sent),

        "failed":
            len(failed),

        "failed_groups":
            failed,
    }

    print(
        "EXTRAS_BROADCAST_FINISHED",
        result,
        flush=True,
    )

    return result
