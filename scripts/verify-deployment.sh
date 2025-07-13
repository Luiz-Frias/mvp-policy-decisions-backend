#!/bin/bash
# Deployment Verification Script
# This script verifies that the production deployment is working correctly

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PRODUCTION_URL="https://mvp-policy-decisions-backend-production.up.railway.app"
STAGING_URL="https://mvp-policy-decisions-backend-staging.up.railway.app"
TIMEOUT=30
MAX_RETRIES=5

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

test_endpoint() {
    local url="$1"
    local expected_status="${2:-200}"
    local description="${3:-endpoint}"

    log "Testing $description: $url"

    local http_status
    local response_time
    local response_body

    # Capture both status code and response time
    local curl_output
    curl_output=$(curl -w "%{http_code}:%{time_total}" -s -m "$TIMEOUT" "$url" 2>/dev/null || echo "000:0")

    http_status="${curl_output##*:}"
    http_status="${http_status%:*}"
    response_time="${curl_output##*:}"
    response_body="${curl_output%:*}"

    # Remove the status and time from response body
    response_body="${response_body%:*}"

    if [ "$http_status" = "$expected_status" ]; then
        local response_time_ms
        response_time_ms=$(echo "$response_time * 1000" | bc -l 2>/dev/null || echo "0")
        log_success "$description returned $http_status (${response_time_ms%.*}ms)"

        # Check response time performance
        if (( $(echo "$response_time > 2.0" | bc -l) )); then
            log_warning "Slow response time: ${response_time}s"
        fi

        return 0
    else
        log_error "$description returned $http_status (expected $expected_status)"
        log_error "Response: ${response_body:0:200}..."
        return 1
    fi
}

test_health_endpoints() {
    local base_url="$1"
    local environment="$2"

    log "Testing health endpoints for $environment environment..."

    local failed=0

    # Basic health check
    if ! test_endpoint "$base_url/api/v1/health" 200 "basic health check"; then
        ((failed++))
    fi

    # Liveness probe
    if ! test_endpoint "$base_url/api/v1/health/live" 200 "liveness probe"; then
        ((failed++))
    fi

    # Readiness probe (might fail if dependencies are down)
    if ! test_endpoint "$base_url/api/v1/health/ready" 200 "readiness probe"; then
        log_warning "Readiness probe failed - this may indicate dependency issues"
    fi

    # Detailed health check
    if ! test_endpoint "$base_url/api/v1/health/detailed" 200 "detailed health check"; then
        log_warning "Detailed health check failed"
    fi

    return $failed
}

test_api_endpoints() {
    local base_url="$1"
    local environment="$2"

    log "Testing API endpoints for $environment environment..."

    local failed=0

    # OpenAPI documentation
    if ! test_endpoint "$base_url/docs" 200 "API documentation"; then
        ((failed++))
    fi

    # OpenAPI JSON spec
    if ! test_endpoint "$base_url/openapi.json" 200 "OpenAPI specification"; then
        ((failed++))
    fi

    # Test public endpoints (those that don't require authentication)

    # These endpoints typically require authentication, so we expect 401
    if ! test_endpoint "$base_url/api/v1/policies" 401 "policies endpoint (auth required)"; then
        # If we don't get 401, it might be 403 or another auth-related status
        local status
        status=$(curl -s -o /dev/null -w "%{http_code}" -m "$TIMEOUT" "$base_url/api/v1/policies" 2>/dev/null || echo "000")
        if [[ "$status" =~ ^(401|403)$ ]]; then
            log_success "policies endpoint properly requires authentication ($status)"
        else
            log_error "policies endpoint returned unexpected status: $status"
            ((failed++))
        fi
    fi

    return $failed
}

