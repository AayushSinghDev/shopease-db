from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
import products.views as product_views
from accounts import seller_views, admin_views
from discounts import views as discount_views

# ── Seller URLs ───────────────────────────────────────────────
seller_urls = [
    path('dashboard/',                      seller_views.seller_dashboard),
    path('products/',                       seller_views.seller_products),
    path('product/add/',                    seller_views.add_product),
    path('product/edit/<int:pk>/',          seller_views.edit_product),
    path('product/delete/<int:pk>/',        seller_views.delete_product),
    path('orders/',                         seller_views.seller_orders),
    path('orders/update/<int:pk>/',         seller_views.update_order_status),
    path('discounts/',                      seller_views.seller_discounts),
    path('discounts/add/',                  discount_views.add_discount),
    path('discounts/delete/<int:code_id>/', discount_views.delete_discount),
    path('discounts/toggle/<int:code_id>/', discount_views.toggle_discount),
]

# ── Admin Panel URLs ──────────────────────────────────────────
admin_panel_urls = [
    path('sellers/',                            admin_views.admin_sellers,         name='admin_sellers'),
    path('sellers/<int:seller_id>/',            admin_views.admin_seller_detail,   name='admin_seller_detail'),
    path('customers/',                          admin_views.admin_customers,       name='admin_customers'),
    path('customers/<int:customer_id>/',        admin_views.admin_customer_detail, name='admin_customer_detail'),
    path('products/',                           admin_views.admin_products,        name='admin_products'),
    path('products/<int:product_id>/',          admin_views.admin_product_detail,  name='admin_product_detail'),
    path('orders/',                             admin_views.admin_orders,          name='admin_orders'),
    path('orders/<int:order_id>/',              admin_views.admin_order_detail,    name='admin_order_detail'),
    path('categories/',                         admin_views.admin_categories,      name='admin_categories'),
    path('categories/<int:category_id>/',       admin_views.admin_category_detail, name='admin_category_detail'),
    path('revenue/',                            admin_views.admin_revenue,         name='admin_revenue'),
    path('reviews/',                            admin_views.admin_reviews,         name='admin_reviews'),
    path('reviews/<int:review_id>/delete/',     admin_views.admin_delete_review,   name='admin_delete_review'),
]

# ── Main URLs ─────────────────────────────────────────────────
urlpatterns = [
    path('admin/',       admin.site.urls),
    path('accounts/',    include('accounts.urls')),
    path('products/',    include('products.urls')),
    path('cart/',        include('orders.urls')),
    path('seller/',      include((seller_urls, 'seller'))),
    path('discount/',    include('discounts.urls')),
    path('admin-panel/', include((admin_panel_urls, 'admin_panel'))),
    path('chatbot/',     include('chatbot.urls')),
    path('',             product_views.home, name='home'),
    # SEO
    path('robots.txt',   TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    # Favicon
    path('favicon.ico', RedirectView.as_view(
        url='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect width=%22100%22 height=%22100%22 rx=%2220%22 fill=%22%230d1b3e%22/><text y=%22.9em%22 font-size=%2275%22 x=%2210%22>🛍</text></svg>',
        permanent=True)),
    # Suppress Chrome DevTools 404 noise
    path('.well-known/appspecific/com.chrome.devtools.json',
         TemplateView.as_view(template_name='robots.txt', content_type='application/json')),

]

handler404 = 'ShopEase.views.page_not_found'
handler500 = 'ShopEase.views.server_error'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
