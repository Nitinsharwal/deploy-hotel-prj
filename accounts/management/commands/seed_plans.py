"""Idempotent seed for the Free / Pro / Enterprise plan rows."""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Plan


PLANS = [
    {
        "slug": Plan.SLUG_FREE,
        "name": "Free",
        "tagline": "Get listed in minutes",
        "description": "List one hotel, accept bookings, no monthly fee. Upgrade any time.",
        "price_monthly_inr": Decimal("0"),
        "max_hotels": 1,
        "max_rooms_per_hotel": 3,
        "max_images_per_hotel": 5,
        "has_analytics": False,
        "has_featured_listing": False,
        "has_api_access": False,
        "has_priority_support": False,
        "commission_percent": Decimal("10"),
        "sort_order": 1,
        "is_active": True,
        "is_default": True,
    },
    {
        "slug": Plan.SLUG_PRO,
        "name": "Pro",
        "tagline": "For growing properties",
        "description": "Up to 10 hotels. Unlimited rooms and images. Featured listings, analytics, lower commission.",
        "price_monthly_inr": Decimal("999"),
        "max_hotels": 10,
        "max_rooms_per_hotel": None,
        "max_images_per_hotel": None,
        "has_analytics": True,
        "has_featured_listing": True,
        "has_api_access": False,
        "has_priority_support": False,
        "commission_percent": Decimal("7"),
        "sort_order": 2,
        "is_active": True,
        "is_default": False,
    },
    {
        "slug": Plan.SLUG_ENTERPRISE,
        "name": "Enterprise",
        "tagline": "For hotel groups & chains",
        "description": "Unlimited everything. API access, priority support, lowest commission.",
        "price_monthly_inr": Decimal("4999"),
        "max_hotels": None,
        "max_rooms_per_hotel": None,
        "max_images_per_hotel": None,
        "has_analytics": True,
        "has_featured_listing": True,
        "has_api_access": True,
        "has_priority_support": True,
        "commission_percent": Decimal("3"),
        "sort_order": 3,
        "is_active": True,
        "is_default": False,
    },
]


class Command(BaseCommand):
    help = "Create or update the Free / Pro / Enterprise plans."

    @transaction.atomic
    def handle(self, *args, **opts):
        created = updated = 0
        for cfg in PLANS:
            slug = cfg["slug"]
            _, was_created = Plan.objects.update_or_create(
                slug=slug,
                defaults={k: v for k, v in cfg.items() if k != "slug"},
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  + {slug:12s} created"))
            else:
                updated += 1
                self.stdout.write(f"  ~ {slug:12s} updated")

        defaults_qs = Plan.objects.filter(is_default=True)
        if defaults_qs.count() > 1:
            keep = defaults_qs.filter(slug=Plan.SLUG_FREE).first() or defaults_qs.first()
            Plan.objects.exclude(pk=keep.pk).filter(is_default=True).update(is_default=False)
            self.stdout.write(self.style.WARNING(f"  fixed multiple is_default rows — kept {keep.slug}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Done. created={created} updated={updated}"))
