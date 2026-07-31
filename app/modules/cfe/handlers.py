import base64
import time
from datetime import datetime, timezone
from sqlalchemy import select
from app.config import settings
from app.db import SessionLocal
from app.models import BotControl, CfeRequest
from app.multibot import claim_or_validate_group, client_instance_allowed, enabled_cfe_providers, provider_by_group
from app.modules.cfe.flow import associate_provider_message, claim_delivery, finish, load_pending, request_key, resolve_by_provider_message, save_pending
from app.modules.cfe.parser import (
    extract_service_number,
    extract_service_numbers,
    extract_service_number_from_pdf,
    extract_service_number_from_status_text,
    text_is_deregistered,
    text_is_no_record,
)
from app.queue import redis_conn
from app.services.evolution import extract_sent_message_id, get_media_base64, send_pdf_base64, send_text
from app.webhook_utils import get_document, get_from_me, get_instance, get_message_id, get_participant, get_push_name, get_quoted_message_id, get_remote_jid, get_text


def _increment_usage(db, row: CfeRequest) -> None:
    if row.usage_counted:
        return
    bot = db.scalar(select(BotControl).where(BotControl.instance_name == row.client_instance).with_for_update())
    if bot:
        bot.used_total += 1
    row.usage_counted = True


def _find_pending_by_service_number(
    service_number: str,
    provider_group_jid: str,
) -> tuple[str, dict]:
    """
    Busca la solicitud pendiente correspondiente
    al número leído dentro del PDF.

    Se usa cuando el proveedor envía el PDF
    individualmente, sin citar el mensaje del bot.
    """

    with SessionLocal() as db:
        rows = db.scalars(
            select(CfeRequest)
            .where(
                CfeRequest.service_number
                == service_number,

                CfeRequest.provider_group_jid
                == provider_group_jid,

                CfeRequest.status
                == 'WAITING_PROVIDER',
            )
            .order_by(
                CfeRequest.created_at.asc()
            )
        ).all()

    for row in rows:
        pending = load_pending(
            row.request_key
        )

        if pending:
            return (
                row.request_key,
                pending,
            )

    return "", {}


def _complete_text_provider_result(
    *,
    key: str,
    pending: dict,
    response_message_id: str,
    status: str,
    client_message: str,
) -> dict:
    """
    Entrega al cliente un resultado textual
    del proveedor y cierra la solicitud.
    """

    if not claim_delivery(
        key
    ):
        return {
            "ok": True,
            "ignored": "already_claimed",
        }

    try:
        send_text(
            pending[
                "client_group_jid"
            ],
            client_message,
            pending[
                "client_instance"
            ],
        )

    except Exception:
        # Permite que el proveedor reintente
        # si falló el aviso al cliente.
        redis_conn.delete(
            f"extras:cfe:delivery-claim:{key}"
        )
        raise

    with SessionLocal() as db:
        row = db.scalar(
            select(
                CfeRequest
            )
            .where(
                CfeRequest.request_key
                == key
            )
            .with_for_update()
        )

        if row:
            row.status = status

            row.provider_response_message_id = (
                response_message_id
            )

            row.completed_at = datetime.now(
                timezone.utc
            )

            db.commit()

    finish(
        key,
        pending.get(
            "provider_message_id",
            "",
        ),
    )

    print(
        "CFE_TEXT_RESULT_DONE",
        {
            "request_key":
                key,

            "service_number":
                pending[
                    "service_number"
                ],

            "status":
                status,

            "provider_response_message_id":
                response_message_id,
        },
        flush=True,
    )

    return {
        "ok": True,
        "status": status,
        "service_number":
            pending[
                "service_number"
            ],
    }


def _send_provider_text_with_retry(
    *,
    provider_group_jid: str,
    service_number: str,
    transport_instance: str,
    max_attempts: int = 3,
) -> tuple[dict, str]:
    """
    Envía un número al proveedor con reintentos.

    Retorna:
        (respuesta_de_evolution, provider_message_id)
    """

    last_error: Exception | None = None

    for attempt in range(
        1,
        max_attempts + 1,
    ):
        try:
            response = send_text(
                provider_group_jid,
                service_number,
                transport_instance,
            )

            provider_message_id = (
                extract_sent_message_id(
                    response
                )
            )

            if not provider_message_id:
                raise RuntimeError(
                    "PROVIDER_MESSAGE_ID_EMPTY"
                )

            print(
                "CFE_PROVIDER_SEND_ATTEMPT_OK",
                {
                    "service_number":
                        service_number,

                    "attempt":
                        attempt,

                    "provider_message_id":
                        provider_message_id,
                },
                flush=True,
            )

            return (
                response,
                provider_message_id,
            )

        except Exception as exc:
            last_error = exc

            print(
                "CFE_PROVIDER_SEND_ATTEMPT_FAILED",
                {
                    "service_number":
                        service_number,

                    "attempt":
                        attempt,

                    "max_attempts":
                        max_attempts,

                    "error":
                        str(exc),
                },
                flush=True,
            )

            if attempt < max_attempts:
                time.sleep(
                    1.0 * attempt
                )

    raise RuntimeError(
        "PROVIDER_SEND_FAILED_AFTER_RETRIES: "
        f"{last_error}"
    )


