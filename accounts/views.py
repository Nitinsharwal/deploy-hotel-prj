import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q as models_Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    CustomerRegisterForm,
    HotelForm,
    LoginForm,
    ProfileForm,
    RoomForm,
    VendorRegisterForm,
)
from .models import (
    Booking,
    Room,
    amenities,
    hotel_images,
    hotel_owner,
    hotel_vendor,
    hotels,
)
from .utils import generateSlug, random_token, sendEmail, sendOtp


def logout_user(request):
    logout(request)
    return redirect("login_page")


def login_page(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please enter a valid email and password.")
            return redirect("/account/login_page")

        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]

        # ── Superuser path: 2FA via email OTP ──────────────────────────────
        # Superusers created with `python manage.py createsuperuser` typically
        # don't have a hotel_owner profile. We branch on `is_superuser` so the
        # check happens BEFORE the customer profile lookup. Auth succeeds
        # silently first (no session), then we email a 6-digit code and
        # require the user to enter it on /account/super_otp_verify/ before
        # we actually call login(request, ...).
        su = User.objects.filter(
            models_Q(email__iexact=email) | models_Q(username__iexact=email),
            is_superuser=True,
        ).first()
        if su:
            authd = authenticate(request, username=su.username, password=password)
            if authd is None:
                messages.error(request, "Invalid credentials")
                return redirect("/account/login_page")
            # Generate a fresh OTP, hash it, stash with a 10-min expiry on the session.
            otp = f"{random.randint(100000, 999999)}"
            request.session["pending_su_id"] = su.id
            request.session["pending_su_otp_hash"] = make_password(otp)
            request.session["pending_su_otp_expiry"] = (
                timezone.now() + timedelta(minutes=10)
            ).isoformat()
            request.session["pending_su_attempts"] = 0
            sendOtp(su.email, otp)
            messages.info(request, f"Security code sent to {su.email}.")
            return redirect("super_otp_verify")

        # ── Regular customer path ─────────────────────────────────────────
        owner = hotel_owner.objects.select_related("user").filter(user__email=email).first()
        if not owner:
            messages.error(request, "Account Not Found..!!")
            return redirect("/account/register_page")
        if not owner.is_verified:
            messages.error(request, "Account Not verified..!!")
            return redirect("/account/login_page")

        # request is passed so django-axes can record/throttle failed attempts.
        user = authenticate(request, username=owner.user.username, password=password)
        if user:
            messages.success(request, "Welcome to noma hotel..!")
            login(request, user)
            return redirect("/")
        messages.error(request, "Invalid credentials")
        return redirect("/account/login_page")
    return render(request, "login_page.html")


def super_otp_verify(request):
    """Second factor for superuser logins.

    Reads pending state from session (set by login_page after a successful
    superuser password match). On a correct OTP we finally call login() and
    redirect to /super-admin/. Limited to 5 attempts to thwart brute force,
    expires in 10 minutes.
    """
    pending_id = request.session.get("pending_su_id")
    if not pending_id:
        return redirect("login_page")

    expiry_iso = request.session.get("pending_su_otp_expiry")
    expired = True
    if expiry_iso:
        try:
            expired = timezone.now() > datetime.fromisoformat(expiry_iso)
        except ValueError:
            expired = True
    if expired:
        for k in (
            "pending_su_id",
            "pending_su_otp_hash",
            "pending_su_otp_expiry",
            "pending_su_attempts",
        ):
            request.session.pop(k, None)
        messages.error(request, "Code expired. Please log in again.")
        return redirect("login_page")

    user_email = User.objects.filter(pk=pending_id).values_list("email", flat=True).first() or ""

    if request.method == "POST":
        attempts = request.session.get("pending_su_attempts", 0)
        if attempts >= 5:
            for k in (
                "pending_su_id",
                "pending_su_otp_hash",
                "pending_su_otp_expiry",
                "pending_su_attempts",
            ):
                request.session.pop(k, None)
            messages.error(request, "Too many wrong attempts. Please log in again.")
            return redirect("login_page")

        otp = (request.POST.get("otp") or "").strip()
        otp_hash = request.session.get("pending_su_otp_hash")
        if otp and otp_hash and check_password(otp, otp_hash):
            try:
                user = User.objects.get(pk=pending_id, is_superuser=True)
            except User.DoesNotExist:
                messages.error(request, "Account no longer exists.")
                return redirect("login_page")
            # Clean session before logging in (login() rotates the session anyway).
            for k in (
                "pending_su_id",
                "pending_su_otp_hash",
                "pending_su_otp_expiry",
                "pending_su_attempts",
            ):
                request.session.pop(k, None)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Two-factor verification successful — welcome back.")
            return redirect("super_dashboard")

        request.session["pending_su_attempts"] = attempts + 1
        messages.error(request, f"Wrong code. {4 - attempts} attempts remaining.")
        return redirect("super_otp_verify")

    return render(request, "super_otp_verify.html", {"email": user_email})


