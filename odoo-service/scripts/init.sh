#!/bin/bash
set -e

echo "Initializing Odoo multi-tenant service..."

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is up - continuing"

# Wait for Redis to be ready
echo "Waiting for Redis..."
until redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD ping; do
  echo "Redis is unavailable - sleeping"
  sleep 2
done

echo "Redis is up - continuing"

# Set proper permissions
chown -R odoo:odoo /opt/odoo/multi-tenant/

echo "Initialization complete!"
