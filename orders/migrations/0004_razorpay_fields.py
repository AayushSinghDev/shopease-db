from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_rename_date_order_created_at_remove_order_product_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('pending',  'Pending'),
                    ('paid',     'Paid'),
                    ('failed',   'Failed'),
                    ('refunded', 'Refunded'),
                ],
                default='pending',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='razorpay_order_id',
            field=models.CharField(max_length=200, null=True, blank=True),
        ),
    ]
