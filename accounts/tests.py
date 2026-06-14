import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from accounts.forms import CustomerRegisterForm, VendorRegisterForm
from accounts.models import hotel_owner


@pytest.mark.django_db
def test_customer_register_form_rejects_duplicate_email():
    User.objects.create_user(username="x@x.com", email="x@x.com", password="pw12345678")
    form = CustomerRegisterForm(
        data={
            "firstname": "A",
            "lastname": "B",
            "phone_number": "+919999999999",
            "email": "x@x.com",
            "password": "pw12345678",
        }
    )
    assert not form.is_valid()


@pytest.mark.django_db
def test_customer_register_form_rejects_short_password():
    form = CustomerRegisterForm(
        data={
            "firstname": "A",
            "lastname": "B",
            "phone_number": "+919999999991",
            "email": "new@x.com",
            "password": "short",
        }
    )
    assert not form.is_valid()
    assert "password" in form.errors


@pytest.mark.django_db
def test_vendor_register_form_happy_path():
    form = VendorRegisterForm(
        data={
            "firstname": "A",
            "lastname": "B",
            "business_name": "Biz",
            "phone_number": "+919999999992",
            "email": "biz@x.com",
            "password": "pw12345678",
        }
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_login_page_renders(client):
    resp = client.get(reverse("login_page"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_unverified_owner_cannot_login(client):
    user = User.objects.create_user(username="u@x.com", email="u@x.com", password="pw12345678")
    hotel_owner.objects.create(user=user, phone_number="+919000000001", is_verified=False)
    resp = client.post(reverse("login_page"), {"email": "u@x.com", "password": "pw12345678"})
    assert resp.status_code == 302
    assert "/account/login_page" in resp.url


@pytest.mark.django_db
def test_batch_image_upload_creates_multiple_rows(client, tmp_path):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from accounts.models import hotel_images, hotel_vendor, hotels

    # Tiny valid PNGs: 1x1 transparent.
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00"
        b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    owner_user = User.objects.create_user(
        username="vbatch@x.com", email="vbatch@x.com", password="pw12345678"
    )
    vendor = hotel_vendor.objects.create(
        user=owner_user,
        business_name="Batch",
        phone_number="+919999900001",
        is_verified=True,
    )
    hotel = hotels.objects.create(
        hotel_name="Batch Hotel",
        hotel_description="d",
        hotel_slug="batch-hotel",
        hotel_owner=vendor,
        hotel_price=1000,
        hotel_offer_price=900,
        hotel_location="Goa",
    )
    client.force_login(owner_user)

    f1 = SimpleUploadedFile("a.png", png_bytes, content_type="image/png")
    f2 = SimpleUploadedFile("b.png", png_bytes, content_type="image/png")
    bad = SimpleUploadedFile("c.txt", b"hello", content_type="text/plain")

    resp = client.post(reverse("upload_images", args=[hotel.hotel_slug]), {"images": [f1, f2, bad]})
    assert resp.status_code == 302
    assert hotel_images.objects.filter(hotel=hotel).count() == 2  # txt rejected


@pytest.mark.django_db
def test_bill_subscriptions_renews_paid_plan_and_creates_invoice():
    from datetime import timedelta
    from django.core.management import call_command
    from django.utils import timezone
    from accounts.models import Plan, VendorCharge, VendorSubscription, hotel_vendor

    user = User.objects.create_user(username="renew@x.com", email="renew@x.com", password="pw")
    vendor = hotel_vendor.objects.create(user=user, business_name="Renew Co", phone_number="111")
    pro = Plan.objects.get(slug=Plan.SLUG_PRO)

    today = timezone.localdate()
    sub = VendorSubscription.objects.create(
        vendor=vendor,
        plan=pro,
        status=VendorSubscription.Status.ACTIVE,
        period_start=today - timedelta(days=31),
        period_end=today - timedelta(days=1),
    )

    call_command("bill_subscriptions")

    sub.refresh_from_db()
    assert sub.status == VendorSubscription.Status.EXPIRED

    new_sub = VendorSubscription.objects.filter(
        vendor=vendor, status=VendorSubscription.Status.ACTIVE
    ).first()
    assert new_sub is not None
    assert new_sub.plan == pro
    assert new_sub.period_start == today

    charge = VendorCharge.objects.filter(vendor=vendor, kind=VendorCharge.Kind.SUBSCRIPTION).first()
    assert charge is not None
    assert charge.amount == pro.price_monthly_inr


@pytest.mark.django_db
def test_bill_subscriptions_executes_scheduled_downgrade_to_free():
    from datetime import timedelta
    from django.core.management import call_command
    from django.utils import timezone
    from accounts.models import Plan, VendorSubscription, hotel_vendor

    user = User.objects.create_user(username="dn@x.com", email="dn@x.com", password="pw")
    vendor = hotel_vendor.objects.create(user=user, business_name="Down Co", phone_number="222")
    pro = Plan.objects.get(slug=Plan.SLUG_PRO)
    free = Plan.objects.get(slug=Plan.SLUG_FREE)

    today = timezone.localdate()
    VendorSubscription.objects.create(
        vendor=vendor,
        plan=pro,
        status=VendorSubscription.Status.CANCELLED,
        period_start=today - timedelta(days=31),
        period_end=today - timedelta(days=1),
        cancelled_at=timezone.now(),
    )

    call_command("bill_subscriptions")

    new_sub = VendorSubscription.objects.filter(
        vendor=vendor, status=VendorSubscription.Status.ACTIVE
    ).first()
    assert new_sub is not None
    assert new_sub.plan == free
