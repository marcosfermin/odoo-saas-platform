#!/usr/bin/env python3
"""
Customer Portal Web UI
Serves the customer portal frontend interface
"""

from flask import Blueprint, jsonify

# Create blueprint
web_bp = Blueprint('web', __name__, template_folder='../templates', static_folder='../static')

@web_bp.route('/')
def index():
    """Customer portal home page"""
    return jsonify({
        'message': 'Customer Portal',
        'description': 'Self-service portal for customers',
        'api_endpoints': {
            'auth': '/api/auth',
            'tenants': '/api/tenants',
            'billing': '/api/billing',
            'support': '/api/support',
            'health': '/health'
        }
    })

@web_bp.route('/login')
def login_page():
    """Login page"""
    return jsonify({
        'message': 'Login Page',
        'description': 'Use POST /api/auth/login to authenticate'
    })

@web_bp.route('/register')
def register_page():
    """Registration page"""
    return jsonify({
        'message': 'Registration Page',
        'description': 'Use POST /api/auth/register to create account'
    })

@web_bp.route('/dashboard')
def dashboard():
    """Customer dashboard page"""
    return jsonify({
        'message': 'Customer Dashboard',
        'description': 'Main customer dashboard interface'
    })

@web_bp.route('/tenants')
def tenants():
    """My tenants page"""
    return jsonify({
        'message': 'My Tenants',
        'description': 'Manage your Odoo instances'
    })

@web_bp.route('/billing')
def billing():
    """Billing page"""
    return jsonify({
        'message': 'Billing',
        'description': 'Manage subscriptions and payments'
    })

@web_bp.route('/support')
def support():
    """Support page"""
    return jsonify({
        'message': 'Support',
        'description': 'Create and manage support tickets'
    })
