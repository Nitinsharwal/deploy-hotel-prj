"""Template context processors registered globally in settings.TEMPLATES.

Anything returned here is automatically available in EVERY template render
that includes a RequestContext (which is the default for ``render()``).
Keep entries cheap — they run on every request, including 404s.
"""

from __future__ import annotations


def chatbot_context(request):
    """Inject ``hb_ctx`` for the floating support chat widget.

    Why a context processor and not per-view code:
        The chatbot widget is included from base.html, so it loads on
        every page. Threading {email, booking_ref} through every view
        that renders a base-extending template would mean editing 40+
        views — and adding a brand new view would need the same setup.
        A context processor handles all current and future pages
        automatically.

    What ``hb_ctx`` contains:
        - ``email``: the logged-in user's email, or "" for anonymous
        - ``booking_ref``: reference of their most-recent booking, or
          "" if they have none yet

    Performance note:
        For anonymous users we short-circuit before any DB query. For
        authed users we hit the Booking table with a single indexed
        ``.order_by("-pk").first()``. Cheap on small tables (<100k rows);
        if Booking ever grows huge, consider caching by user-id with a
        short TTL.

    Failure mode:
        If anything throws (DB unreachable, Booking model not imported
        yet during a migration, etc.) we return empty values rather
        than blowing up the page render. The chat widget gracefully
        degrades — it just won't auto-fill the latest booking.
    """
    ctx = {"email": "", "booking_ref": ""}

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"hb_ctx": ctx}

    ctx["email"] = user.email or ""

    try:
        # Import lazily to avoid a circular import (accounts.models imports
        # User which can trigger app-loading issues if this module is
        # imported too early in startup).
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
        # Don't break the page over a chat widget convenience.
        pass

    return {"hb_ctx": ctx}
