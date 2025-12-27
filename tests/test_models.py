#!/usr/bin/env python3
"""
Tests for database models
"""

import pytest
from datetime import datetime
from uuid import uuid4


class TestCustomerModel:
    """Tests for Customer model"""

    def test_create_customer(self, db_session):
        """Test creating a customer"""
        from shared.models import Customer, CustomerRole

        customer = Customer(
            email='model_test@example.com',
            first_name='Model',
            last_name='Test',
            role=CustomerRole.OWNER.value,
            is_active=True
        )
        customer.set_password('TestPassword123!')

        db_session.add(customer)
        db_session.commit()

        assert customer.id is not None
        assert customer.email == 'model_test@example.com'
        assert customer.check_password('TestPassword123!')
        assert not customer.check_password('wrongpassword')

    def test_email_validation(self, db_session):
        """Test email validation"""
        from shared.models import Customer

        with pytest.raises(ValueError):
            customer = Customer(
                email='invalid-email',
                first_name='Test',
                last_name='User'
            )

    def test_role_validation(self, db_session):
        """Test role validation"""
        from shared.models import Customer

        with pytest.raises(ValueError):
            customer = Customer(
                email='test@example.com',
                first_name='Test',
                last_name='User',
                role='invalid_role'
            )

    def test_customer_to_dict(self, sample_customer):
        """Test customer to_dict method"""
        data = sample_customer.to_dict()

        assert 'id' in data
        assert 'email' in data
        assert data['email'] == 'test@example.com'
        assert 'password_hash' not in data  # Should not expose password


class TestTenantModel:
    """Tests for Tenant model"""

    def test_create_tenant(self, db_session, sample_customer, sample_plan):
        """Test creating a tenant"""
        from shared.models import Tenant, TenantState

        tenant = Tenant(
            slug='model-test-tenant',
            name='Model Test Tenant',
            customer_id=sample_customer.id,
            plan_id=sample_plan.id,
            state=TenantState.CREATING.value,
            db_name='tenant_model_test',
            odoo_version='16.0'
        )

        db_session.add(tenant)
        db_session.commit()

        assert tenant.id is not None
        assert tenant.slug == 'model-test-tenant'
        assert tenant.state == TenantState.CREATING.value

    def test_slug_validation(self, db_session, sample_customer, sample_plan):
        """Test slug validation"""
        from shared.models import Tenant

        with pytest.raises(ValueError):
            tenant = Tenant(
                slug='INVALID SLUG!',  # Invalid characters
                name='Test',
                customer_id=sample_customer.id,
                plan_id=sample_plan.id,
                db_name='test_db'
            )

    def test_state_validation(self, db_session, sample_customer, sample_plan):
        """Test state validation"""
        from shared.models import Tenant

        with pytest.raises(ValueError):
            tenant = Tenant(
                slug='valid-slug',
                name='Test',
                customer_id=sample_customer.id,
                plan_id=sample_plan.id,
                db_name='test_db',
                state='invalid_state'
            )

    def test_tenant_is_active(self, sample_tenant):
        """Test is_active property"""
        assert sample_tenant.is_active is True

    def test_tenant_to_dict(self, sample_tenant):
        """Test tenant to_dict method"""
        data = sample_tenant.to_dict()

        assert 'id' in data
        assert 'slug' in data
        assert 'state' in data
        assert data['slug'] == 'test-tenant'


class TestPlanModel:
    """Tests for Plan model"""

    def test_create_plan(self, db_session):
        """Test creating a plan"""
        from shared.models import Plan
        from decimal import Decimal

        plan = Plan(
            name='Model Test Plan',
            description='A test plan',
            price_monthly=Decimal('49.99'),
            price_yearly=Decimal('499.99'),
            max_tenants=5,
            max_users_per_tenant=25,
            is_active=True
        )

        db_session.add(plan)
        db_session.commit()

        assert plan.id is not None
        assert plan.name == 'Model Test Plan'
        assert plan.price_monthly == Decimal('49.99')


class TestAuditLogModel:
    """Tests for AuditLog model"""

    def test_create_audit_log(self, db_session, sample_customer):
        """Test creating an audit log"""
        from shared.models import AuditLog, AuditAction

        audit = AuditLog(
            actor_id=sample_customer.id,
            actor_email=sample_customer.email,
            actor_role=sample_customer.role,
            action=AuditAction.CREATE.value,
            resource_type='tenant',
            resource_id='test-id',
            ip_address='127.0.0.1'
        )

        db_session.add(audit)
        db_session.commit()

        assert audit.id is not None
        assert audit.payload_hash is not None  # Hash should be calculated

    def test_audit_log_immutability(self, db_session, sample_customer):
        """Test that audit log hash is calculated"""
        from shared.models import AuditLog, AuditAction

        audit = AuditLog(
            actor_id=sample_customer.id,
            action=AuditAction.UPDATE.value,
            resource_type='customer',
            resource_id=str(sample_customer.id),
            old_values={'name': 'old'},
            new_values={'name': 'new'}
        )

        db_session.add(audit)
        db_session.commit()

        # Hash should be set
        assert audit.payload_hash is not None
        assert len(audit.payload_hash) == 64  # SHA-256 hex length


class TestSubscriptionModel:
    """Tests for Subscription model"""

    def test_create_subscription(self, db_session, sample_customer, sample_plan):
        """Test creating a subscription"""
        from shared.models import Subscription
        from decimal import Decimal

        subscription = Subscription(
            customer_id=sample_customer.id,
            plan_id=sample_plan.id,
            provider='stripe',
            external_id='sub_test123',
            status='active',
            amount=Decimal('29.99'),
            currency='usd',
            interval='month'
        )

        db_session.add(subscription)
        db_session.commit()

        assert subscription.id is not None
        assert subscription.status == 'active'


class TestSupportTicketModel:
    """Tests for SupportTicket model"""

    def test_create_ticket(self, db_session, sample_customer):
        """Test creating a support ticket"""
        from shared.models import SupportTicket

        ticket = SupportTicket(
            customer_id=sample_customer.id,
            subject='Test Ticket',
            description='This is a test ticket',
            priority='normal',
            status='open',
            category='technical'
        )

        db_session.add(ticket)
        db_session.commit()

        assert ticket.id is not None
        assert ticket.status == 'open'
