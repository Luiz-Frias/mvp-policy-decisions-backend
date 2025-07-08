#!/bin/bash
# SSL Certificate Monitoring and Management Script
# This script monitors SSL certificate health and renewal status for production domains

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PRODUCTION_DOMAINS=(
    "mvp-policy-decisions-backend-production.up.railway.app"
    # Add custom domain when configured
    # "api.mvp-policy-decisions.com"
)

STAGING_DOMAINS=(
    "mvp-policy-decisions-backend-staging.up.railway.app"
)

# SSL monitoring thresholds
WARNING_DAYS=30  # Warn when certificate expires within 30 days
CRITICAL_DAYS=7  # Critical alert when certificate expires within 7 days

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

check_ssl_certificate() {
    local domain="$1"
    local port="${2:-443}"

    log "Checking SSL certificate for $domain:$port..."

    # Get certificate information
    local cert_info
    if ! cert_info=$(echo | openssl s_client -servername "$domain" -connect "$domain:$port" 2>/dev/null | openssl x509 -noout -dates -subject -issuer 2>/dev/null); then
        log_error "Failed to retrieve certificate for $domain"
        return 1
    fi

    # Extract expiration date
    local expiry_date
    expiry_date=$(echo "$cert_info" | grep "notAfter=" | cut -d= -f2)

    if [ -z "$expiry_date" ]; then
        log_error "Could not parse certificate expiry date for $domain"
        return 1
    fi

    # Convert to epoch time for comparison
    local expiry_epoch
    expiry_epoch=$(date -d "$expiry_date" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "$expiry_date" +%s 2>/dev/null)

    if [ -z "$expiry_epoch" ]; then
        log_error "Could not parse expiry date: $expiry_date"
        return 1
    fi

    local current_epoch
    current_epoch=$(date +%s)

    local days_until_expiry
    days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))

    # Extract subject and issuer
    local subject
    subject=$(echo "$cert_info" | grep "subject=" | cut -d= -f2-)

    local issuer
    issuer=$(echo "$cert_info" | grep "issuer=" | cut -d= -f2-)

    # Check certificate status
    if [ $days_until_expiry -lt 0 ]; then
        log_error "Certificate for $domain has EXPIRED (${days_until_expiry#-} days ago)"
        echo "  Subject: $subject"
        echo "  Issuer: $issuer"
        echo "  Expired: $expiry_date"
        return 2
    elif [ $days_until_expiry -le $CRITICAL_DAYS ]; then
        log_error "Certificate for $domain expires in $days_until_expiry days (CRITICAL)"
        echo "  Subject: $subject"
        echo "  Issuer: $issuer"
        echo "  Expires: $expiry_date"
        return 2
    elif [ $days_until_expiry -le $WARNING_DAYS ]; then
        log_warning "Certificate for $domain expires in $days_until_expiry days (WARNING)"
        echo "  Subject: $subject"
        echo "  Issuer: $issuer"
        echo "  Expires: $expiry_date"
        return 1
    else
        log_success "Certificate for $domain is valid for $days_until_expiry days"
        echo "  Subject: $subject"
        echo "  Issuer: $issuer"
        echo "  Expires: $expiry_date"
        return 0
    fi
}

check_ssl_configuration() {
    local domain="$1"

    log "Checking SSL configuration for $domain..."

    # Test SSL Labs-style checks
    local ssl_output
    if ! ssl_output=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null); then
        log_error "Could not connect to $domain:443"
        return 1
    fi

    # Check protocol version
    local protocol
    protocol=$(echo "$ssl_output" | grep "Protocol" | awk '{print $3}')

    if [[ "$protocol" =~ ^TLSv1\.[23]$ ]]; then
        log_success "Protocol: $protocol (Good)"
    elif [[ "$protocol" =~ ^TLSv1\.1$ ]]; then
        log_warning "Protocol: $protocol (Outdated but acceptable)"
    else
        log_error "Protocol: $protocol (Insecure)"
    fi

    # Check cipher
    local cipher
    cipher=$(echo "$ssl_output" | grep "Cipher" | awk '{print $3}')

    if [[ "$cipher" =~ AES.*GCM|CHACHA20 ]]; then
        log_success "Cipher: $cipher (Strong)"
    elif [[ "$cipher" =~ AES ]]; then
        log_warning "Cipher: $cipher (Acceptable)"
    else
        log_error "Cipher: $cipher (Weak)"
    fi

    # Check for security headers (requires HTTP test)
    check_security_headers "$domain"
}

check_security_headers() {
    local domain="$1"

    log "Checking security headers for $domain..."

    local headers
    if ! headers=$(curl -I -s -m 10 "https://$domain/" 2>/dev/null); then
        log_warning "Could not retrieve headers from $domain"
        return 1
    fi

    # Check for important security headers
    local checks=(
        "strict-transport-security:HSTS"
        "x-content-type-options:X-Content-Type-Options"
        "x-frame-options:X-Frame-Options"
        "x-xss-protection:X-XSS-Protection"
        "content-security-policy:CSP"
    )

    for check in "${checks[@]}"; do
        local header_name="${check%%:*}"
        local display_name="${check##*:}"

        if echo "$headers" | grep -qi "^$header_name:"; then
            log_success "$display_name header present"
        else
            log_warning "$display_name header missing"
        fi
    done
}

