"""provider listings and activations

Revision ID: e3b2a91d7c55
Revises: d8f1b34c9e07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'e3b2a91d7c55'
down_revision = 'd8f1b34c9e07'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('provider_listings',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('provider_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('metadata_json', sa.Text(), nullable=False),
    sa.Column('enforcement_classification', sa.String(), nullable=False),
    sa.Column('classification_evidence_json', sa.Text(), nullable=False),
    sa.Column('recorded_at', sa.String(), nullable=False),
    sa.Column('provenance', sa.String(), nullable=False),
    sa.CheckConstraint("enforcement_classification IN ('enforcing', 'monitor_only')", name='ck_provider_listings_classification'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('provider_listings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_provider_listings_provider_id'), ['provider_id'], unique=False)

    op.create_table('provider_activations',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('listing_id', sa.String(), nullable=False),
    sa.Column('decision_record_id', sa.String(), nullable=False),
    sa.Column('state', sa.String(), nullable=False),
    sa.Column('recorded_at', sa.String(), nullable=False),
    sa.Column('provenance', sa.String(), nullable=False),
    sa.CheckConstraint("state IN ('active', 'disabled', 'revoked')", name='ck_provider_activations_state'),
    sa.ForeignKeyConstraint(['decision_record_id'], ['decision_records.id'], ),
    sa.ForeignKeyConstraint(['listing_id'], ['provider_listings.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('provider_activations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_provider_activations_decision_record_id'), ['decision_record_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_provider_activations_listing_id'), ['listing_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('provider_activations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_provider_activations_listing_id'))
        batch_op.drop_index(batch_op.f('ix_provider_activations_decision_record_id'))

    op.drop_table('provider_activations')
    with op.batch_alter_table('provider_listings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_provider_listings_provider_id'))

    op.drop_table('provider_listings')
