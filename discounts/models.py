from django.db import models


class DiscountCode(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('flat', 'Flat Amount'),
    ]

    code = models.CharField(max_length=50, unique=True, db_index=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    expiry_date = models.DateField()
    usage_limit = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'accounts.Seller',
        on_delete=models.CASCADE,
        related_name='discount_codes'
    )

    def __str__(self):
        return self.code

    def is_valid(self, cart_total):
        from django.utils import timezone
        today = timezone.now().date()
        if not self.is_active:
            return False, "This code is inactive."
        if today > self.expiry_date:
            return False, "This code has expired."
        if self.used_count >= self.usage_limit:
            return False, "This code has reached its usage limit."
        if cart_total < self.minimum_order_value:
            return False, f"Minimum order value is ₹{self.minimum_order_value}."
        return True, "Valid"

    def get_discount_amount(self, cart_total):
        if self.discount_type == 'percentage':
            return round((cart_total * self.discount_value) / 100, 2)
        else:
            return min(self.discount_value, cart_total)

    class Meta:
        verbose_name = 'Discount Code'