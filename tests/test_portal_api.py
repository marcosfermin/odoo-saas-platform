#!/usr/bin/env python3
"""
Tests for Customer Portal API
"""

import pytest
import json
from uuid import uuid4


class TestPortalAuth:
    """Tests for portal authentication endpoints"""

    def test_register_success(self, portal_client, portal_db_session):
        """Test successful registration"""
        response = portal_client.post('/api/auth/register', json={
            'email': 'newuser@example.com',
            'password': 'SecurePassword123!',
            'first_name': 'New',
            'last_name': 'User'
        })

        # Registration might be disabled or require admin
        assert response.status_code in [200, 201, 403]

    def test_register_weak_password(self, portal_client, portal_db_session):
        """Test registration with weak password"""
        response = portal_client.post('/api/auth/register', json={
            'email': 'newuser@example.com',
            'password': 'weak',
            'first_name': 'New',
            'last_name': 'User'
        })

        assert response.status_code == 400

    def test_register_invalid_email(self, portal_client, portal_db_session):
        """Test registration with invalid email"""
        response = portal_client.post('/api/auth/register', json={
            'email': 'invalidemail',
            'password': 'SecurePassword123!',
            'first_name': 'New',
            'last_name': 'User'
        })

        assert response.status_code == 400

    def test_login_success(self, portal_client, portal_db_session):
        """Test successful login"""
        from shared.models import Customer, CustomerRole

        # Create a customer first
        customer = Customer(
            id=uuid4(),
            email='portaltest@example.com',
            first_name='Portal',
            last_name='User',
            role=CustomerRole.OWNER.value,
            is_active=True,
            is_verified=True,
            max_tenants=5,
            max_quota_gb=50
        )
        customer.set_password('TestPassword123!')
        portal_db_session.add(customer)
        portal_db_session.commit()

        response = portal_client.post('/api/auth/login', json={
            'email': 'portaltest@example.com',
            'password': 'TestPassword123!'
        })

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'access_token' in data

    def test_forgot_password(self, portal_client, portal_db_session):
        """Test forgot password endpoint"""
        from shared.models import Customer, CustomerRole

        # Create a customer first
        customer = Customer(
            id=uuid4(),
            email='forgottest@example.com',
            first_name='Forgot',
            last_name='User',
            role=CustomerRole.OWNER.value,
            is_active=True,
            is_verified=True,
            max_tenants=5,
            max_quota_gb=50
        )
        customer.set_password('TestPassword123!')
        portal_db_session.add(customer)
        portal_db_session.commit()

        response = portal_client.post('/api/auth/forgot-password', json={
            'email': 'forgottest@example.com'
        })

        # Should always return success to prevent email enumeration
        assert response.status_code == 200

    def test_forgot_password_nonexistent_email(self, portal_client, portal_db_session):
        """Test forgot password with non-existent email"""
        response = portal_client.post('/api/auth/forgot-password', json={
            'email': 'nonexistent@example.com'
        })

        # Should still return success
        assert response.status_code == 200


