#!/usr/bin/env python3
"""
Shared database models for Odoo SaaS Platform
Multi-tenant architecture with proper isolation and security
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any
import hashlib
import json
import uuid

from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Text, JSON, 
    ForeignKey, Decimal, BigInteger, Index, UniqueConstraint,
    CheckConstraint, event
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.dialects.postgresql import UUID, JSONB
from werkzeug.security import generate_password_hash, check_password_hash

Base = declarative_base()


class TenantState(Enum):
    """Tenant lifecycle states"""
    CREATING = "creating"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETING = "deleting"
    DELETED = "deleted"
    ERROR = "error"


class CustomerRole(Enum):
    """Customer roles with hierarchical permissions"""
    OWNER = "owner"           # Full access, billing, can delete account
    ADMIN = "admin"           # Manage tenants, users, settings
    VIEWER = "viewer"         # Read-only access


class AuditAction(Enum):
    """Audit log action types"""
    CREATE = "create"
    UPDATE = "update"  
    DELETE = "delete"
    SUSPEND = "suspend"
    UNSUSPEND = "unsuspend"
    BACKUP = "backup"
    RESTORE = "restore"
    LOGIN = "login"
    LOGOUT = "logout"
    MODULE_INSTALL = "module_install"
    MODULE_UNINSTALL = "module_uninstall"
    IMPERSONATE = "impersonate"


class BillingProvider(Enum):
    """Supported billing providers"""
    STRIPE = "stripe"
    PADDLE = "paddle"


class SubscriptionStatus(Enum):
    """Subscription lifecycle states"""
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"


class Customer(Base):
    """Customer accounts with authentication and authorization"""
    __tablename__ = "customers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Profile information
    first_name = Column(String(100))
    last_name = Column(String(100))
    company = Column(String(200))
    phone = Column(String(20))
    
    # Authentication & authorization
    role = Column(String(20), nullable=False, default=CustomerRole.OWNER.value)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # 2FA (optional)
    totp_secret = Column(String(32))  # Base32 encoded secret
    backup_codes = Column(JSON)       # Array of backup codes
    
    # Resource limits
    max_tenants = Column(Integer, default=5, nullable=False)
    max_quota_gb = Column(Integer, default=50, nullable=False)
    
    # Billing integration
    stripe_customer_id = Column(String(100))
    paddle_customer_id = Column(String(100))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    email_verified_at = Column(DateTime)
    
    # Relationships
    tenants = relationship("Tenant", back_populates="customer", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="actor")
    subscriptions = relationship("Subscription", back_populates="customer")
    support_tickets = relationship("SupportTicket", back_populates="customer")
    
    def set_password(self, password: str) -> None:
        """Hash and set password securely"""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password: str) -> bool:
        """Verify password against hash"""
        return check_password_hash(self.password_hash, password)
    
    @validates('email')
    def validate_email(self, key: str, email: str) -> str:
        """Validate email format"""
        import re
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            raise ValueError("Invalid email format")
        return email.lower().strip()
    
    @validates('role')
    def validate_role(self, key: str, role: str) -> str:
        """Validate role enum"""
        if role not in [r.value for r in CustomerRole]:
            raise ValueError(f"Invalid role: {role}")
        return role
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'company': self.company,
            'role': self.role,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'max_tenants': self.max_tenants,
            'max_quota_gb': self.max_quota_gb,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class Plan(Base):
    """Billing plans with quotas and features"""
    __tablename__ = "plans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    
    # Pricing
    price_monthly = Column(Decimal(10, 2))
    price_yearly = Column(Decimal(10, 2))
    currency = Column(String(3), default='USD', nullable=False)
    
    # Quotas and limits
    max_tenants = Column(Integer, default=1, nullable=False)
    max_users_per_tenant = Column(Integer, default=10, nullable=False)
    max_db_size_gb = Column(Integer, default=5, nullable=False)
    max_filestore_gb = Column(Integer, default=2, nullable=False)
    
    # Features (JSON)
    features = Column(JSONB, default=dict)
    allowed_modules = Column(JSON)  # Array of allowed Odoo modules
    
    # Billing integration IDs
    stripe_price_id_monthly = Column(String(100))
    stripe_price_id_yearly = Column(String(100))
    paddle_plan_id = Column(String(100))
    
    # Settings
    is_active = Column(Boolean, default=True, nullable=False)
    trial_days = Column(Integer, default=14)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenants = relationship("Tenant", back_populates="plan")
    subscriptions = relationship("Subscription", back_populates="plan")


class Tenant(Base):
    """Multi-tenant Odoo instances with isolation"""
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    
    # Owner and plan
    customer_id = Column(UUID(as_uuid=True), ForeignKey('customers.id'), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey('plans.id'), nullable=False)
    
    # State management
    state = Column(String(20), default=TenantState.CREATING.value, nullable=False)
    state_message = Column(Text)  # Error messages or state details
    
    # Database configuration
    db_name = Column(String(100), nullable=False, unique=True)
    db_host = Column(String(255))  # For distributed deployments
    db_port = Column(Integer, default=5432)
    
    # Storage configuration
    filestore_path = Column(String(500))  # Local path or S3 prefix
    filestore_bucket = Column(String(100))  # S3 bucket name
    
    # Resource usage tracking
    current_users = Column(Integer, default=0, nullable=False)
    db_size_bytes = Column(BigInteger, default=0, nullable=False)
    filestore_size_bytes = Column(BigInteger, default=0, nullable=False)
    
    # Domain and SSL
    custom_domain = Column(String(255))
    ssl_cert_path = Column(String(500))
    ssl_key_path = Column(String(500))
    
    # Odoo configuration
    odoo_version = Column(String(10), default='16.0', nullable=False)
    installed_modules = Column(JSON, default=list)  # Array of module names
    odoo_config = Column(JSONB, default=dict)  # Additional Odoo config
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    suspended_at = Column(DateTime)
    last_backup_at = Column(DateTime)
    
    # Relationships
    customer = relationship("Customer", back_populates="tenants")
    plan = relationship("Plan", back_populates="tenants")
    usage_records = relationship("UsageRecord", back_populates="tenant")
    backups = relationship("Backup", back_populates="tenant")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('db_size_bytes >= 0', name='positive_db_size'),
        CheckConstraint('filestore_size_bytes >= 0', name='positive_filestore_size'),
        CheckConstraint('current_users >= 0', name='positive_users'),
        Index('idx_tenant_customer_state', 'customer_id', 'state'),
        Index('idx_tenant_state_updated', 'state', 'updated_at'),
    )
    
    @validates('slug')
    def validate_slug(self, key: str, slug: str) -> str:
        """Validate tenant slug format"""
        import re
        if not re.match(r'^[a-z0-9-]+$', slug):
            raise ValueError("Slug can only contain lowercase letters, numbers, and hyphens")
        if len(slug) < 3 or len(slug) > 50:
            raise ValueError("Slug must be between 3 and 50 characters")
        return slug
    
    @validates('state')
    def validate_state(self, key: str, state: str) -> str:
        """Validate state enum"""
        if state not in [s.value for s in TenantState]:
            raise ValueError(f"Invalid state: {state}")
        return state
    
    @property
    def is_active(self) -> bool:
        """Check if tenant is in active state"""
        return self.state == TenantState.ACTIVE.value
    
    @property
    def full_domain(self) -> str:
        """Get full domain for this tenant"""
        if self.custom_domain:
            return self.custom_domain
        return f"{self.slug}.{os.getenv('DOMAIN', 'localhost')}"
    
    def get_db_url(self) -> str:
        """Get database connection URL"""
        host = self.db_host or os.getenv('PG_HOST', 'localhost')
        port = self.db_port or int(os.getenv('PG_PORT', 5432))
        user = os.getenv('PG_USER', 'odoo')
        password = os.getenv('PG_PASSWORD', '')
        return f"postgresql://{user}:{password}@{host}:{port}/{self.db_name}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'slug': self.slug,
            'name': self.name,
            'state': self.state,
            'state_message': self.state_message,
            'db_name': self.db_name,
            'current_users': self.current_users,
            'db_size_bytes': self.db_size_bytes,
            'filestore_size_bytes': self.filestore_size_bytes,
            'custom_domain': self.custom_domain,
            'full_domain': self.full_domain,
            'odoo_version': self.odoo_version,
            'installed_modules': self.installed_modules,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'suspended_at': self.suspended_at.isoformat() if self.suspended_at else None,
            'last_backup_at': self.last_backup_at.isoformat() if self.last_backup_at else None
        }


class AuditLog(Base):
    """Immutable audit trail for all platform operations"""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Actor (who performed the action)
    actor_id = Column(UUID(as_uuid=True), ForeignKey('customers.id'))
    actor_email = Column(String(255))  # Denormalized for deleted users
    actor_role = Column(String(20))
    
    # Action details
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50))  # tenant, customer, plan, etc.
    resource_id = Column(String(100))
    
    # Context
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(String(500))
    session_id = Column(String(100))
    
    # Change details
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    metadata = Column(JSONB, default=dict)
    
    # Immutability protection
    payload_hash = Column(String(64), nullable=False)  # SHA-256 of serialized data
    
    # Timestamp (immutable)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    actor = relationship("Customer", back_populates="audit_logs")
    
    # Constraints
    __table_args__ = (
        Index('idx_audit_actor_action', 'actor_id', 'action'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_created_at', 'created_at'),
    )
    
    def __init__(self, **kwargs):
        """Initialize with payload hash for immutability"""
        super().__init__(**kwargs)
        self._calculate_payload_hash()
    
    def _calculate_payload_hash(self) -> None:
        """Calculate SHA-256 hash of audit payload"""
        payload = {
            'actor_id': str(self.actor_id) if self.actor_id else None,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'old_values': self.old_values,
            'new_values': self.new_values,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        payload_json = json.dumps(payload, sort_keys=True, default=str)
        self.payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()
    
    @validates('action')
    def validate_action(self, key: str, action: str) -> str:
        """Validate action enum"""
        if action not in [a.value for a in AuditAction]:
            raise ValueError(f"Invalid action: {action}")
        return action


class UsageRecord(Base):
    """Periodic usage snapshots for billing and monitoring"""
    __tablename__ = "usage_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=False)
    
    # Usage metrics
    db_size_bytes = Column(BigInteger, nullable=False)
    filestore_size_bytes = Column(BigInteger, nullable=False)
    users_count = Column(Integer, nullable=False)
    requests_count = Column(BigInteger, default=0)
    storage_requests = Column(BigInteger, default=0)
    
    # Performance metrics
    avg_response_time_ms = Column(Integer)
    error_count = Column(Integer, default=0)
    
    # Additional metrics (JSON)
    metrics = Column(JSONB, default=dict)
    
    # Time period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="usage_records")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'period_start', name='unique_tenant_period'),
        Index('idx_usage_tenant_period', 'tenant_id', 'period_start'),
        Index('idx_usage_recorded_at', 'recorded_at'),
    )


class Subscription(Base):
    """Customer billing subscriptions"""
    __tablename__ = "subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey('customers.id'), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey('plans.id'), nullable=False)
    
    # Billing provider integration
    provider = Column(String(20), nullable=False)  # stripe, paddle
    external_id = Column(String(100), nullable=False)  # Provider subscription ID
    
    # Subscription details
    status = Column(String(20), nullable=False)
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    trial_end = Column(DateTime)
    canceled_at = Column(DateTime)
    ended_at = Column(DateTime)
    
    # Billing
    amount = Column(Decimal(10, 2))
    currency = Column(String(3), default='USD')
    interval = Column(String(20))  # month, year
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
    payment_events = relationship("PaymentEvent", back_populates="subscription")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('provider', 'external_id', name='unique_provider_subscription'),
        Index('idx_subscription_customer_status', 'customer_id', 'status'),
    )


class PaymentEvent(Base):
    """Payment events from billing providers"""
    __tablename__ = "payment_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey('subscriptions.id'))
    
    # Provider details
    provider = Column(String(20), nullable=False)
    external_id = Column(String(100), nullable=False)
    event_type = Column(String(50), nullable=False)
    
    # Payment details
    amount = Column(Decimal(10, 2))
    currency = Column(String(3))
    status = Column(String(20))
    
    # Raw webhook data
    raw_data = Column(JSONB)
    processed_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    subscription = relationship("Subscription", back_populates="payment_events")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('provider', 'external_id', name='unique_provider_event'),
        Index('idx_payment_event_subscription', 'subscription_id'),
        Index('idx_payment_event_type', 'event_type'),
    )


class Backup(Base):
    """Backup records with S3 storage details"""
    __tablename__ = "backups"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=False)
    
    # Backup details
    type = Column(String(20), default='full', nullable=False)  # full, incremental
    status = Column(String(20), default='pending', nullable=False)
    size_bytes = Column(BigInteger)
    
    # Storage location
    s3_bucket = Column(String(100))
    s3_key = Column(String(500))
    s3_kms_key_id = Column(String(100))
    
    # Metadata
    compression = Column(String(20), default='gzip')
    checksum_sha256 = Column(String(64))
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)
    expires_at = Column(DateTime)
    
    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="backups")
    
    # Constraints
    __table_args__ = (
        Index('idx_backup_tenant_started', 'tenant_id', 'started_at'),
        Index('idx_backup_status', 'status'),
        Index('idx_backup_expires_at', 'expires_at'),
    )


class SupportTicket(Base):
    """Customer support tickets"""
    __tablename__ = "support_tickets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey('customers.id'), nullable=False)
    
    # Ticket details
    subject = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(20), default='normal')  # low, normal, high, urgent
    status = Column(String(20), default='open')      # open, in_progress, resolved, closed
    category = Column(String(50))  # billing, technical, general
    
    # Assignment
    assigned_to = Column(String(100))  # Staff member email
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime)
    
    # Relationships
    customer = relationship("Customer", back_populates="support_tickets")
    
    # Constraints
    __table_args__ = (
        Index('idx_ticket_customer_status', 'customer_id', 'status'),
        Index('idx_ticket_priority_created', 'priority', 'created_at'),
    )


# Event listeners for automatic timestamp updates
@event.listens_for(Customer, 'before_update')
@event.listens_for(Tenant, 'before_update') 
@event.listens_for(Plan, 'before_update')
@event.listens_for(Subscription, 'before_update')
@event.listens_for(SupportTicket, 'before_update')
def receive_before_update(mapper, connection, target):
    """Update timestamp on model changes"""
    target.updated_at = datetime.utcnow()


# Import os here to avoid circular imports at module level
import os