from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class hotel_owner(User):
    firstname  = models.CharField(max_length=28,null=True)
    lastname = models.CharField(max_length=28,null=True)
    profile_pic = models.ImageField(upload_to='profile')
    phone_number = models.CharField(unique=True, max_length=100)
    email_token = models.CharField(max_length=100,null=True,blank=True)
    otp = models.CharField(max_length=8,null=True,blank=True)
    is_verified = models.BooleanField(default=False)
    class Meta:
        def __str__(self):
            return self.name
        

class hotel_vendor(User):
    firstname  = models.CharField(max_length=28,null=True)
    lastname = models.CharField(max_length=28,null=True)
    profile_pic = models.ImageField(upload_to='profile')
    business_name = models.CharField(max_length=100)
    phone_number = models.CharField(unique=True, max_length=100)
    email_token = models.CharField(max_length=100,null=True,blank=True)
    otp = models.CharField(max_length=8,null=True,blank=True)
    is_verified = models.BooleanField(default=False)

    class Meta:
        def __str__(self):
            return self.name
        

class amenities(models.Model):
    amenities_name = models.CharField(max_length=120)
    icon = models.ImageField(upload_to="hotels")
    def __str__(self):
        return self.amenities_name
    

class hotels(models.Model):
    hotel_name = models.CharField(max_length=200)
    hotel_description = models.TextField(max_length=1200)
    hotel_slug = models.SlugField(max_length=250,unique=True)
    hotel_owner = models.ForeignKey(hotel_vendor, on_delete=models.CASCADE, related_name="hotels")
    hotel_aminities = models.ManyToManyField(amenities)
    hotel_price = models.FloatField()
    hotel_offer_price = models.FloatField()
    hotel_location = models.TextField()
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.hotel_name
    
class hotel_images(models.Model):
    hotel = models.ForeignKey(hotels,  on_delete=models.CASCADE, related_name="hotel_images")
    image = models.ImageField(upload_to="hotels")

class hotel_manager(models.Model):
    hotel = models.ForeignKey(hotels,  on_delete=models.CASCADE, related_name="hotel_manager")
    manager_name = models.CharField(max_length=110)
    manager_contact = models.CharField(max_length=110)


class customers(models.Model): 
    hotel = models.ForeignKey(hotels, on_delete=models.CASCADE, related_name='customer_bookings')
    customer_fname = models.CharField(max_length=100)
    customer_lname = models.CharField(max_length=100)
    customer_email = models.EmailField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    payment = models.FloatField()

    def __str__(self):
        return f"{self.customer_fname} {self.customer_lname}"