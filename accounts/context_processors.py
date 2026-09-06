from __future__ import annotations


def chatbot_context(request):

    ctx = {"email": "", "booking_ref": ""}

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"hb_ctx": ctx}

    ctx["email"] = user.email or ""

    try:
        from .models import Booking

        latest = (
            Booking.objects.filter(user=user)
            .order_by("-pk")
            .values_list("reference", flat=True)
            .first()
        )
        if latest:
            ctx["booking_ref"] = latest
    except Exception:
        pass

    return {"hb_ctx": ctx}
