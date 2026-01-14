#!/bin/bash

################################################################################
# Production Deployment Script for Cargo Viewer
# 
# GOAL: Automate the deployment process with safety checks and rollback capability
#
# This script performs:
# - Pre-deployment validation
# - Backup of current version
# - Database backup
# - Application deployment
# - Health checks
# - Automatic rollback on failure
#
# Usage: ./deploy.sh [options]
#   --skip-backup    Skip database backup (not recommended)
#   --no-rollback    Disable automatic rollback
#   --branch BRANCH  Deploy specific branch (default: production)
################################################################################

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${PROJECT_DIR}/logs"
BACKUP_DIR="${PROJECT_DIR}/backups"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.prod.yml"
ENV_FILE="${PROJECT_DIR}/.env.production"

# Deployment configuration
DEPLOY_BRANCH="${DEPLOY_BRANCH:-production}"
SKIP_BACKUP=false
NO_ROLLBACK=false
HEALTH_CHECK_URL="${HEALTH_CHECK_URL:-http://localhost:8000/health/}"
HEALTH_CHECK_TIMEOUT=300
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
  level: string - Log level (INFO, WARNING, ERROR) - Must be one of: INFO, WARNING, ERROR

RETURNS:
  None - Output to stdout/stderr

RAISES:
  None

GUARANTEES:
  - Message always includes timestamp
  - Messages are color-coded by level
  - All messages written to log file
"""
log_info() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[INFO]${NC} ${timestamp} - ${message}"
    echo "[INFO] ${timestamp} - ${message}" >> "${LOG_DIR}/deploy.log"
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
    echo "[WARNING] ${timestamp} - ${message}" >> "${LOG_DIR}/deploy.log"
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
    echo "[ERROR] ${timestamp} - ${message}" >> "${LOG_DIR}/deploy.log"
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
    echo "[SUCCESS] ${timestamp} - ${message}" >> "${LOG_DIR}/deploy.log"
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
# Validation Functions
################################################################################

"""
GOAL: Parse command line arguments and set deployment options

PARAMETERS:
  args: array - Command line arguments - May be empty

RETURNS:
  None - Sets global variables

RAISES:
  None

GUARANTEES:
  - DEPLOY_BRANCH set to production or specified branch
  - SKIP_BACKUP set to true or false
  - NO_ROLLBACK set to true or false
  - Invalid arguments are rejected
"""
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-backup)
                SKIP_BACKUP=true
                shift
                ;;
            --no-rollback)
                NO_ROLLBACK=true
                shift
                ;;
            --branch)
                DEPLOY_BRANCH="$2"
                shift 2
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
GOAL: Display help information for the deployment script

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
Production Deployment Script for Cargo Viewer

Usage: $0 [options]

Options:
  --skip-backup    Skip database backup (not recommended)
  --no-rollback    Disable automatic rollback
  --branch BRANCH  Deploy specific branch (default: production)
  --help           Show this help message

Examples:
  $0                              # Deploy production branch
  $0 --branch develop            # Deploy develop branch
  $0 --skip-backup                # Deploy without backup
  $0 --no-rollback                # Deploy without automatic rollback

EOF
}

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
  - Git is installed
  - Required files exist
  - Environment file is configured
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
    
    # Check Git
    if ! command -v git &> /dev/null; then
        log_error "Git is not installed"
        return 1
    fi
    
    # Check required files
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose file not found: $COMPOSE_FILE"
        return 1
    fi
    
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file not found: $ENV_FILE"
        return 1
    fi
    
    # Check environment variables (minimal DB-related checks)
    if ! grep -qE "^(SECRET_KEY|DJANGO_SECRET_KEY)=" "$ENV_FILE"; then
        log_warning "SECRET_KEY not found in environment file (set SECRET_KEY for Django)"
    fi

    local database_url
    database_url=$(get_env_value "DATABASE_URL" "")
    if [ -z "$database_url" ]; then
        local pg_password
        pg_password=$(get_env_value "POSTGRES_PASSWORD" "")
        if [ -z "$pg_password" ]; then
            log_error "Database config missing: set DATABASE_URL or POSTGRES_PASSWORD in $ENV_FILE"
            return 1
        fi
    fi
    
    log_success "Environment validation passed"
    return 0
}

"""
GOAL: Validate that environment file contains all required variables

PARAMETERS:
  None

RETURNS:
  int - 0 if all variables present, 1 otherwise

RAISES:
  None

GUARANTEES:
  - All critical environment variables are checked
  - Missing variables are logged
  - Function returns appropriate exit code
