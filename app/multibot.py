import re
import secrets
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.models import AuthorizedGroup, BotControl, ProviderSetting


def normalize_instance(value: str) -> str:
    value = re.sub(r'[^a-zA-Z0-9_-]+', '', (value or '').strip())
    if not value or len(value) > 120:
        raise ValueError('INSTANCE_NAME_INVALID')
    return value


def new_panel_token() -> str:
    return secrets.token_urlsafe(32)


def get_bot(db: Session, instance: str) -> BotControl | None:
    return db.scalar(select(BotControl).where(BotControl.instance_name == instance))


def client_instance_allowed(db: Session, instance: str) -> tuple[bool, str]:
    if instance in settings.cfe_client_instances or instance == settings.MAIN_INSTANCE:
        return True, 'legacy_or_main'
    bot = get_bot(db, instance)
    if not bot or not bot.is_active:
        return False, 'instance_not_registered'
    if bot.is_blocked:
        return False, 'bot_blocked'
    if bot.limit_total > 0 and bot.used_total >= bot.limit_total:
        return False, 'limit_exhausted'
    return True, 'ok'


def claim_or_validate_group(
    db: Session,
    group_jid: str,
    instance: str,
) -> tuple[bool, str]:
    """
    Solo valida grupos previamente autorizados.

    Un grupo nuevo no se registra automáticamente
    cuando manda un número de servicio. Debe
    autorizarse con /addgroup o desde el panel.
    """

    row = db.scalar(
        select(
            AuthorizedGroup
        ).where(
            AuthorizedGroup.group_jid
            == group_jid
        )
    )

    if row is None:
        return (
            False,
            "group_not_authorized",
        )

    if row.owner_instance != instance:
        return (
            False,
            "group_owned_by_other_instance",
        )

    if row.is_blocked:
        return (
            False,
            "group_blocked",
        )

    return True, "ok"


def enabled_cfe_providers(db: Session) -> list[ProviderSetting]:
    return list(db.scalars(select(ProviderSetting).where(
        ProviderSetting.module == 'CFE', ProviderSetting.is_enabled.is_(True),
        ProviderSetting.provider_type == 'WHATSAPP_GROUP', ProviderSetting.group_jid.is_not(None)
    ).order_by(ProviderSetting.priority.asc(), ProviderSetting.id.asc())).all())


def provider_by_group(db: Session, group_jid: str) -> ProviderSetting | None:
    return db.scalar(select(ProviderSetting).where(
        ProviderSetting.group_jid == group_jid,
        ProviderSetting.is_enabled.is_(True)
    ))
