#!/usr/bin/env python3
"""
Validation Utilities
Common validation functions for API inputs
"""

import jsonschema
from flask import jsonify
from jsonschema import validate, ValidationError

def validate_json(request, schema):
    """
    Validate JSON request data against a schema
    
    Args:
        request: Flask request object
        schema: JSON schema dictionary
        
    Returns:
        dict: Validated data
        
    Raises:
        ValueError: If validation fails
    """
    try:
        # Check if request has JSON data
        if not request.is_json:
            raise ValueError("Content-Type must be application/json")
        
        data = request.get_json()
        if data is None:
            raise ValueError("Invalid JSON data")
        
        # Validate against schema
        validate(instance=data, schema=schema)
        
        return data
        
    except ValidationError as e:
        raise ValueError(f"Validation error: {e.message}")
    except Exception as e:
        raise ValueError(f"JSON parsing error: {str(e)}")

def validate_email(email):
    """
    Validate email format
    
    Args:
        email (str): Email address to validate
        
    Returns:
        bool: True if valid email format
    """
    import re
    
    if not email or not isinstance(email, str):
        return False
    
    # Basic email regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_password_strength(password):
    """
    Validate password strength
    
    Args:
        password (str): Password to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not password or not isinstance(password, str):
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if len(password) > 128:
        return False, "Password must be less than 128 characters"
    
    # Check for at least one lowercase letter
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    # Check for at least one uppercase letter
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    # Check for at least one digit
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    
    # Check for at least one special character
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is valid"

def sanitize_string(value, max_length=None):
    """
    Sanitize string input by stripping whitespace and limiting length
    
    Args:
        value: Input value to sanitize
        max_length (int, optional): Maximum allowed length
        
    Returns:
        str: Sanitized string
    """
    if not value:
        return ""
    
    # Convert to string and strip whitespace
    sanitized = str(value).strip()
    
    # Limit length if specified
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized

def validate_tenant_subdomain(subdomain):
    """
    Validate tenant subdomain format
    
    Args:
        subdomain (str): Subdomain to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not subdomain or not isinstance(subdomain, str):
        return False, "Subdomain is required"
    
    # Strip and lowercase
    subdomain = subdomain.strip().lower()
    
    # Check length
    if len(subdomain) < 3:
        return False, "Subdomain must be at least 3 characters long"
    
    if len(subdomain) > 63:
        return False, "Subdomain must be less than 63 characters"
    
    # Check format (alphanumeric and hyphens, not starting/ending with hyphen)
    import re
    pattern = r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$'
    
    if not re.match(pattern, subdomain):
        return False, "Subdomain can only contain lowercase letters, numbers, and hyphens (not at start/end)"
    
    # Check for reserved subdomains
    reserved = [
        'www', 'api', 'admin', 'support', 'help', 'docs', 'mail',
        'ftp', 'smtp', 'pop', 'imap', 'ns1', 'ns2', 'mx', 'test',
        'staging', 'dev', 'demo', 'portal', 'app', 'dashboard',
        'billing', 'payment', 'webhook', 'status', 'health'
    ]
    
    if subdomain in reserved:
        return False, f"'{subdomain}' is a reserved subdomain"
    
    return True, "Subdomain is valid"

def validate_phone_number(phone):
    """
    Validate phone number format (basic validation)
    
    Args:
        phone (str): Phone number to validate
        
    Returns:
        bool: True if valid phone format
    """
    if not phone or not isinstance(phone, str):
        return False
    
    # Remove common formatting characters
    cleaned = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('+', '')
    
    # Check if all remaining characters are digits
    if not cleaned.isdigit():
        return False
    
    # Check length (7-15 digits is typical for international numbers)
    if len(cleaned) < 7 or len(cleaned) > 15:
        return False
    
    return True