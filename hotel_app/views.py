import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Booking, Payment, amenities, hotels
from accounts.utils import sendCustomer

from . import payments as gateway
from .forms import BookingForm, ReviewForm

logger = logging.getLogger(__name__)


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _parse_decimal(value):
    try:
        return Decimal(value)
    except (TypeError, InvalidOperation):
        return None


# Cache key constants — also referenced by accounts/signals.py to invalidate.
CACHE_KEY_BLOCKED_VENDORS = "blocked_vendor_ids"
CACHE_KEY_HOME_PREFIX = "home_hotels"  # full key: f"{prefix}:{params_hash}"
CACHE_TTL_BLOCKED = 5 * 60  # 5 min, signal-busted on save
CACHE_TTL_HOME = 60  # 1 min — listings refresh quickly


def _compute_blocked_vendor_ids():
    """Underlying computation — bypasses cache. Used by the cached wrapper
    below and by tests that want to assert exact state.
    """
    from datetime import timedelta

    from django.utils import timezone

    from accounts.models import VendorCharge

    today = timezone.now().date()
    blocked = set()
    for c in VendorCharge.objects.filter(status="pending").only(
        "vendor_id", "due_date", "grace_days"
    ):
        if c.due_date is None:
            continue
        if today > c.due_date + timedelta(days=c.grace_days):
            blocked.add(c.vendor_id)
    return blocked


def _blocked_vendor_ids():
    """Cached IDs of vendors whose hotels should be hidden from the public site.

    A vendor is "blocked" if they have at least one PENDING VendorCharge
    that's past its grace period (due_date + grace_days).

    Cached for CACHE_TTL_BLOCKED. Signals on VendorCharge.save() invalidate
    immediately when status flips to PAID/WAIVED — so a vendor who pays sees
    their hotels reappear without waiting for the TTL.
    """
    from django.core.cache import cache

    cached = cache.get(CACHE_KEY_BLOCKED_VENDORS)
    if cached is not None:
        return cached
    result = _compute_blocked_vendor_ids()
    # Cache the FROZEN set so callers can't accidentally mutate the shared
    # cache value (LocMemCache returns the same object reference each get).
    cache.set(CACHE_KEY_BLOCKED_VENDORS, frozenset(result), CACHE_TTL_BLOCKED)
    return result


def _home_cache_key(get_params):
    """Stable cache key for the home-page hotel list, built from the
    relevant filter / sort GET params. Sorted so ?a=1&b=2 and ?b=2&a=1
    map to the same cache entry. Amenity list is sorted too.

    The key also includes a version counter (incremented by signal handlers
    in accounts/signals.py whenever a hotel / review / vendor charge changes).
    Bumping the version effectively invalidates *every* cached filter combo
    in one operation — works on any cache backend, no `delete_pattern` needed.
    """
    import hashlib

    from django.core.cache import cache

    parts = []
    for k in ("search", "location", "max_price", "min_rating", "start_date", "end_date", "sort"):
        v = (get_params.get(k) or "").strip()
        if v:
            parts.append(f"{k}={v}")
    amenities = sorted(get_params.getlist("amenity"))
    if amenities:
        parts.append("amenities=" + ",".join(amenities))
    if not parts:
        suffix = "default"
    else:
        # Hash so the key length stays bounded even with long search strings.
        suffix = hashlib.md5("|".join(parts).encode()).hexdigest()[:16]
    version = cache.get(f"{CACHE_KEY_HOME_PREFIX}:version", 0)
    return f"{CACHE_KEY_HOME_PREFIX}:v{version}:{suffix}"


