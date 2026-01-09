# Production Deployment Plan - Cargo Viewer

**Version:** 1.0  
**Project:** cargo-viewer (Django 5.0)  
**Last Updated:** 2026-01-09

---

## Table of Contents

1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Environment Setup](#environment-setup)
4. [Server Configuration](#server-configuration)
5. [Database Setup](#database-setup)
6. [Redis Setup](#redis-setup)
7. [Environment Variables](#environment-variables)
8. [Application Deployment](#application-deployment)
9. [Nginx Configuration](#nginx-configuration)
10. [SSL Certificates](#ssl-certificates)
11. [CDN Setup](#cdn-setup)
12. [Monitoring Setup](#monitoring-setup)
13. [Migrations](#migrations)
14. [Static Files](#static-files)
15. [Health Checks](#health-checks)
16. [Logging](#logging)
17. [Backup Strategy](#backup-strategy)
18. [Post-Deployment Verification](#post-deployment-verification)
19. [Troubleshooting Guide](#troubleshooting-guide)
20. [Rollback Procedure](#rollback-procedure)

---

## Introduction

This document provides a comprehensive guide for deploying the cargo-viewer Django 5.0 application to production. The deployment includes:

- Django application with Gunicorn
- PostgreSQL database
- Redis for caching and Celery
- Nginx as reverse proxy
- SSL/TLS certificates
- CDN for static files
- Sentry for error monitoring
- Automated backups
- Health checks and monitoring

### Key Features

- **Security:** HTTPS, security headers, rate limiting, CSRF protection
- **Performance:** Database indexing, query optimization, caching
- **Reliability:** Circuit breakers, retry logic, health checks
- **Monitoring:** Sentry integration, audit logging, metrics
- **Scalability:** Docker containerization, horizontal scaling ready

---

## Prerequisites

### System Requirements

- **Operating System:** Ubuntu 22.04 LTS or CentOS 8+
- **CPU:** 2+ cores (recommended 4+)
- **RAM:** 4GB minimum (recommended 8GB+)
- **Storage:** 50GB minimum (recommended 100GB+)
- **Network:** Public IP with open ports 80, 443

### Software Requirements

```bash
# Required software versions
- Docker: 24.0+
- Docker Compose: 2.20+
- Python: 3.11+
- PostgreSQL: 15+
- Redis: 7.0+
- Nginx: 1.24+
- Certbot: 2.0+
```

### Required Services

- **Domain Name:** Registered domain with DNS configured
- **Email:** For SSL certificate notifications
- **CDN Account:** CloudFlare or similar
- **Sentry Account:** For error monitoring
- **Backup Storage:** S3-compatible storage or external server

### Access Requirements

- **SSH Access:** Root or sudo access to server
- **Git Access:** Repository clone permissions
- **Database Access:** PostgreSQL superuser credentials
- **API Keys:** CargoTech API credentials
- **Telegram Bot:** Bot token and webhook URL

---

## Environment Setup

### Step 1: System Update

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    net-tools \
    ufw \
    fail2ban \
    unzip \
    software-properties-common
```

### Step 2: Configure Firewall

```bash
# Configure UFW firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# Verify firewall status
sudo ufw status
```

### Step 3: Create Deployment User

```bash
# Create dedicated deployment user
sudo adduser deploy
sudo usermod -aG sudo deploy

# Create application directory
sudo mkdir -p /opt/cargo-viewer
sudo chown deploy:deploy /opt/cargo-viewer

# Switch to deploy user
su - deploy
```

### Step 4: Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add deploy user to docker group
sudo usermod -aG docker deploy

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

### Step 5: Clone Repository

```bash
# Clone repository
cd /opt/cargo-viewer
git clone <repository-url> .
git checkout production

# Create necessary directories
mkdir -p logs media static backups
```

---

## Server Configuration

### Step 1: System Limits

```bash
# Edit system limits
sudo vim /etc/security/limits.conf

# Add these lines:
* soft nofile 65536
* hard nofile 65536
* soft nproc 65536
* hard nproc 65536
```

### Step 2: Kernel Parameters

```bash
# Edit sysctl configuration
sudo vim /etc/sysctl.conf

# Add these lines:
net.ipv4.tcp_max_syn_backlog = 4096
net.core.somaxconn = 4096
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 30
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5

# Apply changes
sudo sysctl -p
```

### Step 3: Timezone Configuration

```bash
# Set timezone to UTC
sudo timedatectl set-timezone UTC

# Verify
timedatectl
```

### Step 4: Log Rotation

```bash
# Create logrotate configuration
sudo vim /etc/logrotate.d/cargo-viewer

# Add this content:
/opt/cargo-viewer/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 deploy deploy
    sharedscripts
    postrotate
        docker-compose -f /opt/cargo-viewer/docker-compose.prod.yml exec -T web kill -USR1 $(cat /tmp/gunicorn.pid)
    endscript
}
```

---

## Database Setup

### Step 1: PostgreSQL Installation

```bash
# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Step 2: Create Database and User

```bash
# Switch to postgres user
sudo -u postgres psql

# Execute these SQL commands:
CREATE DATABASE cargo_viewer_prod;
CREATE USER cargo_viewer_user WITH PASSWORD '<strong-password>';
GRANT ALL PRIVILEGES ON DATABASE cargo_viewer_prod TO cargo_viewer_user;
ALTER USER cargo_viewer_user CREATEDB;
\q
```

### Step 3: Configure PostgreSQL

```bash
# Edit PostgreSQL configuration
sudo vim /etc/postgresql/15/main/postgresql.conf

# Modify these settings:
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 1310kB
min_wal_size = 1GB
max_wal_size = 4GB

# Edit pg_hba.conf
sudo vim /etc/postgresql/15/main/pg_hba.conf

# Add this line (before other host entries):
host    cargo_viewer_prod    cargo_viewer_user    127.0.0.1/32    md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Step 4: Test Connection

```bash
# Test database connection
psql -h localhost -U cargo_viewer_user -d cargo_viewer_prod -c "SELECT version();"
```

---

## Redis Setup

### Step 1: Install Redis

```bash
# Install Redis
sudo apt install -y redis-server

# Configure Redis
sudo vim /etc/redis/redis.conf

# Modify these settings:
bind 127.0.0.1
port 6379
maxmemory 512mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec
```

### Step 2: Start Redis Service

```bash
# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Verify Redis is running
redis-cli ping
# Should return: PONG
```

### Step 3: Test Redis Connection

```bash
# Test Redis
redis-cli
> SET test "hello"
> GET test
> DEL test
> EXIT
```

---

## Environment Variables

### Step 1: Create .env File

```bash
# Create production environment file
cd /opt/cargo-viewer
cp .env.example .env.production
```

### Step 2: Configure Environment Variables

```bash
# Edit .env.production
vim .env.production
```

```env
# Django Settings
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=<generate-50-char-random-string>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgresql://cargo_viewer_user:<password>@localhost:5432/cargo_viewer_prod
POSTGRES_DB=cargo_viewer_prod
POSTGRES_USER=cargo_viewer_user
POSTGRES_PASSWORD=<strong-password>
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0

# Security
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SECURE_BROWSER_XSS_FILTER=True
SECURE_CONTENT_TYPE_NOSNIFF=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# CORS
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
CORS_ALLOW_CREDENTIALS=True

# CargoTech API
CARGOTECH_API_URL=https://api.cargotech.com
CARGOTECH_API_KEY=<your-api-key>
CARGOTECH_API_SECRET=<your-api-secret>
CARGOTECH_TIMEOUT=30

# Telegram Bot
TELEGRAM_BOT_TOKEN=<your-bot-token>
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/telegram/webhook/
TELEGRAM_ADMIN_CHAT_ID=<admin-chat-id>

# CDN
CDN_ENABLED=True
CDN_URL=https://cdn.yourdomain.com
CDN_PROVIDER=cloudflare

# Sentry
SENTRY_DSN=https://<sentry-dsn>@sentry.io/<project-id>
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<your-email>
EMAIL_HOST_PASSWORD=<your-email-password>
DEFAULT_FROM_EMAIL=<your-email>

# Logging
LOG_LEVEL=INFO
DJANGO_LOG_LEVEL=INFO

# Celery
CELERY_BROKER_URL=redis://127.0.0.1:6379/1
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2
CELERY_TASK_ALWAYS_EAGER=False

# Feature Flags
FEATURE_RATE_LIMITING=True
FEATURE_CIRCUIT_BREAKER=True
FEATURE_AUDIT_LOGGING=True
FEATURE_TELEGRAM_BOT=True
FEATURE_SUBSCRIPTIONS=True

# Performance
GUNICORN_WORKERS=4
GUNICORN_THREADS=4
GUNICORN_TIMEOUT=120
GUNICORN_MAX_REQUESTS=1000
GUNICORN_MAX_REQUESTS_JITTER=100
```

### Step 3: Generate Secret Key

```bash
# Generate Django secret key
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Step 4: Secure Environment File

```bash
# Set restrictive permissions
chmod 600 .env.production
```

---

## Application Deployment

### Step 1: Build Docker Images

```bash
# Build production images
docker-compose -f docker-compose.prod.yml build --no-cache

# Verify images were built
docker images | grep cargo-viewer
```

### Step 2: Initialize Database

```bash
# Run migrations
docker-compose -f docker-compose.prod.yml run --rm web python manage.py migrate --settings=config.settings.production

# Create superuser
docker-compose -f docker-compose.prod.yml run --rm web python manage.py createsuperuser --settings=config.settings.production
```

### Step 3: Collect Static Files

```bash
# Collect static files
docker-compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --settings=config.settings.production --noinput
```

### Step 4: Start Services

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Check service status
docker-compose -f docker-compose.prod.yml ps
```

### Step 5: Verify Application

```bash
# Check application logs
docker-compose -f docker-compose.prod.yml logs -f web

# Test application
curl -I http://localhost:8000/
```

---

## Nginx Configuration

### Step 1: Install Nginx

```bash
# Install Nginx
sudo apt install -y nginx

# Start Nginx
sudo systemctl start nginx
sudo systemctl enable nginx
```

### Step 2: Create Nginx Configuration

```bash
# Copy Nginx configuration
sudo cp nginx.conf /etc/nginx/sites-available/cargo-viewer

# Enable site
sudo ln -s /etc/nginx/sites-available/cargo-viewer /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default
```

### Step 3: Test Nginx Configuration

```bash
# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### Step 4: Configure Nginx for Production

```nginx
# /etc/nginx/sites-available/cargo-viewer
upstream cargo_viewer_backend {
    least_conn;
    server 127.0.0.1:8000 max_fails=3 fail_timeout=30s;
    keepalive 64;
}

# Rate limiting zones
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=general_limit:10m rate=30r/s;
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com www.yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificates (will be configured with Certbot)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https:; font-src 'self' https://cdn.jsdelivr.net; connect-src 'self' https://api.cargotech.com; frame-ancestors 'self';" always;

    # Client body size limit
    client_max_body_size 20M;
    client_body_buffer_size 128k;

    # Timeouts
    client_body_timeout 60s;
    client_header_timeout 60s;
    keepalive_timeout 65s;
    send_timeout 60s;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss application/rss+xml font/truetype font/opentype application/vnd.ms-fontobject image/svg+xml;

    # Logging
    access_log /var/log/nginx/cargo-viewer-access.log;
    error_log /var/log/nginx/cargo-viewer-error.log;

    # Static files (served from CDN in production)
    location /static/ {
        alias /opt/cargo-viewer/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Media files
    location /media/ {
        alias /opt/cargo-viewer/media/;
        expires 30d;
        add_header Cache-Control "public";
    }

    # Health check endpoint
    location /health/ {
        limit_req zone=general_limit burst=50 nodelay;
        proxy_pass http://cargo_viewer_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        access_log off;
    }

    # API endpoints with rate limiting
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        limit_conn conn_limit 10;
        
        proxy_pass http://cargo_viewer_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }

    # Telegram webhook
    location /telegram/webhook/ {
        limit_req zone=general_limit burst=100 nodelay;
        proxy_pass http://cargo_viewer_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Admin panel
    location /admin/ {
        limit_req zone=general_limit burst=10 nodelay;
        limit_conn conn_limit 5;
        
        proxy_pass http://cargo_viewer_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Additional security for admin
        satisfy all;
        allow <your-admin-ip>;
        deny all;
    }

    # All other requests
    location / {
        limit_req zone=general_limit burst=50 nodelay;
        limit_conn conn_limit 20;
        
        proxy_pass http://cargo_viewer_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
        
        proxy_redirect off;
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }

    # Deny access to hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }

    # Deny access to sensitive files
    location ~* \.(env|git|sql|pyc)$ {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

---

## SSL Certificates

### Step 1: Install Certbot

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Stop Nginx temporarily
sudo systemctl stop nginx
```

### Step 2: Obtain SSL Certificate

```bash
# Obtain certificate
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com --email your-email@example.com --agree-tos --non-interactive

# Verify certificate
sudo ls -la /etc/letsencrypt/live/yourdomain.com/
```

### Step 3: Configure Auto-Renewal

```bash
# Test renewal
sudo certbot renew --dry-run

# Certbot automatically sets up cron job
# Verify cron job
sudo systemctl status certbot.timer
```

### Step 4: Restart Nginx

```bash
# Start Nginx
sudo systemctl start nginx

# Verify SSL
curl -I https://yourdomain.com/
```

---

## CDN Setup

### Step 1: CloudFlare Configuration

1. **Add Domain to CloudFlare**
   - Log in to CloudFlare dashboard
   - Add your domain
   - Change nameservers to CloudFlare nameservers

2. **Configure DNS Records**
   ```
   Type: A
   Name: @
   IPv4 address: <your-server-ip>
   Proxy status: Proxied (orange cloud)
   
   Type: A
   Name: www
   IPv4 address: <your-server-ip>
   Proxy status: Proxied (orange cloud)
   ```

3. **Configure CDN Settings**
   - Enable Auto Minify for CSS, JS, HTML
   - Enable Brotli compression
   - Set Browser Cache TTL to 4 hours
   - Enable Always Online
   - Enable Rocket Loader for JavaScript

### Step 2: Upload Static Files to CDN

```bash
# Upload static files to CDN
docker-compose -f docker-compose.prod.yml run --rm web python manage.py upload_static_to_cdn --settings=config.settings.production
```

### Step 3: Configure CDN in Django

```python
# In production.py settings
CDN_ENABLED = True
CDN_URL = 'https://cdn.yourdomain.com'
STATIC_URL = f'{CDN_URL}/static/'
```

### Step 4: Purge Cache on Deploy

```bash
# Purge CloudFlare cache after deployment
curl -X POST "https://api.cloudflare.com/client/v4/zones/<zone-id>/purge_cache" \
  -H "Authorization: Bearer <api-token>" \
  -H "Content-Type: application/json" \
  --data '{"purge_everything":true}'
```

---

## Monitoring Setup

### Step 1: Configure Sentry

```bash
# Install Sentry SDK
pip install sentry-sdk[django]

# Sentry is already configured in production.py
# Verify Sentry is working
python manage.py shell --settings=config.settings.production
>>> import sentry_sdk
>>> sentry_sdk.capture_message("Sentry test message")
```

### Step 2: Configure Application Monitoring

```python
# In production.py settings
SENTRY_DSN = env('SENTRY_DSN')
SENTRY_ENVIRONMENT = 'production'
SENTRY_TRACES_SAMPLE_RATE = 0.1
SENTRY_PROFILES_SAMPLE_RATE = 0.1
SENTRY_SEND_DEFAULT_PII = False
```

### Step 3: Set Up Health Checks

```bash
# Create health check monitoring script
# This will be called by monitoring service
curl -f https://yourdomain.com/health/ || echo "Health check failed"
```

### Step 4: Configure Log Aggregation

```bash
# Install rsyslog for centralized logging
sudo apt install -y rsyslog

# Configure rsyslog to forward logs
sudo vim /etc/rsyslog.d/50-cargo-viewer.conf

# Add:
*.* @@log-server.example.com:514
& stop
```

---

## Migrations

### Step 1: Create Migration Plan

```bash
# Review pending migrations
docker-compose -f docker-compose.prod.yml run --rm web python manage.py showmigrations --settings=config.settings.production --plan
```

### Step 2: Backup Database Before Migration

```bash
# Backup database
docker-compose -f docker-compose.prod.yml exec db pg_dump -U cargo_viewer_user cargo_viewer_prod > backups/pre-migration-$(date +%Y%m%d-%H%M%S).sql
```

### Step 3: Run Migrations

```bash
# Run migrations with zero downtime
docker-compose -f docker-compose.prod.yml run --rm web python manage.py migrate --settings=config.settings.production --noinput
```

### Step 4: Verify Migrations

```bash
# Check migration status
docker-compose -f docker-compose.prod.yml run --rm web python manage.py showmigrations --settings=config.settings.production

# Test application
curl -I https://yourdomain.com/
```

### Step 5: Post-Migration Tasks

```bash
# Create database indexes if needed
docker-compose -f docker-compose.prod.yml run --rm web python manage.py createindexes --settings=config.settings.production

# Analyze tables for query optimization
docker-compose -f docker-compose.prod.yml exec db psql -U cargo_viewer_user -d cargo_viewer_prod -c "ANALYZE;"
```

---

## Static Files

### Step 1: Collect Static Files

```bash
# Collect static files
docker-compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --settings=config.settings.production --noinput --clear
```

### Step 2: Optimize Static Files

```bash
# Optimize images (optional)
docker-compose -f docker-compose.prod.yml run --rm web python manage.py optimize_images --settings=config.settings.production

# Minify CSS and JS (optional)
docker-compose -f docker-compose.prod.yml run --rm web python manage.py minify_static --settings=config.settings.production
```

### Step 3: Upload to CDN

```bash
# Upload static files to CDN
docker-compose -f docker-compose.prod.yml run --rm web python manage.py upload_static_to_cdn --settings=config.settings.production
```

### Step 4: Verify Static Files

```bash
# Test static file access
curl -I https://cdn.yourdomain.com/static/css/main.css
curl -I https://cdn.yourdomain.com/static/js/main.js
```

---

## Health Checks

### Step 1: Configure Health Check Endpoints

```python
# Health check endpoints are already configured in health_views.py
# Available endpoints:
# - /health/ - Basic health check
# - /health/detailed/ - Detailed health check
# - /health/db/ - Database health
# - /health/redis/ - Redis health
# - /health/external/ - External API health
```

### Step 2: Set Up External Monitoring

```bash
# Use services like UptimeRobot, Pingdom, or StatusCake
# Monitor these endpoints:
# - https://yourdomain.com/health/ (every 1 minute)
# - https://yourdomain.com/health/detailed/ (every 5 minutes)
```

### Step 3: Configure Docker Health Checks

```yaml
# In docker-compose.prod.yml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Step 4: Test Health Checks

```bash
# Test health endpoints
curl https://yourdomain.com/health/
curl https://yourdomain.com/health/detailed/
curl https://yourdomain.com/health/db/
curl https://yourdomain.com/health/redis/
```

---

## Logging

### Step 1: Configure Logging

```python
# Logging is configured in production.py
# Log levels:
# - DEBUG: Detailed information
# - INFO: General information
# - WARNING: Warning messages
# - ERROR: Error messages
# - CRITICAL: Critical errors
```

### Step 2: View Logs

```bash
# View application logs
docker-compose -f docker-compose.prod.yml logs -f web

# View Nginx logs
sudo tail -f /var/log/nginx/cargo-viewer-access.log
sudo tail -f /var/log/nginx/cargo-viewer-error.log

# View PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

### Step 3: Configure Log Rotation

```bash
# Log rotation is already configured in Step 4 of Server Configuration
# Verify log rotation
sudo logrotate -d /etc/logrotate.d/cargo-viewer
```

### Step 4: Centralized Logging (Optional)

```bash
# Install ELK Stack or use cloud service
# Example: Loki + Grafana
docker run -d \
  --name loki \
  -p 3100:3100 \
  grafana/loki

docker run -d \
  --name promtail \
  -v /var/log:/var/log:ro \
  -v /opt/cargo-viewer/logs:/opt/cargo-viewer/logs:ro \
  grafana/promtail \
  -config.file=/etc/promtail/config.yml
```

---

## Backup Strategy

### Step 1: Database Backups

```bash
# Create backup script
vim scripts/backup.sh

# Make executable
chmod +x scripts/backup.sh

# Add to crontab for daily backups at 2 AM
crontab -e

# Add:
0 2 * * * /opt/cargo-viewer/scripts/backup.sh
```

### Step 2: Media Files Backup

```bash
# Backup media files
tar -czf backups/media-$(date +%Y%m%d-%H%M%S).tar.gz media/

# Upload to S3 or external storage
aws s3 cp backups/media-$(date +%Y%m%d-%H%M%S).tar.gz s3://cargo-viewer-backups/media/
```

### Step 3: Configuration Backup

```bash
# Backup configuration files
tar -czf backups/config-$(date +%Y%m%d-%H%M%S).tar.gz \
  .env.production \
  docker-compose.prod.yml \
  nginx.conf \
  supervisor.conf
```

### Step 4: Retention Policy

```bash
# Keep backups for 30 days
find backups/ -name "*.sql" -mtime +30 -delete
find backups/ -name "*.tar.gz" -mtime +30 -delete

# Keep weekly backups for 12 weeks
find backups/ -name "*weekly*.sql" -mtime +84 -delete
```

---

## Post-Deployment Verification

### Step 1: Application Health Check

```bash
# Check health endpoint
curl -f https://yourdomain.com/health/ || echo "Health check failed"

# Check detailed health
curl https://yourdomain.com/health/detailed/
```

### Step 2: Database Connectivity

```bash
# Test database connection
docker-compose -f docker-compose.prod.yml exec web python manage.py dbshell --settings=config.settings.production -c "SELECT 1;"
```

### Step 3: Redis Connectivity

```bash
# Test Redis connection
docker-compose -f docker-compose.prod.yml exec web python -c "import redis; r = redis.from_url('redis://redis:6379/0'); print(r.ping())"
```

### Step 4: External API Integration

```bash
# Test CargoTech API
docker-compose -f docker-compose.prod.yml exec web python manage.py test_cargotech_api --settings=config.settings.production
```

### Step 5: Static Files

```bash
# Verify static files are accessible
curl -I https://cdn.yourdomain.com/static/css/main.css
curl -I https://cdn.yourdomain.com/static/js/main.js
```

### Step 6: SSL Certificate

```bash
# Verify SSL certificate
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com </dev/null | openssl x509 -noout -dates

# Check SSL rating
curl https://www.ssllabs.com/ssltest/analyze.html?d=yourdomain.com
```

### Step 7: Security Headers

```bash
# Check security headers
curl -I https://yourdomain.com/ | grep -i "strict-transport-security\|x-frame-options\|x-content-type-options\|x-xss-protection\|content-security-policy"
```

### Step 8: Performance Test

```bash
# Run load test
ab -n 1000 -c 10 https://yourdomain.com/

# Check response times
curl -w "@curl-format.txt" -o /dev/null -s https://yourdomain.com/
```

### Step 9: Admin Panel Access

```bash
# Test admin panel access
curl -I https://yourdomain.com/admin/

# Login with superuser credentials
```

### Step 10: Telegram Bot

```bash
# Test Telegram bot webhook
curl -X POST https://api.telegram.org/bot<bot-token>/setWebhook?url=https://yourdomain.com/telegram/webhook/

# Verify webhook
curl https://api.telegram.org/bot<bot-token>/getWebhookInfo
```

---

## Troubleshooting Guide

### Common Issues

#### 1. Application Not Starting

**Symptoms:** Container exits immediately or returns 500 errors

**Solutions:**
```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs web

# Check environment variables
docker-compose -f docker-compose.prod.yml config

# Restart services
docker-compose -f docker-compose.prod.yml restart web
```

#### 2. Database Connection Errors

**Symptoms:** "connection refused" or "authentication failed" errors

**Solutions:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -h localhost -U cargo_viewer_user -d cargo_viewer_prod -c "SELECT 1;"

# Check DATABASE_URL in .env.production
grep DATABASE_URL .env.production

# Restart database
sudo systemctl restart postgresql
```

#### 3. Redis Connection Errors

**Symptoms:** "Redis connection refused" errors

**Solutions:**
```bash
# Check Redis is running
sudo systemctl status redis-server

# Test connection
redis-cli ping

# Check REDIS_URL in .env.production
grep REDIS_URL .env.production

# Restart Redis
sudo systemctl restart redis-server
```

#### 4. Static Files Not Loading

**Symptoms:** 404 errors for CSS/JS files

**Solutions:**
```bash
# Recollect static files
docker-compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --settings=config.settings.production --noinput

# Check static file permissions
ls -la static/

# Check CDN configuration
curl -I https://cdn.yourdomain.com/static/css/main.css
```

#### 5. SSL Certificate Issues

**Symptoms:** "SSL certificate error" or "certificate expired"

**Solutions:**
```bash
# Check certificate expiration
sudo certbot certificates

# Renew certificate
sudo certbot renew

# Restart Nginx
sudo systemctl restart nginx
```

#### 6. Nginx 502 Bad Gateway

**Symptoms:** Nginx returns 502 error

**Solutions:**
```bash
# Check if Gunicorn is running
docker-compose -f docker-compose.prod.yml ps web

# Check Nginx error logs
sudo tail -f /var/log/nginx/cargo-viewer-error.log

# Restart services
docker-compose -f docker-compose.prod.yml restart web
sudo systemctl restart nginx
```

#### 7. High Memory Usage

**Symptoms:** Server becomes unresponsive due to high memory

**Solutions:**
```bash
# Check memory usage
free -h
docker stats

# Reduce Gunicorn workers
# Edit .env.production:
GUNICORN_WORKERS=2

# Restart application
docker-compose -f docker-compose.prod.yml restart web
```

#### 8. Slow Database Queries

**Symptoms:** Application response time is slow

**Solutions:**
```bash
# Check slow queries
docker-compose -f docker-compose.prod.yml exec db psql -U cargo_viewer_user -d cargo_viewer_prod -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# Analyze tables
docker-compose -f docker-compose.prod.yml exec db psql -U cargo_viewer_user -d cargo_viewer_prod -c "ANALYZE;"

# Create indexes
docker-compose -f docker-compose.prod.yml run --rm web python manage.py createindexes --settings=config.settings.production
```

#### 9. Sentry Not Receiving Errors

**Symptoms:** Errors not appearing in Sentry

**Solutions:**
```bash
# Verify SENTRY_DSN in .env.production
grep SENTRY_DSN .env.production

# Test Sentry integration
docker-compose -f docker-compose.prod.yml run --rm web python -c "import sentry_sdk; sentry_sdk.capture_message('Test message')"

# Check Sentry dashboard
```

#### 10. Telegram Bot Not Responding

**Symptoms:** Bot doesn't respond to messages

**Solutions:**
```bash
# Check webhook URL
curl https://api.telegram.org/bot<bot-token>/getWebhookInfo

# Verify webhook endpoint
curl -X POST https://yourdomain.com/telegram/webhook/ -d '{"update_id": 1}'

# Check TELEGRAM_BOT_TOKEN in .env.production
grep TELEGRAM_BOT_TOKEN .env.production

# Check logs
docker-compose -f docker-compose.prod.yml logs web | grep telegram
```

### Debug Mode

```bash
# Enable debug mode temporarily
# Edit .env.production:
DJANGO_DEBUG=True

# Restart application
docker-compose -f docker-compose.prod.yml restart web

# Check logs
docker-compose -f docker-compose.prod.yml logs -f web

# Don't forget to disable debug mode after debugging!
```

### Get Help

If you encounter issues not covered in this guide:

1. Check application logs: `docker-compose -f docker-compose.prod.yml logs web`
2. Check Nginx logs: `sudo tail -f /var/log/nginx/cargo-viewer-error.log`
3. Check Sentry dashboard for errors
4. Review this deployment guide
5. Contact DevOps team

---

## Rollback Procedure

### Automatic Rollback

The deployment script includes automatic rollback on failure:

```bash
# The deploy.sh script will:
# 1. Backup current version
# 2. Deploy new version
# 3. Run health checks
# 4. Rollback if health checks fail
```

### Manual Rollback

If you need to manually rollback:

```bash
# Run rollback script
./scripts/rollback.sh

# Or manually:
# 1. Restore database backup
docker-compose -f docker-compose.prod.yml exec db psql -U cargo_viewer_user -d cargo_viewer_prod < backups/pre-deployment-<timestamp>.sql

# 2. Restore previous code
git checkout <previous-commit-hash>

# 3. Rebuild and restart
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# 4. Verify rollback
curl https://yourdomain.com/health/
```

### Rollback Verification

After rollback, verify:

```bash
# Check health
curl https://yourdomain.com/health/

# Check database
docker-compose -f docker-compose.prod.yml exec web python manage.py dbshell --settings=config.settings.production -c "SELECT COUNT(*) FROM cargos_cargo;"

# Check logs
docker-compose -f docker-compose.prod.yml logs -f web
```

---

## Maintenance

### Regular Maintenance Tasks

#### Daily
- Monitor application health
- Check error logs in Sentry
- Review system resources

#### Weekly
- Review backup logs
- Check disk space usage
- Update security patches

#### Monthly
- Review and rotate SSL certificates
- Update dependencies
- Performance tuning
- Security audit

### Update Procedure

```bash
# 1. Backup current version
./scripts/backup.sh

# 2. Pull latest changes
git pull origin production

# 3. Update dependencies
docker-compose -f docker-compose.prod.yml build --no-cache

# 4. Run migrations
docker-compose -f docker-compose.prod.yml run --rm web python manage.py migrate --settings=config.settings.production --noinput

# 5. Collect static files
docker-compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --settings=config.settings.production --noinput

# 6. Restart services
docker-compose -f docker-compose.prod.yml up -d

# 7. Verify deployment
curl https://yourdomain.com/health/
```

---

## Security Checklist

### Pre-Deployment

- [ ] All secrets stored in environment variables
- [ ] Database uses strong passwords
- [ ] SSL/TLS certificates configured
- [ ] Security headers enabled
- [ ] Rate limiting configured
- [ ] CORS properly configured
- [ ] Debug mode disabled
- [ ] Sentry monitoring enabled

### Post-Deployment

- [ ] SSL certificate valid
- [ ] Security headers present
- [ ] No exposed sensitive files
- [ ] Database not publicly accessible
- [ ] Rate limiting working
- [ ] CSRF protection enabled
- [ ] Health checks passing
- [ ] No errors in Sentry

---

## Performance Checklist

### Pre-Deployment

- [ ] Database indexes created
- [ ] Query optimization applied
- [ ] Caching configured
- [ ] CDN enabled
- [ ] Gzip compression enabled
- [ ] Static files optimized
- [ ] Image optimization applied

### Post-Deployment

- [ ] Page load time < 2s
- [ ] Time to First Byte < 200ms
- [ ] Database queries optimized
- [ ] Cache hit ratio > 80%
- [ ] No memory leaks
- [ ] CPU usage < 70%
- [ ] Memory usage < 80%

---

## Support

For deployment issues or questions:

- **Documentation:** Check this guide first
- **Sentry:** Review error dashboard
- **Logs:** Check application and Nginx logs
- **Team:** Contact DevOps team

---

## Appendix

### A. Environment Variables Reference

See `.env.example` for complete list of environment variables.

### B. Docker Commands Reference

```bash
# Build images
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Stop services
docker-compose -f docker-compose.prod.yml down

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Execute command in container
docker-compose -f docker-compose.prod.yml exec web <command>

# Run one-off command
docker-compose -f docker-compose.prod.yml run --rm web <command>
```

### C. Useful Commands

```bash
# Check disk usage
df -h

# Check memory usage
free -h

# Check running processes
ps aux

# Check network connections
netstat -tulpn

# Check Docker containers
docker ps -a

# Check Docker logs
docker logs <container-id>

# Restart service
sudo systemctl restart <service-name>

# Check service status
sudo systemctl status <service-name>
```

### D. Contact Information

- **DevOps Team:** devops@example.com
- **On-Call:** +1-555-0123
- **Emergency:** emergency@example.com

---

**End of Production Deployment Plan**
