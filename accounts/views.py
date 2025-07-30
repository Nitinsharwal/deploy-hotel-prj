from django.shortcuts import render,redirect,HttpResponse
from .models import hotel_owner, hotel_vendor, hotels, amenities, hotel_images,customers
from django.db.models import Q
from django.contrib import messages
from .utils import *
from django.contrib.auth import  authenticate,login,logout
from django.contrib.auth.decorators import login_required
from .utils import generateSlug
from django.http import  HttpResponseRedirect
import random
from hotel_app.views import *

def logout_user(request):
    logout(request)
    return redirect('login_page')

def login_page(request):
    if request.method=="POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        Hotel_Owner = hotel_owner.objects.filter(email =  email)

        if not Hotel_Owner.exists():
            messages.error(request,"Account Not Found..!!")
            return redirect('/account/register_page')
        if not Hotel_Owner[0].is_verified:
            messages.error(request,"Account Not verified..!!")
            return redirect('/account/login_page')

        Hotel_Owner = authenticate(username = Hotel_Owner[0].username,password=password)
        
        if Hotel_Owner:
            messages.success(request,"Welcome to noma hotel..!")
            login(request, Hotel_Owner)
            return redirect('/')
        messages.error(request,'Invaild credentials')
        return redirect('/account/login_page')
    return render(request,'login_page.html')


def register_page(request):
    if request.method=="POST":
        firstname = request.POST.get('firstname')
        lastname = request.POST.get('lastname')
        phone_number = request.POST.get('phone_number')
        email = request.POST.get('email')
        password = request.POST.get('password')
        if len(password) < 8:
            messages.warning(request, "Your password is too short use 8 digit password..")
            return redirect('/account/register_page')

        Hotel_Owner = hotel_owner.objects.filter(
            Q(phone_number =  phone_number ) | Q(email =  email )
        )

        if Hotel_Owner.exists():
            messages.error(request,"Account already exists..!!")
            return redirect('/account/register_page')

        Hotel_Owner = hotel_owner.objects.create(
            username = email,
            firstname = firstname,
            lastname = lastname,
            phone_number = phone_number,
            email = email,
            password  = password,
            email_token= random_token()
        )
        Hotel_Owner.set_password(password)
        Hotel_Owner.save()
        sendEmail(email,Hotel_Owner.email_token)
        messages.success(request,"An email is  sent to your email..!")
        return redirect('/account/register_page')
    return render(request,'register_page.html')


def verify_email_token(request,token):
    try:
        Hotel_Owner = hotel_owner.objects.get(email_token = token)
        Hotel_Owner.is_verified = True
        Hotel_Owner.save()
        messages.success(request,"E-mail Verified!")
        return redirect('/account/login_page')
    except Exception as e:
        return HttpResponse("Invaild Token....!")


def send_otp(request,email):
    Hotel_Owner = hotel_owner.objects.filter(email =  email)

    if not Hotel_Owner.exists():
        messages.error(request,"Account Not Found..!!")
        return redirect('/account/register_page')

    otp = random.randint(1000,9999)
    Hotel_Owner.update(otp = otp)
    sendOtp(email,otp)
    messages.success(request,"An Otp is send to your mail")
    return redirect(f'/account/{email}/verify_otp')

def verify_otp(request,email):
    if request.method == "POST":
        otp = request.POST.get('otp')
        Hotel_Owner = hotel_owner.objects.get(email = email)

        if otp == Hotel_Owner.otp:
            messages.success(request,"Login sucessful")
            login(request, Hotel_Owner)
            return redirect('/')
        messages.warning(request, "Wrong otp")
        return redirect(f'/account/{email}/verify_otp')

    return render(request, 'send_otp.html')


# -----------------------for  Businessman------------------
def vendor_logout(request):
    logout(request)
    return redirect('/account/vendor_login')

def vendor_login(request):
    if request.method=="POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        Hotel_Vendor = hotel_vendor.objects.filter(email =  email)

        if not Hotel_Vendor.exists():
            messages.error(request,"Account Not Found..!!")
            return redirect('/account/vendor_register')
        if not Hotel_Vendor[0].is_verified:
            messages.error(request,"Account Not verified..!!")
            return redirect('/account/vendor_login')

        Hotel_Vendor = authenticate(username = Hotel_Vendor[0].username,password=password)
        
        if Hotel_Vendor:
            messages.success(request,"Welcome to Noma hotel..!")
            login(request, Hotel_Vendor)
            return redirect('ven_dashboard')
        messages.error(request,'Invaild credentials')
        return redirect('/account/vendor_login')
    return render(request,'vendor/vendor_login.html')


