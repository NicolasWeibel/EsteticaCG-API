from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0022_alter_combo_slug_alter_combo_title_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="image",
            field=models.ImageField(
                blank=True, null=True, upload_to="catalog/categories/"
            ),
        ),
        migrations.AlterField(
            model_name="objective",
            name="image",
            field=models.ImageField(
                blank=True, null=True, upload_to="catalog/filters/objectives/"
            ),
        ),
    ]
