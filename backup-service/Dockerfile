# Backup Service Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including PostgreSQL client for backups
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    gzip \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . /app/

# Install Python dependencies (backup service essentials)
RUN pip install --no-cache-dir boto3 psycopg2-binary python-dotenv \
    prometheus-client structlog schedule

# Create directories for backups and logs
RUN mkdir -p /tmp/backups /app/logs

# Expose metrics port
EXPOSE 9092

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:9092/health || exit 1

# Run backup service
CMD ["python", "-m", "app.main"]
