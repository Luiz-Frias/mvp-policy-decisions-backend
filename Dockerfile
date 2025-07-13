# Multi-stage build for optimal size and security
FROM python:3.11-slim as builder

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files first for better Docker layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies in virtual environment
ENV UV_VENV=/app/.venv
RUN uv sync --frozen --no-dev

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/logs && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser . .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check for Railway/Kubernetes
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/api/v1/health/live || exit 1

# Switch to non-root user
USER appuser

# Expose ports for API and WebSocket
EXPOSE 8080 8081

# Create startup script with proper error handling
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "🚀 Starting MVP Policy Decision Backend - Production"\n\
echo "Environment: $APP_ENV"\n\
echo "API Port: $API_PORT"\n\
echo "WebSocket Port: $WEBSOCKET_PORT"\n\
\n\
# Run database migrations if DATABASE_URL is available\n\
if [ -n "$DATABASE_URL" ]; then\n\
    echo "🔄 Running database migrations..."\n\
    uv run alembic upgrade head || {\n\
        echo "❌ Database migrations failed"\n\
        exit 1\n\
    }\n\
    echo "✅ Database migrations completed"\n\
else\n\
    echo "⚠️ DATABASE_URL not set, skipping migrations"\n\
fi\n\
\n\
# Start the application with proper signal handling\n\
echo "🌐 Starting FastAPI server..."\n\
exec uv run uvicorn src.pd_prime_demo.main:app \\\n\
    --host ${API_HOST:-0.0.0.0} \\\n\
    --port ${API_PORT:-8080} \\\n\
    --workers ${WORKERS:-1} \\\n\
    --log-level ${LOG_LEVEL:-info} \\\n\
    --access-log \\\n\
    --use-colors \\\n\
    --loop uvloop \\\n\
    --http httptools' > /app/start.sh && \
    chmod +x /app/start.sh

# Use the startup script as the default command
CMD ["/app/start.sh"]
