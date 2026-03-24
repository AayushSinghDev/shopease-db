from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Fixed migration: uses standard ALTER TABLE without IF NOT EXISTS
    (compatible with MySQL 5.7 and MySQL 8.0+)
    """
    dependencies = [
        ('products', '0003_productimage_productvariant'),
    ]

    operations = [
        migrations.AddField(
            model_name='productimage',
            name='is_primary',
            field=models.BooleanField(default=False),
        ),
    ]
