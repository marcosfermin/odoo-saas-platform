#!/usr/bin/env python3
"""
Admin Dashboard - Plan Management API
Full CRUD operations for managing billing plans
"""

import os
import sys
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_current_user
from marshmallow import Schema, fields, validate, ValidationError

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.models import Plan, Tenant, Subscription, AuditAction
from admin.app import db, limiter
from admin.app.utils.auth import require_admin, audit_log, rate_limit_key

# Create blueprint
plans_bp = Blueprint('plans', __name__)


# Validation schemas
class CreatePlanSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    description = fields.Str()
    price_monthly = fields.Decimal(places=2)
    price_yearly = fields.Decimal(places=2)
    currency = fields.Str(validate=validate.Length(equal=3))
    max_tenants = fields.Int(validate=validate.Range(min=1, max=100))
    max_users_per_tenant = fields.Int(validate=validate.Range(min=1, max=1000))
    max_db_size_gb = fields.Int(validate=validate.Range(min=1, max=500))
    max_filestore_gb = fields.Int(validate=validate.Range(min=1, max=500))
    features = fields.Dict()
    allowed_modules = fields.List(fields.Str())
    stripe_price_id_monthly = fields.Str()
    stripe_price_id_yearly = fields.Str()
    paddle_plan_id = fields.Str()
    is_active = fields.Bool()
    trial_days = fields.Int(validate=validate.Range(min=0, max=90))


class UpdatePlanSchema(Schema):
    name = fields.Str(validate=validate.Length(min=2, max=100))
    description = fields.Str()
    price_monthly = fields.Decimal(places=2)
    price_yearly = fields.Decimal(places=2)
    currency = fields.Str(validate=validate.Length(equal=3))
    max_tenants = fields.Int(validate=validate.Range(min=1, max=100))
    max_users_per_tenant = fields.Int(validate=validate.Range(min=1, max=1000))
    max_db_size_gb = fields.Int(validate=validate.Range(min=1, max=500))
    max_filestore_gb = fields.Int(validate=validate.Range(min=1, max=500))
    features = fields.Dict()
    allowed_modules = fields.List(fields.Str())
    stripe_price_id_monthly = fields.Str()
    stripe_price_id_yearly = fields.Str()
    paddle_plan_id = fields.Str()
    is_active = fields.Bool()
    trial_days = fields.Int(validate=validate.Range(min=0, max=90))


