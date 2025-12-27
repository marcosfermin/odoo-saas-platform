#!/usr/bin/env python3
"""
Authentication API for Admin Dashboard
Handles login, logout, token refresh, and user management
"""

import os
import sys
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_current_user, get_jwt
)
from marshmallow import Schema, fields, validate, ValidationError

# Add project root to path for shared imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.models import Customer, CustomerRole, AuditAction
from admin.app import db, limiter
from admin.app.utils.auth import (
    audit_log, AuthenticationService, rate_limit_key,
    require_admin, require_verified
)

# Create blueprint
auth_bp = Blueprint('auth', __name__)

# Validation schemas
class LoginSchema(Schema):
    email = fields.Email(required=True, validate=validate.Length(max=255))
    password = fields.Str(required=True, validate=validate.Length(min=1))
    remember_me = fields.Bool(missing=False)

class RegisterSchema(Schema):
    email = fields.Email(required=True, validate=validate.Length(max=255))
    password = fields.Str(required=True, validate=validate.Length(min=8))
    first_name = fields.Str(required=True, validate=validate.Length(max=100))
    last_name = fields.Str(required=True, validate=validate.Length(max=100))
    company = fields.Str(validate=validate.Length(max=200))
    phone = fields.Str(validate=validate.Length(max=20))

class ChangePasswordSchema(Schema):
    current_password = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=8))
    confirm_password = fields.Str(required=True)

