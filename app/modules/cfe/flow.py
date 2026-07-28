import hashlib
import json
import time
from app.config import settings
from app.queue import redis_conn


def request_key(instance: str, group_jid: str, message_id: str) -> str:
    return hashlib.sha256(f'{instance}|{group_jid}|{message_id}'.encode()).hexdigest()


def _pending_key(key: str) -> str:
    return f'extras:cfe:pending:{key}'


def _provider_key(message_id: str) -> str:
    return f'extras:cfe:provider-message:{message_id}'


def save_pending(key: str, payload: dict) -> None:
    redis_conn.setex(_pending_key(key), settings.CFE_PENDING_TTL_SECONDS, json.dumps(payload, ensure_ascii=False))


def load_pending(key: str) -> dict:
    raw = redis_conn.get(_pending_key(key))
    return json.loads(raw) if raw else {}


def associate_provider_message(key: str, provider_message_id: str) -> None:
    redis_conn.setex(_provider_key(provider_message_id), settings.CFE_PENDING_TTL_SECONDS, key)


def resolve_by_provider_message(provider_message_id: str) -> str:
    return redis_conn.get(_provider_key(provider_message_id)) or ''


def claim_delivery(key: str) -> bool:
    return bool(redis_conn.set(f'extras:cfe:delivery-claim:{key}', str(time.time()), nx=True, ex=settings.CFE_PENDING_TTL_SECONDS))


def finish(key: str, provider_message_id: str = '') -> None:
    keys = [_pending_key(key), f'extras:cfe:delivery-claim:{key}']
    if provider_message_id:
        keys.append(_provider_key(provider_message_id))
    redis_conn.delete(*keys)
