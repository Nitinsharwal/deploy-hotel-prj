import uuid
from django.core.mail import send_mail
from django.conf import settings
from django.utils.text import slugify
from .models import hotels,customers


def random_token():
    return str(uuid.uuid4())

def sendEmail(email, token):
    subject = "Verify your email address"
    message = f"""Hi, please verify your email before login using the link below:
http://127.0.0.1:8000/account/verify-account/{token}
"""
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [email],
        fail_silently=False,
    )
    return str(uuid.uuid4())

def sendOtp(email, otp):
    subject = "OTP for account login"
    message = f"""Hii, use this otp to login :

        {otp}
"""
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [email],
        fail_silently=False,
    )
    return str(uuid.uuid4())

def generateSlug(hotel_name):
    slug = slugify(hotel_name) + str(uuid.uuid4()).split('-')[0]
    if hotels.objects.filter(hotel_slug = slug).exists():
        return generateSlug(hotel_name)
    return slug

def sendCustomer(customer_email,hotel,payment):
    subject = "Noma Hotel booked"
    message = f"""Thanks for booked hotel here your complete receipt below:\n
                Your Hotel Name : {hotel}\n
                Payment : {payment}\n
"""
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [customer_email],
        fail_silently=False,
    )
    return str(uuid.uuid4())