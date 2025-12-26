from django.shortcuts import render,redirect
from datetime import datetime
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.decorators import login_required
from accounts.models import hotels,customers, hotel_owner, hotel_vendor
from django.http import  HttpResponseRedirect
from django.contrib import messages
from datetime import datetime
from decimal import Decimal, InvalidOperation
from accounts.utils import *

# @login_required(login_url='/account/login_page/')
def home(request):
    Hotel = hotels.objects.all()
    search_query = request.GET.get('search')
    if search_query:
        Hotel = Hotel.filter(hotel_name__icontains=search_query)
    sort_by = request.GET.get('sort')
    if sort_by == 'low':
        Hotel = Hotel.order_by('hotel_price')
    elif sort_by == 'high':
        Hotel = Hotel.order_by('-hotel_price')

    return render(request, 'index.html',context={'Hotel':Hotel})


@login_required(login_url='/account/login_page/')
def hotel_details(request,slug):
    hotel_obj = hotels.objects.get(hotel_slug = slug)
    if request.method == 'POST':
        customer_fname = request.POST.get('customer_fname')
        customer_lname  = request.POST.get('customer_lname')
        customer_email = request.POST.get('customer_email')
        try:
            payment = Decimal(request.POST.get('payment'))
        except (InvalidOperation, TypeError):
            messages.error(request, 'Invalid payment amount.')
            return HttpResponseRedirect(request.path_info)
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        start_date = datetime.strptime(start_date,'%Y-%m-%d')
        end_date = datetime.strptime(end_date,'%Y-%m-%d')
        days_count = (end_date -  start_date).days
        
        Customers_email = customers.objects.filter(customer_email =  customer_email )
        if Customers_email.exists():
            messages.error(request,"You already booked hotel..!!")
            return redirect('hotel_details', slug=slug)
        if payment < hotel_obj.hotel_offer_price:
            messages.warning(request, 'No bargaining please enter required payment..!')
            return HttpResponseRedirect(request.path_info)
        if days_count<=0:
            messages.warning(request,"Invaild date")
            return HttpResponseRedirect(request.path_info)
        Customers = customers.objects.create(
            customer_fname = customer_fname,
            customer_lname = customer_lname,
            customer_email = customer_email,
            hotel = hotel_obj,
            start_date = start_date,
            end_date = end_date,
            payment = hotel_obj.hotel_offer_price * days_count
        )
        messages.success(request,"Hotel Booked..!")
        sendCustomer(Customers.customer_email,Customers.hotel,Customers.payment)
        return HttpResponseRedirect(request.path_info)
    return render(request,'hotel_details.html',context={'hotel': hotel_obj})

def user_logout(request):
    logout(request)
    return redirect('/account/vendor_login/')

def about(request):
    return render(request,'about.html')


def contact(request):
    return render(request,'contact.html')

