"""add site_notes table + pgvector extension

Revision ID: b1f3c7a9d2e4
Revises: fff62028844f
Create Date: 2026-09-02 16:00:00.000000+00:00

Enables the `vector` extension (shipped by Dockerfile.postgres — the stock
postgis image doesn't have it) and adds `site_notes`, which stores a
free-text note plus its embedding for similarity search.

No ANN index (HNSW / IVFFlat) on `embedding` on purpose: at demo scale
(tens of rows) a sequential scan + sort is sub-millisecond, and a special
vector index is the one thing most likely to make `alembic revision
--autogenerate` emit a spurious diff (see
tests/test_migrations.py::test_autogenerate_ignores_tiger_and_topology_schemas).
Add one here if `site_notes` ever grows past a few thousand rows.
"""
from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1f3c7a9d2e4"
down_revision: Union[str, None] = "fff62028844f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 256


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "site_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(EMBEDDING_DIM), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_site_notes_site_id"), "site_notes", ["site_id"], unique=False)
    op.create_index(
        op.f("ix_site_notes_created_at"), "site_notes", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_site_notes_created_at"), table_name="site_notes")
    op.drop_index(op.f("ix_site_notes_site_id"), table_name="site_notes")
    op.drop_table("site_notes")
    # Leave the `vector` extension installed — dropping an extension is not
    # implied by dropping one table that used it, and nothing else here owns it.
