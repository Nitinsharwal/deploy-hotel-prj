"""Data migration: give every existing hotel a default Room and copy each
legacy `customers` row into a Booking with status=CONFIRMED.

We keep the legacy `customers` table intact (no row deletes) so we have a
fallback if anything goes wrong. A future migration can drop it once verified.
"""
import secrets
from decimal import Decimal

from django.db import migrations


def _make_reference():
    # 10-char URL-safe ref like "NM-XQK9F2". Collisions on 10 chars of base32 are negligible at this scale.
    return "NM-" + secrets.token_hex(4).upper()


def forwards(apps, schema_editor):
    Hotel = apps.get_model("accounts", "hotels")
    Room = apps.get_model("accounts", "Room")
    Booking = apps.get_model("accounts", "Booking")
    Customer = apps.get_model("accounts", "customers")

    # 1. One default room per hotel — using offer price as the base price.
    default_rooms = {}
    for hotel in Hotel.objects.all():
        room, _ = Room.objects.get_or_create(
            hotel=hotel,
            name="Standard Room",
            defaults={
                "room_type": "standard",
                "capacity": 2,
                "total_count": 10,  # safe default; vendors edit later
                "base_price": Decimal(str(hotel.hotel_offer_price or hotel.hotel_price or 0)),
                "is_active": True,
            },
        )
        default_rooms[hotel.pk] = room

    # 2. Copy each legacy customer row into a Booking.
    for legacy in Customer.objects.all().iterator():
        room = default_rooms.get(legacy.hotel_id)
        if room is None:
            continue
        # Skip if we've already migrated this row (idempotent on re-run).
        if Booking.objects.filter(
            room=room,
            guest_email=legacy.customer_email,
            start_date=legacy.start_date,
            end_date=legacy.end_date,
        ).exists():
            continue
        Booking.objects.create(
            reference=_make_reference(),
            room=room,
            user=None,
            guest_first_name=legacy.customer_fname,
            guest_last_name=legacy.customer_lname,
            guest_email=legacy.customer_email,
            guest_phone="",
            start_date=legacy.start_date,
            end_date=legacy.end_date,
            num_guests=1,
            total_amount=Decimal(str(legacy.payment or 0)),
            status="confirmed",
        )


def backwards(apps, schema_editor):
    # We never delete migrated bookings on reverse — they may have had
    # follow-up edits. The forward step is idempotent, so just no-op here.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_booking_room_payment_booking_room_booking_user_and_more"),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
