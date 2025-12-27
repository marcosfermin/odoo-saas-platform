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
    from shared.models import Base, Customer, Tenant, Plan, AuditLog, Subscription
    from flask_sqlalchemy.query import Query

    app = create_app('testing')

    # Create tables using the shared models Base
    with app.app_context():
        Base.metadata.create_all(bind=db.engine)

        # Patch models to add Flask-SQLAlchemy query support
        for model in [Customer, Tenant, Plan, AuditLog, Subscription]:
            model.query = db.session.query_property()

        yield app
        Base.metadata.drop_all(bind=db.engine)


@pytest.fixture(scope='function')
def client(app):
    """Create test client for admin app"""
    return app.test_client()


@pytest.fixture(scope='session')
def portal_app():
    """Create portal application for testing"""
    from portal.app import create_app, db
    from shared.models import Base

    app = create_app('testing')

    # Create tables using the shared models Base
    with app.app_context():
        Base.metadata.create_all(bind=db.engine)
        yield app
        Base.metadata.drop_all(bind=db.engine)


@pytest.fixture(scope='function')
def portal_client(portal_app):
    """Create test client for portal app"""
    return portal_app.test_client()


@pytest.fixture(scope='function')
def portal_db_session(portal_app):
    """Create database session for portal testing"""
    from portal.app import db
    from shared.models import Base

    with portal_app.app_context():
        # Clear all tables before each test
        for table in reversed(Base.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()

        yield db.session

        # Rollback any uncommitted changes
        db.session.rollback()


@pytest.fixture(scope='function')
def db_session(app):
    """Create database session for testing"""
    from admin.app import db
    from shared.models import Base

    with app.app_context():
        # Clear all tables before each test
        for table in reversed(Base.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()

        yield db.session

        # Rollback any uncommitted changes
        db.session.rollback()


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