def register_page(request):
    if request.method == "POST":
        form = CustomerRegisterForm(request.POST)
        if not form.is_valid():
            for err in form.non_field_errors():
                messages.error(request, err)
            for field, errs in form.errors.items():
                if field == "__all__":
                    continue
                for err in errs:
                    messages.error(request, f"{field}: {err}")
            return redirect("/account/register_page")

        data = form.cleaned_data
        user = User.objects.create_user(
            username=data["email"],
            email=data["email"],
            first_name=data["firstname"],
            last_name=data["lastname"],
            password=data["password"],
        )
        owner_profile = hotel_owner.objects.create(
            user=user,
            phone_number=data["phone_number"],
            email_token=random_token(),
        )
        sendEmail(data["email"], owner_profile.email_token)
        # Second, branded "Welcome to Noma" email. Best-effort — never blocks
        # registration if SMTP hiccups; errors are logged inside _safe_send_mail.
        from .utils import sendCustomerWelcome

        sendCustomerWelcome(user)
        messages.success(request, "An email is sent to your email..!")
        return redirect("/account/register_page")
    return render(request, "register_page.html")


def verify_email_token(request, token):
    owner = hotel_owner.objects.filter(email_token=token).first()
    if owner:
        owner.is_verified = True
        owner.save(update_fields=["is_verified"])
        messages.success(request, "E-mail verified! You can log in now.")
        return redirect("/account/login_page")

    vendor = hotel_vendor.objects.filter(email_token=token).first()
    if vendor:
        vendor.is_verified = True
        vendor.save(update_fields=["is_verified"])
        messages.success(request, "Vendor email verified! Please log in.")
        return redirect("/account/vendor_login")

    return HttpResponse("Invalid token....!", status=400)


def send_otp(request, email):
    owner = hotel_owner.objects.select_related("user").filter(user__email=email).first()
    if not owner:
        messages.error(request, "Account Not Found..!!")
        return redirect("/account/register_page")

    otp = str(random.randint(100000, 999999))
    # Store only the hash; the plaintext OTP exists in memory just long enough to email it.
    owner.otp = make_password(otp)
    owner.save(update_fields=["otp"])
    sendOtp(email, otp)
    messages.success(request, "An OTP has been sent to your email")
    return redirect(f"/account/{email}/verify_otp")


