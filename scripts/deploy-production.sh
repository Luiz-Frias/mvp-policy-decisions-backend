#!/bin/bash
# Production Deployment Script for Railway
# This script handles full production deployment with health checks and rollback

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PRODUCTION_URL="https://mvp-policy-decisions-backend-production.up.railway.app"
HEALTH_ENDPOINT="/api/v1/health"
READY_ENDPOINT="/api/v1/health/ready"

# Deployment configuration
MAX_HEALTH_CHECK_ATTEMPTS=20
HEALTH_CHECK_INTERVAL=15
ROLLBACK_ON_FAILURE=${ROLLBACK_ON_FAILURE:-true}
DEPLOYMENT_TIMEOUT=${DEPLOYMENT_TIMEOUT:-600}

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✅${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ❌${NC} $1"
}

check_prerequisites() {
    log "Checking deployment prerequisites..."

    # Check if Railway CLI is installed
    if ! command -v railway &> /dev/null; then
        log_error "Railway CLI not found. Installing..."
        curl -fsSL https://railway.app/install.sh | sh
        export PATH="$HOME/.railway/bin:$PATH"
    fi

    # Check if Doppler CLI is installed
    if ! command -v doppler &> /dev/null; then
        log_error "Doppler CLI not found. Please install it:"
        log_error "curl -Ls https://cli.doppler.com/install.sh | sh"
        exit 1
    fi

    # Check if authenticated with Railway
    if ! railway whoami &> /dev/null; then
        log_error "Not authenticated with Railway. Please run: railway login"
        exit 1
    fi

    # Check if authenticated with Doppler
    if ! doppler me &> /dev/null; then
        log_error "Not authenticated with Doppler. Please run: doppler login"
        exit 1
    fi

    # Check if uv is available
    if ! command -v uv &> /dev/null; then
        log_error "uv not found. Please install it:"
        log_error "curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi

    log_success "All prerequisites met"
}

run_pre_deployment_tests() {
    log "Running pre-deployment tests..."

    cd "$PROJECT_ROOT"

    # Install dependencies
    log "Installing dependencies..."
    uv sync --all-extras --dev

    # Run test suite
    log "Running test suite..."
    if ! uv run pytest tests/ -x --tb=short; then
        log_error "Tests failed. Aborting deployment."
        exit 1
    fi

    # Run security checks
    log "Running security checks..."
    if ! uv run bandit -r src/ --severity-level medium; then
        log_error "Security issues detected. Aborting deployment."
        exit 1
    fi

    # Check for dependency vulnerabilities
    log "Checking dependency vulnerabilities..."
    if ! uv run safety check; then
        log_warning "Dependency vulnerabilities detected. Review before deploying."
    fi

    # Run linting
    log "Running code quality checks..."
    uv run black --check src tests || log_warning "Code formatting issues detected"
    uv run isort --check-only src tests || log_warning "Import sorting issues detected"
    uv run mypy src || log_warning "Type checking issues detected"

    log_success "Pre-deployment tests completed"
}

backup_current_deployment() {
    log "Creating backup of current deployment..."

    # Get current deployment info
    CURRENT_DEPLOYMENT=$(railway logs --json 2>/dev/null | head -1 | jq -r '.deployment_id // "unknown"' 2>/dev/null || echo "unknown")

    # Save deployment info
    cat > deployment-backup.json << EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "deployment_id": "$CURRENT_DEPLOYMENT",
    "git_commit": "$(git rev-parse HEAD)",
    "git_branch": "$(git branch --show-current)",
    "production_url": "$PRODUCTION_URL"
}
EOF

    log_success "Backup created: deployment-backup.json"
}

deploy_to_railway() {
    log "Deploying to Railway production..."

    cd "$PROJECT_ROOT"

    # Set production environment
    railway environment production

    # Deploy with timeout
    log "Starting Railway deployment..."

    # Start deployment in background
    railway deploy --detach &
    DEPLOY_PID=$!

    # Wait for deployment with timeout
    DEPLOY_START_TIME=$(date +%s)
    while kill -0 $DEPLOY_PID 2>/dev/null; do
        CURRENT_TIME=$(date +%s)
        ELAPSED=$((CURRENT_TIME - DEPLOY_START_TIME))

        if [ $ELAPSED -gt $DEPLOYMENT_TIMEOUT ]; then
            log_error "Deployment timeout after ${DEPLOYMENT_TIMEOUT}s"
            kill $DEPLOY_PID 2>/dev/null || true
            return 1
        fi

        log "Deployment in progress... (${ELAPSED}s elapsed)"
        sleep 10
    done

    wait $DEPLOY_PID
    DEPLOY_RESULT=$?

    if [ $DEPLOY_RESULT -eq 0 ]; then
        log_success "Railway deployment completed"
        return 0
    else
        log_error "Railway deployment failed"
        return 1
    fi
}

