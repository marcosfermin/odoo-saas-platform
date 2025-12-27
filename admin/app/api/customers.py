#!/usr/bin/env python3
"""
Admin Dashboard - Customer Management API
Full CRUD operations for managing customers
"""

import os
import sys
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_current_user
from marshmallow import Schema, fields, validate, ValidationError

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.models import Customer, Tenant, Subscription, CustomerRole, AuditAction
from admin.app import db, limiter
from admin.app.utils.auth import require_admin, audit_log, rate_limit_key, AuthenticationService

# Create blueprint
customers_bp = Blueprint('customers', __name__)


# Validation schemas
class CreateCustomerSchema(Schema):
    email = fields.Email(required=True, validate=validate.Length(max=255))
    password = fields.Str(required=True, validate=validate.Length(min=8))
    first_name = fields.Str(required=True, validate=validate.Length(max=100))
    last_name = fields.Str(required=True, validate=validate.Length(max=100))
    company = fields.Str(validate=validate.Length(max=200))
    phone = fields.Str(validate=validate.Length(max=20))
    role = fields.Str(validate=validate.OneOf([r.value for r in CustomerRole]))
    max_tenants = fields.Int(validate=validate.Range(min=1, max=100))
    max_quota_gb = fields.Int(validate=validate.Range(min=1, max=1000))


class UpdateCustomerSchema(Schema):
    first_name = fields.Str(validate=validate.Length(max=100))
    last_name = fields.Str(validate=validate.Length(max=100))
    company = fields.Str(validate=validate.Length(max=200))
    phone = fields.Str(validate=validate.Length(max=20))
    role = fields.Str(validate=validate.OneOf([r.value for r in CustomerRole]))
    is_active = fields.Bool()
    is_verified = fields.Bool()
    max_tenants = fields.Int(validate=validate.Range(min=1, max=100))
    max_quota_gb = fields.Int(validate=validate.Range(min=1, max=1000))