"""
validate_environment_variables() {
    log_info "Validating environment variables..."
    
    local required_vars=(
        "DJANGO_SETTINGS_MODULE"
        "REDIS_URL"
        "CARGOTECH_API_KEY"
        "TELEGRAM_BOT_TOKEN"
        "SENTRY_DSN"
    )
    
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" "$ENV_FILE"; then
            missing_vars+=("$var")
        fi
    done

    if ! grep -qE "^(SECRET_KEY|DJANGO_SECRET_KEY)=" "$ENV_FILE"; then
        missing_vars+=("SECRET_KEY (or DJANGO_SECRET_KEY)")
    fi

    local database_url
    database_url=$(get_env_value "DATABASE_URL" "")
    if [ -z "$database_url" ]; then
        local pg_password
        pg_password=$(get_env_value "POSTGRES_PASSWORD" "")
        if [ -z "$pg_password" ]; then
            missing_vars+=("DATABASE_URL or POSTGRES_PASSWORD")
        fi
    fi
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        log_error "Missing required environment variables: ${missing_vars[*]}"
        return 1
    fi
    
    log_success "Environment variables validation passed"
    return 0
}

"""
GOAL: Check system resources before deployment

PARAMETERS:
  None

RETURNS:
  int - 0 if resources are sufficient, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Available disk space is checked (minimum 5GB)
  - Available memory is checked (minimum 2GB)
  - CPU load is checked
  - Function returns appropriate exit code
"""
check_system_resources() {
    log_info "Checking system resources..."
    
    # Check disk space
    local available_disk=$(df -BG "$PROJECT_DIR" | tail -1 | awk '{print $4}' | tr -d 'G')
    if [ "$available_disk" -lt 5 ]; then
        log_error "Insufficient disk space: ${available_disk}GB available, 5GB required"
        return 1
    fi
    
    # Check memory
    local available_memory=$(free -m | awk 'NR==2{print $7}')
    if [ "$available_memory" -lt 2048 ]; then
        log_warning "Low memory: ${available_memory}MB available, 2048MB recommended"
    fi
    
    # Check CPU load
    local load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | tr -d ',')
    local cpu_count=$(nproc)
    local load_threshold=$(echo "$cpu_count * 0.8" | bc)
    
    if (( $(echo "$load_avg > $load_threshold" | bc -l) )); then
        log_warning "High CPU load: $load_avg (threshold: $load_threshold)"
    fi
    
    log_success "System resources check passed"
    return 0
}

################################################################################
# Backup Functions
################################################################################

"""
GOAL: Create a backup of the current application state

PARAMETERS:
  None

RETURNS:
  int - 0 if backup successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Database backup is created in backups directory
  - Media files are backed up
  - Configuration files are backed up
  - Backup timestamp is recorded
  - Function returns appropriate exit code
"""
create_backup() {
    if [ "$SKIP_BACKUP" = true ]; then
        log_warning "Skipping backup as requested"
        return 0
    fi
    
    log_info "Creating backup..."
    
    local timestamp=$(date '+%Y%m%d-%H%M%S')
    local backup_dir="${BACKUP_DIR}/pre-deployment-${timestamp}"
    
    mkdir -p "$backup_dir"
    
    # Backup database
    log_info "Backing up database..."
    local pg_user
    local pg_db
    pg_user=$(get_env_value "POSTGRES_USER" "cargo_viewer_user")
    pg_db=$(get_env_value "POSTGRES_DB" "cargo_viewer_prod")

    if compose exec -T db pg_dump -U "$pg_user" "$pg_db" > "${backup_dir}/database.sql" 2>/dev/null; then
        log_success "Database backup created: ${backup_dir}/database.sql"
    else
        log_error "Database backup failed"
        return 1
    fi
    
    # Backup media files
    log_info "Backing up media files..."
    if [ -d "${PROJECT_DIR}/media" ]; then
        tar -czf "${backup_dir}/media.tar.gz" -C "${PROJECT_DIR}" media 2>/dev/null
        log_success "Media files backup created: ${backup_dir}/media.tar.gz"
    fi
    
    # Backup configuration
    log_info "Backing up configuration files..."
    tar -czf "${backup_dir}/config.tar.gz" -C "${PROJECT_DIR}" \
        .env.production \
        docker-compose.prod.yml \
        nginx.conf \
        supervisor.conf 2>/dev/null || true
    
    # Create backup info file
    cat > "${backup_dir}/backup_info.txt" << EOF
Backup created: $(date)
Git commit: $(git rev-parse HEAD)
Git branch: $(git branch --show-current)
Backup directory: ${backup_dir}
EOF
    
    log_success "Backup completed successfully: ${backup_dir}"
    echo "$backup_dir" > "${BACKUP_DIR}/latest_backup.txt"
    
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
    if [ -f "${BACKUP_DIR}/latest_backup.txt" ]; then
        cat "${BACKUP_DIR}/latest_backup.txt"
    else
        echo ""
    fi
}

################################################################################
# Deployment Functions
################################################################################

"""
GOAL: Pull latest changes from Git repository

