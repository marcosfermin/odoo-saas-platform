#!/usr/bin/env python3
"""
Database seed script for Odoo SaaS Platform
Creates default plans and demo data for development/testing
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import models
from shared.models import Base, Customer, Plan, Tenant, AuditLog, CustomerRole, TenantState, AuditAction

def get_database_url() -> str:
    """Get database URL from environment variables"""
    host = os.getenv('PG_HOST', 'localhost')
    port = os.getenv('PG_PORT', '5432')
    user = os.getenv('PG_USER', 'odoo')
    password = os.getenv('PG_PASSWORD', 'password')
    database = os.getenv('PG_DATABASE', 'odoo_saas_platform')
    
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"

def create_default_plans(session) -> dict:
    """Create default billing plans"""
    plans = {}
    
    # Free plan
    free_plan = Plan(
        name="Free",
        description="Perfect for trying out Odoo SaaS with basic features",
        price_monthly=Decimal('0.00'),
        price_yearly=Decimal('0.00'),
        currency='USD',
        max_tenants=1,
        max_users_per_tenant=3,
        max_db_size_gb=1,
        max_filestore_gb=1,
        features={
            "custom_domain": False,
            "backup_retention_days": 7,
            "support_level": "community",
            "api_access": False,
            "advanced_reporting": False
        },
        allowed_modules=[
            "base", "web", "mail", "contacts", "calendar",
            "note", "portal", "website"
        ],
        trial_days=0,
        is_active=True
    )
    session.add(free_plan)
    plans['free'] = free_plan
    
    # Starter plan
    starter_plan = Plan(
        name="Starter",
        description="Great for small businesses getting started with Odoo",
        price_monthly=Decimal('29.00'),
        price_yearly=Decimal('290.00'),  # 2 months free
        currency='USD',
        max_tenants=1,
        max_users_per_tenant=10,
        max_db_size_gb=5,
        max_filestore_gb=5,
        features={
            "custom_domain": True,
            "backup_retention_days": 30,
            "support_level": "email",
            "api_access": True,
            "advanced_reporting": False,
            "ssl_certificates": True
        },
        allowed_modules=[
            "base", "web", "mail", "contacts", "calendar",
            "sale", "crm", "project", "hr", "account",
            "stock", "purchase", "website", "portal", "note"
        ],
        trial_days=14,
        is_active=True
    )
    session.add(starter_plan)
    plans['starter'] = starter_plan
    
    # Professional plan
    pro_plan = Plan(
        name="Professional",
        description="Advanced features for growing businesses",
        price_monthly=Decimal('79.00'),
        price_yearly=Decimal('790.00'),  # 2 months free
        currency='USD',
        max_tenants=3,
        max_users_per_tenant=25,
        max_db_size_gb=20,
        max_filestore_gb=20,
        features={
            "custom_domain": True,
            "backup_retention_days": 90,
            "support_level": "priority",
            "api_access": True,
            "advanced_reporting": True,
            "ssl_certificates": True,
            "white_labeling": True,
            "multiple_tenants": True
        },
        allowed_modules=[
            "base", "web", "mail", "contacts", "calendar",
            "sale", "crm", "project", "hr", "account",
            "stock", "purchase", "website", "portal", "note",
            "mrp", "maintenance", "fleet", "helpdesk",
            "marketing_automation", "social", "survey"
        ],
        trial_days=14,
        is_active=True
    )
    session.add(pro_plan)
    plans['professional'] = pro_plan
    
    # Enterprise plan
    enterprise_plan = Plan(
        name="Enterprise",
        description="Full-featured solution for large organizations",
        price_monthly=Decimal('199.00'),
        price_yearly=Decimal('1990.00'),  # 2 months free
        currency='USD',
        max_tenants=10,
        max_users_per_tenant=100,
        max_db_size_gb=100,
        max_filestore_gb=100,
        features={
            "custom_domain": True,
            "backup_retention_days": 365,
            "support_level": "phone",
            "api_access": True,
            "advanced_reporting": True,
            "ssl_certificates": True,
            "white_labeling": True,
            "multiple_tenants": True,
            "dedicated_support": True,
            "sla_99_9": True,
            "custom_modules": True
        },
        allowed_modules="*",  # All modules allowed
        trial_days=30,
        is_active=True
    )
    session.add(enterprise_plan)
    plans['enterprise'] = enterprise_plan
    
    session.commit()
    print(f"✅ Created {len(plans)} default plans")
    return plans

def create_demo_customer(session, plans: dict) -> Customer:
    """Create demo customer account"""
    demo_customer = Customer(
        email="demo@example.com",
        first_name="Demo",
        last_name="User",
        company="Demo Company",
        phone="+1-555-0123",
        role=CustomerRole.OWNER.value,
        is_active=True,
        is_verified=True,
        max_tenants=5,
        max_quota_gb=100,
        email_verified_at=datetime.utcnow()
    )
    demo_customer.set_password("demo123")
    session.add(demo_customer)
    session.commit()
    
    # Log customer creation
    audit_log = AuditLog(
        actor_id=demo_customer.id,
        actor_email=demo_customer.email,
        actor_role=demo_customer.role,
        action=AuditAction.CREATE.value,
        resource_type="customer",
        resource_id=str(demo_customer.id),
        new_values={
            "email": demo_customer.email,
            "company": demo_customer.company
        },
        metadata={
            "source": "seed_data",
            "demo": True
        }
    )
    session.add(audit_log)
    session.commit()
    
    print(f"✅ Created demo customer: {demo_customer.email}")
    return demo_customer

def create_admin_customer(session) -> Customer:
    """Create admin customer account"""
    admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
    admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    admin_customer = Customer(
        email=admin_email,
        first_name="Platform",
        last_name="Admin",
        company="Odoo SaaS Platform",
        role=CustomerRole.ADMIN.value,
        is_active=True,
        is_verified=True,
        max_tenants=999,  # Unlimited for admin
        max_quota_gb=999,
        email_verified_at=datetime.utcnow()
    )
    admin_customer.set_password(admin_password)
    session.add(admin_customer)
    session.commit()
    
    # Log admin creation
    audit_log = AuditLog(
        actor_id=admin_customer.id,
        actor_email=admin_customer.email,
        actor_role=admin_customer.role,
        action=AuditAction.CREATE.value,
        resource_type="customer",
        resource_id=str(admin_customer.id),
        new_values={
            "email": admin_customer.email,
            "role": admin_customer.role
        },
        metadata={
            "source": "seed_data",
            "admin": True
        }
    )
    session.add(audit_log)
    session.commit()
    
    print(f"✅ Created admin customer: {admin_customer.email}")
    return admin_customer

def create_demo_tenants(session, customer: Customer, plans: dict) -> list:
    """Create demo tenant instances"""
    tenants = []
    
    # Demo tenant on starter plan
    demo_tenant = Tenant(
        slug="demo-company",
        name="Demo Company Instance",
        customer_id=customer.id,
        plan_id=plans['starter'].id,
        state=TenantState.ACTIVE.value,
        db_name="tenant_demo_company",
        filestore_path="/var/lib/odoo/filestore/demo-company",
        current_users=3,
        db_size_bytes=104857600,  # 100MB
        filestore_size_bytes=52428800,  # 50MB
        odoo_version="16.0",
        installed_modules=[
            "base", "web", "mail", "contacts", "sale", "crm"
        ]
    )
    session.add(demo_tenant)
    tenants.append(demo_tenant)
    
    # Development tenant on free plan
    dev_tenant = Tenant(
        slug="demo-dev",
        name="Demo Development",
        customer_id=customer.id,
        plan_id=plans['free'].id,
        state=TenantState.ACTIVE.value,
        db_name="tenant_demo_dev",
        filestore_path="/var/lib/odoo/filestore/demo-dev",
        current_users=1,
        db_size_bytes=20971520,   # 20MB
        filestore_size_bytes=10485760,  # 10MB
        odoo_version="16.0",
        installed_modules=["base", "web", "mail", "contacts"]
    )
    session.add(dev_tenant)
    tenants.append(dev_tenant)
    
    session.commit()
    
    # Log tenant creation
    for tenant in tenants:
        audit_log = AuditLog(
            actor_id=customer.id,
            actor_email=customer.email,
            actor_role=customer.role,
            action=AuditAction.CREATE.value,
            resource_type="tenant",
            resource_id=str(tenant.id),
            new_values={
                "slug": tenant.slug,
                "name": tenant.name,
                "plan": plans['starter'].name if tenant == demo_tenant else plans['free'].name
            },
            metadata={
                "source": "seed_data",
                "demo": True
            }
        )
        session.add(audit_log)
    
    session.commit()
    print(f"✅ Created {len(tenants)} demo tenants")
    return tenants

def main():
    """Main seeding function"""
    print("🌱 Starting database seeding...")
    
    # Connect to database
    engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check if already seeded
        existing_plans = session.query(Plan).count()
        if existing_plans > 0 and not os.getenv('RESEED_DATA', '').lower() == 'true':
            print("⚠️  Database already seeded. Set RESEED_DATA=true to override.")
            return
        
        # Clear existing data if reseeding
        if os.getenv('RESEED_DATA', '').lower() == 'true':
            print("🗑️  Clearing existing seed data...")
            session.query(AuditLog).delete()
            session.query(Tenant).delete()
            session.query(Customer).delete()
            session.query(Plan).delete()
            session.commit()
        
        # Create default plans
        plans = create_default_plans(session)
        
        # Create demo data if requested
        if os.getenv('SEED_DEMO_DATA', '').lower() == 'true':
            print("🎭 Creating demo data...")
            
            # Create demo customer
            demo_customer = create_demo_customer(session, plans)
            
            # Create admin customer
            admin_customer = create_admin_customer(session)
            
            # Create demo tenants
            create_demo_tenants(session, demo_customer, plans)
        
        print("✅ Database seeding completed successfully!")
        
        # Print summary
        plan_count = session.query(Plan).count()
        customer_count = session.query(Customer).count()
        tenant_count = session.query(Tenant).count()
        
        print(f"""
📊 Database Summary:
   - Plans: {plan_count}
   - Customers: {customer_count}
   - Tenants: {tenant_count}
        """)
        
        if os.getenv('SEED_DEMO_DATA', '').lower() == 'true':
            print("""
🔑 Demo Credentials:
   - Demo User: demo@example.com / demo123
   - Admin User: admin@example.com / admin123
            """)
    
    except Exception as e:
        print(f"❌ Error during seeding: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()