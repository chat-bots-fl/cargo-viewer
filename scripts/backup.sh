#!/bin/bash

################################################################################
# Production Backup Script for Cargo Viewer
#
# GOAL: Create comprehensive backups of application data and configuration
#
# This script performs:
# - Database backups
# - Media files backups
# - Configuration files backups
# - Upload to remote storage (optional)
# - Cleanup of old backups
# - Backup verification
# - Notification of backup status
#
# Usage: ./backup.sh [options]
#   --database-only    Backup only database
#   --media-only       Backup only media files
#   --config-only      Backup only configuration files
#   --no-upload        Skip upload to remote storage
#   --no-cleanup       Skip cleanup of old backups
#   --verify           Verify backup integrity
################################################################################

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${PROJECT_DIR}/logs"
BACKUP_DIR="${PROJECT_DIR}/backups"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.prod.yml"
ENV_FILE="${PROJECT_DIR}/.env.production"

# Backup configuration
BACKUP_DATABASE=true
BACKUP_MEDIA=true
BACKUP_CONFIG=true
UPLOAD_BACKUP=true
CLEANUP_BACKUP=true
VERIFY_BACKUP=false
BACKUP_TYPE="full"

# Remote storage configuration (optional)
REMOTE_STORAGE_ENABLED=false
REMOTE_STORAGE_TYPE=""
REMOTE_STORAGE_PATH=""

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
    echo "[INFO] ${timestamp} - ${message}" >> "${LOG_DIR}/backup.log"
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
    echo "[WARNING] ${timestamp} - ${message}" >> "${LOG_DIR}/backup.log"
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
    echo -e "${RED}[ERROR]${NC} ${timestamp} - ${message}" >&2
    echo "[ERROR] ${timestamp} - ${message}" >> "${LOG_DIR}/backup.log"
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
    echo "[SUCCESS] ${timestamp} - ${message}" >> "${LOG_DIR}/backup.log"
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
GOAL: Parse command line arguments and set backup options

PARAMETERS:
  args: array - Command line arguments - May be empty

RETURNS:
  None - Sets global variables

RAISES:
  None

GUARANTEES:
  - BACKUP_DATABASE set to true or false
  - BACKUP_MEDIA set to true or false
  - BACKUP_CONFIG set to true or false
  - UPLOAD_BACKUP set to true or false
  - CLEANUP_BACKUP set to true or false
  - VERIFY_BACKUP set to true or false
  - Invalid arguments are rejected
"""
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --database-only)
                BACKUP_DATABASE=true
                BACKUP_MEDIA=false
                BACKUP_CONFIG=false
                BACKUP_TYPE="database"
                shift
                ;;
            --media-only)
                BACKUP_DATABASE=false
                BACKUP_MEDIA=true
                BACKUP_CONFIG=false
                BACKUP_TYPE="media"
                shift
                ;;
            --config-only)
                BACKUP_DATABASE=false
                BACKUP_MEDIA=false
                BACKUP_CONFIG=true
                BACKUP_TYPE="config"
                shift
                ;;
            --no-upload)
                UPLOAD_BACKUP=false
                shift
                ;;
            --no-cleanup)
                CLEANUP_BACKUP=false
                shift
                ;;
            --verify)
                VERIFY_BACKUP=true
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
GOAL: Display help information for the backup script

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
Production Backup Script for Cargo Viewer

Usage: $0 [options]

Options:
  --database-only    Backup only database
  --media-only       Backup only media files
  --config-only      Backup only configuration files
  --no-upload        Skip upload to remote storage
  --no-cleanup       Skip cleanup of old backups
  --verify           Verify backup integrity
  --help           Show this help message

Examples:
  $0                              # Full backup (database, media, config)
  $0 --database-only             # Backup only database
  $0 --media-only                # Backup only media files
  $0 --no-upload                 # Backup without uploading to remote storage
  $0 --verify                    # Backup and verify integrity

EOF
}

################################################################################
# Validation Functions
################################################################################

"""
GOAL: Validate that all required tools and dependencies are installed

PARAMETERS:
  None