wait_for_deployment() {
    log "Waiting for deployment to be ready..."

    # Wait a bit for Railway to start the new deployment
    sleep 30

    local attempt=1
    while [ $attempt -le $MAX_HEALTH_CHECK_ATTEMPTS ]; do
        log "Health check attempt $attempt/$MAX_HEALTH_CHECK_ATTEMPTS..."

        # Check health endpoint
        if curl -f -s --connect-timeout 10 --max-time 30 "$PRODUCTION_URL$HEALTH_ENDPOINT" > health-check.json; then
            log_success "Health check passed"

            # Verify response structure
            if jq -e '.status == "healthy"' health-check.json > /dev/null 2>&1; then
                log_success "Application is healthy"

                # Check readiness endpoint
                if curl -f -s --connect-timeout 10 --max-time 30 "$PRODUCTION_URL$READY_ENDPOINT" > /dev/null; then
                    log_success "Application is ready"
                    return 0
                else
                    log_warning "Application healthy but not ready yet"
                fi
            else
                log_warning "Health endpoint responded but status not healthy"
                cat health-check.json
            fi
        else
            log_warning "Health check failed"
        fi

        if [ $attempt -eq $MAX_HEALTH_CHECK_ATTEMPTS ]; then
            log_error "Health checks failed after $MAX_HEALTH_CHECK_ATTEMPTS attempts"
            return 1
        fi

        log "Waiting ${HEALTH_CHECK_INTERVAL}s before next attempt..."
        sleep $HEALTH_CHECK_INTERVAL
        attempt=$((attempt + 1))
    done

    return 1
}

run_smoke_tests() {
    log "Running smoke tests..."

    # Test critical endpoints
    ENDPOINTS=(
        "$HEALTH_ENDPOINT"
        "$READY_ENDPOINT"
        "/docs"
        "/openapi.json"
    )

    for endpoint in "${ENDPOINTS[@]}"; do
        log "Testing endpoint: $endpoint"

        if curl -f -s --connect-timeout 10 --max-time 30 "$PRODUCTION_URL$endpoint" > /dev/null; then
            log_success "✅ $endpoint"
        else
            log_error "❌ $endpoint failed"
            return 1
        fi
    done

    # Test database connectivity through API
    log "Testing database connectivity..."
    if curl -f -s "$PRODUCTION_URL$HEALTH_ENDPOINT" | jq -e '.database.status == "connected"' > /dev/null 2>&1; then
        log_success "Database connectivity verified"
    else
        log_error "Database connectivity issues detected"
        return 1
    fi

    # Test Redis connectivity through API
    log "Testing Redis connectivity..."
    if curl -f -s "$PRODUCTION_URL$HEALTH_ENDPOINT" | jq -e '.cache.status == "connected"' > /dev/null 2>&1; then
        log_success "Redis connectivity verified"
    else
        log_warning "Redis connectivity issues detected (non-critical)"
    fi

    log_success "All smoke tests passed"
    return 0
}

run_performance_validation() {
    log "Running performance validation..."

    # Test response times
    local total_time=0
    local count=0
    local max_acceptable_time=2000  # 2 seconds in milliseconds

    for i in {1..5}; do
        start_time=$(date +%s%N)

        if curl -f -s --connect-timeout 10 --max-time 30 "$PRODUCTION_URL$HEALTH_ENDPOINT" > /dev/null; then
            end_time=$(date +%s%N)
            response_time=$(( (end_time - start_time) / 1000000 ))
            total_time=$((total_time + response_time))
            count=$((count + 1))

            log "Response time #$i: ${response_time}ms"

            if [ $response_time -gt $max_acceptable_time ]; then
                log_warning "Slow response detected: ${response_time}ms"
            fi
        else
            log_error "Performance test failed on attempt $i"
        fi
    done

    if [ $count -gt 0 ]; then
        avg_time=$((total_time / count))
        log "Average response time: ${avg_time}ms"

        if [ $avg_time -le 1000 ]; then
            log_success "Performance validation passed (${avg_time}ms < 1000ms)"
            return 0
        elif [ $avg_time -le $max_acceptable_time ]; then
            log_warning "Performance acceptable but could be better (${avg_time}ms)"
            return 0
        else
            log_error "Performance validation failed (${avg_time}ms > ${max_acceptable_time}ms)"
            return 1
        fi
    else
        log_error "Performance validation failed - no successful requests"
        return 1
    fi
}

