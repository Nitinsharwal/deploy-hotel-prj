from django.urls import path

from hotel_app import views

urlpatterns = [
    path("", views.home, name="home"),
    path("hotel_details/<slug>", views.hotel_details, name="hotel_details"),
    path("user_logout", views.user_logout, name="user_logout"),
    path("about", views.about, name="about"),
    path("contact", views.contact, name="contact"),
    path("pricing/", views.pricing, name="pricing"),
    path("my_bookings/", views.my_bookings, name="my_bookings"),
    path("bookings/<reference>/cancel/", views.cancel_booking, name="cancel_booking"),
    path("bookings/<reference>/review/", views.submit_review, name="submit_review"),
    # Payments (DEMO MODE — Razorpay verify/webhook routes disabled, see views.py)
    path("bookings/<reference>/pay/", views.payment_checkout, name="payment_checkout"),
    path("bookings/<reference>/pay/confirm/", views.dummy_pay, name="dummy_pay"),
    path("bookings/<reference>/pay/success/", views.payment_success, name="payment_success"),
    path("bookings/<reference>/pay/cancel/", views.payment_cancel, name="payment_cancel"),
    path("bookings/<reference>/slip/", views.booking_slip, name="booking_slip"),
]
