#!/usr/bin/env bash
set -eo pipefail

# Multi-tenant Odoo entrypoint script
# Handles tenant-specific configuration and database setup

echo "Starting multi-tenant Odoo setup..."

# Default configuration
DB_HOST=${DB_HOST:-db}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-odoo}
DB_PASSWORD=${DB_PASSWORD:-odoo}
REDIS_HOST=${REDIS_HOST:-redis}
REDIS_PORT=${REDIS_PORT:-6379}

# Multi-tenant specific configuration
TENANT_DB_PREFIX=${TENANT_DB_PREFIX:-tenant_}
ODOO_CONFIG_DIR=${ODOO_CONFIG_DIR:-/opt/odoo/multi-tenant/config}
ODOO_LOG_DIR=${ODOO_LOG_DIR:-/opt/odoo/multi-tenant/logs}
ODOO_FILESTORE_DIR=${ODOO_FILESTORE_DIR:-/opt/odoo/multi-tenant/filestore}

# Create necessary directories
mkdir -p "$ODOO_LOG_DIR"
mkdir -p "$ODOO_FILESTORE_DIR"
mkdir -p "$ODOO_CONFIG_DIR"

# Function to wait for PostgreSQL
wait_for_postgres() {
    echo "Waiting for PostgreSQL to be ready..."
    while ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER"; do
        echo "PostgreSQL is not ready yet, waiting..."
        sleep 2
    done
    echo "PostgreSQL is ready!"
}

# Function to wait for Redis
wait_for_redis() {
    echo "Waiting for Redis to be ready..."
    while ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; do
        echo "Redis is not ready yet, waiting..."
        sleep 2
    done
    echo "Redis is ready!"
}

# Function to generate Odoo configuration
generate_odoo_config() {
    local config_file="$1"
    
    cat > "$config_file" << EOF
[options]
# Database settings
db_host = ${DB_HOST}
db_port = ${DB_PORT}
db_user = ${DB_USER}
db_password = ${DB_PASSWORD}
db_maxconn = 64

# Multi-tenant settings
dbfilter = ^%h$
list_db = False
save_db_password = False

# Server settings
xmlrpc_port = 8069
longpolling_port = 8072
workers = 4
max_cron_threads = 2
limit_memory_hard = 2684354560
limit_memory_soft = 2147483648
limit_request = 8192
limit_time_cpu = 600
limit_time_real = 1200

# File storage
data_dir = ${ODOO_FILESTORE_DIR}

# Logging
log_level = info
log_handler = :INFO
logfile = ${ODOO_LOG_DIR}/odoo.log
log_db = False
log_db_level = warning

# Session storage (Redis)
session_store = redis
session_redis_host = ${REDIS_HOST}
session_redis_port = ${REDIS_PORT}
session_redis_db = 1
session_redis_password = 

# Addons path
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/opt/odoo/addons/custom

# Security
admin_passwd = ${ODOO_MASTER_PASSWORD:-admin123}

# Performance
unaccent = True
without_demo = True

# Multi-processing
proxy_mode = True

# Metrics
enable_metrics = True
metrics_port = 8071
EOF
}

# Function to start tenant management service
start_tenant_service() {
    if [ -d "/opt/odoo/tenant-service" ]; then
        echo "Starting tenant management service..."
        cd /opt/odoo/tenant-service
        python3 app.py &
        TENANT_SERVICE_PID=$!
        echo "Tenant management service started with PID $TENANT_SERVICE_PID"
    fi
}

# Function to handle shutdown
cleanup() {
    echo "Shutting down services..."
    if [ ! -z "$TENANT_SERVICE_PID" ]; then
        kill -TERM "$TENANT_SERVICE_PID" 2>/dev/null || true
        wait "$TENANT_SERVICE_PID" 2>/dev/null || true
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Wait for dependencies
wait_for_postgres
wait_for_redis

# Generate Odoo configuration
ODOO_CONFIG_FILE="$ODOO_CONFIG_DIR/odoo.conf"
generate_odoo_config "$ODOO_CONFIG_FILE"

echo "Odoo configuration generated at $ODOO_CONFIG_FILE"

# Start tenant management service
start_tenant_service

# If first argument is 'odoo', run Odoo with our configuration
if [ "$1" = 'odoo' ]; then
    echo "Starting Odoo with multi-tenant configuration..."

    # Ensure proper permissions (we're running as root now)
    chown -R odoo:odoo "$ODOO_LOG_DIR"
    chown -R odoo:odoo "$ODOO_FILESTORE_DIR"
    chown -R odoo:odoo "$ODOO_CONFIG_DIR"

    # Start Odoo as odoo user using gosu
    echo "Starting Odoo process as odoo user..."
    if command -v gosu &> /dev/null; then
        exec gosu odoo /usr/bin/odoo -c "$ODOO_CONFIG_FILE" --logfile="$ODOO_LOG_DIR/odoo.log"
    else
        # Fallback to su if gosu is not available
        exec su -s /bin/bash odoo -c "/usr/bin/odoo -c $ODOO_CONFIG_FILE --logfile=$ODOO_LOG_DIR/odoo.log"
    fi
else
    # Run custom command
    exec "$@"
fi