from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    Booking,
    Payment,
    VendorCharge,
    hotel_vendor,
    hotels,
)


def _require_superuser(view):
    def wrapper(request, *args, **kwargs):
        u = request.user
        if not (u.is_authenticated and u.is_superuser):
            raise Http404("Not found.")
        return view(request, *args, **kwargs)

    wrapper.__name__ = view.__name__
    return wrapper


@_require_superuser
def payments(request):
    qs = (
        VendorCharge.objects.select_related("vendor", "vendor__user")
        .filter(status=VendorCharge.Status.PAID)
        .order_by("-paid_at", "-id")
    )

    kind = (request.GET.get("kind") or "").strip()
    q = (request.GET.get("q") or "").strip()
    if kind:
        qs = qs.filter(kind=kind)
    if q:
        qs = qs.filter(
            Q(vendor__business_name__icontains=q)
            | Q(vendor__user__email__icontains=q)
            | Q(description__icontains=q)
        )

    totals = {
        "count": qs.count(),
        "sum_amount": qs.aggregate(s=Sum("amount"))["s"] or 0,
        "all_time_count": VendorCharge.objects.filter(status=VendorCharge.Status.PAID).count(),
        "all_time_sum": VendorCharge.objects.filter(status=VendorCharge.Status.PAID).aggregate(
            s=Sum("amount")
        )["s"]
        or 0,
    }

    return render(
        request,
        "super_admin/payments.html",
        {
            "payments": qs[:200],
            "totals": totals,
            "kind_filter": kind or "all",
            "q": q,
            "kind_choices": VendorCharge.Kind.choices,
        },
    )


@_require_superuser
def dashboard(request):
    """Overview: vendor counts, charges totals, recent activity."""
    vendors_qs = (
        hotel_vendor.objects.select_related("user")
        .annotate(
            n_hotels=Count("hotels", distinct=True),
            n_bookings=Count("hotels__rooms__bookings", distinct=True),
            outstanding=Sum(
                "charges__amount",
                filter=Q(charges__status=VendorCharge.Status.PENDING),
            ),
            paid_to_date=Sum(
                "charges__amount",
                filter=Q(charges__status=VendorCharge.Status.PAID),
            ),
        )
        .order_by("-id")
    )

    # Top-line numbers
    stats = {
        "vendors_total": vendors_qs.count(),
        "vendors_verified": vendors_qs.filter(is_verified=True).count(),
        "hotels_total": hotels.objects.count(),
        "hotels_active": hotels.objects.filter(is_active=True).count(),
        "bookings_total": Booking.objects.count(),
        "revenue_paid": Payment.objects.filter(status=Payment.Status.SUCCESS).aggregate(
            s=Sum("amount")
        )["s"]
        or 0,
        "charges_pending": VendorCharge.objects.filter(
            status=VendorCharge.Status.PENDING
        ).aggregate(s=Sum("amount"))["s"]
        or 0,
        "charges_paid": VendorCharge.objects.filter(status=VendorCharge.Status.PAID).aggregate(
            s=Sum("amount")
        )["s"]
        or 0,
    }

    # Optional search by business name / email
    q = (request.GET.get("q") or "").strip()
    if q:
        vendors_qs = vendors_qs.filter(
            Q(business_name__icontains=q)
            | Q(user__email__icontains=q)
            | Q(phone_number__icontains=q)
        )

    # Status filter
    status_filter = request.GET.get("status")
    if status_filter == "verified":
        vendors_qs = vendors_qs.filter(is_verified=True)
    elif status_filter == "unverified":
        vendors_qs = vendors_qs.filter(is_verified=False)

    return render(
        request,
        "super_admin/dashboard.html",
        {
            "vendors": vendors_qs,
            "stats": stats,
            "q": q,
            "status_filter": status_filter or "all",
        },
    )


@_require_superuser
def vendor_detail(request, vendor_id):
    """Detailed view: vendor info + hotels + charges."""
    vendor = get_object_or_404(
        hotel_vendor.objects.select_related("user"),
        pk=vendor_id,
    )
    vendor_hotels = hotels.objects.filter(hotel_owner=vendor).annotate(
        n_rooms=Count("rooms", distinct=True), n_bookings=Count("rooms__bookings", distinct=True)
    )
    charges = vendor.charges.select_related("hotel").all()
    totals = {
        "outstanding": charges.filter(status=VendorCharge.Status.PENDING).aggregate(
            s=Sum("amount")
        )["s"]
        or 0,
        "paid": charges.filter(status=VendorCharge.Status.PAID).aggregate(s=Sum("amount"))["s"]
        or 0,
        "waived": charges.filter(status=VendorCharge.Status.WAIVED).aggregate(s=Sum("amount"))["s"]
        or 0,
    }

    return render(
        request,
        "super_admin/vendor_detail.html",
        {
            "vendor": vendor,
            "vendor_hotels": vendor_hotels,
            "charges": charges,
            "totals": totals,
        },
    )


@_require_superuser
@require_POST
def toggle_verified(request, vendor_id):
    vendor = get_object_or_404(hotel_vendor, pk=vendor_id)
    vendor.is_verified = not vendor.is_verified
    vendor.save(update_fields=["is_verified"])
    word = "verified" if vendor.is_verified else "unverified"
    messages.success(request, f"{vendor.business_name} marked {word}.")
    return redirect("super_vendor_detail", vendor_id=vendor.id)


