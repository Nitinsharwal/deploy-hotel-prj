"""
Daily housekeeping: advance CONFIRMED bookings whose check-out has passed to COMPLETED.

Why a management command vs. a signal/cron-in-app:
- Idempotent and safe to re-run; just an UPDATE with a date guard.
- Easy to schedule from anywhere: system cron, Render cron job, GitHub Actions,
  django-q/celery beat — without coupling app code to a scheduler.
- Logs how many rows it touched so monitoring can alert on anomalies.

Typical schedule: once per day, just after midnight in your business timezone.
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Booking

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Mark CONFIRMED bookings as COMPLETED once their check-out date is in the past."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the count that would be updated, but make no changes.",
        )

    def handle(self, *args, **options):
        today = timezone.now().date()
        qs = Booking.objects.filter(
            status=Booking.Status.CONFIRMED,
            end_date__lte=today,
        )
        count = qs.count()

        if options["dry_run"]:
            self.stdout.write(f"[dry-run] Would mark {count} booking(s) as COMPLETED.")
            return

        if count == 0:
            self.stdout.write("Nothing to do — no past CONFIRMED bookings.")
            return

        # update() bypasses save() and signals; that's fine here because we
        # don't have any post-save logic on Booking that needs to fire.
        qs.update(status=Booking.Status.COMPLETED, updated_at=timezone.now())
        msg = f"Marked {count} booking(s) as COMPLETED."
        self.stdout.write(self.style.SUCCESS(msg))
        logger.info(msg)
