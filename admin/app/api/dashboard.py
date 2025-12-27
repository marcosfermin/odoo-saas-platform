#!/usr/bin/env python3
"""
Admin Dashboard - Dashboard Statistics API
Provides platform-wide statistics and metrics for the admin dashboard
"""

import os
import sys
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import func

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.models import (
    Customer, Tenant, Plan, Subscription, PaymentEvent,
    AuditLog, SupportTicket, TenantState, CustomerRole
)
from admin.app import db
from admin.app.utils.auth import require_admin

# Create blueprint
dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/stats', methods=['GET'])
@require_admin
def get_dashboard_stats():
    """Get comprehensive dashboard statistics"""
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    # Customer statistics
    total_customers = Customer.query.count()
    active_customers = Customer.query.filter(Customer.is_active == True).count()
    new_customers_24h = Customer.query.filter(Customer.created_at >= last_24h).count()
    new_customers_7d = Customer.query.filter(Customer.created_at >= last_7d).count()
    new_customers_30d = Customer.query.filter(Customer.created_at >= last_30d).count()

    # Tenant statistics
    total_tenants = Tenant.query.count()
    active_tenants = Tenant.query.filter(Tenant.state == TenantState.ACTIVE.value).count()
    suspended_tenants = Tenant.query.filter(Tenant.state == TenantState.SUSPENDED.value).count()
    creating_tenants = Tenant.query.filter(Tenant.state == TenantState.CREATING.value).count()
    error_tenants = Tenant.query.filter(Tenant.state == TenantState.ERROR.value).count()
    new_tenants_24h = Tenant.query.filter(Tenant.created_at >= last_24h).count()
    new_tenants_7d = Tenant.query.filter(Tenant.created_at >= last_7d).count()

    # Subscription statistics
    total_subscriptions = Subscription.query.count()
    active_subscriptions = Subscription.query.filter(Subscription.status == 'active').count()
    trialing_subscriptions = Subscription.query.filter(Subscription.status == 'trialing').count()
    canceled_subscriptions_30d = Subscription.query.filter(
        Subscription.canceled_at >= last_30d
    ).count()

    # Revenue statistics (last 30 days)
    revenue_30d = db.session.query(
        func.sum(PaymentEvent.amount)
    ).filter(
        PaymentEvent.created_at >= last_30d,
        PaymentEvent.status == 'succeeded'
    ).scalar() or 0

    # Plan distribution
    plan_distribution = db.session.query(
        Plan.name,
        func.count(Tenant.id)
    ).join(Tenant).group_by(Plan.name).all()

    # Storage usage
    total_db_size = db.session.query(func.sum(Tenant.db_size_bytes)).scalar() or 0
    total_filestore_size = db.session.query(func.sum(Tenant.filestore_size_bytes)).scalar() or 0

    # Support tickets
    open_tickets = SupportTicket.query.filter(
        SupportTicket.status.in_(['open', 'in_progress'])
    ).count()
    urgent_tickets = SupportTicket.query.filter(
        SupportTicket.status.in_(['open', 'in_progress']),
        SupportTicket.priority == 'urgent'
    ).count()

    # Recent activity (audit logs)
    recent_logins = AuditLog.query.filter(
        AuditLog.action == 'login',
        AuditLog.created_at >= last_24h
    ).count()

    return jsonify({
        'statistics': {
            'customers': {
                'total': total_customers,
                'active': active_customers,
                'inactive': total_customers - active_customers,
                'new_24h': new_customers_24h,
                'new_7d': new_customers_7d,
                'new_30d': new_customers_30d
            },
            'tenants': {
                'total': total_tenants,
                'active': active_tenants,
                'suspended': suspended_tenants,
                'creating': creating_tenants,
                'error': error_tenants,
                'new_24h': new_tenants_24h,
                'new_7d': new_tenants_7d
            },
            'subscriptions': {
                'total': total_subscriptions,
                'active': active_subscriptions,
                'trialing': trialing_subscriptions,
                'canceled_30d': canceled_subscriptions_30d
            },
            'revenue': {
                'last_30d': float(revenue_30d),
                'currency': 'USD'
            },
            'storage': {
                'total_db_size_gb': round(total_db_size / (1024**3), 2),
                'total_filestore_size_gb': round(total_filestore_size / (1024**3), 2),
                'total_size_gb': round((total_db_size + total_filestore_size) / (1024**3), 2)
            },
            'support': {
                'open_tickets': open_tickets,
                'urgent_tickets': urgent_tickets
            },
            'activity': {
                'logins_24h': recent_logins
            },
            'plan_distribution': {
                name: count for name, count in plan_distribution
            }
        },
        'generated_at': now.isoformat()
    }), 200


