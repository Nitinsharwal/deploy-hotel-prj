import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import VendorCharge
from accounts.utils import sendChargeReminder

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Email vendors about pending platform charges in the reminder window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show who would be emailed without actually sending.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Send even if a reminder was already sent today.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        today = now.date()
        sent = 0
        skipped_already_sent = 0
        skipped_outside_window = 0

        qs = VendorCharge.objects.filter(status=VendorCharge.Status.PENDING).select_related(
            "vendor", "vendor__user"
        )
        for charge in qs:
            if not charge.is_in_reminder_window:
                skipped_outside_window += 1
                continue
            if (
                not options["force"]
                and charge.last_reminded_at
                and charge.last_reminded_at.date() == today
            ):
                skipped_already_sent += 1
                continue

            if options["dry_run"]:
                self.stdout.write(
                    f"[dry-run] would email {charge.vendor.user.email} "
                    f"about ₹{charge.amount} due {charge.due_date}"
                )
                sent += 1
                continue

            ok = sendChargeReminder(charge)
            if ok:
                charge.last_reminded_at = now
                charge.save(update_fields=["last_reminded_at"])
                sent += 1
            else:
                logger.warning("Reminder email failed for charge %s", charge.id)

        verb = "Would email" if options["dry_run"] else "Emailed"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {sent} vendor(s). "
                f"Skipped: {skipped_already_sent} already-sent today, "
                f"{skipped_outside_window} outside reminder window."
            )
        )
