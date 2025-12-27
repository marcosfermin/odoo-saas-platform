#!/usr/bin/env python3
"""
Admin Dashboard API Package
Exports all API blueprints for Flask application registration
"""

from .auth import auth_bp
from .health import health_bp
from .tenants import tenants_bp
from .customers import customers_bp
from .plans import plans_bp
from .audit import audit_bp
from .dashboard import dashboard_bp

__all__ = [
    'auth_bp',
    'health_bp',
    'tenants_bp',
    'customers_bp',
    'plans_bp',
    'audit_bp',
    'dashboard_bp'
]
