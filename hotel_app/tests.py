from datetime import date, timedelta
from decimal import Decimal
import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from accounts.models import Booking, Payment, Review, Room, hotel_vendor, hotels
from hotel_app.forms import BookingForm


@pytest.fixture
def vendor(db):
    user = User.objects.create_user(username="v@x.com", email="v@x.com", password="pw12345678")
    return hotel_vendor.objects.create(
        user=user, business_name="X Stays", phone_number="+1000000001", is_verified=True
    )


@pytest.fixture
def hotel(vendor):
    return hotels.objects.create(
        hotel_name="Test Hotel",
        hotel_description="desc",
        hotel_slug="test-hotel",
        hotel_owner=vendor,
        hotel_price=2000.0,
        hotel_offer_price=1500.0,
        hotel_location="Goa",
    )


@pytest.fixture
def room(hotel):
    return Room.objects.create(
        hotel=hotel,
        name="Deluxe",
        room_type=Room.RoomType.DELUXE,
        capacity=2,
        total_count=2,
        base_price=Decimal("1500.00"),
    )


def _form_data(room, **overrides):
    data = {
        "room": room.pk,
        "guest_first_name": "A",
        "guest_last_name": "B",
        "guest_email": "a@b.com",
        "guest_phone": "+10",
        "num_guests": 1,
        "start_date": (date.today() + timedelta(days=1)).isoformat(),
        "end_date": (date.today() + timedelta(days=3)).isoformat(),
        "payment_method": "card",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_home_lists_active_hotels(client, hotel):
    resp = client.get(reverse("home"))
    assert resp.status_code == 200
    assert b"Test Hotel" in resp.content


@pytest.mark.django_db
def test_home_filter_by_max_price_excludes_pricier(client, hotel, vendor):
    hotels.objects.create(
        hotel_name="Pricey Palace",
        hotel_description="x",
        hotel_slug="pricey",
        hotel_owner=vendor,
        hotel_price=9999.0,
        hotel_offer_price=8000.0,
        hotel_location="Goa",
    )
    resp = client.get(reverse("home"), {"max_price": "2000"})
    assert b"Test Hotel" in resp.content
    assert b"Pricey Palace" not in resp.content


@pytest.mark.django_db
def test_home_date_filter_hides_fully_booked(client, hotel, room):
    # total_count=2; book both for the requested window
    for i in range(2):
        Booking.objects.create(
            reference=f"NM-BLK{i:05d}",
            room=room,
            guest_first_name="X",
            guest_last_name="Y",
            guest_email=f"x{i}@y.com",
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=12),
            num_guests=1,
            total_amount=Decimal("3000"),
            status=Booking.Status.CONFIRMED,
        )
    resp = client.get(
        reverse("home"),
        {
            "start_date": (date.today() + timedelta(days=10)).isoformat(),
            "end_date": (date.today() + timedelta(days=12)).isoformat(),
        },
    )
    assert b"Test Hotel" not in resp.content


@pytest.mark.django_db
def test_hotel_details_requires_login(client, hotel):
    resp = client.get(reverse("hotel_details", args=[hotel.hotel_slug]))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_booking_form_rejects_past_dates(hotel, room):
    form = BookingForm(
        data=_form_data(room, start_date=(date.today() - timedelta(days=1)).isoformat()),
        hotel=hotel,
    )
    assert not form.is_valid()


@pytest.mark.django_db
def test_booking_form_rejects_over_capacity(hotel, room):
    form = BookingForm(data=_form_data(room, num_guests=10), hotel=hotel)
    assert not form.is_valid()


@pytest.mark.django_db
def test_booking_form_happy_path_creates_pending_booking(hotel, room):
    form = BookingForm(data=_form_data(room), hotel=hotel)
    assert form.is_valid(), form.errors
    booking = form.save()
    assert booking.status == Booking.Status.PENDING
    assert booking.reference.startswith("NM-")
    assert booking.total_amount == Decimal("3000.00")  # 2 nights × 1500


@pytest.mark.django_db
def test_room_availability_fills_up(hotel, room):
    # total_count=2, so the third overlapping booking must be rejected.
    for i in range(2):
        Booking.objects.create(
            reference=f"NM-FILL{i:04d}",
            room=room,
            guest_first_name="X",
            guest_last_name="Y",
            guest_email=f"x{i}@y.com",
            start_date=date.today() + timedelta(days=2),
            end_date=date.today() + timedelta(days=4),
            num_guests=1,
            total_amount=Decimal("3000"),
            status=Booking.Status.CONFIRMED,
        )
    form = BookingForm(
        data=_form_data(
            room,
            start_date=(date.today() + timedelta(days=2)).isoformat(),
            end_date=(date.today() + timedelta(days=4)).isoformat(),
        ),
        hotel=hotel,
    )
    assert not form.is_valid()


