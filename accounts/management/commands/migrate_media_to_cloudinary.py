"""Bulk-upload everything in MEDIA_ROOT to the configured Cloudinary cloud.

WHY a separate command:
    Django's ``default_storage`` switches to Cloudinary when
    ``CLOUDINARY_CLOUD_NAME`` is set, but that only affects NEW uploads. Files
    already sitting at ``./media/hotels/foo.jpg`` on the developer's laptop
    must be copied to Cloudinary once, otherwise the production site will
    show broken images for every existing Hotel.image / Vendor.profile_image.

WHAT this does:
    1. Walks ``MEDIA_ROOT`` recursively.
    2. For each file, computes the storage key by stripping ``MEDIA_ROOT``
       from the path — so ``./media/hotels/foo.jpg`` → ``hotels/foo.jpg``.
       That matches the key stored in the FileField column, so no DB rows
       need to change after the upload.
    3. Skips files that already exist in Cloudinary unless ``--force`` is
       passed (idempotent — safe to re-run).

USAGE:
    # First time — uploads everything:
    python manage.py migrate_media_to_cloudinary

    # Force re-upload (e.g. you compressed local images and want Cloudinary
    # to mirror the new versions):
    python manage.py migrate_media_to_cloudinary --force

    # Preview only:
    python manage.py migrate_media_to_cloudinary --dry-run

PRECONDITIONS:
    - .env / Render env has CLOUDINARY_CLOUD_NAME / API_KEY / API_SECRET set.
    - ``django-cloudinary-storage`` + ``cloudinary`` installed (requirements.txt).
    - settings.py auto-flips DEFAULT_FILE_STORAGE to the Cloudinary backend
      when CLOUDINARY_CLOUD_NAME is set, so this command relies on
      ``default_storage`` already pointing at Cloudinary by the time it runs.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Upload every file under MEDIA_ROOT to the configured Cloudinary cloud."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-upload files that already exist in Cloudinary (default: skip).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be uploaded without actually uploading.",
        )

    def handle(self, *args, **opts):
        # Belt-and-suspenders: refuse to run when Cloudinary isn't configured.
        # Otherwise default_storage would be FileSystemStorage and we'd
        # "upload" files to themselves on disk — silent and confusing.
        if not getattr(settings, "CLOUDINARY_CLOUD_NAME", ""):
            raise CommandError(
                "CLOUDINARY_CLOUD_NAME is not set. This command only makes "
                "sense when cloud storage is configured. Set CLOUDINARY_* "
                "vars in .env first."
            )

        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"MEDIA_ROOT does not exist: {media_root}. Nothing to upload."
                )
            )
            return

        force = opts["force"]
        dry_run = opts["dry_run"]

        files: list[Path] = [p for p in media_root.rglob("*") if p.is_file()]
        if not files:
            self.stdout.write(
                self.style.WARNING(f"No files under {media_root}. Nothing to do.")
            )
            return

        self.stdout.write(
            f"Found {len(files)} file(s) under {media_root}. "
            f"Target cloud: {settings.CLOUDINARY_CLOUD_NAME}"
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN — no uploads will happen."))

        uploaded = 0
        skipped = 0
        failed = 0

        for path in files:
            # Storage key relative to MEDIA_ROOT. This matches what Django
            # stored in the FileField column when the file was first uploaded
            # via the local FileSystemStorage backend — so post-migration,
            # every existing DB row's `.url` resolves to a Cloudinary URL
            # without any SQL update.
            key = str(path.relative_to(media_root))

            try:
                if default_storage.exists(key) and not force:
                    self.stdout.write(f"  skip   {key}  (already in Cloudinary)")
                    skipped += 1
                    continue

                if dry_run:
                    self.stdout.write(f"  would  {key}")
                    continue

                with path.open("rb") as fh:
                    saved_as = default_storage.save(key, fh)
                self.stdout.write(self.style.SUCCESS(f"  upload {saved_as}"))
                uploaded += 1

            except Exception as exc:
                # Don't let one bad file kill the run. Operator can fix the
                # underlying issue and re-run with --force later.
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"  fail   {key}: {exc.__class__.__name__}: {exc}")
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. uploaded={uploaded}  skipped={skipped}  failed={failed}"
            )
        )
