import requests
from app.config import settings


def _headers():
    return {'apikey': settings.EVOLUTION_API_KEY, 'Content-Type': 'application/json'}


def _url(path: str) -> str:
    return f"{settings.EVOLUTION_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def create_instance(instance_name: str) -> dict:
    r = requests.post(_url('instance/create'), headers=_headers(), json={
        'instanceName': instance_name, 'qrcode': True, 'integration': 'WHATSAPP-BAILEYS'
    }, timeout=30)
    if r.status_code not in (200, 201) and 'already' not in r.text.lower():
        r.raise_for_status()
    return r.json() if r.content else {'ok': True}


def set_webhook(instance_name: str) -> dict:
    public = settings.PUBLIC_BASE_URL.rstrip('/')
    if not public:
        raise RuntimeError('PUBLIC_BASE_URL_EMPTY')
    url = f"{public}/webhooks/evolution?secret={settings.WEBHOOK_SECRET}"
    r = requests.post(_url(f'webhook/set/{instance_name}'), headers=_headers(), json={
        'webhook': {'enabled': True, 'url': url, 'webhook_by_events': False, 'events': ['MESSAGES_UPSERT']}
    }, timeout=30)
    r.raise_for_status()
    return r.json() if r.content else {'ok': True}


def connection_state(instance_name: str) -> str:
    r = requests.get(_url(f'instance/connectionState/{instance_name}'), headers=_headers(), timeout=10)
    if r.status_code == 404:
        return 'missing'
    r.raise_for_status()
    data = r.json()
    return str(data.get('instance', {}).get('state') or data.get('state') or 'unknown').lower()


def connect_instance(instance_name: str) -> dict:
    r = requests.get(_url(f'instance/connect/{instance_name}'), headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json() if r.content else {}
