from django.contrib import admin

from .models import (
    Booking,
    ContactMessage,
    Payment,
    Review,
    Room,
    VendorCharge,
    amenities,
    hotel_images,
    hotel_manager,
    hotel_owner,
    hotel_vendor,
    hotels,
)

admin.site.site_header = "Hotel Noma"
admin.site.site_title = "Noma Admin Panel"
admin.site.index_title = "Welcome to Noma Admin Panel"


@admin.register(hotel_owner)
class HotelOwnerAdmin(admin.ModelAdmin):
    list_display = (
        "get_username",
        "get_first_name",
        "get_last_name",
        "phone_number",
        "is_verified",
    )
    search_fields = ("user__username", "user__email", "phone_number")

    def get_username(self, obj):
        return obj.user.username

    def get_first_name(self, obj):
        return obj.user.first_name

    def get_last_name(self, obj):
        return obj.user.last_name

    get_username.short_description = "Username"
    get_first_name.short_description = "First Name"
    get_last_name.short_description = "Last Name"


@admin.register(hotel_vendor)
class HotelVendorAdmin(admin.ModelAdmin):
    list_display = (
        "business_name",
        "get_username",
        "phone_number",
        "is_verified",
    )
    search_fields = ("business_name", "user__username", "phone_number")

    def get_username(self, obj):
        return obj.user.username

    get_username.short_description = "Username"


@admin.register(hotels)
class HotelsAdmin(admin.ModelAdmin):
    list_display = (
        "hotel_name",
        "hotel_owner",
        "hotel_price",
        "hotel_offer_price",
        "hotel_location",
        "is_active",
    )
    prepopulated_fields = {"hotel_slug": ("hotel_name",)}
    search_fields = ("hotel_name", "hotel_location")
    list_filter = ("is_active",)


@admin.register(amenities)
class AmenitiesAdmin(admin.ModelAdmin):
    list_display = ("amenities_name",)
    search_fields = ("amenities_name",)


# `customers` legacy table dropped in migration 0009 — data was already
# copied into Booking via the data migration 0004.


@admin.register(hotel_images)
class HotelImagesAdmin(admin.ModelAdmin):
    list_display = ("hotel", "image")


@admin.register(hotel_manager)
class HotelManagerAdmin(admin.ModelAdmin):
    list_display = ("hotel", "manager_name", "manager_contact")


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = (
        "hotel",
        "name",
        "room_type",
        "capacity",
        "total_count",
        "base_price",
        "is_active",
    )
    list_filter = ("room_type", "is_active")
    search_fields = ("hotel__hotel_name", "name")
    readonly_fields = ("created_at", "updated_at")


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = (
        "amount",
        "method",
        "status",
        "transaction_id",
        "gateway_response",
        "created_at",
        "updated_at",
    )
    can_delete = False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "room",
        "guest_email",
        "start_date",
        "end_date",
        "status",
        "total_amount",
        "created_at",
    )
    list_filter = ("status", "start_date")
    search_fields = (
        "reference",
        "guest_email",
        "guest_first_name",
        "guest_last_name",
        "room__hotel__hotel_name",
    )
    readonly_fields = ("reference", "total_amount", "created_at", "updated_at", "cancelled_at")
    inlines = [PaymentInline]
    actions = ["mark_completed"]

    @admin.action(description="Mark selected bookings as completed")
    def mark_completed(self, request, queryset):
        queryset.update(status=Booking.Status.COMPLETED)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("hotel", "score", "user", "title", "created_at")
    list_filter = ("score",)
    search_fields = ("hotel__hotel_name", "title", "body", "user__email")
    readonly_fields = ("booking", "hotel", "user", "created_at", "updated_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("booking", "amount", "method", "status", "transaction_id", "created_at")
    list_filter = ("status", "method")
    search_fields = ("booking__reference", "transaction_id")
    readonly_fields = ("created_at", "updated_at")


@admin.register(VendorCharge)
class VendorChargeAdmin(admin.ModelAdmin):
    list_display = ("vendor", "kind", "amount", "status", "hotel", "created_at")
    list_filter = ("status", "kind")
    search_fields = ("vendor__business_name", "description", "notes")
    readonly_fields = ("created_at", "paid_at")
    actions = ["mark_paid_bulk", "mark_waived_bulk"]

    @admin.action(description="Mark selected as PAID")
    def mark_paid_bulk(self, request, queryset):
        for c in queryset:
            c.mark_paid()

    @admin.action(description="Mark selected as WAIVED")
    def mark_waived_bulk(self, request, queryset):
        for c in queryset:
            c.mark_waived()


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "first_name", "last_name", "email", "subject", "status")
    list_filter = ("status", "created_at")
    search_fields = ("first_name", "last_name", "email", "subject", "message")
    readonly_fields = (
        "first_name",
        "last_name",
        "email",
        "subject",
        "message",
        "user",
        "ip_address",
        "user_agent",
        "created_at",
    )
    fieldsets = (
        ("Message", {"fields": ("first_name", "last_name", "email", "subject", "message")}),
        ("Triage", {"fields": ("status", "internal_notes", "resolved_at")}),
        (
            "Metadata",
            {
                "fields": ("user", "ip_address", "user_agent", "created_at"),
                "classes": ("collapse",),
            },
        ),
    )
    actions = ["mark_resolved", "mark_spam"]
    date_hierarchy = "created_at"

    @admin.action(description="Mark selected as RESOLVED")
    def mark_resolved(self, request, queryset):
        from django.utils import timezone

        queryset.update(status=ContactMessage.Status.RESOLVED, resolved_at=timezone.now())

    @admin.action(description="Mark selected as SPAM")
    def mark_spam(self, request, queryset):
        queryset.update(status=ContactMessage.Status.SPAM)
