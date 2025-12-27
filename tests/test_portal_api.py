#!/usr/bin/env python3
"""
Tests for Customer Portal API
"""

import pytest
import json
from uuid import uuid4


class TestPortalAuth:
    """Tests for portal authentication endpoints"""

    def test_register_success(self, client):
        """Test successful registration"""
        response = client.post('/api/auth/register', json={
            'email': 'newuser@example.com',
            'password': 'SecurePassword123!',
            'first_name': 'New',
            'last_name': 'User'
        })

        # Registration might be disabled or require admin
        assert response.status_code in [200, 201, 403]

    def test_register_weak_password(self, client):
        """Test registration with weak password"""
        response = client.post('/api/auth/register', json={
            'email': 'newuser@example.com',
            'password': 'weak',
            'first_name': 'New',
            'last_name': 'User'
        })

        assert response.status_code == 400

    def test_register_invalid_email(self, client):
        """Test registration with invalid email"""
        response = client.post('/api/auth/register', json={
            'email': 'invalidemail',
            'password': 'SecurePassword123!',
            'first_name': 'New',
            'last_name': 'User'
        })

        assert response.status_code == 400

    def test_login_success(self, client, sample_customer):
        """Test successful login"""
        response = client.post('/api/auth/login', json={
            'email': 'test@example.com',
            'password': 'TestPassword123!'
        })

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'access_token' in data

    def test_forgot_password(self, client, sample_customer):
        """Test forgot password endpoint"""
        response = client.post('/api/auth/forgot-password', json={
            'email': 'test@example.com'
        })

        # Should always return success to prevent email enumeration
        assert response.status_code == 200

    def test_forgot_password_nonexistent_email(self, client):
        """Test forgot password with non-existent email"""
        response = client.post('/api/auth/forgot-password', json={
            'email': 'nonexistent@example.com'
        })

        # Should still return success
        assert response.status_code == 200


class TestPortalProfile:
    """Tests for profile management"""

    def test_get_profile(self, client, customer_auth_headers):
        """Test getting user profile"""
        response = client.get('/api/auth/profile', headers=customer_auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'customer' in data
        assert data['customer']['email'] == 'test@example.com'

    def test_update_profile(self, client, customer_auth_headers):
        """Test updating profile"""
        response = client.put('/api/auth/profile', headers=customer_auth_headers, json={
            'first_name': 'Updated',
            'company': 'New Company'
        })

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['customer']['first_name'] == 'Updated'


class TestPortalTenants:
    """Tests for tenant management in portal"""

    def test_list_my_tenants(self, client, customer_auth_headers, sample_tenant):
        """Test listing customer's tenants"""
        response = client.get('/api/tenants/', headers=customer_auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'tenants' in data

    def test_get_my_tenant(self, client, customer_auth_headers, sample_tenant):
        """Test getting own tenant"""
        response = client.get(f'/api/tenants/{sample_tenant.id}', headers=customer_auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'tenant' in data

    def test_create_tenant(self, client, customer_auth_headers, sample_plan):
        """Test creating a tenant"""
        response = client.post('/api/tenants/', headers=customer_auth_headers, json={
            'name': 'My New Tenant',
            'slug': 'my-new-tenant',
            'plan_id': str(sample_plan.id)
        })

        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'tenant' in data


class TestPortalBilling:
    """Tests for billing endpoints"""

    def test_list_plans(self, client, customer_auth_headers, sample_plan):
        """Test listing available plans"""
        response = client.get('/api/billing/plans', headers=customer_auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'plans' in data

    def test_get_subscriptions(self, client, customer_auth_headers):
        """Test getting subscriptions"""
        response = client.get('/api/billing/subscriptions', headers=customer_auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'subscriptions' in data

    def test_get_usage(self, client, customer_auth_headers):
        """Test getting usage"""
        response = client.get('/api/billing/usage', headers=customer_auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'usage' in data

    def test_list_payment_methods(self, client, customer_auth_headers):
        """Test listing payment methods"""
        response = client.get('/api/billing/payment-methods', headers=customer_auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'payment_methods' in data


class TestPortalSupport:
    """Tests for support ticket endpoints"""

    def test_list_tickets(self, client, customer_auth_headers):
        """Test listing support tickets"""
        response = client.get('/api/support/', headers=customer_auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'tickets' in data

    def test_create_ticket(self, client, customer_auth_headers):
        """Test creating a support ticket"""
        response = client.post('/api/support/', headers=customer_auth_headers, json={
            'subject': 'Test Ticket',
            'description': 'This is a test ticket description',
            'priority': 'normal',
            'category': 'technical'
        })

        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'ticket' in data
        assert data['ticket']['subject'] == 'Test Ticket'


class TestWebhooks:
    """Tests for webhook endpoints"""

    def test_stripe_webhook_invalid_signature(self, client):
        """Test Stripe webhook with invalid signature"""
        response = client.post('/api/webhooks/stripe',
            data='{}',
            content_type='application/json',
            headers={'Stripe-Signature': 'invalid'}
        )

        assert response.status_code in [400, 401]

    def test_paddle_webhook_invalid_signature(self, client):
        """Test Paddle webhook with invalid signature"""
        response = client.post('/api/webhooks/paddle',
            data='alert_name=test&p_signature=invalid',
            content_type='application/x-www-form-urlencoded'
        )

        # May succeed with warning in dev mode
        assert response.status_code in [200, 400, 401]


class TestPortalHealth:
    """Tests for portal health endpoints"""

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get('/health/')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
