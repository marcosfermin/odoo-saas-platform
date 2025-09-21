#!/usr/bin/env python3
"""
Admin Dashboard Web UI
Serves the admin dashboard frontend interface
"""

from flask import Blueprint, render_template, redirect, url_for, jsonify

# Create blueprint
web_bp = Blueprint('web', __name__, template_folder='../templates', static_folder='../static')

@web_bp.route('/')
def index():
    """Admin dashboard home page"""
    # For now, return a simple JSON response
    # TODO: Implement proper React/Vue frontend
    return jsonify({
        'message': 'Admin Dashboard',
        'description': 'Web UI will be implemented here',
        'api_endpoints': {
            'auth': '/api/auth',
            'tenants': '/api/tenants',
            'customers': '/api/customers',
            'plans': '/api/plans',
            'audit': '/api/audit',
            'dashboard': '/api/dashboard',
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

@web_bp.route('/dashboard')
def dashboard():
    """Main dashboard page"""
    return jsonify({
        'message': 'Dashboard Page',
        'description': 'Main admin dashboard interface'
    })

@web_bp.route('/tenants')
def tenants():
    """Tenants management page"""
    return jsonify({
        'message': 'Tenants Management',
        'description': 'Manage tenant instances'
    })

@web_bp.route('/customers')
def customers():
    """Customers management page"""
    return jsonify({
        'message': 'Customers Management',
        'description': 'Manage customer accounts'
    })

@web_bp.route('/plans')
def plans():
    """Plans management page"""
    return jsonify({
        'message': 'Plans Management', 
        'description': 'Manage billing plans'
    })

@web_bp.route('/audit')
def audit():
    """Audit logs page"""
    return jsonify({
        'message': 'Audit Logs',
        'description': 'View system audit trail'
    })