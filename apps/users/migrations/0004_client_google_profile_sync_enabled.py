from django.db import migrations, models


def disable_sync_for_existing_named_clients(apps, schema_editor):
    Client = apps.get_model("users", "Client")
    Client.objects.update(google_profile_sync_enabled=False)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_rename_avatar_url_client_google_avatar_url_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="google_profile_sync_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            disable_sync_for_existing_named_clients,
            reverse_code=noop_reverse,
        ),
    ]
