from typing import Any


def get_data(payload: dict) -> dict:
    data = payload.get('data')
    return data if isinstance(data, dict) else payload


def get_instance(payload: dict) -> str:
    data = get_data(payload)
    return str(payload.get('instance') or data.get('instance') or '').strip()


def get_key(payload: dict) -> dict:
    data = get_data(payload)
    key = data.get('key') or payload.get('key') or {}
    return key if isinstance(key, dict) else {}


def get_remote_jid(payload: dict) -> str:
    return str(get_key(payload).get('remoteJid') or '').strip()


def get_message_id(payload: dict) -> str:
    return str(get_key(payload).get('id') or '').strip()


def get_from_me(payload: dict) -> bool:
    return bool(get_key(payload).get('fromMe'))


def get_participant(payload: dict) -> str:
    key = get_key(payload)
    data = get_data(payload)
    return str(key.get('participant') or data.get('participant') or '').strip()


def get_push_name(payload: dict) -> str:
    data = get_data(payload)
    return str(data.get('pushName') or payload.get('pushName') or 'Cliente').strip()


def unwrap_message(message: dict) -> dict:
    current = message or {}
    for wrapper in ('ephemeralMessage', 'viewOnceMessage', 'viewOnceMessageV2', 'documentWithCaptionMessage'):
        wrapped = current.get(wrapper)
        if isinstance(wrapped, dict) and isinstance(wrapped.get('message'), dict):
            current = wrapped['message']
    return current


def get_message(payload: dict) -> dict:
    data = get_data(payload)
    message = data.get('message') or payload.get('message') or {}
    return unwrap_message(message if isinstance(message, dict) else {})


def get_text(payload: dict) -> str:
    message = get_message(payload)
    ext = message.get('extendedTextMessage') or {}
    image = message.get('imageMessage') or {}
    document = message.get('documentMessage') or {}
    return str(message.get('conversation') or ext.get('text') or image.get('caption') or document.get('caption') or '').strip()


def get_document(payload: dict) -> dict:
    message = get_message(payload)
    doc = message.get('documentMessage') or {}
    return doc if isinstance(doc, dict) else {}


def get_quoted_message_id(payload: dict) -> str:
    message = get_message(payload)
    contexts: list[dict[str, Any]] = []
    for value in message.values():
        if isinstance(value, dict) and isinstance(value.get('contextInfo'), dict):
            contexts.append(value['contextInfo'])
    data = get_data(payload)
    if isinstance(data.get('contextInfo'), dict):
        contexts.append(data['contextInfo'])
    for context in contexts:
        for key in ('stanzaId', 'quotedStanzaId', 'quotedStanzaID', 'quotedMessageId', 'quotedMessageID'):
            if context.get(key):
                return str(context[key]).strip()
    return ''