def home(request):
    from django.core.cache import cache

    # Hot path: if we've computed this exact filter combination in the last
    # CACHE_TTL_HOME seconds, reuse the result. We cache the *list* of hotels
    # (forcing queryset evaluation) so the cached object has no live DB cursor.
    # Note: this is anon-and-auth shared because the user-specific bits
    # (navbar, bottom bar) live in templates, not in this data. Different
    # users browsing the same filters see the same hotel grid — which is what
    # we want.
    cache_key = _home_cache_key(request.GET)
    cached_hotels = cache.get(cache_key)

    # ---- Parse params (always — they get echoed back into the form) ----
    search_query = (request.GET.get("search") or "").strip()
    location = (request.GET.get("location") or "").strip()
    max_price = _parse_decimal(request.GET.get("max_price"))
    min_rating = _parse_decimal(request.GET.get("min_rating"))
    amenity_ids = [int(a) for a in request.GET.getlist("amenity") if a.isdigit()]
    start = _parse_date(request.GET.get("start_date"))
    end = _parse_date(request.GET.get("end_date"))
    sort_by = request.GET.get("sort")

    if cached_hotels is None:
        qs = hotels.objects.filter(is_active=True).prefetch_related(
            "hotel_amenities", "hotel_images"
        )
        # Hide hotels whose vendor has overdue platform charges.
        blocked = _blocked_vendor_ids()
        if blocked:
            qs = qs.exclude(hotel_owner_id__in=blocked)

        if search_query:
            qs = qs.filter(
                Q(hotel_name__icontains=search_query) | Q(hotel_location__icontains=search_query)
            )
        if location:
            qs = qs.filter(hotel_location__icontains=location)
        if max_price is not None:
            qs = qs.filter(hotel_offer_price__lte=float(max_price))
        if min_rating is not None:
            qs = qs.filter(rating_avg__gte=min_rating)
        if amenity_ids:
            # Match hotels that have ALL the selected amenities (AND), not ANY.
            qs = (
                qs.filter(hotel_amenities__in=amenity_ids)
                .annotate(
                    n_match=Count(
                        "hotel_amenities",
                        filter=Q(hotel_amenities__in=amenity_ids),
                        distinct=True,
                    )
                )
                .filter(n_match=len(amenity_ids))
            )
        if start and end and end > start:
            # Keep only hotels that have at least one room with free inventory
            # over the requested window. We compute this in Python rather than a
            # single SQL window query for clarity at this scale.
            available_hotel_ids = []
            for h in qs.prefetch_related("rooms__bookings"):
                for r in h.rooms.filter(is_active=True):
                    if r.is_available(start, end):
                        available_hotel_ids.append(h.pk)
                        break
            qs = qs.filter(pk__in=available_hotel_ids)

        if sort_by == "low":
            qs = qs.order_by("hotel_offer_price")
        elif sort_by == "high":
            qs = qs.order_by("-hotel_offer_price")
        elif sort_by == "rating":
            qs = qs.order_by("-rating_avg", "-rating_count")
        else:
            qs = qs.order_by("-rating_avg", "hotel_name")

        # Force-evaluate to a list before caching. The list contains model
        # instances with their prefetch_related caches intact — the template
        # can iterate without hitting the DB again.
        cached_hotels = list(qs.distinct())
        cache.set(cache_key, cached_hotels, CACHE_TTL_HOME)

    context = {
        # `cached_hotels` is a plain list, prefetch caches intact — the
        # template iterates it identically to a queryset.
        "Hotel": cached_hotels,
        "all_amenities": amenities.objects.all(),
        "q": {
            "search": search_query,
            "location": location,
            "max_price": request.GET.get("max_price", ""),
            "min_rating": request.GET.get("min_rating", ""),
            "start_date": request.GET.get("start_date", ""),
            "end_date": request.GET.get("end_date", ""),
            "sort": sort_by or "",
            "amenity_ids": amenity_ids,
        },
    }
    if request.headers.get("HX-Request") == "true":
        return render(request, "_hotel_grid.html", context)
    return render(request, "index.html", context)


