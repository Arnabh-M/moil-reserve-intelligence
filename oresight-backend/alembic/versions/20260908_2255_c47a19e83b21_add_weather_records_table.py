"""add weather_records table

Revision ID: c47a19e83b21
Revises: db428e3b813a
Create Date: 2026-09-08 22:55:00.000000+00:00

Adds `weather_records` table to persist current observations and hourly forecast
records per MOIL mine site. Purely additive migration: no existing table, column,
or constraint is altered. Supports full downgrade rollback.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c47a19e83b21'
down_revision: Union[str, None] = 'db428e3b813a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'weather_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('rainfall_mm', sa.Float(), nullable=False, server_default=sa.text('0.0')),
        sa.Column('temperature_c', sa.Float(), nullable=True),
        sa.Column('humidity_pct', sa.Float(), nullable=True),
        sa.Column('wind_speed_kmh', sa.Float(), nullable=True),
        sa.Column('wind_direction_deg', sa.Float(), nullable=True),
        sa.Column('weather_type', sa.Text(), nullable=True),
        sa.Column('is_forecast', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('source', sa.Text(), nullable=False, server_default=sa.text("'open-meteo'")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('site_id', 'timestamp', 'is_forecast', name='uq_weather_records_site_timestamp_forecast'),
    )
    op.create_index(op.f('ix_weather_records_site_id'), 'weather_records', ['site_id'], unique=False)
    op.create_index(op.f('ix_weather_records_timestamp'), 'weather_records', ['timestamp'], unique=False)
    op.create_index('ix_weather_records_site_timestamp', 'weather_records', ['site_id', 'timestamp'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_weather_records_site_timestamp', table_name='weather_records')
    op.drop_index(op.f('ix_weather_records_timestamp'), table_name='weather_records')
    op.drop_index(op.f('ix_weather_records_site_id'), table_name='weather_records')
    op.drop_table('weather_records')
