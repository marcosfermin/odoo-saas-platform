#!/usr/bin/env python3
"""
Webhook Handlers for Billing Providers
Handles Stripe and Paddle webhooks for subscription events
"""

import os
import sys
import hmac
import hashlib
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.models import Subscription, PaymentEvent, Customer, Plan
from portal.app import db

# Create blueprint
webhooks_bp = Blueprint('webhooks', __name__)

def verify_stripe_signature(payload, signature, secret):
    """Verify Stripe webhook signature"""
    try:
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Stripe sends signature as "v1=<signature>"
        if signature.startswith('v1='):
            signature = signature[3:]
        
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        current_app.logger.error(f"Error verifying Stripe signature: {e}")
        return False

def verify_paddle_signature(payload, signature, public_key):
    """Verify Paddle webhook signature"""
    try:
        # TODO: Implement Paddle signature verification
        # This would use RSA public key verification
        current_app.logger.warning("Paddle signature verification not implemented")
        return True  # Skip verification for now
    except Exception as e:
        current_app.logger.error(f"Error verifying Paddle signature: {e}")
        return False

@webhooks_bp.route('/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks"""
    payload = request.get_data()
    signature = request.headers.get('Stripe-Signature')
    
    if not signature:
        current_app.logger.warning("Missing Stripe signature")
        return jsonify({'error': 'Missing signature'}), 400
    
    # Verify webhook signature
    webhook_secret = current_app.config.get('STRIPE_SIGNING_SECRET', '')
    if webhook_secret and not verify_stripe_signature(payload, signature, webhook_secret):
        current_app.logger.warning("Invalid Stripe signature")
        return jsonify({'error': 'Invalid signature'}), 400
    
    try:
        event = json.loads(payload.decode('utf-8'))
        event_type = event.get('type')
        event_id = event.get('id')
        
        current_app.logger.info(f"Received Stripe webhook: {event_type} ({event_id})")
        
        # Check if we've already processed this event
        existing_event = PaymentEvent.query.filter_by(
            provider='stripe',
            external_id=event_id
        ).first()
        
        if existing_event:
            current_app.logger.info(f"Event {event_id} already processed")
            return jsonify({'status': 'success'}), 200
        
        # Process different event types
        if event_type == 'customer.subscription.created':
            handle_stripe_subscription_created(event)
        elif event_type == 'customer.subscription.updated':
            handle_stripe_subscription_updated(event)
        elif event_type == 'customer.subscription.deleted':
            handle_stripe_subscription_deleted(event)
        elif event_type == 'invoice.payment_succeeded':
            handle_stripe_invoice_payment_succeeded(event)
        elif event_type == 'invoice.payment_failed':
            handle_stripe_invoice_payment_failed(event)
        elif event_type == 'customer.subscription.trial_will_end':
            handle_stripe_trial_will_end(event)
        else:
            current_app.logger.info(f"Unhandled Stripe event type: {event_type}")
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error processing Stripe webhook: {e}")
        return jsonify({'error': 'Processing failed'}), 500

@webhooks_bp.route('/paddle', methods=['POST'])
def paddle_webhook():
    """Handle Paddle webhooks"""
    payload = request.get_data()
    signature = request.headers.get('Paddle-Signature')
    
    try:
        # Paddle sends data as form-encoded
        data = request.form.to_dict()
        alert_name = data.get('alert_name')
        alert_id = data.get('alert_id')
        
        current_app.logger.info(f"Received Paddle webhook: {alert_name} ({alert_id})")
        
        # Verify signature if available
        public_key = current_app.config.get('PADDLE_PUBLIC_KEY_BASE64', '')
        if signature and public_key:
            if not verify_paddle_signature(payload, signature, public_key):
                current_app.logger.warning("Invalid Paddle signature")
                return jsonify({'error': 'Invalid signature'}), 400
        
        # Check if we've already processed this event
        existing_event = PaymentEvent.query.filter_by(
            provider='paddle',
            external_id=alert_id
        ).first()
        
        if existing_event:
            current_app.logger.info(f"Event {alert_id} already processed")
            return jsonify({'status': 'success'}), 200
        
        # Process different alert types
        if alert_name == 'subscription_created':
            handle_paddle_subscription_created(data)
        elif alert_name == 'subscription_updated':
            handle_paddle_subscription_updated(data)
        elif alert_name == 'subscription_cancelled':
            handle_paddle_subscription_cancelled(data)
        elif alert_name == 'subscription_payment_succeeded':
            handle_paddle_payment_succeeded(data)
        elif alert_name == 'subscription_payment_failed':
            handle_paddle_payment_failed(data)
        else:
            current_app.logger.info(f"Unhandled Paddle alert: {alert_name}")
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error processing Paddle webhook: {e}")
        return jsonify({'error': 'Processing failed'}), 500

def handle_stripe_subscription_created(event):
    """Handle Stripe subscription.created event"""
    subscription_data = event['data']['object']
    
    # TODO: Create subscription record
    current_app.logger.info(f"Stripe subscription created: {subscription_data['id']}")

def handle_stripe_subscription_updated(event):
    """Handle Stripe subscription.updated event"""
    subscription_data = event['data']['object']
    
    # Find existing subscription
    subscription = Subscription.query.filter_by(
        provider='stripe',
        external_id=subscription_data['id']
    ).first()
    
    if subscription:
        # Update subscription status
        subscription.status = subscription_data['status']
        subscription.current_period_start = datetime.fromtimestamp(
            subscription_data['current_period_start']
        ) if subscription_data.get('current_period_start') else None
        subscription.current_period_end = datetime.fromtimestamp(
            subscription_data['current_period_end']
        ) if subscription_data.get('current_period_end') else None
        
        if subscription_data.get('canceled_at'):
            subscription.canceled_at = datetime.fromtimestamp(subscription_data['canceled_at'])
        
        db.session.commit()
        current_app.logger.info(f"Updated subscription: {subscription.id}")

def handle_stripe_subscription_deleted(event):
    """Handle Stripe subscription.deleted event"""
    subscription_data = event['data']['object']
    
    subscription = Subscription.query.filter_by(
        provider='stripe',
        external_id=subscription_data['id']
    ).first()
    
    if subscription:
        subscription.status = 'canceled'
        subscription.ended_at = datetime.utcnow()
        db.session.commit()
        current_app.logger.info(f"Canceled subscription: {subscription.id}")

def handle_stripe_invoice_payment_succeeded(event):
    """Handle Stripe invoice.payment_succeeded event"""
    invoice_data = event['data']['object']
    
    # Create payment event record
    payment_event = PaymentEvent(
        provider='stripe',
        external_id=event['id'],
        event_type='invoice.payment_succeeded',
        amount=invoice_data.get('amount_paid', 0) / 100,  # Convert from cents
        currency=invoice_data.get('currency', 'usd'),
        status='succeeded',
        raw_data=event,
        processed_at=datetime.utcnow()
    )
    
    # Link to subscription if available
    if invoice_data.get('subscription'):
        subscription = Subscription.query.filter_by(
            provider='stripe',
            external_id=invoice_data['subscription']
        ).first()
        if subscription:
            payment_event.subscription_id = subscription.id
    
    db.session.add(payment_event)
    db.session.commit()
    
    current_app.logger.info(f"Payment succeeded: {invoice_data['id']}")

def handle_stripe_invoice_payment_failed(event):
    """Handle Stripe invoice.payment_failed event"""
    invoice_data = event['data']['object']
    
    # Create payment event record
    payment_event = PaymentEvent(
        provider='stripe',
        external_id=event['id'],
        event_type='invoice.payment_failed',
        amount=invoice_data.get('amount_due', 0) / 100,
        currency=invoice_data.get('currency', 'usd'),
        status='failed',
        raw_data=event,
        processed_at=datetime.utcnow()
    )
    
    # Link to subscription if available
    if invoice_data.get('subscription'):
        subscription = Subscription.query.filter_by(
            provider='stripe',
            external_id=invoice_data['subscription']
        ).first()
        if subscription:
            payment_event.subscription_id = subscription.id
    
    db.session.add(payment_event)
    db.session.commit()
    
    current_app.logger.warning(f"Payment failed: {invoice_data['id']}")

def handle_stripe_trial_will_end(event):
    """Handle Stripe customer.subscription.trial_will_end event"""
    subscription_data = event['data']['object']
    
    # TODO: Send trial ending notification email
    current_app.logger.info(f"Trial ending for subscription: {subscription_data['id']}")

def handle_paddle_subscription_created(data):
    """Handle Paddle subscription_created alert"""
    # TODO: Create subscription record from Paddle data
    current_app.logger.info(f"Paddle subscription created: {data.get('subscription_id')}")

def handle_paddle_subscription_updated(data):
    """Handle Paddle subscription_updated alert"""
    subscription_id = data.get('subscription_id')
    
    subscription = Subscription.query.filter_by(
        provider='paddle',
        external_id=subscription_id
    ).first()
    
    if subscription:
        # Update subscription from Paddle data
        subscription.status = data.get('status', subscription.status)
        # TODO: Update other fields from Paddle data
        
        db.session.commit()
        current_app.logger.info(f"Updated Paddle subscription: {subscription.id}")

def handle_paddle_subscription_cancelled(data):
    """Handle Paddle subscription_cancelled alert"""
    subscription_id = data.get('subscription_id')
    
    subscription = Subscription.query.filter_by(
        provider='paddle',
        external_id=subscription_id
    ).first()
    
    if subscription:
        subscription.status = 'canceled'
        subscription.canceled_at = datetime.utcnow()
        db.session.commit()
        current_app.logger.info(f"Canceled Paddle subscription: {subscription.id}")

def handle_paddle_payment_succeeded(data):
    """Handle Paddle subscription_payment_succeeded alert"""
    # Create payment event record
    payment_event = PaymentEvent(
        provider='paddle',
        external_id=data.get('alert_id'),
        event_type='subscription_payment_succeeded',
        amount=float(data.get('sale_gross', 0)),
        currency=data.get('currency', 'USD').lower(),
        status='succeeded',
        raw_data=data,
        processed_at=datetime.utcnow()
    )
    
    # Link to subscription if available
    subscription_id = data.get('subscription_id')
    if subscription_id:
        subscription = Subscription.query.filter_by(
            provider='paddle',
            external_id=subscription_id
        ).first()
        if subscription:
            payment_event.subscription_id = subscription.id
    
    db.session.add(payment_event)
    db.session.commit()
    
    current_app.logger.info(f"Paddle payment succeeded: {data.get('order_id')}")

def handle_paddle_payment_failed(data):
    """Handle Paddle subscription_payment_failed alert"""
    # Create payment event record
    payment_event = PaymentEvent(
        provider='paddle',
        external_id=data.get('alert_id'),
        event_type='subscription_payment_failed',
        amount=float(data.get('sale_gross', 0)),
        currency=data.get('currency', 'USD').lower(),
        status='failed',
        raw_data=data,
        processed_at=datetime.utcnow()
    )
    
    # Link to subscription if available
    subscription_id = data.get('subscription_id')
    if subscription_id:
        subscription = Subscription.query.filter_by(
            provider='paddle',
            external_id=subscription_id
        ).first()
        if subscription:
            payment_event.subscription_id = subscription.id
    
    db.session.add(payment_event)
    db.session.commit()
    
    current_app.logger.warning(f"Paddle payment failed: {data.get('order_id')}")

# Health check
@webhooks_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'webhooks',
        'timestamp': datetime.utcnow().isoformat()
    }), 200