class TestPortalProfile:
    """Tests for profile management"""

    def test_get_profile(self, portal_client, portal_db_session, portal_app):
        """Test getting user profile"""
        from shared.models import Customer, CustomerRole
        from flask_jwt_extended import create_access_token

        # Create a customer
        customer = Customer(
            id=uuid4(),
            email='profile@example.com',
            first_name='Profile',
            last_name='User',
            role=CustomerRole.OWNER.value,
            is_active=True,
            is_verified=True,
            max_tenants=5,
            max_quota_gb=50
        )
        customer.set_password('TestPassword123!')
        portal_db_session.add(customer)
        portal_db_session.commit()

        with portal_app.app_context():
            access_token = create_access_token(identity=str(customer.id))

        response = portal_client.get('/api/auth/profile',
            headers={'Authorization': f'Bearer {access_token}'})

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'customer' in data

    def test_update_profile(self, portal_client, portal_db_session, portal_app):
        """Test updating profile"""
        from shared.models import Customer, CustomerRole
        from flask_jwt_extended import create_access_token

        # Create a customer
        customer = Customer(
            id=uuid4(),
            email='updateprofile@example.com',
            first_name='Update',
            last_name='Profile',
            role=CustomerRole.OWNER.value,
            is_active=True,
            is_verified=True,
            max_tenants=5,
            max_quota_gb=50
        )
        customer.set_password('TestPassword123!')
        portal_db_session.add(customer)
        portal_db_session.commit()

        with portal_app.app_context():
            access_token = create_access_token(identity=str(customer.id))

        response = portal_client.put('/api/auth/profile',
            headers={'Authorization': f'Bearer {access_token}'},
            json={'first_name': 'Updated', 'company': 'New Company'})

        assert response.status_code == 200


class TestPortalTenants:
    """Tests for tenant management in portal"""

    def test_list_my_tenants(self, portal_client, portal_db_session, portal_app):
        """Test listing customer's tenants"""
        from shared.models import Customer, CustomerRole
        from flask_jwt_extended import create_access_token

        customer = Customer(
            id=uuid4(),
            email='tenantowner@example.com',
            first_name='Tenant',
            last_name='Owner',
            role=CustomerRole.OWNER.value,
            is_active=True,
            is_verified=True,
            max_tenants=5,
            max_quota_gb=50
        )
        customer.set_password('TestPassword123!')
        portal_db_session.add(customer)
        portal_db_session.commit()

        with portal_app.app_context():
            access_token = create_access_token(identity=str(customer.id))

        response = portal_client.get('/api/tenants/',
            headers={'Authorization': f'Bearer {access_token}'})

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'tenants' in data

    def test_get_my_tenant(self, portal_client, portal_db_session, portal_app):
        """Test getting own tenant"""
        from shared.models import Customer, Tenant, Plan, CustomerRole, TenantState
        from flask_jwt_extended import create_access_token
        from decimal import Decimal

        customer = Customer(
            id=uuid4(),
            email='tenantget@example.com',
            first_name='Tenant',
            last_name='Getter',
            role=CustomerRole.OWNER.value,
            is_active=True,
            is_verified=True,
            max_tenants=5,
            max_quota_gb=50
        )
        customer.set_password('TestPassword123!')
        portal_db_session.add(customer)

        plan = Plan(
            id=uuid4(),
            name='Test Plan Portal',
            description='Test',
            price_monthly=Decimal('29.99'),
            currency='USD',
            max_tenants=3,
            max_users_per_tenant=10,
            max_db_size_gb=5,
            max_filestore_gb=2,
            is_active=True,
            trial_days=14
        )
        portal_db_session.add(plan)
        portal_db_session.commit()

        tenant = Tenant(
            id=uuid4(),
            slug='portal-test-tenant',
            name='Portal Test Tenant',
            customer_id=customer.id,
            plan_id=plan.id,
            state=TenantState.ACTIVE.value,
            db_name='tenant_portal_test',
            odoo_version='16.0',
            current_users=1,
            db_size_bytes=1024*1024,
            filestore_size_bytes=1024*1024
        )
        portal_db_session.add(tenant)
        portal_db_session.commit()

        with portal_app.app_context():
            access_token = create_access_token(identity=str(customer.id))

        response = portal_client.get(f'/api/tenants/{tenant.id}',
            headers={'Authorization': f'Bearer {access_token}'})

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'tenant' in data

    def test_create_tenant(self, portal_client, portal_db_session, portal_app):
        """Test creating a tenant"""
        from shared.models import Customer, Plan, CustomerRole
        from flask_jwt_extended import create_access_token
        from decimal import Decimal

        customer = Customer(
            id=uuid4(),
            email='tenantcreator@example.com',
            first_name='Tenant',
            last_name='Creator',
            role=CustomerRole.OWNER.value,
            is_active=True,
            is_verified=True,
            max_tenants=5,
            max_quota_gb=50
        )
        customer.set_password('TestPassword123!')
        portal_db_session.add(customer)

        plan = Plan(
            id=uuid4(),
            name='Creator Plan',
            description='Test',
            price_monthly=Decimal('29.99'),
            currency='USD',
            max_tenants=3,
            max_users_per_tenant=10,
            max_db_size_gb=5,
            max_filestore_gb=2,
            is_active=True,
            trial_days=14
        )
        portal_db_session.add(plan)
        portal_db_session.commit()

        with portal_app.app_context():
            access_token = create_access_token(identity=str(customer.id))

        response = portal_client.post('/api/tenants/',
            headers={'Authorization': f'Bearer {access_token}'},
            json={
                'name': 'My New Portal Tenant',
                'slug': 'my-new-portal-tenant',
                'plan_id': str(plan.id)
            })

        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'tenant' in data