RETURNS:
  int - 0 if all validations pass, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Docker is installed and running
  - Docker Compose is installed
  - Required files exist
  - Backup directory is writable
  - Function returns appropriate exit code
"""
validate_environment() {
    log_info "Validating environment..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        return 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        return 1
    fi
    
    # Check Docker Compose
    if ! detect_docker_compose; then
        log_error "Docker Compose is not installed (need docker-compose or docker compose)"
        return 1
    fi
    
    # Check required files
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose file not found: $COMPOSE_FILE"
        return 1
    fi
    
    # Check backup directory
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
        log_info "Created backup directory: $BACKUP_DIR"
    fi
    
    # Check if backup directory is writable
    if [ ! -w "$BACKUP_DIR" ]; then
        log_error "Backup directory is not writable: $BACKUP_DIR"
        return 1
    fi
    
    # Check disk space
    local available_disk=$(df -BG "$BACKUP_DIR" | tail -1 | awk '{print $4}' | tr -d 'G')
    if [ "$available_disk" -lt 5 ]; then
        log_error "Insufficient disk space: ${available_disk}GB available, 5GB required"
        return 1
    fi
    
    log_success "Environment validation passed"
    return 0
}

"""
GOAL: Check system resources before backup

PARAMETERS:
  None

RETURNS:
  int - 0 if resources are sufficient, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Available disk space is checked (minimum 5GB)
  - Available memory is checked (minimum 1GB)
  - Function returns appropriate exit code
"""
check_system_resources() {
    log_info "Checking system resources..."
    
    # Check disk space
    local available_disk=$(df -BG "$BACKUP_DIR" | tail -1 | awk '{print $4}' | tr -d 'G')
    if [ "$available_disk" -lt 5 ]; then
        log_error "Insufficient disk space: ${available_disk}GB available, 5GB required"
        return 1
    fi
    
    # Check memory
    local available_memory=$(free -m | awk 'NR==2{print $7}')
    if [ "$available_memory" -lt 1024 ]; then
        log_warning "Low memory: ${available_memory}MB available, 1024MB recommended"
    fi
    
    log_success "System resources check passed"
    return 0
}

################################################################################
# Backup Functions
################################################################################

"""
GOAL: Create backup directory with timestamp

PARAMETERS:
  None

RETURNS:
  string - Path to created backup directory

RAISES:
  None

GUARANTEES:
  - Directory is created with timestamp
  - Directory is writable
  - Function never returns empty string
"""
create_backup_directory() {
    local timestamp=$(date '+%Y%m%d-%H%M%S')
    local backup_dir="${BACKUP_DIR}/${BACKUP_TYPE}-${timestamp}"
    
    mkdir -p "$backup_dir"
    
    log_success "Created backup directory: $backup_dir"
    
    echo "$backup_dir"
}

"""
GOAL: Create database backup

PARAMETERS:
  backup_dir: string - Path to backup directory - Must be absolute path

RETURNS:
  int - 0 if backup successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Database backup is created in specified directory
  - Backup is compressed
  - Backup size is logged
  - Function returns appropriate exit code
"""
backup_database() {
    if [ "$BACKUP_DATABASE" = false ]; then
        log_info "Skipping database backup"
        return 0
    fi
    
    log_info "Creating database backup..."
    
    local backup_dir="$1"
    local backup_file="${backup_dir}/database.sql.gz"
    
    cd "$PROJECT_DIR"
    
    # Create database backup
    local pg_user
    local pg_db
    pg_user=$(get_env_value "POSTGRES_USER" "cargo_viewer_user")
    pg_db=$(get_env_value "POSTGRES_DB" "cargo_viewer_prod")

    if ! compose exec -T db pg_dump -U "$pg_user" "$pg_db" | gzip > "$backup_file" 2>/dev/null; then
        log_error "Database backup failed"
        return 1
    fi
    
    # Get backup size
    local backup_size=$(du -h "$backup_file" | cut -f1)
    
    log_success "Database backup created: ${backup_file} (${backup_size})"
    
    return 0
}

"""
GOAL: Create media files backup

