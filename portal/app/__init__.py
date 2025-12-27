#!/usr/bin/env python3
"""
Odoo SaaS Platform - Customer Portal
Flask application for customer self-service with billing and tenant management
"""

import os
import logging
from datetime import timedelta
from flask import Flask, request, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize extensions (reuse from admin app)
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)

def create_app(config_name=None):
    """Flask application factory for customer portal"""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(get_config_class(config_name))
    
    # Handle proxy headers
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)
    
    # Initialize CORS
    CORS(app, 
         origins=app.config.get('CORS_ALLOWED_ORIGINS', []),
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
         allow_headers=['Content-Type', 'Authorization'],
         supports_credentials=True)
    
    # Configure logging
    configure_logging(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register JWT callbacks
    register_jwt_callbacks(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register CLI commands
    register_cli_commands(app)
    
    return app

def get_config_class(config_name=None):
    """Get configuration class based on environment"""
    config_name = config_name or os.getenv('FLASK_ENV', 'development')
    
    class Config:
        # Flask settings
        SECRET_KEY = os.getenv('SECRET_KEY') or 'dev-secret-change-in-production'
        
        # Database (shared with admin)
        SQLALCHEMY_DATABASE_URI = get_database_url()
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': int(os.getenv('PG_POOL_SIZE', 10)),
            'pool_recycle': 3600,
            'pool_pre_ping': True
        }
        
        # JWT settings
        JWT_SECRET_KEY = os.getenv('SECRET_KEY') or 'jwt-secret-change-in-production'
        JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600)))
        JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', 604800)))
        JWT_ALGORITHM = 'HS256'
        
        # Redis
        REDIS_URL = get_redis_url()
        RATELIMIT_STORAGE_URL = get_redis_url()
        RATELIMIT_DEFAULT = os.getenv('RATE_LIMIT_PER_MINUTE', '60/minute')
        
        # CORS
        CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
        
        # Billing
        STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
        STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
        STRIPE_SIGNING_SECRET = os.getenv('STRIPE_SIGNING_SECRET', '')
        
        PADDLE_PUBLIC_KEY_BASE64 = os.getenv('PADDLE_PUBLIC_KEY_BASE64', '')
        PADDLE_SIGNING_SECRET = os.getenv('PADDLE_SIGNING_SECRET', '')
        
        # Application settings
        ITEMS_PER_PAGE = 20
        MAX_CONTENT_LENGTH = 16 * 1024 * 1024
        DEFAULT_TRIAL_DAYS = int(os.getenv('DEFAULT_TRIAL_DAYS', 14))
        
        # Email
        MAIL_SERVER = os.getenv('SMTP_HOST', 'localhost')
        MAIL_PORT = int(os.getenv('SMTP_PORT', 587))
        MAIL_USE_TLS = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
        MAIL_USERNAME = os.getenv('SMTP_USER', '')
        MAIL_PASSWORD = os.getenv('SMTP_PASSWORD', '')
        MAIL_DEFAULT_SENDER = os.getenv('FROM_EMAIL', 'noreply@example.com')
        
    class DevelopmentConfig(Config):
        DEBUG = True
        TESTING = False
        
    class ProductionConfig(Config):
        DEBUG = False
        TESTING = False
        SESSION_COOKIE_SECURE = True
        SESSION_COOKIE_HTTPONLY = True
        SESSION_COOKIE_SAMESITE = 'Lax'
        
    class TestingConfig(Config):
        TESTING = True
        DEBUG = True
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        SQLALCHEMY_ENGINE_OPTIONS = {}  # SQLite doesn't support pool_size
        WTF_CSRF_ENABLED = False
        
    config_classes = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'testing': TestingConfig
    }
    
    return config_classes.get(config_name, DevelopmentConfig)

def get_database_url():
    """Get database URL from environment"""
    host = os.getenv('PG_HOST', 'localhost')
    port = os.getenv('PG_PORT', '5432')
    user = os.getenv('PG_USER', 'odoo')
    password = os.getenv('PG_PASSWORD', 'password')
    database = os.getenv('PG_DATABASE', 'odoo_saas_platform')
    
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"

def get_redis_url():
    """Get Redis URL from environment"""
    host = os.getenv('REDIS_HOST', 'localhost')
    port = os.getenv('REDIS_PORT', '6379')
    password = os.getenv('REDIS_PASSWORD', '')
    db = os.getenv('REDIS_DB', '0')
    
    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"

def configure_logging(app):
    """Configure application logging"""
    log_level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper())
    
    if not app.debug:
        import json
        import sys
        
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    'timestamp': self.formatTime(record),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'service': 'customer-portal'
                }
                
                if hasattr(g, 'current_user_id'):
                    log_entry['user_id'] = g.current_user_id
                if hasattr(g, 'correlation_id'):
                    log_entry['correlation_id'] = g.correlation_id
                    
                return json.dumps(log_entry)
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        app.logger.addHandler(handler)
        app.logger.setLevel(log_level)

def register_error_handlers(app):
    """Register application error handlers"""
    from flask import jsonify
    from werkzeug.exceptions import HTTPException
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Bad Request',
            'message': str(error.description) if hasattr(error, 'description') else 'Invalid request'
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Authentication required'
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'error': 'Forbidden',
            'message': 'Access denied'
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not Found',
            'message': 'Resource not found'
        }), 404
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({
            'error': 'Too Many Requests',
            'message': 'Rate limit exceeded'
        }), 429
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f'Internal server error: {error}')
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500

def register_jwt_callbacks(app):
    """Register JWT callbacks"""
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from shared.models import Customer
    
    @jwt.user_identity_loader
    def user_identity_lookup(user):
        if isinstance(user, Customer):
            return str(user.id)
        return str(user)
    
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        identity = jwt_data["sub"]
        return db.session.query(Customer).filter_by(id=identity).one_or_none()
    
    @jwt.additional_claims_loader
    def add_claims_to_jwt(identity):
        # Identity can be either a Customer object or a string ID
        if isinstance(identity, Customer):
            user = identity
        else:
            user = db.session.query(Customer).filter_by(id=identity).one_or_none()
        if user:
            return {
                'role': user.role,
                'email': user.email,
                'is_verified': user.is_verified
            }
        return {}

def register_blueprints(app):
    """Register application blueprints"""
    from portal.app.api import (
        auth_bp, tenants_bp, billing_bp, support_bp, 
        webhooks_bp, health_bp
    )
    from portal.app.web import web_bp
    
    # API blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(tenants_bp, url_prefix='/api/tenants')
    app.register_blueprint(billing_bp, url_prefix='/api/billing')
    app.register_blueprint(support_bp, url_prefix='/api/support')
    app.register_blueprint(webhooks_bp, url_prefix='/webhooks')
    app.register_blueprint(health_bp, url_prefix='/health')
    
    # Web UI blueprint
    app.register_blueprint(web_bp)

def register_cli_commands(app):
    """Register CLI commands"""
    import click
    
    @app.cli.command()
    def health_check():
        """Check portal health"""
        try:
            # Test database connection
            db.session.execute('SELECT 1')
            click.echo('✅ Portal health check passed')
        except Exception as e:
            click.echo(f'❌ Portal health check failed: {e}')

__all__ = ['create_app', 'db', 'jwt', 'limiter']