def verify_otp(request, email):
    if request.method == "POST":
        otp = request.POST.get("otp", "").strip()
        owner = hotel_owner.objects.select_related("user").filter(user__email=email).first()

        if owner and owner.otp and check_password(otp, owner.otp):
            owner.otp = None
            owner.save(update_fields=["otp"])
            messages.success(request, "Login successful")
            # We bypass authenticate() for OTP, so user.backend isn't set.
            # With django-axes adding a 2nd backend, login() can't pick one
            # automatically — tell it which to record on the session.
            login(request, owner.user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("/")
        messages.warning(request, "Wrong OTP")
        return redirect(f"/account/{email}/verify_otp")

    return render(request, "send_otp.html")


# -----------------------for Businessman / Vendor------------------
def vendor_logout(request):
    logout(request)
    return redirect("/account/vendor_login")


def vendor_login(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please enter a valid email and password.")
            return redirect("/account/vendor_login")

        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]
        vendor = hotel_vendor.objects.select_related("user").filter(user__email=email).first()
        if not vendor:
            messages.error(request, "Account Not Found..!!")
            return redirect("/account/vendor_register")
        if not vendor.is_verified:
            messages.error(request, "Account Not verified..!!")
            return redirect("/account/vendor_login")

        user = authenticate(request, username=vendor.user.username, password=password)
        if user:
            messages.success(request, "Welcome to Noma hotel..!")
            login(request, user)
            return redirect("ven_dashboard")
        messages.error(request, "Invalid credentials")
        return redirect("/account/vendor_login")
    return render(request, "vendor/vendor_login.html")


def vendor_register(request):
    if request.method == "POST":
        form = VendorRegisterForm(request.POST, request.FILES)
        if not form.is_valid():
            for err in form.non_field_errors():
                messages.error(request, err)
            for field, errs in form.errors.items():
                if field == "__all__":
                    continue
                for err in errs:
                    messages.error(request, f"{field}: {err}")
            return redirect("/account/vendor_register")

        data = form.cleaned_data
        user = User.objects.create_user(
            username=data["email"],
            email=data["email"],
            first_name=data["firstname"],
            last_name=data["lastname"],
            password=data["password"],
        )
        vendor_profile = hotel_vendor.objects.create(
            user=user,
            business_name=data["business_name"],
            phone_number=data["phone_number"],
            profile_pic=data.get("profile_image"),
            email_token=random_token(),
        )
        sendEmail(data["email"], vendor_profile.email_token)
        # Branded vendor welcome — same best-effort pattern as customer flow.
        from .utils import sendVendorWelcome

        sendVendorWelcome(vendor_profile)
        messages.success(request, "An email is sent to your email..!")
        return redirect("/account/vendor_login")
    return render(request, "vendor/vendor_register.html")


@login_required(login_url="vendor_login")
def ven_dashboard(request):
    vendor = hotel_vendor.objects.filter(user=request.user).first()
    if not vendor:
        messages.error(request, "You are not registered as a hotel vendor.")
        return redirect("vendor_register")

    vendor_hotels = hotels.objects.filter(hotel_owner=vendor).prefetch_related(
        "hotel_images", "rooms"
    )
    bookings = (
        Booking.objects.filter(room__hotel__in=vendor_hotels)
        .select_related("room", "room__hotel", "user")
        .order_by("-created_at")
    )

    # Pull charges so we can show the outstanding-amount banner + table.
    # Sorted with the most urgent (overdue → soon-due → recent) first.
    from .models import VendorCharge

    pending_charges = list(
        vendor.charges.filter(status=VendorCharge.Status.PENDING).order_by("due_date")
    )
    past_charges = vendor.charges.exclude(status=VendorCharge.Status.PENDING).order_by(
        "-created_at"
    )[:10]
    outstanding_total = sum((c.amount for c in pending_charges), start=Decimal("0"))
    has_overdue = any(c.is_overdue for c in pending_charges)

    return render(
        request,
        "vendor/ven_dashboard.html",
        context={
            "hotels": vendor_hotels,
            "bookings": bookings,
            "pending_charges": pending_charges,
            "past_charges": past_charges,
            "outstanding_total": outstanding_total,
            "has_overdue": has_overdue,
        },
    )


@login_required(login_url="vendor_login")
def add_hotel(request):
    vendor = hotel_vendor.objects.filter(user=request.user).first()
    if not vendor:
        messages.error(request, "You are not registered as a hotel vendor.")
        return redirect("vendor_register")

    if request.method == "POST":
        form = HotelForm(request.POST)
        if form.is_valid():
            hotel_obj = form.save(commit=False)
            hotel_obj.hotel_owner = vendor
            hotel_obj.hotel_slug = generateSlug(form.cleaned_data["hotel_name"])
            hotel_obj.save()
            form.save_m2m()
            messages.success(request, "Hotel added successfully..!!")
            return redirect("/account/add_hotel")
        for err in form.non_field_errors():
            messages.error(request, err)
    else:
        form = HotelForm()

    return render(
        request,
        "vendor/add_hotel.html",
        context={"form": form, "Amenities": amenities.objects.all()},
    )


@login_required(login_url="vendor_login")
def upload_images(request, slug):
    hotel_obj = get_object_or_404(hotels, hotel_slug=slug)
    if hotel_obj.hotel_owner.user_id != request.user.id:
        raise PermissionDenied("You do not own this hotel.")

    if request.method == "POST":
        # Accept either the new batch field ('images') or the legacy single-file
        # field ('image') — the template now sends 'images' with `multiple`.
        files = request.FILES.getlist("images")
        if not files and "image" in request.FILES:
            files = [request.FILES["image"]]

        allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
        max_bytes = 5 * 1024 * 1024  # 5 MB per file
        accepted, rejected = [], []
        for f in files:
            if f.content_type not in allowed_types:
                rejected.append(f"{f.name} (unsupported type)")
                continue
            if f.size > max_bytes:
                rejected.append(f"{f.name} (over 5MB)")
                continue
            accepted.append(hotel_images(hotel=hotel_obj, image=f))

        if not accepted and not rejected:
            messages.error(request, "Please choose at least one image to upload.")
            return HttpResponseRedirect(request.path_info)

        # bulk_create skips signals & per-row save() — fine because hotel_images
        # has no overrides. Single round-trip instead of N.
        hotel_images.objects.bulk_create(accepted)

        if accepted:
            messages.success(
                request, f"Uploaded {len(accepted)} image{'s' if len(accepted) != 1 else ''}."
            )
        for r in rejected:
            messages.warning(request, f"Skipped {r}")
        return HttpResponseRedirect(request.path_info)

    return render(
        request,
        "vendor/upload_image.html",
        context={"images": hotel_obj.hotel_images.all(), "hotel": hotel_obj},
    )


@login_required(login_url="vendor_login")
def delete_images(request, id):
    img = get_object_or_404(hotel_images, id=id)
    if img.hotel.hotel_owner.user_id != request.user.id:
        raise PermissionDenied("You do not own this hotel image.")
    if request.method != "POST":
        # Refuse GET to prevent CSRF / prefetcher-triggered deletes.
        return redirect("upload_images", slug=img.hotel.hotel_slug)
    slug = img.hotel.hotel_slug
    img.delete()
    messages.warning(request, "Image deleted successfully")
    return redirect("upload_images", slug=slug)


@login_required(login_url="vendor_login")
def edit_hotel(request, slug):
    hotel_obj = get_object_or_404(hotels, hotel_slug=slug)
    if hotel_obj.hotel_owner.user_id != request.user.id:
        raise PermissionDenied("You are not authorized to edit this hotel.")

    if request.method == "POST":
        form = HotelForm(request.POST, instance=hotel_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Hotel Updated Successfully")
            return HttpResponseRedirect(request.path_info)
        for err in form.non_field_errors():
            messages.error(request, err)
    else:
        form = HotelForm(instance=hotel_obj)

    return render(
        request,
        "vendor/edit_hotel.html",
        context={"form": form, "hotel": hotel_obj, "Amenities": amenities.objects.all()},
    )


# ---------- Room CRUD ----------


def _vendor_owned_hotel_or_403(request, slug):
    hotel_obj = get_object_or_404(hotels, hotel_slug=slug)
    if hotel_obj.hotel_owner.user_id != request.user.id:
        raise PermissionDenied("You do not own this hotel.")
    return hotel_obj


@login_required(login_url="vendor_login")
def manage_rooms(request, slug):
    hotel_obj = _vendor_owned_hotel_or_403(request, slug)
    rooms = hotel_obj.rooms.all()
    return render(
        request,
        "vendor/manage_rooms.html",
        context={"hotel": hotel_obj, "rooms": rooms},
    )


@login_required(login_url="vendor_login")
def add_room(request, slug):
    hotel_obj = _vendor_owned_hotel_or_403(request, slug)
    if request.method == "POST":
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.hotel = hotel_obj
            room.save()
            messages.success(request, f"Room '{room.name}' added.")
            return redirect("manage_rooms", slug=slug)
    else:
        form = RoomForm()
    return render(
        request,
        "vendor/room_form.html",
        context={"form": form, "hotel": hotel_obj, "mode": "add"},
    )


@login_required(login_url="vendor_login")
def edit_room(request, slug, room_id):
    hotel_obj = _vendor_owned_hotel_or_403(request, slug)
    room = get_object_or_404(Room, pk=room_id, hotel=hotel_obj)
    if request.method == "POST":
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, "Room updated.")
            return redirect("manage_rooms", slug=slug)
    else:
        form = RoomForm(instance=room)
    return render(
        request,
        "vendor/room_form.html",
        context={"form": form, "hotel": hotel_obj, "room": room, "mode": "edit"},
    )


@login_required(login_url="vendor_login")
def delete_room(request, slug, room_id):
    hotel_obj = _vendor_owned_hotel_or_403(request, slug)
    room = get_object_or_404(Room, pk=room_id, hotel=hotel_obj)
    if request.method != "POST":
        # Soft-guard: only allow POST to avoid accidental GET deletes from crawlers.
        return redirect("manage_rooms", slug=slug)
    # Prevent deletion if active bookings reference this room — protect=PROTECT on FK already
    # raises ProtectedError, but a friendlier check here gives a better UX.
    if room.bookings.exclude(status=Booking.Status.CANCELLED).exists():
        messages.error(
            request, "Cannot delete — this room has active bookings. Deactivate it instead."
        )
        return redirect("manage_rooms", slug=slug)
    room.delete()
    messages.warning(request, "Room deleted.")
    return redirect("manage_rooms", slug=slug)


# ---------- My profile (customer-facing account hub) ----------


@login_required(login_url="login_page")
def profile(request):
    """The personal dashboard: account details + booking history + reviews + stats."""
    # Avoid circular import; Booking/Review live in accounts.models so this is fine.
    from django.db.models import Count, Sum

    from .models import Booking, Review

    user = request.user
    owner = getattr(user, "owner_profile", None)  # may be None for vendors / superusers

    # Bookings — one queryset, partitioned in template by status.
    bookings_qs = (
        Booking.objects.filter(user=user)
        .select_related("room", "room__hotel")
        .prefetch_related("payments")
    )
    # Status-based partitioning happens in the template via {% if b.status == 'pending' %}
    # blocks — keeping it there means one queryset, no extra DB round-trips.

    # Stats — one DB round-trip each. With ~hundreds of bookings per user this is fine.
    stat_counts = bookings_qs.aggregate(
        total=Count("id"),
        confirmed=Count("id", filter=models_Q(status=Booking.Status.CONFIRMED)),
        pending=Count("id", filter=models_Q(status=Booking.Status.PENDING)),
        cancelled=Count("id", filter=models_Q(status=Booking.Status.CANCELLED)),
        completed=Count("id", filter=models_Q(status=Booking.Status.COMPLETED)),
    )
    total_spent = (
        bookings_qs.filter(
            status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED]
        ).aggregate(s=Sum("total_amount"))["s"]
        or 0
    )

    reviews = (
        Review.objects.filter(user=user)
        .select_related("hotel", "booking", "booking__room")
        .order_by("-created_at")
    )

    profile_form = ProfileForm(
        user=user,
        owner=owner,
        initial={
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": owner.phone_number if owner else "",
        },
    )

    return render(
        request,
        "profile.html",
        {
            "profile_user": user,
            "owner": owner,
            "bookings": bookings_qs,
            "stats": stat_counts,
            "total_spent": total_spent,
            "reviews": reviews,
            "profile_form": profile_form,
        },
    )


