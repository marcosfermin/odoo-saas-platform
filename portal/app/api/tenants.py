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

    # Queue tenant provisioning job
    try:
        from redis import Redis
        from rq import Queue

        redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        redis_conn = Redis.from_url(redis_url)
        queue = Queue('high', connection=redis_conn)

        job = queue.enqueue(
            'workers.jobs.tenant_jobs.provision_tenant_job',
            str(new_tenant.id),
            str(current_customer.id),
            {
                'slug': new_tenant.slug,
                'name': new_tenant.name,
                'db_name': new_tenant.db_name,
                'plan_id': str(plan.id),
                'odoo_version': new_tenant.odoo_version
            },
            job_timeout=600
        )
        current_app.logger.info(
            f"Tenant provisioning job queued: {new_tenant.slug} (job_id: {job.id})"
        )
    except Exception as e:
        current_app.logger.warning(f"Failed to queue provisioning job: {e}")

    current_app.logger.info(
        f"Tenant creation requested: {new_tenant.slug} by {current_customer.email}"
    )

    return jsonify({
        'message': 'Tenant creation initiated',
        'tenant': new_tenant.to_dict(),
        'status': 'provisioning'
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

    # Get module name from request
    data = request.get_json() or {}
    module_name = data.get('module_name')

    if not module_name:
        return jsonify({
            'error': 'Missing Module',
            'message': 'module_name is required'
        }), 400

    # Check if module is allowed by plan
    allowed_modules = []
    if tenant.plan and tenant.plan.allowed_modules:
        if isinstance(tenant.plan.allowed_modules, list):
            allowed_modules = tenant.plan.allowed_modules
        elif tenant.plan.allowed_modules == "*":
            allowed_modules = None  # All modules allowed

    if allowed_modules is not None and module_name not in allowed_modules:
        return jsonify({
            'error': 'Module Not Allowed',
            'message': f'Module {module_name} is not included in your plan'
        }), 403

    # Check if already installed
    if tenant.installed_modules and module_name in tenant.installed_modules:
        return jsonify({
            'error': 'Already Installed',
            'message': f'Module {module_name} is already installed'
        }), 400

    # Queue module installation job
    try:
        from redis import Redis
        from rq import Queue

        redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        redis_conn = Redis.from_url(redis_url)
        queue = Queue('default', connection=redis_conn)

        job = queue.enqueue(
            'workers.jobs.tenant_jobs.install_module_job',
            str(tenant.id),
            module_name,
            str(current_customer.id),
            job_timeout=300
        )

        current_app.logger.info(
            f"Module installation job queued: {module_name} for {tenant.slug} (job_id: {job.id})"
        )

        return jsonify({
            'message': 'Module installation queued',
            'job_id': job.id,
            'module': module_name,
            'tenant_id': str(tenant.id)
        }), 202

    except Exception as e:
        current_app.logger.error(f"Failed to queue module installation: {e}")
        return jsonify({
            'error': 'Queue Failed',
            'message': 'Failed to queue module installation job'
        }), 500

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

    # Queue backup job
    try:
        from redis import Redis
        from rq import Queue

        redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        redis_conn = Redis.from_url(redis_url)
        queue = Queue('default', connection=redis_conn)

        job = queue.enqueue(
            'workers.jobs.tenant_jobs.backup_tenant_job',
            str(tenant.id),
            job_timeout=1800  # 30 minutes for backup
        )

        current_app.logger.info(
            f"Backup job queued for tenant: {tenant.slug} by {current_customer.email} (job_id: {job.id})"
        )

        return jsonify({
            'message': 'Backup job queued successfully',
            'job_id': job.id,
            'tenant_id': str(tenant.id)
        }), 202

    except Exception as e:
        current_app.logger.error(f"Failed to queue backup job: {e}")
        return jsonify({
            'error': 'Queue Failed',
            'message': 'Failed to queue backup job'
        }), 500

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

    # Get pagination parameters
    lines = min(request.args.get('lines', 100, type=int), 500)
    log_type = request.args.get('type', 'odoo')  # odoo, error, access

    # Try to retrieve logs from the Odoo service
    try:
        import requests
        odoo_service_url = os.getenv('ODOO_SERVICE_URL', 'http://odoo-service:8080')

        response = requests.get(
            f"{odoo_service_url}/tenants/{tenant.id}/logs",
            params={'lines': lines, 'type': log_type},
            timeout=10
        )

        if response.status_code == 200:
            log_data = response.json()
            return jsonify({
                'tenant_id': str(tenant.id),
                'tenant_slug': tenant.slug,
                'log_type': log_type,
                'lines_requested': lines,
                'logs': log_data.get('logs', [])
            }), 200
        else:
            current_app.logger.warning(
                f"Failed to retrieve logs for {tenant.slug}: HTTP {response.status_code}"
            )
            return jsonify({
                'tenant_id': str(tenant.id),
                'tenant_slug': tenant.slug,
                'log_type': log_type,
                'logs': [],
                'message': 'Log retrieval temporarily unavailable'
            }), 200

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Error retrieving logs for {tenant.slug}: {e}")
        return jsonify({
            'tenant_id': str(tenant.id),
            'tenant_slug': tenant.slug,
            'log_type': log_type,
            'logs': [],
            'message': 'Log service temporarily unavailable'
        }), 200

# Health check
@tenants_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'portal-tenants',
        'timestamp': datetime.utcnow().isoformat()
    }), 200