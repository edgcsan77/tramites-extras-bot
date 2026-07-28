import base64
from datetime import datetime, timezone
from sqlalchemy import select
from app.config import settings
from app.db import SessionLocal
from app.models import CfeRequest
from app.modules.cfe.flow import associate_provider_message, claim_delivery, finish, load_pending, request_key, resolve_by_provider_message, save_pending
from app.modules.cfe.parser import extract_service_number, text_is_no_record
from app.queue import redis_conn
from app.services.evolution import extract_sent_message_id, get_media_base64, send_pdf_base64, send_text
from app.webhook_utils import get_document, get_from_me, get_instance, get_message_id, get_participant, get_push_name, get_quoted_message_id, get_remote_jid, get_text


def process_client(payload: dict) -> dict:
    instance = get_instance(payload)
    remote_jid = get_remote_jid(payload)
    message_id = get_message_id(payload)
    if get_from_me(payload) or not remote_jid.endswith('@g.us') or instance not in settings.cfe_client_instances:
        return {'ok': True, 'ignored': 'not_client_request'}
    dedupe = f'extras:cfe:input:{message_id}'
    if not redis_conn.set(dedupe, '1', nx=True, ex=86400):
        return {'ok': True, 'ignored': 'duplicate'}
    service_number, error = extract_service_number(get_text(payload))
    requester = get_participant(payload) or remote_jid
    requester_name = get_push_name(payload)
    if error:
        send_text(remote_jid, f'⚠️ {requester_name}, {error}', instance)
        return {'ok': True, 'validation_error': error}
    key = request_key(instance, remote_jid, message_id)
    pending = {
        'request_key': key, 'service_number': service_number,
        'requester_wa_id': requester, 'requester_name': requester_name,
        'client_group_jid': remote_jid, 'client_instance': instance,
        'client_message_id': message_id,
        'provider_group_jid': settings.CFE_PROVIDER_GROUP_JID,
        'provider_instance': settings.CFE_PROVIDER_INSTANCE,
    }
    with SessionLocal() as db:
        row = CfeRequest(**pending, status='QUEUED')
        db.add(row); db.commit()
        save_pending(key, pending)
        response = send_text(settings.CFE_PROVIDER_GROUP_JID, service_number, settings.CFE_PROVIDER_INSTANCE)
        provider_message_id = extract_sent_message_id(response)
        if not provider_message_id:
            row.status = 'ERROR'; row.error_message = 'PROVIDER_MESSAGE_ID_EMPTY'; db.commit()
            raise RuntimeError('PROVIDER_MESSAGE_ID_EMPTY')
        associate_provider_message(key, provider_message_id)
        pending['provider_message_id'] = provider_message_id
        save_pending(key, pending)
        row.provider_message_id = provider_message_id; row.status = 'WAITING_PROVIDER'; db.commit()
    send_text(remote_jid, f'⚡ {requester_name}, solicitud recibida para el servicio {service_number}.', instance)
    print('CFE_SENT_TO_PROVIDER', {'request_key': key, 'provider_message_id': provider_message_id}, flush=True)
    return {'ok': True, 'request_key': key}


def process_provider(payload: dict) -> dict:
    instance = get_instance(payload)
    remote_jid = get_remote_jid(payload)
    if get_from_me(payload) or instance != settings.CFE_PROVIDER_INSTANCE or remote_jid != settings.CFE_PROVIDER_GROUP_JID:
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
    if text_is_no_record(text):
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
        row = db.scalar(select(CfeRequest).where(CfeRequest.request_key == key))
        if row:
            row.status = 'DONE'; row.provider_response_message_id = response_message_id; row.provider_pdf_filename = filename; row.completed_at = datetime.now(timezone.utc); db.commit()
    finish(key, pending.get('provider_message_id', ''))
    print('CFE_REQUEST_DONE', {'request_key': key, 'service_number': pending['service_number']}, flush=True)
    return {'ok': True, 'status': 'DONE'}
