#!/bin/bash
# MVP Policy Decision Backend - Demo Quick Start
# This script sets up and runs the complete demo environment

set -e

echo "🚀 Starting MVP Policy Decision Demo Setup..."

# Set demo environment variables
export DATABASE_URL="postgresql://demo_user:demo_pass@localhost:5432/pd_prime_demo"  # pragma: allowlist secret
export REDIS_URL="redis://localhost:6379/0"
export SECRET_KEY="demo-secret-key-change-this-in-production-32chars"  # pragma: allowlist secret
export JWT_SECRET="demo-jwt-secret-change-this-in-production-32chars"  # pragma: allowlist secret
export API_ENV="development"
export API_HOST="0.0.0.0"
export API_PORT="8000"
export API_CORS_ORIGINS='["http://localhost:3000","http://127.0.0.1:3000"]'
export ENABLE_METRICS="true"
export ENABLE_PROFILING="false"

echo "✅ Environment variables set"

# Check if PostgreSQL and Redis are running
echo "🔍 Checking dependencies..."

if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL not found. Please install PostgreSQL 14+"
    echo "   On Ubuntu: sudo apt install postgresql postgresql-contrib"
    echo "   On macOS: brew install postgresql"
    exit 1
fi

if ! command -v redis-cli &> /dev/null; then
    echo "❌ Redis not found. Please install Redis"
    echo "   On Ubuntu: sudo apt install redis-server"
    echo "   On macOS: brew install redis"
    exit 1
fi

# Check if database is running
if ! pg_isready -h localhost -p 5432 &> /dev/null; then
    echo "❌ PostgreSQL is not running. Please start PostgreSQL service"
    echo "   On Ubuntu: sudo systemctl start postgresql"
    echo "   On macOS: brew services start postgresql"
    exit 1
fi

# Check if Redis is running
if ! redis-cli ping &> /dev/null; then
    echo "❌ Redis is not running. Please start Redis service"
    echo "   On Ubuntu: sudo systemctl start redis-server"
    echo "   On macOS: brew services start redis"
    exit 1
fi

echo "✅ Dependencies check passed"

# Function to kill processes using specific ports
cleanup_ports() {
    echo "🧹 Cleaning up any existing processes on ports 8000 and 3000..."

    # Kill any process using port 8000 (backend)
    if lsof -ti:8000 &> /dev/null; then
        echo "  🔄 Killing existing process on port 8000..."
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        sleep 2
    fi

    # Kill any process using port 3000 (frontend)
    if lsof -ti:3000 &> /dev/null; then
        echo "  🔄 Killing existing process on port 3000..."
        lsof -ti:3000 | xargs kill -9 2>/dev/null || true
        sleep 2
    fi

    # Also kill any uvicorn or node processes that might be hanging
    pkill -f "uvicorn.*pd_prime_demo" 2>/dev/null || true
    pkill -f "node.*frontend" 2>/dev/null || true

    echo "✅ Port cleanup complete"
}

# Clean up any existing processes
cleanup_ports

# Create demo database if it doesn't exist
echo "📊 Setting up demo database..."
createdb pd_prime_demo 2>/dev/null || echo "Database already exists, continuing..."

# Create demo user
psql -h localhost -p 5432 -d postgres -c "
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'demo_user') THEN
            CREATE USER demo_user WITH PASSWORD 'demo_pass';  -- pragma: allowlist secret
        END IF;
    END
    \$\$;
" 2>/dev/null || true

psql -h localhost -p 5432 -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE pd_prime_demo TO demo_user;" 2>/dev/null || true

echo "✅ Database setup complete"

# Run database migrations
echo "🔄 Running database migrations..."
uv run alembic upgrade head

echo "✅ Database migrations complete"

# Seed demo data
echo "🌱 Seeding demo data..."
uv run python scripts/seed_data.py

echo "✅ Demo data seeded"

# Start backend server in background
echo "🚀 Starting backend server..."
uv run uvicorn src.pd_prime_demo.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
sleep 5

# Check if backend is responding
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend server started successfully at http://localhost:8000"
    echo "📋 API Documentation: http://localhost:8000/docs"
else
    echo "❌ Backend server failed to start"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# Start frontend server
echo "🎨 Starting frontend server..."
cd frontend
if [ ! -d node_modules ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

# Start frontend in background
npm run dev &
FRONTEND_PID=$!

# Wait for frontend to start
echo "⏳ Waiting for frontend to start..."
sleep 10

if curl -f http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Frontend server started successfully at http://localhost:3000"
else
    echo "❌ Frontend server failed to start"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    exit 1
fi

echo ""
echo "🎉 DEMO IS READY!"
echo "🔗 Frontend: http://localhost:3000"
echo "🔗 Backend API: http://localhost:8000"
echo "📋 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for user interrupt
trap 'echo "🛑 Stopping demo servers..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; exit 0' INT
wait
