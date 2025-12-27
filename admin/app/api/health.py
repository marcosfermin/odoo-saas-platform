#!/usr/bin/env python3
"""
Health Check API for Admin Dashboard
Provides health and readiness endpoints for monitoring
"""

import os
import sys
from datetime import datetime
from flask import Blueprint, jsonify, current_app
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from admin.app import db
from shared.models import Customer

# Create blueprint
health_bp = Blueprint('health', __name__)

@health_bp.route('/', methods=['GET'])
def health_check():
    """Basic health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'admin-dashboard',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    }), 200

@health_bp.route('/ready', methods=['GET'])
def readiness_check():
    """Readiness check - verifies all dependencies are available"""
    checks = {
        'database': False,
        'redis': False
    }
    overall_status = 'ready'
    
    # Check database connection
    try:
        db.session.execute(text('SELECT 1'))
        checks['database'] = True
        current_app.logger.debug("Database connection check passed")
    except Exception as e:
        checks['database'] = False
        overall_status = 'not ready'
        current_app.logger.error(f"Database connection check failed: {e}")
    
    # Check Redis connection (if configured)
    try:
        import redis
        redis_url = current_app.config.get('REDIS_URL')
        if redis_url:
            r = redis.from_url(redis_url)
            r.ping()
            checks['redis'] = True
            current_app.logger.debug("Redis connection check passed")
        else:
            checks['redis'] = True  # Not configured, so consider it healthy
    except Exception as e:
        checks['redis'] = False
        overall_status = 'not ready'
        current_app.logger.error(f"Redis connection check failed: {e}")
    
    status_code = 200 if overall_status == 'ready' else 503
    
    return jsonify({
        'status': overall_status,
        'service': 'admin-dashboard',
        'timestamp': datetime.utcnow().isoformat(),
        'checks': checks
    }), status_code

@health_bp.route('/live', methods=['GET'])
def liveness_check():
    """Liveness check - basic application responsiveness"""
    try:
        # Perform minimal check
        current_time = datetime.utcnow()
        
        return jsonify({
            'status': 'alive',
            'service': 'admin-dashboard',
            'timestamp': current_time.isoformat(),
            'uptime': current_time.isoformat()  # TODO: Track actual uptime
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Liveness check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'service': 'admin-dashboard',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }), 500

@health_bp.route('/metrics', methods=['GET'])
def metrics():
    """Basic metrics for monitoring"""
    try:
        # Get basic database metrics
        total_customers = db.session.query(Customer).count()
        active_customers = db.session.query(Customer).filter_by(is_active=True).count()
        admin_users = db.session.query(Customer).filter_by(role='admin').count()
        
        return jsonify({
            'service': 'admin-dashboard',
            'timestamp': datetime.utcnow().isoformat(),
            'metrics': {
                'database': {
                    'total_customers': total_customers,
                    'active_customers': active_customers,
                    'admin_users': admin_users
                },
                'application': {
                    'debug_mode': current_app.debug,
                    'environment': os.getenv('FLASK_ENV', 'unknown')
                }
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Metrics collection failed: {e}")
        return jsonify({
            'service': 'admin-dashboard',
            'timestamp': datetime.utcnow().isoformat(),
            'error': 'Failed to collect metrics',
            'details': str(e)
        }), 500

@health_bp.route('/version', methods=['GET'])
def version_info():
    """Version and build information"""
    return jsonify({
        'service': 'admin-dashboard',
        'version': '1.0.0',
        'build_date': '2024-01-01T00:00:00Z',  # TODO: Set actual build date
        'git_commit': 'unknown',  # TODO: Set from CI/CD
        'python_version': sys.version,
        'environment': os.getenv('FLASK_ENV', 'unknown')
    }), 200