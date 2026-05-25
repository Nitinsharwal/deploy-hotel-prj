"""
Custom allauth SocialAccountAdapter.

Why we need this:
- `SOCIALACCOUNT_EMAIL_AUTHENTICATION` only links to users that have a
  verified `account_emailaddress` row managed by allauth.
- Users registered via our own `register_page` view (created with
  `User.objects.create_user(...)`) do NOT have that row, so the auto-link
  silently fails and allauth shows its "/accounts/3rdparty/signup/" form.
- This adapter closes that gap: on every social login it checks for an
  existing User with the same email and connects (links) the social account
  to it, treating the Google-verified email as trustworthy.

Trust model: Google's `email_verified` claim is included in the OAuth ID
token. We require it before auto-linking — if Google did NOT verify the
email, we let allauth's default flow run (which will show the signup form
or fail safely), so an attacker can't hijack someone else's account by
claiming an unverified email on a malicious provider.
"""

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import User


class AutoConnectByEmailAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        # Already linked to a local user — nothing to do.
        if sociallogin.is_existing:
            return

        email = (sociallogin.account.extra_data or {}).get("email")
        email_verified = (sociallogin.account.extra_data or {}).get("email_verified", False)
        if not email or not email_verified:
            return

        # Find an existing User. We match by email field OR username (we use
        # email as username in our register flow).
        existing = (
            User.objects.filter(email__iexact=email).first()
            or User.objects.filter(username__iexact=email).first()
        )
        if existing is None:
            return  # let allauth create a new user via the normal auto-signup path

        # Attach the social account to the existing user. allauth handles the
        # rest (logging them in with the right session / backend).
        sociallogin.connect(request, existing)
