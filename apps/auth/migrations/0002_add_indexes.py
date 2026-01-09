# Generated migration for adding indexes to TelegramSession model

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("driver_auth", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="telegramsession",
            index=models.Index(fields=["user", "revoked_at"], name="auth_telegram_user_revoked_idx"),
        ),
        migrations.AddIndex(
            model_name="telegramsession",
            index=models.Index(fields=["expires_at"], name="auth_telegram_expires_idx"),
        ),
        migrations.AddIndex(
            model_name="driverprofile",
            index=models.Index(fields=["telegram_user_id"], name="auth_driver_telegram_id_idx"),
        ),
    ]