@customers_bp.route('/', methods=['GET'])
@require_admin
def list_customers():
    """List all customers with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    # Build query
    query = Customer.query

    # Filter by role
    role = request.args.get('role')
    if role:
        query = query.filter(Customer.role == role)

    # Filter by status
    status = request.args.get('status')
    if status == 'active':
        query = query.filter(Customer.is_active == True)
    elif status == 'inactive':
        query = query.filter(Customer.is_active == False)

    # Filter by verified
    verified = request.args.get('verified')
    if verified == 'true':
        query = query.filter(Customer.is_verified == True)
    elif verified == 'false':
        query = query.filter(Customer.is_verified == False)

    # Search
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            Customer.email.ilike(f'%{search}%') |
            Customer.first_name.ilike(f'%{search}%') |
            Customer.last_name.ilike(f'%{search}%') |
            Customer.company.ilike(f'%{search}%')
        )

    # Order by
    order_by = request.args.get('order_by', 'created_at')
    order_dir = request.args.get('order_dir', 'desc')

    if hasattr(Customer, order_by):
        order_column = getattr(Customer, order_by)
        if order_dir == 'desc':
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())
    else:
        query = query.order_by(Customer.created_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    customers = []
    for customer in pagination.items:
        customer_data = customer.to_dict()
        # Add tenant count
        customer_data['tenant_count'] = Tenant.query.filter_by(customer_id=customer.id).count()
        # Add subscription info
        active_sub = Subscription.query.filter_by(
            customer_id=customer.id,
            status='active'
        ).first()
        if active_sub:
            customer_data['subscription'] = {
                'id': str(active_sub.id),
                'status': active_sub.status,
                'plan_name': active_sub.plan.name if active_sub.plan else None
            }
        customers.append(customer_data)

    return jsonify({
        'customers': customers,
        'pagination': {
            'page': page,
            'pages': pagination.pages,
            'per_page': per_page,
            'total': pagination.total,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200


@customers_bp.route('/<customer_id>', methods=['GET'])
@require_admin
def get_customer(customer_id):
    """Get customer details"""
    customer = Customer.query.get(customer_id)

    if not customer:
        return jsonify({
            'error': 'Customer Not Found',
            'message': 'The requested customer does not exist'
        }), 404

    customer_data = customer.to_dict()

    # Add tenants
    tenants = Tenant.query.filter_by(customer_id=customer.id).all()
    customer_data['tenants'] = [t.to_dict() for t in tenants]

    # Add subscriptions
    subscriptions = Subscription.query.filter_by(customer_id=customer.id).all()
    customer_data['subscriptions'] = []
    for sub in subscriptions:
        sub_data = {
            'id': str(sub.id),
            'status': sub.status,
            'provider': sub.provider,
            'amount': float(sub.amount) if sub.amount else None,
            'currency': sub.currency,
            'interval': sub.interval,
            'current_period_end': sub.current_period_end.isoformat() if sub.current_period_end else None,
            'plan': {
                'id': str(sub.plan.id),
                'name': sub.plan.name
            } if sub.plan else None
        }
        customer_data['subscriptions'].append(sub_data)

    # Add usage summary
    total_db_size = sum(t.db_size_bytes for t in tenants)
    total_filestore_size = sum(t.filestore_size_bytes for t in tenants)
    customer_data['usage'] = {
        'tenant_count': len(tenants),
        'total_db_size_mb': round(total_db_size / 1024 / 1024, 2),
        'total_filestore_size_mb': round(total_filestore_size / 1024 / 1024, 2),
        'quota_used_percent': round(
            ((total_db_size + total_filestore_size) / (customer.max_quota_gb * 1024**3)) * 100, 1
        ) if customer.max_quota_gb else 0
    }

    return jsonify({'customer': customer_data}), 200


@customers_bp.route('/', methods=['POST'])
@require_admin
@limiter.limit("20 per hour", key_func=rate_limit_key)
def create_customer():
    """Create new customer"""
    try:
        schema = CreateCustomerSchema()
        data = schema.load(request.get_json() or {})
    except ValidationError as err:
        return jsonify({
            'error': 'Validation Error',
            'message': 'Invalid request data',
            'details': err.messages
        }), 400

    # Check if email exists
    existing = Customer.query.filter_by(email=data['email'].lower()).first()
    if existing:
        return jsonify({
            'error': 'Email Exists',
            'message': 'A customer with this email already exists'
        }), 409

    # Validate password strength
    is_valid, errors = AuthenticationService.validate_password_strength(data['password'])
    if not is_valid:
        return jsonify({
            'error': 'Weak Password',
            'message': 'Password does not meet requirements',
            'details': errors
        }), 400

    # Create customer
    new_customer = Customer(
        email=data['email'].lower(),
        first_name=data['first_name'],
        last_name=data['last_name'],
        company=data.get('company'),
        phone=data.get('phone'),
        role=data.get('role', CustomerRole.OWNER.value),
        is_active=True,
        is_verified=True,  # Admin-created accounts are auto-verified
        max_tenants=data.get('max_tenants', 5),
        max_quota_gb=data.get('max_quota_gb', 50),
        email_verified_at=datetime.utcnow()
    )
    new_customer.set_password(data['password'])

    db.session.add(new_customer)
    db.session.commit()

    # Audit log
    audit_log(
        action=AuditAction.CREATE.value,
        resource_type='customer',
        resource_id=str(new_customer.id),
        new_values={
            'email': new_customer.email,
            'role': new_customer.role
        }
    )

    current_app.logger.info(f"Customer created: {new_customer.email}")

    return jsonify({
        'message': 'Customer created successfully',
        'customer': new_customer.to_dict()
    }), 201


@customers_bp.route('/<customer_id>', methods=['PUT'])
@require_admin
@limiter.limit("30 per hour", key_func=rate_limit_key)
def update_customer(customer_id):
    """Update customer"""
    try:
        schema = UpdateCustomerSchema()
        data = schema.load(request.get_json() or {})
    except ValidationError as err:
        return jsonify({
            'error': 'Validation Error',
            'message': 'Invalid request data',
            'details': err.messages
        }), 400

    customer = Customer.query.get(customer_id)
    if not customer:
        return jsonify({
            'error': 'Customer Not Found',
            'message': 'The requested customer does not exist'
        }), 404

    current_user = get_current_user()

    # Prevent self-role-change
    if 'role' in data and str(customer.id) == str(current_user.id):
        return jsonify({
            'error': 'Self Modification',
            'message': 'You cannot change your own role'
        }), 400

    # Prevent self-deactivation
    if 'is_active' in data and not data['is_active'] and str(customer.id) == str(current_user.id):
        return jsonify({
            'error': 'Self Deactivation',
            'message': 'You cannot deactivate your own account'
        }), 400

    old_values = {
        'first_name': customer.first_name,
        'last_name': customer.last_name,
        'company': customer.company,
        'role': customer.role,
        'is_active': customer.is_active,
        'is_verified': customer.is_verified,
        'max_tenants': customer.max_tenants,
        'max_quota_gb': customer.max_quota_gb
    }

    # Update fields
    for field, value in data.items():
        if hasattr(customer, field):
            setattr(customer, field, value)

    db.session.commit()

    # Audit log
    audit_log(
        action=AuditAction.UPDATE.value,
        resource_type='customer',
        resource_id=str(customer.id),
        old_values=old_values,
        new_values=data
    )

    current_app.logger.info(f"Customer updated: {customer.email}")

    return jsonify({
        'message': 'Customer updated successfully',
        'customer': customer.to_dict()
    }), 200


@customers_bp.route('/<customer_id>', methods=['DELETE'])
@require_admin
@limiter.limit("10 per hour", key_func=rate_limit_key)
def delete_customer(customer_id):
    """Delete customer (and all associated tenants)"""
    customer = Customer.query.get(customer_id)

    if not customer:
        return jsonify({
            'error': 'Customer Not Found',
            'message': 'The requested customer does not exist'
        }), 404

    current_user = get_current_user()

    # Prevent self-deletion
    if str(customer.id) == str(current_user.id):
        return jsonify({
            'error': 'Self Deletion',
            'message': 'You cannot delete your own account'
        }), 400

    # Check for active tenants
    active_tenants = Tenant.query.filter(
        Tenant.customer_id == customer.id,
        Tenant.state.notin_(['deleted', 'deleting'])
    ).count()

    if active_tenants > 0:
        return jsonify({
            'error': 'Active Tenants Exist',
            'message': f'Customer has {active_tenants} active tenants. Delete tenants first.'
        }), 400

    # Store info for audit log
    customer_email = customer.email

    # Delete customer (cascade will handle related records)
    db.session.delete(customer)
    db.session.commit()

    # Audit log
    audit_log(
        action=AuditAction.DELETE.value,
        resource_type='customer',
        resource_id=str(customer_id),
        old_values={'email': customer_email}
    )

    current_app.logger.info(f"Customer deleted: {customer_email}")

    return jsonify({
        'message': 'Customer deleted successfully'
    }), 200


@customers_bp.route('/<customer_id>/reset-password', methods=['POST'])
@require_admin
@limiter.limit("10 per hour", key_func=rate_limit_key)
def reset_customer_password(customer_id):
    """Reset customer password"""
    customer = Customer.query.get(customer_id)

    if not customer:
        return jsonify({
            'error': 'Customer Not Found',
            'message': 'The requested customer does not exist'
        }), 404

    data = request.get_json() or {}
    new_password = data.get('new_password')

    if not new_password:
        return jsonify({
            'error': 'Missing Password',
            'message': 'new_password is required'
        }), 400

    # Validate password strength
    is_valid, errors = AuthenticationService.validate_password_strength(new_password)
    if not is_valid:
        return jsonify({
            'error': 'Weak Password',
            'message': 'Password does not meet requirements',
            'details': errors
        }), 400

    customer.set_password(new_password)
    db.session.commit()

    # Audit log
    audit_log(
        action=AuditAction.UPDATE.value,
        resource_type='customer',
        resource_id=str(customer.id),
        metadata={'action_type': 'password_reset'}
    )

    current_app.logger.info(f"Password reset for customer: {customer.email}")

    return jsonify({
        'message': 'Password reset successfully'
    }), 200


@customers_bp.route('/<customer_id>/impersonate', methods=['POST'])
@require_admin
@limiter.limit("5 per hour", key_func=rate_limit_key)
def impersonate_customer(customer_id):
    """Generate impersonation token for customer"""
    from flask_jwt_extended import create_access_token

    customer = Customer.query.get(customer_id)

    if not customer:
        return jsonify({
            'error': 'Customer Not Found',
            'message': 'The requested customer does not exist'
        }), 404

    if not customer.is_active:
        return jsonify({
            'error': 'Customer Inactive',
            'message': 'Cannot impersonate an inactive customer'
        }), 400

    # Create impersonation token
    access_token = create_access_token(
        identity=customer,
        additional_claims={'impersonated': True}
    )

    # Audit log
    audit_log(
        action=AuditAction.IMPERSONATE.value,
        resource_type='customer',
        resource_id=str(customer.id),
        metadata={'target_email': customer.email}
    )

    current_app.logger.info(f"Impersonation token created for: {customer.email}")

    return jsonify({
        'message': 'Impersonation token created',
        'access_token': access_token,
        'customer': {
            'id': str(customer.id),
            'email': customer.email
        }
    }), 200


# Health check
@customers_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'admin-customers',
        'timestamp': datetime.utcnow().isoformat()
    }), 200
