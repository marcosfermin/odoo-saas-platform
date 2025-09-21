"""Initial schema with all SaaS platform tables

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
    # Create UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Create customers table
    op.create_table('customers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('company', sa.String(length=200), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False, default='owner'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('totp_secret', sa.String(length=32), nullable=True),
        sa.Column('backup_codes', sa.JSON(), nullable=True),
        sa.Column('max_tenants', sa.Integer(), nullable=False, default=5),
        sa.Column('max_quota_gb', sa.Integer(), nullable=False, default=50),
        sa.Column('stripe_customer_id', sa.String(length=100), nullable=True),
        sa.Column('paddle_customer_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.func.now()),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('email_verified_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_customers_email', 'customers', ['email'])
    
    # Create plans table
    op.create_table('plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_monthly', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('price_yearly', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False, default='USD'),
        sa.Column('max_tenants', sa.Integer(), nullable=False, default=1),
        sa.Column('max_users_per_tenant', sa.Integer(), nullable=False, default=10),
        sa.Column('max_db_size_gb', sa.Integer(), nullable=False, default=5),
        sa.Column('max_filestore_gb', sa.Integer(), nullable=False, default=2),
        sa.Column('features', postgresql.JSONB(astext_type=sa.Text()), nullable=True, default={}),
        sa.Column('allowed_modules', sa.JSON(), nullable=True),
        sa.Column('stripe_price_id_monthly', sa.String(length=100), nullable=True),
        sa.Column('stripe_price_id_yearly', sa.String(length=100), nullable=True),
        sa.Column('paddle_plan_id', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('trial_days', sa.Integer(), nullable=True, default=14),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create tenants table
    op.create_table('tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('state', sa.String(length=20), nullable=False, default='creating'),
        sa.Column('state_message', sa.Text(), nullable=True),
        sa.Column('db_name', sa.String(length=100), nullable=False),
        sa.Column('db_host', sa.String(length=255), nullable=True),
        sa.Column('db_port', sa.Integer(), nullable=True, default=5432),
        sa.Column('filestore_path', sa.String(length=500), nullable=True),
        sa.Column('filestore_bucket', sa.String(length=100), nullable=True),
        sa.Column('current_users', sa.Integer(), nullable=False, default=0),
        sa.Column('db_size_bytes', sa.BigInteger(), nullable=False, default=0),
        sa.Column('filestore_size_bytes', sa.BigInteger(), nullable=False, default=0),
        sa.Column('custom_domain', sa.String(length=255), nullable=True),
        sa.Column('ssl_cert_path', sa.String(length=500), nullable=True),
        sa.Column('ssl_key_path', sa.String(length=500), nullable=True),
        sa.Column('odoo_version', sa.String(length=10), nullable=False, default='16.0'),
        sa.Column('installed_modules', sa.JSON(), nullable=True, default=[]),
        sa.Column('odoo_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True, default={}),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.func.now()),
        sa.Column('suspended_at', sa.DateTime(), nullable=True),
        sa.Column('last_backup_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('db_size_bytes >= 0', name='positive_db_size'),
        sa.CheckConstraint('filestore_size_bytes >= 0', name='positive_filestore_size'),
        sa.CheckConstraint('current_users >= 0', name='positive_users'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
        sa.UniqueConstraint('db_name')
    )
    op.create_index('ix_tenants_slug', 'tenants', ['slug'])
    op.create_index('idx_tenant_customer_state', 'tenants', ['customer_id', 'state'])
    op.create_index('idx_tenant_state_updated', 'tenants', ['state', 'updated_at'])
    
    # Create audit_logs table
    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('actor_email', sa.String(length=255), nullable=True),
        sa.Column('actor_role', sa.String(length=20), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=True),
        sa.Column('resource_id', sa.String(length=100), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.Column('old_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, default={}),
        sa.Column('payload_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.ForeignKeyConstraint(['actor_id'], ['customers.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_actor_action', 'audit_logs', ['actor_id', 'action'])
    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type', 'resource_id'])
    op.create_index('idx_audit_created_at', 'audit_logs', ['created_at'])
    
    # Create subscriptions table
    op.create_table('subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('external_id', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('current_period_start', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('trial_end', sa.DateTime(), nullable=True),
        sa.Column('canceled_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=True, default='USD'),
        sa.Column('interval', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.func.now()),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'external_id', name='unique_provider_subscription')
    )
    op.create_index('idx_subscription_customer_status', 'subscriptions', ['customer_id', 'status'])
    
    # Create payment_events table
    op.create_table('payment_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('external_id', sa.String(length=100), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('raw_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'external_id', name='unique_provider_event')
    )
    op.create_index('idx_payment_event_subscription', 'payment_events', ['subscription_id'])
    op.create_index('idx_payment_event_type', 'payment_events', ['event_type'])
    
    # Create usage_records table
    op.create_table('usage_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('db_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('filestore_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('users_count', sa.Integer(), nullable=False),
        sa.Column('requests_count', sa.BigInteger(), nullable=True, default=0),
        sa.Column('storage_requests', sa.BigInteger(), nullable=True, default=0),
        sa.Column('avg_response_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True, default=0),
        sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True, default={}),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'period_start', name='unique_tenant_period')
    )
    op.create_index('idx_usage_tenant_period', 'usage_records', ['tenant_id', 'period_start'])
    op.create_index('idx_usage_recorded_at', 'usage_records', ['recorded_at'])
    
    # Create backups table
    op.create_table('backups',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False, default='full'),
        sa.Column('status', sa.String(length=20), nullable=False, default='pending'),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('s3_bucket', sa.String(length=100), nullable=True),
        sa.Column('s3_key', sa.String(length=500), nullable=True),
        sa.Column('s3_kms_key_id', sa.String(length=100), nullable=True),
        sa.Column('compression', sa.String(length=20), nullable=True, default='gzip'),
        sa.Column('checksum_sha256', sa.String(length=64), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True, default=0),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_backup_tenant_started', 'backups', ['tenant_id', 'started_at'])
    op.create_index('idx_backup_status', 'backups', ['status'])
    op.create_index('idx_backup_expires_at', 'backups', ['expires_at'])
    
    # Create support_tickets table
    op.create_table('support_tickets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subject', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=True, default='normal'),
        sa.Column('status', sa.String(length=20), nullable=True, default='open'),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('assigned_to', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ticket_customer_status', 'support_tickets', ['customer_id', 'status'])
    op.create_index('idx_ticket_priority_created', 'support_tickets', ['priority', 'created_at'])


def downgrade() -> None:
    op.drop_table('support_tickets')
    op.drop_table('backups')
    op.drop_table('usage_records')
    op.drop_table('payment_events')
    op.drop_table('subscriptions')
    op.drop_table('audit_logs')
    op.drop_table('tenants')
    op.drop_table('plans')
    op.drop_table('customers')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')