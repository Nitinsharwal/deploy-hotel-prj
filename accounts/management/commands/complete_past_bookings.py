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

        qs.update(status=Booking.Status.COMPLETED, updated_at=timezone.now())
        msg = f"Marked {count} booking(s) as COMPLETED."
        self.stdout.write(self.style.SUCCESS(msg))
        logger.info(msg)
