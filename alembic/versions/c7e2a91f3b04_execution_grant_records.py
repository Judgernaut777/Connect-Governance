"""execution grant records

Revision ID: c7e2a91f3b04
Revises: ba04fd9f1a6b
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'c7e2a91f3b04'
down_revision = 'ba04fd9f1a6b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('execution_grant_records',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('decision_record_id', sa.String(), nullable=False),
    sa.Column('grant_json', sa.Text(), nullable=False),
    sa.Column('issuer_key_id', sa.String(), nullable=False),
    sa.Column('provider_id', sa.String(), nullable=False),
    sa.Column('work_request_id', sa.String(), nullable=False),
    sa.Column('issued_at', sa.String(), nullable=False),
    sa.Column('not_before', sa.String(), nullable=True),
    sa.Column('not_after', sa.String(), nullable=True),
    sa.Column('correlation_id', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['decision_record_id'], ['decision_records.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('execution_grant_records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_execution_grant_records_correlation_id'), ['correlation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_execution_grant_records_decision_record_id'), ['decision_record_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_execution_grant_records_issuer_key_id'), ['issuer_key_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_execution_grant_records_provider_id'), ['provider_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_execution_grant_records_work_request_id'), ['work_request_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('execution_grant_records', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_execution_grant_records_work_request_id'))
        batch_op.drop_index(batch_op.f('ix_execution_grant_records_provider_id'))
        batch_op.drop_index(batch_op.f('ix_execution_grant_records_issuer_key_id'))
        batch_op.drop_index(batch_op.f('ix_execution_grant_records_decision_record_id'))
        batch_op.drop_index(batch_op.f('ix_execution_grant_records_correlation_id'))

    op.drop_table('execution_grant_records')