@dashboard_bp.route('/charts/tenants', methods=['GET'])
@require_admin
def get_tenant_chart_data():
    """Get tenant creation trend data for charts"""
    days = request.args.get('days', 30, type=int)
    days = min(days, 90)  # Limit to 90 days

    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # Get daily tenant creation counts
    daily_counts = db.session.query(
        func.date(Tenant.created_at).label('date'),
        func.count(Tenant.id).label('count')
    ).filter(
        Tenant.created_at >= start_date
    ).group_by(
        func.date(Tenant.created_at)
    ).order_by(
        func.date(Tenant.created_at)
    ).all()

    # Format data
    chart_data = []
    for date, count in daily_counts:
        chart_data.append({
            'date': date.isoformat() if date else None,
            'count': count
        })

    return jsonify({
        'chart_data': chart_data,
        'period_days': days
    }), 200


@dashboard_bp.route('/charts/revenue', methods=['GET'])
@require_admin
def get_revenue_chart_data():
    """Get revenue trend data for charts"""
    days = request.args.get('days', 30, type=int)
    days = min(days, 90)

    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # Get daily revenue
    daily_revenue = db.session.query(
        func.date(PaymentEvent.created_at).label('date'),
        func.sum(PaymentEvent.amount).label('amount')
    ).filter(
        PaymentEvent.created_at >= start_date,
        PaymentEvent.status == 'succeeded'
    ).group_by(
        func.date(PaymentEvent.created_at)
    ).order_by(
        func.date(PaymentEvent.created_at)
    ).all()

    chart_data = []
    for date, amount in daily_revenue:
        chart_data.append({
            'date': date.isoformat() if date else None,
            'amount': float(amount) if amount else 0
        })

    return jsonify({
        'chart_data': chart_data,
        'period_days': days,
        'currency': 'USD'
    }), 200


@dashboard_bp.route('/charts/subscriptions', methods=['GET'])
@require_admin
def get_subscription_chart_data():
    """Get subscription status distribution"""
    status_counts = db.session.query(
        Subscription.status,
        func.count(Subscription.id)
    ).group_by(Subscription.status).all()

    return jsonify({
        'chart_data': {status: count for status, count in status_counts}
    }), 200


@dashboard_bp.route('/recent-activity', methods=['GET'])
@require_admin
def get_recent_activity():
    """Get recent platform activity"""
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 100)

    # Get recent audit logs
    recent_logs = AuditLog.query.order_by(
        AuditLog.created_at.desc()
    ).limit(limit).all()

    activities = []
    for log in recent_logs:
        activities.append({
            'id': str(log.id),
            'action': log.action,
            'resource_type': log.resource_type,
            'resource_id': log.resource_id,
            'actor_email': log.actor_email,
            'ip_address': log.ip_address,
            'created_at': log.created_at.isoformat() if log.created_at else None
        })

    return jsonify({'activities': activities}), 200