def _send_single_client_request(
    *,
    instance: str,
    remote_jid: str,
    message_id: str,
    service_number: str,
    requester: str,
    requester_name: str,
    item_index: int,
) -> dict:
    """
    Crea y envía una solicitud individual dentro
    de un mensaje que puede contener varios servicios.
    """

    key = request_key(
        instance,
        remote_jid,
        (
            f"{message_id}:"
            f"{item_index}:"
            f"{service_number}"
        ),
    )

    transport_instance = (
        settings.provider_transport_instance
    )

    if not transport_instance:
        raise RuntimeError(
            "PROVIDER_TRANSPORT_INSTANCE_EMPTY"
        )

    with SessionLocal() as db:
        providers = enabled_cfe_providers(
            db
        )

        # Compatibilidad con proveedor del .env.
        if (
            not providers
            and settings.CFE_PROVIDER_GROUP_JID
        ):
            providers = [
                type(
                    "LegacyProvider",
                    (),
                    {
                        "provider_name":
                            "cfe_legacy",

                        "display_name":
                            "CFE principal",

                        "group_jid":
                            settings
                            .CFE_PROVIDER_GROUP_JID,
                    },
                )()
            ]

        if not providers:
            return {
                "ok": False,
                "service_number":
                    service_number,

                "error":
                    "no_provider_enabled",
            }

        row = None
        last_error = None
        pending = {}

        for provider in providers:
            pending = {
                "request_key":
                    key,

                "service_number":
                    service_number,

                "requester_wa_id":
                    requester,

                "requester_name":
                    requester_name,

                "client_group_jid":
                    remote_jid,

                "client_instance":
                    instance,

                "client_message_id":
                    (
                        f"{message_id}:"
                        f"{item_index}:"
                        f"{service_number}"
                    ),

                "provider_name":
                    provider.provider_name,

                "provider_group_jid":
                    provider.group_jid,

                "provider_instance":
                    transport_instance,
            }

            try:
                (
                    response,
                    provider_message_id,
                ) = _send_provider_text_with_retry(
                    provider_group_jid=
                        provider.group_jid,
                
                    service_number=
                        service_number,
                
                    transport_instance=
                        transport_instance,
                
                    max_attempts=3,
                )

                row = CfeRequest(
                    **pending,
                    provider_message_id=
                        provider_message_id,
                    status=
                        "WAITING_PROVIDER",
                )

                db.add(row)
                db.commit()

                associate_provider_message(
                    key,
                    provider_message_id,
                )

                pending[
                    "provider_message_id"
                ] = provider_message_id

                save_pending(
                    key,
                    pending,
                )

                break

            except Exception as exc:
                db.rollback()
            
                last_error = str(
                    exc
                )
            
                print(
                    "CFE_REQUEST_DB_OR_SEND_FAILED",
                    {
                        "exception_type":
                            type(exc).__name__,
            
                        "provider":
                            provider.provider_name,
            
                        "service_number":
                            service_number,
            
                        "client_message_id":
                            (
                                f"{message_id}:"
                                f"{item_index}:"
                                f"{service_number}"
                            ),
            
                        "error":
                            last_error,
                    },
                    flush=True,
                )

                print(
                    "CFE_PROVIDER_SEND_FAILED",
                    {
                        "provider":
                            provider.provider_name,

                        "service_number":
                            service_number,

                        "error":
                            last_error,
                    },
                    flush=True,
                )

        if row is None:
            return {
                "ok": False,
                "service_number":
                    service_number,

                "error":
                    last_error
                    or "provider_send_failed",
            }

    print(
        "CFE_SENT_TO_PROVIDER",
        {
            "request_key":
                key,

            "service_number":
                service_number,

            "provider":
                pending[
                    "provider_name"
                ],

            "provider_message_id":
                pending[
                    "provider_message_id"
                ],
        },
        flush=True,
    )

    return {
        "ok": True,
        "request_key":
            key,

        "service_number":
            service_number,

        "provider":
            pending[
                "provider_name"
            ],
    }


