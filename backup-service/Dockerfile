# Backup Service Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    gzip \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY backup-service/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared module
COPY shared/ /app/shared/

# Copy application code
COPY backup-service/ .

# Create backup directories
RUN mkdir -p /tmp/backups

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /tmp/backups

# Switch to non-root user
USER appuser

# Expose metrics port
EXPOSE 9092

# Run backup service
CMD ["python", "-m", "app.backup_service"]
