from django.contrib import admin
from django.urls import path
from accounts import views

urlpatterns = [
    path('login_page/',views.login_page,name='login_page'),
    path('logout_user/',views.logout_user,name='logout_user'),
    path('register_page/',views.register_page,name='register_page'),
    path('send_otp/<str:email>/', views.send_otp, name='send_otp'),
    path('<str:email>/verify_otp/', views.verify_otp, name='verify_otp'),
    path('verify-account/<token>/',views.verify_email_token,name='verify_email_token'),

    path('vendor_login/',views.vendor_login,name='vendor_login'),
    path('vendor_logout/',views.vendor_logout,name='vendor_logout'),
    path('vendor_register/',views.vendor_register,name='vendor_register'),
    path('ven_dashboard/',views.ven_dashboard,name='ven_dashboard'),
    path('add_hotel/',views.add_hotel,name='add_hotel'),
    path('<slug>/upload_images/',views.upload_images,name='upload_images'),
    path('delete_images/<id>',views.delete_images,name='delete_images'),
    path('edit_hotel/<slug>',views.edit_hotel,name='edit_hotel'),
]