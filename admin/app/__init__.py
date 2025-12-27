#!/usr/bin/env python3
"""
Odoo SaaS Platform - Admin Dashboard
Flask application for platform operators with RBAC and comprehensive APIs
"""

import os
import logging
from datetime import timedelta
from flask import Flask, request, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
import redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)

def create_app(config_name=None):
    """Flask application factory"""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(get_config_class(config_name))
    
    # Handle proxy headers (for load balancers)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    
    # Initialize rate limiter
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
        
        # Database
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
        
        # Redis for caching and rate limiting
        REDIS_URL = get_redis_url()
        
        # Rate limiting
        RATELIMIT_STORAGE_URL = get_redis_url()
        RATELIMIT_DEFAULT = os.getenv('RATE_LIMIT_PER_MINUTE', '60/minute')
        
        # CORS
        CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
        
        # Security
        WTF_CSRF_ENABLED = True
        WTF_CSRF_TIME_LIMIT = None
        
        # Application settings
        ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@example.com')
        ITEMS_PER_PAGE = 20
        MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file uploads
        
        # Monitoring
        PROMETHEUS_METRICS = True
        
    class DevelopmentConfig(Config):
        DEBUG = True
        TESTING = False
        
    class ProductionConfig(Config):
        DEBUG = False
        TESTING = False
        
        # Enhanced security for production
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
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s'
    )
    
    # Structured logging for production
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
                }
                
                # Add extra fields from request context
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
            'message': 'Insufficient permissions'
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
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        return jsonify({
            'error': error.name,
            'message': error.description
        }), error.code

def register_jwt_callbacks(app):
    """Register JWT callbacks for user loading and verification"""
    from flask_jwt_extended import get_jwt
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from shared.models import Customer
    
    @jwt.user_identity_loader
    def user_identity_lookup(user):
        """Convert user object to identity for JWT token"""
        if isinstance(user, Customer):
            return str(user.id)
        return str(user)
    
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        """Load user from JWT token identity"""
        identity = jwt_data["sub"]
        return db.session.query(Customer).filter_by(id=identity).one_or_none()
    
    @jwt.additional_claims_loader
    def add_claims_to_jwt(identity):
        """Add custom claims to JWT token"""
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
    
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            'error': 'Token Expired',
            'message': 'The JWT token has expired'
        }), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            'error': 'Invalid Token',
            'message': 'The JWT token is invalid'
        }), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({
            'error': 'Authorization Required',
            'message': 'A valid JWT token is required'
        }), 401

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        """Check if the token has been revoked (in Redis blacklist)"""
        try:
            jti = jwt_payload.get('jti')
            if not jti:
                return False

            redis_url = get_redis_url()
            redis_conn = redis.Redis.from_url(redis_url)
            token_in_blacklist = redis_conn.get(f"token_blacklist:{jti}")
            return token_in_blacklist is not None
        except Exception as e:
            app.logger.warning(f"Error checking token blacklist: {e}")
            return False

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({
            'error': 'Token Revoked',
            'message': 'This token has been revoked. Please login again.'
        }), 401

def register_blueprints(app):
    """Register application blueprints"""
    from admin.app.api import auth_bp, tenants_bp, customers_bp, plans_bp, audit_bp, dashboard_bp, health_bp
    from admin.app.web import web_bp
    
    # API blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(tenants_bp, url_prefix='/api/tenants')
    app.register_blueprint(customers_bp, url_prefix='/api/customers')
    app.register_blueprint(plans_bp, url_prefix='/api/plans')
    app.register_blueprint(audit_bp, url_prefix='/api/audit')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(health_bp, url_prefix='/health')
    
    # Web UI blueprint
    app.register_blueprint(web_bp)

def register_cli_commands(app):
    """Register CLI commands"""
    import click
    
    @app.cli.command()
    @click.option('--seed-demo', is_flag=True, help='Include demo data')
    def init_db(seed_demo):
        """Initialize the database"""
        db.create_all()
        click.echo('✅ Database initialized')
        
        if seed_demo:
            # Run seed script
            import subprocess
            import sys
            result = subprocess.run([
                sys.executable, 'scripts/seed_data.py'
            ], env={**os.environ, 'SEED_DEMO_DATA': 'true'})
            
            if result.returncode == 0:
                click.echo('✅ Demo data seeded')
            else:
                click.echo('❌ Failed to seed demo data')
    
    @app.cli.command()
    def create_admin():
        """Create admin user interactively"""
        click.echo('Creating admin user...')
        
        email = click.prompt('Email')
        password = click.prompt('Password', hide_input=True, confirmation_prompt=True)
        first_name = click.prompt('First Name', default='Admin')
        last_name = click.prompt('Last Name', default='User')
        
        from shared.models import Customer, CustomerRole
        
        admin = Customer(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=CustomerRole.ADMIN.value,
            is_active=True,
            is_verified=True,
            max_tenants=999,
            max_quota_gb=999
        )
        admin.set_password(password)
        
        db.session.add(admin)
        db.session.commit()
        
        click.echo(f'✅ Admin user created: {email}')

# Request middleware for correlation IDs and user context
def setup_request_context():
    """Setup request context with correlation ID and user info"""
    import uuid
    from flask import request, g
    from flask_jwt_extended import get_jwt_identity, jwt_required, verify_jwt_in_request
    
    # Generate correlation ID for request tracing
    g.correlation_id = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
    
    # Try to load current user from JWT
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            g.current_user_id = user_id
    except:
        pass  # No valid JWT token

# Export main components
__all__ = ['create_app', 'db', 'jwt', 'limiter']