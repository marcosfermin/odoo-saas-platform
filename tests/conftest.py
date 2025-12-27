#!/usr/bin/env python3
"""
Pytest configuration and fixtures for Odoo SaaS Platform tests
"""

import os
import sys
import pytest
from datetime import datetime
from uuid import uuid4

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment
os.environ['FLASK_ENV'] = 'testing'
os.environ['TESTING'] = 'true'
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing'


@pytest.fixture(scope='session')
def app():
    """Create application for testing"""
    from admin.app import create_app, db

    app = create_app('testing')

    # Create tables
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture(scope='function')
def db_session(app):
    """Create database session for testing"""
    from admin.app import db

    with app.app_context():
        # Start a transaction
        connection = db.engine.connect()
        transaction = connection.begin()

        # Bind session to connection
        options = dict(bind=connection, binds={})
        session = db.create_scoped_session(options=options)
        db.session = session

        yield session

        # Rollback transaction
        transaction.rollback()
        connection.close()
        session.remove()


@pytest.fixture
def sample_customer(db_session):
    """Create a sample customer for testing"""
    from shared.models import Customer, CustomerRole

    customer = Customer(
        id=uuid4(),
        email='test@example.com',
        first_name='Test',
        last_name='User',
        role=CustomerRole.OWNER.value,
        is_active=True,
        is_verified=True,
        max_tenants=5,
        max_quota_gb=50
    )
    customer.set_password('TestPassword123!')

    db_session.add(customer)
    db_session.commit()

    return customer


@pytest.fixture
def admin_customer(db_session):
    """Create an admin customer for testing"""
    from shared.models import Customer, CustomerRole

    customer = Customer(
        id=uuid4(),
        email='admin@example.com',
        first_name='Admin',
        last_name='User',
        role=CustomerRole.ADMIN.value,
        is_active=True,
        is_verified=True,
        max_tenants=999,
        max_quota_gb=999
    )
    customer.set_password('AdminPassword123!')

    db_session.add(customer)
    db_session.commit()

    return customer


@pytest.fixture
def sample_plan(db_session):
    """Create a sample plan for testing"""
    from shared.models import Plan
    from decimal import Decimal

    plan = Plan(
        id=uuid4(),
        name='Test Plan',
        description='A test plan',
        price_monthly=Decimal('29.99'),
        price_yearly=Decimal('299.99'),
        currency='USD',
        max_tenants=3,
        max_users_per_tenant=10,
        max_db_size_gb=5,
        max_filestore_gb=2,
        features={'feature1': True, 'feature2': True},
        is_active=True,
        trial_days=14
    )

    db_session.add(plan)
    db_session.commit()

    return plan


@pytest.fixture
def sample_tenant(db_session, sample_customer, sample_plan):
    """Create a sample tenant for testing"""
    from shared.models import Tenant, TenantState

    tenant = Tenant(
        id=uuid4(),
        slug='test-tenant',
        name='Test Tenant',
        customer_id=sample_customer.id,
        plan_id=sample_plan.id,
        state=TenantState.ACTIVE.value,
        db_name='tenant_test_tenant',
        filestore_path='/var/lib/odoo/filestore/test-tenant',
        odoo_version='16.0',
        current_users=5,
        db_size_bytes=1024 * 1024 * 100,  # 100 MB
        filestore_size_bytes=1024 * 1024 * 50  # 50 MB
    )

    db_session.add(tenant)
    db_session.commit()

    return tenant


@pytest.fixture
def auth_headers(app, admin_customer):
    """Get authentication headers for admin user"""
    from flask_jwt_extended import create_access_token

    with app.app_context():
        access_token = create_access_token(identity=admin_customer)
        return {'Authorization': f'Bearer {access_token}'}


@pytest.fixture
def customer_auth_headers(app, sample_customer):
    """Get authentication headers for regular customer"""
    from flask_jwt_extended import create_access_token

    with app.app_context():
        access_token = create_access_token(identity=sample_customer)
        return {'Authorization': f'Bearer {access_token}'}
