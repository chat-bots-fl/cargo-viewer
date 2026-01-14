#!/bin/bash

################################################################################
# Production PostgreSQL Setup Script for Cargo Viewer
#
# GOAL: Prepare `.env.production`, start PostgreSQL container, and (optionally)
#       apply Django migrations for production.
#
# Usage:
#   ./scripts/setup_db_production.sh
#   ./scripts/setup_db_production.sh --skip-migrations
################################################################################

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.prod.yml"
ENV_FILE="${PROJECT_DIR}/.env.production"
ENV_TEMPLATE_FILE="${PROJECT_DIR}/.env.production.example"

# Defaults (recommended)
DEFAULT_POSTGRES_DB="cargo_viewer_prod"
DEFAULT_POSTGRES_USER="cargo_viewer_user"

# Options
SKIP_MIGRATIONS=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
"""
log_info() {
    local message="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
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
"""
log_success() {
    local message="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
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
"""
log_warning() {
    local message="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
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
"""
log_error() {
    local message="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[ERROR]${NC} ${timestamp} - ${message}" >&2
}

################################################################################
# Helpers
################################################################################

"""
GOAL: Detect a working Docker Compose command

PARAMETERS:
  None

RETURNS:
  None - Sets global DOCKER_COMPOSE_CMD array

RAISES:
  None

GUARANTEES:
  - DOCKER_COMPOSE_CMD is set to either (docker-compose) or (docker compose)
  - Exits with non-zero if Docker Compose is not available
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

    log_error "Docker Compose not found (need docker-compose or docker compose)."
    exit 1
}

"""
GOAL: Run docker compose with production files and env

PARAMETERS:
  args: string[] - Compose arguments - Not empty

RETURNS:
  int - Exit code from docker compose

RAISES:
  None

GUARANTEES:
  - Always uses `docker-compose.prod.yml`
  - Always uses `.env.production` for interpolation via `--env-file`
"""
compose() {
    "${DOCKER_COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

"""
GOAL: Read an env var from `.env.production` without exporting it

PARAMETERS:
  key: string - Variable name - Must be non-empty
  default: string - Default value if missing/empty - Optional

RETURNS:
  string - Raw value (no surrounding quotes removed)

RAISES:
  None

GUARANTEES:
  - Never fails if file is missing; returns default
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

"""
GOAL: Upsert KEY=VALUE into `.env.production`

PARAMETERS:
  key: string - Variable name - Must be non-empty
  value: string - Variable value - May be empty (but usually should not)

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - Updates existing key or appends a new line
  - Leaves other lines unchanged
"""
upsert_env_value() {
    local key="$1"
    local value="$2"

    if [ ! -f "$ENV_FILE" ]; then
        touch "$ENV_FILE"
    fi

    if grep -qE "^${key}=" "$ENV_FILE"; then
        sed -i.bak "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
        rm -f "${ENV_FILE}.bak"
    else
        echo "${key}=${value}" >> "$ENV_FILE"
    fi
}

"""
GOAL: Generate a strong URL-safe password for Postgres

PARAMETERS:
  None

RETURNS:
  string - Random password - Non-empty

RAISES:
  RuntimeError: If no generator is available

GUARANTEES:
  - Returned string contains only URL-safe characters
  - Length is sufficient for production use
"""
generate_password() {
    if command -v python3 &> /dev/null; then
        python3 -c "import secrets; print(secrets.token_urlsafe(48))"
        return 0
    fi

    if command -v python &> /dev/null; then
        python -c "import secrets; print(secrets.token_urlsafe(48))"
        return 0
    fi

    log_error "Cannot generate password: python3/python not found."
    exit 1
}

"""
GOAL: Ensure `.env.production` exists (create from template if needed)

PARAMETERS:
  None

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - `.env.production` exists after execution
"""
ensure_env_file() {
    if [ -f "$ENV_FILE" ]; then
        return 0
    fi

    if [ -f "$ENV_TEMPLATE_FILE" ]; then
        cp "$ENV_TEMPLATE_FILE" "$ENV_FILE"
        log_success "Created $ENV_FILE from $ENV_TEMPLATE_FILE"
        return 0
    fi

    if [ -f "${PROJECT_DIR}/.env.example" ]; then
        cp "${PROJECT_DIR}/.env.example" "$ENV_FILE"
        log_success "Created $ENV_FILE from .env.example"
        return 0
    fi

    touch "$ENV_FILE"
    log_warning "Created empty $ENV_FILE (no template found)"
}

"""
GOAL: Ensure Postgres credentials are set in `.env.production`

PARAMETERS:
  None

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD are non-empty
  - Defaults are applied if missing
"""
ensure_postgres_env() {
    local db
    local user
    local password

    db=$(get_env_value "POSTGRES_DB" "$DEFAULT_POSTGRES_DB")
    user=$(get_env_value "POSTGRES_USER" "$DEFAULT_POSTGRES_USER")
    password=$(get_env_value "POSTGRES_PASSWORD" "")

    if [ -z "$db" ]; then
        db="$DEFAULT_POSTGRES_DB"
    fi
    if [ -z "$user" ]; then
        user="$DEFAULT_POSTGRES_USER"
    fi

    if [ -z "$password" ] || [[ "$password" == CHANGE_ME__* ]]; then
        password=$(generate_password)
        log_warning "POSTGRES_PASSWORD was empty/placeholder; generated a new strong password"
        upsert_env_value "POSTGRES_PASSWORD" "$password"
    fi

    upsert_env_value "POSTGRES_DB" "$db"
    upsert_env_value "POSTGRES_USER" "$user"

    log_info "Postgres settings (write these to .env.production if needed):"
    echo "  POSTGRES_DB=${db}"
    echo "  POSTGRES_USER=${user}"
    echo "  POSTGRES_PASSWORD=${password}"
}

"""
GOAL: Ensure host directories for bind-mounted volumes exist

PARAMETERS:
  None

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - `/opt/cargo-viewer/data/postgres` exists if permissions allow
"""
ensure_volume_dirs() {
    local pg_dir="/opt/cargo-viewer/data/postgres"
    local redis_dir="/opt/cargo-viewer/data/redis"

    for dir in "$pg_dir" "$redis_dir"; do
        if [ -d "$dir" ]; then
            continue
        fi

        if command -v sudo &> /dev/null; then
            sudo mkdir -p "$dir" || true
        else
            mkdir -p "$dir" || true
        fi

        if [ -d "$dir" ]; then
            log_success "Created directory: $dir"
        else
            log_warning "Could not create directory: $dir (create it manually)"
        fi
    done
}

"""
GOAL: Start PostgreSQL container and wait for readiness

PARAMETERS:
  None

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - Exits with non-zero if DB is not ready within timeout
"""
start_and_wait_db() {
    log_info "Starting PostgreSQL container (service: db)..."
    compose up -d db

    log_info "Waiting for PostgreSQL to be ready..."
    local attempts=60
    local i
    for i in $(seq 1 "$attempts"); do
        if compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > /dev/null 2>&1; then
            log_success "PostgreSQL is ready"
            return 0
        fi
        sleep 1
    done

    log_error "PostgreSQL did not become ready in ${attempts}s"
    log_error "Check logs: ${DOCKER_COMPOSE_CMD[*]} --env-file \"$ENV_FILE\" -f \"$COMPOSE_FILE\" logs db"
    exit 1
}

"""
GOAL: Apply Django migrations against production settings

PARAMETERS:
  None

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - Exits non-zero on migration failure
"""
run_migrations() {
    log_info "Applying Django migrations (production settings)..."
    compose run --rm web python manage.py migrate --settings=config.settings.production --noinput
    log_success "Migrations applied"
}

"""
GOAL: Parse CLI arguments for this script

PARAMETERS:
  args: array - CLI args - May be empty

RETURNS:
  None - Sets global options

RAISES:
  None

GUARANTEES:
  - Unknown args cause exit with error
"""
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --skip-migrations)
                SKIP_MIGRATIONS=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [--skip-migrations]"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Usage: $0 [--skip-migrations]"
                exit 1
                ;;
        esac
    done
}

################################################################################
# Main
################################################################################

main() {
    parse_args "$@"

    detect_docker_compose

    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running (docker info failed)."
        exit 1
    fi

    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Compose file not found: $COMPOSE_FILE"
        exit 1
    fi

    ensure_env_file
    ensure_postgres_env
    ensure_volume_dirs
    start_and_wait_db

    if [ "$SKIP_MIGRATIONS" = false ]; then
        run_migrations
    else
        log_warning "Skipping migrations (--skip-migrations)"
    fi

    log_success "Production DB setup completed"
}

main "$@"

