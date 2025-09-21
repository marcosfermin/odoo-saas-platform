#!/usr/bin/env python3
"""
Customer Portal Billing API
Handles subscriptions, invoices, and payment management
"""

import os
import sys
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_current_user
from marshmallow import Schema, fields, validate, ValidationError

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.models import Plan, Subscription, PaymentEvent, Customer
from portal.app import db, limiter

# Create blueprint
billing_bp = Blueprint('billing', __name__)

def rate_limit_key():
    """Generate rate limiting key based on user"""
    user = get_current_user()
    if user:
        return f"user:{user.id}"
    return f"ip:{request.remote_addr}"

@billing_bp.route('/plans', methods=['GET'])
def list_plans():
    """List available billing plans"""
    # Get active plans
    plans = Plan.query.filter_by(is_active=True).order_by(Plan.price_monthly).all()
    
    plan_data = []
    for plan in plans:
        plan_info = {
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
            'features': plan.features or {},
            'trial_days': plan.trial_days
        }
        
        # Calculate savings for yearly plans
        if plan.price_monthly and plan.price_yearly:
            monthly_total = float(plan.price_monthly) * 12
            yearly_price = float(plan.price_yearly)
            if yearly_price < monthly_total:
                plan_info['yearly_savings'] = round(monthly_total - yearly_price, 2)
                plan_info['yearly_savings_percent'] = round(((monthly_total - yearly_price) / monthly_total) * 100, 1)
        
        plan_data.append(plan_info)
    
    return jsonify({
        'plans': plan_data
    }), 200

@billing_bp.route('/subscriptions', methods=['GET'])
@jwt_required()
def list_subscriptions():
    """List customer subscriptions"""
    current_customer = get_current_user()
    
    subscriptions = Subscription.query.filter_by(
        customer_id=current_customer.id
    ).order_by(Subscription.created_at.desc()).all()
    
    subscription_data = []
    for sub in subscriptions:
        sub_info = {
            'id': str(sub.id),
            'status': sub.status,
            'provider': sub.provider,
            'amount': float(sub.amount) if sub.amount else None,
            'currency': sub.currency,
            'interval': sub.interval,
            'current_period_start': sub.current_period_start.isoformat() if sub.current_period_start else None,
            'current_period_end': sub.current_period_end.isoformat() if sub.current_period_end else None,
            'trial_end': sub.trial_end.isoformat() if sub.trial_end else None,
            'canceled_at': sub.canceled_at.isoformat() if sub.canceled_at else None,
            'created_at': sub.created_at.isoformat(),
            'plan': {
                'id': str(sub.plan.id),
                'name': sub.plan.name,
                'description': sub.plan.description
            } if sub.plan else None
        }
        subscription_data.append(sub_info)
    
    return jsonify({
        'subscriptions': subscription_data
    }), 200

@billing_bp.route('/subscriptions/<subscription_id>', methods=['GET'])
@jwt_required()
def get_subscription(subscription_id):
    """Get subscription details"""
    current_customer = get_current_user()
    
    subscription = Subscription.query.filter_by(
        id=subscription_id,
        customer_id=current_customer.id
    ).first()
    
    if not subscription:
        return jsonify({
            'error': 'Subscription Not Found',
            'message': 'The requested subscription does not exist or you do not have access to it'
        }), 404
    
    # Get recent payment events
    recent_payments = PaymentEvent.query.filter_by(
        subscription_id=subscription.id
    ).order_by(PaymentEvent.created_at.desc()).limit(10).all()
    
    payment_data = []
    for payment in recent_payments:
        payment_data.append({
            'id': str(payment.id),
            'event_type': payment.event_type,
            'status': payment.status,
            'amount': float(payment.amount) if payment.amount else None,
            'currency': payment.currency,
            'created_at': payment.created_at.isoformat(),
            'processed_at': payment.processed_at.isoformat() if payment.processed_at else None
        })
    
    subscription_data = {
        'id': str(subscription.id),
        'status': subscription.status,
        'provider': subscription.provider,
        'external_id': subscription.external_id,
        'amount': float(subscription.amount) if subscription.amount else None,
        'currency': subscription.currency,
        'interval': subscription.interval,
        'current_period_start': subscription.current_period_start.isoformat() if subscription.current_period_start else None,
        'current_period_end': subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        'trial_end': subscription.trial_end.isoformat() if subscription.trial_end else None,
        'canceled_at': subscription.canceled_at.isoformat() if subscription.canceled_at else None,
        'ended_at': subscription.ended_at.isoformat() if subscription.ended_at else None,
        'created_at': subscription.created_at.isoformat(),
        'plan': {
            'id': str(subscription.plan.id),
            'name': subscription.plan.name,
            'description': subscription.plan.description,
            'features': subscription.plan.features
        } if subscription.plan else None,
        'recent_payments': payment_data
    }
    
    return jsonify({
        'subscription': subscription_data
    }), 200

