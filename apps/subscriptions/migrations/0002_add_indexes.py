# Generated migration for adding indexes to Subscription model

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["user_id", "is_active", "expires_at"], name="sub_user_active_expires_idx"),
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["access_token"], name="sub_access_token_idx"),
        ),
    ]
