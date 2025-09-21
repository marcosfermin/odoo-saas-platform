#!/usr/bin/env python3
"""
Customer Portal Authentication API
Handles customer registration, login, and account management
"""

import os
import sys
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_current_user
)
from marshmallow import Schema, fields, validate, ValidationError

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.models import Customer, CustomerRole, AuditAction
from portal.app import db, limiter

# Create blueprint
auth_bp = Blueprint('auth', __name__)

# Validation schemas
class RegisterSchema(Schema):
    email = fields.Email(required=True, validate=validate.Length(max=255))
    password = fields.Str(required=True, validate=validate.Length(min=8))
    first_name = fields.Str(required=True, validate=validate.Length(max=100))
    last_name = fields.Str(required=True, validate=validate.Length(max=100))
    company = fields.Str(validate=validate.Length(max=200))
    phone = fields.Str(validate=validate.Length(max=20))

class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)
    remember_me = fields.Bool(missing=False)

class UpdateProfileSchema(Schema):
    first_name = fields.Str(validate=validate.Length(max=100))
    last_name = fields.Str(validate=validate.Length(max=100))
    company = fields.Str(validate=validate.Length(max=200))
    phone = fields.Str(validate=validate.Length(max=20))

def rate_limit_key():
    """Generate rate limiting key based on IP"""
    return f"ip:{request.remote_addr}"

@auth_bp.route('/register', methods=['POST'])
@limiter.limit("5 per minute", key_func=rate_limit_key)
def register():
    """Customer registration"""
    try:
        schema = RegisterSchema()
        data = schema.load(request.get_json() or {})
    except ValidationError as err:
        return jsonify({
            'error': 'Validation Error',
            'message': 'Invalid request data',
            'details': err.messages
        }), 400

    # Check if customer already exists
    existing_customer = Customer.query.filter_by(email=data['email'].lower()).first()
    if existing_customer:
        return jsonify({
            'error': 'Customer Exists',
            'message': 'An account with this email already exists'
        }), 409

    # Validate password strength
    from admin.app.utils.auth import AuthenticationService
    is_valid, password_errors = AuthenticationService.validate_password_strength(data['password'])
    if not is_valid:
        return jsonify({
            'error': 'Weak Password',
            'message': 'Password does not meet security requirements',
            'details': password_errors
        }), 400

    # Check for compromised password
    if AuthenticationService.is_password_compromised(data['password']):
        return jsonify({
            'error': 'Compromised Password',
            'message': 'This password appears in known data breaches. Please choose a different password.'
        }), 400

    # Create new customer
    new_customer = Customer(
        email=data['email'].lower(),
        first_name=data['first_name'],
        last_name=data['last_name'],
        company=data.get('company'),
        phone=data.get('phone'),
        role=CustomerRole.OWNER.value,  # Portal customers are owners
        is_active=True,
        is_verified=False,  # Email verification required
        max_tenants=1,      # Default limit
        max_quota_gb=10
    )
    new_customer.set_password(data['password'])

    db.session.add(new_customer)
    db.session.commit()

    current_app.logger.info(f"New customer registered: {new_customer.email}")

    return jsonify({
        'message': 'Registration successful',
        'customer': {
            'id': str(new_customer.id),
            'email': new_customer.email,
            'first_name': new_customer.first_name,
            'last_name': new_customer.last_name,
            'is_verified': new_customer.is_verified
        }
    }), 201

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute", key_func=rate_limit_key)
def login():
    """Customer login"""
    try:
        schema = LoginSchema()
        data = schema.load(request.get_json() or {})
    except ValidationError as err:
        return jsonify({
            'error': 'Validation Error',
            'message': 'Invalid request data',
            'details': err.messages
        }), 400

    # Find customer by email
    customer = Customer.query.filter_by(email=data['email'].lower()).first()

    if not customer or not customer.check_password(data['password']):
        current_app.logger.warning(f"Failed login attempt: {data['email']}")
        return jsonify({
            'error': 'Authentication Failed',
            'message': 'Invalid email or password'
        }), 401

    if not customer.is_active:
        current_app.logger.warning(f"Login attempt by disabled customer: {customer.email}")
        return jsonify({
            'error': 'Account Disabled',
            'message': 'Your account has been disabled. Please contact support.'
        }), 403

    # Create tokens
    access_token = create_access_token(identity=customer)
    refresh_token = create_refresh_token(identity=customer)

    # Update last login
    customer.last_login = datetime.utcnow()
    db.session.commit()

    current_app.logger.info(f"Customer login successful: {customer.email}")

    return jsonify({
        'message': 'Login successful',
        'access_token': access_token,
        'refresh_token': refresh_token,
        'customer': {
            'id': str(customer.id),
            'email': customer.email,
            'first_name': customer.first_name,
            'last_name': customer.last_name,
            'company': customer.company,
            'is_verified': customer.is_verified,
            'max_tenants': customer.max_tenants,
            'last_login': customer.last_login.isoformat() if customer.last_login else None
        }
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    current_customer = get_current_user()
    
    if not current_customer or not current_customer.is_active:
        return jsonify({
            'error': 'Invalid User',
            'message': 'Customer account is invalid or disabled'
        }), 401

    access_token = create_access_token(identity=current_customer)
    
    return jsonify({
        'access_token': access_token
    }), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Customer logout"""
    current_customer = get_current_user()
    
    if current_customer:
        current_app.logger.info(f"Customer logged out: {current_customer.email}")
    
    # TODO: Add token to blacklist
    
    return jsonify({
        'message': 'Logout successful'
    }), 200

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get customer profile"""
    current_customer = get_current_user()
    
    return jsonify({
        'customer': current_customer.to_dict()
    }), 200

@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update customer profile"""
    try:
        schema = UpdateProfileSchema()
        data = schema.load(request.get_json() or {})
    except ValidationError as err:
        return jsonify({
            'error': 'Validation Error',
            'message': 'Invalid request data',
            'details': err.messages
        }), 400

    current_customer = get_current_user()
    
    # Update fields
    for field, value in data.items():
        if hasattr(current_customer, field):
            setattr(current_customer, field, value)

    db.session.commit()

    current_app.logger.info(f"Profile updated: {current_customer.email}")

    return jsonify({
        'message': 'Profile updated successfully',
        'customer': current_customer.to_dict()
    }), 200

@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    """Verify email address"""
    # TODO: Implement email verification with tokens
    return jsonify({
        'message': 'Email verification not yet implemented',
        'todo': 'Implement email verification with secure tokens'
    }), 501

@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per minute", key_func=rate_limit_key)
def forgot_password():
    """Request password reset"""
    # TODO: Implement password reset
    return jsonify({
        'message': 'Password reset not yet implemented',
        'todo': 'Implement secure password reset with email tokens'
    }), 501

@auth_bp.route('/reset-password', methods=['POST'])
@limiter.limit("3 per minute", key_func=rate_limit_key)
def reset_password():
    """Reset password with token"""
    # TODO: Implement password reset confirmation
    return jsonify({
        'message': 'Password reset confirmation not yet implemented',
        'todo': 'Implement password reset with secure token validation'
    }), 501

# Health check for auth service
@auth_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'portal-auth',
        'timestamp': datetime.utcnow().isoformat()
    }), 200