from django.contrib import admin
from .models import *


admin.site.site_header = "Hotel Noma"
admin.site.site_title = "Noma admin pannel"
admin.site.index_title = "Welcome to noma admin pannel"
class hotel_ownerAdmin(admin.ModelAdmin):
    list_display = [
        'firstname',
        'lastname',
        'profile_pic',
        'phone_number',
        'email_token',
        'otp',
        'is_verified',
    ]
admin.site.register(hotel_owner,hotel_ownerAdmin)

class hotel_vendorAdmin(admin.ModelAdmin):
    list_display = [
        'firstname',
        'lastname',
        'profile_pic',
        'phone_number',
        'email_token',
        'business_name',
        'is_verified',
    ]
    search_fields = ['hotel_vendor']
admin.site.register(hotel_vendor,hotel_vendorAdmin)

class hotelsAdmin(admin.ModelAdmin):
    list_display = [
        'hotel_name',
        'hotel_description',
        'hotel_owner',
        'hotel_price',
        'hotel_offer_price',
        'hotel_location',
    ]
    search_fields = ['hotel_name']
admin.site.register(hotels,hotelsAdmin)

class customersAdmin(admin.ModelAdmin):
    list_display = [
        'hotel',
        'customer_fname',
        'customer_lname',
        'customer_email',
        'start_date',
        'end_date',
        'payment',
    ]
    search_fields = ['hotel__hotel_name', 'customer_fname', 'customer_email'] 

admin.site.register(customers,customersAdmin)

admin.site.register(amenities)