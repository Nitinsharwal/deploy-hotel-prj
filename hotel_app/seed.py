from django.contrib.auth.models import User
from accounts.models import *
from faker import Faker
import random
from random import choice

fake = Faker()

def createUser():
    for _ in range(19):
        email = fake.email()
        hotel_vendor.objects.create(
            email=email,
            business_name=fake.company(),
            username=email,
            first_name=fake.first_name(),
            phone_number=random.randint(7000000000, 9999999999) 
        )

def createHotel():
    vendors = list(hotel_vendor.objects.all())
    amenities_list = list(amenities.objects.all())

    for _ in range(30):
        Hotel_vendor = choice(vendors) 
        hotel = hotels.objects.create(
            hotel_name=fake.company(),
            hotel_description=fake.text(),
            hotel_slug=fake.slug(),
            hotel_owner=Hotel_vendor,  
            hotel_location=fake.address(),
            hotel_price=round(random.uniform(1000, 5000), 2),
            hotel_offer_price=round(random.uniform(500, 4000), 2),
            is_active=fake.boolean()
        )

        hotel.hotel_aminities.set(random.sample(amenities_list, k=random.randint(1, len(amenities_list))))
