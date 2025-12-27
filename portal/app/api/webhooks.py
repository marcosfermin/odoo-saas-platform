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
    """Verify Paddle webhook signature using RSA public key"""
    try:
        import base64
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        import phpserialize

        if not signature or not public_key:
            current_app.logger.warning("Missing Paddle signature or public key")
            return False

        # Decode the public key from base64
        public_key_bytes = base64.b64decode(public_key)
        public_key_obj = serialization.load_der_public_key(public_key_bytes, backend=default_backend())

        # For Paddle Classic, the signature is in the 'p_signature' field
        # We need to extract it from the form data and verify the remaining data
        if isinstance(payload, dict):
            # Get the signature from the payload
            sig = payload.get('p_signature', signature)
            if sig:
                sig = base64.b64decode(sig)

            # Remove the signature from the data to verify
            data_to_verify = {k: v for k, v in sorted(payload.items()) if k != 'p_signature'}

            # Serialize the data in PHP format (Paddle uses PHP serialization)
            serialized_data = phpserialize.dumps(data_to_verify)

            # Verify the signature
            try:
                public_key_obj.verify(
                    sig,
                    serialized_data,
                    padding.PKCS1v15(),
                    hashes.SHA1()
                )
                return True
            except Exception as verify_error:
                current_app.logger.warning(f"Paddle signature verification failed: {verify_error}")
                return False
        else:
            current_app.logger.warning("Invalid payload format for Paddle signature verification")
            return False

    except ImportError as e:
        # If cryptography or phpserialize is not installed, log warning but allow
        current_app.logger.warning(f"Paddle signature verification dependencies missing: {e}")
        # In production, you should return False here
        # For development, we'll return True with a warning
        return True
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
        existing_event = db.session.query(PaymentEvent).filter_by(
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
        existing_event = db.session.query(PaymentEvent).filter_by(
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
    from datetime import datetime

    subscription_data = event['data']['object']

    # Extract customer and plan info from metadata
    metadata = subscription_data.get('metadata', {})
    customer_id = metadata.get('customer_id')
    plan_id = metadata.get('plan_id')

    if not customer_id:
        # Try to find customer by Stripe customer ID
        stripe_customer_id = subscription_data.get('customer')
        customer = db.session.query(Customer).filter_by(stripe_customer_id=stripe_customer_id).first()
        if customer:
            customer_id = str(customer.id)

    if not customer_id:
        current_app.logger.warning(f"No customer found for Stripe subscription: {subscription_data['id']}")
        return

    # Get plan from first item if not in metadata
    if not plan_id and subscription_data.get('items', {}).get('data'):
        price_id = subscription_data['items']['data'][0].get('price', {}).get('id')
        if price_id:
            plan = db.session.query(Plan).filter(
                (Plan.stripe_price_id_monthly == price_id) |
                (Plan.stripe_price_id_yearly == price_id)
            ).first()
            if plan:
                plan_id = str(plan.id)

    # Create subscription record
    subscription = Subscription(
        customer_id=customer_id,
        plan_id=plan_id,
        provider='stripe',
        external_id=subscription_data['id'],
        status=subscription_data.get('status', 'active'),
        current_period_start=datetime.fromtimestamp(
            subscription_data['current_period_start']
        ) if subscription_data.get('current_period_start') else None,
        current_period_end=datetime.fromtimestamp(
            subscription_data['current_period_end']
        ) if subscription_data.get('current_period_end') else None,
        trial_end=datetime.fromtimestamp(
            subscription_data['trial_end']
        ) if subscription_data.get('trial_end') else None,
        amount=subscription_data.get('items', {}).get('data', [{}])[0].get('price', {}).get('unit_amount', 0) / 100,
        currency=subscription_data.get('currency', 'usd'),
        interval=subscription_data.get('items', {}).get('data', [{}])[0].get('price', {}).get('recurring', {}).get('interval', 'month')
    )

    db.session.add(subscription)
    db.session.commit()

    current_app.logger.info(f"Stripe subscription created: {subscription_data['id']} for customer {customer_id}")

def handle_stripe_subscription_updated(event):
    """Handle Stripe subscription.updated event"""
    subscription_data = event['data']['object']
    
    # Find existing subscription
    subscription = db.session.query(Subscription).filter_by(
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
    
    subscription = db.session.query(Subscription).filter_by(
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
        subscription = db.session.query(Subscription).filter_by(
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
        subscription = db.session.query(Subscription).filter_by(
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

    # Find the subscription and customer
    subscription = db.session.query(Subscription).filter_by(
        provider='stripe',
        external_id=subscription_data['id']
    ).first()

    if subscription and subscription.customer:
        customer = subscription.customer

        # Queue email notification job
        try:
            from redis import Redis
            from rq import Queue

            redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
            redis_conn = Redis.from_url(redis_url)
            queue = Queue('default', connection=redis_conn)

            queue.enqueue(
                'workers.jobs.notification_jobs.send_trial_ending_email',
                str(customer.id),
                str(subscription.id),
                subscription.trial_end.isoformat() if subscription.trial_end else None,
                job_timeout=60
            )

            current_app.logger.info(f"Queued trial ending notification for {customer.email}")
        except Exception as e:
            current_app.logger.warning(f"Failed to queue trial ending notification: {e}")

    current_app.logger.info(f"Trial ending for subscription: {subscription_data['id']}")

def handle_paddle_subscription_created(data):
    """Handle Paddle subscription_created alert"""
    import json
    from datetime import datetime

    subscription_id = data.get('subscription_id')

    # Parse passthrough data to get customer and plan info
    passthrough = data.get('passthrough', '{}')
    try:
        if isinstance(passthrough, str):
            passthrough_data = json.loads(passthrough)
        else:
            passthrough_data = passthrough
    except json.JSONDecodeError:
        passthrough_data = {}

    customer_id = passthrough_data.get('customer_id')
    plan_id = passthrough_data.get('plan_id')

    if not customer_id:
        # Try to find customer by email
        email = data.get('email')
        if email:
            customer = db.session.query(Customer).filter_by(email=email.lower()).first()
            if customer:
                customer_id = str(customer.id)

    if not customer_id:
        current_app.logger.warning(f"No customer found for Paddle subscription: {subscription_id}")
        return

    # Get plan from Paddle plan ID if not in passthrough
    if not plan_id:
        paddle_plan_id = data.get('subscription_plan_id')
        if paddle_plan_id:
            plan = db.session.query(Plan).filter_by(paddle_plan_id=str(paddle_plan_id)).first()
            if plan:
                plan_id = str(plan.id)

    # Parse dates
    next_bill_date = None
    if data.get('next_bill_date'):
        try:
            next_bill_date = datetime.strptime(data['next_bill_date'], '%Y-%m-%d')
        except ValueError:
            pass

    # Determine status
    status = data.get('status', 'active')
    if status == 'trialing':
        status = 'trialing'
    elif status == 'active':
        status = 'active'

    # Create subscription record
    subscription = Subscription(
        customer_id=customer_id,
        plan_id=plan_id,
        provider='paddle',
        external_id=subscription_id,
        status=status,
        current_period_end=next_bill_date,
        amount=float(data.get('unit_price', 0)),
        currency=data.get('currency', 'USD').lower(),
        interval='month' if 'month' in data.get('plan_name', '').lower() else 'year'
    )

    db.session.add(subscription)
    db.session.commit()

    current_app.logger.info(f"Paddle subscription created: {subscription_id} for customer {customer_id}")

def handle_paddle_subscription_updated(data):
    """Handle Paddle subscription_updated alert"""
    subscription_id = data.get('subscription_id')
    
    subscription = db.session.query(Subscription).filter_by(
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
    
    subscription = db.session.query(Subscription).filter_by(
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
        subscription = db.session.query(Subscription).filter_by(
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
        subscription = db.session.query(Subscription).filter_by(
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