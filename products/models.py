from django.db import models
from django.db.models import Avg
from accounts.models import Seller


class Category(models.Model):
    name  = models.CharField(max_length=100, unique=True)
    image = models.ImageField(upload_to='category_images/', blank=True, null=True)

    def __str__(self):
        return self.name

    @property
    def image_url(self):
        if self.image:
            val = str(self.image)
            if val.startswith('http://') or val.startswith('https://'):
                return val
            return self.image.url
        return None

    class Meta:
        verbose_name          = 'Category'
        verbose_name_plural   = 'Categories'


class Product(models.Model):
    name        = models.CharField(max_length=200)
    description = models.TextField()
    price       = models.DecimalField(max_digits=10, decimal_places=2)
    stock       = models.PositiveIntegerField(default=0)
    image       = models.ImageField(upload_to='product_images/', blank=True, null=True)
    seller      = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name='products')
    category    = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def image_url(self):
        if self.image:
            val = str(self.image)
            if val.startswith('http://') or val.startswith('https://'):
                return val
            return self.image.url
        return None

    def avg_rating(self):
        """Uses DB aggregation — no Python-side loop, no N+1 query."""
        result = self.reviews.aggregate(avg=Avg('rating'))
        return round(result['avg'], 1) if result['avg'] else 0

    def review_count(self):
        return self.reviews.count()

    def all_images(self):
        """Return main image + extra images as a list of URLs."""
        imgs = []
        if self.image_url:
            imgs.append(self.image_url)
        try:
            for pi in self.extra_images.all().order_by('order'):
                if pi.image:
                    val = str(pi.image)
                    imgs.append(val if val.startswith('http') else pi.image.url)
        except Exception:
            pass
        return imgs

    class Meta:
        verbose_name = 'Product'


class ProductImage(models.Model):
    """Up to 7 extra images per product (plus the main = 8 total)."""
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='extra_images')
    image      = models.ImageField(upload_to='product_images/')
    order      = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Product Image'
        ordering     = ['order']

    @property
    def image_url(self):
        if self.image:
            val = str(self.image)
            return val if val.startswith('http') else self.image.url
        return None

    def __str__(self):
        return f"Image for {self.product.name}"


class ProductVariant(models.Model):
    VARIANT_TYPES = [
        ('size',    'Size'),
        ('color',   'Color'),
        ('storage', 'Storage'),
        ('weight',  'Weight'),
        ('other',   'Other'),
    ]
    product      = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    variant_type = models.CharField(max_length=20, choices=VARIANT_TYPES, default='size')
    value        = models.CharField(max_length=100)
    price_extra  = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    stock        = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Product Variant'

    def __str__(self):
        return f"{self.product.name} — {self.get_variant_type_display()}: {self.value}"


class Review(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    customer   = models.ForeignKey('accounts.Customer', on_delete=models.CASCADE, related_name='reviews')
    rating     = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    comment    = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name    = 'Review'
        unique_together = ('product', 'customer')

    def __str__(self):
        return f"{self.customer.name} → {self.product.name} ({self.rating}★)"


class Wishlist(models.Model):
    customer = models.ForeignKey('accounts.Customer', on_delete=models.CASCADE, related_name='wishlist')
    product  = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name    = 'Wishlist'
        unique_together = ('customer', 'product')

    def __str__(self):
        return f"{self.customer.name} → {self.product.name}"
