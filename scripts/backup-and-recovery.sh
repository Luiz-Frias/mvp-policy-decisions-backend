#!/bin/bash
# Backup and Disaster Recovery Script for Railway Production
# This script handles database backups, configuration backups, and disaster recovery procedures

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
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
RETENTION_DAYS=${RETENTION_DAYS:-30}
PRODUCTION_URL="https://mvp-policy-decisions-backend-production.up.railway.app"

# Backup configuration
MAX_BACKUP_SIZE_GB=${MAX_BACKUP_SIZE_GB:-10}
COMPRESSION_LEVEL=${COMPRESSION_LEVEL:-6}
ENCRYPT_BACKUPS=${ENCRYPT_BACKUPS:-true}
GPG_RECIPIENT=${GPG_RECIPIENT:-"backup@mvp-policy-decisions.com"}

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
    log "Checking backup prerequisites..."

    # Check if Doppler CLI is installed
    if ! command -v doppler &> /dev/null; then
        log_error "Doppler CLI not found. Please install it:"
        log_error "curl -Ls https://cli.doppler.com/install.sh | sh"
        exit 1
    fi

    # Check if authenticated with Doppler
    if ! doppler me &> /dev/null; then
        log_error "Not authenticated with Doppler. Please run: doppler login"
        exit 1
    fi

    # Check if PostgreSQL client is available
    if ! command -v pg_dump &> /dev/null; then
        log_error "PostgreSQL client (pg_dump) not found. Installing..."
        # Try to install postgresql-client
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y postgresql-client
        elif command -v yum &> /dev/null; then
            sudo yum install -y postgresql
        else
            log_error "Please install PostgreSQL client manually"
            exit 1
        fi
    fi

    # Check if GPG is available for encryption
    if [ "$ENCRYPT_BACKUPS" = "true" ] && ! command -v gpg &> /dev/null; then
        log_error "GPG not found but encryption is enabled. Installing..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y gnupg
        else
            log_warning "GPG not available. Disabling encryption."
            ENCRYPT_BACKUPS=false
        fi
    fi

    # Create backup directory
    mkdir -p "$BACKUP_DIR"

    log_success "Prerequisites check completed"
}

