# Multi-tenant Odoo Docker Image
# Based on official Odoo image with multi-tenancy enhancements

FROM odoo:16.0

USER root

# Install additional system dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    build-essential \
    libssl-dev \
    libffi-dev \
    postgresql-client \
    redis-tools \
    curl \
    jq \
    nano \
    htop \
    && rm -rf /var/lib/apt/lists/*

# Install additional Python packages for multi-tenancy
RUN pip3 install --no-cache-dir \
    redis \
    boto3 \
    psycopg2-binary \
    requests \
    pyjwt \
    python-dotenv \
    prometheus-client \
    structlog

# Create directories for multi-tenant setup
RUN mkdir -p /opt/odoo/multi-tenant/{config,logs,filestore,backups,scripts}
RUN mkdir -p /opt/odoo/addons/custom
RUN mkdir -p /var/lib/odoo/sessions

# Copy custom configuration and scripts
COPY config/ /opt/odoo/multi-tenant/config/
COPY scripts/ /opt/odoo/multi-tenant/scripts/
COPY addons/ /opt/odoo/addons/custom/

# Copy tenant management service
COPY app/ /opt/odoo/tenant-service/

# Set proper permissions
RUN chown -R odoo:odoo /opt/odoo/multi-tenant
RUN chown -R odoo:odoo /opt/odoo/addons/custom
RUN chown -R odoo:odoo /opt/odoo/tenant-service
RUN chown -R odoo:odoo /var/lib/odoo

# Make scripts executable (if any exist)
RUN find /opt/odoo/multi-tenant/scripts -type f \( -name "*.sh" -o -name "*.py" \) -exec chmod +x {} \; 2>/dev/null || true

# Create entrypoint script for multi-tenant setup
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Environment variables for multi-tenancy
ENV ODOO_MULTI_TENANT=true
ENV ODOO_DB_FILTER=^%h$
ENV ODOO_LIST_DB=false
ENV ODOO_SAVE_DB_PASSWORD=false

# Expose ports
EXPOSE 8069 8071 8072

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8069/web/health || exit 1

# Set the entrypoint (runs as root, then switches to odoo user if needed)
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["odoo"]