test_performance() {
    local base_url="$1"
    local environment="$2"

    log "Testing performance for $environment environment..."

    local endpoint="$base_url/api/v1/health"
    local total_time=0
    local successful_requests=0
    local failed_requests=0

    log "Running performance test (10 requests)..."

    for i in {1..10}; do
        local start_time
        start_time=$(date +%s.%N)

        if curl -f -s -m "$TIMEOUT" "$endpoint" > /dev/null 2>&1; then
            local end_time
            end_time=$(date +%s.%N)
            local request_time
            request_time=$(echo "$end_time - $start_time" | bc -l)
            total_time=$(echo "$total_time + $request_time" | bc -l)
            ((successful_requests++))

            log "Request $i: ${request_time}s"
        else
            log_error "Request $i failed"
            ((failed_requests++))
        fi

        # Small delay between requests
        sleep 0.1
    done

    if [ $successful_requests -gt 0 ]; then
        local avg_time
        avg_time=$(echo "scale=3; $total_time / $successful_requests" | bc -l)
        local avg_time_ms
        avg_time_ms=$(echo "$avg_time * 1000" | bc -l)

        log "Performance Results:"
        log "  Successful requests: $successful_requests/10"
        log "  Failed requests: $failed_requests/10"
        log "  Average response time: ${avg_time_ms%.*}ms"

        # Check if performance meets requirements
        if (( $(echo "$avg_time < 0.1" | bc -l) )); then
            log_success "Performance excellent (<100ms average)"
        elif (( $(echo "$avg_time < 0.5" | bc -l) )); then
            log_success "Performance good (<500ms average)"
        elif (( $(echo "$avg_time < 1.0" | bc -l) )); then
            log_warning "Performance acceptable (<1s average)"
        else
            log_error "Performance poor (>${avg_time}s average)"
            return 1
        fi

        if [ $failed_requests -eq 0 ]; then
            log_success "100% request success rate"
        else
            local success_rate
            success_rate=$(echo "scale=1; $successful_requests * 100 / 10" | bc -l)
            log_warning "Success rate: ${success_rate}%"
        fi
    else
        log_error "All performance test requests failed"
        return 1
    fi

    return 0
}

test_ssl_certificate() {
    local url="$1"
    local environment="$2"

    log "Testing SSL certificate for $environment environment..."

    # Extract domain from URL
    local domain
    domain=$(echo "$url" | sed 's|https\?://||' | sed 's|/.*||')

    log "Checking SSL certificate for $domain..."

    # Test SSL connection
    local ssl_info
    if ssl_info=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -dates -subject 2>/dev/null); then

        # Extract expiry date
        local expiry_date
        expiry_date=$(echo "$ssl_info" | grep "notAfter=" | cut -d= -f2)

        if [ -n "$expiry_date" ]; then
            local expiry_epoch
            expiry_epoch=$(date -d "$expiry_date" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "$expiry_date" +%s 2>/dev/null)

            if [ -n "$expiry_epoch" ]; then
                local current_epoch
                current_epoch=$(date +%s)
                local days_until_expiry
                days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))

                if [ $days_until_expiry -lt 0 ]; then
                    log_error "SSL certificate has expired!"
                    return 1
                elif [ $days_until_expiry -le 7 ]; then
                    log_error "SSL certificate expires in $days_until_expiry days (critical)"
                    return 1
                elif [ $days_until_expiry -le 30 ]; then
                    log_warning "SSL certificate expires in $days_until_expiry days"
                else
                    log_success "SSL certificate valid for $days_until_expiry days"
                fi

                log "Certificate expires: $expiry_date"
            fi
        fi

        # Extract subject
        local subject
        subject=$(echo "$ssl_info" | grep "subject=" | cut -d= -f2-)
        log "Certificate subject: $subject"

    else
        log_error "Could not retrieve SSL certificate information"
        return 1
    fi

    return 0
}

test_security_headers() {
    local base_url="$1"
    local environment="$2"

    log "Testing security headers for $environment environment..."

    local headers
    if ! headers=$(curl -I -s -m "$TIMEOUT" "$base_url/" 2>/dev/null); then
        log_error "Could not retrieve headers"
        return 1
    fi

    local failed=0

    # Check for important security headers
    if echo "$headers" | grep -qi "strict-transport-security"; then
        log_success "HSTS header present"
    else
        log_warning "HSTS header missing"
        ((failed++))
    fi

    if echo "$headers" | grep -qi "x-content-type-options"; then
        log_success "X-Content-Type-Options header present"
    else
        log_warning "X-Content-Type-Options header missing"
        ((failed++))
    fi

    if echo "$headers" | grep -qi "x-frame-options"; then
        log_success "X-Frame-Options header present"
    else
        log_warning "X-Frame-Options header missing"
        ((failed++))
    fi

    # Check for server header disclosure
    if echo "$headers" | grep -qi "server:"; then
        local server_header
        server_header=$(echo "$headers" | grep -i "server:" | cut -d: -f2- | tr -d ' \r\n')
        if [[ "$server_header" =~ (nginx|apache|iis)/[0-9] ]]; then
            log_warning "Server header discloses version: $server_header"
        else
            log "Server header: $server_header"
        fi
    fi

    return $failed
}

