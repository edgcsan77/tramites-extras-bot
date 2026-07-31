import base64
from datetime import datetime, timezone
from sqlalchemy import select
from app.config import settings
from app.db import SessionLocal
from app.models import BotControl, CfeRequest
from app.multibot import claim_or_validate_group, client_instance_allowed, enabled_cfe_providers, provider_by_group
from app.modules.cfe.flow import associate_provider_message, claim_delivery, finish, load_pending, request_key, resolve_by_provider_message, save_pending
from app.modules.cfe.parser import (
    extract_service_number,
    extract_service_number_from_pdf,
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


def process_client(payload: dict) -> dict:
    instance = get_instance(payload)
    remote_jid = get_remote_jid(payload)
    message_id = get_message_id(payload)
    if get_from_me(payload) or not remote_jid.endswith('@g.us'):
        return {'ok': True, 'ignored': 'not_client_request'}

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
    
        # El grupo proveedor nunca debe entrar
        # como grupo cliente, esté registrado
        # en SQL o configurado mediante .env.
        if provider or legacy_provider_group:
            return {
                'ok': True,
                'ignored': 'provider_group',
            }
        allowed, reason = client_instance_allowed(db, instance)
        if not allowed:
            return {'ok': True, 'ignored': reason}
        group_ok, group_reason = claim_or_validate_group(db, remote_jid, instance)
        if not group_ok:
            return {'ok': True, 'ignored': group_reason}

    text = get_text(payload).strip()

    # Ignora conversaciones normales del grupo:
    # ".", "hola", "gracias", emojis, etc.
    # Solo intenta procesar mensajes que contengan al menos un número.
    if not any(char.isdigit() for char in text):
        return {
            'ok': True,
            'ignored': 'non_numeric_chat_message',
        }
    
    dedupe = f'extras:cfe:input:{instance}:{message_id}'
    if not redis_conn.set(dedupe, '1', nx=True, ex=86400):
        return {
            'ok': True,
            'ignored': 'duplicate',
        }
    
    service_number, error = extract_service_number(text)
    
    requester = (
        get_participant(payload)
        or remote_jid
    )
    
    requester_name = get_push_name(payload)
    
    if error:
        send_text(
            remote_jid,
            f'⚠️ {requester_name}, {error}',
            instance,
        )
    
        return {
            'ok': True,
            'validation_error': error,
        }

    key = request_key(instance, remote_jid, message_id)
    transport_instance = settings.provider_transport_instance
    if not transport_instance:
        raise RuntimeError('PROVIDER_TRANSPORT_INSTANCE_EMPTY')

    with SessionLocal() as db:
        providers = enabled_cfe_providers(db)
        # Compatibilidad inicial: permite operar con el grupo del .env antes de crear proveedores.
        if not providers and settings.CFE_PROVIDER_GROUP_JID:
            providers = [type('LegacyProvider', (), {
                'provider_name': 'cfe_legacy', 'display_name': 'CFE principal',
                'group_jid': settings.CFE_PROVIDER_GROUP_JID
            })()]
        if not providers:
            send_text(remote_jid, f'⚠️ {requester_name}, no hay proveedor CFE habilitado.', instance)
            return {'ok': True, 'ignored': 'no_provider_enabled'}

        row = None
        last_error = None
        for provider in providers:
            pending = {
                'request_key': key, 'service_number': service_number,
                'requester_wa_id': requester, 'requester_name': requester_name,
                'client_group_jid': remote_jid, 'client_instance': instance,
                'client_message_id': message_id,
                'provider_name': provider.provider_name,
                'provider_group_jid': provider.group_jid,
                'provider_instance': transport_instance,
            }
            try:
                response = send_text(provider.group_jid, service_number, transport_instance)
                provider_message_id = extract_sent_message_id(response)
                if not provider_message_id:
                    raise RuntimeError('PROVIDER_MESSAGE_ID_EMPTY')
                row = CfeRequest(**pending, provider_message_id=provider_message_id, status='WAITING_PROVIDER')
                db.add(row)
                db.commit()
                associate_provider_message(key, provider_message_id)
                pending['provider_message_id'] = provider_message_id
                save_pending(key, pending)
                break
            except Exception as exc:
                db.rollback()
                last_error = str(exc)
                print('CFE_PROVIDER_SEND_FAILED', {'provider': provider.provider_name, 'error': last_error}, flush=True)

        if row is None:
            send_text(remote_jid, f'⚠️ {requester_name}, no fue posible enviar la solicitud a los proveedores.', instance)
            return {'ok': True, 'status': 'ERROR', 'error': last_error}

    send_text(remote_jid, f'⚡ {requester_name}, solicitud recibida para el servicio {service_number}.', instance)
    print('CFE_SENT_TO_PROVIDER', {'request_key': key, 'provider': pending['provider_name'], 'provider_message_id': pending['provider_message_id']}, flush=True)
    return {'ok': True, 'request_key': key}


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

    is_no_record = (
        text_is_no_record(text)
        or any(
            phrase
            in str(text or '').upper()
            for phrase
            in custom_phrases
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

    # ==================================================
    # 2. Respuesta textual "sin recibo"
    # ==================================================

    if is_no_record:
        # Para respuestas de "no encontrado",
        # seguimos exigiendo cita porque un texto
        # sin número no permite saber qué solicitud
        # debe cerrarse.
        if not quoted_id:
            return {
                'ok': True,
                'ignored':
                    'no_record_without_quote',
            }

        if not key:
            return {
                'ok': True,
                'ignored':
                    'quote_not_associated',
            }

        if not pending:
            return {
                'ok': True,
                'ignored':
                    'pending_expired',
            }

        if not claim_delivery(key):
            return {
                'ok': True,
                'ignored':
                    'already_claimed',
            }

        send_text(
            pending['client_group_jid'],
            (
                f"⚠️ "
                f"{pending['requester_name']}, "
                "el proveedor no encontró "
                "recibo para "
                f"{pending['service_number']}."
            ),
            pending['client_instance'],
        )

        with SessionLocal() as db:
            row = db.scalar(
                select(CfeRequest).where(
                    CfeRequest.request_key
                    == key
                )
            )

            if row:
                row.status = 'NO_RECORD'

                row.provider_response_message_id = (
                    response_message_id
                )

                row.completed_at = (
                    datetime.now(
                        timezone.utc
                    )
                )

                db.commit()

        finish(
            key,
            pending.get(
                'provider_message_id',
                '',
            ),
        )

        return {
            'ok': True,
            'status': 'NO_RECORD',
        }

    # ==================================================
    # 3. La respuesta debe contener un documento PDF
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
    # 4. Descargar el PDF recibido
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
    # 5. Si no venía citado, leer el número del PDF
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
    # 6. Validar que el PDF corresponda a la solicitud
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
    # 7. Reclamar y entregar una sola vez
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
