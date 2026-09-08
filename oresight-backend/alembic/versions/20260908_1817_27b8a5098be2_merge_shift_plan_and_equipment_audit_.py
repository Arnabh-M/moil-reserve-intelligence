"""merge shift-plan and equipment-audit-log heads

Revision ID: 27b8a5098be2
Revises: db428e3b813a, 87b25057ff45
Create Date: 2026-09-08 18:17:14.380569+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = '27b8a5098be2'
down_revision: Union[str, None] = ('db428e3b813a', '87b25057ff45')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
