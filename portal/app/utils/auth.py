#!/usr/bin/env python3
"""
Authentication Utilities
Common authentication and authorization functions
"""

import os
import sys
from functools import wraps
from flask import jsonify, current_app
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.models import Customer

def require_customer(f):
    """
    Decorator to require valid customer authentication
    
    Args:
        f: Function to decorate
        
    Returns:
        Decorated function that validates customer exists
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Verify JWT token exists
            verify_jwt_in_request()
            
            # Get customer ID from token
            customer_id = get_jwt_identity()
            
            if not customer_id:
                return jsonify({'error': 'Invalid token: missing customer ID'}), 401
            
            # Verify customer exists and is active
            customer = Customer.query.get(customer_id)
            if not customer:
                return jsonify({'error': 'Customer not found'}), 401
            
            if customer.status != 'active':
                return jsonify({'error': f'Customer account is {customer.status}'}), 403
            
            # Continue to the original function
            return f(*args, **kwargs)
            
        except Exception as e:
            current_app.logger.error(f"Authentication error: {e}")
            return jsonify({'error': 'Authentication failed'}), 401
    
    return decorated_function

def get_current_customer():
    """
    Get the current authenticated customer
    
    Returns:
        Customer: Current customer object or None
    """
    try:
        customer_id = get_jwt_identity()
        if not customer_id:
            return None
        
        customer = Customer.query.get(customer_id)
        return customer if customer and customer.status == 'active' else None
        
    except Exception:
        return None

def customer_owns_tenant(customer_id, tenant_id):
    """
    Check if a customer owns a specific tenant
    
    Args:
        customer_id (int): Customer ID
        tenant_id (int): Tenant ID
        
    Returns:
        bool: True if customer owns the tenant
    """
    try:
        from shared.models import Tenant
        
        tenant = Tenant.query.filter_by(
            id=tenant_id,
            customer_id=customer_id
        ).first()
        
        return tenant is not None
        
    except Exception:
        return False

def require_tenant_ownership(f):
    """
    Decorator to require customer owns the tenant specified in the route
    
    Expects tenant_id to be available in route parameters
    
    Args:
        f: Function to decorate
        
    Returns:
        Decorated function that validates tenant ownership
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            customer_id = get_jwt_identity()
            
            # Get tenant_id from route parameters
            tenant_id = kwargs.get('tenant_id')
            
            if not tenant_id:
                return jsonify({'error': 'Tenant ID required'}), 400
            
            if not customer_owns_tenant(customer_id, tenant_id):
                return jsonify({'error': 'Tenant not found or access denied'}), 404
            
            return f(*args, **kwargs)
            
        except Exception as e:
            current_app.logger.error(f"Tenant ownership check error: {e}")
            return jsonify({'error': 'Access validation failed'}), 500
    
    return decorated_function

def hash_password(password):
    """
    Hash a password using bcrypt
    
    Args:
        password (str): Plain text password
        
    Returns:
        str: Hashed password
    """
    try:
        from werkzeug.security import generate_password_hash
        return generate_password_hash(password)
    except Exception as e:
        current_app.logger.error(f"Password hashing error: {e}")
        raise

def check_password(password_hash, password):
    """
    Check a password against its hash
    
    Args:
        password_hash (str): Stored password hash
        password (str): Plain text password to check
        
    Returns:
        bool: True if password matches hash
    """
    try:
        from werkzeug.security import check_password_hash
        return check_password_hash(password_hash, password)
    except Exception as e:
        current_app.logger.error(f"Password check error: {e}")
        return False

def generate_api_key():
    """
    Generate a secure API key
    
    Returns:
        str: Random API key
    """
    import secrets
    import string
    
    # Generate 32-character API key
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))

def validate_api_key(api_key, customer_id):
    """
    Validate an API key for a customer
    
    Args:
        api_key (str): API key to validate
        customer_id (int): Customer ID
        
    Returns:
        bool: True if API key is valid
    """
    try:
        customer = Customer.query.get(customer_id)
        if not customer or customer.status != 'active':
            return False
        
        # TODO: Implement API key validation logic
        # This would check against stored API keys in the database
        return False  # Placeholder
        
    except Exception:
        return False

def log_auth_event(customer_id, event_type, details=None, ip_address=None):
    """
    Log an authentication event
    
    Args:
        customer_id (int): Customer ID
        event_type (str): Type of event (login, logout, failed_login, etc.)
        details (dict, optional): Additional event details
        ip_address (str, optional): IP address of the request
    """
    try:
        current_app.logger.info(
            f"Auth event - Customer: {customer_id}, Event: {event_type}, "
            f"IP: {ip_address}, Details: {details}"
        )
        
        # TODO: Store auth events in database for audit trail
        
    except Exception as e:
        current_app.logger.error(f"Error logging auth event: {e}")

def rate_limit_key_func():
    """
    Generate rate limiting key based on customer ID or IP
    
    Returns:
        str: Rate limiting key
    """
    try:
        from flask import request
        
        # Try to get customer ID from JWT
        customer_id = get_jwt_identity()
        if customer_id:
            return f"customer:{customer_id}"
        
        # Fall back to IP address
        return f"ip:{request.remote_addr}"
        
    except Exception:
        from flask import request
        return f"ip:{request.remote_addr}"