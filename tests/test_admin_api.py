#!/usr/bin/env python3
"""
Tests for Admin Dashboard API
"""

import pytest
import json
from uuid import uuid4


class TestAdminAuth:
    """Tests for admin authentication endpoints"""

    def test_login_success(self, client, admin_customer):
        """Test successful login"""
        response = client.post('/api/auth/login', json={
            'email': 'admin@example.com',
            'password': 'AdminPassword123!'
        })

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'access_token' in data
        assert 'refresh_token' in data
        assert data['user']['email'] == 'admin@example.com'

    def test_login_invalid_credentials(self, client, admin_customer):
        """Test login with invalid credentials"""
        response = client.post('/api/auth/login', json={
            'email': 'admin@example.com',
            'password': 'wrongpassword'
        })

        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data

    def test_login_missing_fields(self, client):
        """Test login with missing fields"""
        response = client.post('/api/auth/login', json={
            'email': 'admin@example.com'
        })

        assert response.status_code == 400

    def test_logout(self, client, auth_headers):
        """Test logout"""
        response = client.post('/api/auth/logout', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['message'] == 'Logout successful'


class TestTenantsAPI:
    """Tests for tenants management API"""

    def test_list_tenants(self, client, auth_headers, sample_tenant):
        """Test listing tenants"""
        response = client.get('/api/tenants/', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'tenants' in data
        assert 'pagination' in data
        assert len(data['tenants']) >= 1

    def test_list_tenants_with_filters(self, client, auth_headers, sample_tenant):
        """Test listing tenants with filters"""
        response = client.get('/api/tenants/?state=active&search=test', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'tenants' in data

    def test_get_tenant(self, client, auth_headers, sample_tenant):
        """Test getting a single tenant"""
        response = client.get(f'/api/tenants/{sample_tenant.id}', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'tenant' in data
        assert data['tenant']['slug'] == 'test-tenant'

    def test_get_tenant_not_found(self, client, auth_headers):
        """Test getting non-existent tenant"""
        response = client.get(f'/api/tenants/{uuid4()}', headers=auth_headers)

        assert response.status_code == 404

    def test_create_tenant(self, client, auth_headers, sample_customer, sample_plan):
        """Test creating a tenant"""
        response = client.post('/api/tenants/', headers=auth_headers, json={
            'name': 'New Tenant',
            'slug': 'new-tenant',
            'customer_id': str(sample_customer.id),
            'plan_id': str(sample_plan.id)
        })

        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'tenant' in data
        assert data['tenant']['slug'] == 'new-tenant'

    def test_create_tenant_duplicate_slug(self, client, auth_headers, sample_customer, sample_plan, sample_tenant):
        """Test creating a tenant with duplicate slug"""
        response = client.post('/api/tenants/', headers=auth_headers, json={
            'name': 'Another Tenant',
            'slug': 'test-tenant',  # Already exists
            'customer_id': str(sample_customer.id),
            'plan_id': str(sample_plan.id)
        })

        assert response.status_code == 409

    def test_update_tenant(self, client, auth_headers, sample_tenant):
        """Test updating a tenant"""
        response = client.put(f'/api/tenants/{sample_tenant.id}', headers=auth_headers, json={
            'name': 'Updated Tenant Name'
        })

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['tenant']['name'] == 'Updated Tenant Name'

    def test_suspend_tenant(self, client, auth_headers, sample_tenant):
        """Test suspending a tenant"""
        response = client.post(f'/api/tenants/{sample_tenant.id}/suspend', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['tenant']['state'] == 'suspended'

    def test_delete_tenant(self, client, auth_headers, sample_tenant):
        """Test deleting a tenant"""
        response = client.delete(f'/api/tenants/{sample_tenant.id}', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'message' in data


class TestCustomersAPI:
    """Tests for customers management API"""

    def test_list_customers(self, client, auth_headers, sample_customer):
        """Test listing customers"""
        response = client.get('/api/customers/', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'customers' in data
        assert 'pagination' in data

    def test_get_customer(self, client, auth_headers, sample_customer):
        """Test getting a single customer"""
        response = client.get(f'/api/customers/{sample_customer.id}', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'customer' in data
        assert data['customer']['email'] == 'test@example.com'

    def test_create_customer(self, client, auth_headers):
        """Test creating a customer"""
        response = client.post('/api/customers/', headers=auth_headers, json={
            'email': 'newcustomer@example.com',
            'password': 'NewPassword123!',
            'first_name': 'New',
            'last_name': 'Customer'
        })

        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'customer' in data
        assert data['customer']['email'] == 'newcustomer@example.com'

    def test_create_customer_duplicate_email(self, client, auth_headers, sample_customer):
        """Test creating a customer with duplicate email"""
        response = client.post('/api/customers/', headers=auth_headers, json={
            'email': 'test@example.com',
            'password': 'Password123!',
            'first_name': 'Duplicate',
            'last_name': 'User'
        })

        assert response.status_code == 409

    def test_update_customer(self, client, auth_headers, sample_customer):
        """Test updating a customer"""
        response = client.put(f'/api/customers/{sample_customer.id}', headers=auth_headers, json={
            'first_name': 'Updated',
            'company': 'Test Company'
        })

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['customer']['first_name'] == 'Updated'


class TestPlansAPI:
    """Tests for plans management API"""

    def test_list_plans(self, client, auth_headers, sample_plan):
        """Test listing plans"""
        response = client.get('/api/plans/', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'plans' in data
        assert len(data['plans']) >= 1

    def test_get_plan(self, client, auth_headers, sample_plan):
        """Test getting a single plan"""
        response = client.get(f'/api/plans/{sample_plan.id}', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'plan' in data
        assert data['plan']['name'] == 'Test Plan'

    def test_create_plan(self, client, auth_headers):
        """Test creating a plan"""
        response = client.post('/api/plans/', headers=auth_headers, json={
            'name': 'Premium Plan',
            'description': 'A premium plan',
            'price_monthly': '99.99',
            'max_tenants': 10,
            'max_users_per_tenant': 50
        })

        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'plan' in data
        assert data['plan']['name'] == 'Premium Plan'

    def test_update_plan(self, client, auth_headers, sample_plan):
        """Test updating a plan"""
        response = client.put(f'/api/plans/{sample_plan.id}', headers=auth_headers, json={
            'description': 'Updated description',
            'price_monthly': '39.99'
        })

        assert response.status_code == 200

    def test_deactivate_plan(self, client, auth_headers, sample_plan):
        """Test deactivating a plan"""
        response = client.post(f'/api/plans/{sample_plan.id}/deactivate', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['plan']['is_active'] is False


class TestAuditAPI:
    """Tests for audit log API"""

    def test_list_audit_logs(self, client, auth_headers):
        """Test listing audit logs"""
        response = client.get('/api/audit/', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'audit_logs' in data
        assert 'pagination' in data

    def test_get_audit_stats(self, client, auth_headers):
        """Test getting audit statistics"""
        response = client.get('/api/audit/stats', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'statistics' in data

    def test_list_actions(self, client, auth_headers):
        """Test listing available actions"""
        response = client.get('/api/audit/actions', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'actions' in data


class TestDashboardAPI:
    """Tests for dashboard API"""

    def test_get_dashboard_stats(self, client, auth_headers):
        """Test getting dashboard statistics"""
        response = client.get('/api/dashboard/stats', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'statistics' in data
        assert 'customers' in data['statistics']
        assert 'tenants' in data['statistics']

    def test_get_tenant_chart_data(self, client, auth_headers):
        """Test getting tenant chart data"""
        response = client.get('/api/dashboard/charts/tenants', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'chart_data' in data

    def test_get_recent_activity(self, client, auth_headers):
        """Test getting recent activity"""
        response = client.get('/api/dashboard/recent-activity', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'activities' in data

    def test_get_system_alerts(self, client, auth_headers):
        """Test getting system alerts"""
        response = client.get('/api/dashboard/alerts', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'alerts' in data

    def test_get_health_summary(self, client, auth_headers):
        """Test getting health summary"""
        response = client.get('/api/dashboard/health-summary', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'overall_status' in data
        assert 'components' in data


class TestHealthEndpoints:
    """Tests for health check endpoints"""

    def test_health_check(self, client):
        """Test main health check"""
        response = client.get('/health/')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'

    def test_readiness_check(self, client):
        """Test readiness check"""
        response = client.get('/health/ready')

        assert response.status_code in [200, 503]


class TestUnauthorizedAccess:
    """Tests for unauthorized access"""

    def test_tenants_without_auth(self, client):
        """Test accessing tenants without authentication"""
        response = client.get('/api/tenants/')

        assert response.status_code == 401

    def test_customers_without_auth(self, client):
        """Test accessing customers without authentication"""
        response = client.get('/api/customers/')

        assert response.status_code == 401

    def test_plans_without_auth(self, client):
        """Test accessing plans without authentication"""
        response = client.get('/api/plans/')

        assert response.status_code == 401
