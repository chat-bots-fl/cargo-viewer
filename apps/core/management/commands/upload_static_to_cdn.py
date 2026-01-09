"""
GOAL: Upload static files to CDN (Cloudflare R2 or AWS CloudFront).

PARAMETERS:
  cdn_provider: str - CDN provider ("cloudflare" or "aws") - Must be "cloudflare" or "aws"
  dry_run: bool - Simulate upload without actual transfer - Default False
  verbosity: int - Output verbosity level (0-3) - 0=silent, 1=normal, 2=verbose, 3=debug

RETURNS:
  None - Command prints results to stdout

RAISES:
  ValueError: If CDN provider not supported
  ValueError: If required credentials missing
  RuntimeError: If upload fails

GUARANTEES:
  - All static files are uploaded to CDN
  - Upload progress is logged
  - Failed uploads are reported
  - Dry run mode doesn't modify CDN
"""
import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.staticfiles.finders import find
from django.contrib.staticfiles.storage import staticfiles_storage


class Command(BaseCommand):
    help = "Upload static files to CDN (Cloudflare R2 or AWS CloudFront)"

    def __init__(self, *args, **kwargs):
        """
        Initialize command with logger and configuration.
        """
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)
        self.uploaded_count = 0
        self.failed_count = 0
        self.skipped_count = 0

    def add_arguments(self, parser) -> None:
        """
        Add command-line arguments for CDN provider and options.
        """
        parser.add_argument(
            "--provider",
            type=str,
            default="cloudflare",
            choices=["cloudflare", "aws"],
            help="CDN provider (cloudflare or aws)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate upload without actual transfer",
        )
        parser.add_argument(
            "--bucket",
            type=str,
            help="Override default bucket name",
        )
        parser.add_argument(
            "--path",
            type=str,
            default="",
            help="Subdirectory path within bucket (e.g., 'static')",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Upload static files to CDN with progress logging.
        """
        cdn_provider = options["provider"]
        dry_run = options["dry_run"]
        bucket = options.get("bucket")
        path = options.get("path", "")

        self.stdout.write(
            self.style.SUCCESS(f"Uploading static files to {cdn_provider} CDN...")
        )

        if not settings.CDN_ENABLED:
            self.stdout.write(
                self.style.WARNING("CDN_ENABLED is False in settings. Upload may not be needed.")
            )

        # Validate configuration
        self._validate_cdn_config(cdn_provider, bucket)

        # Collect static files
        static_files = self._collect_static_files()

        if not static_files:
            self.stdout.write(self.style.WARNING("No static files found to upload."))
            return

        self.stdout.write(f"Found {len(static_files)} static files to upload.")

        # Upload files
        if cdn_provider == "cloudflare":
            self._upload_to_cloudflare_r2(static_files, bucket, path, dry_run)
        elif cdn_provider == "aws":
            self._upload_to_cloudfront(static_files, bucket, path, dry_run)

        # Print summary
        self._print_summary(dry_run)

    def _validate_cdn_config(self, cdn_provider: str, bucket: Optional[str]) -> None:
        """
        Validate CDN provider configuration and credentials.

        PARAMETERS:
          cdn_provider: str - CDN provider name
          bucket: Optional[str] - Bucket name override

        RAISES:
          ValueError: If configuration is invalid
        """
        if cdn_provider == "cloudflare":
            if not bucket:
                bucket = os.getenv("CLOUDFLARE_R2_BUCKET")
            if not bucket:
                raise ValueError(
                    "Cloudflare R2 bucket not specified. "
                    "Use --bucket or set CLOUDFLARE_R2_BUCKET environment variable."
                )
            if not os.getenv("CLOUDFLARE_ACCOUNT_ID"):
                raise ValueError(
                    "CLOUDFLARE_ACCOUNT_ID environment variable not set."
                )
            if not os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID"):
                raise ValueError(
                    "CLOUDFLARE_R2_ACCESS_KEY_ID environment variable not set."
                )
            if not os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY"):
                raise ValueError(
                    "CLOUDFLARE_R2_SECRET_ACCESS_KEY environment variable not set."
                )

        elif cdn_provider == "aws":
            if not bucket:
                bucket = os.getenv("AWS_S3_BUCKET")
            if not bucket:
                raise ValueError(
                    "AWS S3 bucket not specified. "
                    "Use --bucket or set AWS_S3_BUCKET environment variable."
                )
            if not os.getenv("AWS_ACCESS_KEY_ID"):
                raise ValueError(
                    "AWS_ACCESS_KEY_ID environment variable not set."
                )
            if not os.getenv("AWS_SECRET_ACCESS_KEY"):
                raise ValueError(
                    "AWS_SECRET_ACCESS_KEY environment variable not set."
                )

    def _collect_static_files(self) -> List[Dict[str, Any]]:
        """
        Collect all static files from staticfiles storage.

        RETURNS:
          List[Dict[str, Any]] - List of file dictionaries with path and content
        """
        static_files = []

        # Collect from STATICFILES_DIRS
        for static_dir in settings.STATICFILES_DIRS:
            for root, dirs, files in os.walk(static_dir):
                for file in files:
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(static_dir)
                    static_files.append({
                        "path": relative_path,
                        "full_path": file_path,
                    })

        return static_files

    def _upload_to_cloudflare_r2(
        self,
        static_files: List[Dict[str, Any]],
        bucket: str,
        path: str,
        dry_run: bool
    ) -> None:
        """
        Upload static files to Cloudflare R2.

        PARAMETERS:
          static_files: List[Dict[str, Any]] - Files to upload
          bucket: str - R2 bucket name
          path: str - Subdirectory path
          dry_run: bool - Simulate upload
        """
        try:
            import boto3
            from botocore.client import Config
        except ImportError:
            raise RuntimeError(
                "boto3 is required for Cloudflare R2 uploads. "
                "Install with: pip install boto3"
            )

        # Configure boto3 for Cloudflare R2
        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{os.getenv('CLOUDFLARE_ACCOUNT_ID')}.r2.cloudflarestorage.com",
            aws_access_key_id=os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
        )

        for file_info in static_files:
            file_path = file_info["path"]
            full_path = file_info["full_path"]

            # Build S3 key
            s3_key = str(Path(path) / file_path) if path else str(file_path)

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f"[DRY RUN] Would upload: {s3_key}")
                )
                self.skipped_count += 1
                continue

            try:
                # Upload file
                with open(full_path, "rb") as f:
                    content_type = self._get_content_type(file_path)
                    s3.upload_fileobj(
                        f,
                        bucket,
                        s3_key,
                        ExtraArgs={
                            "ContentType": content_type,
                            "CacheControl": "public, max-age=31536000, immutable",
                        }
                    )

                self.uploaded_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Uploaded: {s3_key}")
                )

            except Exception as e:
                self.failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"✗ Failed to upload {s3_key}: {e}")
                )

    def _upload_to_cloudfront(
        self,
        static_files: List[Dict[str, Any]],
        bucket: str,
        path: str,
        dry_run: bool
    ) -> None:
        """
        Upload static files to AWS S3 (for CloudFront distribution).

        PARAMETERS:
          static_files: List[Dict[str, Any]] - Files to upload
          bucket: str - S3 bucket name
          path: str - Subdirectory path
          dry_run: bool - Simulate upload
        """
        try:
            import boto3
        except ImportError:
            raise RuntimeError(
                "boto3 is required for AWS CloudFront uploads. "
                "Install with: pip install boto3"
            )

        # Configure boto3 for AWS S3
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )

        for file_info in static_files:
            file_path = file_info["path"]
            full_path = file_info["full_path"]

            # Build S3 key
            s3_key = str(Path(path) / file_path) if path else str(file_path)

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f"[DRY RUN] Would upload: {s3_key}")
                )
                self.skipped_count += 1
                continue

            try:
                # Upload file
                with open(full_path, "rb") as f:
                    content_type = self._get_content_type(file_path)
                    s3.upload_fileobj(
                        f,
                        bucket,
                        s3_key,
                        ExtraArgs={
                            "ContentType": content_type,
                            "CacheControl": "public, max-age=31536000, immutable",
                        }
                    )

                self.uploaded_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Uploaded: {s3_key}")
                )

            except Exception as e:
                self.failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"✗ Failed to upload {s3_key}: {e}")
                )

    def _get_content_type(self, file_path: Path) -> str:
        """
        Get MIME content type for file based on extension.

        PARAMETERS:
          file_path: Path - File path

        RETURNS:
          str - MIME content type
        """
        content_types = {
            ".css": "text/css",
            ".js": "application/javascript",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
            ".eot": "application/vnd.ms-fontobject",
            ".ico": "image/x-icon",
            ".json": "application/json",
            ".txt": "text/plain",
            ".html": "text/html",
            ".xml": "application/xml",
        }

        suffix = file_path.suffix.lower()
        return content_types.get(suffix, "application/octet-stream")

    def _print_summary(self, dry_run: bool) -> None:
        """
        Print upload summary with statistics.

        PARAMETERS:
          dry_run: bool - Whether this was a dry run
        """
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("Upload Summary"))
        self.stdout.write("=" * 50)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Skipped (dry run): {self.skipped_count} files")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully uploaded: {self.uploaded_count} files")
            )
            if self.failed_count > 0:
                self.stdout.write(
                    self.style.ERROR(f"Failed to upload: {self.failed_count} files")
                )

        total = self.uploaded_count + self.failed_count + self.skipped_count
        self.stdout.write(f"Total files: {total}")
        self.stdout.write("=" * 50)
