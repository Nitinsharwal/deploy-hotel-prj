from django.db import models
from django.contrib.auth.models import User



class hotel_owner(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="owner_profile")
    profile_pic = models.ImageField(upload_to='profile', null=True, blank=True)
    phone_number = models.CharField(max_length=20, unique=True)
    email_token = models.CharField(max_length=100, null=True, blank=True)
    otp = models.CharField(max_length=8, null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username


class hotel_vendor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="vendor_profile")
    business_name = models.CharField(max_length=191)
    profile_pic = models.ImageField(upload_to='profile', null=True, blank=True)
    phone_number = models.CharField(max_length=20, unique=True)
    email_token = models.CharField(max_length=100, null=True, blank=True)
    otp = models.CharField(max_length=8, null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.business_name



class amenities(models.Model):
    amenities_name = models.CharField(max_length=191)
    icon = models.ImageField(upload_to="hotels")

    def __str__(self):
        return self.amenities_name


class hotels(models.Model):
    hotel_name = models.CharField(max_length=191)
    hotel_description = models.TextField()
    hotel_slug = models.SlugField(max_length=191, unique=True)
    hotel_owner = models.ForeignKey(hotel_vendor, on_delete=models.CASCADE, related_name="hotels")
    hotel_amenities = models.ManyToManyField(amenities)
    hotel_price = models.FloatField()
    hotel_offer_price = models.FloatField()
    hotel_location = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.hotel_name


class hotel_images(models.Model):
    hotel = models.ForeignKey(hotels, on_delete=models.CASCADE, related_name="hotel_images")
    image = models.ImageField(upload_to="hotels")


class hotel_manager(models.Model):
    hotel = models.ForeignKey(hotels, on_delete=models.CASCADE, related_name="hotel_managers")
    manager_name = models.CharField(max_length=100)
    manager_contact = models.CharField(max_length=20)


class customers(models.Model):
    hotel = models.ForeignKey(hotels, on_delete=models.CASCADE, related_name='customer_bookings')
    customer_fname = models.CharField(max_length=100)
    customer_lname = models.CharField(max_length=100)
    customer_email = models.EmailField(max_length=191)
    start_date = models.DateField()
    end_date = models.DateField()
    payment = models.FloatField()

    def __str__(self):
        return f"{self.customer_fname} {self.customer_lname}"
