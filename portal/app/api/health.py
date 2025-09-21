#!/usr/bin/env python3
"""
Health Check API
Provides health status endpoints for the customer portal
"""

from datetime import datetime
from flask import Blueprint, jsonify

# Create blueprint
health_bp = Blueprint('health', __name__)

@health_bp.route('/', methods=['GET'])
def health_check():
    """Main health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'customer-portal',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    }), 200

@health_bp.route('/ready', methods=['GET'])
def readiness_check():
    """Readiness check for Kubernetes"""
    return jsonify({
        'status': 'ready',
        'service': 'customer-portal',
        'timestamp': datetime.utcnow().isoformat()
    }), 200

@health_bp.route('/live', methods=['GET'])
def liveness_check():
    """Liveness check for Kubernetes"""
    return jsonify({
        'status': 'alive',
        'service': 'customer-portal',
        'timestamp': datetime.utcnow().isoformat()
    }), 200