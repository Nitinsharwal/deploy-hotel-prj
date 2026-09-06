import uuid
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import User


class AutoConnectByEmailAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            return

        email = (sociallogin.account.extra_data or {}).get("email")
        email_verified = (sociallogin.account.extra_data or {}).get("email_verified", False)
        if not email or not email_verified:
            return

        existing = (
            User.objects.filter(email__iexact=email).first()
            or User.objects.filter(username__iexact=email).first()
        )
        if existing is None:
            return

        if not existing.username:
            existing.username = existing.email.lower() or f"user-{existing.pk}-{uuid.uuid4().hex[:6]}"
            existing.save(update_fields=["username"])

        sociallogin.connect(request, existing)

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        if not user.username:
            email = (data.get("email") or "").lower()
            user.username = email or f"user-{uuid.uuid4().hex[:10]}"
        if User.objects.filter(username=user.username).exclude(pk=user.pk).exists():
            user.username = f"{user.username[:140]}-{uuid.uuid4().hex[:6]}"
        return user
