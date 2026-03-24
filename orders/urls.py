from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Cart
    path('',                           views.cart_view,        name='cart'),
    path('add/<int:product_id>/',      views.add_to_cart,      name='add_to_cart'),
    path('increase/<int:product_id>/', views.increase_quantity, name='increase'),
    path('decrease/<int:product_id>/', views.decrease_quantity, name='decrease'),
    path('remove/<int:product_id>/',   views.remove_from_cart,  name='remove'),
    path('clear/',                     views.clear_cart,        name='clear_cart'),
    # Checkout
    path('checkout/',                  views.checkout,          name='checkout'),
    path('confirmation/',              views.confirmation,      name='confirmation'),
    # Razorpay
    path('razorpay/create/',           views.razorpay_create_order, name='razorpay_create'),
    path('razorpay/payment/',          views.razorpay_payment_page, name='razorpay_payment'),
    path('razorpay/verify/',           views.razorpay_verify,       name='razorpay_verify'),
    path('razorpay/failed/',           views.razorpay_failed,       name='razorpay_failed'),
    # My Orders
    path('my-orders/',                 views.my_orders,         name='my_orders'),
    path('my-orders/<int:pk>/',        views.order_detail,      name='order_detail'),
    path('my-orders/<int:pk>/cancel/', views.cancel_order,      name='cancel_order'),
    path('address/<int:address_id>/delete/', views.delete_address, name='delete_address'),
]