@billing_bp.route('/create-checkout-session', methods=['POST'])
@jwt_required()
@limiter.limit("10 per hour", key_func=rate_limit_key)
def create_checkout_session():
    """Create Stripe checkout session"""
    try:
        data = request.get_json() or {}
        plan_id = data.get('plan_id')
        billing_interval = data.get('interval', 'monthly')  # monthly or yearly
        
        if not plan_id:
            return jsonify({
                'error': 'Missing Plan',
                'message': 'plan_id is required'
            }), 400
            
    except Exception as err:
        return jsonify({
            'error': 'Invalid Request',
            'message': 'Invalid request data'
        }), 400
    
    current_customer = get_current_user()
    
    # Get plan
    plan = Plan.query.get(plan_id)
    if not plan or not plan.is_active:
        return jsonify({
            'error': 'Invalid Plan',
            'message': 'The selected plan is not available'
        }), 400
    
    # TODO: Create Stripe checkout session
    # This would integrate with Stripe API to create a checkout session
    
    return jsonify({
        'message': 'Stripe checkout not yet implemented',
        'todo': 'Implement Stripe checkout session creation',
        'plan': {
            'id': str(plan.id),
            'name': plan.name,
            'price_monthly': float(plan.price_monthly) if plan.price_monthly else None,
            'price_yearly': float(plan.price_yearly) if plan.price_yearly else None
        }
    }), 501

@billing_bp.route('/create-paddle-checkout', methods=['POST'])
@jwt_required()
@limiter.limit("10 per hour", key_func=rate_limit_key)
def create_paddle_checkout():
    """Create Paddle checkout"""
    try:
        data = request.get_json() or {}
        plan_id = data.get('plan_id')
        
        if not plan_id:
            return jsonify({
                'error': 'Missing Plan',
                'message': 'plan_id is required'
            }), 400
            
    except Exception as err:
        return jsonify({
            'error': 'Invalid Request',
            'message': 'Invalid request data'
        }), 400
    
    current_customer = get_current_user()
    
    # Get plan
    plan = Plan.query.get(plan_id)
    if not plan or not plan.is_active:
        return jsonify({
            'error': 'Invalid Plan',
            'message': 'The selected plan is not available'
        }), 400
    
    # TODO: Create Paddle checkout
    # This would integrate with Paddle API
    
    return jsonify({
        'message': 'Paddle checkout not yet implemented',
        'todo': 'Implement Paddle checkout creation',
        'plan': {
            'id': str(plan.id),
            'name': plan.name,
            'paddle_plan_id': plan.paddle_plan_id
        }
    }), 501

@billing_bp.route('/invoices', methods=['GET'])
@jwt_required()
def list_invoices():
    """List customer invoices"""
    current_customer = get_current_user()
    
    # Get payment events that represent invoices
    payment_events = PaymentEvent.query.join(Subscription).filter(
        Subscription.customer_id == current_customer.id,
        PaymentEvent.event_type.in_(['invoice.payment_succeeded', 'invoice.payment_failed', 'invoice.created'])
    ).order_by(PaymentEvent.created_at.desc()).limit(50).all()
    
    invoice_data = []
    for event in payment_events:
        invoice_info = {
            'id': str(event.id),
            'subscription_id': str(event.subscription_id) if event.subscription_id else None,
            'status': event.status,
            'amount': float(event.amount) if event.amount else None,
            'currency': event.currency,
            'event_type': event.event_type,
            'created_at': event.created_at.isoformat(),
            'processed_at': event.processed_at.isoformat() if event.processed_at else None,
            'provider': event.provider
        }
        invoice_data.append(invoice_info)
    
    return jsonify({
        'invoices': invoice_data
    }), 200

@billing_bp.route('/payment-methods', methods=['GET'])
@jwt_required()
def list_payment_methods():
    """List customer payment methods"""
    current_customer = get_current_user()
    
    # TODO: Retrieve payment methods from Stripe/Paddle
    
    return jsonify({
        'message': 'Payment methods retrieval not yet implemented',
        'todo': 'Implement payment method retrieval from billing providers',
        'payment_methods': []
    }), 501

@billing_bp.route('/cancel-subscription', methods=['POST'])
@jwt_required()
@limiter.limit("5 per hour", key_func=rate_limit_key)
def cancel_subscription():
    """Cancel subscription"""
    try:
        data = request.get_json() or {}
        subscription_id = data.get('subscription_id')
        
        if not subscription_id:
            return jsonify({
                'error': 'Missing Subscription',
                'message': 'subscription_id is required'
            }), 400
            
    except Exception as err:
        return jsonify({
            'error': 'Invalid Request',
            'message': 'Invalid request data'
        }), 400
    
    current_customer = get_current_user()
    
    subscription = Subscription.query.filter_by(
        id=subscription_id,
        customer_id=current_customer.id
    ).first()
    
    if not subscription:
        return jsonify({
            'error': 'Subscription Not Found',
            'message': 'The requested subscription does not exist or you do not have access to it'
        }), 404
    
    if subscription.status in ['canceled', 'ended']:
        return jsonify({
            'error': 'Already Canceled',
            'message': 'This subscription is already canceled'
        }), 400
    
    # TODO: Cancel subscription with billing provider
    # This would call Stripe or Paddle API to cancel the subscription
    
    current_app.logger.info(
        f"Subscription cancellation requested: {subscription.external_id} by {current_customer.email}"
    )
    
    return jsonify({
        'message': 'Subscription cancellation not yet implemented',
        'todo': 'Implement subscription cancellation with billing providers'
    }), 501

@billing_bp.route('/usage', methods=['GET'])
@jwt_required()
def get_usage():
    """Get current billing period usage"""
    current_customer = get_current_user()
    
    # TODO: Calculate usage across all tenants
    # This would aggregate usage from all customer tenants
    
    return jsonify({
        'message': 'Usage calculation not yet implemented',
        'todo': 'Implement usage aggregation across customer tenants',
        'usage': {
            'tenants_count': 0,
            'total_users': 0,
            'total_storage_gb': 0,
            'total_requests': 0
        }
    }), 501

# Health check
@billing_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'portal-billing',
        'timestamp': datetime.utcnow().isoformat()
    }), 200