@pytest.mark.django_db
def test_cancelled_booking_frees_inventory(hotel, room):
    Booking.objects.create(
        reference="NM-CANCEL01",
        room=room,
        guest_first_name="X",
        guest_last_name="Y",
        guest_email="cancel@y.com",
        start_date=date.today() + timedelta(days=2),
        end_date=date.today() + timedelta(days=4),
        num_guests=1,
        total_amount=Decimal("3000"),
        status=Booking.Status.CANCELLED,
    )
    assert (
        room.booked_count(date.today() + timedelta(days=2), date.today() + timedelta(days=4)) == 0
    )


@pytest.mark.django_db
def test_booking_cancel_method_blocks_past_or_completed(hotel, room):
    booking = Booking.objects.create(
        reference="NM-PAST00001",
        room=room,
        guest_first_name="X",
        guest_last_name="Y",
        guest_email="p@y.com",
        start_date=date.today() - timedelta(days=2),
        end_date=date.today() - timedelta(days=1),
        num_guests=1,
        total_amount=Decimal("1500"),
        status=Booking.Status.CONFIRMED,
    )
    assert not booking.is_cancellable
    with pytest.raises(ValueError):
        booking.cancel()


@pytest.mark.django_db
def test_cancel_booking_view_requires_owner(client, hotel, room):
    owner = User.objects.create_user(
        username="owner@x.com", email="owner@x.com", password="pw12345678"
    )
    other = User.objects.create_user(
        username="other@x.com", email="other@x.com", password="pw12345678"
    )
    booking = Booking.objects.create(
        reference="NM-OWN0001A",
        room=room,
        user=owner,
        guest_first_name="A",
        guest_last_name="B",
        guest_email="owner@x.com",
        start_date=date.today() + timedelta(days=5),
        end_date=date.today() + timedelta(days=7),
        num_guests=1,
        total_amount=Decimal("3000"),
        status=Booking.Status.CONFIRMED,
    )
    client.force_login(other)
    resp = client.post(reverse("cancel_booking", args=[booking.reference]))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_review_only_allowed_for_completed_booking(client, hotel, room):
    user = User.objects.create_user(username="rev@x.com", email="rev@x.com", password="pw12345678")
    booking = Booking.objects.create(
        reference="NM-REV00001",
        room=room,
        user=user,
        guest_first_name="A",
        guest_last_name="B",
        guest_email="rev@x.com",
        start_date=date.today() + timedelta(days=5),
        end_date=date.today() + timedelta(days=7),
        num_guests=1,
        total_amount=Decimal("3000"),
        status=Booking.Status.CONFIRMED,  # not completed yet
    )
    client.force_login(user)
    resp = client.post(
        reverse("submit_review", args=[booking.reference]),
        data={"score": 5, "title": "Great", "body": "Loved it"},
    )
    # Redirects to my_bookings with an error, no Review created.
    assert resp.status_code == 302
    assert not Review.objects.filter(booking=booking).exists()


@pytest.mark.django_db
def test_review_updates_hotel_rating_cache(hotel, room):
    user = User.objects.create_user(username="rc@x.com", email="rc@x.com", password="pw12345678")
    booking = Booking.objects.create(
        reference="NM-RATE00001",
        room=room,
        user=user,
        guest_first_name="A",
        guest_last_name="B",
        guest_email="rc@x.com",
        start_date=date.today() - timedelta(days=5),
        end_date=date.today() - timedelta(days=2),
        num_guests=1,
        total_amount=Decimal("3000"),
        status=Booking.Status.COMPLETED,
    )
    Review.objects.create(booking=booking, hotel=hotel, user=user, score=4, body="ok")
    hotel.refresh_from_db()
    assert hotel.rating_count == 1
    assert float(hotel.rating_avg) == 4.0


@pytest.mark.django_db
def test_payment_attached_to_booking_after_form_submit(client, hotel, room):
    customer = User.objects.create_user(username="c@x.com", email="c@x.com", password="pw12345678")
    client.force_login(customer)
    resp = client.post(
        reverse("hotel_details", args=[hotel.hotel_slug]),
        data=_form_data(room),
    )
    assert resp.status_code == 302
    booking = Booking.objects.get(guest_email="a@b.com")
    assert booking.payments.count() == 1
    assert booking.payments.first().status == Payment.Status.INITIATED


