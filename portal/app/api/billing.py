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
    plans = db.session.query(Plan).filter_by(is_active=True).order_by(Plan.price_monthly).all()
    
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
    
    subscriptions = db.session.query(Subscription).filter_by(
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
    
    subscription = db.session.query(Subscription).filter_by(
        id=subscription_id,
        customer_id=current_customer.id
    ).first()
    
    if not subscription:
        return jsonify({
            'error': 'Subscription Not Found',
            'message': 'The requested subscription does not exist or you do not have access to it'
        }), 404
    
    # Get recent payment events
    recent_payments = db.session.query(PaymentEvent).filter_by(
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
    plan = db.session.get(Plan, plan_id)
    if not plan or not plan.is_active:
        return jsonify({
            'error': 'Invalid Plan',
            'message': 'The selected plan is not available'
        }), 400
    
    # Create Stripe checkout session
    try:
        import stripe
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY') or os.getenv('STRIPE_SECRET_KEY')

        if not stripe.api_key:
            return jsonify({
                'error': 'Configuration Error',
                'message': 'Stripe is not configured'
            }), 500

        # Get or create Stripe customer
        if not current_customer.stripe_customer_id:
            stripe_customer = stripe.Customer.create(
                email=current_customer.email,
                name=f"{current_customer.first_name} {current_customer.last_name}",
                metadata={
                    'customer_id': str(current_customer.id),
                    'company': current_customer.company or ''
                }
            )
            current_customer.stripe_customer_id = stripe_customer.id
            db.session.commit()

        # Determine price ID based on interval
        if billing_interval == 'yearly':
            price_id = plan.stripe_price_id_yearly
            if not price_id:
                return jsonify({
                    'error': 'Plan Not Available',
                    'message': 'Yearly billing is not available for this plan'
                }), 400
        else:
            price_id = plan.stripe_price_id_monthly
            if not price_id:
                return jsonify({
                    'error': 'Plan Not Available',
                    'message': 'Monthly billing is not available for this plan'
                }), 400

        # Create checkout session
        success_url = os.getenv('PORTAL_URL', 'http://localhost:5001') + '/billing/success?session_id={CHECKOUT_SESSION_ID}'
        cancel_url = os.getenv('PORTAL_URL', 'http://localhost:5001') + '/billing/cancel'

        session = stripe.checkout.Session.create(
            customer=current_customer.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'customer_id': str(current_customer.id),
                'plan_id': str(plan.id),
                'interval': billing_interval
            },
            subscription_data={
                'trial_period_days': plan.trial_days if plan.trial_days else None,
                'metadata': {
                    'customer_id': str(current_customer.id),
                    'plan_id': str(plan.id)
                }
            }
        )

        current_app.logger.info(
            f"Stripe checkout session created for {current_customer.email}: {session.id}"
        )

        return jsonify({
            'checkout_url': session.url,
            'session_id': session.id,
            'plan': {
                'id': str(plan.id),
                'name': plan.name,
                'interval': billing_interval
            }
        }), 200

    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        return jsonify({
            'error': 'Stripe Error',
            'message': str(e.user_message) if hasattr(e, 'user_message') else 'Payment processing failed'
        }), 400
    except Exception as e:
        current_app.logger.error(f"Checkout session creation failed: {e}")
        return jsonify({
            'error': 'Checkout Failed',
            'message': 'Failed to create checkout session'
        }), 500

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
    plan = db.session.get(Plan, plan_id)
    if not plan or not plan.is_active:
        return jsonify({
            'error': 'Invalid Plan',
            'message': 'The selected plan is not available'
        }), 400
    
    # Create Paddle checkout
    try:
        paddle_vendor_id = current_app.config.get('PADDLE_VENDOR_ID') or os.getenv('PADDLE_VENDOR_ID')
        paddle_api_key = current_app.config.get('PADDLE_API_KEY') or os.getenv('PADDLE_API_KEY')

        if not paddle_vendor_id or not paddle_api_key:
            return jsonify({
                'error': 'Configuration Error',
                'message': 'Paddle is not configured'
            }), 500

        if not plan.paddle_plan_id:
            return jsonify({
                'error': 'Plan Not Available',
                'message': 'This plan is not available for Paddle checkout'
            }), 400

        # Get billing interval from request
        billing_interval = data.get('interval', 'monthly')

        # Build Paddle checkout URL
        # For Paddle Billing (v2), we generate a client-side checkout
        portal_url = os.getenv('PORTAL_URL', 'http://localhost:5001')
        success_url = f"{portal_url}/billing/success"

        # Paddle checkout payload for client-side initialization
        checkout_data = {
            'vendor_id': int(paddle_vendor_id),
            'product_id': plan.paddle_plan_id,
            'customer_email': current_customer.email,
            'customer_country': 'US',  # Default, can be customized
            'passthrough': {
                'customer_id': str(current_customer.id),
                'plan_id': str(plan.id),
                'interval': billing_interval
            },
            'success_url': success_url,
            'title': f'{plan.name} Subscription',
            'message': plan.description or f'Subscribe to {plan.name}',
            'custom_data': {
                'customer_id': str(current_customer.id),
                'plan_id': str(plan.id)
            }
        }

        # Store Paddle customer ID if not already stored
        if not current_customer.paddle_customer_id:
            current_customer.paddle_customer_id = f"paddle_{current_customer.id}"
            db.session.commit()

        current_app.logger.info(
            f"Paddle checkout data generated for {current_customer.email}"
        )

        return jsonify({
            'checkout_type': 'paddle',
            'checkout_data': checkout_data,
            'vendor_id': int(paddle_vendor_id),
            'product_id': plan.paddle_plan_id,
            'customer_email': current_customer.email,
            'plan': {
                'id': str(plan.id),
                'name': plan.name,
                'paddle_plan_id': plan.paddle_plan_id
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"Paddle checkout creation failed: {e}")
        return jsonify({
            'error': 'Checkout Failed',
            'message': 'Failed to create Paddle checkout'
        }), 500

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
    
    # Retrieve payment methods from Stripe
    payment_methods = []

    try:
        import stripe
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY') or os.getenv('STRIPE_SECRET_KEY')

        if stripe.api_key and current_customer.stripe_customer_id:
            # Get payment methods from Stripe
            stripe_methods = stripe.PaymentMethod.list(
                customer=current_customer.stripe_customer_id,
                type='card'
            )

            for method in stripe_methods.data:
                card = method.card
                payment_methods.append({
                    'id': method.id,
                    'provider': 'stripe',
                    'type': 'card',
                    'brand': card.brand,
                    'last4': card.last4,
                    'exp_month': card.exp_month,
                    'exp_year': card.exp_year,
                    'is_default': method.id == stripe_methods.data[0].id if stripe_methods.data else False
                })

    except Exception as e:
        current_app.logger.warning(f"Failed to retrieve Stripe payment methods: {e}")

    return jsonify({
        'payment_methods': payment_methods
    }), 200

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
    
    subscription = db.session.query(Subscription).filter_by(
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

    # Cancel subscription with billing provider
    try:
        if subscription.provider == 'stripe':
            import stripe
            stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY') or os.getenv('STRIPE_SECRET_KEY')

            if not stripe.api_key:
                return jsonify({
                    'error': 'Configuration Error',
                    'message': 'Stripe is not configured'
                }), 500

            # Cancel at period end (grace period) or immediately based on request
            cancel_immediately = data.get('cancel_immediately', False)

            if cancel_immediately:
                stripe.Subscription.delete(subscription.external_id)
                subscription.status = 'canceled'
                subscription.ended_at = datetime.utcnow()
            else:
                stripe.Subscription.modify(
                    subscription.external_id,
                    cancel_at_period_end=True
                )
                subscription.status = 'canceled'

            subscription.canceled_at = datetime.utcnow()
            db.session.commit()

            current_app.logger.info(
                f"Stripe subscription canceled: {subscription.external_id} by {current_customer.email}"
            )

        elif subscription.provider == 'paddle':
            # For Paddle, we need to use their API
            import requests

            paddle_vendor_id = os.getenv('PADDLE_VENDOR_ID')
            paddle_api_key = os.getenv('PADDLE_API_KEY')

            if paddle_vendor_id and paddle_api_key:
                response = requests.post(
                    'https://vendors.paddle.com/api/2.0/subscription/users_cancel',
                    data={
                        'vendor_id': paddle_vendor_id,
                        'vendor_auth_code': paddle_api_key,
                        'subscription_id': subscription.external_id
                    }
                )

                if response.status_code == 200:
                    subscription.status = 'canceled'
                    subscription.canceled_at = datetime.utcnow()
                    db.session.commit()

                    current_app.logger.info(
                        f"Paddle subscription canceled: {subscription.external_id}"
                    )
                else:
                    current_app.logger.error(f"Paddle cancellation failed: {response.text}")
                    return jsonify({
                        'error': 'Cancellation Failed',
                        'message': 'Failed to cancel subscription with Paddle'
                    }), 500

        return jsonify({
            'message': 'Subscription canceled successfully',
            'subscription': {
                'id': str(subscription.id),
                'status': subscription.status,
                'canceled_at': subscription.canceled_at.isoformat() if subscription.canceled_at else None
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"Subscription cancellation failed: {e}")
        return jsonify({
            'error': 'Cancellation Failed',
            'message': 'Failed to cancel subscription'
        }), 500

@billing_bp.route('/usage', methods=['GET'])
@jwt_required()
def get_usage():
    """Get current billing period usage"""
    from shared.models import Tenant

    current_customer = get_current_user()

    # Calculate usage across all tenants
    tenants = db.session.query(Tenant).filter_by(customer_id=current_customer.id).all()

    total_users = sum(t.current_users for t in tenants)
    total_db_size = sum(t.db_size_bytes for t in tenants)
    total_filestore_size = sum(t.filestore_size_bytes for t in tenants)
    total_storage = total_db_size + total_filestore_size

    # Get active tenants count
    active_tenants = sum(1 for t in tenants if t.state == 'active')

    # Get subscription info for quotas
    active_subscription = db.session.query(Subscription).filter_by(
        customer_id=current_customer.id,
        status='active'
    ).first()

    # Calculate quota usage percentages
    max_tenants = current_customer.max_tenants
    max_quota_gb = current_customer.max_quota_gb

    usage_data = {
        'tenants': {
            'count': len(tenants),
            'active': active_tenants,
            'limit': max_tenants,
            'usage_percent': round((len(tenants) / max_tenants) * 100, 1) if max_tenants else 0
        },
        'users': {
            'total': total_users
        },
        'storage': {
            'db_size_mb': round(total_db_size / (1024 * 1024), 2),
            'filestore_size_mb': round(total_filestore_size / (1024 * 1024), 2),
            'total_size_gb': round(total_storage / (1024**3), 2),
            'limit_gb': max_quota_gb,
            'usage_percent': round((total_storage / (max_quota_gb * 1024**3)) * 100, 1) if max_quota_gb else 0
        },
        'by_tenant': []
    }

    # Add per-tenant breakdown
    for tenant in tenants:
        tenant_storage = tenant.db_size_bytes + tenant.filestore_size_bytes
        usage_data['by_tenant'].append({
            'id': str(tenant.id),
            'slug': tenant.slug,
            'name': tenant.name,
            'state': tenant.state,
            'users': tenant.current_users,
            'storage_mb': round(tenant_storage / (1024 * 1024), 2)
        })

    # Add subscription info if available
    if active_subscription:
        usage_data['subscription'] = {
            'id': str(active_subscription.id),
            'status': active_subscription.status,
            'current_period_end': active_subscription.current_period_end.isoformat() if active_subscription.current_period_end else None,
            'plan': {
                'id': str(active_subscription.plan.id),
                'name': active_subscription.plan.name
            } if active_subscription.plan else None
        }

    return jsonify({
        'usage': usage_data,
        'generated_at': datetime.utcnow().isoformat()
    }), 200

# Health check
@billing_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'portal-billing',
        'timestamp': datetime.utcnow().isoformat()
    }), 200