test_http_to_https_redirect() {
    local domain="$1"

    log "Testing HTTP to HTTPS redirect for $domain..."

    local http_response
    if http_response=$(curl -I -s -m 10 -L "http://$domain/" 2>/dev/null); then
        if echo "$http_response" | grep -q "HTTP/2 200\|HTTP/1.1 200"; then
            # Check if we got redirected to HTTPS
            if echo "$http_response" | grep -qi "location:.*https://"; then
                log_success "HTTP redirects to HTTPS correctly"
            else
                log_warning "HTTP does not redirect to HTTPS"
            fi
        else
            log_warning "HTTP request did not return 200 OK"
        fi
    else
        log_warning "Could not test HTTP redirect (expected for Railway domains)"
    fi
}

generate_ssl_report() {
    local report_file="ssl_report_$(date +%Y%m%d_%H%M%S).json"

    log "Generating SSL certificate report..."

    cat > "$report_file" << 'EOF'
{
    "report_timestamp": "",
    "domains": [],
    "summary": {
        "total_domains": 0,
        "healthy_certificates": 0,
        "warning_certificates": 0,
        "critical_certificates": 0,
        "expired_certificates": 0
    }
}
EOF

    # Update timestamp
    jq --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '.report_timestamp = $timestamp' "$report_file" > "${report_file}.tmp" && mv "${report_file}.tmp" "$report_file"

    local total_domains=0
    local healthy=0
    local warning=0
    local critical=0
    local expired=0

    # Check production domains
    for domain in "${PRODUCTION_DOMAINS[@]}"; do
        log "Analyzing production domain: $domain"

        local domain_status="unknown"
        local days_until_expiry=0
        local certificate_info=""

        # Get certificate info
        local cert_output
        if cert_output=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -dates -subject -issuer 2>/dev/null); then
            local expiry_date
            expiry_date=$(echo "$cert_output" | grep "notAfter=" | cut -d= -f2)

            if [ -n "$expiry_date" ]; then
                local expiry_epoch
                expiry_epoch=$(date -d "$expiry_date" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "$expiry_date" +%s 2>/dev/null)

                if [ -n "$expiry_epoch" ]; then
                    local current_epoch
                    current_epoch=$(date +%s)
                    days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))

                    if [ $days_until_expiry -lt 0 ]; then
                        domain_status="expired"
                        ((expired++))
                    elif [ $days_until_expiry -le $CRITICAL_DAYS ]; then
                        domain_status="critical"
                        ((critical++))
                    elif [ $days_until_expiry -le $WARNING_DAYS ]; then
                        domain_status="warning"
                        ((warning++))
                    else
                        domain_status="healthy"
                        ((healthy++))
                    fi
                fi
            fi

            certificate_info=$(echo "$cert_output" | tr '\n' ' ')
        fi

        # Add domain to report
        local domain_data
        domain_data=$(jq -n \
            --arg domain "$domain" \
            --arg environment "production" \
            --arg status "$domain_status" \
            --argjson days "$days_until_expiry" \
            --arg cert_info "$certificate_info" \
            --arg check_time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                domain: $domain,
                environment: $environment,
                status: $status,
                days_until_expiry: $days,
                certificate_info: $cert_info,
                last_checked: $check_time
            }')

        jq --argjson domain_data "$domain_data" '.domains += [$domain_data]' "$report_file" > "${report_file}.tmp" && mv "${report_file}.tmp" "$report_file"

        ((total_domains++))
    done

    # Check staging domains
    for domain in "${STAGING_DOMAINS[@]}"; do
        log "Analyzing staging domain: $domain"

        local domain_status="unknown"
        local days_until_expiry=0
        local certificate_info=""

        # Get certificate info (similar logic as production)
        local cert_output
        if cert_output=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -dates -subject -issuer 2>/dev/null); then
            local expiry_date
            expiry_date=$(echo "$cert_output" | grep "notAfter=" | cut -d= -f2)

            if [ -n "$expiry_date" ]; then
                local expiry_epoch
                expiry_epoch=$(date -d "$expiry_date" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "$expiry_date" +%s 2>/dev/null)

                if [ -n "$expiry_epoch" ]; then
                    local current_epoch
                    current_epoch=$(date +%s)
                    days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))

                    if [ $days_until_expiry -lt 0 ]; then
                        domain_status="expired"
                    elif [ $days_until_expiry -le $CRITICAL_DAYS ]; then
                        domain_status="critical"
                    elif [ $days_until_expiry -le $WARNING_DAYS ]; then
                        domain_status="warning"
                    else
                        domain_status="healthy"
                    fi
                fi
            fi

            certificate_info=$(echo "$cert_output" | tr '\n' ' ')
        fi

        # Add staging domain to report
        local domain_data
        domain_data=$(jq -n \
            --arg domain "$domain" \
            --arg environment "staging" \
            --arg status "$domain_status" \
            --argjson days "$days_until_expiry" \
            --arg cert_info "$certificate_info" \
            --arg check_time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                domain: $domain,
                environment: $environment,
                status: $status,
                days_until_expiry: $days,
                certificate_info: $cert_info,
                last_checked: $check_time
            }')

        jq --argjson domain_data "$domain_data" '.domains += [$domain_data]' "$report_file" > "${report_file}.tmp" && mv "${report_file}.tmp" "$report_file"

        ((total_domains++))
    done

    # Update summary
    jq \
        --argjson total "$total_domains" \
        --argjson healthy "$healthy" \
        --argjson warning "$warning" \
        --argjson critical "$critical" \
        --argjson expired "$expired" \
        '.summary = {
            total_domains: $total,
            healthy_certificates: $healthy,
            warning_certificates: $warning,
            critical_certificates: $critical,
            expired_certificates: $expired
        }' "$report_file" > "${report_file}.tmp" && mv "${report_file}.tmp" "$report_file"

    log_success "SSL report generated: $report_file"

    # Display summary
    echo
    log "SSL Certificate Summary:"
    echo "  Total domains: $total_domains"
    echo "  ✅ Healthy: $healthy"
    echo "  ⚠️ Warning: $warning"
    echo "  ❌ Critical: $critical"
    echo "  💀 Expired: $expired"
    echo

    return 0
}