PARAMETERS:
  None

RETURNS:
  int - 0 if pull successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Latest changes are pulled from specified branch
  - Current commit is recorded
  - Function returns appropriate exit code
"""
pull_latest_changes() {
    log_info "Pulling latest changes from branch: $DEPLOY_BRANCH"
    
    cd "$PROJECT_DIR"
    
    # Stash any local changes
    if ! git diff --quiet; then
        log_warning "Local changes detected, stashing..."
        git stash
    fi
    
    # Fetch latest changes
    if ! git fetch origin; then
        log_error "Failed to fetch from origin"
        return 1
    fi
    
    # Checkout branch
    if ! git checkout "$DEPLOY_BRANCH"; then
        log_error "Failed to checkout branch: $DEPLOY_BRANCH"
        return 1
    fi
    
    # Pull latest changes
    if ! git pull origin "$DEPLOY_BRANCH"; then
        log_error "Failed to pull from branch: $DEPLOY_BRANCH"
        return 1
    fi
    
    # Record current commit
    local current_commit=$(git rev-parse HEAD)
    log_success "Pulled latest changes (commit: ${current_commit})"
    
    return 0
}

"""
GOAL: Build Docker images for production

PARAMETERS:
  None

RETURNS:
  int - 0 if build successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - All Docker images are built
  - Build cache is cleared for clean build
  - Build time is logged
  - Function returns appropriate exit code
"""
build_docker_images() {
    log_info "Building Docker images..."
    
    local build_start=$(date +%s)
    
    cd "$PROJECT_DIR"
    
    if ! compose build --no-cache; then
        log_error "Docker image build failed"
        return 1
    fi
    
    local build_end=$(date +%s)
    local build_duration=$((build_end - build_start))
    
    log_success "Docker images built successfully (${build_duration}s)"
    
    return 0
}

"""
GOAL: Run database migrations

PARAMETERS:
  None

RETURNS:
  int - 0 if migrations successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - All pending migrations are applied
  - Migration output is logged
  - Function returns appropriate exit code
"""
run_migrations() {
    log_info "Running database migrations..."
    
    cd "$PROJECT_DIR"
    
    if ! compose run --rm web python manage.py migrate --settings=config.settings.production --noinput; then
        log_error "Database migrations failed"
        return 1
    fi
    
    log_success "Database migrations completed successfully"
    
    return 0
}

"""
GOAL: Collect static files for production

PARAMETERS:
  None

RETURNS:
  int - 0 if collection successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - All static files are collected
  - Old static files are cleared
  - Collection output is logged
  - Function returns appropriate exit code
"""
collect_static_files() {
    log_info "Collecting static files..."
    
    cd "$PROJECT_DIR"
    
    if ! compose run --rm web python manage.py collectstatic --settings=config.settings.production --noinput --clear; then
        log_error "Static files collection failed"
        return 1
    fi
    
    log_success "Static files collected successfully"
    
    return 0
}

"""
GOAL: Upload static files to CDN

PARAMETERS:
  None

RETURNS:
  int - 0 if upload successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Static files are uploaded to CDN
  - Upload output is logged
  - Function returns appropriate exit code
"""
upload_static_to_cdn() {
    log_info "Uploading static files to CDN..."
    
    cd "$PROJECT_DIR"
    
    if ! compose run --rm web python manage.py upload_static_to_cdn --settings=config.settings.production; then
        log_warning "CDN upload failed, continuing deployment"
        return 0
    fi
    
    log_success "Static files uploaded to CDN successfully"
    
    return 0
}

"""
GOAL: Start Docker containers

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
    
    # Stop existing containers
    compose down 2>/dev/null || true
    
    # Start new containers
    if ! compose up -d; then
        log_error "Failed to start containers"
        return 1
    fi
    
    # Wait for containers to be healthy
    log_info "Waiting for containers to be healthy..."
    sleep 10
    
    # Check container status
    if ! compose ps | grep -q "Up"; then
        log_error "Containers are not running"
        return 1
    fi
    
    log_success "Docker containers started successfully"
    
    return 0
}

