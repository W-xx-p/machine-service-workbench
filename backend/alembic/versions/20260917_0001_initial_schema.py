"""Create the initial machine service workbench schema.

Revision ID: 20260917_0001
Revises: None
Create Date: 2026-09-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260917_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        from pgvector.sqlalchemy import Vector

        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        embedding_type = Vector(128)
    else:
        embedding_type = sa.JSON()

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "product_series",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("manufacturer", sa.String(120), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_title", sa.String(255), nullable=False),
        sa.Column("data_classification", sa.String(40), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_product_series_code", "product_series", ["code"], unique=True)

    op.create_table(
        "machine_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "series_id",
            sa.Integer(),
            sa.ForeignKey("product_series.id", name="fk_machine_models_series_id"),
            nullable=False,
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("specs", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("data_classification", sa.String(40), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_machine_models_series_id", "machine_models", ["series_id"])
    op.create_index("ix_machine_models_code", "machine_models", ["code"], unique=True)

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("doc_type", sa.String(40), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("model_codes", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_kind", sa.String(40), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("parse_status", sa.String(24), nullable=False),
        sa.Column("parse_message", sa.Text(), nullable=True),
        sa.Column(
            "uploaded_by",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_documents_uploaded_by"),
            nullable=False,
        ),
        sa.Column(
            "reviewed_by",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_documents_reviewed_by"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_documents_title", "documents", ["title"])
    op.create_index("ix_documents_review_status", "documents", ["review_status"])
    op.create_index("ix_documents_checksum", "documents", ["checksum"])

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", name="fk_document_chunks_document_id"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(255), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", embedding_type, nullable=True),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])

    op.create_table(
        "alarms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("system", sa.String(80), nullable=False),
        sa.Column("applies_to", sa.JSON(), nullable=False),
        sa.Column("symptoms", sa.JSON(), nullable=False),
        sa.Column("possible_causes", sa.JSON(), nullable=False),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("stop_conditions", sa.JSON(), nullable=False),
        sa.Column("source_title", sa.String(255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_section", sa.String(120), nullable=False),
        sa.Column("knowledge_version", sa.String(40), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("data_classification", sa.String(40), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_alarms_code", "alarms", ["code"], unique=True)

    op.create_table(
        "parts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("part_no", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("applies_to", sa.JSON(), nullable=False),
        sa.Column("replaces", sa.JSON(), nullable=False),
        sa.Column("key_specs", sa.JSON(), nullable=False),
        sa.Column("verification_notes", sa.JSON(), nullable=False),
        sa.Column("source_title", sa.String(255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("data_classification", sa.String(40), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_parts_part_no", "parts", ["part_no"], unique=True)

    op.create_table(
        "maintenance_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_no", sa.String(80), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("model_code", sa.String(64), nullable=False),
        sa.Column("alarm_code", sa.String(64), nullable=True),
        sa.Column("symptom", sa.Text(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=False),
        sa.Column("verification", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("data_classification", sa.String(40), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_maintenance_cases_case_no", "maintenance_cases", ["case_no"], unique=True)
    op.create_index("ix_maintenance_cases_model_code", "maintenance_cases", ["model_code"])
    op.create_index("ix_maintenance_cases_alarm_code", "maintenance_cases", ["alarm_code"])

    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("item_type", sa.String(40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("applies_to", sa.JSON(), nullable=False),
        sa.Column("source_title", sa.String(255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_section", sa.String(120), nullable=True),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column(
            "reviewed_by",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_knowledge_items_reviewed_by"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_classification", sa.String(40), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_knowledge_items_title", "knowledge_items", ["title"])
    op.create_index("ix_knowledge_items_review_status", "knowledge_items", ["review_status"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_conversations_user_id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    op.create_table(
        "conversation_contexts",
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey(
                "conversations.id",
                name="fk_conversation_contexts_conversation_id",
                ondelete="CASCADE",
            ),
            primary_key=True,
        ),
        sa.Column("model_code", sa.String(64), nullable=True),
        sa.Column("serial_number", sa.String(80), nullable=True),
        sa.Column("alarm_code", sa.String(64), nullable=True),
        sa.Column("symptom", sa.Text(), nullable=True),
        sa.Column("completed_checks", sa.JSON(), nullable=False),
        sa.Column("feedback_history", sa.JSON(), nullable=False),
        sa.Column("latest_feedback", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False),
        sa.Column("history_start_message_id", sa.Integer(), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", name="fk_messages_conversation_id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("messages.id", name="fk_feedback_message_id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_feedback_user_id"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feedback_message_id", "feedback", ["message_id"])
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_audit_logs_user_id"),
            nullable=True,
        ),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(60), nullable=False),
        sa.Column("target_id", sa.String(80), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("feedback")
    op.drop_table("messages")
    op.drop_table("conversation_contexts")
    op.drop_table("conversations")
    op.drop_table("knowledge_items")
    op.drop_table("maintenance_cases")
    op.drop_table("parts")
    op.drop_table("alarms")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("machine_models")
    op.drop_table("product_series")
    op.drop_table("users")
