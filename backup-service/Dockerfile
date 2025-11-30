# Backup Service
# S3-based backup service with KMS encryption

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

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/

# Copy shared modules from parent directory
COPY ../shared /app/shared

# Create necessary directories
RUN mkdir -p /tmp/backups

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose metrics port
EXPOSE 9092

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "backup_service.py" || exit 1

# Run backup service
CMD ["python", "-m", "app.backup_service"]