@_require_superuser
@require_POST
def create_charge(request, vendor_id):
    """Add a new charge against a vendor (publishing fee, boost, etc.)."""
    vendor = get_object_or_404(hotel_vendor, pk=vendor_id)
    try:
        amount = Decimal(request.POST.get("amount", "0"))
    except InvalidOperation:
        messages.error(request, "Invalid amount.")
        return redirect("super_vendor_detail", vendor_id=vendor.id)
    if amount <= 0:
        messages.error(request, "Amount must be positive.")
        return redirect("super_vendor_detail", vendor_id=vendor.id)

    kind = request.POST.get("kind", VendorCharge.Kind.PUBLISH)
    description = (request.POST.get("description") or "").strip()[:200]
    hotel_id = request.POST.get("hotel_id") or None
    hotel_obj = None
    if hotel_id:
        hotel_obj = hotels.objects.filter(pk=hotel_id, hotel_owner=vendor).first()

    # Optional due date — if omitted, defaults to the end of the current month
    # for SUBSCRIPTION-type charges (typical monthly billing pattern), else 30d out.
    import calendar
    from datetime import date, timedelta

    due_raw = (request.POST.get("due_date") or "").strip()
    due_date = None
    if due_raw:
        try:
            due_date = date.fromisoformat(due_raw)
        except ValueError:
            messages.error(request, "Invalid due date.")
            return redirect("super_vendor_detail", vendor_id=vendor.id)
    else:
        today = date.today()
        if kind == VendorCharge.Kind.SUBSCRIPTION:
            last_day = calendar.monthrange(today.year, today.month)[1]
            due_date = date(today.year, today.month, last_day)
        else:
            due_date = today + timedelta(days=30)

    try:
        grace_days = int(request.POST.get("grace_days") or 15)
        if grace_days < 0 or grace_days > 180:
            raise ValueError
    except ValueError:
        messages.error(request, "Grace days must be between 0 and 180.")
        return redirect("super_vendor_detail", vendor_id=vendor.id)

    VendorCharge.objects.create(
        vendor=vendor,
        hotel=hotel_obj,
        kind=kind,
        amount=amount,
        description=description,
        due_date=due_date,
        grace_days=grace_days,
        notes=(request.POST.get("notes") or "").strip()[:500],
    )
    messages.success(
        request,
        f"Charge of ₹{amount} added for {vendor.business_name} — due {due_date.strftime('%d %b %Y')}.",
    )
    return redirect("super_vendor_detail", vendor_id=vendor.id)


@_require_superuser
def edit_charge(request, charge_id):
    charge = get_object_or_404(
        VendorCharge.objects.select_related("vendor"),
        pk=charge_id,
    )
    vendor = charge.vendor
    if charge.status != VendorCharge.Status.PENDING:
        messages.error(
            request,
            "This charge is no longer pending and can't be edited. Delete it and create a new one if needed.",
        )
        return redirect("super_vendor_detail", vendor_id=vendor.id)

    vendor_hotels = hotels.objects.filter(hotel_owner=vendor)

    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except InvalidOperation:
            messages.error(request, "Invalid amount.")
            return redirect("super_edit_charge", charge_id=charge.id)
        if amount <= 0:
            messages.error(request, "Amount must be positive.")
            return redirect("super_edit_charge", charge_id=charge.id)

        from datetime import date as _date

        due_raw = (request.POST.get("due_date") or "").strip()
        new_due = None
        if due_raw:
            try:
                new_due = _date.fromisoformat(due_raw)
            except ValueError:
                messages.error(request, "Invalid due date.")
                return redirect("super_edit_charge", charge_id=charge.id)

        try:
            grace_days = int(request.POST.get("grace_days") or 15)
            if grace_days < 0 or grace_days > 180:
                raise ValueError
        except ValueError:
            messages.error(request, "Grace days must be between 0 and 180.")
            return redirect("super_edit_charge", charge_id=charge.id)

        hotel_id = request.POST.get("hotel_id") or None
        new_hotel = None
        if hotel_id:
            new_hotel = vendor_hotels.filter(pk=hotel_id).first()

        charge.amount = amount
        charge.kind = request.POST.get("kind", charge.kind)
        charge.description = (request.POST.get("description") or "").strip()[:200]
        charge.hotel = new_hotel
        charge.due_date = new_due
        charge.grace_days = grace_days
        charge.notes = (request.POST.get("notes") or "").strip()[:500]
        charge.save()

        messages.success(request, f"Charge updated — now ₹{charge.amount}.")
        return redirect("super_vendor_detail", vendor_id=vendor.id)

    return render(
        request,
        "super_admin/charge_edit.html",
        {
            "charge": charge,
            "vendor": vendor,
            "vendor_hotels": vendor_hotels,
        },
    )


@_require_superuser
@require_POST
def update_charge_status(request, charge_id, action):
    """action ∈ {'paid', 'waived', 'delete'}."""
    charge = get_object_or_404(VendorCharge.objects.select_related("vendor"), pk=charge_id)
    vendor_id = charge.vendor_id

    if action == "paid":
        charge.mark_paid()
        messages.success(request, f"Charge ₹{charge.amount} marked PAID.")
    elif action == "waived":
        charge.mark_waived()
        messages.success(request, f"Charge ₹{charge.amount} marked WAIVED.")
    elif action == "delete":
        amt = charge.amount
        charge.delete()
        messages.warning(request, f"Charge ₹{amt} deleted.")
    else:
        messages.error(request, "Unknown action.")
    return redirect("super_vendor_detail", vendor_id=vendor_id)
