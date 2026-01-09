#!/bin/bash

################################################################################
# Docker Entrypoint Script for Cargo Viewer Production
#
# GOAL: Initialize and start the application with proper configuration
#
# This script performs:
# - Wait for dependencies (database, redis)
# - Run database migrations
# - Collect static files
# - Start the application
################################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
  - Function never fails
"""
log_info() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[INFO]${NC} ${timestamp} - ${message}"
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
  - Function never fails
"""
log_success() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[SUCCESS]${NC} ${timestamp} - ${message}"
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
  - Function never fails
"""
log_warning() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[WARNING]${NC} ${timestamp} - ${message}"
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
  - Function never fails
"""
log_error() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[ERROR]${NC} ${timestamp} - ${message}" >&2
}

"""
GOAL: Wait for PostgreSQL database to be ready

PARAMETERS:
  host: string - Database host - Not empty
  port: int - Database port - Must be positive
  user: string - Database user - Not empty
  db: string - Database name - Not empty

RETURNS:
  int - 0 if database is ready, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Function waits up to 60 seconds for database
  - Returns 0 if connection successful
  - Returns 1 if timeout reached
"""
wait_for_db() {
    local host="${1:-${DB_HOST:-db}}"
    local port="${2:-${DB_PORT:-5432}}"
    local user="${3:-${POSTGRES_USER:-cargo_viewer_user}}"
    local db="${4:-${POSTGRES_DB:-cargo_viewer_prod}}"
    
    log_info "Waiting for PostgreSQL database at ${host}:${port}..."
    
    local max_attempts=60
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if PGPASSWORD="${POSTGRES_PASSWORD}" pg_isready -h "$host" -p "$port" -U "$user" -d "$db" > /dev/null 2>&1; then
            log_success "PostgreSQL database is ready"
            return 0
        fi
        
        attempt=$((attempt + 1))
        log_info "Waiting for database... (${attempt}/${max_attempts})"
        sleep 1
    done
    
    log_error "Database connection timeout after ${max_attempts} seconds"
    return 1
}

"""
GOAL: Wait for Redis to be ready

PARAMETERS:
  host: string - Redis host - Not empty
  port: int - Redis port - Must be positive

RETURNS:
  int - 0 if Redis is ready, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Function waits up to 30 seconds for Redis
  - Returns 0 if connection successful
  - Returns 1 if timeout reached
"""
wait_for_redis() {
    local host="${1:-${REDIS_HOST:-redis}}"
    local port="${2:-${REDIS_PORT:-6379}}"
    
    log_info "Waiting for Redis at ${host}:${port}..."
    
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if redis-cli -h "$host" -p "$port" ping > /dev/null 2>&1; then
            log_success "Redis is ready"
            return 0
        fi
        
        attempt=$((attempt + 1))
        log_info "Waiting for Redis... (${attempt}/${max_attempts})"
        sleep 1
    done
    
    log_error "Redis connection timeout after ${max_attempts} seconds"
    return 1
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
    
    if python manage.py migrate --noinput; then
        log_success "Database migrations completed successfully"
        return 0
    else
        log_error "Database migrations failed"
        return 1
    fi
}

"""
GOAL: Collect static files

PARAMETERS:
  None

RETURNS:
  int - 0 if collection successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - All static files are collected
  - Collection output is logged
  - Function returns appropriate exit code
"""
collect_static() {
    log_info "Collecting static files..."
    
    if python manage.py collectstatic --noinput --clear; then
        log_success "Static files collected successfully"
        return 0
    else
        log_error "Static files collection failed"
        return 1
    fi
}

"""
GOAL: Create necessary directories

PARAMETERS:
  None

RETURNS:
  int - 0 if directories created successfully, 1 otherwise

RAISES:
  None

GUARANTEES:
  - All required directories are created
  - Directories have proper permissions
  - Function returns appropriate exit code
"""
create_directories() {
    log_info "Creating necessary directories..."
    
    local directories=(
        "/app/media"
        "/app/static"
        "/app/logs"
        "/app/backups"
    )
    
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            log_info "Created directory: $dir"
        fi
    done
    
    log_success "Directories created successfully"
    return 0
}

"""
GOAL: Check if this is a Celery worker process

PARAMETERS:
  None

RETURNS:
  int - 0 if Celery worker, 1 otherwise

RAISES:
  None

GUARANTEES:
  - Returns 0 if command contains 'celery'
  - Returns 1 otherwise
  - Function never fails
"""
is_celery_worker() {
    if [[ "$*" == *"celery"* ]]; then
        return 0
    else
        return 1
    fi
}

"""
GOAL: Main entrypoint function

PARAMETERS:
  None

RETURNS:
  int - 0 if initialization successful, 1 otherwise

RAISES:
  None

GUARANTEES:
  - All initialization steps are executed
  - Application is started properly
  - Function returns appropriate exit code
"""
main() {
    log_info "========================================="
    log_info "Starting Cargo Viewer Application"
    log_info "========================================="
    
    # Create necessary directories
    create_directories
    
    # Wait for dependencies
    if ! wait_for_db; then
        log_error "Failed to connect to database"
        exit 1
    fi
    
    if ! wait_for_redis; then
        log_error "Failed to connect to Redis"
        exit 1
    fi
    
    # Run migrations and collect static only for web server
    if ! is_celery_worker "$@"; then
        run_migrations
        collect_static
    fi
    
    log_info "========================================="
    log_success "Application initialized successfully"
    log_info "Starting application..."
    log_info "========================================="
    
    # Execute the main command
    exec "$@"
}

# Run main function
main "$@"
