"""chunk_entities junction table

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-03 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chunk_entities",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("chunk_id", sa.Uuid(), sa.ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.Uuid(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("chunk_id", "entity_id", name="uq_chunk_entity"),
    )
    op.create_index("idx_ce_chunk_id", "chunk_entities", ["chunk_id"])
    op.create_index("idx_ce_entity_id", "chunk_entities", ["entity_id"])


def downgrade() -> None:
    op.drop_index("idx_ce_entity_id", table_name="chunk_entities")
    op.drop_index("idx_ce_chunk_id", table_name="chunk_entities")
    op.drop_table("chunk_entities")
