"""Initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-30 22:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # The app calls db.create_all() on startup, so tables can already exist
    # when this migration runs. Only create the ones that are missing.
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    # admins table
    if 'admins' not in existing:
        op.create_table(
            'admins',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('username', sa.String(length=80), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_admins_username'), 'admins', ['username'], unique=True)

    # documents table
    if 'documents' not in existing:
        op.create_table(
            'documents',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('public_id', sa.String(length=36), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('category', sa.String(length=100), nullable=True),
            sa.Column('tags', sa.String(length=255), nullable=True),
            sa.Column('author', sa.String(length=150), nullable=True),
            sa.Column('document_date', sa.Date(), nullable=True),
            sa.Column('expiry_date', sa.Date(), nullable=True),
            sa.Column('original_filename', sa.String(length=255), nullable=False),
            sa.Column('stored_filename', sa.String(length=255), nullable=False),
            sa.Column('file_extension', sa.String(length=10), nullable=False),
            sa.Column('mime_type', sa.String(length=100), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=False),
            sa.Column('uploaded_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('stored_filename')
        )
        op.create_index(op.f('ix_documents_category'), 'documents', ['category'], unique=False)
        op.create_index(op.f('ix_documents_is_active'), 'documents', ['is_active'], unique=False)
        op.create_index(op.f('ix_documents_public_id'), 'documents', ['public_id'], unique=True)
        op.create_index(op.f('ix_documents_title'), 'documents', ['title'], unique=False)

    # scan_logs table
    if 'scan_logs' not in existing:
        op.create_table(
            'scan_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('document_id', sa.Integer(), nullable=False),
            sa.Column('scanned_at', sa.DateTime(), nullable=False),
            sa.Column('user_agent', sa.String(length=512), nullable=True),
            sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_scan_logs_document_id'), 'scan_logs', ['document_id'], unique=False)

    # retired_public_ids table
    if 'retired_public_ids' not in existing:
        op.create_table(
            'retired_public_ids',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('public_id', sa.String(length=36), nullable=False),
            sa.Column('retired_at', sa.DateTime(), nullable=False),
            sa.Column('reason', sa.String(length=100), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_retired_public_ids_public_id'), 'retired_public_ids', ['public_id'], unique=True)

def downgrade():
    op.drop_index(op.f('ix_retired_public_ids_public_id'), table_name='retired_public_ids')
    op.drop_table('retired_public_ids')
    op.drop_index(op.f('ix_scan_logs_document_id'), table_name='scan_logs')
    op.drop_table('scan_logs')
    op.drop_index(op.f('ix_documents_title'), table_name='documents')
    op.drop_index(op.f('ix_documents_public_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_is_active'), table_name='documents')
    op.drop_index(op.f('ix_documents_category'), table_name='documents')
    op.drop_table('documents')
    op.drop_index(op.f('ix_admins_username'), table_name='admins')
    op.drop_table('admins')