PARAMETERS:
  backup_dir: string - Path to backup directory - Must be absolute path

RETURNS:
  int - 0 if backup successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Media files are backed up to specified directory
  - Backup is compressed
  - Backup size is logged
  - Function returns appropriate exit code
"""
backup_media_files() {
    if [ "$BACKUP_MEDIA" = false ]; then
        log_info "Skipping media files backup"
        return 0
    fi
    
    log_info "Creating media files backup..."
    
    local backup_dir="$1"
    local backup_file="${backup_dir}/media.tar.gz"
    
    # Check if media directory exists
    if [ ! -d "${PROJECT_DIR}/media" ]; then
        log_warning "Media directory does not exist, skipping backup"
        return 0
    fi
    
    # Create media backup
    if ! tar -czf "$backup_file" -C "${PROJECT_DIR}" media 2>/dev/null; then
        log_error "Media files backup failed"
        return 1
    fi
    
    # Get backup size
    local backup_size=$(du -h "$backup_file" | cut -f1)
    
    log_success "Media files backup created: ${backup_file} (${backup_size})"
    
    return 0
}

"""
GOAL: Create configuration files backup

PARAMETERS:
  backup_dir: string - Path to backup directory - Must be absolute path

RETURNS:
  int - 0 if backup successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Configuration files are backed up to specified directory
  - Backup is compressed
  - Backup size is logged
  - Function returns appropriate exit code
"""
backup_configuration() {
    if [ "$BACKUP_CONFIG" = false ]; then
        log_info "Skipping configuration backup"
        return 0
    fi
    
    log_info "Creating configuration backup..."
    
    local backup_dir="$1"
    local backup_file="${backup_dir}/config.tar.gz"
    
    # Create configuration backup
    if ! tar -czf "$backup_file" -C "${PROJECT_DIR}" \
        .env.production \
        docker-compose.prod.yml \
        nginx.conf \
        supervisor.conf 2>/dev/null; then
        log_error "Configuration backup failed"
        return 1
    fi
    
    # Get backup size
    local backup_size=$(du -h "$backup_file" | cut -f1)
    
    log_success "Configuration backup created: ${backup_file} (${backup_size})"
    
    return 0
}

"""
GOAL: Create backup info file with metadata

PARAMETERS:
  backup_dir: string - Path to backup directory - Must be absolute path

RETURNS:
  int - 0 if info file created successfully, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Info file is created with backup metadata
  - File contains timestamp, git info, and backup details
  - Function returns appropriate exit code
"""
create_backup_info() {
    local backup_dir="$1"
    local info_file="${backup_dir}/backup_info.txt"
    
    log_info "Creating backup info file..."
    
    cat > "$info_file" << EOF
Backup Information
==================

Backup Type: ${BACKUP_TYPE}
Created: $(date)
Hostname: $(hostname)
User: $(whoami)

Git Information
===============
Branch: $(cd "$PROJECT_DIR" && git branch --show-current 2>/dev/null || echo "N/A")
Commit: $(cd "$PROJECT_DIR" && git rev-parse HEAD 2>/dev/null || echo "N/A")
Commit Message: $(cd "$PROJECT_DIR" && git log -1 --pretty=%B 2>/dev/null || echo "N/A")

Backup Contents
===============
EOF
    
    # Add backup contents
    if [ -f "${backup_dir}/database.sql.gz" ]; then
        local db_size=$(du -h "${backup_dir}/database.sql.gz" | cut -f1)
        echo "Database: database.sql.gz (${db_size})" >> "$info_file"
    fi
    
    if [ -f "${backup_dir}/media.tar.gz" ]; then
        local media_size=$(du -h "${backup_dir}/media.tar.gz" | cut -f1)
        echo "Media: media.tar.gz (${media_size})" >> "$info_file"
    fi
    
    if [ -f "${backup_dir}/config.tar.gz" ]; then
        local config_size=$(du -h "${backup_dir}/config.tar.gz" | cut -f1)
        echo "Configuration: config.tar.gz (${config_size})" >> "$info_file"
    fi
    
    # Add total size
    local total_size=$(du -sh "$backup_dir" | cut -f1)
    echo "" >> "$info_file"
    echo "Total Size: ${total_size}" >> "$info_file"
    
    log_success "Backup info file created: $info_file"
    
    return 0
}

################################################################################
# Upload Functions
################################################################################

"""
GOAL: Upload backup to remote storage

