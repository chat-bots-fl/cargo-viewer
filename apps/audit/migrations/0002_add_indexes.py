# Generated migration for adding indexes to AuditLog model

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["user", "action_type", "created_at"], name="audit_user_action_created_idx"),
        ),
    ]
