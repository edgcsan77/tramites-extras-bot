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
    provider_group_jid: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    provider_instance: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(180), index=True)
    provider_response_message_id: Mapped[str | None] = mapped_column(String(180), unique=True, index=True)
    provider_pdf_filename: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='QUEUED', index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    delivery_claimed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
