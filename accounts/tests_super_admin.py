"""Tests for the super-admin area, vendor charges, and the blocked-vendor
filter on public listings."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from accounts.models import VendorCharge, hotel_vendor, hotels

# ---------- fixtures -----------------------------------------------------


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="root@x.com",
        email="root@x.com",
        password="pw12345678",
    )


@pytest.fixture
def vendor(db):
    u = User.objects.create_user(username="v@x.com", email="v@x.com", password="pw12345678")
    return hotel_vendor.objects.create(
        user=u,
        business_name="Stays Co",
        phone_number="+1900000200",
        is_verified=True,
    )


@pytest.fixture
def vendor_hotel(vendor):
    return hotels.objects.create(
        hotel_name="Stays Co Beachfront",
        hotel_description="desc",
        hotel_slug="stays-co-beach",
        hotel_owner=vendor,
        hotel_price=2000.0,
        hotel_offer_price=1500.0,
        hotel_location="Goa",
    )


# ---------- access control: 404 for non-superusers -----------------------


@pytest.mark.django_db
def test_super_dashboard_404s_for_anonymous(client):
    assert client.get(reverse("super_dashboard")).status_code == 404


@pytest.mark.django_db
def test_super_dashboard_404s_for_regular_user(client, vendor):
    client.force_login(vendor.user)
    assert client.get(reverse("super_dashboard")).status_code == 404


@pytest.mark.django_db
def test_super_dashboard_loads_for_superuser(client, superuser, vendor):
    client.force_login(superuser)
    resp = client.get(reverse("super_dashboard"))
    assert resp.status_code == 200
    assert b"Stays Co" in resp.content


@pytest.mark.django_db
def test_vendor_detail_loads_for_superuser(client, superuser, vendor):
    client.force_login(superuser)
    resp = client.get(reverse("super_vendor_detail", args=[vendor.id]))
    assert resp.status_code == 200


# ---------- VendorCharge date helpers ------------------------------------


@pytest.mark.django_db
def test_charge_overdue_when_past_grace(vendor):
    c = VendorCharge.objects.create(
        vendor=vendor,
        amount=Decimal("100"),
        kind=VendorCharge.Kind.PUBLISH,
        due_date=date.today() - timedelta(days=20),
        grace_days=15,
    )
    assert c.is_overdue is True
    assert c.effective_due_date == c.due_date + timedelta(days=15)


@pytest.mark.django_db
def test_charge_not_overdue_when_inside_grace(vendor):
    c = VendorCharge.objects.create(
        vendor=vendor,
        amount=Decimal("100"),
        due_date=date.today() - timedelta(days=5),
        grace_days=15,
    )
    assert c.is_overdue is False
    assert c.is_in_reminder_window is True


@pytest.mark.django_db
def test_reminder_window_starts_five_days_before_due(vendor):
    c = VendorCharge.objects.create(
        vendor=vendor,
        amount=Decimal("100"),
        due_date=date.today() + timedelta(days=3),  # 3 days out
        grace_days=15,
    )
    assert c.is_in_reminder_window is True


@pytest.mark.django_db
def test_paid_charge_never_in_reminder_window(vendor):
    c = VendorCharge.objects.create(
        vendor=vendor,
        amount=Decimal("100"),
        due_date=date.today() - timedelta(days=1),
        grace_days=15,
    )
    c.mark_paid()
    assert c.is_in_reminder_window is False
    assert c.is_overdue is False


# ---------- blocked-vendor filter on public listings --------------------


@pytest.mark.django_db
def test_overdue_vendor_hotel_hidden_from_home(client, vendor, vendor_hotel):
    # Create a clearly-overdue charge: due 30 days ago, no grace.
    VendorCharge.objects.create(
        vendor=vendor,
        amount=Decimal("100"),
        due_date=date.today() - timedelta(days=30),
        grace_days=0,
    )
    resp = client.get(reverse("home"))
    assert resp.status_code == 200
    assert b"Stays Co Beachfront" not in resp.content


@pytest.mark.django_db
def test_overdue_vendor_hotel_404s_on_direct_url(client, vendor, vendor_hotel):
    VendorCharge.objects.create(
        vendor=vendor,
        amount=Decimal("100"),
        due_date=date.today() - timedelta(days=30),
        grace_days=0,
    )
    # The detail view requires auth before checking the block — log in first.
    customer = User.objects.create_user(username="c@x.com", email="c@x.com", password="pw12345678")
    client.force_login(customer)
    resp = client.get(reverse("hotel_details", args=[vendor_hotel.hotel_slug]))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_paying_overdue_charge_unblocks_listing(client, vendor, vendor_hotel):
    charge = VendorCharge.objects.create(
        vendor=vendor,
        amount=Decimal("100"),
        due_date=date.today() - timedelta(days=30),
        grace_days=0,
    )
    # Block confirmed.
    assert b"Stays Co Beachfront" not in client.get(reverse("home")).content
    # Vendor pays.
    charge.mark_paid()
    # Listing returns.
    assert b"Stays Co Beachfront" in client.get(reverse("home")).content


# ---------- vendor pay_charge view --------------------------------------


@pytest.mark.django_db
def test_pay_charge_marks_paid_and_redirects(client, vendor):
    charge = VendorCharge.objects.create(
        vendor=vendor,
        amount=Decimal("500"),
        due_date=date.today(),
        grace_days=15,
    )
    client.force_login(vendor.user)
    resp = client.post(reverse("pay_charge", args=[charge.id]))
    assert resp.status_code == 302
    charge.refresh_from_db()
    assert charge.status == VendorCharge.Status.PAID
    assert charge.paid_at is not None


@pytest.mark.django_db
def test_pay_charge_rejects_non_owner(client, vendor):
    charge = VendorCharge.objects.create(
        vendor=vendor,
        amount=Decimal("500"),
        due_date=date.today(),
    )
    intruder = User.objects.create_user(
        username="bad@x.com", email="bad@x.com", password="pw12345678"
    )
    client.force_login(intruder)
    resp = client.post(reverse("pay_charge", args=[charge.id]))
    assert resp.status_code == 403
    charge.refresh_from_db()
    assert charge.status == VendorCharge.Status.PENDING