class UpdateProfileSchema(Schema):
    first_name = fields.Str(validate=validate.Length(max=100))
    last_name = fields.Str(validate=validate.Length(max=100))
    company = fields.Str(validate=validate.Length(max=200))
    phone = fields.Str(validate=validate.Length(max=20))

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute", key_func=rate_limit_key)
def login():
    """Authenticate user and return JWT tokens"""
    try:
        # Validate request data
        schema = LoginSchema()
        data = schema.load(request.get_json() or {})
        
    except ValidationError as err:
        return jsonify({
            'error': 'Validation Error',
            'message': 'Invalid request data',
            'details': err.messages
        }), 400
    
    # Find user by email
    user = Customer.query.filter_by(email=data['email'].lower()).first()
    
    if not user or not user.check_password(data['password']):
        current_app.logger.warning(f"Failed login attempt for email: {data['email']}")
        return jsonify({
            'error': 'Authentication Failed',
            'message': 'Invalid email or password'
        }), 401
    
    if not user.is_active:
        current_app.logger.warning(f"Login attempt by disabled user: {user.email}")
        return jsonify({
            'error': 'Account Disabled',
            'message': 'Your account has been disabled. Please contact support.'
        }), 403
    
    # Check if user has admin privileges for admin dashboard
    if user.role not in [CustomerRole.ADMIN.value, CustomerRole.OWNER.value]:
        current_app.logger.warning(f"Non-admin user attempted admin login: {user.email}")
        return jsonify({
            'error': 'Access Denied',
            'message': 'Admin privileges required to access this dashboard'
        }), 403
    
    # Create tokens
    expires_delta = timedelta(hours=24) if data['remember_me'] else None
    access_token = create_access_token(
        identity=user,
        expires_delta=expires_delta
    )
    refresh_token = create_refresh_token(identity=user)
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Log successful login
    audit_log(
        action=AuditAction.LOGIN.value,
        resource_type='customer',
        resource_id=str(user.id),
        metadata={
            'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
            'user_agent': request.headers.get('User-Agent', ''),
            'remember_me': data['remember_me']
        }
    )
    
    current_app.logger.info(f"Successful admin login: {user.email}")
    
    return jsonify({
        'message': 'Login successful',
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': str(user.id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'is_verified': user.is_verified,
            'last_login': user.last_login.isoformat() if user.last_login else None
        }
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token using refresh token"""
    current_user = get_current_user()
    
    if not current_user or not current_user.is_active:
        return jsonify({
            'error': 'Invalid User',
            'message': 'User account is invalid or disabled'
        }), 401
    
    # Create new access token
    access_token = create_access_token(identity=current_user)
    
    return jsonify({
        'access_token': access_token
    }), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user and invalidate tokens"""
    current_user = get_current_user()
    jti = get_jwt()['jti']
    
    # Log logout action
    if current_user:
        audit_log(
            action=AuditAction.LOGOUT.value,
            resource_type='customer',
            resource_id=str(current_user.id),
            metadata={
                'token_jti': jti,
                'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            }
        )
        current_app.logger.info(f"User logged out: {current_user.email}")
    
    # Add token to Redis blacklist
    try:
        from redis import Redis

        redis_url = current_app.config.get('REDIS_URL') or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        redis_conn = Redis.from_url(redis_url)

        # Get token expiry from JWT
        jwt_data = get_jwt()
        exp_timestamp = jwt_data.get('exp', 0)

        # Calculate TTL (time until token expires)
        import time
        ttl = max(0, exp_timestamp - int(time.time()))

        if ttl > 0:
            # Add token JTI to blacklist with expiry
            redis_conn.setex(
                f"token_blacklist:{jti}",
                ttl,
                "revoked"
            )
            current_app.logger.info(f"Token {jti} added to blacklist with TTL {ttl}s")

    except Exception as e:
        current_app.logger.warning(f"Failed to add token to blacklist: {e}")
        # Continue with logout even if blacklist fails

    return jsonify({
        'message': 'Logout successful'
    }), 200

@auth_bp.route('/register', methods=['POST'])
@require_admin
@limiter.limit("10 per minute", key_func=rate_limit_key)
def register():
    """Register new admin user (admin only)"""
    try:
        schema = RegisterSchema()
        data = schema.load(request.get_json() or {})
        
    except ValidationError as err:
        return jsonify({
            'error': 'Validation Error',
            'message': 'Invalid request data',
            'details': err.messages
        }), 400
    
    # Validate password strength
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
    
    # Check if user already exists
    existing_user = Customer.query.filter_by(email=data['email'].lower()).first()
    if existing_user:
        return jsonify({
            'error': 'User Exists',
            'message': 'A user with this email address already exists'
        }), 409
    
    # Create new user
    new_user = Customer(
        email=data['email'].lower(),
        first_name=data['first_name'],
        last_name=data['last_name'],
        company=data.get('company'),
        phone=data.get('phone'),
        role=CustomerRole.ADMIN.value,  # New users are admins
        is_active=True,
        is_verified=True,  # Auto-verify admin created accounts
        max_tenants=999,   # High limits for admin users
        max_quota_gb=999,
        email_verified_at=datetime.utcnow()
    )
    new_user.set_password(data['password'])
    
    db.session.add(new_user)
    db.session.commit()
    
    # Log user creation
    audit_log(
        action=AuditAction.CREATE.value,
        resource_type='customer',
        resource_id=str(new_user.id),
        new_values={
            'email': new_user.email,
            'role': new_user.role,
            'created_by': get_current_user().email
        }
    )
    
    current_app.logger.info(f"New admin user created: {new_user.email}")
    
    return jsonify({
        'message': 'User created successfully',
        'user': {
            'id': str(new_user.id),
            'email': new_user.email,
            'first_name': new_user.first_name,
            'last_name': new_user.last_name,
            'role': new_user.role,
            'created_at': new_user.created_at.isoformat()
        }
    }), 201

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile"""
    current_user = get_current_user()
    
    return jsonify({
        'user': current_user.to_dict()
    }), 200

@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
@require_verified
def update_profile():
    """Update current user profile"""
    try:
        schema = UpdateProfileSchema()
        data = schema.load(request.get_json() or {})
        
    except ValidationError as err:
        return jsonify({
            'error': 'Validation Error',
            'message': 'Invalid request data',
            'details': err.messages
        }), 400
    
    current_user = get_current_user()
    old_values = {
        'first_name': current_user.first_name,
        'last_name': current_user.last_name,
        'company': current_user.company,
        'phone': current_user.phone
    }
    
    # Update fields
    for field, value in data.items():
        if hasattr(current_user, field):
            setattr(current_user, field, value)
    
    db.session.commit()
    
    # Log profile update
    audit_log(
        action=AuditAction.UPDATE.value,
        resource_type='customer',
        resource_id=str(current_user.id),
        old_values=old_values,
        new_values=data
    )
    
    current_app.logger.info(f"Profile updated: {current_user.email}")
    
    return jsonify({
        'message': 'Profile updated successfully',
        'user': current_user.to_dict()
    }), 200

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
@require_verified
@limiter.limit("3 per minute", key_func=rate_limit_key)
def change_password():
    """Change user password"""
    try:
        schema = ChangePasswordSchema()
        data = schema.load(request.get_json() or {})
        
    except ValidationError as err:
        return jsonify({
            'error': 'Validation Error',
            'message': 'Invalid request data',
            'details': err.messages
        }), 400
    
    current_user = get_current_user()
    
    # Verify current password
    if not current_user.check_password(data['current_password']):
        return jsonify({
            'error': 'Authentication Failed',
            'message': 'Current password is incorrect'
        }), 401
    
    # Verify password confirmation
    if data['new_password'] != data['confirm_password']:
        return jsonify({
            'error': 'Password Mismatch',
            'message': 'New password and confirmation do not match'
        }), 400
    
    # Validate new password strength
    is_valid, password_errors = AuthenticationService.validate_password_strength(data['new_password'])
    if not is_valid:
        return jsonify({
            'error': 'Weak Password',
            'message': 'New password does not meet security requirements',
            'details': password_errors
        }), 400
    
    # Check for compromised password
    if AuthenticationService.is_password_compromised(data['new_password']):
        return jsonify({
            'error': 'Compromised Password',
            'message': 'This password appears in known data breaches. Please choose a different password.'
        }), 400
    
    # Update password
    current_user.set_password(data['new_password'])
    db.session.commit()
    
    # Log password change
    audit_log(
        action=AuditAction.UPDATE.value,
        resource_type='customer',
        resource_id=str(current_user.id),
        metadata={'action_type': 'password_change'}
    )
    
    current_app.logger.info(f"Password changed: {current_user.email}")
    
    return jsonify({
        'message': 'Password changed successfully'
    }), 200

@auth_bp.route('/users', methods=['GET'])
@require_admin
def list_users():
    """List all admin users (admin only)"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Filter by role (admins only)
    query = Customer.query.filter(
        Customer.role.in_([CustomerRole.ADMIN.value, CustomerRole.OWNER.value])
    )
    
    # Apply search filter
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            Customer.email.ilike(f'%{search}%') |
            Customer.first_name.ilike(f'%{search}%') |
            Customer.last_name.ilike(f'%{search}%') |
            Customer.company.ilike(f'%{search}%')
        )
    
    # Apply status filter
    status = request.args.get('status')
    if status == 'active':
        query = query.filter(Customer.is_active == True)
    elif status == 'inactive':
        query = query.filter(Customer.is_active == False)
    
    # Order by creation date
    query = query.order_by(Customer.created_at.desc())
    
    # Paginate results
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    return jsonify({
        'users': [user.to_dict() for user in pagination.items],
        'pagination': {
            'page': page,
            'pages': pagination.pages,
            'per_page': per_page,
            'total': pagination.total,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200

@auth_bp.route('/users/<user_id>/toggle', methods=['POST'])
@require_admin
def toggle_user_status(user_id):
    """Toggle user active/inactive status (admin only)"""
    user = Customer.query.get_or_404(user_id)
    current_user = get_current_user()
    
    # Prevent self-deactivation
    if user.id == current_user.id:
        return jsonify({
            'error': 'Self Action Not Allowed',
            'message': 'You cannot deactivate your own account'
        }), 400
    
    old_status = user.is_active
    user.is_active = not user.is_active
    db.session.commit()
    
    # Log status change
    audit_log(
        action=AuditAction.UPDATE.value,
        resource_type='customer',
        resource_id=str(user.id),
        old_values={'is_active': old_status},
        new_values={'is_active': user.is_active},
        metadata={'action_type': 'status_toggle'}
    )
    
    action = 'activated' if user.is_active else 'deactivated'
    current_app.logger.info(f"User {action}: {user.email} by {current_user.email}")
    
    return jsonify({
        'message': f'User {action} successfully',
        'user': user.to_dict()
    }), 200

# Health check for auth service
@auth_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'auth',
        'timestamp': datetime.utcnow().isoformat()
    }), 200