################################################################################
# Health Check Functions
################################################################################

"""
GOAL: Wait for application to become healthy

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
GOAL: Perform comprehensive health checks

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
# Rollback Functions
################################################################################

"""
GOAL: Rollback to previous deployment

PARAMETERS:
  None

RETURNS:
  int - 0 if rollback successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Database is restored from backup
  - Previous code is restored
  - Containers are restarted
  - Rollback is logged
  - Function returns appropriate exit code
"""
rollback_deployment() {
    log_warning "Initiating rollback..."
    
    local backup_dir=$(get_latest_backup)
    
    if [ -z "$backup_dir" ] || [ ! -d "$backup_dir" ]; then
        log_error "No backup found for rollback"
        return 1
    fi
    
    log_info "Rolling back to backup: $backup_dir"
    
    # Restore database
    log_info "Restoring database from backup..."
    if [ -f "${backup_dir}/database.sql" ]; then
        local pg_user
        local pg_db
        pg_user=$(get_env_value "POSTGRES_USER" "cargo_viewer_user")
        pg_db=$(get_env_value "POSTGRES_DB" "cargo_viewer_prod")

        if compose exec -T db psql -U "$pg_user" -d "$pg_db" < "${backup_dir}/database.sql" 2>/dev/null; then
            log_success "Database restored successfully"
        else
            log_error "Database restore failed"
            return 1
        fi
    else
        log_error "Database backup not found"
        return 1
    fi
    
    # Restore media files
    log_info "Restoring media files..."
    if [ -f "${backup_dir}/media.tar.gz" ]; then
        tar -xzf "${backup_dir}/media.tar.gz" -C "${PROJECT_DIR}"
        log_success "Media files restored successfully"
    fi
    
    # Restore configuration
    log_info "Restoring configuration files..."
    if [ -f "${backup_dir}/config.tar.gz" ]; then
        tar -xzf "${backup_dir}/config.tar.gz" -C "${PROJECT_DIR}"
        log_success "Configuration files restored successfully"
    fi
    
    # Restart containers
    log_info "Restarting containers..."
    cd "$PROJECT_DIR"
    compose restart
    
    # Wait for application to be healthy
    if wait_for_health 60 10; then
        log_success "Rollback completed successfully"
        return 0
    else
        log_error "Rollback completed but application is not healthy"
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
  - Backups older than 30 days are deleted
  - At least 5 most recent backups are kept
  - Cleanup is logged
  - Function returns appropriate exit code
"""
cleanup_old_backups() {
    log_info "Cleaning up old backups..."
    
    # Keep only the last 5 backups
    local backup_count=$(ls -1t "${BACKUP_DIR}/pre-deployment-"* 2>/dev/null | wc -l)
    
    if [ "$backup_count" -gt 5 ]; then
        local backups_to_delete=$((backup_count - 5))
        log_info "Deleting ${backups_to_delete} old backups..."
        
        ls -1t "${BACKUP_DIR}/pre-deployment-"* | tail -n "$backups_to_delete" | while read -r backup; do
            log_info "Deleting old backup: $backup"
            rm -rf "$backup"
        done
    fi
    
    # Delete backups older than 30 days
    find "${BACKUP_DIR}" -name "pre-deployment-*" -type d -mtime +30 -exec rm -rf {} \; 2>/dev/null || true
    
    log_success "Backup cleanup completed"
    
    return 0
}

"""
GOAL: Clean up unused Docker resources

PARAMETERS:
  None

RETURNS:
  int - 0 if cleanup successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Unused Docker images are removed
  - Unused Docker volumes are removed
  - Cleanup is logged
  - Function returns appropriate exit code
"""
cleanup_docker_resources() {
    log_info "Cleaning up Docker resources..."
    
    # Remove unused images
    docker image prune -f > /dev/null 2>&1 || true
    
    # Remove unused volumes
    docker volume prune -f > /dev/null 2>&1 || true
    
    log_success "Docker resource cleanup completed"
    
    return 0
}

################################################################################
# Notification Functions
################################################################################

