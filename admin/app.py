#!/usr/bin/env python3
"""
Odoo SaaS Platform - Admin Dashboard
Main Flask application entry point
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from admin.app import create_app, db

def main():
    """Main application entry point"""
    # Get configuration from environment
    config_name = os.getenv('FLASK_ENV', 'development')
    
    # Create Flask application
    app = create_app(config_name)
    
    # Create database tables if they don't exist
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database tables created/verified")
        except Exception as e:
            print(f"❌ Failed to create database tables: {e}")
            sys.exit(1)
    
    # Run the application
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', '').lower() == 'true'
    
    print(f"🚀 Starting Admin Dashboard on http://{host}:{port}")
    print(f"📝 Environment: {config_name}")
    print(f"🔧 Debug mode: {debug}")
    
    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    main()