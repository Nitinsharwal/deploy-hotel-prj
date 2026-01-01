from django.contrib import admin
from .models import (
    hotel_owner,
    hotel_vendor,
    hotels,
    amenities,
    customers,
    hotel_images,
    hotel_manager
)

admin.site.site_header = "Hotel Noma"
admin.site.site_title = "Noma Admin Panel"
admin.site.index_title = "Welcome to Noma Admin Panel"

@admin.register(hotel_owner)
class HotelOwnerAdmin(admin.ModelAdmin):
    list_display = (
        'get_username',
        'get_first_name',
        'get_last_name',
        'phone_number',
        'is_verified',
    )
    search_fields = ('user__username', 'user__email', 'phone_number')

    def get_username(self, obj):
        return obj.user.username

    def get_first_name(self, obj):
        return obj.user.first_name

    def get_last_name(self, obj):
        return obj.user.last_name

    get_username.short_description = 'Username'
    get_first_name.short_description = 'First Name'
    get_last_name.short_description = 'Last Name'

@admin.register(hotel_vendor)
class HotelVendorAdmin(admin.ModelAdmin):
    list_display = (
        'business_name',
        'get_username',
        'phone_number',
        'is_verified',
    )
    search_fields = ('business_name', 'user__username', 'phone_number')

    def get_username(self, obj):
        return obj.user.username

    get_username.short_description = 'Username'


@admin.register(hotels)
class HotelsAdmin(admin.ModelAdmin):
    list_display = (
        'hotel_name',
        'hotel_owner',
        'hotel_price',
        'hotel_offer_price',
        'hotel_location',
        'is_active',
    )
    prepopulated_fields = {"hotel_slug": ("hotel_name",)}
    search_fields = ('hotel_name', 'hotel_location')
    list_filter = ('is_active',)


@admin.register(amenities)
class AmenitiesAdmin(admin.ModelAdmin):
    list_display = ('amenities_name',)
    search_fields = ('amenities_name',)


@admin.register(customers)
class CustomersAdmin(admin.ModelAdmin):
    list_display = (
        'hotel',
        'customer_fname',
        'customer_lname',
        'customer_email',
        'start_date',
        'end_date',
        'payment',
    )
    search_fields = (
        'hotel__hotel_name',
        'customer_fname',
        'customer_lname',
        'customer_email',
    )


@admin.register(hotel_images)
class HotelImagesAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'image')


@admin.register(hotel_manager)
class HotelManagerAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'manager_name', 'manager_contact')
