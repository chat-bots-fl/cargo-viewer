# CDN Setup Guide

## Overview

This guide explains how to configure and deploy static files to a CDN (Content Delivery Network) for the cargo-viewer project. The project supports two CDN providers:

- **Cloudflare R2** - Recommended for cost-effectiveness and performance
- **AWS CloudFront** - Alternative with extensive AWS integration

## Table of Contents

1. [Quick Start](#quick-start)
2. [Cloudflare R2 Setup](#cloudflare-r2-setup)
3. [AWS CloudFront Setup](#aws-cloudfront-setup)
4. [Configuration](#configuration)
5. [Uploading Static Files](#uploading-static-files)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)

---

## Quick Start

### 1. Enable CDN in Settings

Set the following environment variables in your `.env` file:

```bash
CDN_ENABLED=True
CDN_URL=https://cdn.yourdomain.com
CDN_STATIC_PREFIX=static
```

### 2. Configure CDN Provider

Choose your provider and set the required credentials:

**For Cloudflare R2:**
```bash
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_R2_BUCKET=your_bucket_name
CLOUDFLARE_R2_ACCESS_KEY_ID=your_access_key
CLOUDFLARE_R2_SECRET_ACCESS_KEY=your_secret_key
```

**For AWS CloudFront:**
```bash
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_S3_BUCKET=your_bucket_name
AWS_REGION=us-east-1
```

### 3. Upload Static Files

Test with dry run first:
```bash
python manage.py upload_static_to_cdn --provider cloudflare --dry-run
```

Upload for real:
```bash
python manage.py upload_static_to_cdn --provider cloudflare
```

---

## Cloudflare R2 Setup

### Step 1: Create R2 Bucket

1. Log in to your Cloudflare dashboard
2. Navigate to **R2 > Create Bucket**
3. Choose a bucket name (e.g., `cargo-viewer-static`)
4. Select a region (recommended: nearest to your users)
5. Click **Create Bucket**

### Step 2: Create API Token

1. Navigate to **User Profile > API Tokens**
2. Click **Create Token**
3. Use the **Edit Cloudflare R2** template
4. Configure permissions:
   - **Account Resources**: Your account → R2 → Read & Write
5. Click **Continue to summary** → **Create Token**
6. Copy the **Token ID** (this is your `CLOUDFLARE_R2_ACCESS_KEY_ID`)
7. Copy the **Client Secret** (this is your `CLOUDFLARE_R2_SECRET_ACCESS_KEY`)

### Step 3: Find Your Account ID

1. Log in to Cloudflare dashboard
2. Click on your domain
3. Scroll down to **API** section on the right sidebar
4. Copy the **Account ID**

### Step 4: Configure Custom Domain (Optional)

To use a custom domain for your CDN:

1. Navigate to **R2 > your-bucket > Settings**
2. Click **Set up Public Access**
3. Click **Connect Domain**
4. Enter your domain (e.g., `cdn.cargo-viewer.com`)
5. Follow the DNS instructions to add CNAME records

### Step 5: Configure Environment Variables

Add to your `.env` file:

```bash
CDN_ENABLED=True
CDN_URL=https://cdn.cargo-viewer.com
CDN_STATIC_PREFIX=static
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_R2_BUCKET=cargo-viewer-static
CLOUDFLARE_R2_ACCESS_KEY_ID=your_token_id
CLOUDFLARE_R2_SECRET_ACCESS_KEY=your_client_secret
```

---

## AWS CloudFront Setup

### Step 1: Create S3 Bucket

1. Log in to AWS Console
2. Navigate to **S3 > Create Bucket**
3. Choose a bucket name (e.g., `cargo-viewer-static`)
4. Select a region
5. Configure bucket settings:
   - **Block Public Access**: Off (for public CDN access)
   - **Bucket Versioning**: Optional
6. Click **Create Bucket**

### Step 2: Configure Bucket Policy

1. Navigate to your bucket
2. Go to **Permissions > Bucket Policy**
3. Add the following policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::cargo-viewer-static/*"
    }
  ]
}
```

### Step 3: Create CloudFront Distribution

1. Navigate to **CloudFront > Create Distribution**
2. Configure **Origin Settings**:
   - **Origin Domain Name**: Select your S3 bucket
   - **S3 Bucket Access**: Yes use OAI (bucket restricted)
3. Configure **Default Cache Behavior Settings**:
   - **Viewer Protocol Policy**: Redirect HTTP to HTTPS
   - **Allowed HTTP Methods**: GET, HEAD
   - **Cached HTTP Methods**: GET, HEAD
4. Configure **Distribution Settings**:
   - **Price Class**: Use only US, Canada, Europe (or your region)
   - **Alternate Domain Names (CNAMEs)**: `cdn.cargo-viewer.com`
   - **Custom SSL Certificate**: Select your certificate
5. Click **Create Distribution**

### Step 4: Create IAM User

1. Navigate to **IAM > Users > Create User**
2. Username: `cargo-viewer-cdn`
3. Select **Attach policies directly**
4. Create inline policy with permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::cargo-viewer-static",
        "arn:aws:s3:::cargo-viewer-static/*"
      ]
    }
  ]
}
```

5. Create user and copy **Access Key ID** and **Secret Access Key**

### Step 5: Configure Environment Variables

Add to your `.env` file:

```bash
CDN_ENABLED=True
CDN_URL=https://cdn.cargo-viewer.com
CDN_STATIC_PREFIX=static
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_S3_BUCKET=cargo-viewer-static
AWS_REGION=us-east-1
```

---

## Configuration

### Settings Reference

| Setting | Description | Default | Required |
|---------|-------------|---------|----------|
| `CDN_ENABLED` | Enable/disable CDN | `False` | No |
| `CDN_URL` | CDN base URL | `""` | Yes (if enabled) |
| `CDN_STATIC_PREFIX` | Path prefix for static files | `static` | No |

### Environment-Specific Settings

#### Development

CDN is disabled by default in development:

```python
# config/settings/development.py
CDN_ENABLED = False
```

Static files are served locally by WhiteNoise.

#### Production

CDN is enabled in production:

```python
# config/settings/production.py
CDN_ENABLED = True
CDN_URL = "https://cdn.cargo-viewer.com"
CDN_STATIC_PREFIX = "static"
```

### Graceful Degradation

The CDN implementation includes graceful degradation:

- If `CDN_ENABLED` is `False`, static files are served locally
- If `CDN_URL` is empty, falls back to local serving
- Templates automatically use the correct URL via `{% static %}` tag

---

## Uploading Static Files

### Management Command

The `upload_static_to_cdn` command uploads static files to your CDN:

```bash
python manage.py upload_static_to_cdn [options]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--provider` | CDN provider (`cloudflare` or `aws`) | `cloudflare` |
| `--bucket` | Override default bucket name | From env var |
| `--path` | Subdirectory path within bucket | `""` |
| `--dry-run` | Simulate upload without transfer | `False` |

### Examples

**Upload to Cloudflare R2:**
```bash
python manage.py upload_static_to_cdn --provider cloudflare
```

**Upload to AWS S3 (for CloudFront):**
```bash
python manage.py upload_static_to_cdn --provider aws
```

**Dry run to test:**
```bash
python manage.py upload_static_to_cdn --provider cloudflare --dry-run
```

**Upload to specific bucket with path:**
```bash
python manage.py upload_static_to_cdn --provider aws --bucket my-bucket --path static
```

### Deployment Workflow

1. **Collect static files:**
   ```bash
   python manage.py collectstatic --noinput
   ```

2. **Upload to CDN (dry run first):**
   ```bash
   python manage.py upload_static_to_cdn --provider cloudflare --dry-run
   ```

3. **Upload for real:**
   ```bash
   python manage.py upload_static_to_cdn --provider cloudflare
   ```

4. **Verify CDN URL:**
   ```bash
   curl -I https://cdn.cargo-viewer.com/static/css/main.css
   ```

### CI/CD Integration

Add to your deployment script:

```bash
#!/bin/bash

# Collect static files
python manage.py collectstatic --noinput

# Upload to CDN
python manage.py upload_static_to_cdn --provider cloudflare

# Deploy application
# ... rest of deployment
```

---

## Troubleshooting

### CDN Not Working

**Symptom:** Static files still loading from application server

**Solutions:**
1. Verify `CDN_ENABLED=True` in production settings
2. Check `CDN_URL` is set correctly
3. Restart application after changing settings
4. Clear browser cache

### Upload Fails

**Symptom:** `upload_static_to_cdn` command fails

**Solutions:**

**Cloudflare R2:**
1. Verify `CLOUDFLARE_ACCOUNT_ID` is correct
2. Check API token has R2 read/write permissions
3. Ensure bucket name is correct
4. Check network connectivity

**AWS CloudFront:**
1. Verify AWS credentials are correct
2. Check IAM user has S3 permissions
3. Ensure bucket exists and is accessible
4. Verify bucket policy allows public read

### 403 Forbidden Errors

**Symptom:** CDN returns 403 for static files

**Solutions:**

**Cloudflare R2:**
1. Ensure bucket public access is enabled
2. Check custom domain DNS configuration
3. Verify bucket CORS settings

**AWS CloudFront:**
1. Check S3 bucket policy allows public read
2. Verify CloudFront OAI/Origin Access Control
3. Check CloudFront distribution is deployed

### Cache Issues

**Symptom:** Old static files served after update

**Solutions:**
1. Invalidate CloudFront cache:
   ```bash
   aws cloudfront create-invalidation \
     --distribution-id YOUR_DISTRIBUTION_ID \
     --paths "/*"
   ```
2. Clear Cloudflare cache (if using Cloudflare)
3. Use cache-busting version in filenames

### Permission Denied

**Symptom:** Upload fails with permission error

**Solutions:**
1. Verify API token/credentials have write permissions
2. Check bucket ACL settings
3. Ensure IAM policy includes `s3:PutObject`

### Connection Timeout

**Symptom:** Upload times out

**Solutions:**
1. Check network connectivity
2. Verify firewall allows outbound connections
3. Try uploading smaller batches
4. Check CDN service status

---

## Best Practices

### 1. Use Dry Run First

Always test with `--dry-run` before actual upload:

```bash
python manage.py upload_static_to_cdn --provider cloudflare --dry-run
```

### 2. Version Static Files

Use cache-busting in filenames for major updates:

```python
# In templates
{% load static %}
<link rel="stylesheet" href="{% static 'css/main.v1.2.3.css' %}" />
```

### 3. Set Proper Cache Headers

The upload command sets cache headers automatically:

```
Cache-Control: public, max-age=31536000, immutable
```

This caches files for 1 year, reducing CDN costs.

### 4. Monitor CDN Usage

- **Cloudflare R2**: Check usage in Cloudflare dashboard
- **AWS CloudFront**: Monitor via CloudWatch metrics

### 5. Use Environment-Specific URLs

Different environments use different CDN URLs:

```bash
# Development
CDN_URL=https://dev-cdn.cargo-viewer.com

# Staging
CDN_URL=https://staging-cdn.cargo-viewer.com

# Production
CDN_URL=https://cdn.cargo-viewer.com
```

### 6. Backup Static Files

Keep a backup of static files in version control:

```bash
# Backup static files before upload
tar -czf static-backup-$(date +%Y%m%d).tar.gz static/
```

### 7. Automate Uploads

Integrate CDN upload into your CI/CD pipeline:

```yaml
# Example GitHub Actions
- name: Upload to CDN
  run: |
    python manage.py collectstatic --noinput
    python manage.py upload_static_to_cdn --provider cloudflare
```

### 8. Use CDN for All Static Assets

Ensure all static assets use CDN:

- CSS files
- JavaScript files
- Images
- Fonts
- Icons

### 9. Implement Fallback

Configure fallback to local serving if CDN fails:

```python
# In settings.py
CDN_ENABLED = True
CDN_URL = "https://cdn.cargo-viewer.com"
# WhiteNoise serves locally if CDN fails
```

### 10. Monitor Performance

Track CDN performance metrics:

- Cache hit ratio
- Response times
- Bandwidth usage
- Error rates

---

## Additional Resources

- [Cloudflare R2 Documentation](https://developers.cloudflare.com/r2/)
- [AWS CloudFront Documentation](https://docs.aws.amazon.com/cloudfront/)
- [Django Static Files Documentation](https://docs.djangoproject.com/en/5.0/howto/static-files/)
- [WhiteNoise Documentation](https://whitenoise.evans.io/en/stable/)

---

## Support

For issues or questions:

1. Check this troubleshooting guide
2. Review CDN provider documentation
3. Check project logs in `logs/` directory
4. Open an issue in the project repository
