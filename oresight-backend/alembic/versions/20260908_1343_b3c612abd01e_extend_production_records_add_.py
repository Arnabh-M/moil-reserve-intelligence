"""extend production_records; add production_record_audit; site_notes revision groundwork

Revision ID: b3c612abd01e
Revises: ddd398038e1a
Create Date: 2026-09-08 13:43:22.962500+00:00

Field Intake Hardening Phase 1 (production persistence) + Phase 2's §6
site_notes revision groundwork. Purely additive.

WHY THIS MIGRATION IS WRITTEN AS CONDITIONAL DDL, NOT A PLAIN AUTOGENERATE
DUMP: `alembic revision --autogenerate` against this dev DB produced a
completely empty diff (`upgrade()`/`downgrade()` both just `pass`). That's
because a prior session had already applied this exact schema change and
was killed before committing a migration file for it; the DB was left with
the columns physically present, and `alembic_version` was stamped back to
this migration's parent (`ddd398038e1a`) once the orphaned schema was
verified to match. Autogenerate diffs the live DB via reflection, so
seeing no difference is correct given that history — but shipping the
empty migration as-is would be silently wrong everywhere else: a fresh
clone, CI, or prod has none of these columns and would get nothing.

So every statement below uses `IF NOT EXISTS` (native since Postgres 9.6)
or a `DO $$ ... $$` existence guard, making this migration simultaneously:
  - a genuine schema-creating migration on a fresh DB, and
  - a safe no-op re-application on this dev DB, where the state already
    matches.
`downgrade()` is NOT conditional in the same way — it always removes the
columns/table/constraint this migration owns, which is the correct
"undo" semantics regardless of how upgrade() got there.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3c612abd01e'
down_revision: Union[str, None] = 'ddd398038e1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- new table: production_record_audit --
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS production_record_audit (
            id SERIAL PRIMARY KEY,
            record_id INTEGER NOT NULL REFERENCES production_records(id) ON DELETE CASCADE,
            field VARCHAR NOT NULL,
            old_value TEXT,
            new_value TEXT,
            changed_by VARCHAR DEFAULT 'system',
            changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_production_record_audit_changed_at "
        "ON production_record_audit (changed_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_production_record_audit_record_id "
        "ON production_record_audit (record_id)"
    )

    # -- production_records: new columns (all nullable or server-defaulted,
    # so every existing row stays valid with no backfill) --
    op.execute(
        "ALTER TABLE production_records "
        "ADD COLUMN IF NOT EXISTS shift VARCHAR NOT NULL DEFAULT 'general'"
    )
    op.execute("ALTER TABLE production_records ADD COLUMN IF NOT EXISTS operating_hours NUMERIC(4,2)")
    op.execute("ALTER TABLE production_records ADD COLUMN IF NOT EXISTS downtime_hours NUMERIC(4,2)")
    op.execute("ALTER TABLE production_records ADD COLUMN IF NOT EXISTS material_processed NUMERIC")
    op.execute("ALTER TABLE production_records ADD COLUMN IF NOT EXISTS quality_grade NUMERIC(5,2)")
    op.execute("ALTER TABLE production_records ADD COLUMN IF NOT EXISTS shortfall_reasons VARCHAR[]")
    op.execute("ALTER TABLE production_records ADD COLUMN IF NOT EXISTS shortfall_other_note TEXT")
    op.execute("ALTER TABLE production_records ADD COLUMN IF NOT EXISTS variance_class VARCHAR")
    op.execute(
        "ALTER TABLE production_records "
        "ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
    )
    op.execute("ALTER TABLE production_records ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ")
    op.execute(
        "ALTER TABLE production_records "
        "ADD COLUMN IF NOT EXISTS created_by VARCHAR DEFAULT 'system'"
    )
    op.execute("ALTER TABLE production_records ADD COLUMN IF NOT EXISTS updated_by VARCHAR")

    # -- constraint swap: (site_id, date) -> (site_id, date, shift) --
    # Every existing row already has shift='general' via the column default
    # above, so the new 3-column constraint is satisfiable immediately.
    # New constraint created first (existence-guarded), old one dropped only
    # if still present — the table is covered by a unique constraint at
    # every point in between, and this is safe to re-run.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_production_records_site_date_shift'
            ) THEN
                ALTER TABLE production_records
                    ADD CONSTRAINT uq_production_records_site_date_shift UNIQUE (site_id, date, shift);
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_production_records_site_date'
            ) THEN
                ALTER TABLE production_records DROP CONSTRAINT uq_production_records_site_date;
            END IF;
        END $$;
        """
    )

    # -- site_notes: revision groundwork (§6) — no update endpoint exists
    # yet, these columns are unused by any current code path --
    op.execute("ALTER TABLE site_notes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ")
    op.execute(
        "ALTER TABLE site_notes ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE site_notes DROP COLUMN IF EXISTS revision")
    op.execute("ALTER TABLE site_notes DROP COLUMN IF EXISTS updated_at")

    # Reverse of the upgrade swap: old constraint back first, then drop the
    # new one — never a moment without a duplicate-guard.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_production_records_site_date'
            ) THEN
                ALTER TABLE production_records
                    ADD CONSTRAINT uq_production_records_site_date UNIQUE (site_id, date);
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_production_records_site_date_shift'
            ) THEN
                ALTER TABLE production_records DROP CONSTRAINT uq_production_records_site_date_shift;
            END IF;
        END $$;
        """
    )

    op.execute("ALTER TABLE production_records DROP COLUMN IF EXISTS updated_by")
    op.execute("ALTER TABLE production_records DROP COLUMN IF EXISTS created_by")
    op.execute("ALTER TABLE production_records DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE production_records DROP COLUMN IF EXISTS created_at")
    op.execute("ALTER TABLE production_records DROP COLUMN IF EXISTS variance_class")
    op.execute("ALTER TABLE production_records DROP COLUMN IF EXISTS shortfall_other_note")
    op.execute("ALTER TABLE production_records DROP COLUMN IF EXISTS shortfall_reasons")
    op.execute("ALTER TABLE production_records DROP COLUMN IF EXISTS quality_grade")
    op.execute("ALTER TABLE production_records DROP COLUMN IF EXISTS material_processed")
    op.execute("ALTER TABLE production_records DROP COLUMN IF EXISTS downtime_hours")
    op.execute("ALTER TABLE production_records DROP COLUMN IF EXISTS operating_hours")
    op.execute("ALTER TABLE production_records DROP COLUMN IF EXISTS shift")

    op.execute("DROP TABLE IF EXISTS production_record_audit")