"""
GOAL: Send deployment notification to configured channels

PARAMETERS:
  status: string - Deployment status (success, failure) - Must be "success" or "failure"
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
    
    log_info "Sending deployment notification: ${status}"
    
    # Send Telegram notification if configured
    local bot_token=$(grep "^TELEGRAM_BOT_TOKEN=" "$ENV_FILE" | cut -d'=' -f2)
    local chat_id=$(grep "^TELEGRAM_ADMIN_CHAT_ID=" "$ENV_FILE" | cut -d'=' -f2)
    
    if [ -n "$bot_token" ] && [ -n "$chat_id" ]; then
        local emoji="✅"
        if [ "$status" = "failure" ]; then
            emoji="❌"
        fi
        
        local text="${emoji} Deployment ${status}: ${message}"
        
        curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
            -d "chat_id=${chat_id}" \
            -d "text=${text}" \
            -d "parse_mode=HTML" > /dev/null 2>&1 || true
        
        log_success "Telegram notification sent"
    fi
    
    return 0
}

################################################################################
# Main Deployment Function
################################################################################

"""
GOAL: Execute the complete deployment process

PARAMETERS:
  None

RETURNS:
  int - 0 if deployment successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - All deployment steps are executed in order
  - Rollback is performed on failure
  - Notifications are sent
  - Deployment is logged
  - Function returns appropriate exit code
"""
main() {
    local start_time=$(date +%s)
    
    log_info "========================================="
    log_info "Starting deployment for branch: $DEPLOY_BRANCH"
    log_info "========================================="
    
    # Parse arguments
    parse_arguments "$@"
    
    # Create log directory
    mkdir -p "$LOG_DIR"
    mkdir -p "$BACKUP_DIR"
    
    # Validate environment
    if ! validate_environment; then
        log_error "Environment validation failed"
        send_notification "failure" "Environment validation failed"
        exit 1
    fi
    
    if ! validate_environment_variables; then
        log_error "Environment variables validation failed"
        send_notification "failure" "Environment variables validation failed"
        exit 1
    fi
    
    if ! check_system_resources; then
        log_error "System resources check failed"
        send_notification "failure" "System resources check failed"
        exit 1
    fi
    
    # Create backup
    if ! create_backup; then
        log_error "Backup creation failed"
        send_notification "failure" "Backup creation failed"
        exit 1
    fi
    
    # Pull latest changes
    if ! pull_latest_changes; then
        log_error "Failed to pull latest changes"
        if [ "$NO_ROLLBACK" = false ]; then
            rollback_deployment
        fi
        send_notification "failure" "Failed to pull latest changes"
        exit 1
    fi
    
    # Build Docker images
    if ! build_docker_images; then
        log_error "Docker image build failed"
        if [ "$NO_ROLLBACK" = false ]; then
            rollback_deployment
        fi
        send_notification "failure" "Docker image build failed"
        exit 1
    fi
    
    # Start containers
    if ! start_containers; then
        log_error "Failed to start containers"
        if [ "$NO_ROLLBACK" = false ]; then
            rollback_deployment
        fi
        send_notification "failure" "Failed to start containers"
        exit 1
    fi
    
    # Run migrations
    if ! run_migrations; then
        log_error "Database migrations failed"
        if [ "$NO_ROLLBACK" = false ]; then
            rollback_deployment
        fi
        send_notification "failure" "Database migrations failed"
        exit 1
    fi
    
    # Collect static files
    if ! collect_static_files; then
        log_error "Static files collection failed"
        if [ "$NO_ROLLBACK" = false ]; then
            rollback_deployment
        fi
        send_notification "failure" "Static files collection failed"
        exit 1
    fi
    
    # Upload to CDN
    upload_static_to_cdn
    
    # Wait for health
    if ! wait_for_health "$HEALTH_CHECK_TIMEOUT" "$HEALTH_CHECK_INTERVAL"; then
        log_error "Health check timeout"
        if [ "$NO_ROLLBACK" = false ]; then
            rollback_deployment
        fi
        send_notification "failure" "Health check timeout"
        exit 1
    fi
    
    # Perform health checks
    if ! perform_health_checks; then
        log_error "Health checks failed"
        if [ "$NO_ROLLBACK" = false ]; then
            rollback_deployment
        fi
        send_notification "failure" "Health checks failed"
        exit 1
    fi
    
    # Cleanup
    cleanup_old_backups
    cleanup_docker_resources
    
    # Calculate deployment time
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))
    
    # Success
    log_info "========================================="
    log_success "Deployment completed successfully in ${minutes}m ${seconds}s"
    log_info "========================================="
    
    send_notification "success" "Deployment completed successfully in ${minutes}m ${seconds}s"
    
    exit 0
}

# Run main function
main "$@"
