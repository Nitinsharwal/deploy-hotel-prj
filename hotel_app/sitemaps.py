from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from accounts.models import hotels

class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = "weekly"

    def items(self):
        return ["home", "about", "contact"]

    def location(self, name):
        return reverse(name)


class HotelSitemap(Sitemap):
    priority = 0.8
    changefreq = "monthly"

    def items(self):
        return hotels.objects.filter(is_active=True).only("hotel_slug")

    def location(self, obj):
        return reverse("hotel_details", args=[obj.hotel_slug])
