from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

try:
    from pgvector.sqlalchemy import Vector

    EMBEDDING_TYPE: Any = Vector(128).with_variant(JSON(), "sqlite")
except ImportError:
    EMBEDDING_TYPE = JSON()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(24), default="engineer", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProductSeries(TimestampMixin, Base):
    __tablename__ = "product_series"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    manufacturer: Mapped[str] = mapped_column(String(120))
    source_url: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str] = mapped_column(String(255))
    data_classification: Mapped[str] = mapped_column(String(40), default="official_public")
    models: Mapped[list["MachineModel"]] = relationship(back_populates="series")


class MachineModel(TimestampMixin, Base):
    __tablename__ = "machine_models"
    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("product_series.id"), index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(32), default="public-web")
    specs: Mapped[dict] = mapped_column(JSON, default=dict)
    source_url: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24), default="active")
    data_classification: Mapped[str] = mapped_column(String(40), default="official_public")
    series: Mapped[ProductSeries] = relationship(back_populates="models")


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("checksum", name="uq_documents_checksum"),
        UniqueConstraint("title", "version", name="uq_documents_title_version"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(Text)
    doc_type: Mapped[str] = mapped_column(String(40), default="manual")
    version: Mapped[str] = mapped_column(String(64), default="1.0")
    model_codes: Mapped[list] = mapped_column(JSON, default=list)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_kind: Mapped[str] = mapped_column(String(40), default="internal")
    review_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    parse_status: Mapped[str] = mapped_column(String(24), default="pending")
    parse_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checksum: Mapped[str] = mapped_column(String(64))
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(EMBEDDING_TYPE, nullable=True)
    document: Mapped[Document] = relationship(back_populates="chunks")


class Alarm(TimestampMixin, Base):
    __tablename__ = "alarms"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    system: Mapped[str] = mapped_column(String(80))
    applies_to: Mapped[list] = mapped_column(JSON, default=list)
    symptoms: Mapped[list] = mapped_column(JSON, default=list)
    possible_causes: Mapped[list] = mapped_column(JSON, default=list)
    checks: Mapped[list] = mapped_column(JSON, default=list)
    actions: Mapped[list] = mapped_column(JSON, default=list)
    stop_conditions: Mapped[list] = mapped_column(JSON, default=list)
    source_title: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_section: Mapped[str] = mapped_column(String(120))
    knowledge_version: Mapped[str] = mapped_column(String(40), default="demo-1.0")
    review_status: Mapped[str] = mapped_column(String(24), default="published")
    data_classification: Mapped[str] = mapped_column(String(40), default="demo_process_data")


class Part(TimestampMixin, Base):
    __tablename__ = "parts"
    id: Mapped[int] = mapped_column(primary_key=True)
    part_no: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80))
    applies_to: Mapped[list] = mapped_column(JSON, default=list)
    replaces: Mapped[list] = mapped_column(JSON, default=list)
    key_specs: Mapped[dict] = mapped_column(JSON, default=dict)
    verification_notes: Mapped[list] = mapped_column(JSON, default=list)
    source_title: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(String(24), default="published")
    data_classification: Mapped[str] = mapped_column(String(40), default="demo_process_data")


class MaintenanceCase(TimestampMixin, Base):
    __tablename__ = "maintenance_cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_no: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    model_code: Mapped[str] = mapped_column(String(64), index=True)
    alarm_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    symptom: Mapped[str] = mapped_column(Text)
    root_cause: Mapped[str] = mapped_column(Text)
    resolution: Mapped[str] = mapped_column(Text)
    verification: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")
    review_status: Mapped[str] = mapped_column(String(24), default="published")
    data_classification: Mapped[str] = mapped_column(String(40), default="demo_process_data")


class KnowledgeItem(TimestampMixin, Base):
    __tablename__ = "knowledge_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    item_type: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(Text)
    applies_to: Mapped[list] = mapped_column(JSON, default=list)
    source_title: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_section: Mapped[str | None] = mapped_column(String(120), nullable=True)
    version: Mapped[str] = mapped_column(String(40), default="1.0")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    review_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_classification: Mapped[str] = mapped_column(String(40), default="internal")


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="新会话")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    context: Mapped["ConversationContext | None"] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", uselist=False
    )


class ConversationContext(TimestampMixin, Base):
    """Structured troubleshooting state kept separately from the immutable chat log."""

    __tablename__ = "conversation_contexts"
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    model_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    alarm_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    symptom: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_checks: Mapped[list] = mapped_column(JSON, default=list)
    feedback_history: Mapped[list] = mapped_column(JSON, default=list)
    latest_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="collecting_information")
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    history_start_message_id: Mapped[int] = mapped_column(Integer, default=0)
    conversation: Mapped[Conversation] = relationship(back_populates="context")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(60))
    target_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
