#!/usr/bin/env python3
"""
Authentication utilities and RBAC decorators for Admin Dashboard
Provides role-based access control and audit logging
"""

import functools
import os
import sys
from datetime import datetime
from typing import List, Optional, Callable, Any
from flask import jsonify, request, g, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, get_current_user
from werkzeug.exceptions import Forbidden

# Add project root to path for shared imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.models import Customer, AuditLog, CustomerRole, AuditAction
from admin.app import db

class PermissionError(Exception):
    """Custom exception for permission errors"""
    pass

def require_roles(*roles: str) -> Callable:
    """
    Decorator to require specific roles for accessing endpoints
    
    Args:
        roles: List of allowed role strings
        
    Returns:
        Decorated function that checks user roles
        
    Usage:
        @require_roles('admin', 'owner')
        def admin_only_view():
            pass
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            current_user = get_current_user()
            
            if not current_user:
                current_app.logger.warning(f"No user found for JWT token")
                return jsonify({
                    'error': 'Authentication Failed',
                    'message': 'User not found'
                }), 401
            
            if not current_user.is_active:
                current_app.logger.warning(f"Inactive user attempted access: {current_user.email}")
                return jsonify({
                    'error': 'Account Disabled',
                    'message': 'Your account has been disabled'
                }), 403
            
            if current_user.role not in roles:
                current_app.logger.warning(
                    f"User {current_user.email} with role {current_user.role} "
                    f"attempted to access endpoint requiring roles: {roles}"
                )
                return jsonify({
                    'error': 'Insufficient Permissions',
                    'message': f'This action requires one of the following roles: {", ".join(roles)}'
                }), 403
            
            # Set user context for audit logging
            g.current_user = current_user
            g.current_user_id = str(current_user.id)
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_admin(f: Callable) -> Callable:
    """
    Decorator to require admin role
    
    Usage:
        @require_admin
        def admin_only_view():
            pass
    """
    return require_roles(CustomerRole.ADMIN.value)(f)

def require_verified(f: Callable) -> Callable:
    """
    Decorator to require verified email address
    
    Usage:
        @require_verified
        def verified_only_view():
            pass
    """
    @functools.wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        current_user = get_current_user()
        
        if not current_user or not current_user.is_verified:
            return jsonify({
                'error': 'Email Verification Required',
                'message': 'Please verify your email address to access this feature'
            }), 403
        
        g.current_user = current_user
        g.current_user_id = str(current_user.id)
        
        return f(*args, **kwargs)
    
    return decorated_function

def audit_log(
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
    metadata: Optional[dict] = None
) -> None:
    """
    Create audit log entry for user actions
    
    Args:
        action: Action performed (create, update, delete, etc.)
        resource_type: Type of resource affected (tenant, customer, plan, etc.)
        resource_id: ID of the affected resource
        old_values: Previous values (for updates)
        new_values: New values (for creates/updates)
        metadata: Additional metadata
    """
    try:
        current_user = get_current_user()
        if not current_user:
            return  # Skip audit logging if no user context
        
        audit_entry = AuditLog(
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_role=current_user.role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
            user_agent=request.headers.get('User-Agent', '')[:500],
            session_id=get_jwt().get('jti', ''),
            old_values=old_values,
            new_values=new_values,
            metadata=metadata or {}
        )
        
        db.session.add(audit_entry)
        db.session.commit()
        
        current_app.logger.info(
            f"Audit log created: {current_user.email} performed {action} on {resource_type} {resource_id}"
        )
        
    except Exception as e:
        current_app.logger.error(f"Failed to create audit log: {e}")
        # Don't fail the main operation if audit logging fails
        db.session.rollback()

def audit_action(
    action: str,
    resource_type: str,
    resource_id_func: Optional[Callable] = None,
    metadata_func: Optional[Callable] = None
) -> Callable:
    """
    Decorator to automatically audit user actions
    
    Args:
        action: Action being performed
        resource_type: Type of resource
        resource_id_func: Function to extract resource ID from args/kwargs
        metadata_func: Function to extract metadata from args/kwargs
        
    Usage:
        @audit_action('create', 'tenant', lambda *args, **kwargs: kwargs.get('tenant_id'))
        def create_tenant(**kwargs):
            pass
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            # Execute the main function first
            result = f(*args, **kwargs)
            
            # Extract resource ID and metadata
            resource_id = None
            if resource_id_func:
                try:
                    resource_id = resource_id_func(*args, **kwargs)
                except Exception as e:
                    current_app.logger.warning(f"Failed to extract resource ID for audit: {e}")
            
            metadata = {}
            if metadata_func:
                try:
                    metadata = metadata_func(*args, **kwargs) or {}
                except Exception as e:
                    current_app.logger.warning(f"Failed to extract metadata for audit: {e}")
            
            # Add function name to metadata
            metadata['function'] = f.__name__
            
            # Create audit log
            audit_log(
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None,
                metadata=metadata
            )
            
            return result
        
        return decorated_function
    return decorator