@login_required(login_url="/account/login_page/")
def hotel_details(request, slug):
    hotel_obj = get_object_or_404(
        hotels.objects.prefetch_related("rooms").select_related("hotel_owner"),
        hotel_slug=slug,
    )
    # If the owner has overdue platform charges, hide the hotel from the
    # public site (the vendor can still see + manage it from their dashboard).
    if hotel_obj.hotel_owner_id in _blocked_vendor_ids():
        # Customer never knows the URL existed.
        from django.http import Http404

        raise Http404("Hotel not available.")

    if request.method == "POST":
        form = BookingForm(request.POST, hotel=hotel_obj, user=request.user)
        if form.is_valid():
            booking = form.save()
            # Record the initial payment attempt as INITIATED. A real payment
            # gateway callback would later flip this to SUCCESS and bump the
            # booking to CONFIRMED.
            Payment.objects.create(
                booking=booking,
                amount=booking.total_amount,
                method=form.cleaned_data["payment_method"],
                status=Payment.Status.INITIATED,
            )
            messages.success(
                request,
                f"Booking {booking.reference} created. Complete payment to confirm.",
            )
            sendCustomer(booking.guest_email, booking.room.hotel, booking.total_amount)
            return redirect("payment_checkout", reference=booking.reference)

        for error in form.non_field_errors():
            messages.error(request, error)
        for field, errs in form.errors.items():
            if field == "__all__":
                continue
            for err in errs:
                messages.error(request, f"{field}: {err}")
    else:
        # Pre-fill guest details from the user's account so they don't retype.
        # Phone lives on the hotel_owner profile (if the user is a customer);
        # fall back to empty if they don't have one yet.
        user = request.user
        phone = ""
        owner = getattr(user, "owner_profile", None)
        if owner:
            phone = owner.phone_number or ""
        form = BookingForm(
            hotel=hotel_obj,
            user=user,
            initial={
                "guest_first_name": user.first_name,
                "guest_last_name": user.last_name,
                "guest_email": user.email,
                "guest_phone": phone,
                "num_guests": 1,
            },
        )

    reviews = hotel_obj.reviews.select_related("user").all()[:20]

    return render(
        request,
        "hotel_details.html",
        context={
            "hotel": hotel_obj,
            "form": form,
            "rooms": hotel_obj.rooms.filter(is_active=True),
            "reviews": reviews,
        },
    )


@login_required(login_url="/account/login_page/")
def submit_review(request, reference):
    """Only the booking owner can review, and only after the stay is completed."""
    booking = get_object_or_404(Booking, reference=reference)
    if booking.user_id != request.user.id:
        raise PermissionDenied("Not your booking.")
    if booking.status != Booking.Status.COMPLETED:
        messages.error(request, "You can only review a stay after check-out.")
        return redirect("my_bookings")
    if hasattr(booking, "review"):
        messages.info(request, "You've already reviewed this stay.")
        return redirect("my_bookings")

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.booking = booking
            review.hotel = booking.room.hotel
            review.user = request.user
            review.save()
            messages.success(request, "Thanks for your review!")
            return redirect("hotel_details", slug=booking.room.hotel.hotel_slug)
    else:
        form = ReviewForm()
    return render(request, "submit_review.html", {"form": form, "booking": booking})


@login_required(login_url="/account/login_page/")
def my_bookings(request):
    bookings = (
        Booking.objects.filter(user=request.user)
        .select_related("room", "room__hotel")
        .prefetch_related("payments")
    )
    return render(request, "my_bookings.html", {"bookings": bookings})


@login_required(login_url="/account/login_page/")
def cancel_booking(request, reference):
    booking = get_object_or_404(Booking, reference=reference)
    # Owner check: only the guest who made it, or staff, can cancel.
    if booking.user_id != request.user.id and not request.user.is_staff:
        raise PermissionDenied("Not your booking.")
    if not booking.is_cancellable:
        messages.error(request, "This booking can no longer be cancelled.")
        return redirect("my_bookings")

    booking.cancel(reason=request.POST.get("reason", "")[:500])

    # Best-effort refund — never block the user-facing cancel on the gateway being slow/down.
    if settings.RAZORPAY_KEY_SECRET:
        status, detail = gateway.refund_booking(booking)
        if status == "refunded":
            messages.success(
                request,
                f"Booking {booking.reference} cancelled and refund initiated (ref: {detail}).",
            )
        elif status == "nothing-to-refund":
            messages.success(request, f"Booking {booking.reference} cancelled.")
        else:
            # Cancellation already saved; surface a non-fatal note.
            messages.warning(
                request,
                f"Booking {booking.reference} cancelled, but refund could not be processed automatically. "
                "Our team will follow up.",
            )
            logger.error("Refund failed for %s: %s", booking.reference, detail)
    else:
        messages.success(request, f"Booking {booking.reference} cancelled.")

    return redirect("my_bookings")


