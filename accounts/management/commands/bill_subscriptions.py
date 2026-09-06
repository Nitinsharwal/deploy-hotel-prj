from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Plan, VendorCharge, VendorSubscription


class Command(BaseCommand):
    help = "Roll subscriptions whose period_end has passed; issue invoices or downgrade as needed."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opts):
        dry_run = opts["dry_run"]
        today = timezone.localdate()
        free_plan = Plan.objects.filter(slug=Plan.SLUG_FREE, is_active=True).first()

        due = VendorSubscription.objects.select_related("plan", "vendor").filter(
            status__in=[VendorSubscription.Status.ACTIVE, VendorSubscription.Status.CANCELLED],
            period_end__lt=today,
        )

        renewed = downgraded = invoiced = 0

        for sub in due:
            vendor = sub.vendor
            old_plan = sub.plan

            if sub.status == VendorSubscription.Status.CANCELLED:
                self.stdout.write(f"  downgrade  {vendor.business_name} ({old_plan.slug} → free)")
                if not dry_run:
                    sub.status = VendorSubscription.Status.EXPIRED
                    sub.save(update_fields=["status", "updated_at"])
                    if free_plan:
                        VendorSubscription.objects.create(
                            vendor=vendor,
                            plan=free_plan,
                            status=VendorSubscription.Status.ACTIVE,
                            period_start=today,
                            period_end=today + timedelta(days=30),
                        )
                downgraded += 1
                continue

            new_start = sub.period_end + timedelta(days=1)
            new_end = new_start + timedelta(days=30)
            self.stdout.write(
                f"  renew      {vendor.business_name} ({old_plan.slug}): "
                f"{new_start} → {new_end}"
            )
            if not dry_run:
                sub.status = VendorSubscription.Status.EXPIRED
                sub.save(update_fields=["status", "updated_at"])
                VendorSubscription.objects.create(
                    vendor=vendor,
                    plan=old_plan,
                    status=VendorSubscription.Status.ACTIVE,
                    period_start=new_start,
                    period_end=new_end,
                )
                if old_plan.price_monthly_inr > 0:
                    VendorCharge.objects.create(
                        vendor=vendor,
                        kind=VendorCharge.Kind.SUBSCRIPTION,
                        amount=old_plan.price_monthly_inr,
                        description=f"{old_plan.name} plan — {new_start} to {new_end}",
                        due_date=new_start + timedelta(days=7),
                        grace_days=14,
                        status=VendorCharge.Status.PENDING,
                    )
                    invoiced += 1
            renewed += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. renewed={renewed} downgraded={downgraded} invoiced={invoiced}"
                f"{' (DRY RUN)' if dry_run else ''}"
            )
        )
