from django.shortcuts import render, redirect, HttpResponse
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
import random

from hotel_app.views import *
from .models import hotel_owner, hotel_vendor, hotels, amenities, hotel_images, customers
from .utils import generateSlug, random_token, sendEmail, sendOtp, sendCustomer

def logout_user(request):
    logout(request)
    return redirect('login_page')

def login_page(request):
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')

        owner_qs = hotel_owner.objects.select_related('user').filter(user__email=email)
        if not owner_qs.exists():
            messages.error(request, "Account Not Found..!!")
            return redirect('/account/register_page')
        owner = owner_qs.first()
        if not owner.is_verified:
            messages.error(request, "Account Not verified..!!")
            return redirect('/account/login_page')

        user = authenticate(username=owner.user.username, password=password)
        if user:
            messages.success(request, "Welcome to noma hotel..!")
            login(request, user)
            return redirect('/')
        messages.error(request, 'Invalid credentials')
        return redirect('/account/login_page')
    return render(request, 'login_page.html')


def register_page(request):
    if request.method == "POST":
        firstname = request.POST.get('firstname')
        lastname = request.POST.get('lastname')
        phone_number = request.POST.get('phone_number')
        email = request.POST.get('email')
        password = request.POST.get('password')
        if len(password) < 8:
            messages.warning(request, "Your password is too short use 8 digit password..")
            return redirect('/account/register_page')

        if (
            User.objects.filter(Q(email=email) | Q(username=email)).exists()
            or hotel_owner.objects.filter(phone_number=phone_number).exists()
        ):
            messages.error(request, "Account already exists..!!")
            return redirect('/account/register_page')

        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=firstname,
            last_name=lastname,
            password=password,
        )
        owner_profile = hotel_owner.objects.create(
            user=user,
            phone_number=phone_number,
            email_token=random_token(),
        )
        sendEmail(email, owner_profile.email_token)
        messages.success(request, "An email is sent to your email..!")
        return redirect('/account/register_page')
    return render(request, 'register_page.html')


def verify_email_token(request,token):
    try:
        owner = hotel_owner.objects.get(email_token=token)
        owner.is_verified = True
        owner.save()
        messages.success(request, "E-mail verified! You can log in now.")
        return redirect('/account/login_page')
    except hotel_owner.DoesNotExist:
        try:
            vendor = hotel_vendor.objects.get(email_token=token)
            vendor.is_verified = True
            vendor.save()
            messages.success(request, "Vendor email verified! Please log in.")
            return redirect('/account/vendor_login')
        except hotel_vendor.DoesNotExist:
            return HttpResponse("Invalid token....!")


def send_otp(request,email):
    owner_qs = hotel_owner.objects.select_related('user').filter(user__email=email)

    if not owner_qs.exists():
        messages.error(request, "Account Not Found..!!")
        return redirect('/account/register_page')

    otp = random.randint(1000,9999)
    owner_qs.update(otp=otp)
    sendOtp(email, otp)
    messages.success(request, "An Otp is send to your mail")
    return redirect(f'/account/{email}/verify_otp')

def verify_otp(request,email):
    if request.method == "POST":
        otp = request.POST.get('otp')
        owner = hotel_owner.objects.select_related('user').get(user__email=email)

        if otp == owner.otp:
            messages.success(request, "Login successful")
            login(request, owner.user)
            return redirect('/')
        messages.warning(request, "Wrong otp")
        return redirect(f'/account/{email}/verify_otp')

    return render(request, 'send_otp.html')


# -----------------------for  Businessman------------------
def vendor_logout(request):
    logout(request)
    return redirect('/account/vendor_login')

def vendor_login(request):
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')

        vendor_qs = hotel_vendor.objects.select_related('user').filter(user__email=email)

        if not vendor_qs.exists():
            messages.error(request, "Account Not Found..!!")
            return redirect('/account/vendor_register')
        vendor = vendor_qs.first()
        if not vendor.is_verified:
            messages.error(request, "Account Not verified..!!")
            return redirect('/account/vendor_login')

        user = authenticate(username=vendor.user.username, password=password)

        if user:
            messages.success(request, "Welcome to Noma hotel..!")
            login(request, user)
            return redirect('ven_dashboard')
        messages.error(request, 'Invalid credentials')
        return redirect('/account/vendor_login')
    return render(request, 'vendor/vendor_login.html')


