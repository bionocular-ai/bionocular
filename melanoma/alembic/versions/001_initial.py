"""Initial migration for documents table.

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE documenttype AS ENUM ('abstract', 'publication')")
    op.execute("CREATE TYPE documentstatus AS ENUM ('ingested', 'processing_failed')")
    
    # Create documents table
    op.create_table('documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('type', sa.Enum('abstract', 'publication', name='documenttype'), nullable=False),
        sa.Column('upload_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.Enum('ingested', 'processing_failed', name='documentstatus'), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_documents_hash'), 'documents', ['hash'], unique=True)
    op.create_index(op.f('ix_documents_id'), 'documents', ['id'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_documents_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_hash'), table_name='documents')
    
    # Drop table
    op.drop_table('documents')
    
    # Drop enum types
    op.execute("DROP TYPE documentstatus")
    op.execute("DROP TYPE documenttype")