def process_client(
    payload: dict,
) -> dict:
    instance = get_instance(
        payload
    )

    remote_jid = get_remote_jid(
        payload
    )

    message_id = get_message_id(
        payload
    )

    if (
        get_from_me(payload)
        or not remote_jid.endswith(
            "@g.us"
        )
    ):
        return {
            "ok": True,
            "ignored":
                "not_client_request",
        }

    with SessionLocal() as db:
        provider = provider_by_group(
            db,
            remote_jid,
        )

        legacy_provider_group = bool(
            settings.CFE_PROVIDER_GROUP_JID
            and remote_jid
            == settings.CFE_PROVIDER_GROUP_JID
        )

        # Nunca interpretar el grupo proveedor
        # como grupo cliente.
        if (
            provider
            or legacy_provider_group
        ):
            return {
                "ok": True,
                "ignored":
                    "provider_group",
            }

        allowed, reason = (
            client_instance_allowed(
                db,
                instance,
            )
        )

        if not allowed:
            return {
                "ok": True,
                "ignored":
                    reason,
            }

        group_ok, group_reason = (
            claim_or_validate_group(
                db,
                remote_jid,
                instance,
            )
        )

        if not group_ok:
            return {
                "ok": True,
                "ignored":
                    group_reason,
            }

    text = get_text(
        payload
    ).strip()

    # Ignora conversación normal:
    # ".", "hola", emojis, etc.
    if not any(
        char.isdigit()
        for char in text
    ):
        return {
            "ok": True,
            "ignored":
                "non_numeric_chat_message",
        }

    dedupe = (
        f"extras:cfe:input:"
        f"{instance}:{message_id}"
    )

    if not redis_conn.set(
        dedupe,
        "1",
        nx=True,
        ex=86400,
    ):
        return {
            "ok": True,
            "ignored":
                "duplicate",
        }

    service_numbers, error = (
        extract_service_numbers(
            text
        )
    )

    requester = (
        get_participant(payload)
        or remote_jid
    )

    requester_name = (
        get_push_name(payload)
    )

    if error:
        send_text(
            remote_jid,
            (
                f"⚠️ {requester_name}, "
                f"{error}"
            ),
            instance,
        )

        return {
            "ok": True,
            "validation_error":
                error,
        }

    successful: list[str] = []
    failed: list[str] = []
    request_keys: list[str] = []

    for index, service_number in enumerate(
        service_numbers,
        start=1,
    ):
        # Evita mandar varios mensajes a Evolution
        # exactamente en el mismo instante.
        if index > 1:
            time.sleep(0.8)
    
        result = (
            _send_single_client_request(
                instance=
                    instance,
    
                remote_jid=
                    remote_jid,
    
                message_id=
                    message_id,
    
                service_number=
                    service_number,
    
                requester=
                    requester,
    
                requester_name=
                    requester_name,
    
                item_index=
                    index,
            )
        )

        if result.get(
            "ok"
        ):
            successful.append(
                service_number
            )

            request_keys.append(
                result[
                    "request_key"
                ]
            )

        else:
            failed.append(
                service_number
            )

    if successful:
        if len(successful) == 1:
            confirmation = (
                f"⚡ {requester_name}, "
                "solicitud recibida para el "
                f"servicio {successful[0]}."
            )

        else:
            services_text = "\n".join(
                f"• {value}"
                for value
                in successful
            )

            confirmation = (
                f"⚡ {requester_name}, "
                f"recibí {len(successful)} "
                "solicitudes CFE:\n"
                f"{services_text}"
            )

        send_text(
            remote_jid,
            confirmation,
            instance,
        )

    if failed:
        failed_text = "\n".join(
            f"• {value}"
            for value
            in failed
        )

        send_text(
            remote_jid,
            (
                f"⚠️ {requester_name}, "
                "no fue posible enviar estas "
                "solicitudes al proveedor:\n"
                f"{failed_text}"
            ),
            instance,
        )

    print(
        "CFE_BATCH_RESULT",
        {
            "message_id":
                message_id,
    
            "requested":
                service_numbers,
    
            "successful":
                successful,
    
            "failed":
                failed,
        },
        flush=True,
    )

    return {
        "ok": bool(
            successful
        ),
        "total":
            len(service_numbers),

        "successful":
            successful,

        "failed":
            failed,

        "request_keys":
            request_keys,
    }
    