def user_logout(request):
    logout(request)
    return redirect("/account/vendor_login/")


def about(request):
    return render(request, "about.html")


def pricing(request):
    from accounts.models import Plan, hotel_vendor
    plans = Plan.objects.filter(is_active=True).order_by("sort_order", "price_monthly_inr")
    vendor = None
    if request.user.is_authenticated:
        vendor = hotel_vendor.objects.filter(user=request.user).first()
    return render(request, "pricing.html", {
        "plans": plans,
        "is_vendor": vendor is not None,
        "current_plan": vendor.current_plan if vendor else None,
    })


def contact(request):
    """Public Contact Us page — renders the form, processes the POST.

    On success: persist a ContactMessage, fire off (a) an ops notification
    email to the team, (b) an ack email to the submitter, then PRG-redirect
    to ?sent=1 so a browser refresh doesn't resubmit.
    """
    from accounts.utils import sendContactAck, sendContactNotification

    from .forms import ContactForm

    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            if request.user.is_authenticated:
                msg.user = request.user
            # Capture light request metadata for triage / spam analysis.
            xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
            msg.ip_address = (
                xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
            ) or None
            msg.user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:255]
            msg.save()

            # Best-effort emails — never block the success path on SMTP.
            sendContactNotification(msg)
            sendContactAck(msg)

            messages.success(
                request,
                "Thanks — we got your message. We'll get back to you within 1–2 business days.",
            )
            # Post/Redirect/Get so a refresh doesn't resubmit.
            return redirect(f"{request.path}?sent=1")
    else:
        # Pre-fill from logged-in user so they don't retype.
        initial = {}
        if request.user.is_authenticated:
            initial.update(
                {
                    "first_name": request.user.first_name,
                    "last_name": request.user.last_name,
                    "email": request.user.email,
                }
            )
        form = ContactForm(initial=initial)

    return render(
        request,
        "contact.html",
        {
            "form": form,
            "sent": request.GET.get("sent") == "1",
        },
    )


# ---------- Payment (DEMO MODE) ----------
# Real Razorpay integration lives in hotel_app/payments.py — kept intact for
# when you're ready to switch back. To re-enable: paste real keys into .env,
# revert payment_checkout/payment_verify below to the Razorpay versions
# (see git history), and re-add the razorpay_webhook URL.


@login_required(login_url="/account/login_page/")
def payment_checkout(request, reference):
    """DEMO MODE — render a simulated checkout page.

    No real money moves. The user sees a polished mock checkout, clicks
    "Pay now" (which POSTs to /pay/confirm/), and the booking gets confirmed
    immediately. A receipt slip is emailed and made downloadable.
    """
    booking = get_object_or_404(
        Booking.objects.select_related("room", "room__hotel"),
        reference=reference,
    )
    if booking.user_id != request.user.id:
        raise PermissionDenied("Not your booking.")
    if booking.status != Booking.Status.PENDING:
        messages.info(request, "This booking is not awaiting payment.")
        return redirect("my_bookings")

    return render(request, "payment_checkout.html", {"booking": booking})


