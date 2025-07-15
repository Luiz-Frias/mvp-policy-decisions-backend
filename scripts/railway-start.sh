#!/bin/bash
set -e

echo "🚀 Starting MVP Policy Decision Backend on Railway"
echo "Environment: Production (Railway)"
echo "Using Doppler for secrets management"

# Install Doppler CLI if not present
if ! command -v doppler &> /dev/null; then
    echo "📦 Installing Doppler CLI..."
    curl -Ls --tlsv1.2 --proto "=https" --retry 3 https://cli.doppler.com/install.sh | sh
fi

# Configure PgBouncer connection string from Railway's DATABASE_URL
if [ -n "$DATABASE_URL" ]; then
    echo "🔗 Configuring PgBouncer connection..."
    # Parse DATABASE_URL to get components for PgBouncer
    # Format: postgresql://user:password@host:port/database
    export PGBOUNCER_DATABASE_URL="postgresql://${DATABASE_USER}:${DATABASE_PASSWORD}@localhost:6432/${DATABASE_NAME}"
fi

# Start PgBouncer in the background (lightweight process)
if [ "$PGBOUNCER_ENABLED" = "true" ]; then
    echo "🏊 Starting PgBouncer..."
    # Generate PgBouncer config dynamically
    cat > /tmp/pgbouncer.ini <<EOF
[databases]
${DATABASE_NAME} = host=${DATABASE_HOST} port=${DATABASE_PORT} dbname=${DATABASE_NAME}

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
auth_type = trust
pool_mode = transaction
max_client_conn = ${PGBOUNCER_MAX_CLIENT_CONN:-100}
default_pool_size = ${PGBOUNCER_DEFAULT_POOL_SIZE:-10}
min_pool_size = ${PGBOUNCER_MIN_POOL_SIZE:-2}
server_lifetime = 3600
server_idle_timeout = 600
log_connections = 1
log_disconnections = 1
EOF
    
    # Start PgBouncer
    pgbouncer -d /tmp/pgbouncer.ini
    
    # Wait for PgBouncer to be ready
    sleep 2
    
    # Update database URL to use PgBouncer
    export DATABASE_URL=$PGBOUNCER_DATABASE_URL
fi

# Run migrations through Doppler
echo "🔄 Running database migrations..."
doppler run --config prd -- uv run alembic upgrade head || {
    echo "❌ Database migrations failed"
    exit 1
}

# Start the application through Doppler
echo "🌐 Starting FastAPI server with Doppler..."
exec doppler run --config prd -- uv run uvicorn src.policy_core.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8080} \
    --workers 1 \
    --log-level info \
    --access-log \
    --loop uvloop