def vendor_register(request):
    if request.method=="POST":
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

        Hotel_Vendor = hotel_vendor.objects.filter(
            Q(phone_number =  phone_number ) | Q(email =  email )
        )

        if Hotel_Vendor.exists():
            messages.error(request,"Account already exists please login..!!")
            return redirect('/account/vendor_login')

        Hotel_Vendor = hotel_vendor.objects.create(
            username = email,
            firstname = firstname,
            lastname = lastname,
            business_name=business_name,
            phone_number = phone_number,
            email = email,
            profile_pic = profile_image,
            password  = password,
            email_token= random_token()
        )
        Hotel_Vendor.set_password(password)
        Hotel_Vendor.save()
        sendEmail(email,Hotel_Vendor.email_token)
        messages.success(request,"An email is  sent to your email..!")
        return redirect('/account/vendor_login')
    return render(request,'vendor/vendor_register.html')

@login_required(login_url='vendor_login')
def ven_dashboard(request):
    vendor_hotels = hotels.objects.filter(hotel_owner=request.user)
    bookings = customers.objects.filter(hotel__in=vendor_hotels).select_related('hotel')

    context = {
        'hotels': vendor_hotels,
        'bookings': bookings,
    }
    return render(request, 'vendor/ven_dashboard.html', context)

@login_required(login_url='vendor_login')
def add_hotel(request):
    if request.method == "POST":
        hotel_name  = request.POST.get('hotel_name')
        hotel_description = request.POST.get('hotel_description')
        hotel_aminities = request.POST.getlist('hotel_aminities')
        hotel_price = request.POST.get('hotel_price')
        hotel_offer_price = request.POST.get('hotel_offer_price')
        hotel_location = request.POST.get('hotel_location')
        hotel_slug = generateSlug(hotel_name)

        try:
            Hotel_vendor = hotel_vendor.objects.get(id=request.user.id)
        except hotel_vendor.DoesNotExist:
            return HttpResponse("You are not registered as a hotel vendor.")


        hotel_obj  = hotels.objects.create(
            hotel_name = hotel_name,
            hotel_description = hotel_description,
            hotel_price = hotel_price,
            hotel_offer_price = hotel_offer_price,
            hotel_location = hotel_location,
            hotel_slug = hotel_slug,
            hotel_owner = Hotel_vendor,
        )

        for amenitie in hotel_aminities:
            amenitie = amenities.objects.get(id = amenitie)
            hotel_obj.hotel_aminities.add(amenitie)
            hotel_obj.save()

        messages.success(request,"Hotel added succesfull..!!")
        return redirect('/account/add_hotel')

    Amenities = amenities.objects.all()
    return render(request, 'vendor/add_hotel.html', context = {'Amenities' : Amenities })

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
    hotel_obj = hotels.objects.get(hotel_slug = slug)
    if request.user.id != hotel_obj.hotel_owner.id:
        return HttpResponse('You are unauthorized person')
    if request.method == "POST":
        hotel_name  = request.POST.get('hotel_name')
        hotel_description = request.POST.get('hotel_description')
        hotel_aminities = request.POST.getlist('hotel_aminities')
        hotel_price = request.POST.get('hotel_price')
        hotel_offer_price = request.POST.get('hotel_offer_price')
        hotel_location = request.POST.get('hotel_location')

        hotel_obj.hotel_name = hotel_name
        hotel_obj.hotel_description = hotel_description
        hotel_obj.hotel_price = hotel_price
        hotel_obj.hotel_offer_price = hotel_offer_price
        hotel_obj.hotel_location = hotel_location
        hotel_obj.save()
        messages.success(request,"Hotel Updated Succesfull")
        return HttpResponseRedirect(request.path_info)
    Amenities = amenities.objects.all()
    return render(request, 'vendor/edit_hotel.html',context={'hotel':hotel_obj, 'Amenities':Amenities})