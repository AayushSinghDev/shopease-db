from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('',                    views.home,             name='home'),
    path('login/',              views.login_view,       name='login'),
    path('register/',           views.register_view,    name='register'),
    path('logout/',             views.logout_view,      name='logout'),
    path('dashboard/customer/', views.customer_dashboard, name='customer_dashboard'),
    path('dashboard/seller/',   views.seller_dashboard,   name='seller_dashboard'),
    path('dashboard/admin/',    views.admin_dashboard,    name='admin_dashboard'),
    path('profile/',            views.customer_profile,   name='customer_profile'),
    path('seller-profile/',     views.seller_profile,     name='seller_profile'),
    # Face Recognition
    path('face/register/',      views.face_register,      name='face_register'),
    path('face/login/',         views.face_login,         name='face_login'),
]
