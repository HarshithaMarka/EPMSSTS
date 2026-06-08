# Production Dockerfile for EPMSSTS
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements.lock.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY epmssts/ epmssts/
COPY frontend/ frontend/
COPY .env.production.example .env.production.example

# Create outputs directory
RUN mkdir -p outputs artifacts/calibration && useradd -m -u 10001 appuser && chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health/ready || exit 1

# Expose ports
EXPOSE 8000

STOPSIGNAL SIGTERM

# Run API server
CMD ["uvicorn", "epmssts.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "30", "--timeout-graceful-shutdown", "20"]