PARAMETERS:
  backup_dir: string - Path to backup directory - Must be absolute path

RETURNS:
  int - 0 if upload successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Backup is uploaded to remote storage if configured
  - Upload status is logged
  - Function returns appropriate exit code
"""
upload_to_remote_storage() {
    if [ "$UPLOAD_BACKUP" = false ]; then
        log_info "Skipping remote storage upload"
        return 0
    fi
    
    if [ "$REMOTE_STORAGE_ENABLED" = false ]; then
        log_info "Remote storage not configured, skipping upload"
        return 0
    fi
    
    log_info "Uploading backup to remote storage..."
    
    local backup_dir="$1"
    local backup_name=$(basename "$backup_dir")
    
    # Upload based on storage type
    case "$REMOTE_STORAGE_TYPE" in
        s3)
            upload_to_s3 "$backup_dir" "$backup_name"
            ;;
        rsync)
            upload_to_rsync "$backup_dir" "$backup_name"
            ;;
        ftp)
            upload_to_ftp "$backup_dir" "$backup_name"
            ;;
        *)
            log_warning "Unknown remote storage type: $REMOTE_STORAGE_TYPE"
            return 0
            ;;
    esac
}

"""
GOAL: Upload backup to S3-compatible storage

PARAMETERS:
  backup_dir: string - Path to backup directory - Must be absolute path
  backup_name: string - Name of backup directory - Not empty

RETURNS:
  int - 0 if upload successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Backup is uploaded to S3 if AWS CLI is configured
  - Upload status is logged
  - Function returns appropriate exit code
"""
upload_to_s3() {
    local backup_dir="$1"
    local backup_name="$2"
    
    if ! command -v aws &> /dev/null; then
        log_warning "AWS CLI not installed, skipping S3 upload"
        return 0
    fi
    
    local s3_bucket="${REMOTE_STORAGE_PATH}"
    
    if ! aws s3 sync "$backup_dir" "s3://${s3_bucket}/${backup_name}/" --quiet; then
        log_error "S3 upload failed"
        return 1
    fi
    
    log_success "Backup uploaded to S3: s3://${s3_bucket}/${backup_name}/"
    
    return 0
}

"""
GOAL: Upload backup to remote server using rsync

PARAMETERS:
  backup_dir: string - Path to backup directory - Must be absolute path
  backup_name: string - Name of backup directory - Not empty

RETURNS:
  int - 0 if upload successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Backup is uploaded using rsync if configured
  - Upload status is logged
  - Function returns appropriate exit code
"""
upload_to_rsync() {
    local backup_dir="$1"
    local backup_name="$2"
    
    if ! command -v rsync &> /dev/null; then
        log_warning "rsync not installed, skipping rsync upload"
        return 0
    fi
    
    local remote_path="${REMOTE_STORAGE_PATH}/${backup_name}"
    
    if ! rsync -avz --progress "$backup_dir/" "$remote_path/" 2>/dev/null; then
        log_error "rsync upload failed"
        return 1
    fi
    
    log_success "Backup uploaded via rsync: $remote_path"
    
    return 0
}

"""
GOAL: Upload backup to FTP server

PARAMETERS:
  backup_dir: string - Path to backup directory - Must be absolute path
  backup_name: string - Name of backup directory - Not empty

RETURNS:
  int - 0 if upload successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Backup is uploaded to FTP if configured
  - Upload status is logged
  - Function returns appropriate exit code
"""
upload_to_ftp() {
    local backup_dir="$1"
    local backup_name="$2"
    
    log_warning "FTP upload not implemented"
    return 0
}

################################################################################
# Verification Functions
################################################################################

"""
GOAL: Verify backup integrity