@require_POST
@login_required(login_url="/account/login_page/")
def dummy_pay(request, reference):
    """DEMO MODE confirm — marks the booking paid + emails the slip.

    Idempotent: if the booking is already CONFIRMED we just bounce them to
    the success page without re-emailing.
    """
    booking = get_object_or_404(
        Booking.objects.select_related("room", "room__hotel"),
        reference=reference,
    )
    if booking.user_id != request.user.id:
        raise PermissionDenied("Not your booking.")

    if booking.status == Booking.Status.PENDING:
        # Reuse the existing INITIATED Payment or create a fresh one.
        payment = (
            booking.payments.filter(status=Payment.Status.INITIATED).order_by("-created_at").first()
        )
        if payment is None:
            payment = Payment.objects.create(
                booking=booking,
                amount=booking.total_amount,
                method=Payment.Method.CARD,
                status=Payment.Status.INITIATED,
            )
        method = (request.POST.get("method") or "card").lower()
        method_map = {
            "card": Payment.Method.CARD,
            "upi": Payment.Method.UPI,
            "netbanking": Payment.Method.NETBANKING,
            "wallet": Payment.Method.WALLET,
        }
        payment.method = method_map.get(method, Payment.Method.CARD)
        payment.status = Payment.Status.SUCCESS
        payment.transaction_id = f"DEMO-{booking.reference}"
        payment.gateway_response = {"demo_mode": True, "method": method}
        payment.save(
            update_fields=["method", "status", "transaction_id", "gateway_response", "updated_at"]
        )

        booking.status = Booking.Status.CONFIRMED
        booking.save(update_fields=["status", "updated_at"])

        # Email the slip — best-effort; failure logs but doesn't block the user.
        from accounts.utils import sendBookingSlip

        # Pass `request` so the email's "view slip" link uses the same
        # host the customer just booked from (live URL in prod, not the
        # SITE_URL env default which is set to localhost for dev).
        sendBookingSlip(booking, request=request)

    return redirect("payment_success", reference=booking.reference)


# --- Razorpay verify endpoint (DISABLED in demo mode). Kept for easy re-enable.
# @require_POST
# @login_required(login_url='/account/login_page/')
# def payment_verify(request, reference):
#     """Browser-side success callback from Razorpay checkout.js."""
#     booking = get_object_or_404(Booking, reference=reference)
#     if booking.user_id != request.user.id:
#         raise PermissionDenied("Not your booking.")
#     order_id = request.POST.get("razorpay_order_id")
#     payment_id = request.POST.get("razorpay_payment_id")
#     signature = request.POST.get("razorpay_signature")
#     if not (order_id and payment_id and signature):
#         messages.error(request, "Payment response was incomplete. Please retry.")
#         return redirect('my_bookings')
#     _, status = gateway.verify_and_capture(order_id, payment_id, signature)
#     if status.startswith("ok") or status == "noop:already-success":
#         messages.success(request, f"Payment received — booking {booking.reference} confirmed.")
#         return redirect('payment_success', reference=booking.reference)
#     messages.error(request, "We couldn't verify your payment. If you were charged, please contact support.")
#     return redirect('my_bookings')


@login_required(login_url="/account/login_page/")
def booking_slip(request, reference):
    """Render a printable/downloadable booking receipt.

    The same template is reused for the email (renders to a string before
    sending). Users land here via 'Download slip' on payment_success or
    'View slip' from my bookings.
    """
    booking = get_object_or_404(
        Booking.objects.select_related("room", "room__hotel", "user"),
        reference=reference,
    )
    if booking.user_id != request.user.id and not request.user.is_staff:
        raise PermissionDenied("Not your booking.")
    return render(request, "booking_slip.html", {"booking": booking})


@login_required(login_url="/account/login_page/")
def payment_success(request, reference):
    """Friendly landing page after a successful payment."""
    booking = get_object_or_404(Booking, reference=reference)
    if booking.user_id != request.user.id:
        raise PermissionDenied("Not your booking.")
    return render(request, "payment_success.html", {"booking": booking})


@login_required(login_url="/account/login_page/")
def payment_cancel(request, reference):
    booking = get_object_or_404(Booking, reference=reference)
    if booking.user_id != request.user.id:
        raise PermissionDenied("Not your booking.")
    messages.warning(request, "Payment cancelled. Your booking is still on hold.")
    return redirect("my_bookings")


# --- Razorpay webhook (DISABLED in demo mode). Kept for easy re-enable.
# @csrf_exempt
# @require_POST
# def razorpay_webhook(request):
#     payload = request.body
#     sig = request.META.get("HTTP_X_RAZORPAY_SIGNATURE", "")
#     try:
#         event = gateway.construct_event(payload, sig)
#     except ValueError:
#         return HttpResponse(status=400)
#     except Exception:
#         logger.exception("Razorpay webhook signature verification failed")
#         return HttpResponse(status=400)
#     try:
#         gateway.handle_webhook_event(event)
#     except Exception:
#         logger.exception("Razorpay webhook processing failed for event %s", event.get("id"))
#         return HttpResponse(status=500)
#     return HttpResponse(status=200)
