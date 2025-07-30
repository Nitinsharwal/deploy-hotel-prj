from django.contrib import admin
from django.urls import path
from hotel_app import views

urlpatterns = [
    path('',views.home,name='home'),
    path('hotel_details/<slug>',views.hotel_details,name='hotel_details'),
    path('user_logout',views.user_logout,name='user_logout'),
    path('about',views.about,name='about'),
    path('contact',views.contact,name='contact'),
]