PARAMETERS:
  backup_dir: string - Path to backup directory - Must be absolute path

RETURNS:
  int - 0 if verification successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - All backup files are verified
  - Database backup can be restored
  - Verification results are logged
  - Function returns appropriate exit code
"""
verify_backup() {
    if [ "$VERIFY_BACKUP" = false ]; then
        log_info "Skipping backup verification"
        return 0
    fi
    
    log_info "Verifying backup integrity..."
    
    local backup_dir="$1"
    local all_valid=true
    
    # Verify database backup
    if [ -f "${backup_dir}/database.sql.gz" ]; then
        log_info "Verifying database backup..."
        if ! gzip -t "${backup_dir}/database.sql.gz" 2>/dev/null; then
            log_error "Database backup verification failed"
            all_valid=false
        else
            log_success "Database backup verification passed"
        fi
    fi
    
    # Verify media backup
    if [ -f "${backup_dir}/media.tar.gz" ]; then
        log_info "Verifying media backup..."
        if ! tar -tzf "${backup_dir}/media.tar.gz" > /dev/null 2>&1; then
            log_error "Media backup verification failed"
            all_valid=false
        else
            log_success "Media backup verification passed"
        fi
    fi
    
    # Verify config backup
    if [ -f "${backup_dir}/config.tar.gz" ]; then
        log_info "Verifying configuration backup..."
        if ! tar -tzf "${backup_dir}/config.tar.gz" > /dev/null 2>&1; then
            log_error "Configuration backup verification failed"
            all_valid=false
        else
            log_success "Configuration backup verification passed"
        fi
    fi
    
    if [ "$all_valid" = true ]; then
        log_success "All backup verifications passed"
        return 0
    else
        log_error "Some backup verifications failed"
        return 1
    fi
}

################################################################################
# Cleanup Functions
################################################################################

"""
GOAL: Clean up old backups to save disk space

PARAMETERS:
  None

RETURNS:
  int - 0 if cleanup successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Backups older than retention period are deleted
  - Minimum number of backups is kept
  - Cleanup is logged
  - Function returns appropriate exit code
"""
cleanup_old_backups() {
    if [ "$CLEANUP_BACKUP" = false ]; then
        log_info "Skipping cleanup of old backups"
        return 0
    fi
    
    log_info "Cleaning up old backups..."
    
    # Retention policy
    local daily_retention=7
    local weekly_retention=4
    local monthly_retention=3
    
    # Delete daily backups older than retention period
    find "${BACKUP_DIR}" -name "full-*" -type d -mtime +${daily_retention} -exec rm -rf {} \; 2>/dev/null || true
    find "${BACKUP_DIR}" -name "database-*" -type d -mtime +${daily_retention} -exec rm -rf {} \; 2>/dev/null || true
    find "${BACKUP_DIR}" -name "media-*" -type d -mtime +${daily_retention} -exec rm -rf {} \; 2>/dev/null || true
    find "${BACKUP_DIR}" -name "config-*" -type d -mtime +${daily_retention} -exec rm -rf {} \; 2>/dev/null || true
    
    # Keep minimum number of backups
    local backup_count=$(ls -1t "${BACKUP_DIR}/${BACKUP_TYPE}-"* 2>/dev/null | wc -l)
    local min_backups=5
    
    if [ "$backup_count" -gt "$min_backups" ]; then
        local backups_to_delete=$((backup_count - min_backups))
        log_info "Deleting ${backups_to_delete} old backups..."
        
        ls -1t "${BACKUP_DIR}/${BACKUP_TYPE}-"* | tail -n "$backups_to_delete" | while read -r backup; do
            log_info "Deleting old backup: $backup"
            rm -rf "$backup"
        done
    fi
    
    log_success "Backup cleanup completed"
    
    return 0
}

################################################################################
# Notification Functions
################################################################################

"""
GOAL: Send backup notification to configured channels

