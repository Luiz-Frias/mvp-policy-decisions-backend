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
COPY pyproject.toml uv.lock README.md ./

# Install dependencies in virtual environment
ENV UV_VENV=/app/.venv
RUN uv sync --frozen --no-dev

# Production stage
FROM python:3.11-slim

# Cache bust to force rebuild - UPDATE THIS TO FORCE NEW BUILD
ARG CACHEBUST=20250715-actually-run-the-migrations

# Force rebuild with timestamp
RUN echo "Build timestamp: $(date -u +%Y%m%d-%H%M%S)"

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy uv from the official image (recommended approach)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN chmod +x /bin/uv /bin/uvx

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/logs && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Copy virtual environment from builder stage with correct ownership
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser . .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check for Railway/Kubernetes
# Give migrations plenty of time to complete before health checks start
# start-period: 5 minutes for migrations + app startup
# timeout: 30s for slow queries during migration
# retries: 5 to be more forgiving
HEALTHCHECK --interval=30s --start-period=300s --retries=5 \
    CMD curl -f http://localhost:8080/api/v1/health/live || exit 1

# Switch to non-root user
USER appuser

# Expose ports for API and WebSocket
EXPOSE 8080 8081

# Copy startup scripts
COPY --chown=appuser:appuser migrate.sh /app/migrate.sh
COPY --chown=appuser:appuser start-app.sh /app/start-app.sh
COPY --chown=appuser:appuser app.sh /app/app.sh
RUN chmod +x /app/migrate.sh /app/start-app.sh /app/app.sh

# Default command - Railway will override this with service-specific commands
# migrator service: bash /app/migrate.sh
# api service: bash /app/start-app.sh  
# websocket service: bash /app/start-app.sh
CMD ["/bin/bash", "/app/start-app.sh"]
