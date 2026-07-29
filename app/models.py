from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class CfeRequest(Base):
    __tablename__ = 'cfe_requests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_key: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    service_number: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    requester_wa_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    requester_name: Mapped[str | None] = mapped_column(String(160))
    client_group_jid: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    client_instance: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    client_message_id: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    provider_name: Mapped[str | None] = mapped_column(String(120), index=True)
    provider_group_jid: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    provider_instance: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # transporte, compatibilidad
    provider_message_id: Mapped[str | None] = mapped_column(String(180), index=True)
    provider_response_message_id: Mapped[str | None] = mapped_column(String(180), unique=True, index=True)
    provider_pdf_filename: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='QUEUED', index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    delivery_claimed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    usage_counted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RenapoRequest(Base):
    __tablename__ = 'renapo_requests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_key: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    curp: Mapped[str] = mapped_column(String(18), nullable=False, index=True)
    requester_wa_id: Mapped[str] = mapped_column(String(100), nullable=False)
    client_group_jid: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    client_instance: Mapped[str] = mapped_column(String(100), nullable=False)
    client_message_id: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='DISABLED', index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BotControl(Base):
    __tablename__ = 'bot_controls'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    panel_token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    limit_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    used_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AuthorizedGroup(Base):
    __tablename__ = 'authorized_groups'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_jid: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    owner_instance: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    custom_name: Mapped[str | None] = mapped_column(String(200))
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ProviderSetting(Base):
    __tablename__ = 'provider_settings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    module: Mapped[str] = mapped_column(String(30), nullable=False, default='CFE', index=True)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False, default='WHATSAPP_GROUP')
    group_jid: Mapped[str | None] = mapped_column(String(160), unique=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    no_record_phrases: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class BotRechargeLog(Base):
    __tablename__ = 'bot_recharge_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    new_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    used_at_recharge: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