@dashboard_bp.route('/alerts', methods=['GET'])
@require_admin
def get_system_alerts():
    """Get current system alerts and warnings"""
    alerts = []

    # Check for error tenants
    error_count = Tenant.query.filter(Tenant.state == TenantState.ERROR.value).count()
    if error_count > 0:
        alerts.append({
            'type': 'error',
            'title': 'Tenant Errors',
            'message': f'{error_count} tenant(s) in error state',
            'action_url': '/admin/tenants?state=error'
        })

    # Check for stuck creating tenants (>1 hour old)
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    stuck_creating = Tenant.query.filter(
        Tenant.state == TenantState.CREATING.value,
        Tenant.created_at < one_hour_ago
    ).count()
    if stuck_creating > 0:
        alerts.append({
            'type': 'warning',
            'title': 'Stuck Provisioning',
            'message': f'{stuck_creating} tenant(s) stuck in creating state',
            'action_url': '/admin/tenants?state=creating'
        })

    # Check for urgent support tickets
    urgent_tickets = SupportTicket.query.filter(
        SupportTicket.status.in_(['open', 'in_progress']),
        SupportTicket.priority == 'urgent'
    ).count()
    if urgent_tickets > 0:
        alerts.append({
            'type': 'warning',
            'title': 'Urgent Tickets',
            'message': f'{urgent_tickets} urgent support ticket(s)',
            'action_url': '/admin/support?priority=urgent'
        })

    # Check for failed payments (last 24 hours)
    last_24h = datetime.utcnow() - timedelta(hours=24)
    failed_payments = PaymentEvent.query.filter(
        PaymentEvent.created_at >= last_24h,
        PaymentEvent.status == 'failed'
    ).count()
    if failed_payments > 0:
        alerts.append({
            'type': 'warning',
            'title': 'Failed Payments',
            'message': f'{failed_payments} failed payment(s) in last 24 hours',
            'action_url': '/admin/billing?status=failed'
        })

    # Check for expiring trials (next 3 days)
    three_days = datetime.utcnow() + timedelta(days=3)
    expiring_trials = Subscription.query.filter(
        Subscription.status == 'trialing',
        Subscription.trial_end <= three_days,
        Subscription.trial_end > datetime.utcnow()
    ).count()
    if expiring_trials > 0:
        alerts.append({
            'type': 'info',
            'title': 'Expiring Trials',
            'message': f'{expiring_trials} trial(s) expiring in next 3 days',
            'action_url': '/admin/subscriptions?status=trialing'
        })

    return jsonify({'alerts': alerts}), 200


@dashboard_bp.route('/top-customers', methods=['GET'])
@require_admin
def get_top_customers():
    """Get top customers by tenant count and usage"""
    limit = request.args.get('limit', 10, type=int)
    limit = min(limit, 50)

    # Top customers by tenant count
    top_by_tenants = db.session.query(
        Customer.id,
        Customer.email,
        Customer.company,
        func.count(Tenant.id).label('tenant_count')
    ).join(Tenant).filter(
        Tenant.state != TenantState.DELETED.value
    ).group_by(
        Customer.id, Customer.email, Customer.company
    ).order_by(
        func.count(Tenant.id).desc()
    ).limit(limit).all()

    # Top customers by storage usage
    top_by_storage = db.session.query(
        Customer.id,
        Customer.email,
        Customer.company,
        func.sum(Tenant.db_size_bytes + Tenant.filestore_size_bytes).label('total_storage')
    ).join(Tenant).group_by(
        Customer.id, Customer.email, Customer.company
    ).order_by(
        func.sum(Tenant.db_size_bytes + Tenant.filestore_size_bytes).desc()
    ).limit(limit).all()

    return jsonify({
        'top_by_tenants': [
            {
                'customer_id': str(c.id),
                'email': c.email,
                'company': c.company,
                'tenant_count': c.tenant_count
            }
            for c in top_by_tenants
        ],
        'top_by_storage': [
            {
                'customer_id': str(c.id),
                'email': c.email,
                'company': c.company,
                'storage_gb': round(c.total_storage / (1024**3), 2) if c.total_storage else 0
            }
            for c in top_by_storage
        ]
    }), 200


@dashboard_bp.route('/health-summary', methods=['GET'])
@require_admin
def get_health_summary():
    """Get overall platform health summary"""
    # Database connection check
    try:
        db.session.execute(db.text('SELECT 1'))
        db_healthy = True
    except Exception:
        db_healthy = False

    # Redis connection check
    try:
        from redis import Redis
        redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        redis_conn = Redis.from_url(redis_url)
        redis_conn.ping()
        redis_healthy = True
    except Exception:
        redis_healthy = False

    # Calculate overall health
    components = [
        ('database', db_healthy),
        ('redis', redis_healthy)
    ]

    healthy_count = sum(1 for _, healthy in components if healthy)
    overall_health = 'healthy' if healthy_count == len(components) else (
        'degraded' if healthy_count > 0 else 'unhealthy'
    )

    return jsonify({
        'overall_status': overall_health,
        'components': {name: 'healthy' if healthy else 'unhealthy' for name, healthy in components},
        'checked_at': datetime.utcnow().isoformat()
    }), 200


# Health check
@dashboard_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'admin-dashboard',
        'timestamp': datetime.utcnow().isoformat()
    }), 200
