#!/usr/bin/env python3
"""
Tenant Management Service
Handles Odoo tenant lifecycle management within the container
"""

import os
import sys
import json
import time
import logging
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify
from threading import Thread
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import redis

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
DB_HOST = os.environ.get('DB_HOST', 'db')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_USER = os.environ.get('DB_USER', 'odoo')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'odoo')
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
TENANT_DB_PREFIX = os.environ.get('TENANT_DB_PREFIX', 'tenant_')
ODOO_MASTER_PASSWORD = os.environ.get('ODOO_MASTER_PASSWORD', 'admin123')

# Initialize Redis connection
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=2, decode_responses=True)
    redis_client.ping()
    logger.info("Connected to Redis")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None

class TenantManager:
    """Manages Odoo tenant operations"""
    
    def __init__(self):
        self.db_host = DB_HOST
        self.db_port = DB_PORT
        self.db_user = DB_USER
        self.db_password = DB_PASSWORD
        
    def get_postgres_connection(self, database=None):
        """Get PostgreSQL connection"""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                user=self.db_user,
                password=self.db_password,
                database=database or 'postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            return conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
    
    def database_exists(self, db_name):
        """Check if database exists"""
        try:
            conn = self.get_postgres_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (db_name,)
            )
            
            exists = cursor.fetchone() is not None
            cursor.close()
            conn.close()
            
            return exists
        except Exception as e:
            logger.error(f"Error checking database existence: {e}")
            return False
    
    def create_database(self, db_name):
        """Create a new database for tenant"""
        try:
            if self.database_exists(db_name):
                logger.info(f"Database {db_name} already exists")
                return True
            
            conn = self.get_postgres_connection()
            cursor = conn.cursor()
            
            # Create database
            cursor.execute(f'CREATE DATABASE "{db_name}" OWNER "{self.db_user}"')
            logger.info(f"Created database: {db_name}")
            
            cursor.close()
            conn.close()
            
            return True
        except Exception as e:
            logger.error(f"Error creating database {db_name}: {e}")
            return False
    
    def drop_database(self, db_name):
        """Drop tenant database"""
        try:
            if not self.database_exists(db_name):
                logger.info(f"Database {db_name} does not exist")
                return True
            
            conn = self.get_postgres_connection()
            cursor = conn.cursor()
            
            # Terminate connections to the database
            cursor.execute("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
            """, (db_name,))
            
            # Drop database
            cursor.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
            logger.info(f"Dropped database: {db_name}")
            
            cursor.close()
            conn.close()
            
            return True
        except Exception as e:
            logger.error(f"Error dropping database {db_name}: {e}")
            return False
    
    def initialize_odoo_database(self, db_name, admin_password='admin'):
        """Initialize Odoo database with base modules"""
        try:
            logger.info(f"Initializing Odoo database: {db_name}")
            
            # Use Odoo CLI to initialize database
            cmd = [
                'python3', '/usr/bin/odoo',
                '-d', db_name,
                '--init', 'base',
                '--stop-after-init',
                '--without-demo', 'all',
                '--db_host', self.db_host,
                '--db_port', str(self.db_port),
                '--db_user', self.db_user,
                '--db_password', self.db_password,
                '--admin-passwd', ODOO_MASTER_PASSWORD
            ]
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if process.returncode == 0:
                logger.info(f"Successfully initialized Odoo database: {db_name}")
                return True
            else:
                logger.error(f"Failed to initialize Odoo database: {process.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout initializing Odoo database: {db_name}")
            return False
        except Exception as e:
            logger.error(f"Error initializing Odoo database {db_name}: {e}")
            return False
    
    def install_module(self, db_name, module_name):
        """Install Odoo module in tenant database"""
        try:
            logger.info(f"Installing module {module_name} in database {db_name}")
            
            cmd = [
                'python3', '/usr/bin/odoo',
                '-d', db_name,
                '--install', module_name,
                '--stop-after-init',
                '--db_host', self.db_host,
                '--db_port', str(self.db_port),
                '--db_user', self.db_user,
                '--db_password', self.db_password,
                '--admin-passwd', ODOO_MASTER_PASSWORD
            ]
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if process.returncode == 0:
                logger.info(f"Successfully installed module {module_name} in {db_name}")
                return True
            else:
                logger.error(f"Failed to install module: {process.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout installing module {module_name} in {db_name}")
            return False
        except Exception as e:
            logger.error(f"Error installing module {module_name}: {e}")
            return False
    
    def uninstall_module(self, db_name, module_name):
        """Uninstall Odoo module from tenant database"""
        try:
            logger.info(f"Uninstalling module {module_name} from database {db_name}")
            
            cmd = [
                'python3', '/usr/bin/odoo',
                '-d', db_name,
                '--uninstall', module_name,
                '--stop-after-init',
                '--db_host', self.db_host,
                '--db_port', str(self.db_port),
                '--db_user', self.db_user,
                '--db_password', self.db_password,
                '--admin-passwd', ODOO_MASTER_PASSWORD
            ]
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if process.returncode == 0:
                logger.info(f"Successfully uninstalled module {module_name} from {db_name}")
                return True
            else:
                logger.error(f"Failed to uninstall module: {process.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout uninstalling module {module_name} from {db_name}")
            return False
        except Exception as e:
            logger.error(f"Error uninstalling module {module_name}: {e}")
            return False
    
    def backup_database(self, db_name, backup_path):
        """Create database backup"""
        try:
            logger.info(f"Creating backup for database {db_name}")
            
            cmd = [
                'pg_dump',
                '-h', self.db_host,
                '-p', str(self.db_port),
                '-U', self.db_user,
                '-f', backup_path,
                '--format=custom',
                '--compress=9',
                db_name
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_password
            
            process = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout
            )
            
            if process.returncode == 0:
                logger.info(f"Successfully created backup: {backup_path}")
                return True
            else:
                logger.error(f"Failed to create backup: {process.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout creating backup for {db_name}")
            return False
        except Exception as e:
            logger.error(f"Error creating backup for {db_name}: {e}")
            return False
    
    def restore_database(self, db_name, backup_path):
        """Restore database from backup"""
        try:
            logger.info(f"Restoring database {db_name} from {backup_path}")
            
            # Create database first
            if not self.create_database(db_name):
                return False
            
            cmd = [
                'pg_restore',
                '-h', self.db_host,
                '-p', str(self.db_port),
                '-U', self.db_user,
                '-d', db_name,
                '--clean',
                '--if-exists',
                backup_path
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_password
            
            process = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout
            )
            
            if process.returncode == 0:
                logger.info(f"Successfully restored database from: {backup_path}")
                return True
            else:
                logger.error(f"Failed to restore database: {process.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout restoring database {db_name}")
            return False
        except Exception as e:
            logger.error(f"Error restoring database {db_name}: {e}")
            return False

# Initialize tenant manager
tenant_manager = TenantManager()

# API Routes
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'tenant-manager',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/tenants/<tenant_id>/create', methods=['POST'])
def create_tenant(tenant_id):
    """Create new tenant database"""
    try:
        data = request.get_json() or {}
        db_name = f"{TENANT_DB_PREFIX}{tenant_id}"
        
        # Create database
        if not tenant_manager.create_database(db_name):
            return jsonify({'error': 'Failed to create database'}), 500
        
        # Initialize Odoo database
        if not tenant_manager.initialize_odoo_database(db_name):
            # Clean up if initialization fails
            tenant_manager.drop_database(db_name)
            return jsonify({'error': 'Failed to initialize Odoo database'}), 500
        
        # Store tenant info in Redis
        if redis_client:
            tenant_info = {
                'tenant_id': tenant_id,
                'db_name': db_name,
                'status': 'active',
                'created_at': datetime.utcnow().isoformat()
            }
            redis_client.hset(f"tenant:{tenant_id}", mapping=tenant_info)
        
        logger.info(f"Successfully created tenant: {tenant_id}")
        
        return jsonify({
            'status': 'success',
            'tenant_id': tenant_id,
            'database': db_name,
            'message': 'Tenant created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating tenant {tenant_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/tenants/<tenant_id>/delete', methods=['DELETE'])
def delete_tenant(tenant_id):
    """Delete tenant database"""
    try:
        db_name = f"{TENANT_DB_PREFIX}{tenant_id}"
        
        # Drop database
        if not tenant_manager.drop_database(db_name):
            return jsonify({'error': 'Failed to delete database'}), 500
        
        # Remove from Redis
        if redis_client:
            redis_client.delete(f"tenant:{tenant_id}")
        
        logger.info(f"Successfully deleted tenant: {tenant_id}")
        
        return jsonify({
            'status': 'success',
            'tenant_id': tenant_id,
            'message': 'Tenant deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting tenant {tenant_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/tenants/<tenant_id>/modules/<module_name>/install', methods=['POST'])
def install_module(tenant_id, module_name):
    """Install module in tenant"""
    try:
        db_name = f"{TENANT_DB_PREFIX}{tenant_id}"
        
        if not tenant_manager.database_exists(db_name):
            return jsonify({'error': 'Tenant database not found'}), 404
        
        if not tenant_manager.install_module(db_name, module_name):
            return jsonify({'error': 'Failed to install module'}), 500
        
        logger.info(f"Successfully installed module {module_name} for tenant {tenant_id}")
        
        return jsonify({
            'status': 'success',
            'tenant_id': tenant_id,
            'module': module_name,
            'message': 'Module installed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error installing module {module_name} for tenant {tenant_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/tenants/<tenant_id>/modules/<module_name>/uninstall', methods=['DELETE'])
def uninstall_module(tenant_id, module_name):
    """Uninstall module from tenant"""
    try:
        db_name = f"{TENANT_DB_PREFIX}{tenant_id}"
        
        if not tenant_manager.database_exists(db_name):
            return jsonify({'error': 'Tenant database not found'}), 404
        
        if not tenant_manager.uninstall_module(db_name, module_name):
            return jsonify({'error': 'Failed to uninstall module'}), 500
        
        logger.info(f"Successfully uninstalled module {module_name} from tenant {tenant_id}")
        
        return jsonify({
            'status': 'success',
            'tenant_id': tenant_id,
            'module': module_name,
            'message': 'Module uninstalled successfully'
        })
        
    except Exception as e:
        logger.error(f"Error uninstalling module {module_name} from tenant {tenant_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/tenants/<tenant_id>/backup', methods=['POST'])
def backup_tenant(tenant_id):
    """Create tenant backup"""
    try:
        db_name = f"{TENANT_DB_PREFIX}{tenant_id}"
        
        if not tenant_manager.database_exists(db_name):
            return jsonify({'error': 'Tenant database not found'}), 404
        
        # Create backup filename with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{tenant_id}_{timestamp}.dump"
        backup_path = f"/opt/odoo/multi-tenant/backups/{backup_filename}"
        
        if not tenant_manager.backup_database(db_name, backup_path):
            return jsonify({'error': 'Failed to create backup'}), 500
        
        logger.info(f"Successfully created backup for tenant {tenant_id}: {backup_filename}")
        
        return jsonify({
            'status': 'success',
            'tenant_id': tenant_id,
            'backup_file': backup_filename,
            'backup_path': backup_path,
            'message': 'Backup created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating backup for tenant {tenant_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('TENANT_SERVICE_PORT', '8080'))
    app.run(host='0.0.0.0', port=port, debug=False)