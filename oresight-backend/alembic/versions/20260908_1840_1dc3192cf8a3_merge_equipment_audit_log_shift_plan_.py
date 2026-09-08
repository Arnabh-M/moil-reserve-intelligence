"""merge equipment-audit-log/shift-plan mergepoint with weather-records head

Revision ID: 1dc3192cf8a3
Revises: 27b8a5098be2, c47a19e83b21
Create Date: 2026-09-08 18:40:25.536952+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = '1dc3192cf8a3'
down_revision: Union[str, None] = ('27b8a5098be2', 'c47a19e83b21')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