def get_current_user_safe() -> Optional[Customer]:
    """
    Safely get current user without raising exceptions
    
    Returns:
        Current user or None if not authenticated
    """
    try:
        return get_current_user()
    except:
        return None

def check_resource_access(resource, user: Customer, action: str = 'read') -> bool:
    """
    Check if user has access to a specific resource
    
    Args:
        resource: The resource object to check access for
        user: The user requesting access
        action: The action being performed ('read', 'write', 'delete')
        
    Returns:
        True if access is allowed, False otherwise
    """
    # Admin users have access to everything
    if user.role == CustomerRole.ADMIN.value:
        return True
    
    # Check resource-specific access rules
    if hasattr(resource, 'customer_id'):
        # Resource belongs to a customer
        if resource.customer_id == user.id:
            return True
        
        # Owners can access their organization's resources
        if user.role == CustomerRole.OWNER.value:
            # Add organization-level access logic here if needed
            pass
    
    return False

def require_resource_access(
    resource_loader: Callable,
    action: str = 'read'
) -> Callable:
    """
    Decorator to check access to specific resources
    
    Args:
        resource_loader: Function that loads the resource from request args
        action: Action being performed on the resource
        
    Usage:
        @require_resource_access(lambda tenant_id: Tenant.query.get(tenant_id), 'write')
        def update_tenant(tenant_id):
            pass
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            current_user = get_current_user()
            
            if not current_user:
                return jsonify({
                    'error': 'Authentication Required',
                    'message': 'Valid authentication is required'
                }), 401
            
            try:
                resource = resource_loader(*args, **kwargs)
                
                if not resource:
                    return jsonify({
                        'error': 'Resource Not Found',
                        'message': 'The requested resource does not exist'
                    }), 404
                
                if not check_resource_access(resource, current_user, action):
                    current_app.logger.warning(
                        f"User {current_user.email} denied {action} access to {type(resource).__name__} {resource.id}"
                    )
                    return jsonify({
                        'error': 'Access Denied',
                        'message': f'You do not have {action} access to this resource'
                    }), 403
                
                # Pass resource to the function
                kwargs['resource'] = resource
                g.current_user = current_user
                g.current_resource = resource
                
                return f(*args, **kwargs)
                
            except Exception as e:
                current_app.logger.error(f"Error in resource access check: {e}")
                return jsonify({
                    'error': 'Access Check Failed',
                    'message': 'Unable to verify resource access'
                }), 500
        
        return decorated_function
    return decorator

class AuthenticationService:
    """Service class for authentication operations"""
    
    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, list[str]]:
        """
        Validate password strength
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one number")
        
        # Check for special characters
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            errors.append("Password must contain at least one special character")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def is_password_compromised(password: str) -> bool:
        """
        Check if password appears in common breach databases
        This is a placeholder - implement with haveibeenpwned API or similar
        
        Returns:
            True if password is compromised
        """
        # Common weak passwords
        weak_passwords = {
            'password', '123456', 'password123', 'admin', 'qwerty',
            'letmein', 'welcome', 'monkey', '1234567890', 'password1'
        }
        
        return password.lower() in weak_passwords

def rate_limit_key() -> str:
    """Generate rate limiting key based on user or IP"""
    user = get_current_user_safe()
    if user:
        return f"user:{user.id}"
    return f"ip:{request.remote_addr}"

# Export main components
__all__ = [
    'require_roles',
    'require_admin', 
    'require_verified',
    'require_resource_access',
    'audit_log',
    'audit_action',
    'get_current_user_safe',
    'check_resource_access',
    'AuthenticationService',
    'rate_limit_key'
]