def process_provider(
    payload: dict,
) -> dict:
    instance = get_instance(
        payload
    )

    remote_jid = get_remote_jid(
        payload
    )

    if (
        get_from_me(payload)
        or not remote_jid.endswith(
            '@g.us'
        )
    ):
        return {
            'ok': True,
            'ignored':
                'not_provider_response',
        }

    with SessionLocal() as db:
        provider = provider_by_group(
            db,
            remote_jid,
        )

    legacy_group = bool(
        settings.CFE_PROVIDER_GROUP_JID
        and remote_jid
        == settings.CFE_PROVIDER_GROUP_JID
    )

    if not provider and not legacy_group:
        return {
            'ok': True,
            'ignored':
                'not_provider_response',
        }

    response_message_id = (
        get_message_id(payload)
    )

    quoted_id = (
        get_quoted_message_id(payload)
    )

    text = get_text(payload)

    custom_phrases = tuple()

    if (
        provider
        and provider.no_record_phrases
    ):
        custom_phrases = tuple(
            value.strip().upper()
            for value
            in provider.no_record_phrases.split(
                '|'
            )
            if value.strip()
        )

    is_deregistered = (
        text_is_deregistered(
            text
        )
    )
    
    is_no_record = (
        not is_deregistered
        and (
            text_is_no_record(
                text
            )
            or any(
                phrase
                in str(
                    text or ""
                ).upper()
                for phrase
                in custom_phrases
            )
        )
    )

    # ==================================================
    # 1. Intentar resolver mediante respuesta citada
    # ==================================================

    key = ""
    pending: dict = {}

    if quoted_id:
        key = resolve_by_provider_message(
            quoted_id
        )

        if key:
            pending = load_pending(
                key
            )

    # Si el proveedor no citó, pero escribió algo como:
    # 331150802454 Dado de baja
    # buscamos la solicitud pendiente por el número.
    if (
        not quoted_id
        and (
            is_deregistered
            or is_no_record
        )
    ):
        (
            status_service_number,
            status_number_error,
        ) = extract_service_number_from_status_text(
            text
        )
    
        if not status_number_error:
            key, pending = (
                _find_pending_by_service_number(
                    status_service_number,
                    remote_jid,
                )
            )
    
            if not key or not pending:
                print(
                    "CFE_PROVIDER_STATUS_NO_PENDING",
                    {
                        "service_number":
                            status_service_number,
    
                        "provider_group_jid":
                            remote_jid,
    
                        "text":
                            text,
                    },
                    flush=True,
                )
    
                return {
                    "ok": True,
                    "ignored":
                        "no_pending_for_status_service",
    
                    "service_number":
                        status_service_number,
                }

    # ==================================================
    # 2. Servicio dado de baja
    # ==================================================
    
    if is_deregistered:
        # Citado:
        #   responde "Dado de baja"
        #
        # No citado:
        #   331150802454 Dado de baja
    
        if not key:
            return {
                "ok": True,
                "ignored":
                    "deregistered_request_not_found",
            }
    
        if not pending:
            return {
                "ok": True,
                "ignored":
                    "pending_expired",
            }
    
        service_number = pending[
            "service_number"
        ]
    
        return _complete_text_provider_result(
            key=key,
            pending=pending,
            response_message_id=
                response_message_id,
    
            status="DEREGISTERED",
    
            client_message=(
                f"⚠️ "
                f"{pending['requester_name']}, "
                "el proveedor informó que el "
                f"servicio {service_number} "
                "está dado de baja."
            ),
        )

    # ==================================================
    # 3. Respuesta textual "sin recibo"
    # ==================================================

    if is_no_record:
        # Citado:
        #   responde "No hay recibo"
        #
        # No citado:
        #   331150802454 No hay recibo

        if not key:
            return {
                "ok": True,
                "ignored":
                    "no_record_request_not_found",
            }

        if not pending:
            return {
                "ok": True,
                "ignored":
                    "pending_expired",
            }

        service_number = pending[
            "service_number"
        ]

        return _complete_text_provider_result(
            key=key,
            pending=pending,
            response_message_id=
                response_message_id,

            status="NO_RECORD",

            client_message=(
                f"⚠️ "
                f"{pending['requester_name']}, "
                "el proveedor no encontró "
                "recibo para el servicio "
                f"{service_number}."
            ),
        )

    # ==================================================
    # 4. La respuesta debe contener un documento PDF
    # ==================================================

    doc = get_document(payload)

    if not doc:
        # El proveedor puede conversar en su grupo.
        # No se le contesta ni se procesa como cliente.
        return {
            'ok': True,
            'ignored':
                'provider_response_not_pdf',
        }

    # ==================================================
    # 5. Descargar el PDF recibido
    # ==================================================

    media = get_media_base64(
        response_message_id,
        instance,
    )

    raw = (
        media.get('base64')
        or media.get('data')
        or media.get('media')
        or ''
    )

    if not raw:
        raise RuntimeError(
            'PROVIDER_PDF_BASE64_EMPTY'
        )

    if raw.startswith('data:'):
        raw = raw.split(
            ',',
            1,
        )[1]

    pdf_bytes = base64.b64decode(
        raw,
        validate=False,
    )

    if not pdf_bytes.startswith(
        b'%PDF'
    ):
        raise RuntimeError(
            'PROVIDER_DOCUMENT_IS_NOT_PDF'
        )

    # ==================================================
    # 6. Si no venía citado, leer el número del PDF
    # ==================================================

    pdf_service_number = ""

    if not key or not pending:
        (
            pdf_service_number,
            pdf_error,
        ) = extract_service_number_from_pdf(
            pdf_bytes
        )

        if pdf_error:
            print(
                'CFE_PROVIDER_PDF_UNMATCHED',
                {
                    'message_id':
                        response_message_id,

                    'provider_group_jid':
                        remote_jid,

                    'error':
                        pdf_error,
                },
                flush=True,
            )

            return {
                'ok': True,
                'ignored':
                    'pdf_service_number_not_found',

                'error':
                    pdf_error,
            }

        key, pending = (
            _find_pending_by_service_number(
                pdf_service_number,
                remote_jid,
            )
        )

        if not key or not pending:
            print(
                'CFE_PROVIDER_PDF_NO_PENDING',
                {
                    'service_number':
                        pdf_service_number,

                    'provider_group_jid':
                        remote_jid,

                    'message_id':
                        response_message_id,
                },
                flush=True,
            )

            return {
                'ok': True,
                'ignored':
                    'no_pending_for_pdf_service',

                'service_number':
                    pdf_service_number,
            }

    # ==================================================
    # 7. Validar que el PDF corresponda a la solicitud
    # ==================================================

    if not pdf_service_number:
        (
            pdf_service_number,
            pdf_error,
        ) = extract_service_number_from_pdf(
            pdf_bytes
        )

        # Si venía citado y el PDF no permite
        # extraer texto, conservamos la asociación
        # de la cita para compatibilidad.
        if (
            not pdf_error
            and pdf_service_number
            != pending['service_number']
        ):
            print(
                'CFE_PROVIDER_PDF_SERVICE_MISMATCH',
                {
                    'expected':
                        pending[
                            'service_number'
                        ],

                    'found':
                        pdf_service_number,

                    'message_id':
                        response_message_id,
                },
                flush=True,
            )

            return {
                'ok': True,
                'ignored':
                    'pdf_service_mismatch',

                'expected':
                    pending[
                        'service_number'
                    ],

                'found':
                    pdf_service_number,
            }

    # ==================================================
    # 8. Reclamar y entregar una sola vez
    # ==================================================

    if not claim_delivery(key):
        return {
            'ok': True,
            'ignored':
                'already_claimed',
        }

    service_number = pending[
        'service_number'
    ]

    filename = (
        f"RECIBO_CFE_"
        f"{service_number}.pdf"
    )

    caption = (
        "⚡ Recibo CFE\n"
        f"Servicio: {service_number}\n"
        "Solicitó: "
        f"{pending['requester_name']}"
    )

    try:
        send_pdf_base64(
            pending['client_group_jid'],
            raw,
            filename,
            caption,
            pending['client_instance'],
        )

    except Exception:
        # Si falla la entrega, permitir reintento.
        redis_conn.delete(
            f'extras:cfe:delivery-claim:{key}'
        )
        raise

    with SessionLocal() as db:
        row = db.scalar(
            select(CfeRequest)
            .where(
                CfeRequest.request_key
                == key
            )
            .with_for_update()
        )

        if row:
            row.status = 'DONE'

            row.provider_response_message_id = (
                response_message_id
            )

            row.provider_pdf_filename = (
                filename
            )

            row.completed_at = (
                datetime.now(
                    timezone.utc
                )
            )

            _increment_usage(
                db,
                row,
            )

            db.commit()

    finish(
        key,
        pending.get(
            'provider_message_id',
            '',
        ),
    )

    print(
        'CFE_REQUEST_DONE',
        {
            'request_key':
                key,

            'service_number':
                service_number,

            'matched_by':
                (
                    'quoted_message'
                    if quoted_id
                    else 'pdf_service_number'
                ),

            'provider_response_message_id':
                response_message_id,
        },
        flush=True,
    )

    return {
        'ok': True,
        'status': 'DONE',
        'service_number':
            service_number,

        'matched_by':
            (
                'quoted_message'
                if quoted_id
                else 'pdf_service_number'
            ),
    }