create_backup_metadata() {
    local backup_name="$1"
    local backup_type="$2"
    local backup_file="$3"

    cat > "$BACKUP_DIR/${backup_name}.metadata.json" << EOF
{
    "backup_name": "$backup_name",
    "backup_type": "$backup_type",
    "backup_file": "$backup_file",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
    "git_branch": "$(git branch --show-current 2>/dev/null || echo 'unknown')",
    "production_url": "$PRODUCTION_URL",
    "size_bytes": $(stat -c%s "$backup_file" 2>/dev/null || echo 0),
    "checksum_sha256": "$(sha256sum "$backup_file" | cut -d' ' -f1)",
    "encrypted": $ENCRYPT_BACKUPS,
    "compression_level": $COMPRESSION_LEVEL,
    "created_by": "$(whoami)@$(hostname)",
    "retention_until": "$(date -u -d "+${RETENTION_DAYS} days" +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
}

backup_database() {
    log "Starting database backup..."

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_name="database_${timestamp}"
    local backup_file="$BACKUP_DIR/${backup_name}.sql"

    # Get database URL from Doppler
    local database_url
    database_url=$(doppler secrets get DATABASE_URL --plain) || {
        log_error "Failed to get DATABASE_URL from Doppler"
        return 1
    }

    log "Creating database dump..."

    # Create database backup with compression
    if ! pg_dump "$database_url" \
        --verbose \
        --clean \
        --if-exists \
        --create \
        --format=custom \
        --compress=$COMPRESSION_LEVEL \
        --file="$backup_file"; then
        log_error "Database backup failed"
        return 1
    fi

    # Check backup size
    local backup_size_mb
    backup_size_mb=$(du -m "$backup_file" | cut -f1)
    local backup_size_gb=$(echo "scale=2; $backup_size_mb / 1024" | bc -l)

    log "Database backup size: ${backup_size_gb}GB"

    if (( $(echo "$backup_size_gb > $MAX_BACKUP_SIZE_GB" | bc -l) )); then
        log_error "Backup size (${backup_size_gb}GB) exceeds maximum (${MAX_BACKUP_SIZE_GB}GB)"
        rm -f "$backup_file"
        return 1
    fi

    # Encrypt backup if enabled
    if [ "$ENCRYPT_BACKUPS" = "true" ]; then
        log "Encrypting database backup..."

        if ! gpg --trust-model always --encrypt --recipient "$GPG_RECIPIENT" \
            --cipher-algo AES256 --compress-algo 2 \
            --output "${backup_file}.gpg" "$backup_file"; then
            log_error "Backup encryption failed"
            return 1
        fi

        # Remove unencrypted backup
        rm -f "$backup_file"
        backup_file="${backup_file}.gpg"
        log_success "Database backup encrypted"
    fi

    # Create metadata
    create_backup_metadata "$backup_name" "database" "$backup_file"

    log_success "Database backup completed: $backup_file"
    return 0
}

backup_application_state() {
    log "Starting application state backup..."

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_name="appstate_${timestamp}"
    local backup_file="$BACKUP_DIR/${backup_name}.tar.gz"

    cd "$PROJECT_ROOT"

    # Create application state backup
    log "Creating application state archive..."

    tar -czf "$backup_file" \
        --exclude="node_modules" \
        --exclude=".git" \
        --exclude="__pycache__" \
        --exclude="*.pyc" \
        --exclude=".pytest_cache" \
        --exclude="backups" \
        --exclude="logs" \
        --exclude="tmp" \
        --exclude=".venv" \
        --exclude="venv" \
        .

    # Encrypt if enabled
    if [ "$ENCRYPT_BACKUPS" = "true" ]; then
        log "Encrypting application state backup..."

        if ! gpg --trust-model always --encrypt --recipient "$GPG_RECIPIENT" \
            --cipher-algo AES256 --compress-algo 2 \
            --output "${backup_file}.gpg" "$backup_file"; then
            log_error "Application state encryption failed"
            return 1
        fi

        rm -f "$backup_file"
        backup_file="${backup_file}.gpg"
    fi

    # Create metadata
    create_backup_metadata "$backup_name" "application_state" "$backup_file"

    log_success "Application state backup completed: $backup_file"
    return 0
}

backup_secrets() {
    log "Starting secrets backup..."

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_name="secrets_${timestamp}"
    local backup_file="$BACKUP_DIR/${backup_name}.json"

    # Export secrets from Doppler (this will be encrypted)
    log "Exporting secrets from Doppler..."

    if ! doppler secrets download --format json --no-file > "$backup_file"; then
        log_error "Failed to export secrets from Doppler"
        return 1
    fi

    # Always encrypt secrets backup
    log "Encrypting secrets backup..."

    if ! gpg --trust-model always --encrypt --recipient "$GPG_RECIPIENT" \
        --cipher-algo AES256 --compress-algo 2 \
        --output "${backup_file}.gpg" "$backup_file"; then
        log_error "Secrets encryption failed"
        rm -f "$backup_file"
        return 1
    fi

    # Remove unencrypted secrets
    rm -f "$backup_file"
    backup_file="${backup_file}.gpg"

    # Create metadata
    create_backup_metadata "$backup_name" "secrets" "$backup_file"

    log_success "Secrets backup completed: $backup_file"
    return 0
}

backup_logs() {
    log "Starting logs backup..."

    # For Railway, we'll need to use their CLI to get logs
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_name="logs_${timestamp}"
    local backup_file="$BACKUP_DIR/${backup_name}.log"

    # Check if railway CLI is available
    if command -v railway &> /dev/null; then
        log "Downloading recent logs from Railway..."

        # Get last 1000 lines of logs
        if railway logs --lines 1000 > "$backup_file" 2>/dev/null; then

            # Compress logs
            gzip "$backup_file"
            backup_file="${backup_file}.gz"

            # Encrypt if enabled
            if [ "$ENCRYPT_BACKUPS" = "true" ]; then
                if gpg --trust-model always --encrypt --recipient "$GPG_RECIPIENT" \
                    --cipher-algo AES256 --compress-algo 2 \
                    --output "${backup_file}.gpg" "$backup_file"; then
                    rm -f "$backup_file"
                    backup_file="${backup_file}.gpg"
                fi
            fi

            # Create metadata
            create_backup_metadata "$backup_name" "logs" "$backup_file"

            log_success "Logs backup completed: $backup_file"
        else
            log_warning "Failed to download logs from Railway"
            rm -f "$backup_file"
        fi
    else
        log_warning "Railway CLI not available, skipping logs backup"
    fi
}

cleanup_old_backups() {
    log "Cleaning up old backups (retention: ${RETENTION_DAYS} days)..."

    local deleted_count=0

    # Find and remove old backup files
    while IFS= read -r -d '' file; do
        if [ -f "$file" ]; then
            log "Deleting old backup: $(basename "$file")"
            rm -f "$file"

            # Also remove corresponding metadata file
            local metadata_file="${file%.gpg}.metadata.json"
            [ -f "$metadata_file" ] && rm -f "$metadata_file"

            ((deleted_count++))
        fi
    done < <(find "$BACKUP_DIR" -type f \( -name "*.sql" -o -name "*.tar.gz" -o -name "*.json" -o -name "*.log.gz" -o -name "*.gpg" \) -mtime "+${RETENTION_DAYS}" -print0)

    if [ $deleted_count -gt 0 ]; then
        log_success "Cleaned up $deleted_count old backup files"
    else
        log "No old backups to clean up"
    fi
}

verify_backup_integrity() {
    local backup_file="$1"
    local metadata_file="$2"

    log "Verifying backup integrity for $(basename "$backup_file")..."

    # Check if files exist
    if [ ! -f "$backup_file" ] || [ ! -f "$metadata_file" ]; then
        log_error "Backup or metadata file missing"
        return 1
    fi

    # Verify checksum
    local stored_checksum
    stored_checksum=$(jq -r '.checksum_sha256' "$metadata_file")

    local actual_checksum
    actual_checksum=$(sha256sum "$backup_file" | cut -d' ' -f1)

    if [ "$stored_checksum" != "$actual_checksum" ]; then
        log_error "Checksum mismatch for backup file"
        log_error "Stored: $stored_checksum"
        log_error "Actual: $actual_checksum"
        return 1
    fi

    # Test encryption if backup is encrypted
    local is_encrypted
    is_encrypted=$(jq -r '.encrypted' "$metadata_file")

    if [ "$is_encrypted" = "true" ] && [[ "$backup_file" == *.gpg ]]; then
        log "Testing GPG decryption..."
        if ! gpg --list-packets "$backup_file" &>/dev/null; then
            log_error "GPG file appears corrupted"
            return 1
        fi
    fi

    log_success "Backup integrity verified"
    return 0
}

restore_database() {
    local backup_file="$1"
    local target_database_url="$2"

    log "Starting database restore from $backup_file..."

    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi

    # Handle encrypted backups
    local restore_file="$backup_file"
    if [[ "$backup_file" == *.gpg ]]; then
        log "Decrypting backup file..."
        restore_file="${backup_file%.gpg}"

        if ! gpg --decrypt --output "$restore_file" "$backup_file"; then
            log_error "Failed to decrypt backup file"
            return 1
        fi
    fi

    # Restore database
    log "Restoring database..."
    log_warning "This will DROP and recreate the target database!"

    read -p "Are you sure you want to proceed? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log "Database restore cancelled"
        return 1
    fi

    if ! pg_restore --verbose --clean --if-exists --create \
        --dbname="$target_database_url" "$restore_file"; then
        log_error "Database restore failed"

        # Clean up decrypted file
        [ "$restore_file" != "$backup_file" ] && rm -f "$restore_file"
        return 1
    fi

    # Clean up decrypted file
    [ "$restore_file" != "$backup_file" ] && rm -f "$restore_file"

    log_success "Database restore completed successfully"
    return 0
}

list_backups() {
    log "Available backups:"
    echo

    # Find all metadata files and display backup information
    local backup_count=0

    while IFS= read -r -d '' metadata_file; do
        if [ -f "$metadata_file" ]; then
            local backup_name
            local backup_type
            local timestamp
            local size_bytes
            local encrypted

            backup_name=$(jq -r '.backup_name' "$metadata_file")
            backup_type=$(jq -r '.backup_type' "$metadata_file")
            timestamp=$(jq -r '.timestamp' "$metadata_file")
            size_bytes=$(jq -r '.size_bytes' "$metadata_file")
            encrypted=$(jq -r '.encrypted' "$metadata_file")

            # Convert size to human readable
            local size_human
            if [ "$size_bytes" != "null" ] && [ "$size_bytes" -gt 0 ]; then
                size_human=$(numfmt --to=iec-i --suffix=B "$size_bytes")
            else
                size_human="Unknown"
            fi

            # Format encryption status
            local encryption_status=""
            [ "$encrypted" = "true" ] && encryption_status=" 🔒"

            echo "  📦 $backup_name ($backup_type)$encryption_status"
            echo "     Created: $timestamp"
            echo "     Size: $size_human"
            echo

            ((backup_count++))
        fi
    done < <(find "$BACKUP_DIR" -name "*.metadata.json" -print0 | sort -z)

    if [ $backup_count -eq 0 ]; then
        echo "  No backups found in $BACKUP_DIR"
        echo
    else
        echo "  Total backups: $backup_count"
        echo
    fi
}

disaster_recovery_plan() {
    log "🚨 DISASTER RECOVERY PROCEDURES 🚨"
    echo

    cat << 'EOF'
DISASTER RECOVERY PLAN
======================

In case of a complete system failure, follow these steps:

1. ASSESS THE SITUATION
   - Determine the scope of the failure
   - Check if it's a partial or complete outage
   - Verify backup integrity

2. COMMUNICATION
   - Notify stakeholders immediately
   - Post status updates on monitoring channels
   - Document the incident timeline

3. DATA RECOVERY
   a) Database Recovery:
      ./scripts/backup-and-recovery.sh restore-database <backup_file> <target_url>

   b) Application Recovery:
      - Deploy from latest known good commit
      - Restore application state if needed
      - Verify configuration secrets

