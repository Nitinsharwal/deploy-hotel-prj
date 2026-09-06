from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q

from .models import Room, amenities, hotel_owner, hotel_vendor, hotels


class CustomerRegisterForm(forms.Form):
    firstname = forms.CharField(max_length=150)
    lastname = forms.CharField(max_length=150)
    phone_number = forms.CharField(max_length=20)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email")
        phone = cleaned.get("phone_number")
        if email and User.objects.filter(Q(email=email) | Q(username=email)).exists():
            raise forms.ValidationError("An account with that email already exists.")
        if phone and hotel_owner.objects.filter(phone_number=phone).exists():
            raise forms.ValidationError("That phone number is already registered.")
        return cleaned


class VendorRegisterForm(forms.Form):
    firstname = forms.CharField(max_length=150)
    lastname = forms.CharField(max_length=150)
    business_name = forms.CharField(max_length=191)
    phone_number = forms.CharField(max_length=20)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    profile_image = forms.ImageField(required=False)

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email")
        phone = cleaned.get("phone_number")
        if email and User.objects.filter(Q(email=email) | Q(username=email)).exists():
            raise forms.ValidationError("An account with that email already exists.")
        if phone and hotel_vendor.objects.filter(phone_number=phone).exists():
            raise forms.ValidationError("That phone number is already registered.")
        return cleaned


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class HotelForm(forms.ModelForm):
    hotel_amenities = forms.ModelMultipleChoiceField(
        queryset=amenities.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = hotels
        fields = [
            "hotel_name",
            "hotel_description",
            "hotel_amenities",
            "hotel_price",
            "hotel_offer_price",
            "hotel_location",
        ]

    def clean(self):
        cleaned = super().clean()
        price = cleaned.get("hotel_price")
        offer = cleaned.get("hotel_offer_price")
        if price is not None and offer is not None and offer > price:
            raise forms.ValidationError("Offer price cannot exceed the base price.")
        return cleaned


class ProfileForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    phone_number = forms.CharField(max_length=20, required=False)
    profile_pic = forms.ImageField(required=False)

    def __init__(self, *args, user=None, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.owner = owner

    def clean_phone_number(self):
        phone = (self.cleaned_data.get("phone_number") or "").strip()
        if not phone:
            return None  # null in DB; treated as "no phone set"
        # Reject duplicates EXCEPT the current user's own row.
        from .models import hotel_owner

        clash = hotel_owner.objects.filter(phone_number=phone)
        if self.owner:
            clash = clash.exclude(pk=self.owner.pk)
        if clash.exists():
            raise forms.ValidationError("That phone number is already in use by another account.")
        return phone

    def save(self):
        u = self.user
        u.first_name = self.cleaned_data.get("first_name", "") or u.first_name
        u.last_name = self.cleaned_data.get("last_name", "") or u.last_name
        u.save(update_fields=["first_name", "last_name"])

        if self.owner:
            self.owner.phone_number = self.cleaned_data.get("phone_number")
            pic = self.cleaned_data.get("profile_pic")
            if pic:
                self.owner.profile_pic = pic
            self.owner.save()
        return u


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["name", "room_type", "capacity", "total_count", "base_price", "is_active"]

    def clean_total_count(self):
        n = self.cleaned_data["total_count"]
        if n < 1:
            raise forms.ValidationError("A room type must have at least 1 unit.")
        return n

    def clean_capacity(self):
        n = self.cleaned_data["capacity"]
        if n < 1:
            raise forms.ValidationError("Capacity must be at least 1.")
        return n


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        max_length=191,
        widget=forms.EmailInput(attrs={
            "placeholder": "you@example.com",
            "autocomplete": "email",
            "autofocus": True,
        }),
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class ResetPasswordForm(forms.Form):
    new_password = forms.CharField(
        min_length=8,
        max_length=128,
        widget=forms.PasswordInput(attrs={
            "placeholder": "At least 8 characters",
            "autocomplete": "new-password",
        }),
    )
    confirm_password = forms.CharField(
        min_length=8,
        max_length=128,
        widget=forms.PasswordInput(attrs={
            "placeholder": "Repeat new password",
            "autocomplete": "new-password",
        }),
    )

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get("new_password")
        confirm = cleaned.get("confirm_password")
        if pw and confirm and pw != confirm:
            self.add_error("confirm_password", "Passwords do not match.")
        if pw:
            try:
                validate_password(pw)
            except forms.ValidationError as e:
                self.add_error("new_password", e)
        return cleaned


class OtpResetForm(ResetPasswordForm):
    email = forms.EmailField(
        max_length=191,
        widget=forms.EmailInput(attrs={
            "placeholder": "you@example.com",
            "autocomplete": "email",
        }),
    )
    otp = forms.CharField(
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={
            "placeholder": "6-digit code",
            "inputmode": "numeric",
            "pattern": "[0-9]*",
            "autocomplete": "one-time-code",
        }),
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_otp(self):
        code = self.cleaned_data["otp"].strip()
        if not code.isdigit():
            raise forms.ValidationError("OTP must be 6 digits.")
        return code
