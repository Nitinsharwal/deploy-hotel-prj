from django.contrib.auth.models import User
from django.db import models


class hotel_owner(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="owner_profile")
    profile_pic = models.ImageField(upload_to="profile", null=True, blank=True)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)  # noqa: DJ001
    email_token = models.CharField(max_length=100, null=True, blank=True)  # noqa: DJ001
    otp = models.CharField(max_length=128, null=True, blank=True)  # noqa: DJ001  stores hashed OTP
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username


class hotel_vendor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="vendor_profile")
    business_name = models.CharField(max_length=191)
    profile_pic = models.ImageField(upload_to="profile", null=True, blank=True)
    phone_number = models.CharField(max_length=20, unique=True)
    email_token = models.CharField(max_length=100, null=True, blank=True)  # noqa: DJ001
    otp = models.CharField(max_length=128, null=True, blank=True)  # noqa: DJ001  hashed OTP
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.business_name

    @property
    def has_overdue_charges(self):
        """True if any pending charge is past (due_date + grace_days).
        When True, public hotel listings hide this vendor's hotels.
        """
        return any(c.is_overdue for c in self.charges.filter(status="pending"))

    def overdue_charges(self):
        return [c for c in self.charges.filter(status="pending") if c.is_overdue]


class amenities(models.Model):
    amenities_name = models.CharField(max_length=191)
    icon = models.ImageField(upload_to="hotels")

    def __str__(self):
        return self.amenities_name


class hotels(models.Model):
    hotel_name = models.CharField(max_length=191, db_index=True)
    hotel_description = models.TextField()
    hotel_slug = models.SlugField(max_length=191, unique=True)  # unique already indexed
    hotel_owner = models.ForeignKey(hotel_vendor, on_delete=models.CASCADE, related_name="hotels")
    hotel_amenities = models.ManyToManyField(amenities)
    hotel_price = models.FloatField()
    hotel_offer_price = models.FloatField()
    hotel_location = models.TextField()
    is_active = models.BooleanField(default=True, db_index=True)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.hotel_name

    def recompute_rating(self):
        from django.db.models import Avg, Count

        agg = self.reviews.aggregate(avg=Avg("score"), n=Count("id"))
        self.rating_avg = round(agg["avg"] or 0, 2)
        self.rating_count = agg["n"] or 0
        self.save(update_fields=["rating_avg", "rating_count"])


class hotel_images(models.Model):
    hotel = models.ForeignKey(hotels, on_delete=models.CASCADE, related_name="hotel_images")
    image = models.ImageField(upload_to="hotels")

    def __str__(self):
        # Shows up in admin "Hotel images" list — gives each row a useful label
        # instead of "hotel_images object (12)".
        return f"{self.hotel.hotel_name} — image #{self.pk}"


class hotel_manager(models.Model):
    hotel = models.ForeignKey(hotels, on_delete=models.CASCADE, related_name="hotel_managers")
    manager_name = models.CharField(max_length=100)
    manager_contact = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.manager_name} ({self.hotel.hotel_name})"

class Room(models.Model):
    class RoomType(models.TextChoices):
        STANDARD = "standard", "Standard"
        DELUXE = "deluxe", "Deluxe"
        SUITE = "suite", "Suite"
        FAMILY = "family", "Family"

    hotel = models.ForeignKey(hotels, on_delete=models.CASCADE, related_name="rooms")
    room_type = models.CharField(max_length=20, choices=RoomType.choices, default=RoomType.STANDARD)
    name = models.CharField(max_length=100, help_text="Display name, e.g. 'Sea-view Deluxe'")
    capacity = models.PositiveSmallIntegerField(default=2)
    total_count = models.PositiveSmallIntegerField(
        default=1, help_text="How many of this room exist"
    )
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["hotel", "base_price"]

    def __str__(self):
        return f"{self.hotel.hotel_name} — {self.name}"

    def booked_count(self, start_date, end_date, exclude_booking_id=None):
        """Number of overlapping non-cancelled bookings on this room type."""
        qs = self.bookings.filter(
            start_date__lt=end_date,
            end_date__gt=start_date,
        ).exclude(status=Booking.Status.CANCELLED)
        if exclude_booking_id:
            qs = qs.exclude(pk=exclude_booking_id)
        return qs.count()

    def is_available(self, start_date, end_date, exclude_booking_id=None):
        return self.booked_count(start_date, end_date, exclude_booking_id) < self.total_count


