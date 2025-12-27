#!/usr/bin/env python3
"""
Admin Dashboard - Tenant Management API
Full CRUD operations for managing tenants across all customers
"""

import os
import sys
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_current_user
from marshmallow import Schema, fields, validate, ValidationError

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.models import Tenant, Customer, Plan, TenantState, AuditAction
from admin.app import db, limiter
from admin.app.utils.auth import require_admin, audit_log, rate_limit_key

# Create blueprint
tenants_bp = Blueprint('tenants', __name__)


# Validation schemas
class CreateTenantSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=3, max=200))
    slug = fields.Str(required=True, validate=validate.Length(min=3, max=50))
    customer_id = fields.UUID(required=True)
    plan_id = fields.UUID(required=True)
    custom_domain = fields.Str(validate=validate.Length(max=255))
    odoo_version = fields.Str(validate=validate.Length(max=10))


class UpdateTenantSchema(Schema):
    name = fields.Str(validate=validate.Length(min=3, max=200))
    custom_domain = fields.Str(validate=validate.Length(max=255))
    plan_id = fields.UUID()
    state = fields.Str(validate=validate.OneOf([s.value for s in TenantState]))
    state_message = fields.Str()


@tenants_bp.route('/', methods=['GET'])
@require_admin
def list_tenants():
    """List all tenants with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    # Build query
    query = Tenant.query

    # Filter by state
    state = request.args.get('state')
    if state:
        query = query.filter(Tenant.state == state)

    # Filter by customer
    customer_id = request.args.get('customer_id')
    if customer_id:
        query = query.filter(Tenant.customer_id == customer_id)

    # Filter by plan
    plan_id = request.args.get('plan_id')
    if plan_id:
        query = query.filter(Tenant.plan_id == plan_id)

    # Search by name or slug
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            Tenant.name.ilike(f'%{search}%') |
            Tenant.slug.ilike(f'%{search}%') |
            Tenant.custom_domain.ilike(f'%{search}%')
        )

    # Order by
    order_by = request.args.get('order_by', 'created_at')
    order_dir = request.args.get('order_dir', 'desc')

    if hasattr(Tenant, order_by):
        order_column = getattr(Tenant, order_by)
        if order_dir == 'desc':
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())
    else:
        query = query.order_by(Tenant.created_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    tenants = []
    for tenant in pagination.items:
        tenant_data = tenant.to_dict()
        # Add customer info
        if tenant.customer:
            tenant_data['customer'] = {
                'id': str(tenant.customer.id),
                'email': tenant.customer.email,
                'company': tenant.customer.company
            }
        # Add plan info
        if tenant.plan:
            tenant_data['plan'] = {
                'id': str(tenant.plan.id),
                'name': tenant.plan.name
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


@tenants_bp.route('/<tenant_id>', methods=['GET'])
@require_admin
def get_tenant(tenant_id):
    """Get tenant details"""
    tenant = Tenant.query.get(tenant_id)

    if not tenant:
        return jsonify({
            'error': 'Tenant Not Found',
            'message': 'The requested tenant does not exist'
        }), 404

    tenant_data = tenant.to_dict()

    # Add customer info
    if tenant.customer:
        tenant_data['customer'] = tenant.customer.to_dict()

    # Add plan info
    if tenant.plan:
        tenant_data['plan'] = {
            'id': str(tenant.plan.id),
            'name': tenant.plan.name,
            'description': tenant.plan.description,
            'max_users_per_tenant': tenant.plan.max_users_per_tenant,
            'max_db_size_gb': tenant.plan.max_db_size_gb,
            'max_filestore_gb': tenant.plan.max_filestore_gb,
            'features': tenant.plan.features
        }

    # Add usage statistics
    tenant_data['usage'] = {
        'users_count': tenant.current_users,
        'db_size_mb': round(tenant.db_size_bytes / 1024 / 1024, 2),
        'filestore_size_mb': round(tenant.filestore_size_bytes / 1024 / 1024, 2),
        'db_usage_percent': round(
            (tenant.db_size_bytes / (tenant.plan.max_db_size_gb * 1024**3)) * 100, 1
        ) if tenant.plan and tenant.plan.max_db_size_gb else 0,
        'filestore_usage_percent': round(
            (tenant.filestore_size_bytes / (tenant.plan.max_filestore_gb * 1024**3)) * 100, 1
        ) if tenant.plan and tenant.plan.max_filestore_gb else 0
    }

    return jsonify({'tenant': tenant_data}), 200


@tenants_bp.route('/', methods=['POST'])
@require_admin
@limiter.limit("20 per hour", key_func=rate_limit_key)
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

    # Validate customer exists
    customer = Customer.query.get(data['customer_id'])
    if not customer:
        return jsonify({
            'error': 'Customer Not Found',
            'message': 'The specified customer does not exist'
        }), 400

    # Validate plan exists
    plan = Plan.query.get(data['plan_id'])
    if not plan or not plan.is_active:
        return jsonify({
            'error': 'Invalid Plan',
            'message': 'The selected plan is not available'
        }), 400

    # Check if slug is available
    existing = Tenant.query.filter_by(slug=data['slug']).first()
    if existing:
        return jsonify({
            'error': 'Slug Unavailable',
            'message': 'This tenant slug is already taken'
        }), 409

    # Validate slug format
    import re
    if not re.match(r'^[a-z0-9-]+$', data['slug']):
        return jsonify({
            'error': 'Invalid Slug',
            'message': 'Slug can only contain lowercase letters, numbers, and hyphens'
        }), 400

    # Check customer tenant limit
    existing_count = Tenant.query.filter_by(customer_id=customer.id).count()
    if existing_count >= customer.max_tenants:
        return jsonify({
            'error': 'Tenant Limit Reached',
            'message': f'Customer has reached their limit of {customer.max_tenants} tenants'
        }), 400

    # Create tenant
    db_name = f"tenant_{data['slug'].replace('-', '_')}"

    new_tenant = Tenant(
        slug=data['slug'],
        name=data['name'],
        customer_id=customer.id,
        plan_id=plan.id,
        state=TenantState.CREATING.value,
        db_name=db_name,
        custom_domain=data.get('custom_domain'),
        filestore_path=f"/var/lib/odoo/filestore/{data['slug']}",
        odoo_version=data.get('odoo_version', os.getenv('ODOO_VERSION', '16.0'))
    )

    db.session.add(new_tenant)
    db.session.commit()

    # Queue provisioning job
    try:
        from redis import Redis
        from rq import Queue

        redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        redis_conn = Redis.from_url(redis_url)
        queue = Queue('high', connection=redis_conn)

        queue.enqueue(
            'workers.jobs.tenant_jobs.provision_tenant_job',
            str(new_tenant.id),
            str(customer.id),
            {
                'slug': new_tenant.slug,
                'name': new_tenant.name,
                'db_name': new_tenant.db_name,
                'plan_id': str(plan.id),
                'odoo_version': new_tenant.odoo_version
            },
            job_timeout=600
        )
        current_app.logger.info(f"Queued provisioning job for tenant {new_tenant.slug}")
    except Exception as e:
        current_app.logger.warning(f"Failed to queue provisioning job: {e}")

    # Audit log
    audit_log(
        action=AuditAction.CREATE.value,
        resource_type='tenant',
        resource_id=str(new_tenant.id),
        new_values={
            'slug': new_tenant.slug,
            'name': new_tenant.name,
            'customer_id': str(customer.id),
            'plan_id': str(plan.id)
        }
    )

    current_app.logger.info(f"Tenant created: {new_tenant.slug}")

    return jsonify({
        'message': 'Tenant creation initiated',
        'tenant': new_tenant.to_dict()
    }), 201


@tenants_bp.route('/<tenant_id>', methods=['PUT'])
@require_admin
@limiter.limit("30 per hour", key_func=rate_limit_key)
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

    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify({
            'error': 'Tenant Not Found',
            'message': 'The requested tenant does not exist'
        }), 404

    old_values = {
        'name': tenant.name,
        'custom_domain': tenant.custom_domain,
        'plan_id': str(tenant.plan_id) if tenant.plan_id else None,
        'state': tenant.state
    }

    # Validate plan if changing
    if 'plan_id' in data:
        plan = Plan.query.get(data['plan_id'])
        if not plan or not plan.is_active:
            return jsonify({
                'error': 'Invalid Plan',
                'message': 'The selected plan is not available'
            }), 400

    # Update fields
    for field, value in data.items():
        if hasattr(tenant, field):
            setattr(tenant, field, value)

    db.session.commit()

    # Audit log
    audit_log(
        action=AuditAction.UPDATE.value,
        resource_type='tenant',
        resource_id=str(tenant.id),
        old_values=old_values,
        new_values=data
    )

    current_app.logger.info(f"Tenant updated: {tenant.slug}")

    return jsonify({
        'message': 'Tenant updated successfully',
        'tenant': tenant.to_dict()
    }), 200


@tenants_bp.route('/<tenant_id>', methods=['DELETE'])
@require_admin
@limiter.limit("10 per hour", key_func=rate_limit_key)
def delete_tenant(tenant_id):
    """Delete tenant (marks for deletion)"""
    tenant = Tenant.query.get(tenant_id)

    if not tenant:
        return jsonify({
            'error': 'Tenant Not Found',
            'message': 'The requested tenant does not exist'
        }), 404

    if tenant.state == TenantState.DELETED.value:
        return jsonify({
            'error': 'Already Deleted',
            'message': 'This tenant has already been deleted'
        }), 400

    # Mark as deleting
    old_state = tenant.state
    tenant.state = TenantState.DELETING.value
    db.session.commit()

    # Queue deletion job
    try:
        from redis import Redis
        from rq import Queue

        redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        redis_conn = Redis.from_url(redis_url)
        queue = Queue('high', connection=redis_conn)

        queue.enqueue(
            'workers.jobs.tenant_jobs.delete_tenant_job',
            str(tenant.id),
            job_timeout=600
        )
        current_app.logger.info(f"Queued deletion job for tenant {tenant.slug}")
    except Exception as e:
        current_app.logger.warning(f"Failed to queue deletion job: {e}")

    # Audit log
    audit_log(
        action=AuditAction.DELETE.value,
        resource_type='tenant',
        resource_id=str(tenant.id),
        old_values={'state': old_state},
        new_values={'state': TenantState.DELETING.value}
    )

    current_app.logger.info(f"Tenant marked for deletion: {tenant.slug}")

    return jsonify({
        'message': 'Tenant deletion initiated',
        'tenant': tenant.to_dict()
    }), 200


@tenants_bp.route('/<tenant_id>/suspend', methods=['POST'])
@require_admin
def suspend_tenant(tenant_id):
    """Suspend a tenant"""
    tenant = Tenant.query.get(tenant_id)

    if not tenant:
        return jsonify({
            'error': 'Tenant Not Found',
            'message': 'The requested tenant does not exist'
        }), 404

    if tenant.state != TenantState.ACTIVE.value:
        return jsonify({
            'error': 'Invalid State',
            'message': 'Only active tenants can be suspended'
        }), 400

    old_state = tenant.state
    tenant.state = TenantState.SUSPENDED.value
    tenant.suspended_at = datetime.utcnow()
    db.session.commit()

    # Audit log
    audit_log(
        action=AuditAction.SUSPEND.value,
        resource_type='tenant',
        resource_id=str(tenant.id),
        old_values={'state': old_state},
        new_values={'state': TenantState.SUSPENDED.value}
    )

    return jsonify({
        'message': 'Tenant suspended successfully',
        'tenant': tenant.to_dict()
    }), 200


@tenants_bp.route('/<tenant_id>/unsuspend', methods=['POST'])
@require_admin
def unsuspend_tenant(tenant_id):
    """Unsuspend a tenant"""
    tenant = Tenant.query.get(tenant_id)

    if not tenant:
        return jsonify({
            'error': 'Tenant Not Found',
            'message': 'The requested tenant does not exist'
        }), 404

    if tenant.state != TenantState.SUSPENDED.value:
        return jsonify({
            'error': 'Invalid State',
            'message': 'Only suspended tenants can be unsuspended'
        }), 400

    old_state = tenant.state
    tenant.state = TenantState.ACTIVE.value
    tenant.suspended_at = None
    db.session.commit()

    # Audit log
    audit_log(
        action=AuditAction.UNSUSPEND.value,
        resource_type='tenant',
        resource_id=str(tenant.id),
        old_values={'state': old_state},
        new_values={'state': TenantState.ACTIVE.value}
    )

    return jsonify({
        'message': 'Tenant unsuspended successfully',
        'tenant': tenant.to_dict()
    }), 200


@tenants_bp.route('/<tenant_id>/backup', methods=['POST'])
@require_admin
@limiter.limit("5 per hour", key_func=rate_limit_key)
def backup_tenant(tenant_id):
    """Create a backup for a tenant"""
    tenant = Tenant.query.get(tenant_id)

    if not tenant:
        return jsonify({
            'error': 'Tenant Not Found',
            'message': 'The requested tenant does not exist'
        }), 404

    if tenant.state != TenantState.ACTIVE.value:
        return jsonify({
            'error': 'Invalid State',
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
            job_timeout=1800
        )

        # Audit log
        audit_log(
            action=AuditAction.BACKUP.value,
            resource_type='tenant',
            resource_id=str(tenant.id),
            metadata={'job_id': job.id}
        )

        current_app.logger.info(f"Queued backup job for tenant {tenant.slug}")

        return jsonify({
            'message': 'Backup job queued successfully',
            'job_id': job.id,
            'tenant': tenant.to_dict()
        }), 202

    except Exception as e:
        current_app.logger.error(f"Failed to queue backup job: {e}")
        return jsonify({
            'error': 'Backup Failed',
            'message': 'Failed to queue backup job'
        }), 500


@tenants_bp.route('/<tenant_id>/restore', methods=['POST'])
@require_admin
@limiter.limit("3 per hour", key_func=rate_limit_key)
def restore_tenant(tenant_id):
    """Restore tenant from backup"""
    tenant = Tenant.query.get(tenant_id)

    if not tenant:
        return jsonify({
            'error': 'Tenant Not Found',
            'message': 'The requested tenant does not exist'
        }), 404

    data = request.get_json() or {}
    backup_file = data.get('backup_file')

    if not backup_file:
        return jsonify({
            'error': 'Missing Backup File',
            'message': 'backup_file is required'
        }), 400

    # Queue restore job
    try:
        from redis import Redis
        from rq import Queue

        redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        redis_conn = Redis.from_url(redis_url)
        queue = Queue('high', connection=redis_conn)

        job = queue.enqueue(
            'workers.jobs.tenant_jobs.restore_tenant_job',
            str(tenant.id),
            backup_file,
            job_timeout=1800
        )

        # Audit log
        audit_log(
            action=AuditAction.RESTORE.value,
            resource_type='tenant',
            resource_id=str(tenant.id),
            metadata={'job_id': job.id, 'backup_file': backup_file}
        )

        current_app.logger.info(f"Queued restore job for tenant {tenant.slug}")

        return jsonify({
            'message': 'Restore job queued successfully',
            'job_id': job.id,
            'tenant': tenant.to_dict()
        }), 202

    except Exception as e:
        current_app.logger.error(f"Failed to queue restore job: {e}")
        return jsonify({
            'error': 'Restore Failed',
            'message': 'Failed to queue restore job'
        }), 500


# Health check
@tenants_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'admin-tenants',
        'timestamp': datetime.utcnow().isoformat()
    }), 200
