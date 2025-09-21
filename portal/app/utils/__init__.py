#!/usr/bin/env python3
"""
Portal Utilities Package
Common utility functions for the customer portal
"""

from .validation import (
    validate_json,
    validate_email,
    validate_password_strength,
    validate_tenant_subdomain,
    validate_phone_number,
    sanitize_string
)

from .auth import (
    require_customer,
    require_tenant_ownership,
    get_current_customer,
    customer_owns_tenant,
    hash_password,
    check_password,
    generate_api_key,
    validate_api_key,
    log_auth_event,
    rate_limit_key_func
)

__all__ = [
    # Validation utilities
    'validate_json',
    'validate_email',
    'validate_password_strength', 
    'validate_tenant_subdomain',
    'validate_phone_number',
    'sanitize_string',
    
    # Auth utilities
    'require_customer',
    'require_tenant_ownership',
    'get_current_customer',
    'customer_owns_tenant',
    'hash_password',
    'check_password',
    'generate_api_key',
    'validate_api_key',
    'log_auth_event',
    'rate_limit_key_func'
]