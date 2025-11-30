# Background Workers Service
# RQ-based worker service for asynchronous tasks

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/

# Copy shared modules from parent directory
COPY ../shared /app/shared

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose metrics port
EXPOSE 9091

# Health check (check if worker process is running)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "worker.py" || exit 1

# Run worker
CMD ["python", "-m", "app.worker"]
