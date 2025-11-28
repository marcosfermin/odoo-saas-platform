# Admin Dashboard Service Dockerfile
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

# Install Python dependencies (Flask and essential packages)
RUN pip install --no-cache-dir Flask gunicorn Flask-SQLAlchemy Flask-JWT-Extended \
    Flask-CORS psycopg2-binary python-dotenv prometheus-client structlog redis

# Create logs directory
RUN mkdir -p /app/logs

# Expose ports
EXPOSE 5000 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
