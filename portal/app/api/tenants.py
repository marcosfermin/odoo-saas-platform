#!/usr/bin/env python3
"""
Customer Portal Tenant Management API
Self-service tenant creation and management for customers
"""

import os
import sys
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_current_user
from marshmallow import Schema, fields, validate, ValidationError

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.models import Tenant, Plan, TenantState, AuditAction
from portal.app import db, limiter

# Create blueprint
tenants_bp = Blueprint('tenants', __name__)

# Validation schemas
class CreateTenantSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=3, max=200))
    slug = fields.Str(required=True, validate=validate.Length(min=3, max=50))
    plan_id = fields.UUID(required=True)
    custom_domain = fields.Str(validate=validate.Length(max=255))

class UpdateTenantSchema(Schema):
    name = fields.Str(validate=validate.Length(min=3, max=200))
    custom_domain = fields.Str(validate=validate.Length(max=255))

def rate_limit_key():
    """Generate rate limiting key based on user"""
    user = get_current_user()
    if user:
        return f"user:{user.id}"
    return f"ip:{request.remote_addr}"

@tenants_bp.route('/', methods=['GET'])
@jwt_required()
def list_tenants():
    """List customer's tenants"""
    current_customer = get_current_user()
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Filter tenants by current customer
    query = Tenant.query.filter_by(customer_id=current_customer.id)
    
    # Apply state filter
    state = request.args.get('state')
    if state:
        query = query.filter_by(state=state)
    
    # Order by creation date
    query = query.order_by(Tenant.created_at.desc())
    
    # Paginate results
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    tenants = []
    for tenant in pagination.items:
        tenant_data = tenant.to_dict()
        # Add plan information
        if tenant.plan:
            tenant_data['plan'] = {
                'id': str(tenant.plan.id),
                'name': tenant.plan.name,
                'max_users_per_tenant': tenant.plan.max_users_per_tenant,
                'max_db_size_gb': tenant.plan.max_db_size_gb,
                'max_filestore_gb': tenant.plan.max_filestore_gb
            }
        tenants.append(tenant_data)
    
    return jsonify({
        'tenants': tenants,
        'pagination': {
            'page': page,
            'pages': pagination.pages,
            'per_page': per_page,
            'total': pagination.total,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200

@tenants_bp.route('/', methods=['POST'])
@jwt_required()
@limiter.limit("5 per hour", key_func=rate_limit_key)
def create_tenant():
    """Create new tenant"""
    try:
        schema = CreateTenantSchema()
        data = schema.load(request.get_json() or {})
    except ValidationError as err:
        return jsonify({
            'error': 'Validation Error',
            'message': 'Invalid request data',
            'details': err.messages
        }), 400
    
    current_customer = get_current_user()
    
    # Check if customer has reached tenant limit
    existing_tenants = Tenant.query.filter_by(customer_id=current_customer.id).count()
    if existing_tenants >= current_customer.max_tenants:
        return jsonify({
            'error': 'Tenant Limit Reached',
            'message': f'You have reached your maximum limit of {current_customer.max_tenants} tenants'
        }), 400
    
    # Validate plan exists and is active
    plan = Plan.query.get(data['plan_id'])
    if not plan or not plan.is_active:
        return jsonify({
            'error': 'Invalid Plan',
            'message': 'The selected plan is not available'
        }), 400
    
    # Check if slug is available
    existing_slug = Tenant.query.filter_by(slug=data['slug']).first()
    if existing_slug:
        return jsonify({
            'error': 'Slug Unavailable',
            'message': 'This tenant name is already taken'
        }), 409
    
    # Validate slug format
    import re
    if not re.match(r'^[a-z0-9-]+$', data['slug']):
        return jsonify({
            'error': 'Invalid Slug',
            'message': 'Tenant name can only contain lowercase letters, numbers, and hyphens'
        }), 400
    
    # Create database name
    db_name = f"tenant_{data['slug'].replace('-', '_')}"
    
    # Create tenant
    new_tenant = Tenant(
        slug=data['slug'],
        name=data['name'],
        customer_id=current_customer.id,
        plan_id=plan.id,
        state=TenantState.CREATING.value,
        db_name=db_name,
        custom_domain=data.get('custom_domain'),
        filestore_path=f"/var/lib/odoo/filestore/{data['slug']}",
        odoo_version=os.getenv('ODOO_VERSION', '16.0')
    )
    
    db.session.add(new_tenant)
    db.session.commit()
    
    # TODO: Queue tenant provisioning job
    current_app.logger.info(
        f"Tenant creation requested: {new_tenant.slug} by {current_customer.email}"
    )
    
    return jsonify({
        'message': 'Tenant creation initiated',
        'tenant': new_tenant.to_dict()
    }), 201

@tenants_bp.route('/<tenant_id>', methods=['GET'])
@jwt_required()
def get_tenant(tenant_id):
    """Get tenant details"""
    current_customer = get_current_user()
    
    tenant = Tenant.query.filter_by(
        id=tenant_id,
        customer_id=current_customer.id
    ).first()
    
    if not tenant:
        return jsonify({
            'error': 'Tenant Not Found',
            'message': 'The requested tenant does not exist or you do not have access to it'
        }), 404
    
    tenant_data = tenant.to_dict()
    
    # Add plan information
    if tenant.plan:
        tenant_data['plan'] = {
            'id': str(tenant.plan.id),
            'name': tenant.plan.name,
            'description': tenant.plan.description,
            'max_users_per_tenant': tenant.plan.max_users_per_tenant,
            'max_db_size_gb': tenant.plan.max_db_size_gb,
            'max_filestore_gb': tenant.plan.max_filestore_gb,
            'features': tenant.plan.features,
            'allowed_modules': tenant.plan.allowed_modules
        }
    
    # Add usage information
    tenant_data['usage'] = {
        'users_count': tenant.current_users,
        'db_size_mb': round(tenant.db_size_bytes / 1024 / 1024, 2),
        'filestore_size_mb': round(tenant.filestore_size_bytes / 1024 / 1024, 2),
        'db_usage_percent': round((tenant.db_size_bytes / (tenant.plan.max_db_size_gb * 1024**3)) * 100, 1) if tenant.plan else 0,
        'filestore_usage_percent': round((tenant.filestore_size_bytes / (tenant.plan.max_filestore_gb * 1024**3)) * 100, 1) if tenant.plan else 0
    }
    
    return jsonify({
        'tenant': tenant_data
    }), 200

@tenants_bp.route('/<tenant_id>', methods=['PUT'])
@jwt_required()
@limiter.limit("10 per hour", key_func=rate_limit_key)
def update_tenant(tenant_id):
    """Update tenant"""
    try:
        schema = UpdateTenantSchema()
        data = schema.load(request.get_json() or {})
    except ValidationError as err:
        return jsonify({
            'error': 'Validation Error',
            'message': 'Invalid request data',
            'details': err.messages
        }), 400
    
    current_customer = get_current_user()
    
    tenant = Tenant.query.filter_by(
        id=tenant_id,
        customer_id=current_customer.id
    ).first()
    
    if not tenant:
        return jsonify({
            'error': 'Tenant Not Found',
            'message': 'The requested tenant does not exist or you do not have access to it'
        }), 404
    
    if tenant.state != TenantState.ACTIVE.value:
        return jsonify({
            'error': 'Tenant Not Active',
            'message': 'Tenant must be active to be updated'
        }), 400
    
    # Update fields
    for field, value in data.items():
        if hasattr(tenant, field):
            setattr(tenant, field, value)
    
    db.session.commit()
    
    current_app.logger.info(
        f"Tenant updated: {tenant.slug} by {current_customer.email}"
    )
    
    return jsonify({
        'message': 'Tenant updated successfully',
        'tenant': tenant.to_dict()
    }), 200

@tenants_bp.route('/<tenant_id>/modules', methods=['GET'])
@jwt_required()
def list_modules(tenant_id):
    """List installed modules for tenant"""
    current_customer = get_current_user()
    
    tenant = Tenant.query.filter_by(
        id=tenant_id,
        customer_id=current_customer.id
    ).first()
    
    if not tenant:
        return jsonify({
            'error': 'Tenant Not Found',
            'message': 'The requested tenant does not exist or you do not have access to it'
        }), 404
    
    # Get allowed modules from plan
    allowed_modules = []
    if tenant.plan and tenant.plan.allowed_modules:
        if isinstance(tenant.plan.allowed_modules, list):
            allowed_modules = tenant.plan.allowed_modules
        elif tenant.plan.allowed_modules == "*":
            # All modules allowed - return a standard set
            allowed_modules = [
                "base", "web", "mail", "contacts", "calendar", "sale", "crm", 
                "project", "hr", "account", "stock", "purchase", "website", 
                "portal", "note", "mrp", "maintenance", "fleet"
            ]
    
    return jsonify({
        'installed_modules': tenant.installed_modules or [],
        'available_modules': allowed_modules,
        'plan_name': tenant.plan.name if tenant.plan else None
    }), 200

@tenants_bp.route('/<tenant_id>/modules', methods=['POST'])
@jwt_required()
@limiter.limit("5 per hour", key_func=rate_limit_key)
def install_module(tenant_id):
    """Install module on tenant"""
    current_customer = get_current_user()
    
    tenant = Tenant.query.filter_by(
        id=tenant_id,
        customer_id=current_customer.id
    ).first()
    
    if not tenant:
        return jsonify({
            'error': 'Tenant Not Found',
            'message': 'The requested tenant does not exist or you do not have access to it'
        }), 404
    
    if tenant.state != TenantState.ACTIVE.value:
        return jsonify({
            'error': 'Tenant Not Active',
            'message': 'Modules can only be installed on active tenants'
        }), 400
    
    # TODO: Queue module installation job
    return jsonify({
        'message': 'Module installation not yet implemented',
        'todo': 'Implement module installation via RQ jobs'
    }), 501

@tenants_bp.route('/<tenant_id>/backup', methods=['POST'])
@jwt_required()
@limiter.limit("2 per hour", key_func=rate_limit_key)
def backup_tenant(tenant_id):
    """Create tenant backup"""
    current_customer = get_current_user()
    
    tenant = Tenant.query.filter_by(
        id=tenant_id,
        customer_id=current_customer.id
    ).first()
    
    if not tenant:
        return jsonify({
            'error': 'Tenant Not Found',
            'message': 'The requested tenant does not exist or you do not have access to it'
        }), 404
    
    if tenant.state != TenantState.ACTIVE.value:
        return jsonify({
            'error': 'Tenant Not Active',
            'message': 'Backups can only be created for active tenants'
        }), 400
    
    # TODO: Queue backup job
    current_app.logger.info(
        f"Backup requested for tenant: {tenant.slug} by {current_customer.email}"
    )
    
    return jsonify({
        'message': 'Backup creation not yet implemented',
        'todo': 'Implement backup creation via RQ jobs'
    }), 501

@tenants_bp.route('/<tenant_id>/logs', methods=['GET'])
@jwt_required()
def get_tenant_logs(tenant_id):
    """Get tenant logs (last 100 lines)"""
    current_customer = get_current_user()
    
    tenant = Tenant.query.filter_by(
        id=tenant_id,
        customer_id=current_customer.id
    ).first()
    
    if not tenant:
        return jsonify({
            'error': 'Tenant Not Found',
            'message': 'The requested tenant does not exist or you do not have access to it'
        }), 404
    
    # TODO: Implement log retrieval
    return jsonify({
        'message': 'Log retrieval not yet implemented',
        'todo': 'Implement log retrieval from tenant containers/processes'
    }), 501

# Health check
@tenants_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'portal-tenants',
        'timestamp': datetime.utcnow().isoformat()
    }), 200