4. SERVICE RESTORATION
   - Deploy to Railway production environment
   - Run health checks and smoke tests
   - Verify all endpoints are responding
   - Test critical user workflows

5. POST-INCIDENT
   - Conduct post-mortem analysis
   - Update backup procedures if needed
   - Review and update disaster recovery plan

EMERGENCY CONTACTS:
- System Administrator: [Configure in your environment]
- Database Administrator: [Configure in your environment]
- DevOps Lead: [Configure in your environment]

BACKUP LOCATIONS:
- Local: $BACKUP_DIR
- Cloud: [Configure cloud backup location]

RECOVERY TIME OBJECTIVES (RTO):
- Critical services: < 1 hour
- Full system: < 4 hours

RECOVERY POINT OBJECTIVES (RPO):
- Maximum data loss: < 1 hour (based on backup frequency)

EOF
}

show_usage() {
    cat << EOF
Backup and Disaster Recovery Script

Usage: $0 [COMMAND] [OPTIONS]

Commands:
  backup-all          Create full backup (database + application + secrets)
  backup-database     Create database backup only
  backup-app          Create application state backup only
  backup-secrets      Create secrets backup only
  backup-logs         Create logs backup only

  restore-database    Restore database from backup
  list-backups        List all available backups
  cleanup             Remove old backups based on retention policy
  verify              Verify backup integrity

  disaster-plan       Show disaster recovery procedures
  help                Show this help message

Options:
  --retention-days N  Set backup retention period (default: 30)
  --no-encrypt        Disable backup encryption
  --max-size-gb N     Maximum backup size in GB (default: 10)
  --compression N     Compression level 1-9 (default: 6)

Environment Variables:
  BACKUP_DIR          Directory for storing backups (default: ./backups)
  RETENTION_DAYS      Backup retention in days (default: 30)
  ENCRYPT_BACKUPS     Enable/disable encryption (default: true)
  GPG_RECIPIENT       GPG key for encryption
  MAX_BACKUP_SIZE_GB  Maximum backup size (default: 10)

Examples:
  $0 backup-all
  $0 backup-database --retention-days 7
  $0 restore-database backups/database_20240701_120000.sql.gpg
  $0 list-backups
  $0 cleanup --retention-days 14

EOF
}

