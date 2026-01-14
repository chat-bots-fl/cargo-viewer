#!/bin/bash

################################################################################
# Production Rollback Script for Cargo Viewer
#
# GOAL: Rollback the application to a previous deployment state safely
#
# This script performs:
# - Selection of backup to restore
# - Database restoration
# - Media files restoration
# - Configuration restoration
# - Container restart
# - Health verification
# - Notification of rollback status
#
# Usage: ./rollback.sh [options]
#   --backup DIR      Use specific backup directory
#   --list            List available backups
#   --force           Skip confirmation prompts
################################################################################

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${PROJECT_DIR}/logs"
BACKUP_DIR="${PROJECT_DIR}/backups"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.prod.yml"
ENV_FILE="${PROJECT_DIR}/.env.production"

# Rollback configuration
SPECIFIC_BACKUP=""
LIST_BACKUPS=false
FORCE_ROLLBACK=false
HEALTH_CHECK_URL="${HEALTH_CHECK_URL:-http://localhost:8000/health/}"
HEALTH_CHECK_TIMEOUT=120
HEALTH_CHECK_INTERVAL=10

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Docker Compose command (detected at runtime)
DOCKER_COMPOSE_CMD=()

################################################################################
# Logging Functions
################################################################################

"""
GOAL: Log informational messages with timestamp and color

PARAMETERS:
  message: string - Message to log - Not empty

RETURNS:
  None - Output to stdout

RAISES:
  None

GUARANTEES:
  - Message always includes timestamp
  - Messages are color-coded
  - All messages written to log file
"""
log_info() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[INFO]${NC} ${timestamp} - ${message}"
    echo "[INFO] ${timestamp} - ${message}" >> "${LOG_DIR}/rollback.log"
}

"""
GOAL: Log warning messages with timestamp and yellow color

PARAMETERS:
  message: string - Warning message to log - Not empty

RETURNS:
  None - Output to stdout

RAISES:
  None

GUARANTEES:
  - Message always includes timestamp
  - Messages are displayed in yellow
  - All messages written to log file
"""
log_warning() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[WARNING]${NC} ${timestamp} - ${message}"
    echo "[WARNING] ${timestamp} - ${message}" >> "${LOG_DIR}/rollback.log"
}

"""
GOAL: Log error messages with timestamp and red color

PARAMETERS:
  message: string - Error message to log - Not empty

RETURNS:
  None - Output to stderr

RAISES:
  None

GUARANTEES:
  - Message always includes timestamp
  - Messages are displayed in red
  - All messages written to log file
"""
log_error() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[ERROR]${NC} ${timestamp} - ${message}">&2
    echo "[ERROR] ${timestamp} - ${message}" >> "${LOG_DIR}/rollback.log"
}

"""
GOAL: Log success messages with timestamp and green color

PARAMETERS:
  message: string - Success message to log - Not empty

RETURNS:
  None - Output to stdout

RAISES:
  None

GUARANTEES:
  - Message always includes timestamp
  - Messages are displayed in green
  - All messages written to log file
"""
log_success() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[SUCCESS]${NC} ${timestamp} - ${message}"
    echo "[SUCCESS] ${timestamp} - ${message}" >> "${LOG_DIR}/rollback.log"
}

################################################################################
# Docker Compose + Env Helpers
################################################################################

"""
GOAL: Detect a working Docker Compose command

PARAMETERS:
  None

RETURNS:
  int - 0 if Docker Compose is available, 1 otherwise

RAISES:
  None

GUARANTEES:
  - On success, DOCKER_COMPOSE_CMD is set to either (docker-compose) or (docker compose)
"""
detect_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD=(docker-compose)
        return 0
    fi

    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD=(docker compose)
        return 0
    fi

    return 1
}

