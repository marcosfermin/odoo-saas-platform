#!/usr/bin/env python3
"""
Admin Dashboard - Audit Log API
Query and filter audit logs for compliance and security monitoring
"""

import os
import sys
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_current_user

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.models import AuditLog, Customer, AuditAction
from admin.app import db
from admin.app.utils.auth import require_admin

# Create blueprint
audit_bp = Blueprint('audit', __name__)


@audit_bp.route('/', methods=['GET'])
@require_admin
def list_audit_logs():
    """List audit logs with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)

    # Build query
    query = AuditLog.query

    # Filter by action
    action = request.args.get('action')
    if action:
        query = query.filter(AuditLog.action == action)

    # Filter by resource type
    resource_type = request.args.get('resource_type')
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)

    # Filter by resource ID
    resource_id = request.args.get('resource_id')
    if resource_id:
        query = query.filter(AuditLog.resource_id == resource_id)

    # Filter by actor
    actor_id = request.args.get('actor_id')
    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)

    actor_email = request.args.get('actor_email')
    if actor_email:
        query = query.filter(AuditLog.actor_email.ilike(f'%{actor_email}%'))

    # Filter by IP address
    ip_address = request.args.get('ip_address')
    if ip_address:
        query = query.filter(AuditLog.ip_address == ip_address)

    # Filter by date range
    start_date = request.args.get('start_date')
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(AuditLog.created_at >= start_dt)
        except ValueError:
            pass

    end_date = request.args.get('end_date')
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(AuditLog.created_at <= end_dt)
        except ValueError:
            pass

    # Order by (always by timestamp for audit logs)
    order_dir = request.args.get('order_dir', 'desc')
    if order_dir == 'asc':
        query = query.order_by(AuditLog.created_at.asc())
    else:
        query = query.order_by(AuditLog.created_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    logs = []
    for log in pagination.items:
        log_data = {
            'id': str(log.id),
            'actor_id': str(log.actor_id) if log.actor_id else None,
            'actor_email': log.actor_email,
            'actor_role': log.actor_role,
            'action': log.action,
            'resource_type': log.resource_type,
            'resource_id': log.resource_id,
            'ip_address': log.ip_address,
            'user_agent': log.user_agent,
            'old_values': log.old_values,
            'new_values': log.new_values,
            'metadata': log.metadata,
            'created_at': log.created_at.isoformat() if log.created_at else None
        }
        logs.append(log_data)

    return jsonify({
        'audit_logs': logs,
        'pagination': {
            'page': page,
            'pages': pagination.pages,
            'per_page': per_page,
            'total': pagination.total,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200


@audit_bp.route('/<log_id>', methods=['GET'])
@require_admin
def get_audit_log(log_id):
    """Get single audit log entry"""
    log = AuditLog.query.get(log_id)

    if not log:
        return jsonify({
            'error': 'Audit Log Not Found',
            'message': 'The requested audit log does not exist'
        }), 404

    log_data = {
        'id': str(log.id),
        'actor_id': str(log.actor_id) if log.actor_id else None,
        'actor_email': log.actor_email,
        'actor_role': log.actor_role,
        'action': log.action,
        'resource_type': log.resource_type,
        'resource_id': log.resource_id,
        'ip_address': log.ip_address,
        'user_agent': log.user_agent,
        'session_id': log.session_id,
        'old_values': log.old_values,
        'new_values': log.new_values,
        'metadata': log.metadata,
        'payload_hash': log.payload_hash,
        'created_at': log.created_at.isoformat() if log.created_at else None
    }

    # Include actor details if available
    if log.actor_id:
        actor = Customer.query.get(log.actor_id)
        if actor:
            log_data['actor'] = {
                'id': str(actor.id),
                'email': actor.email,
                'first_name': actor.first_name,
                'last_name': actor.last_name
            }

    return jsonify({'audit_log': log_data}), 200


@audit_bp.route('/actions', methods=['GET'])
@require_admin
def list_actions():
    """List all available audit actions"""
    actions = [{'value': a.value, 'name': a.name} for a in AuditAction]
    return jsonify({'actions': actions}), 200


@audit_bp.route('/resource-types', methods=['GET'])
@require_admin
def list_resource_types():
    """List all resource types that have been audited"""
    result = db.session.query(AuditLog.resource_type).distinct().all()
    resource_types = [r[0] for r in result if r[0]]
    return jsonify({'resource_types': sorted(resource_types)}), 200


@audit_bp.route('/stats', methods=['GET'])
@require_admin
def get_audit_stats():
    """Get audit log statistics"""
    # Time ranges
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    # Total counts
    total_logs = AuditLog.query.count()
    logs_24h = AuditLog.query.filter(AuditLog.created_at >= last_24h).count()
    logs_7d = AuditLog.query.filter(AuditLog.created_at >= last_7d).count()
    logs_30d = AuditLog.query.filter(AuditLog.created_at >= last_30d).count()

    # Actions breakdown (last 30 days)
    action_stats = db.session.query(
        AuditLog.action,
        db.func.count(AuditLog.id)
    ).filter(
        AuditLog.created_at >= last_30d
    ).group_by(AuditLog.action).all()

    # Resource type breakdown (last 30 days)
    resource_stats = db.session.query(
        AuditLog.resource_type,
        db.func.count(AuditLog.id)
    ).filter(
        AuditLog.created_at >= last_30d
    ).group_by(AuditLog.resource_type).all()

    # Top actors (last 30 days)
    actor_stats = db.session.query(
        AuditLog.actor_email,
        db.func.count(AuditLog.id)
    ).filter(
        AuditLog.created_at >= last_30d,
        AuditLog.actor_email.isnot(None)
    ).group_by(AuditLog.actor_email).order_by(
        db.func.count(AuditLog.id).desc()
    ).limit(10).all()

    # Unique IPs (last 24 hours)
    unique_ips_24h = db.session.query(
        db.func.count(db.func.distinct(AuditLog.ip_address))
    ).filter(
        AuditLog.created_at >= last_24h
    ).scalar()

    # Security-related actions (last 24 hours)
    security_actions = ['login', 'logout', 'impersonate']
    security_events_24h = AuditLog.query.filter(
        AuditLog.created_at >= last_24h,
        AuditLog.action.in_(security_actions)
    ).count()

    return jsonify({
        'statistics': {
            'total_logs': total_logs,
            'logs_last_24h': logs_24h,
            'logs_last_7d': logs_7d,
            'logs_last_30d': logs_30d,
            'unique_ips_24h': unique_ips_24h or 0,
            'security_events_24h': security_events_24h,
            'actions_breakdown': {action: count for action, count in action_stats},
            'resource_types_breakdown': {rt: count for rt, count in resource_stats if rt},
            'top_actors': [
                {'email': email, 'action_count': count}
                for email, count in actor_stats
            ]
        }
    }), 200


@audit_bp.route('/export', methods=['GET'])
@require_admin
def export_audit_logs():
    """Export audit logs as JSON (for compliance reports)"""
    # Get date range (required for export)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        return jsonify({
            'error': 'Missing Date Range',
            'message': 'Both start_date and end_date are required for export'
        }), 400

    try:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError:
        return jsonify({
            'error': 'Invalid Date Format',
            'message': 'Dates must be in ISO format'
        }), 400

    # Limit export range to 90 days
    if (end_dt - start_dt).days > 90:
        return jsonify({
            'error': 'Range Too Large',
            'message': 'Export range cannot exceed 90 days'
        }), 400

    # Query logs
    query = AuditLog.query.filter(
        AuditLog.created_at >= start_dt,
        AuditLog.created_at <= end_dt
    ).order_by(AuditLog.created_at.asc())

    # Apply filters
    action = request.args.get('action')
    if action:
        query = query.filter(AuditLog.action == action)

    resource_type = request.args.get('resource_type')
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)

    logs = query.all()

    export_data = {
        'export_metadata': {
            'generated_at': datetime.utcnow().isoformat(),
            'start_date': start_dt.isoformat(),
            'end_date': end_dt.isoformat(),
            'total_records': len(logs),
            'filters': {
                'action': action,
                'resource_type': resource_type
            }
        },
        'audit_logs': []
    }

    for log in logs:
        log_data = {
            'id': str(log.id),
            'actor_id': str(log.actor_id) if log.actor_id else None,
            'actor_email': log.actor_email,
            'actor_role': log.actor_role,
            'action': log.action,
            'resource_type': log.resource_type,
            'resource_id': log.resource_id,
            'ip_address': log.ip_address,
            'user_agent': log.user_agent,
            'old_values': log.old_values,
            'new_values': log.new_values,
            'metadata': log.metadata,
            'payload_hash': log.payload_hash,
            'created_at': log.created_at.isoformat() if log.created_at else None
        }
        export_data['audit_logs'].append(log_data)

    return jsonify(export_data), 200


@audit_bp.route('/verify/<log_id>', methods=['GET'])
@require_admin
def verify_audit_log(log_id):
    """Verify audit log integrity (check payload hash)"""
    log = AuditLog.query.get(log_id)

    if not log:
        return jsonify({
            'error': 'Audit Log Not Found',
            'message': 'The requested audit log does not exist'
        }), 404

    # Recalculate hash
    import hashlib
    import json

    payload = {
        'actor_id': str(log.actor_id) if log.actor_id else None,
        'action': log.action,
        'resource_type': log.resource_type,
        'resource_id': log.resource_id,
        'old_values': log.old_values,
        'new_values': log.new_values,
        'created_at': log.created_at.isoformat() if log.created_at else None
    }
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    calculated_hash = hashlib.sha256(payload_json.encode()).hexdigest()

    is_valid = calculated_hash == log.payload_hash

    return jsonify({
        'log_id': str(log.id),
        'stored_hash': log.payload_hash,
        'calculated_hash': calculated_hash,
        'is_valid': is_valid,
        'verified_at': datetime.utcnow().isoformat()
    }), 200


# Health check
@audit_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'admin-audit',
        'timestamp': datetime.utcnow().isoformat()
    }), 200
