# Generated migration for adding indexes to TelegramSession model

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="telegramsessions",
            index=models.Index(fields=["user", "revoked_at"], name="auth_telegram_user_revoked_idx"),
        ),
        migrations.AddIndex(
            model_name="telegramsessions",
            index=models.Index(fields=["expires_at"], name="auth_telegram_expires_idx"),
        ),
    ]