@plans_bp.route('/', methods=['GET'])
@require_admin
def list_plans():
    """List all plans with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    # Build query
    query = Plan.query

    # Filter by active status
    status = request.args.get('status')
    if status == 'active':
        query = query.filter(Plan.is_active == True)
    elif status == 'inactive':
        query = query.filter(Plan.is_active == False)

    # Search
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            Plan.name.ilike(f'%{search}%') |
            Plan.description.ilike(f'%{search}%')
        )

    # Order by
    order_by = request.args.get('order_by', 'price_monthly')
    order_dir = request.args.get('order_dir', 'asc')

    if hasattr(Plan, order_by):
        order_column = getattr(Plan, order_by)
        if order_dir == 'desc':
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())
    else:
        query = query.order_by(Plan.price_monthly.asc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    plans = []
    for plan in pagination.items:
        plan_data = {
            'id': str(plan.id),
            'name': plan.name,
            'description': plan.description,
            'price_monthly': float(plan.price_monthly) if plan.price_monthly else None,
            'price_yearly': float(plan.price_yearly) if plan.price_yearly else None,
            'currency': plan.currency,
            'max_tenants': plan.max_tenants,
            'max_users_per_tenant': plan.max_users_per_tenant,
            'max_db_size_gb': plan.max_db_size_gb,
            'max_filestore_gb': plan.max_filestore_gb,
            'features': plan.features,
            'allowed_modules': plan.allowed_modules,
            'is_active': plan.is_active,
            'trial_days': plan.trial_days,
            'created_at': plan.created_at.isoformat() if plan.created_at else None,
            # Add usage stats
            'tenant_count': db.session.query(Tenant).filter_by(plan_id=plan.id).count(),
            'subscription_count': db.session.query(Subscription).filter_by(plan_id=plan.id).count()
        }
        plans.append(plan_data)

    return jsonify({
        'plans': plans,
        'pagination': {
            'page': page,
            'pages': pagination.pages,
            'per_page': per_page,
            'total': pagination.total,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200


@plans_bp.route('/<plan_id>', methods=['GET'])
@require_admin
def get_plan(plan_id):
    """Get plan details"""
    plan = db.session.get(Plan, plan_id)

    if not plan:
        return jsonify({
            'error': 'Plan Not Found',
            'message': 'The requested plan does not exist'
        }), 404

    plan_data = {
        'id': str(plan.id),
        'name': plan.name,
        'description': plan.description,
        'price_monthly': float(plan.price_monthly) if plan.price_monthly else None,
        'price_yearly': float(plan.price_yearly) if plan.price_yearly else None,
        'currency': plan.currency,
        'max_tenants': plan.max_tenants,
        'max_users_per_tenant': plan.max_users_per_tenant,
        'max_db_size_gb': plan.max_db_size_gb,
        'max_filestore_gb': plan.max_filestore_gb,
        'features': plan.features,
        'allowed_modules': plan.allowed_modules,
        'stripe_price_id_monthly': plan.stripe_price_id_monthly,
        'stripe_price_id_yearly': plan.stripe_price_id_yearly,
        'paddle_plan_id': plan.paddle_plan_id,
        'is_active': plan.is_active,
        'trial_days': plan.trial_days,
        'created_at': plan.created_at.isoformat() if plan.created_at else None,
        'updated_at': plan.updated_at.isoformat() if plan.updated_at else None
    }

    # Add usage statistics
    tenants = db.session.query(Tenant).filter_by(plan_id=plan.id).all()
    subscriptions = db.session.query(Subscription).filter_by(plan_id=plan.id).all()

    plan_data['statistics'] = {
        'tenant_count': len(tenants),
        'active_tenant_count': sum(1 for t in tenants if t.state == 'active'),
        'subscription_count': len(subscriptions),
        'active_subscription_count': sum(1 for s in subscriptions if s.status == 'active'),
        'total_monthly_revenue': sum(
            float(s.amount) for s in subscriptions
            if s.status == 'active' and s.interval == 'month' and s.amount
        ),
        'total_yearly_revenue': sum(
            float(s.amount) for s in subscriptions
            if s.status == 'active' and s.interval == 'year' and s.amount
        )
    }

    return jsonify({'plan': plan_data}), 200


@plans_bp.route('/', methods=['POST'])
@require_admin
@limiter.limit("20 per hour", key_func=rate_limit_key)
def create_plan():
    """Create new plan"""
    try:
        schema = CreatePlanSchema()
        data = schema.load(request.get_json() or {})
    except ValidationError as err:
        return jsonify({
            'error': 'Validation Error',
            'message': 'Invalid request data',
            'details': err.messages
        }), 400

    # Check if name exists
    existing = db.session.query(Plan).filter_by(name=data['name']).first()
    if existing:
        return jsonify({
            'error': 'Name Exists',
            'message': 'A plan with this name already exists'
        }), 409

    # Create plan
    new_plan = Plan(
        name=data['name'],
        description=data.get('description'),
        price_monthly=data.get('price_monthly'),
        price_yearly=data.get('price_yearly'),
        currency=data.get('currency', 'USD'),
        max_tenants=data.get('max_tenants', 1),
        max_users_per_tenant=data.get('max_users_per_tenant', 10),
        max_db_size_gb=data.get('max_db_size_gb', 5),
        max_filestore_gb=data.get('max_filestore_gb', 2),
        features=data.get('features', {}),
        allowed_modules=data.get('allowed_modules'),
        stripe_price_id_monthly=data.get('stripe_price_id_monthly'),
        stripe_price_id_yearly=data.get('stripe_price_id_yearly'),
        paddle_plan_id=data.get('paddle_plan_id'),
        is_active=data.get('is_active', True),
        trial_days=data.get('trial_days', 14)
    )

    db.session.add(new_plan)
    db.session.commit()

    # Audit log
    audit_log(
        action=AuditAction.CREATE.value,
        resource_type='plan',
        resource_id=str(new_plan.id),
        new_values={
            'name': new_plan.name,
            'price_monthly': float(new_plan.price_monthly) if new_plan.price_monthly else None,
            'price_yearly': float(new_plan.price_yearly) if new_plan.price_yearly else None
        }
    )

    current_app.logger.info(f"Plan created: {new_plan.name}")

    return jsonify({
        'message': 'Plan created successfully',
        'plan': {
            'id': str(new_plan.id),
            'name': new_plan.name,
            'is_active': new_plan.is_active
        }
    }), 201


@plans_bp.route('/<plan_id>', methods=['PUT'])
@require_admin
@limiter.limit("30 per hour", key_func=rate_limit_key)
def update_plan(plan_id):
    """Update plan"""
    try:
        schema = UpdatePlanSchema()
        data = schema.load(request.get_json() or {})
    except ValidationError as err:
        return jsonify({
            'error': 'Validation Error',
            'message': 'Invalid request data',
            'details': err.messages
        }), 400

    plan = db.session.get(Plan, plan_id)
    if not plan:
        return jsonify({
            'error': 'Plan Not Found',
            'message': 'The requested plan does not exist'
        }), 404

    # Check for name conflict
    if 'name' in data and data['name'] != plan.name:
        existing = db.session.query(Plan).filter_by(name=data['name']).first()
        if existing:
            return jsonify({
                'error': 'Name Exists',
                'message': 'A plan with this name already exists'
            }), 409

    old_values = {
        'name': plan.name,
        'price_monthly': float(plan.price_monthly) if plan.price_monthly else None,
        'price_yearly': float(plan.price_yearly) if plan.price_yearly else None,
        'is_active': plan.is_active
    }

    # Update fields
    for field, value in data.items():
        if hasattr(plan, field):
            setattr(plan, field, value)

    db.session.commit()

    # Audit log
    audit_log(
        action=AuditAction.UPDATE.value,
        resource_type='plan',
        resource_id=str(plan.id),
        old_values=old_values,
        new_values={k: (float(v) if isinstance(v, Decimal) else v) for k, v in data.items()}
    )

    current_app.logger.info(f"Plan updated: {plan.name}")

    return jsonify({
        'message': 'Plan updated successfully',
        'plan': {
            'id': str(plan.id),
            'name': plan.name,
            'is_active': plan.is_active
        }
    }), 200


@plans_bp.route('/<plan_id>', methods=['DELETE'])
@require_admin
@limiter.limit("10 per hour", key_func=rate_limit_key)
def delete_plan(plan_id):
    """Delete plan (if no tenants/subscriptions are using it)"""
    plan = db.session.get(Plan, plan_id)

    if not plan:
        return jsonify({
            'error': 'Plan Not Found',
            'message': 'The requested plan does not exist'
        }), 404

    # Check for associated tenants
    tenant_count = db.session.query(Tenant).filter_by(plan_id=plan.id).count()
    if tenant_count > 0:
        return jsonify({
            'error': 'Plan In Use',
            'message': f'This plan has {tenant_count} tenants. Migrate tenants before deleting.'
        }), 400

    # Check for active subscriptions
    sub_count = db.session.query(Subscription).filter(
        Subscription.plan_id == plan.id,
        Subscription.status.in_(['active', 'trialing'])
    ).count()
    if sub_count > 0:
        return jsonify({
            'error': 'Plan In Use',
            'message': f'This plan has {sub_count} active subscriptions. Cancel subscriptions before deleting.'
        }), 400

    plan_name = plan.name
    db.session.delete(plan)
    db.session.commit()

    # Audit log
    audit_log(
        action=AuditAction.DELETE.value,
        resource_type='plan',
        resource_id=str(plan_id),
        old_values={'name': plan_name}
    )

    current_app.logger.info(f"Plan deleted: {plan_name}")

    return jsonify({
        'message': 'Plan deleted successfully'
    }), 200


@plans_bp.route('/<plan_id>/deactivate', methods=['POST'])
@require_admin
def deactivate_plan(plan_id):
    """Deactivate a plan (prevent new subscriptions)"""
    plan = db.session.get(Plan, plan_id)

    if not plan:
        return jsonify({
            'error': 'Plan Not Found',
            'message': 'The requested plan does not exist'
        }), 404

    if not plan.is_active:
        return jsonify({
            'error': 'Already Inactive',
            'message': 'This plan is already inactive'
        }), 400

    plan.is_active = False
    db.session.commit()

    # Audit log
    audit_log(
        action=AuditAction.UPDATE.value,
        resource_type='plan',
        resource_id=str(plan.id),
        old_values={'is_active': True},
        new_values={'is_active': False}
    )

    return jsonify({
        'message': 'Plan deactivated successfully',
        'plan': {
            'id': str(plan.id),
            'name': plan.name,
            'is_active': plan.is_active
        }
    }), 200


@plans_bp.route('/<plan_id>/activate', methods=['POST'])
@require_admin
def activate_plan(plan_id):
    """Activate a plan"""
    plan = db.session.get(Plan, plan_id)

    if not plan:
        return jsonify({
            'error': 'Plan Not Found',
            'message': 'The requested plan does not exist'
        }), 404

    if plan.is_active:
        return jsonify({
            'error': 'Already Active',
            'message': 'This plan is already active'
        }), 400

    plan.is_active = True
    db.session.commit()

    # Audit log
    audit_log(
        action=AuditAction.UPDATE.value,
        resource_type='plan',
        resource_id=str(plan.id),
        old_values={'is_active': False},
        new_values={'is_active': True}
    )

    return jsonify({
        'message': 'Plan activated successfully',
        'plan': {
            'id': str(plan.id),
            'name': plan.name,
            'is_active': plan.is_active
        }
    }), 200


# Health check
@plans_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'admin-plans',
        'timestamp': datetime.utcnow().isoformat()
    }), 200
