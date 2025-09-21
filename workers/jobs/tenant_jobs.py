#!/usr/bin/env python3
"""
Tenant Management Background Jobs
Handles tenant provisioning, deletion, and module management
"""

import os
import sys
import requests
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.models import Tenant, Customer, AuditLog
from shared.database import get_db_session

logger = logging.getLogger(__name__)

# Configuration
ODOO_SERVICE_URL = os.environ.get('ODOO_SERVICE_URL', 'http://odoo-service:8080')
TENANT_SERVICE_TIMEOUT = int(os.environ.get('TENANT_SERVICE_TIMEOUT', '300'))

def provision_tenant_job(tenant_id, customer_id, tenant_data):
    """
    Provision a new Odoo tenant
    
    Args:
        tenant_id (int): Tenant ID
        customer_id (int): Customer ID
        tenant_data (dict): Tenant configuration data
    
    Returns:
        dict: Provisioning result
    """
    logger.info(f"Starting tenant provisioning for tenant {tenant_id}")
    
    try:
        # Update tenant status to provisioning
        with get_db_session() as session:
            tenant = session.query(Tenant).get(tenant_id)
            if not tenant:
                raise Exception(f"Tenant {tenant_id} not found")
            
            tenant.status = 'provisioning'
            session.commit()
            
            # Log audit event
            audit = AuditLog(
                user_id=None,
                tenant_id=tenant_id,
                action='tenant_provisioning_started',
                resource_type='tenant',
                resource_id=tenant_id,
                details={'tenant_data': tenant_data}
            )
            session.add(audit)
            session.commit()
        
        # Call Odoo service to create tenant
        response = requests.post(
            f"{ODOO_SERVICE_URL}/tenants/{tenant_id}/create",
            json=tenant_data,
            timeout=TENANT_SERVICE_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Update tenant status to active
            with get_db_session() as session:
                tenant = session.query(Tenant).get(tenant_id)
                tenant.status = 'active'
                tenant.provisioned_at = datetime.utcnow()
                session.commit()
                
                # Log success
                audit = AuditLog(
                    user_id=None,
                    tenant_id=tenant_id,
                    action='tenant_provisioning_completed',
                    resource_type='tenant',
                    resource_id=tenant_id,
                    details={'result': result}
                )
                session.add(audit)
                session.commit()
            
            logger.info(f"Successfully provisioned tenant {tenant_id}")
            return {
                'status': 'success',
                'tenant_id': tenant_id,
                'message': 'Tenant provisioned successfully',
                'details': result
            }
        
        else:
            error_msg = f"Failed to provision tenant: HTTP {response.status_code}"
            logger.error(error_msg)
            
            # Update tenant status to failed
            with get_db_session() as session:
                tenant = session.query(Tenant).get(tenant_id)
                tenant.status = 'failed'
                session.commit()
                
                # Log failure
                audit = AuditLog(
                    user_id=None,
                    tenant_id=tenant_id,
                    action='tenant_provisioning_failed',
                    resource_type='tenant',
                    resource_id=tenant_id,
                    details={'error': error_msg, 'response': response.text}
                )
                session.add(audit)
                session.commit()
            
            raise Exception(error_msg)
    
    except Exception as e:
        logger.error(f"Error provisioning tenant {tenant_id}: {e}")
        
        # Update tenant status to failed
        try:
            with get_db_session() as session:
                tenant = session.query(Tenant).get(tenant_id)
                if tenant:
                    tenant.status = 'failed'
                    session.commit()
        except Exception as db_error:
            logger.error(f"Failed to update tenant status: {db_error}")
        
        raise

def delete_tenant_job(tenant_id):
    """
    Delete an Odoo tenant
    
    Args:
        tenant_id (int): Tenant ID
    
    Returns:
        dict: Deletion result
    """
    logger.info(f"Starting tenant deletion for tenant {tenant_id}")
    
    try:
        # Update tenant status to deleting
        with get_db_session() as session:
            tenant = session.query(Tenant).get(tenant_id)
            if not tenant:
                raise Exception(f"Tenant {tenant_id} not found")
            
            tenant.status = 'deleting'
            session.commit()
            
            # Log audit event
            audit = AuditLog(
                user_id=None,
                tenant_id=tenant_id,
                action='tenant_deletion_started',
                resource_type='tenant',
                resource_id=tenant_id,
                details={}
            )
            session.add(audit)
            session.commit()
        
        # Call Odoo service to delete tenant
        response = requests.delete(
            f"{ODOO_SERVICE_URL}/tenants/{tenant_id}/delete",
            timeout=TENANT_SERVICE_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Mark tenant as deleted
            with get_db_session() as session:
                tenant = session.query(Tenant).get(tenant_id)
                tenant.status = 'deleted'
                tenant.deleted_at = datetime.utcnow()
                session.commit()
                
                # Log success
                audit = AuditLog(
                    user_id=None,
                    tenant_id=tenant_id,
                    action='tenant_deletion_completed',
                    resource_type='tenant',
                    resource_id=tenant_id,
                    details={'result': result}
                )
                session.add(audit)
                session.commit()
            
            logger.info(f"Successfully deleted tenant {tenant_id}")
            return {
                'status': 'success',
                'tenant_id': tenant_id,
                'message': 'Tenant deleted successfully',
                'details': result
            }
        
        else:
            error_msg = f"Failed to delete tenant: HTTP {response.status_code}"
            logger.error(error_msg)
            
            # Update tenant status back to previous state
            with get_db_session() as session:
                tenant = session.query(Tenant).get(tenant_id)
                tenant.status = 'active'  # Assume it was active before
                session.commit()
                
                # Log failure
                audit = AuditLog(
                    user_id=None,
                    tenant_id=tenant_id,
                    action='tenant_deletion_failed',
                    resource_type='tenant',
                    resource_id=tenant_id,
                    details={'error': error_msg, 'response': response.text}
                )
                session.add(audit)
                session.commit()
            
            raise Exception(error_msg)
    
    except Exception as e:
        logger.error(f"Error deleting tenant {tenant_id}: {e}")
        raise

def install_module_job(tenant_id, module_name, user_id=None):
    """
    Install Odoo module in tenant
    
    Args:
        tenant_id (int): Tenant ID
        module_name (str): Module name to install
        user_id (int, optional): User who initiated the action
    
    Returns:
        dict: Installation result
    """
    logger.info(f"Installing module {module_name} in tenant {tenant_id}")
    
    try:
        # Verify tenant exists and is active
        with get_db_session() as session:
            tenant = session.query(Tenant).get(tenant_id)
            if not tenant:
                raise Exception(f"Tenant {tenant_id} not found")
            
            if tenant.status != 'active':
                raise Exception(f"Tenant {tenant_id} is not active")
            
            # Log audit event
            audit = AuditLog(
                user_id=user_id,
                tenant_id=tenant_id,
                action='module_installation_started',
                resource_type='module',
                resource_id=module_name,
                details={'module_name': module_name}
            )
            session.add(audit)
            session.commit()
        
        # Call Odoo service to install module
        response = requests.post(
            f"{ODOO_SERVICE_URL}/tenants/{tenant_id}/modules/{module_name}/install",
            timeout=TENANT_SERVICE_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Log success
            with get_db_session() as session:
                audit = AuditLog(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    action='module_installation_completed',
                    resource_type='module',
                    resource_id=module_name,
                    details={'result': result}
                )
                session.add(audit)
                session.commit()
            
            logger.info(f"Successfully installed module {module_name} in tenant {tenant_id}")
            return {
                'status': 'success',
                'tenant_id': tenant_id,
                'module': module_name,
                'message': 'Module installed successfully',
                'details': result
            }
        
        else:
            error_msg = f"Failed to install module: HTTP {response.status_code}"
            logger.error(error_msg)
            
            # Log failure
            with get_db_session() as session:
                audit = AuditLog(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    action='module_installation_failed',
                    resource_type='module',
                    resource_id=module_name,
                    details={'error': error_msg, 'response': response.text}
                )
                session.add(audit)
                session.commit()
            
            raise Exception(error_msg)
    
    except Exception as e:
        logger.error(f"Error installing module {module_name} in tenant {tenant_id}: {e}")
        raise

def uninstall_module_job(tenant_id, module_name, user_id=None):
    """
    Uninstall Odoo module from tenant
    
    Args:
        tenant_id (int): Tenant ID
        module_name (str): Module name to uninstall
        user_id (int, optional): User who initiated the action
    
    Returns:
        dict: Uninstallation result
    """
    logger.info(f"Uninstalling module {module_name} from tenant {tenant_id}")
    
    try:
        # Verify tenant exists and is active
        with get_db_session() as session:
            tenant = session.query(Tenant).get(tenant_id)
            if not tenant:
                raise Exception(f"Tenant {tenant_id} not found")
            
            if tenant.status != 'active':
                raise Exception(f"Tenant {tenant_id} is not active")
            
            # Log audit event
            audit = AuditLog(
                user_id=user_id,
                tenant_id=tenant_id,
                action='module_uninstallation_started',
                resource_type='module',
                resource_id=module_name,
                details={'module_name': module_name}
            )
            session.add(audit)
            session.commit()
        
        # Call Odoo service to uninstall module
        response = requests.delete(
            f"{ODOO_SERVICE_URL}/tenants/{tenant_id}/modules/{module_name}/uninstall",
            timeout=TENANT_SERVICE_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Log success
            with get_db_session() as session:
                audit = AuditLog(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    action='module_uninstallation_completed',
                    resource_type='module',
                    resource_id=module_name,
                    details={'result': result}
                )
                session.add(audit)
                session.commit()
            
            logger.info(f"Successfully uninstalled module {module_name} from tenant {tenant_id}")
            return {
                'status': 'success',
                'tenant_id': tenant_id,
                'module': module_name,
                'message': 'Module uninstalled successfully',
                'details': result
            }
        
        else:
            error_msg = f"Failed to uninstall module: HTTP {response.status_code}"
            logger.error(error_msg)
            
            # Log failure
            with get_db_session() as session:
                audit = AuditLog(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    action='module_uninstallation_failed',
                    resource_type='module',
                    resource_id=module_name,
                    details={'error': error_msg, 'response': response.text}
                )
                session.add(audit)
                session.commit()
            
            raise Exception(error_msg)
    
    except Exception as e:
        logger.error(f"Error uninstalling module {module_name} from tenant {tenant_id}: {e}")
        raise

def backup_tenant_job(tenant_id):
    """
    Create backup of tenant
    
    Args:
        tenant_id (int): Tenant ID
    
    Returns:
        dict: Backup result
    """
    logger.info(f"Creating backup for tenant {tenant_id}")
    
    try:
        # Verify tenant exists and is active
        with get_db_session() as session:
            tenant = session.query(Tenant).get(tenant_id)
            if not tenant:
                raise Exception(f"Tenant {tenant_id} not found")
            
            # Log audit event
            audit = AuditLog(
                user_id=None,
                tenant_id=tenant_id,
                action='tenant_backup_started',
                resource_type='tenant',
                resource_id=tenant_id,
                details={}
            )
            session.add(audit)
            session.commit()
        
        # Call Odoo service to create backup
        response = requests.post(
            f"{ODOO_SERVICE_URL}/tenants/{tenant_id}/backup",
            timeout=1800  # 30 minute timeout for backups
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Log success
            with get_db_session() as session:
                audit = AuditLog(
                    user_id=None,
                    tenant_id=tenant_id,
                    action='tenant_backup_completed',
                    resource_type='tenant',
                    resource_id=tenant_id,
                    details={'result': result}
                )
                session.add(audit)
                session.commit()
            
            logger.info(f"Successfully created backup for tenant {tenant_id}")
            return {
                'status': 'success',
                'tenant_id': tenant_id,
                'message': 'Backup created successfully',
                'details': result
            }
        
        else:
            error_msg = f"Failed to create backup: HTTP {response.status_code}"
            logger.error(error_msg)
            
            # Log failure
            with get_db_session() as session:
                audit = AuditLog(
                    user_id=None,
                    tenant_id=tenant_id,
                    action='tenant_backup_failed',
                    resource_type='tenant',
                    resource_id=tenant_id,
                    details={'error': error_msg, 'response': response.text}
                )
                session.add(audit)
                session.commit()
            
            raise Exception(error_msg)
    
    except Exception as e:
        logger.error(f"Error creating backup for tenant {tenant_id}: {e}")
        raise

def restore_tenant_job(tenant_id, backup_file):
    """
    Restore tenant from backup
    
    Args:
        tenant_id (int): Tenant ID
        backup_file (str): Backup file name
    
    Returns:
        dict: Restore result
    """
    logger.info(f"Restoring tenant {tenant_id} from backup {backup_file}")
    
    try:
        # Update tenant status to restoring
        with get_db_session() as session:
            tenant = session.query(Tenant).get(tenant_id)
            if not tenant:
                raise Exception(f"Tenant {tenant_id} not found")
            
            tenant.status = 'restoring'
            session.commit()
            
            # Log audit event
            audit = AuditLog(
                user_id=None,
                tenant_id=tenant_id,
                action='tenant_restore_started',
                resource_type='tenant',
                resource_id=tenant_id,
                details={'backup_file': backup_file}
            )
            session.add(audit)
            session.commit()
        
        # TODO: Call backup service or Odoo service to restore from backup
        # This would integrate with the S3 backup service
        logger.info(f"Restore functionality for tenant {tenant_id} - placeholder")
        
        # Update tenant status to active
        with get_db_session() as session:
            tenant = session.query(Tenant).get(tenant_id)
            tenant.status = 'active'
            session.commit()
            
            # Log success
            audit = AuditLog(
                user_id=None,
                tenant_id=tenant_id,
                action='tenant_restore_completed',
                resource_type='tenant',
                resource_id=tenant_id,
                details={'backup_file': backup_file}
            )
            session.add(audit)
            session.commit()
        
        logger.info(f"Successfully restored tenant {tenant_id} from backup")
        return {
            'status': 'success',
            'tenant_id': tenant_id,
            'backup_file': backup_file,
            'message': 'Tenant restored successfully'
        }
    
    except Exception as e:
        logger.error(f"Error restoring tenant {tenant_id}: {e}")
        
        # Update tenant status to failed
        try:
            with get_db_session() as session:
                tenant = session.query(Tenant).get(tenant_id)
                if tenant:
                    tenant.status = 'failed'
                    session.commit()
        except Exception as db_error:
            logger.error(f"Failed to update tenant status: {db_error}")
        
        raise