rollback_deployment() {
    log_error "Rolling back deployment..."

    if [ ! -f deployment-backup.json ]; then
        log_error "No backup information found. Manual rollback required."
        return 1
    fi

    local backup_commit=$(jq -r '.git_commit' deployment-backup.json)

    if [ "$backup_commit" = "null" ] || [ -z "$backup_commit" ]; then
        log_error "No valid backup commit found. Manual rollback required."
        return 1
    fi

    log "Rolling back to commit: $backup_commit"

    # Checkout previous commit
    git checkout "$backup_commit"

    # Deploy previous version
    railway deploy --detach

    log "Rollback deployment initiated. Checking health..."

    # Wait for rollback to complete
    sleep 60

    if wait_for_deployment; then
        log_success "Rollback completed successfully"
        return 0
    else
        log_error "Rollback failed. Manual intervention required."
        return 1
    fi
}

cleanup() {
    log "Cleaning up temporary files..."
    rm -f health-check.json deployment-backup.json
    log_success "Cleanup completed"
}

main() {
    log "🚀 Starting production deployment to Railway"
    log "Target: $PRODUCTION_URL"
    log "Time: $(date)"

    # Set up cleanup trap
    trap cleanup EXIT

    # Check prerequisites
    check_prerequisites

    # Run pre-deployment tests
    run_pre_deployment_tests

    # Create backup
    backup_current_deployment

    # Deploy to Railway
    if ! deploy_to_railway; then
        log_error "Deployment failed"
        exit 1
    fi

    # Wait for deployment to be ready
    if ! wait_for_deployment; then
        log_error "Deployment health checks failed"

        if [ "$ROLLBACK_ON_FAILURE" = "true" ]; then
            rollback_deployment
        fi
        exit 1
    fi

    # Run smoke tests
    if ! run_smoke_tests; then
        log_error "Smoke tests failed"

        if [ "$ROLLBACK_ON_FAILURE" = "true" ]; then
            rollback_deployment
        fi
        exit 1
    fi

    # Run performance validation
    if ! run_performance_validation; then
        log_error "Performance validation failed"

        if [ "$ROLLBACK_ON_FAILURE" = "true" ]; then
            rollback_deployment
        fi
        exit 1
    fi

    log_success "🎉 Production deployment completed successfully!"
    log_success "Application is live at: $PRODUCTION_URL"
    log_success "API Documentation: $PRODUCTION_URL/docs"
    log_success "Health Status: $PRODUCTION_URL$HEALTH_ENDPOINT"

    # Save successful deployment info
    cat > deployment-success.json << EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "git_commit": "$(git rev-parse HEAD)",
    "git_branch": "$(git branch --show-current)",
    "production_url": "$PRODUCTION_URL",
    "deployment_duration": "$(date +%s)",
    "status": "success"
}
EOF

    log_success "Deployment information saved to deployment-success.json"
}

# Handle script arguments
case "${1:-}" in
    "--help"|"-h")
        echo "Production Deployment Script for Railway"
        echo ""
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --help, -h              Show this help message"
        echo "  --no-rollback          Disable automatic rollback on failure"
        echo "  --no-tests             Skip pre-deployment tests"
        echo "  --timeout SECONDS      Set deployment timeout (default: 600)"
        echo ""
        echo "Environment Variables:"
        echo "  ROLLBACK_ON_FAILURE    Enable/disable rollback (default: true)"
        echo "  DEPLOYMENT_TIMEOUT     Deployment timeout in seconds (default: 600)"
        echo ""
        exit 0
        ;;
    "--no-rollback")
        ROLLBACK_ON_FAILURE=false
        shift
        ;;
    "--no-tests")
        SKIP_TESTS=true
        shift
        ;;
    "--timeout")
        DEPLOYMENT_TIMEOUT="$2"
        shift 2
        ;;
esac

# Run main deployment
main "$@"
