import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Tenant",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("slug", models.SlugField(max_length=63, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("settings", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
    ]
