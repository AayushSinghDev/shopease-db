from django.db import models
from accounts.models import Customer
from products.models import Product


class Address(models.Model):
    customer   = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='addresses')
    name       = models.CharField(max_length=150, default='')
    full_name  = models.CharField(max_length=150, default='')
    phone      = models.CharField(max_length=15, default='')
    house      = models.CharField(max_length=255)
    city       = models.CharField(max_length=100)
    state      = models.CharField(max_length=100)
    pincode    = models.CharField(max_length=10)
    country    = models.CharField(max_length=100, default='India')
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} — {self.city}, {self.state}"

    class Meta:
        verbose_name = 'Address'
        verbose_name_plural = 'Addresses'


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('confirmed', 'Confirmed'),
        ('shipped',   'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('paid',     'Paid'),
        ('failed',   'Failed'),
        ('refunded', 'Refunded'),
    ]

    customer         = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    address          = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method   = models.CharField(max_length=20, default='cod')
    payment_status   = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_id       = models.CharField(max_length=200, null=True, blank=True)
    razorpay_order_id = models.CharField(max_length=200, null=True, blank=True)
    discount_code    = models.CharField(max_length=50, null=True, blank=True)
    discount_amount  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax              = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total            = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.pk} by {self.customer.name}"

    class Meta:
        verbose_name = 'Order'


class OrderItem(models.Model):
    order         = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product       = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items')
    product_name  = models.CharField(max_length=200)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity      = models.PositiveIntegerField()
    subtotal      = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"

    class Meta:
        verbose_name = 'Order Item'