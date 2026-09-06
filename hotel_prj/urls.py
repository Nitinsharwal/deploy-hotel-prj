from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView
from django.views.static import serve


@never_cache
def healthz(_request):
    return HttpResponse("ok", content_type="text/plain")

from hotel_app.sitemaps import HotelSitemap, StaticViewSitemap

sitemaps = {
    "static": StaticViewSitemap,
    "hotels": HotelSitemap,
}

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("healtz", healthz),
    path("admin/", admin.site.urls),
    path("super-admin/", include("accounts.super_admin_urls")),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="robots.txt",
            content_type="text/plain",
            extra_context={
                "site_url": __import__("accounts.utils", fromlist=["get_site_url"]).get_site_url()
            },
        ),
        name="robots",
    ),
    path("account/", include("accounts.urls")),
    path("accounts/", include("allauth.urls")),
    path("", include("hotel_app.urls")),
]

# Static & media
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass

handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"
handler403 = "django.views.defaults.permission_denied"