"""
GOAL: Run docker compose with production compose file and env file

PARAMETERS:
  args: string[] - Compose arguments - Not empty

RETURNS:
  int - Exit code from docker compose

RAISES:
  None

GUARANTEES:
  - Always uses `.env.production` for interpolation via `--env-file`
  - Always uses `docker-compose.prod.yml`
"""
compose() {
    if [ ${#DOCKER_COMPOSE_CMD[@]} -eq 0 ]; then
        if ! detect_docker_compose; then
            log_error "Docker Compose is not installed (need docker-compose or docker compose)"
            return 1
        fi
    fi

    "${DOCKER_COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

"""
GOAL: Read an env var from `.env.production` without exporting it

PARAMETERS:
  key: string - Variable name - Must be non-empty
  default: string - Default value if missing/empty - Optional

RETURNS:
  string - Raw value

RAISES:
  None

GUARANTEES:
  - Never fails; returns default on missing file/key
"""
get_env_value() {
    local key="$1"
    local default_value="${2:-}"

    if [ ! -f "$ENV_FILE" ]; then
        echo "$default_value"
        return 0
    fi

    local value
    value=$(grep -E "^${key}=" "$ENV_FILE" | tail -n1 | cut -d'=' -f2- | tr -d '\r' || true)
    if [ -z "$value" ]; then
        echo "$default_value"
        return 0
    fi

    echo "$value"
}

################################################################################
# Argument Parsing Functions
################################################################################

"""
GOAL: Parse command line arguments and set rollback options

PARAMETERS:
  args: array - Command line arguments - May be empty

RETURNS:
  None - Sets global variables

RAISES:
  None

GUARANTEES:
  - SPECIFIC_BACKUP set to specified directory or empty
  - LIST_BACKUPS set to true or false
  - FORCE_ROLLBACK set to true or false
  - Invalid arguments are rejected
"""
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --backup)
                SPECIFIC_BACKUP="$2"
                shift 2
                ;;
            --list)
                LIST_BACKUPS=true
                shift
                ;;
            --force)
                FORCE_ROLLBACK=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

"""
GOAL: Display help information for the rollback script

PARAMETERS:
  None

RETURNS:
  None - Output to stdout

RAISES:
  None

GUARANTEES:
  - All options are documented
  - Usage examples are provided
  - Function exits after displaying help
"""
show_help() {
    cat << EOF
Production Rollback Script for Cargo Viewer

Usage: $0 [options]

Options:
  --backup DIR      Use specific backup directory
  --list            List available backups
  --force           Skip confirmation prompts
  --help           Show this help message

Examples:
  $0                              # Rollback to latest backup
  $0 --list                       # List available backups
  $0 --backup backups/pre-deployment-20240101-120000  # Rollback to specific backup
  $0 --force                      # Rollback without confirmation

EOF
}

################################################################################
# Backup Listing Functions
################################################################################

