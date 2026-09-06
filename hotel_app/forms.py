import secrets
from datetime import date
from decimal import Decimal

from django import forms

from accounts.models import Booking, Review, Room


def _make_reference():
    return "NM-" + secrets.token_hex(4).upper()


class BookingForm(forms.ModelForm):
    room = forms.ModelChoiceField(queryset=Room.objects.none())
    payment_method = forms.ChoiceField(
        choices=[
            ("card", "Card"),
            ("upi", "UPI"),
            ("netbanking", "Net banking"),
            ("cash", "Cash / on arrival"),
        ],
        initial="card",
    )

    class Meta:
        model = Booking
        fields = [
            "guest_first_name",
            "guest_last_name",
            "guest_email",
            "guest_phone",
            "start_date",
            "end_date",
            "num_guests",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, hotel=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.hotel = hotel
        self.user = user
        if hotel is not None:
            self.fields["room"].queryset = hotel.rooms.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        room = cleaned.get("room")
        num_guests = cleaned.get("num_guests") or 1

        if start and end:
            if start < date.today():
                raise forms.ValidationError("Check-in date cannot be in the past.")
            if (end - start).days <= 0:
                raise forms.ValidationError("Check-out must be after check-in.")

        if room:
            if num_guests > room.capacity:
                raise forms.ValidationError(f"This room sleeps up to {room.capacity} guests.")
            if start and end and not room.is_available(start, end):
                raise forms.ValidationError(
                    "Sorry, this Room type is Already booked for the selected dates."
                )

        return cleaned

    def save(self, commit=True):
        booking = super().save(commit=False)
        booking.reference = _make_reference()
        booking.room = self.cleaned_data["room"]
        booking.user = self.user if (self.user and self.user.is_authenticated) else None
        nights = (booking.end_date - booking.start_date).days
        booking.total_amount = booking.room.base_price * Decimal(nights)
        booking.status = Booking.Status.PENDING  # becomes CONFIRMED once Payment.success arrives
        if commit:
            booking.save()
        return booking


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["score", "title", "body"]
        widgets = {
            "score": forms.Select(choices=[(i, f"{i} ★") for i in range(5, 0, -1)]),
            "body": forms.Textarea(attrs={"rows": 4, "placeholder": "What was your stay like?"}),
        }


class ContactForm(forms.ModelForm):
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"autocomplete": "off", "tabindex": "-1", "aria-hidden": "true"},
        ),
    )

    class Meta:
        from accounts.models import ContactMessage

        model = ContactMessage
        fields = ["first_name", "last_name", "email", "subject", "message"]
        widgets = {
            "message": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Tell us what's on your mind…"}
            ),
        }
        error_messages = {
            "email": {"required": "We need an email so we can reply."},
            "message": {"required": "Please write a message."},
        }

    def clean_message(self):
        msg = (self.cleaned_data.get("message") or "").strip()
        if len(msg) < 10:
            raise forms.ValidationError(
                "Please write at least a sentence so we can help you properly."
            )
        return msg

    def clean(self):
        cleaned = super().clean()
        # Honeypot tripped → silently reject. Don't tell the bot.
        if cleaned.get("website"):
            raise forms.ValidationError("Unable to send.")
        return cleaned
