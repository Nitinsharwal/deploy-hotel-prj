"""
Tiny middlewares for production polish.

`MediaCacheMiddleware` stamps long-lived `Cache-Control` headers on any
response served from `/media/`. Browsers + any CDN in front (Cloudflare,
CloudFront, Bunny) will cache the response at the edge, so hotel photos
load instantly on repeat views and don't hit your Django process again.

Why a middleware (not a view): media is served via Django's `django.views.
static.serve` in dev and via WhiteNoise/CDN in prod. Both go through this
middleware, so the header logic lives in one place.
"""

from django.conf import settings


class MediaCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.media_prefix = getattr(settings, "MEDIA_URL", "/media/")
        self.max_age = getattr(settings, "MEDIA_CACHE_MAX_AGE", 86400)

    def __call__(self, request):
        response = self.get_response(request)
        # Only touch successful GET responses under /media/.
        if (
            request.method == "GET"
            and request.path.startswith(self.media_prefix)
            and 200 <= response.status_code < 400
            and "Cache-Control" not in response  # respect anything already set
        ):
            response["Cache-Control"] = f"public, max-age={self.max_age}, immutable"
            # Hint to CDNs that this is safe to cache by URL alone.
            response.setdefault("Vary", "Accept-Encoding")
        return response
