"""
Customer Portal Web UI Package
Provides web interface routes
"""

from flask import Blueprint, render_template, redirect, url_for

# Create web blueprint
web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    """Homepage"""
    return redirect(url_for('web.dashboard'))


@web_bp.route('/dashboard')
def dashboard():
    """Customer dashboard"""
    # For now, return a simple JSON response
    # TODO: Implement proper HTML template rendering
    return {
        'message': 'Customer Portal Dashboard',
        'status': 'active',
        'endpoints': {
            'api_auth': '/api/auth',
            'api_tenants': '/api/tenants',
            'api_billing': '/api/billing',
            'api_support': '/api/support',
            'webhooks': '/webhooks',
            'health': '/health'
        }
    }


@web_bp.route('/login')
def login():
    """Login page"""
    # TODO: Implement proper login UI
    return {
        'message': 'Login page',
        'redirect_to': '/api/auth/login'
    }


@web_bp.route('/signup')
def signup():
    """Signup page"""
    # TODO: Implement proper signup UI
    return {
        'message': 'Signup page',
        'redirect_to': '/api/auth/signup'
    }


__all__ = ['web_bp']