class Booking(models.Model):
    """A booking lifecycle record. Replaces the legacy `customers` model."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending payment"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    reference = models.CharField(max_length=12, unique=True, db_index=True)
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="bookings")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
        help_text="Set when an authenticated user books. Guest bookings leave this null.",
    )
    guest_first_name = models.CharField(max_length=100)
    guest_last_name = models.CharField(max_length=100)
    guest_email = models.EmailField(max_length=191, db_index=True)
    guest_phone = models.CharField(max_length=20, blank=True)

    start_date = models.DateField()
    end_date = models.DateField()
    num_guests = models.PositiveSmallIntegerField(default=1)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["room", "start_date", "end_date"], name="booking_room_dates_idx"),
            models.Index(fields=["status", "start_date"], name="booking_status_start_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                # Django 4.2 uses `check=` (renamed to `condition=` in 5.1+).
                check=models.Q(end_date__gt=models.F("start_date")),
                name="booking_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.reference} ({self.get_status_display()})"

    @property
    def nights(self):
        return (self.end_date - self.start_date).days

    @property
    def is_cancellable(self):
        from django.utils import timezone

        if self.status in (self.Status.CANCELLED, self.Status.COMPLETED):
            return False
        return self.start_date > timezone.now().date()

    def cancel(self, reason=""):
        from django.utils import timezone

        if not self.is_cancellable:
            raise ValueError("Booking is not cancellable in its current state.")
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        self.save(update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"])


class Payment(models.Model):
    """A payment attempt or completion against a Booking.

    Why separate from Booking: a booking can have multiple payment attempts
    (failed cards, partial refunds). We need an audit trail per attempt with
    the gateway's raw response retained for dispute resolution.
    """

    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    class Method(models.TextChoices):
        CARD = "card", "Card"
        UPI = "upi", "UPI"
        NETBANKING = "netbanking", "Net banking"
        WALLET = "wallet", "Wallet"
        CASH = "cash", "Cash / on arrival"

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CARD)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INITIATED,
        db_index=True,
    )
    # Gateway reference (Stripe payment_intent id, Razorpay order id, etc.)
    transaction_id = models.CharField(max_length=128, blank=True, db_index=True)
    gateway_response = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.pk} for {self.booking.reference} ({self.status})"


class Review(models.Model):
    """A guest review of a hotel. Tied to a completed Booking to prevent
    fake/spam reviews from people who never stayed.
    """

    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="review",
    )
    hotel = models.ForeignKey(hotels, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    score = models.PositiveSmallIntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
    )
    title = models.CharField(max_length=120, blank=True)
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(score__gte=1) & models.Q(score__lte=5),
                name="review_score_1_to_5",
            ),
        ]

    def __str__(self):
        return f"{self.score}★ — {self.hotel.hotel_name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.hotel.recompute_rating()

    def delete(self, *args, **kwargs):
        hotel = self.hotel
        super().delete(*args, **kwargs)
        hotel.recompute_rating()


class VendorCharge(models.Model):
    """A platform fee billed to a vendor — e.g. publishing fee, listing
    boost, monthly subscription. Only the superuser creates/manages these
    via /super-admin/.

    Why a dedicated model (rather than a flag on `hotels.is_active`):
    - One vendor can have many charges over time (audit trail).
    - Charges may or may not be tied to a single hotel (account-wide fees).
    - Different statuses (pending / paid / waived) need their own lifecycle.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        WAIVED = "waived", "Waived"

    class Kind(models.TextChoices):
        PUBLISH = "publish", "Hotel publishing fee"
        BOOST = "boost", "Listing boost"
        SUBSCRIPTION = "subscription", "Monthly subscription"
        OTHER = "other", "Other"

    vendor = models.ForeignKey(
        hotel_vendor,
        on_delete=models.CASCADE,
        related_name="charges",
    )
    hotel = models.ForeignKey(
        hotels,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_charges",
        help_text="Optional — set when the charge is for a specific hotel.",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PUBLISH)
    description = models.CharField(max_length=200, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    # When the vendor must pay by. We send reminders starting 5 days before
    # this date and keep nagging through (due_date + grace_days). After that
    # the vendor's hotels disappear from public listings until they pay.
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text="Pay-by date. Reminders start 5 days before; after grace expires, hotels are hidden.",
    )
    grace_days = models.PositiveSmallIntegerField(
        default=15,
        help_text="Days of grace after due_date before hotels get hidden.",
    )
    last_reminded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Updated by the daily reminder command so we don't email twice in 24h.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="Internal notes (admin only).")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["vendor", "status"], name="vc_vendor_status_idx"),
            models.Index(fields=["status", "due_date"], name="vc_status_due_idx"),
        ]

    def __str__(self):
        return f"{self.vendor.business_name} — ₹{self.amount} ({self.get_status_display()})"

    # ---- date/period helpers ----------------------------------------
    @property
    def effective_due_date(self):
        """When the grace period actually ends. Returns None if no due_date set."""
        from datetime import timedelta

        if self.due_date is None:
            return None
        return self.due_date + timedelta(days=self.grace_days)

    @property
    def is_overdue(self):
        """Pending and past the grace period — vendor's hotels should be hidden."""
        from django.utils import timezone

        if self.status != self.Status.PENDING or self.effective_due_date is None:
            return False
        return timezone.now().date() > self.effective_due_date

    @property
    def is_in_reminder_window(self):
        """True if we should be emailing the vendor about this charge today.

        Window: (due_date − 5d) … (due_date + grace_days). Only for pending.
        """
        from datetime import timedelta

        from django.utils import timezone

        if self.status != self.Status.PENDING or self.due_date is None:
            return False
        today = timezone.now().date()
        return (self.due_date - timedelta(days=5)) <= today <= self.effective_due_date

    @property
    def days_until_due(self):
        """Negative once overdue. None when no due_date set."""
        from django.utils import timezone

        if self.due_date is None:
            return None
        return (self.due_date - timezone.now().date()).days

    # ---- status transitions -----------------------------------------
    def mark_paid(self):
        from django.utils import timezone

        self.status = self.Status.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "paid_at"])

    def mark_waived(self):
        self.status = self.Status.WAIVED
        self.save(update_fields=["status"])


class ContactMessage(models.Model):
    """A submission from the public Contact Us page.

    Why store these in the DB (not just email):
    - Email delivery sometimes fails — we lose nothing if a row exists.
    - Admins can triage in /admin/ and mark resolved.
    - Tracks volume / spam patterns over time.

    `user` is set when the submitter was logged in, so we can show their
    history on the profile page later if we want.
    """

    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"
        SPAM = "spam", "Spam"

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    email = models.EmailField(max_length=191, db_index=True)
    subject = models.CharField(max_length=120, blank=True)
    message = models.TextField()

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_messages",
        help_text="Set when the submitter was logged in.",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    internal_notes = models.TextField(blank=True, help_text="Admin-only.")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name or ''} — {self.subject or '(no subject)'}"


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    otp_hash = models.CharField(max_length=128)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "used_at"])]

    def __str__(self):
        return f"Reset for {self.user.email} (expires {self.expires_at:%Y-%m-%d %H:%M})"

    def is_valid(self):
        from django.utils import timezone

        return self.used_at is None and self.expires_at > timezone.now()

    def mark_used(self):
        from django.utils import timezone

        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])
