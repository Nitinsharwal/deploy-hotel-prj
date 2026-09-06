import logging

from allauth.account.signals import user_signed_up
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Review, VendorCharge, hotel_images, hotel_owner, hotels

logger = logging.getLogger(__name__)


@receiver(post_save, sender=hotel_images)
def resize_hotel_image(sender, instance, created, **kwargs):
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
    sociallogin = kwargs.get("sociallogin")
    if sociallogin is None:
        return

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

def _bust_blocked_vendor_cache():
    from hotel_app.views import CACHE_KEY_BLOCKED_VENDORS

    cache.delete(CACHE_KEY_BLOCKED_VENDORS)


def _bust_home_cache():
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