"""
GOAL: List all available backups with details

PARAMETERS:
  None

RETURNS:
  int - 0 if backups found, 1 otherwise

RAISES:
  None

GUARANTEES:
  - All backups are listed with timestamp
  - Backup details are displayed
  - Function returns appropriate exit code
"""
list_backups() {
    log_info "Available backups:"
    
    local backups=($(ls -1t "${BACKUP_DIR}/pre-deployment-"* 2>/dev/null || true))
    
    if [ ${#backups[@]} -eq 0 ]; then
        log_warning "No backups found"
        return 1
    fi
    
    local index=1
    for backup in "${backups[@]}"; do
        local backup_name=$(basename "$backup")
        local backup_size=$(du -sh "$backup" | cut -f1)
        
        # Read backup info if available
        local backup_info=""
        if [ -f "${backup}/backup_info.txt" ]; then
            backup_info=$(grep -E "(Git commit|Git branch)" "${backup}/backup_info.txt" | tr '\n' ' ')
        fi
        
        echo "  [${index}] ${backup_name} (${backup_size})"
        if [ -n "$backup_info" ]; then
            echo "       ${backup_info}"
        fi
        
        index=$((index + 1))
    done
    
    return 0
}

"""
GOAL: Get the path to the latest backup directory

PARAMETERS:
  None

RETURNS:
  string - Path to latest backup directory, empty string if none exists

RAISES:
  None

GUARANTEES:
  - Returns path to most recent backup
  - Returns empty string if no backups exist
  - Function never fails
"""
get_latest_backup() {
    local latest_backup=$(ls -1t "${BACKUP_DIR}/pre-deployment-"* 2>/dev/null | head -n 1 || echo "")
    echo "$latest_backup"
}

"""
GOAL: Validate that a backup directory exists and contains required files

PARAMETERS:
  backup_dir: string - Path to backup directory - Must be absolute path

RETURNS:
  int - 0 if backup valid, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Backup directory exists
  - Database backup exists
  - Function returns appropriate exit code
"""
validate_backup() {
    local backup_dir="$1"
    
    if [ ! -d "$backup_dir" ]; then
        log_error "Backup directory does not exist: $backup_dir"
        return 1
    fi
    
    if [ ! -f "${backup_dir}/database.sql" ]; then
        log_error "Database backup not found: ${backup_dir}/database.sql"
        return 1
    fi
    
    log_success "Backup validation passed: $backup_dir"
    return 0
}

################################################################################
# Confirmation Functions
################################################################################

"""
GOAL: Prompt user for confirmation before rollback

PARAMETERS:
  backup_dir: string - Path to backup directory - Must be absolute path

RETURNS:
  int - 0 if confirmed, 1 otherwise

RAISES:
  None

GUARANTEES:
  - User is prompted for confirmation
  - Rollback details are displayed
  - Function returns appropriate exit code
"""
confirm_rollback() {
    local backup_dir="$1"
    
    if [ "$FORCE_ROLLBACK" = true ]; then
        log_warning "Skipping confirmation (force mode)"
        return 0
    fi
    
    echo ""
    echo "========================================="
    echo "ROLLBACK CONFIRMATION"
    echo "========================================="
    echo "Backup: $backup_dir"
    echo "This will:"
    echo "  - Restore database from backup"
    echo "  - Restore media files from backup"
    echo "  - Restore configuration from backup"
    echo "  - Restart application containers"
    echo ""
    echo "⚠️  This action cannot be undone!"
    echo "========================================="
    echo ""
    
    read -p "Are you sure you want to rollback? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_warning "Rollback cancelled by user"
        return 1
    fi
    
    return 0
}

################################################################################
# Rollback Functions
################################################################################

"""
GOAL: Stop all Docker containers

PARAMETERS:
  None

RETURNS:
  int - 0 if stop successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - All containers are stopped
  - Stop status is logged
  - Function returns appropriate exit code
"""
stop_containers() {
    log_info "Stopping Docker containers..."
    
    cd "$PROJECT_DIR"
    
    if ! compose down; then
        log_error "Failed to stop containers"
        return 1
    fi
    
    log_success "Docker containers stopped successfully"
    return 0
}

"""
GOAL: Restore database from backup

PARAMETERS:
  backup_dir: string - Path to backup directory - Must be absolute path

RETURNS:
  int - 0 if restore successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Database is restored from backup
  - Restore status is logged
  - Function returns appropriate exit code
"""
restore_database() {
    local backup_dir="$1"
    
    log_info "Restoring database from backup..."
    
    local backup_file="${backup_dir}/database.sql"
    
    if [ ! -f "$backup_file" ]; then
        log_error "Database backup not found: $backup_file"
        return 1
    fi
    
    # Start database container only
    cd "$PROJECT_DIR"
    compose up -d db
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    sleep 10
    
    # Restore database
    local pg_user
    local pg_db
    pg_user=$(get_env_value "POSTGRES_USER" "cargo_viewer_user")
    pg_db=$(get_env_value "POSTGRES_DB" "cargo_viewer_prod")

    if ! compose exec -T db psql -U "$pg_user" -d "$pg_db" < "$backup_file" 2>/dev/null; then
        log_error "Database restore failed"
        return 1
    fi
    
    log_success "Database restored successfully"
    return 0
}

"""
GOAL: Restore media files from backup

PARAMETERS:
  backup_dir: string - Path to backup directory - Must be absolute path

RETURNS:
  int - 0 if restore successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Media files are restored from backup
  - Existing media files are backed up
  - Restore status is logged
  - Function returns appropriate exit code
"""
restore_media_files() {
    local backup_dir="$1"
    
    log_info "Restoring media files from backup..."
    
    local backup_file="${backup_dir}/media.tar.gz"
    
    if [ ! -f "$backup_file" ]; then
        log_warning "Media files backup not found: $backup_file"
        return 0
    fi
    
    # Backup current media files
    if [ -d "${PROJECT_DIR}/media" ]; then
        local current_media_backup="${BACKUP_DIR}/media-pre-rollback-$(date +%Y%m%d-%H%M%S).tar.gz"
        log_info "Backing up current media files to: $current_media_backup"
        tar -czf "$current_media_backup" -C "${PROJECT_DIR}" media
    fi
    
    # Extract media files
    if ! tar -xzf "$backup_file" -C "${PROJECT_DIR}"; then
        log_error "Media files restore failed"
        return 1
    fi
    
    log_success "Media files restored successfully"
    return 0
}

"""
GOAL: Restore configuration files from backup

PARAMETERS:
  backup_dir: string - Path to backup directory - Must be absolute path

RETURNS:
  int - 0 if restore successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Configuration files are restored from backup
  - Existing configuration files are backed up
  - Restore status is logged
  - Function returns appropriate exit code
"""
restore_configuration() {
    local backup_dir="$1"
    
    log_info "Restoring configuration files from backup..."
    
    local backup_file="${backup_dir}/config.tar.gz"
    
    if [ ! -f "$backup_file" ]; then
        log_warning "Configuration backup not found: $backup_file"
        return 0
    fi
    
    # Backup current configuration
    local current_config_backup="${BACKUP_DIR}/config-pre-rollback-$(date +%Y%m%d-%H%M%S).tar.gz"
    log_info "Backing up current configuration to: $current_config_backup"
    tar -czf "$current_config_backup" -C "${PROJECT_DIR}" \
        .env.production \
        docker-compose.prod.yml \
        nginx.conf \
        supervisor.conf 2>/dev/null || true
    
    # Extract configuration files
    if ! tar -xzf "$backup_file" -C "${PROJECT_DIR}"; then
        log_error "Configuration restore failed"
        return 1
    fi
    
    log_success "Configuration files restored successfully"
    return 0
}

"""
GOAL: Start Docker containers after rollback

PARAMETERS:
  None

RETURNS:
  int - 0 if start successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - All containers are started
  - Container status is verified
  - Function returns appropriate exit code
"""
start_containers() {
    log_info "Starting Docker containers..."
    
    cd "$PROJECT_DIR"
    
    if ! compose up -d; then
        log_error "Failed to start containers"
        return 1
    fi
    
    # Wait for containers to be ready
    log_info "Waiting for containers to be ready..."
    sleep 10
    
    # Check container status
    if ! compose ps | grep -q "Up"; then
        log_error "Containers are not running"
        return 1
    fi
    
    log_success "Docker containers started successfully"
    return 0
}

"""
GOAL: Wait for application to become healthy after rollback

PARAMETERS:
  timeout: int - Maximum time to wait in seconds - Must be positive
  interval: int - Time between checks in seconds - Must be positive

RETURNS:
  int - 0 if application becomes healthy, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Health endpoint is checked at specified intervals
  - Timeout is enforced
  - Progress is logged
  - Function returns appropriate exit code
"""
wait_for_health() {
    local timeout="$1"
    local interval="$2"
    
    log_info "Waiting for application to become healthy (timeout: ${timeout}s)..."
    
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if curl -sf "$HEALTH_CHECK_URL" > /dev/null 2>&1; then
            log_success "Application is healthy"
            return 0
        fi
        
        log_info "Application not ready yet, waiting ${interval}s... (${elapsed}/${timeout}s)"
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done
    
    log_error "Application health check timed out after ${timeout}s"
    return 1
}

"""
GOAL: Perform health checks after rollback

PARAMETERS:
  None

RETURNS:
  int - 0 if all checks pass, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Application health endpoint is checked
  - Database connectivity is verified
  - Redis connectivity is verified
  - All check results are logged
  - Function returns appropriate exit code
"""
perform_health_checks() {
    log_info "Performing health checks..."
    
    local all_passed=true
    
    # Check application health
    log_info "Checking application health..."
    if curl -sf "${HEALTH_CHECK_URL}detailed/" > /dev/null 2>&1; then
        log_success "Application health check passed"
    else
        log_error "Application health check failed"
        all_passed=false
    fi
    
    # Check database
    log_info "Checking database connectivity..."
    if compose exec -T web python manage.py dbshell --settings=config.settings.production -c "SELECT 1;" > /dev/null 2>&1; then
        log_success "Database connectivity check passed"
    else
        log_error "Database connectivity check failed"
        all_passed=false
    fi
    
    # Check Redis
    log_info "Checking Redis connectivity..."
    if compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        log_success "Redis connectivity check passed"
    else
        log_error "Redis connectivity check failed"
        all_passed=false
    fi
    
    if [ "$all_passed" = true ]; then
        log_success "All health checks passed"
        return 0
    else
        log_error "Some health checks failed"
        return 1
    fi
}

################################################################################
# Notification Functions
################################################################################

"""
GOAL: Send rollback notification to configured channels

PARAMETERS:
  status: string - Rollback status (success, failure) - Must be "success" or "failure"
  message: string - Notification message - Not empty

RETURNS:
  int - 0 if notification sent, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Notification is sent to Telegram if configured
  - Notification is logged
  - Function returns appropriate exit code
"""
send_notification() {
    local status="$1"
    local message="$2"
    
    log_info "Sending rollback notification: ${status}"
    
    # Send Telegram notification if configured
    local bot_token=$(grep "^TELEGRAM_BOT_TOKEN=" "$ENV_FILE" | cut -d'=' -f2)
    local chat_id=$(grep "^TELEGRAM_ADMIN_CHAT_ID=" "$ENV_FILE" | cut -d'=' -f2)
    
    if [ -n "$bot_token" ] && [ -n "$chat_id" ]; then
        local emoji="✅"
        if [ "$status" = "failure" ]; then
            emoji="❌"
        fi
        
        local text="${emoji} Rollback ${status}: ${message}"
        
        curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
            -d "chat_id=${chat_id}" \
            -d "text=${text}" \
            -d "parse_mode=HTML" > /dev/null 2>&1 || true
        
        log_success "Telegram notification sent"
    fi
    
    return 0
}

################################################################################
# Main Rollback Function
################################################################################

"""
GOAL: Execute the complete rollback process

PARAMETERS:
  None

RETURNS:
  int - 0 if rollback successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - All rollback steps are executed in order
  - Rollback is logged
  - Notifications are sent
  - Function returns appropriate exit code
"""
main() {
    local start_time=$(date +%s)
    
    log_info "========================================="
    log_info "Starting rollback process"
    log_info "========================================="
    
    # Parse arguments
    parse_arguments "$@"
    
    # Create log directory
    mkdir -p "$LOG_DIR"
    mkdir -p "$BACKUP_DIR"
    
    # List backups if requested
    if [ "$LIST_BACKUPS" = true ]; then
        list_backups
        exit 0
    fi
    
    # Determine backup to restore
    local backup_dir="$SPECIFIC_BACKUP"
    if [ -z "$backup_dir" ]; then
        backup_dir=$(get_latest_backup)
        if [ -z "$backup_dir" ]; then
            log_error "No backups found for rollback"
            send_notification "failure" "No backups found for rollback"
            exit 1
        fi
    fi
    
    # Validate backup
    if ! validate_backup "$backup_dir"; then
        log_error "Backup validation failed"
        send_notification "failure" "Backup validation failed"
        exit 1
    fi
    
    # Confirm rollback
    if ! confirm_rollback "$backup_dir"; then
        log_info "Rollback cancelled"
        exit 0
    fi
    
    # Stop containers
    if ! stop_containers; then
        log_error "Failed to stop containers"
        send_notification "failure" "Failed to stop containers"
        exit 1
    fi
    
    # Restore database
    if ! restore_database "$backup_dir"; then
        log_error "Database restore failed"
        send_notification "failure" "Database restore failed"
        exit 1
    fi
    
    # Restore media files
    if ! restore_media_files "$backup_dir"; then
        log_error "Media files restore failed"
        send_notification "failure" "Media files restore failed"
        exit 1
    fi
    
    # Restore configuration
    if ! restore_configuration "$backup_dir"; then
        log_error "Configuration restore failed"
        send_notification "failure" "Configuration restore failed"
        exit 1
    fi
    
    # Start containers
    if ! start_containers; then
        log_error "Failed to start containers"
        send_notification "failure" "Failed to start containers"
        exit 1
    fi
    
    # Wait for health
    if ! wait_for_health "$HEALTH_CHECK_TIMEOUT" "$HEALTH_CHECK_INTERVAL"; then
        log_error "Health check timeout after rollback"
        send_notification "failure" "Health check timeout after rollback"
        exit 1
    fi
    
    # Perform health checks
    if ! perform_health_checks; then
        log_error "Health checks failed after rollback"
        send_notification "failure" "Health checks failed after rollback"
        exit 1
    fi
    
    # Calculate rollback time
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))
    
    # Success
    log_info "========================================="
    log_success "Rollback completed successfully in ${minutes}m ${seconds}s"
    log_info "Backup used: $backup_dir"
    log_info "========================================="
    
    send_notification "success" "Rollback completed successfully in ${minutes}m ${seconds}s"
    
    exit 0
}

# Run main function
main "$@"
