import base64
import time
from typing import Any
import requests
from app.config import settings


def _headers() -> dict[str, str]:
    return {'apikey': settings.EVOLUTION_API_KEY, 'Content-Type': 'application/json'}


def _normalize_number(number: str) -> str:
    value = str(number or '').strip()
    if '@g.us' in value:
        return value
    return value.replace('@s.whatsapp.net', '').replace('+', '').replace(' ', '')


def _post(url: str, payload: dict[str, Any], label: str, attempts: int = 3, timeout=(8, 90)) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            print(label, {'attempt': attempt, 'url': url, 'number': payload.get('number')}, flush=True)
            response = requests.post(url, headers=_headers(), json=payload, timeout=timeout)
            body = response.text or ''
            print(f'{label}_STATUS', response.status_code, flush=True)
            if response.status_code in (200, 201):
                try:
                    return response.json()
                except Exception:
                    return {'ok': True, 'raw': body[:1000]}
            response.raise_for_status()
        except Exception as exc:
            last_error = exc
            print(f'{label}_ERROR', str(exc), flush=True)
            if attempt < attempts:
                time.sleep(min(2 ** attempt, 8))
    assert last_error is not None
    raise last_error


def send_text(number: str, text: str, instance_name: str) -> dict:
    url = f"{settings.EVOLUTION_BASE_URL.rstrip('/')}/message/sendText/{instance_name}"
    return _post(url, {'number': _normalize_number(number), 'text': (text or '').strip()}, 'EXTRAS_SEND_TEXT', attempts=2, timeout=(5, 35))


def send_pdf_base64(number: str, media_b64: str, filename: str, caption: str, instance_name: str) -> dict:
    raw = (media_b64 or '').strip()
    if raw.startswith('data:'):
        raw = raw.split(',', 1)[1]
    raw = raw.replace('\n', '').replace('\r', '')
    pdf_bytes = base64.b64decode(raw, validate=False)
    if not pdf_bytes.startswith(b'%PDF'):
        raise ValueError('MEDIA_IS_NOT_PDF')
    url = f"{settings.EVOLUTION_BASE_URL.rstrip('/')}/message/sendMedia/{instance_name}"
    payload = {'number': _normalize_number(number), 'mediatype': 'document', 'mimetype': 'application/pdf', 'caption': caption, 'fileName': filename, 'media': raw}
    return _post(url, payload, 'EXTRAS_SEND_PDF', attempts=4, timeout=(8, 90))


def get_media_base64(message_id: str, instance_name: str) -> dict:
    url = f"{settings.EVOLUTION_BASE_URL.rstrip('/')}/chat/getBase64FromMediaMessage/{instance_name}"
    payload = {'message': {'key': {'id': message_id}}, 'convertToMp4': False}
    return _post(url, payload, 'EXTRAS_GET_MEDIA', attempts=3, timeout=(5, 35))


def extract_sent_message_id(response: dict) -> str:
    candidates = [
        response.get('key', {}).get('id') if isinstance(response.get('key'), dict) else None,
        response.get('id'), response.get('messageId'),
        response.get('data', {}).get('key', {}).get('id') if isinstance(response.get('data'), dict) else None,
    ]
    return next((str(x).strip() for x in candidates if x), '')