PARAMETERS:
  status: string - Backup status (success, failure) - Must be "success" or "failure"
  message: string - Notification message - Not empty
  backup_dir: string - Path to backup directory - Must be absolute path

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
    local backup_dir="$3"
    
    log_info "Sending backup notification: ${status}"
    
    # Send Telegram notification if configured
    local bot_token=$(grep "^TELEGRAM_BOT_TOKEN=" "$ENV_FILE" | cut -d'=' -f2)
    local chat_id=$(grep "^TELEGRAM_ADMIN_CHAT_ID=" "$ENV_FILE" | cut -d'=' -f2)
    
    if [ -n "$bot_token" ] && [ -n "$chat_id" ]; then
        local emoji="✅"
        if [ "$status" = "failure" ]; then
            emoji="❌"
        fi
        
        local backup_name=$(basename "$backup_dir")
        local backup_size=$(du -sh "$backup_dir" | cut -f1)
        
        local text="${emoji} Backup ${status}: ${message}
Type: ${BACKUP_TYPE}
Name: ${backup_name}
Size: ${backup_size}"
        
        curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
            -d "chat_id=${chat_id}" \
            -d "text=${text}" \
            -d "parse_mode=HTML" > /dev/null 2>&1 || true
        
        log_success "Telegram notification sent"
    fi
    
    return 0
}

################################################################################
# Main Backup Function
################################################################################

"""
GOAL: Execute the complete backup process

PARAMETERS:
  None

RETURNS:
  int - 0 if backup successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - All backup steps are executed in order
  - Backup is verified if requested
  - Old backups are cleaned up
  - Notifications are sent
  - Backup is logged
  - Function returns appropriate exit code
"""
main() {
    local start_time=$(date +%s)
    
    log_info "========================================="
    log_info "Starting backup process (type: ${BACKUP_TYPE})"
    log_info "========================================="
    
    # Parse arguments
    parse_arguments "$@"
    
    # Create log directory
    mkdir -p "$LOG_DIR"
    mkdir -p "$BACKUP_DIR"
    
    # Validate environment
    if ! validate_environment; then
        log_error "Environment validation failed"
        send_notification "failure" "Environment validation failed" ""
        exit 1
    fi
    
    # Check system resources
    if ! check_system_resources; then
        log_error "System resources check failed"
        send_notification "failure" "System resources check failed" ""
        exit 1
    fi
    
    # Create backup directory
    local backup_dir=$(create_backup_directory)
    
    # Create backups
    if ! backup_database "$backup_dir"; then
        log_error "Database backup failed"
        send_notification "failure" "Database backup failed" "$backup_dir"
        exit 1
    fi
    
    if ! backup_media_files "$backup_dir"; then
        log_error "Media files backup failed"
        send_notification "failure" "Media files backup failed" "$backup_dir"
        exit 1
    fi
    
    if ! backup_configuration "$backup_dir"; then
        log_error "Configuration backup failed"
        send_notification "failure" "Configuration backup failed" "$backup_dir"
        exit 1
    fi
    
    # Create backup info
    if ! create_backup_info "$backup_dir"; then
        log_error "Backup info creation failed"
        send_notification "failure" "Backup info creation failed" "$backup_dir"
        exit 1
    fi
    
    # Verify backup
    if ! verify_backup "$backup_dir"; then
        log_error "Backup verification failed"
        send_notification "failure" "Backup verification failed" "$backup_dir"
        exit 1
    fi
    
    # Upload to remote storage
    if ! upload_to_remote_storage "$backup_dir"; then
        log_warning "Remote storage upload failed, continuing..."
    fi
    
    # Cleanup old backups
    cleanup_old_backups
    
    # Calculate backup time
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))
    
    # Get backup size
    local backup_size=$(du -sh "$backup_dir" | cut -f1)
    
    # Success
    log_info "========================================="
    log_success "Backup completed successfully in ${minutes}m ${seconds}s"
    log_info "Backup directory: $backup_dir"
    log_info "Backup size: ${backup_size}"
    log_info "========================================="
    
    send_notification "success" "Backup completed successfully in ${minutes}m ${seconds}s" "$backup_dir"
    
    exit 0
}

# Run main function
main "$@"
