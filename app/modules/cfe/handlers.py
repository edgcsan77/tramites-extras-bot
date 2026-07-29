import base64
from datetime import datetime, timezone
from sqlalchemy import select
from app.config import settings
from app.db import SessionLocal
from app.models import BotControl, CfeRequest
from app.multibot import claim_or_validate_group, client_instance_allowed, enabled_cfe_providers, provider_by_group
from app.modules.cfe.flow import associate_provider_message, claim_delivery, finish, load_pending, request_key, resolve_by_provider_message, save_pending
from app.modules.cfe.parser import extract_service_number, text_is_no_record
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


def process_client(payload: dict) -> dict:
    instance = get_instance(payload)
    remote_jid = get_remote_jid(payload)
    message_id = get_message_id(payload)
    if get_from_me(payload) or not remote_jid.endswith('@g.us'):
        return {'ok': True, 'ignored': 'not_client_request'}

    with SessionLocal() as db:
        # Los grupos proveedores nunca deben entrar como solicitudes de cliente.
        if provider_by_group(db, remote_jid):
            return {'ok': True, 'ignored': 'provider_group'}
        allowed, reason = client_instance_allowed(db, instance)
        if not allowed:
            return {'ok': True, 'ignored': reason}
        group_ok, group_reason = claim_or_validate_group(db, remote_jid, instance)
        if not group_ok:
            return {'ok': True, 'ignored': group_reason}

    dedupe = f'extras:cfe:input:{instance}:{message_id}'
    if not redis_conn.set(dedupe, '1', nx=True, ex=86400):
        return {'ok': True, 'ignored': 'duplicate'}

    service_number, error = extract_service_number(get_text(payload))
    requester = get_participant(payload) or remote_jid
    requester_name = get_push_name(payload)
    if error:
        send_text(remote_jid, f'⚠️ {requester_name}, {error}', instance)
        return {'ok': True, 'validation_error': error}

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


def process_provider(payload: dict) -> dict:
    instance = get_instance(payload)
    remote_jid = get_remote_jid(payload)
    if get_from_me(payload) or not remote_jid.endswith('@g.us'):
        return {'ok': True, 'ignored': 'not_provider_response'}

    with SessionLocal() as db:
        provider = provider_by_group(db, remote_jid)
    legacy_group = settings.CFE_PROVIDER_GROUP_JID and remote_jid == settings.CFE_PROVIDER_GROUP_JID
    if not provider and not legacy_group:
        return {'ok': True, 'ignored': 'not_provider_response'}

    quoted_id = get_quoted_message_id(payload)
    if not quoted_id:
        return {'ok': True, 'ignored': 'provider_response_without_quote'}
    key = resolve_by_provider_message(quoted_id)
    if not key:
        return {'ok': True, 'ignored': 'quote_not_associated'}
    pending = load_pending(key)
    if not pending:
        return {'ok': True, 'ignored': 'pending_expired'}

    response_message_id = get_message_id(payload)
    text = get_text(payload)
    custom_phrases = tuple()
    if provider and provider.no_record_phrases:
        custom_phrases = tuple(x.strip().upper() for x in provider.no_record_phrases.split('|') if x.strip())
    is_no_record = text_is_no_record(text) or any(x in str(text or '').upper() for x in custom_phrases)

    if is_no_record:
        if not claim_delivery(key):
            return {'ok': True, 'ignored': 'already_claimed'}
        send_text(pending['client_group_jid'], f"⚠️ {pending['requester_name']}, el proveedor no encontró recibo para {pending['service_number']}.", pending['client_instance'])
        with SessionLocal() as db:
            row = db.scalar(select(CfeRequest).where(CfeRequest.request_key == key))
            if row:
                row.status = 'NO_RECORD'; row.provider_response_message_id = response_message_id; row.completed_at = datetime.now(timezone.utc); db.commit()
        finish(key, pending.get('provider_message_id', ''))
        return {'ok': True, 'status': 'NO_RECORD'}

    doc = get_document(payload)
    if not doc:
        return {'ok': True, 'ignored': 'provider_response_not_pdf'}
    if not claim_delivery(key):
        return {'ok': True, 'ignored': 'already_claimed'}

    # El PDF se descarga usando la instancia que recibió el evento; no existe una "instancia del proveedor".
    media = get_media_base64(response_message_id, instance)
    raw = media.get('base64') or media.get('data') or media.get('media') or ''
    if not raw:
        raise RuntimeError('PROVIDER_PDF_BASE64_EMPTY')
    if raw.startswith('data:'):
        raw = raw.split(',', 1)[1]
    pdf_bytes = base64.b64decode(raw, validate=False)
    if not pdf_bytes.startswith(b'%PDF'):
        raise RuntimeError('PROVIDER_DOCUMENT_IS_NOT_PDF')

    filename = f"RECIBO_CFE_{pending['service_number']}.pdf"
    caption = f"⚡ Recibo CFE\nServicio: {pending['service_number']}\nSolicitó: {pending['requester_name']}"
    send_pdf_base64(pending['client_group_jid'], raw, filename, caption, pending['client_instance'])
    with SessionLocal() as db:
        row = db.scalar(select(CfeRequest).where(CfeRequest.request_key == key).with_for_update())
        if row:
            row.status = 'DONE'; row.provider_response_message_id = response_message_id; row.provider_pdf_filename = filename; row.completed_at = datetime.now(timezone.utc)
            _increment_usage(db, row)
            db.commit()
    finish(key, pending.get('provider_message_id', ''))
    print('CFE_REQUEST_DONE', {'request_key': key, 'service_number': pending['service_number']}, flush=True)
    return {'ok': True, 'status': 'DONE'}