monitor_all_certificates() {
    log "🔒 SSL Certificate Monitoring Report"
    echo "========================================"
    echo

    local overall_status=0

    # Check production domains
    log "Checking production domains..."
    for domain in "${PRODUCTION_DOMAINS[@]}"; do
        if ! check_ssl_certificate "$domain"; then
            overall_status=1
        fi

        check_ssl_configuration "$domain"
        test_http_to_https_redirect "$domain"
        echo
    done

    # Check staging domains
    if [ ${#STAGING_DOMAINS[@]} -gt 0 ]; then
        log "Checking staging domains..."
        for domain in "${STAGING_DOMAINS[@]}"; do
            if ! check_ssl_certificate "$domain"; then
                # Don't fail overall status for staging issues
                log_warning "Staging domain $domain has SSL issues (non-critical)"
            fi
            echo
        done
    fi

    # Generate comprehensive report
    generate_ssl_report

    return $overall_status
}

setup_ssl_monitoring_cron() {
    log "Setting up SSL monitoring cron job..."

    local script_path="$(realpath "$0")"
    local cron_entry="0 6 * * * $script_path monitor >> /var/log/ssl-monitoring.log 2>&1"

    # Check if cron entry already exists
    if crontab -l 2>/dev/null | grep -q "$script_path"; then
        log_warning "SSL monitoring cron job already exists"
        return 0
    fi

    # Add cron entry
    (crontab -l 2>/dev/null; echo "$cron_entry") | crontab -

    log_success "SSL monitoring cron job installed (runs daily at 6 AM)"
    log "Logs will be written to /var/log/ssl-monitoring.log"
}

show_usage() {
    cat << EOF
SSL Certificate Monitoring and Management Script

Usage: $0 [COMMAND] [OPTIONS]

Commands:
  monitor             Check all SSL certificates and generate report
  check <domain>      Check specific domain's SSL certificate
  report              Generate detailed SSL report only
  setup-cron          Set up daily SSL monitoring cron job
  help                Show this help message

Options:
  --warning-days N    Days before expiry to show warning (default: 30)
  --critical-days N   Days before expiry to show critical alert (default: 7)

Examples:
  $0 monitor
  $0 check mvp-policy-decisions-backend-production.up.railway.app
  $0 report
  $0 setup-cron

Environment Variables:
  SSL_WARNING_DAYS    Warning threshold in days (default: 30)
  SSL_CRITICAL_DAYS   Critical threshold in days (default: 7)

Exit Codes:
  0 - All certificates healthy
  1 - Some certificates have warnings
  2 - Some certificates are critical/expired

EOF
}

main() {
    local command="${1:-monitor}"

    case "$command" in
        "monitor"|"check-all")
            monitor_all_certificates
            ;;
        "check")
            if [ -z "$2" ]; then
                log_error "Please specify a domain to check"
                log_error "Usage: $0 check <domain>"
                exit 1
            fi
            check_ssl_certificate "$2"
            check_ssl_configuration "$2"
            ;;
        "report")
            generate_ssl_report
            ;;
        "setup-cron")
            setup_ssl_monitoring_cron
            ;;
        "help"|"--help"|"-h")
            show_usage
            ;;
        *)
            log_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# Handle command line options
while [[ $# -gt 0 ]]; do
    case $1 in
        --warning-days)
            WARNING_DAYS="$2"
            shift 2
            ;;
        --critical-days)
            CRITICAL_DAYS="$2"
            shift 2
            ;;
        *)
            break
            ;;
    esac
done

# Override with environment variables if set
[ -n "$SSL_WARNING_DAYS" ] && WARNING_DAYS="$SSL_WARNING_DAYS"
[ -n "$SSL_CRITICAL_DAYS" ] && CRITICAL_DAYS="$SSL_CRITICAL_DAYS"

# Run main function
main "$@"
