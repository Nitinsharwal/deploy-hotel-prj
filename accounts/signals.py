import logging

from allauth.account.signals import user_signed_up
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Review, VendorCharge, hotel_images, hotel_owner, hotels

logger = logging.getLogger(__name__)


@receiver(post_save, sender=hotel_images)
def resize_hotel_image(sender, instance, created, **kwargs):
    """Downsize newly uploaded hotel photos to keep page weight reasonable.

    A 2 MB phone photo is overkill for a 4:3 listing card. We cap at 1920×1080
    and re-encode at JPEG quality=85 / PNG optimize. Original aspect ratio is
    preserved. Idempotent: if a re-save fires the signal again we no-op when
    the file is already under the cap.

    Failures don't raise — we just log and let the original through. Better
    a chunky image than a missing one.
    """
    if not created:
        return
    try:
        from PIL import Image

        path = instance.image.path
        with Image.open(path) as img:
            if img.height <= 1080 and img.width <= 1920:
                return
            img.thumbnail((1920, 1080))
            save_kwargs = {"optimize": True}
            if img.format in ("JPEG", "JPG"):
                save_kwargs["quality"] = 85
                save_kwargs["progressive"] = True
            img.save(path, **save_kwargs)
    except Exception:
        logger.exception("Failed to resize hotel image %s", getattr(instance, "id", "?"))


@receiver(user_signed_up)
def create_owner_profile_for_social_signup(sender, request, user, **kwargs):
    # Only act when the User came in via a social provider; plain email signups
    # go through our own register_page view which already creates the profile.
    sociallogin = kwargs.get("sociallogin")
    if sociallogin is None:
        return

    # Names from the OAuth payload — keeps the profile useful from day one.
    extra = sociallogin.account.extra_data or {}
    if not user.first_name and extra.get("given_name"):
        user.first_name = extra["given_name"]
    if not user.last_name and extra.get("family_name"):
        user.last_name = extra["family_name"]
    user.save(update_fields=["first_name", "last_name"])

    hotel_owner.objects.get_or_create(
        user=user,
        defaults={
            "phone_number": None,  # user can add it later from a profile page
            "is_verified": True,  # Google already verified the email
        },
    )


# ── Cache invalidation ────────────────────────────────────────────────────
# Short TTLs in hot_app.views (60s home grid, 5min blocked-vendor set) would
# eventually self-heal. But for actions a user just took (paid a charge,
# added a hotel, posted a review), waiting 60s feels broken. These signal
# handlers wipe the affected cache keys immediately so the next page render
# rebuilds from fresh data.
#
# The keys live in hot_app.views; we import them lazily inside each handler
# to avoid a circular import at module load time.


def _bust_blocked_vendor_cache():
    from hotel_app.views import CACHE_KEY_BLOCKED_VENDORS

    cache.delete(CACHE_KEY_BLOCKED_VENDORS)


def _bust_home_cache():
    """Wipe all home-page cache entries.

    With Redis we could use `cache.delete_pattern("home_hotels:*")` (the
    django-redis client supports it), but the stdlib backend doesn't. We
    use `cache.clear()` only on LocMem in tests; in prod with Redis we'd
    swap this for the pattern delete. For now we mark a version key and the
    home view's key includes it — simpler and backend-agnostic.
    """
    from hotel_app.views import CACHE_KEY_HOME_PREFIX

    # Bump a version counter; the home view incorporates this into its key.
    cur = cache.get(f"{CACHE_KEY_HOME_PREFIX}:version", 0)
    cache.set(f"{CACHE_KEY_HOME_PREFIX}:version", int(cur) + 1, None)


@receiver([post_save, post_delete], sender=VendorCharge)
def vendor_charge_changed(sender, instance, **kwargs):
    """Any charge save/delete could flip a vendor between blocked / unblocked."""
    _bust_blocked_vendor_cache()
    _bust_home_cache()


@receiver([post_save, post_delete], sender=hotels)
def hotel_changed(sender, instance, **kwargs):
    """New/edited hotel or is_active toggle — every filtered home list is stale."""
    _bust_home_cache()


@receiver([post_save, post_delete], sender=Review)
def review_changed(sender, instance, **kwargs):
    """Reviews bump rating_avg; ratings drive the default sort order."""
    _bust_home_cache()
