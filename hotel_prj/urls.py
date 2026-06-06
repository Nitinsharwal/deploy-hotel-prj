"""
URL configuration for hotel_prj project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from django.views.static import serve

from hotel_app.sitemaps import HotelSitemap, StaticViewSitemap

sitemaps = {
    "static": StaticViewSitemap,
    "hotels": HotelSitemap,
}

urlpatterns = [
    # Django's built-in admin — gated by is_staff. Not linked from anywhere in
    # the public UI. Keep it for the data-level fallback (running migrations
    # diffs, raw object editing). Use /super-admin/ for everyday work.
    path("admin/", admin.site.urls),
    # Branded super-admin UI. Returns 404 to non-superusers — the URL itself
    # is invisible to anyone snooping. Implemented in accounts/super_admin.py.
    path("super-admin/", include("accounts.super_admin_urls")),
    # SEO discovery — sitemap is auto-built from sitemaps.py, robots is a
    # static template rendered with SITE_URL so the absolute URL is correct.
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="robots.txt",
            content_type="text/plain",
            # robots.txt is served by a static TemplateView — no per-request
            # render — so we can't auto-detect the host. Fall back to the
            # helper's env-var path (SITE_URL → ALLOWED_HOSTS → localhost).
            # Cron-equivalent: same logic as email reminders without a request.
            extra_context={
                "site_url": __import__("accounts.utils", fromlist=["get_site_url"]).get_site_url()
            },
        ),
        name="robots",
    ),
    path("account/", include("accounts.urls")),
    # allauth lives under /accounts/ (plural) — distinct from our /account/ (singular).
    # Google login URL: /accounts/google/login/
    path("accounts/", include("allauth.urls")),
    path("", include("hotel_app.urls")),
]

# Static & media
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# Serve media even when DEBUG is False (e.g., on simple hosts without a file server)
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]

# Branded error pages. Django uses these handlers when DEBUG=False.
# They live in hotel_app/templates/ and inherit base.html (except 500.html,
# which is intentionally standalone so it still renders if base is broken).
handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"
handler403 = "django.views.defaults.permission_denied"
