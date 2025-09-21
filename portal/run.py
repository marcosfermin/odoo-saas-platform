#!/usr/bin/env python3
"""
Customer Portal Application Entry Point
Main entry point for the customer portal service
"""

import os
import sys
from flask import Flask

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from portal.app import create_app

def create_application():
    """Create Flask application instance"""
    # Determine environment
    env = os.environ.get('FLASK_ENV', 'development')
    
    # Create app with environment-specific config
    app = create_app(env)
    
    return app

# Create the application
app = create_application()

@app.cli.command()
def init_db():
    """Initialize the database"""
    from portal.app import db
    
    print("Creating database tables...")
    db.create_all()
    print("Database initialized successfully!")

@app.cli.command()
def seed_db():
    """Seed the database with initial data"""
    from portal.app import db
    from shared.models import Plan, Customer
    from portal.app.utils.auth import hash_password
    from datetime import datetime
    
    print("Seeding database...")
    
    # Create basic plans if they don't exist
    plans = [
        {
            'name': 'Starter',
            'description': 'Perfect for small businesses getting started',
            'max_users': 5,
            'max_apps': 10,
            'storage_gb': 10,
            'monthly_price': 29.99,
            'annual_price': 299.99,
            'features': ['Basic Support', 'SSL Certificate', 'Daily Backups']
        },
        {
            'name': 'Professional',
            'description': 'Ideal for growing businesses',
            'max_users': 25,
            'max_apps': 50,
            'storage_gb': 100,
            'monthly_price': 99.99,
            'annual_price': 999.99,
            'features': ['Priority Support', 'SSL Certificate', 'Daily Backups', 'Custom Domain']
        },
        {
            'name': 'Enterprise',
            'description': 'Full-featured solution for large organizations',
            'max_users': -1,  # Unlimited
            'max_apps': -1,   # Unlimited
            'storage_gb': 1000,
            'monthly_price': 299.99,
            'annual_price': 2999.99,
            'features': ['24/7 Support', 'SSL Certificate', 'Hourly Backups', 'Custom Domain', 'SLA']
        }
    ]
    
    for plan_data in plans:
        existing = Plan.query.filter_by(name=plan_data['name']).first()
        if not existing:
            plan = Plan(**plan_data)
            db.session.add(plan)
            print(f"Created plan: {plan_data['name']}")
    
    # Create demo customer if it doesn't exist
    demo_email = "demo@example.com"
    existing_customer = Customer.query.filter_by(email=demo_email).first()
    
    if not existing_customer:
        demo_customer = Customer(
            email=demo_email,
            password_hash=hash_password('DemoPassword123!'),
            company_name='Demo Company',
            first_name='Demo',
            last_name='User',
            status='active',
            created_at=datetime.utcnow()
        )
        db.session.add(demo_customer)
        print(f"Created demo customer: {demo_email}")
    
    db.session.commit()
    print("Database seeded successfully!")

@app.cli.command()
def test():
    """Run the tests"""
    import pytest
    
    # Run tests in the tests directory
    test_dir = os.path.join(os.path.dirname(__file__), 'tests')
    if os.path.exists(test_dir):
        pytest.main([test_dir, '-v'])
    else:
        print("Tests directory not found!")

if __name__ == '__main__':
    # Get port from environment or default to 5001
    port = int(os.environ.get('PORT', 5001))
    host = os.environ.get('HOST', '127.0.0.1')
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"Starting Customer Portal on {host}:{port}")
    print(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"Debug mode: {debug}")
    
    app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=debug
    )