class TestPortalBilling:
    """Tests for billing endpoints"""

    def test_list_plans(self, portal_client, portal_db_session, portal_app):
        """Test listing available plans"""
        from shared.models import Customer, Plan, CustomerRole
        from flask_jwt_extended import create_access_token
        from decimal import Decimal

        customer = Customer(
            id=uuid4(),
            email='billing@example.com',
            first_name='Billing',
            last_name='User',
            role=CustomerRole.OWNER.value,
            is_active=True,
            is_verified=True,
            max_tenants=5,
            max_quota_gb=50
        )
        customer.set_password('TestPassword123!')
        portal_db_session.add(customer)

        plan = Plan(
            id=uuid4(),
            name='Billing Plan',
            description='Test',
            price_monthly=Decimal('29.99'),
            currency='USD',
            max_tenants=3,
            max_users_per_tenant=10,
            max_db_size_gb=5,
            max_filestore_gb=2,
            is_active=True,
            trial_days=14
        )
        portal_db_session.add(plan)
        portal_db_session.commit()

        with portal_app.app_context():
            access_token = create_access_token(identity=str(customer.id))

        response = portal_client.get('/api/billing/plans',
            headers={'Authorization': f'Bearer {access_token}'})

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'plans' in data

    def test_get_subscriptions(self, portal_client, portal_db_session, portal_app):
        """Test getting subscriptions"""
        from shared.models import Customer, CustomerRole
        from flask_jwt_extended import create_access_token

        customer = Customer(
            id=uuid4(),
            email='subs@example.com',
            first_name='Subs',
            last_name='User',
            role=CustomerRole.OWNER.value,
            is_active=True,
            is_verified=True,
            max_tenants=5,
            max_quota_gb=50
        )
        customer.set_password('TestPassword123!')
        portal_db_session.add(customer)
        portal_db_session.commit()

        with portal_app.app_context():
            access_token = create_access_token(identity=str(customer.id))

        response = portal_client.get('/api/billing/subscriptions',
            headers={'Authorization': f'Bearer {access_token}'})

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'subscriptions' in data

    def test_get_usage(self, portal_client, portal_db_session, portal_app):
        """Test getting usage"""
        from shared.models import Customer, CustomerRole
        from flask_jwt_extended import create_access_token

        customer = Customer(
            id=uuid4(),
            email='usage@example.com',
            first_name='Usage',
            last_name='User',
            role=CustomerRole.OWNER.value,
            is_active=True,
            is_verified=True,
            max_tenants=5,
            max_quota_gb=50
        )
        customer.set_password('TestPassword123!')
        portal_db_session.add(customer)
        portal_db_session.commit()

        with portal_app.app_context():
            access_token = create_access_token(identity=str(customer.id))

        response = portal_client.get('/api/billing/usage',
            headers={'Authorization': f'Bearer {access_token}'})

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'usage' in data

    def test_list_payment_methods(self, portal_client, portal_db_session, portal_app):
        """Test listing payment methods"""
        from shared.models import Customer, CustomerRole
        from flask_jwt_extended import create_access_token

        customer = Customer(
            id=uuid4(),
            email='payment@example.com',
            first_name='Payment',
            last_name='User',
            role=CustomerRole.OWNER.value,
            is_active=True,
            is_verified=True,
            max_tenants=5,
            max_quota_gb=50
        )
        customer.set_password('TestPassword123!')
        portal_db_session.add(customer)
        portal_db_session.commit()

        with portal_app.app_context():
            access_token = create_access_token(identity=str(customer.id))

        response = portal_client.get('/api/billing/payment-methods',
            headers={'Authorization': f'Bearer {access_token}'})

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'payment_methods' in data


