from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('',                                      views.shop,             name='shop'),
    path('detail/<int:pk>/',                      views.product_detail,   name='product_detail'),
    path('category/',                             views.category_list,    name='category_list'),
    path('wishlist/',                             views.wishlist,         name='wishlist'),
    path('wishlist/toggle/<int:pk>/',             views.toggle_wishlist,  name='toggle_wishlist'),
]
