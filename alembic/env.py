#!/usr/bin/env python3
"""
Alembic environment configuration for Odoo SaaS Platform
Handles database migrations with proper environment loading
"""

from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

# Import models
from shared.models import Base

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for 'autogenerate' support
target_metadata = Base.metadata

def get_database_url() -> str:
    """Get database URL from environment variables"""
    host = os.getenv('PG_HOST', 'localhost')
    port = os.getenv('PG_PORT', '5432')
    user = os.getenv('PG_USER', 'odoo')
    password = os.getenv('PG_PASSWORD', 'password')
    database = os.getenv('PG_DATABASE', 'odoo_saas_platform')
    
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    
    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.
    
    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Include object names in diffs
        compare_type=True,
        compare_server_default=True,
        # Ensure we create indexes
        include_object=include_object
    )

    with context.begin_transaction():
        context.run_migrations()

def include_object(object, name, type_, reflected, compare_to):
    """Include/exclude objects from migration"""
    # Skip certain system tables
    if type_ == "table" and name in ['spatial_ref_sys']:
        return False
    return True

def run_migrations_online() -> None:
    """Run migrations in 'online' mode.
    
    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Override config with environment variables
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = get_database_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Include object names in diffs
            compare_type=True,
            compare_server_default=True,
            # Ensure we create indexes
            include_object=include_object,
            # Transactional migrations
            transaction_per_migration=True
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()