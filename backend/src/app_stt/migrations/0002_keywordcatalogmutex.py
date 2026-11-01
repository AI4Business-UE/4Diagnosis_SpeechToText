from django.db import migrations, models


def create_catalog_mutex(apps, schema_editor):
    KeywordCatalogMutex = apps.get_model("app_stt", "KeywordCatalogMutex")
    KeywordCatalogMutex.objects.create(id=1, revision=0)


class Migration(migrations.Migration):
    dependencies = [
        ("app_stt", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="KeywordCatalogMutex",
            fields=[
                ("id", models.PositiveSmallIntegerField(primary_key=True, serialize=False)),
                ("revision", models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.RunPython(create_catalog_mutex, migrations.RunPython.noop),
    ]