@login_required(login_url="login_page")
def update_profile(request):
    """Handle the profile-edit POST. Always redirects back to /account/profile/."""
    if request.method != "POST":
        return redirect("profile")
    owner = getattr(request.user, "owner_profile", None)
    form = ProfileForm(request.POST, request.FILES, user=request.user, owner=owner)
    if form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
    else:
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(request, f"{field}: {err}")
    return redirect("profile")


# ---------- Vendor pays a platform charge (demo mode) -----------------


@login_required(login_url="vendor_login")
def pay_charge(request, charge_id):
    """Vendor confirms payment for a platform charge.

    Demo mode (matches booking-payment flow): no real money moves. We just
    flip the charge to PAID and email a confirmation. If the vendor was
    overdue → blocked, marking paid unblocks their hotels automatically
    (the blocked-vendor filter just checks for pending overdue charges).
    """
    from .models import VendorCharge

    charge = get_object_or_404(
        VendorCharge.objects.select_related("vendor", "vendor__user"),
        pk=charge_id,
    )
    # Ownership check — only the vendor who owes can pay it.
    if charge.vendor.user_id != request.user.id:
        raise PermissionDenied("Not your charge.")
    if request.method != "POST":
        return redirect("ven_dashboard")
    if charge.status != VendorCharge.Status.PENDING:
        messages.info(request, "That charge isn't pending.")
        return redirect("ven_dashboard")

    charge.mark_paid()
    messages.success(
        request,
        f"Payment received — ₹{charge.amount} ({charge.get_kind_display()}). Thanks!",
    )

    # Best-effort email confirmation. Failure logs but doesn't break the flow.
    from .utils import sendChargePaidConfirmation

    sendChargePaidConfirmation(charge)

    return redirect("ven_dashboard")
