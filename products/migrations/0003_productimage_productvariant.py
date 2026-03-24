from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Fixed migration: creates ProductImage and ProductVariant in Django state
    AND creates tables safely in MySQL.
    """
    dependencies = [
        ('products', '0002_review_wishlist'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='product_images/')),
                ('order', models.SmallIntegerField(default=0)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='products.product')),
            ],
        ),
        migrations.CreateModel(
            name='ProductVariant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('variant_type', models.CharField(default='size', max_length=20)),
                ('value', models.CharField(max_length=100)),
                ('price_extra', models.DecimalField(decimal_places=2, default=0.0, max_digits=8)),
                ('stock', models.PositiveIntegerField(default=0)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variants', to='products.product')),
            ],
        ),
    ]