@pytest.mark.django_db
def test_razorpay_webhook_confirms_booking_on_payment_captured(hotel, room):
    from hotel_app import payments as gateway

    user = User.objects.create_user(username="pay@x.com", email="pay@x.com", password="pw12345678")
    booking = Booking.objects.create(
        reference="NM-PAY00001",
        room=room,
        user=user,
        guest_first_name="A",
        guest_last_name="B",
        guest_email="pay@x.com",
        start_date=date.today() + timedelta(days=10),
        end_date=date.today() + timedelta(days=12),
        num_guests=1,
        total_amount=Decimal("3000"),
        status=Booking.Status.PENDING,
    )
    payment = Payment.objects.create(
        booking=booking,
        amount=booking.total_amount,
        method=Payment.Method.CARD,
        status=Payment.Status.INITIATED,
        transaction_id="order_test_abc123",
    )

    event = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_xyz",
                    "order_id": "order_test_abc123",
                    "method": "upi",
                    "amount": 300000,
                    "currency": "INR",
                }
            }
        },
    }
    result = gateway.handle_webhook_event(event)
    assert result == "ok:confirmed"

    booking.refresh_from_db()
    payment.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED
    assert payment.status == Payment.Status.SUCCESS
    assert payment.method == Payment.Method.UPI
    assert payment.transaction_id == "pay_test_xyz"


@pytest.mark.django_db
def test_complete_past_bookings_command_advances_status(hotel, room):
    from django.core.management import call_command

    past = Booking.objects.create(
        reference="NM-AUTO00001",
        room=room,
        guest_first_name="A",
        guest_last_name="B",
        guest_email="auto@x.com",
        start_date=date.today() - timedelta(days=5),
        end_date=date.today() - timedelta(days=2),
        num_guests=1,
        total_amount=Decimal("3000"),
        status=Booking.Status.CONFIRMED,
    )
    future = Booking.objects.create(
        reference="NM-AUTO00002",
        room=room,
        guest_first_name="C",
        guest_last_name="D",
        guest_email="future@x.com",
        start_date=date.today() + timedelta(days=2),
        end_date=date.today() + timedelta(days=4),
        num_guests=1,
        total_amount=Decimal("3000"),
        status=Booking.Status.CONFIRMED,
    )
    call_command("complete_past_bookings")
    past.refresh_from_db()
    future.refresh_from_db()
    assert past.status == Booking.Status.COMPLETED
    assert future.status == Booking.Status.CONFIRMED  # untouched


@pytest.mark.django_db
def test_cancel_booking_triggers_refund(client, hotel, room, monkeypatch, settings):
    """View should call refund_booking and surface the result without crashing."""
    from hotel_app import payments as gateway

    settings.RAZORPAY_KEY_SECRET = "rzp_test_dummy"
    calls = {}

    def fake_refund(booking, reason=""):
        calls["called_with"] = booking.reference
        return ("refunded", "rfnd_test_123")

    monkeypatch.setattr(gateway, "refund_booking", fake_refund)

    user = User.objects.create_user(username="rb@x.com", email="rb@x.com", password="pw12345678")
    booking = Booking.objects.create(
        reference="NM-RFND00001",
        room=room,
        user=user,
        guest_first_name="A",
        guest_last_name="B",
        guest_email="rb@x.com",
        start_date=date.today() + timedelta(days=5),
        end_date=date.today() + timedelta(days=7),
        num_guests=1,
        total_amount=Decimal("3000"),
        status=Booking.Status.CONFIRMED,
    )
    Payment.objects.create(
        booking=booking,
        amount=booking.total_amount,
        method=Payment.Method.CARD,
        status=Payment.Status.SUCCESS,
        transaction_id="cs_test_paid",
    )

    client.force_login(user)
    resp = client.post(reverse("cancel_booking", args=[booking.reference]))
    assert resp.status_code == 302
    assert calls["called_with"] == booking.reference
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CANCELLED


@pytest.mark.django_db
def test_refund_booking_skips_when_no_success_payment(hotel, room):
    from hotel_app import payments as stripe_payments

    booking = Booking.objects.create(
        reference="NM-NOPAY0001",
        room=room,
        guest_first_name="A",
        guest_last_name="B",
        guest_email="np@x.com",
        start_date=date.today() + timedelta(days=10),
        end_date=date.today() + timedelta(days=12),
        num_guests=1,
        total_amount=Decimal("3000"),
        status=Booking.Status.PENDING,
    )
    status, detail = stripe_payments.refund_booking(booking)
    assert status == "nothing-to-refund"
    assert detail is None


@pytest.mark.django_db
def test_razorpay_webhook_is_idempotent(hotel, room):
    from hotel_app import payments as gateway

    booking = Booking.objects.create(
        reference="NM-IDEM0001",
        room=room,
        guest_first_name="A",
        guest_last_name="B",
        guest_email="idem@x.com",
        start_date=date.today() + timedelta(days=10),
        end_date=date.today() + timedelta(days=12),
        num_guests=1,
        total_amount=Decimal("3000"),
        status=Booking.Status.CONFIRMED,
    )
    Payment.objects.create(
        booking=booking,
        amount=booking.total_amount,
        method=Payment.Method.CARD,
        status=Payment.Status.SUCCESS,
        transaction_id="pay_test_idem",
    )

    event = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_idem",
                    "order_id": "order_test_idem",
                    "method": "card",
                }
            }
        },
    }
    assert gateway.handle_webhook_event(event) == "noop:already-success"