main() {
    local command="${1:-help}"

    case "$command" in
        "backup-all")
            check_prerequisites
            backup_database && backup_application_state && backup_secrets && backup_logs
            cleanup_old_backups
            log_success "Full backup completed successfully"
            ;;
        "backup-database")
            check_prerequisites
            backup_database
            ;;
        "backup-app")
            check_prerequisites
            backup_application_state
            ;;
        "backup-secrets")
            check_prerequisites
            backup_secrets
            ;;
        "backup-logs")
            check_prerequisites
            backup_logs
            ;;
        "restore-database")
            if [ -z "$2" ]; then
                log_error "Please specify backup file to restore"
                log_error "Usage: $0 restore-database <backup_file> [target_database_url]"
                exit 1
            fi

            local target_url="${3:-$(doppler secrets get DATABASE_URL --plain)}"
            restore_database "$2" "$target_url"
            ;;
        "list-backups"|"list")
            list_backups
            ;;
        "cleanup")
            cleanup_old_backups
            ;;
        "verify")
            if [ -z "$2" ]; then
                log_error "Please specify backup file to verify"
                exit 1
            fi
            verify_backup_integrity "$2" "${2%.gpg}.metadata.json"
            ;;
        "disaster-plan"|"dr")
            disaster_recovery_plan
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
        --retention-days)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        --no-encrypt)
            ENCRYPT_BACKUPS=false
            shift
            ;;
        --max-size-gb)
            MAX_BACKUP_SIZE_GB="$2"
            shift 2
            ;;
        --compression)
            COMPRESSION_LEVEL="$2"
            shift 2
            ;;
        *)
            break
            ;;
    esac
done

# Run main function
main "$@"
