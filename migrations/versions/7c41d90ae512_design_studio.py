"""design studio projects

Revision ID: 7c41d90ae512
Revises: 2b9aba54f861
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = '7c41d90ae512'
down_revision = '2b9aba54f861'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('designproject',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('inscription', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('normalized_inscription', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('item_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('frame', sa.JSON(), nullable=True),
    sa.Column('letter_sequence', sa.JSON(), nullable=True),
    sa.Column('verification', sa.JSON(), nullable=True),
    sa.Column('variants', sa.JSON(), nullable=True),
    sa.Column('validations', sa.JSON(), nullable=True),
    sa.Column('selected_variant', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('approver', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('approval_note', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('export_manifest', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('designproject')
