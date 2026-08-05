"""revocation list records

Revision ID: d8f1b34c9e07
Revises: c7e2a91f3b04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'd8f1b34c9e07'
down_revision = 'c7e2a91f3b04'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('revocation_list_records',
    sa.Column('list_id', sa.String(), nullable=False),
    sa.Column('issuer_key_id', sa.String(), nullable=False),
    sa.Column('issued_at', sa.String(), nullable=False),
    sa.Column('list_json', sa.Text(), nullable=False),
    sa.Column('supersedes', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('list_id')
    )
    with op.batch_alter_table('revocation_list_records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_revocation_list_records_issuer_key_id'), ['issuer_key_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('revocation_list_records', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_revocation_list_records_issuer_key_id'))

    op.drop_table('revocation_list_records')
