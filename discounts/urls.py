from django.urls import path
from . import views

app_name = 'discounts'

urlpatterns = [
    path('apply/', views.apply_discount, name='apply'),
    path('remove/', views.remove_discount, name='remove'),
]