verify_deployment() {
    local environment="$1"
    local base_url="$2"

    log "🚀 Verifying $environment deployment: $base_url"
    echo "================================================"
    echo

    local total_failures=0

    # Test connectivity first
    log "Testing basic connectivity..."
    if ! curl -f -s -m "$TIMEOUT" "$base_url/api/v1/health" > /dev/null; then
        log_error "Cannot connect to $environment deployment"
        return 1
    fi
    log_success "Basic connectivity confirmed"
    echo

    # Test health endpoints
    if ! test_health_endpoints "$base_url" "$environment"; then
        ((total_failures++))
    fi
    echo

    # Test API endpoints
    if ! test_api_endpoints "$base_url" "$environment"; then
        ((total_failures++))
    fi
    echo

    # Test performance
    if ! test_performance "$base_url" "$environment"; then
        ((total_failures++))
    fi
    echo

    # Test SSL certificate
    if ! test_ssl_certificate "$base_url" "$environment"; then
        ((total_failures++))
    fi
    echo

    # Test security headers
    if ! test_security_headers "$base_url" "$environment"; then
        log_warning "Some security headers are missing (non-critical for deployment)"
    fi
    echo

    # Summary
    if [ $total_failures -eq 0 ]; then
        log_success "✅ $environment deployment verification PASSED"
        return 0
    else
        log_error "❌ $environment deployment verification FAILED ($total_failures issues)"
        return 1
    fi
}

show_deployment_info() {
    local environment="$1"
    local base_url="$2"

    log "📋 Deployment Information for $environment"
    echo "================================"

    # Get deployment info from health endpoint
    local health_response
    if health_response=$(curl -s -m "$TIMEOUT" "$base_url/api/v1/health" 2>/dev/null); then

        # Parse JSON response
        if command -v jq &> /dev/null; then
            echo "Environment: $(echo "$health_response" | jq -r '.environment')"
            echo "Version: $(echo "$health_response" | jq -r '.version')"
            echo "Uptime: $(echo "$health_response" | jq -r '.uptime_seconds') seconds"
            echo "Status: $(echo "$health_response" | jq -r '.status')"

            local components
            if components=$(echo "$health_response" | jq -r '.components | keys[]' 2>/dev/null); then
                echo "Components:"
                while IFS= read -r component; do
                    local comp_status
                    comp_status=$(echo "$health_response" | jq -r ".components.${component}.status")
                    echo "  - $component: $comp_status"
                done <<< "$components"
            fi
        else
            echo "Health Response (raw):"
            echo "$health_response" | head -10
        fi
    else
        echo "Could not retrieve deployment information"
    fi

    echo
}

main() {
    local command="${1:-verify-production}"

    case "$command" in
        "verify-production"|"prod")
            show_deployment_info "production" "$PRODUCTION_URL"
            verify_deployment "production" "$PRODUCTION_URL"
            ;;
        "verify-staging"|"staging")
            show_deployment_info "staging" "$STAGING_URL"
            verify_deployment "staging" "$STAGING_URL"
            ;;
        "verify-all"|"all")
            local prod_status=0
            local staging_status=0

            log "🚀 Verifying ALL deployments"
            echo "============================"
            echo

            show_deployment_info "production" "$PRODUCTION_URL"
            if ! verify_deployment "production" "$PRODUCTION_URL"; then
                prod_status=1
            fi

            echo
            echo

            show_deployment_info "staging" "$STAGING_URL"
            if ! verify_deployment "staging" "$STAGING_URL"; then
                staging_status=1
            fi

            echo
            log "📊 Overall Results:"
            if [ $prod_status -eq 0 ]; then
                log_success "Production: PASSED"
            else
                log_error "Production: FAILED"
            fi

            if [ $staging_status -eq 0 ]; then
                log_success "Staging: PASSED"
            else
                log_error "Staging: FAILED"
            fi

            return $((prod_status + staging_status))
            ;;
        "test-endpoint")
            if [ -z "$2" ]; then
                log_error "Please specify endpoint URL to test"
                log_error "Usage: $0 test-endpoint <url>"
                exit 1
            fi
            test_endpoint "$2" 200 "custom endpoint"
            ;;
        "help"|"--help"|"-h")
            cat << EOF
Deployment Verification Script

Usage: $0 [COMMAND] [OPTIONS]

Commands:
  verify-production   Verify production deployment (default)
  verify-staging      Verify staging deployment
  verify-all          Verify both production and staging
  test-endpoint URL   Test a specific endpoint
  help                Show this help message

Examples:
  $0                          # Verify production
  $0 verify-all              # Verify both environments
  $0 test-endpoint https://example.com/api/health

Environment Variables:
  PRODUCTION_URL     Production base URL
  STAGING_URL        Staging base URL
  TIMEOUT            Request timeout in seconds (default: 30)

Exit Codes:
  0 - All verifications passed
  1 - Some verifications failed

EOF
            ;;
        *)
            log_error "Unknown command: $command"
            log_error "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