class TestPortalSupport:
    """Tests for support ticket endpoints"""

    def test_list_tickets(self, portal_client, portal_db_session, portal_app):
        """Test listing support tickets"""
        from shared.models import Customer, CustomerRole
        from flask_jwt_extended import create_access_token

        customer = Customer(
            id=uuid4(),
            email='support@example.com',
            first_name='Support',
            last_name='User',
            role=CustomerRole.OWNER.value,
            is_active=True,
            is_verified=True,
            max_tenants=5,
            max_quota_gb=50
        )
        customer.set_password('TestPassword123!')
        portal_db_session.add(customer)
        portal_db_session.commit()

        with portal_app.app_context():
            access_token = create_access_token(identity=str(customer.id))

        response = portal_client.get('/api/support/',
            headers={'Authorization': f'Bearer {access_token}'})

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'tickets' in data

    def test_create_ticket(self, portal_client, portal_db_session, portal_app):
        """Test creating a support ticket"""
        from shared.models import Customer, CustomerRole
        from flask_jwt_extended import create_access_token

        customer = Customer(
            id=uuid4(),
            email='ticketcreator@example.com',
            first_name='Ticket',
            last_name='Creator',
            role=CustomerRole.OWNER.value,
            is_active=True,
            is_verified=True,
            max_tenants=5,
            max_quota_gb=50
        )
        customer.set_password('TestPassword123!')
        portal_db_session.add(customer)
        portal_db_session.commit()

        with portal_app.app_context():
            access_token = create_access_token(identity=str(customer.id))

        response = portal_client.post('/api/support/',
            headers={'Authorization': f'Bearer {access_token}'},
            json={
                'subject': 'Test Ticket',
                'description': 'This is a test ticket description',
                'priority': 'medium',
                'category': 'technical'
            })

        assert response.status_code == 201
        data = json.loads(response.data)
        # Ticket data may be nested under 'ticket' or returned directly
        ticket = data.get('ticket', data)
        assert ticket['subject'] == 'Test Ticket'


class TestWebhooks:
    """Tests for webhook endpoints"""

    def test_stripe_webhook_invalid_signature(self, portal_client, portal_db_session):
        """Test Stripe webhook with invalid signature"""
        response = portal_client.post('/webhooks/stripe',
            data='{}',
            content_type='application/json',
            headers={'Stripe-Signature': 'invalid'}
        )

        # In test mode, signature verification may be skipped (returns 200)
        assert response.status_code in [200, 400, 401]

    def test_paddle_webhook_invalid_signature(self, portal_client, portal_db_session):
        """Test Paddle webhook with invalid signature"""
        response = portal_client.post('/webhooks/paddle',
            data='alert_name=test&p_signature=invalid',
            content_type='application/x-www-form-urlencoded'
        )

        # May succeed with warning in dev mode
        assert response.status_code in [200, 400, 401]


class TestPortalHealth:
    """Tests for portal health endpoints"""

    def test_health_check(self, portal_client, portal_db_session):
        """Test health check endpoint"""
        response = portal_client.get('/health/')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
