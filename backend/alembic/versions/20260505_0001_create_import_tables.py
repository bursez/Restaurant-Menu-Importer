"""create import persistence tables

Revision ID: 20260505_0001
Revises:
Create Date: 2026-05-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260505_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_type", sa.String(length=32), nullable=False),
        sa.Column("source_value", sa.Text(), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ck_imports_status",
        ),
        sa.CheckConstraint(
            "input_type IN ('text', 'url', 'file')",
            name="ck_imports_input_type",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_imports_created_at", "imports", ["created_at"], unique=False)
    op.create_index("ix_imports_status", "imports", ["status"], unique=False)

    op.create_table(
        "extracted_menus",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("restaurant_name", sa.String(length=255), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "validation_status IN ('pending', 'valid', 'invalid')",
            name="ck_extracted_menus_validation_status",
        ),
        sa.ForeignKeyConstraint(["import_id"], ["imports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_id"),
    )
    op.create_index("ix_extracted_menus_restaurant_name", "extracted_menus", ["restaurant_name"], unique=False)

    op.create_table(
        "import_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["import_id"], ["imports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_events_created_at", "import_events", ["created_at"], unique=False)
    op.create_index("ix_import_events_import_id", "import_events", ["import_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_import_events_import_id", table_name="import_events")
    op.drop_index("ix_import_events_created_at", table_name="import_events")
    op.drop_table("import_events")
    op.drop_index("ix_extracted_menus_restaurant_name", table_name="extracted_menus")
    op.drop_table("extracted_menus")
    op.drop_index("ix_imports_status", table_name="imports")
    op.drop_index("ix_imports_created_at", table_name="imports")
    op.drop_table("imports")
