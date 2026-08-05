"""Baseline the existing schema and add quota-token support."""

from alembic import op

from models_db import Base


revision = "20260805_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'user'")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS quota_limits JSONB DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS auth_version INTEGER DEFAULT 1 NOT NULL")


def downgrade() -> None:
    # The baseline is intentionally non-destructive for customer databases.
    pass
