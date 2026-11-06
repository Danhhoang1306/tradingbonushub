"""free text fields from the design (hero card, featured bonus line, rail)

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

BANNER_COLUMNS = (("rail_amount", 20), ("rail_note", 60), ("rail_desc", 255), ("rail_line", 60))


def upgrade() -> None:
    with op.batch_alter_table('brokers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('featured_bonus_text', sa.String(length=60), nullable=False, server_default=''))
    with op.batch_alter_table('banners', schema=None) as batch_op:
        for name, size in BANNER_COLUMNS:
            batch_op.add_column(sa.Column(name, sa.String(length=size), nullable=False, server_default=''))


def downgrade() -> None:
    with op.batch_alter_table('banners', schema=None) as batch_op:
        for name, _ in BANNER_COLUMNS:
            batch_op.drop_column(name)
    with op.batch_alter_table('brokers', schema=None) as batch_op:
        batch_op.drop_column('featured_bonus_text')