def vendor_register(request):
    if request.method == "POST":
        firstname = request.POST.get('firstname')
        lastname = request.POST.get('lastname')
        business_name = request.POST.get('business_name')
        phone_number = request.POST.get('phone_number')
        email = request.POST.get('email')
        profile_image = request.POST.get('profile_image')
        password = request.POST.get('password')
        if len(password) < 8:
            messages.warning(request, "Your password is too short use 8 digit password..")
            return redirect('/account/vendor_register')

        if (
            User.objects.filter(Q(email=email) | Q(username=email)).exists()
            or hotel_vendor.objects.filter(phone_number=phone_number).exists()
        ):
            messages.error(request, "Account already exists please login..!!")
            return redirect('/account/vendor_login')

        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=firstname,
            last_name=lastname,
            password=password,
        )

        vendor_profile = hotel_vendor.objects.create(
            user=user,
            business_name=business_name,
            phone_number=phone_number,
            profile_pic=profile_image,
            email_token=random_token(),
        )

        sendEmail(email, vendor_profile.email_token)
        messages.success(request, "An email is sent to your email..!")
        return redirect('/account/vendor_login')
    return render(request, 'vendor/vendor_register.html')

@login_required(login_url='vendor_login')
def ven_dashboard(request):
    try:
        vendor = hotel_vendor.objects.get(user=request.user)
    except hotel_vendor.DoesNotExist:
        messages.error(request, "You are not registered as a hotel vendor.")
        return redirect('vendor_register')

    vendor_hotels = hotels.objects.filter(hotel_owner=vendor)
    bookings = customers.objects.filter(hotel__in=vendor_hotels).select_related('hotel')

    context = {
        'hotels': vendor_hotels,
        'bookings': bookings,
    }
    return render(request, 'vendor/ven_dashboard.html', context)

@login_required(login_url='vendor_login')
def add_hotel(request):
    if request.method == "POST":
        hotel_name = request.POST.get('hotel_name')
        hotel_description = request.POST.get('hotel_description')
        hotel_amenities_ids = request.POST.getlist('hotel_amenities')
        hotel_price = request.POST.get('hotel_price')
        hotel_offer_price = request.POST.get('hotel_offer_price')
        hotel_location = request.POST.get('hotel_location')
        hotel_slug = generateSlug(hotel_name)

        try:
            Hotel_vendor = hotel_vendor.objects.get(user=request.user)
        except hotel_vendor.DoesNotExist:
            return HttpResponse("You are not registered as a hotel vendor.")


        hotel_obj = hotels.objects.create(
            hotel_name=hotel_name,
            hotel_description=hotel_description,
            hotel_price=hotel_price,
            hotel_offer_price=hotel_offer_price,
            hotel_location=hotel_location,
            hotel_slug=hotel_slug,
            hotel_owner=Hotel_vendor,
        )

        for amenity_id in hotel_amenities_ids:
            amenity = amenities.objects.get(id=amenity_id)
            hotel_obj.hotel_amenities.add(amenity)
        hotel_obj.save()

        messages.success(request, "Hotel added successfully..!!")
        return redirect('/account/add_hotel')

    Amenities = amenities.objects.all()
    return render(request, 'vendor/add_hotel.html', context={'Amenities': Amenities})

@login_required(login_url='vendor_login')
def upload_images(request,slug):
    hotel_obj = hotels.objects.get(hotel_slug = slug) 
    if request.method == "POST":
        image = request.FILES['image']
        print(image)
        hotel_images.objects.create(
            hotel = hotel_obj,
            image = image
        )
        messages.success(request,"Image Uploaded Succesfull")
        return HttpResponseRedirect(request.path_info)
    return render(request, 'vendor/upload_image.html',context={'images':hotel_obj.hotel_images.all()})

@login_required(login_url='vendor_login')
def delete_images(request,id):
    hotel_image = hotel_images.objects.get(id = id) 
    hotel_image.delete()
    messages.warning(request,"Image deleted successful")
    return redirect("ven_dashboard")

@login_required(login_url='vendor_login')
def edit_hotel(request,slug):
    hotel_obj = hotels.objects.get(hotel_slug=slug)
    if request.user.id != hotel_obj.hotel_owner.user_id:
        return HttpResponse('You are unauthorized person')
    if request.method == "POST":
        hotel_name = request.POST.get('hotel_name')
        hotel_description = request.POST.get('hotel_description')
        hotel_amenities_ids = request.POST.getlist('hotel_amenities')
        hotel_price = request.POST.get('hotel_price')
        hotel_offer_price = request.POST.get('hotel_offer_price')
        hotel_location = request.POST.get('hotel_location')

        hotel_obj.hotel_name = hotel_name
        hotel_obj.hotel_description = hotel_description
        hotel_obj.hotel_price = hotel_price
        hotel_obj.hotel_offer_price = hotel_offer_price
        hotel_obj.hotel_location = hotel_location
        if hotel_amenities_ids:
            hotel_obj.hotel_amenities.set(amenities.objects.filter(id__in=hotel_amenities_ids))
        hotel_obj.save()
        messages.success(request, "Hotel Updated Successfully")
        return HttpResponseRedirect(request.path_info)
    Amenities = amenities.objects.all()
    return render(request, 'vendor/edit_hotel.html', context={'hotel': hotel_obj, 'Amenities': Amenities})
