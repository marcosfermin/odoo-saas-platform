# Background Workers Service Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . /app/

# Install Python dependencies (RQ and essential packages)
RUN pip install --no-cache-dir rq redis psycopg2-binary python-dotenv \
    prometheus-client structlog requests

# Create logs directory
RUN mkdir -p /app/logs

# Expose metrics port
EXPOSE 9091

# Health check - check if worker process is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "rq worker" || exit 1

# Run RQ worker
CMD ["python", "-m", "app.worker"]
