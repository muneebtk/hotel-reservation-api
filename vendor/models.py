import uuid
from datetime import datetime
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from .function import generate_unique_slug
from common.models import Country,State,City,Amenity,Categories,PolicyCategory, PolicyName,PaymentTypeCategory,PaymentType, Tax, Transaction,OwnerName
from user.models import VendorProfile,Userdetails
from django.utils.translation import gettext_lazy as _
# Create your models here.

User = get_user_model()

class Roomtype(models.Model):
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('inactive', _('Inactive')),
        ('deleted', _('Deleted')),
    ]

    room_types = models.CharField(max_length=50, null=True, blank=True)  # Room type name (unique)
    room_types_arabic = models.CharField(max_length=50, null=True, blank=True)  
    room_type_icon = models.ImageField(upload_to='roomtype_icons/', null=True, blank=True)  # Optional icon
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')  # Status
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='room_types_created')
    created_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.room_types} ({self.get_status_display()})"
  

class HotelType(models.Model):
    STATUS_CHOICES = (
        ("active", _("Active")),
        ("inactive", _("Inactive")),
        ("deleted", _("Deleted")),
    )

    name = models.CharField(max_length=200, unique=True)
    arabic_name = models.CharField(max_length=200, unique=True, default="None")
    icon = models.ImageField(upload_to="hotel_types_icons/", null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='hotel_types_created')
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")

    def __str__(self):
        return self.name

def hotel_image_path(instance, filename):
    from api.function import format_name

    # file will be uploaded to MEDIA_ROOT/hotel_images/<hotel_name>/<filename>
    hotel_name = instance.hotel.name if instance.hotel else 'default'
    get_formated_name = format_name(hotel_name)
    formated_name = get_formated_name.replace(' ','_')
    return f'hotel_images/hotel_{formated_name}/{filename}'


def hotel_document_path(instance, filename):
    from api.function import format_name

    # file will be uploaded to MEDIA_ROOT/hotel_documents/<hotel_name>/<filename>
    hotel_name = instance.hotel.name if instance.hotel else 'default'
    get_formated_name = format_name(hotel_name)
    formated_name = get_formated_name.replace(' ','_')
    return f'hotel_documents/hotel_{formated_name}/{filename}'



class Hotel(models.Model):
    HOTEL_RATING = (
        ("1", "1 Star"),
        ("2", "2 Star"),
        ("3", "3 Star"),
        ("4", "4 Star"),
        ("5", "5 Star")
    )
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected")
    )
    
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, null=True)
    hotel_type = models.ForeignKey(HotelType, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ManyToManyField(Categories)
    office_number = models.CharField(max_length=20, null=True, blank=True) 
    name = models.CharField(max_length=200, null=True, blank=True) 
    address = models.CharField(max_length=300, null=True, blank=True) 
    owner_name=models.ForeignKey(OwnerName, on_delete=models.CASCADE, null=True, blank=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True)
    city = models.ForeignKey(City, on_delete=models.CASCADE, null=True, blank=True)
    state = models.ForeignKey(State, on_delete=models.CASCADE, null=True, blank=True)
    number_of_rooms = models.IntegerField(null=True, blank=True)
    rooms_available = models.IntegerField(null=True, blank=True)
    hotel_rating = models.CharField(max_length=1, null=True, blank=True, choices=HOTEL_RATING)
    room_types = models.ManyToManyField(Roomtype, blank=True)
    cr_number = models.CharField(max_length=30, null=True, blank=True)  
    vat_number = models.CharField(max_length=30, null=True, blank=True)  
    date_of_expiry = models.DateField(null=True, blank=True)
    logo = models.ImageField(upload_to='hotel_logos/', null=True, blank=True,max_length=10000)
    hotel_id = models.CharField(max_length=20, null=True, blank=True)  

    # New fields
    about_property = models.TextField(null=True, blank=True)
    hotel_policies = models.TextField(null=True, blank=True)
    locality = models.TextField(null=True, blank=True)  
    # building_number = models.CharField(max_length=50, null=True, blank=True)  
    amenities = models.ManyToManyField(Amenity, blank=True)
    post_approval = models.BooleanField(default=False)
    policies = models.ManyToManyField(PolicyCategory, blank=True)
    # categories = models.ManyToManyField(PolicyCategory, blank=True)  
    policies_name = models.ManyToManyField(PolicyName, blank=True)

    checkin_time = models.TimeField(null=True)
    checkout_time = models.TimeField(null=True)
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    approval_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")

    # New fields for Arabic translations
    name_arabic = models.CharField(max_length=200, null=True, blank=True)
    owner_name_arabic = models.CharField(max_length=200, null=True, blank=True)
    # locality_arabic = models.TextField(null=True, blank=True)
    about_property_arabic = models.TextField(null=True, blank=True)
    hotel_policies_arabic = models.TextField(null=True, blank=True)
    created_date = models.DateTimeField(default=timezone.now,null=True, blank=True)
    account_no=models.BigIntegerField(null=True, blank=True)
    account_holder_name=models.CharField(max_length=50 , null=True, blank=True)
    bank=models.CharField(max_length=100,null=True,blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)


    

    def __str__(self) -> str:
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.hotel_id:  
            last_hotel = Hotel.objects.order_by('id').last()
            next_id = 1 if not last_hotel else last_hotel.id + 1
            self.hotel_id = f"HTL{next_id:04d}" 
        super().save(*args, **kwargs)

    def get_approval_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.approval_status, self.approval_status)
    
    def get_vendor_full_name(self):
        """Return the full name of the vendor or None."""
        if self.vendor and self.vendor.name:
            return f"{self.vendor.name}"
        return None
    
    def get_vendor_email(self):
        """Return the email of the vendor or None."""
        if self.vendor and self.vendor.user and self.vendor.user.email:
            return f"{self.vendor.user.email}"
        return None

class HotelImage(models.Model):
    hotel = models.ForeignKey(Hotel, related_name='hotel_images', on_delete=models.CASCADE, null=True)
    image = models.ImageField(upload_to=hotel_image_path)  
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_main_image = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for {self.hotel.name}"


class HotelDocument(models.Model):
    hotel = models.ForeignKey(Hotel, related_name='attached_documents', on_delete=models.CASCADE, null=True)
    document = models.FileField(upload_to=hotel_document_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Document for {self.hotel.name}"



class MealPrice(models.Model):
    meal_type_choices = [
        ('no meals', _('No meals')),
        ('breakfast', _('Breakfast')),
        ('lunch', _('Lunch')),
        ('dinner', _('Dinner')),
    ]
    
    meal_type = models.CharField(max_length=10, choices=meal_type_choices)
    price = models.DecimalField(max_digits=7, decimal_places=3,null=True)
    hotel = models.ForeignKey(Hotel,on_delete=models.CASCADE, null=True)
    created_date = models.DateTimeField(default=timezone.now,null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    def __str__(self) -> str:
        return f"{self.hotel.name}-{self.meal_type}-{self.price}"

class RoomImage(models.Model):
    image = models.ImageField(upload_to='roomtype_images/',null=True)
    created_date = models.DateTimeField(default=timezone.now,null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    def __str__(self) -> str:
        return "%s" % (self.image)


class RoomManagement(models.Model):
    hotel = models.ForeignKey(Hotel,on_delete=models.CASCADE, related_name='room_managements', null=True)
    room_types = models.ForeignKey(Roomtype,on_delete=models.CASCADE, null=True)
    number_of_rooms = models.IntegerField(null=True, blank=True)
    total_occupancy = models.IntegerField(null=True, blank=True)
    availability = models.BooleanField(default=True)
    price_per_night = models.DecimalField(max_digits=11, decimal_places=3, default=0)
    amenities = models.ManyToManyField(Amenity, blank=True)
    adults = models.IntegerField(default=1, null=True, blank=True)  # New field for adults
    children = models.IntegerField(default=0, null=True, blank=True)  # New field for children
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('deleted', 'Deleted'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    image = models.ManyToManyField(RoomImage, blank=True)
    created_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    meals = models.ManyToManyField(MealPrice, blank=True)

    def __str__(self) -> str:
        return "%s - %s" % (self.hotel.name, str(self.room_types.room_types))
    

    @property
    def current_price(self):
        """
        Return the current price for the room.
        If today is Friday or Saturday, return the weekend price if it exists and is active.
        Otherwise, return the regular price per night.
        """
        today = datetime.now().weekday()  # 0 = Monday, ..., 4 = Friday, 5 = Saturday
        if today in (3, 4):  # Thursday or Friday
            # Check if a weekend price exists and is active
            if hasattr(self, 'weekend_price') and self.weekend_price.is_active():
                return self.weekend_price.weekend_price
        # Default to price_per_night if no valid weekend price exists
        return self.price_per_night
 
# class PromoCode(models.Model):
#     code = models.CharField(max_length=50, unique=True,blank=True)
#     created_date = models.DateTimeField(default=timezone.now,blank=True)
#     usage_limit = models.IntegerField(null=True, blank=True)  
#     times_used = models.IntegerField(default=0,blank=True)  
#     hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, null=True, blank=True)  
#     chalet = models.ForeignKey(Chalet, on_delete=models.CASCADE, null=True, blank=True) 
#     def __str__(self):
#         return self.code

# class Offer(models.Model):
#     hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, null=True, blank=True)  
#     chalet = models.ForeignKey(Chalet, on_delete=models.CASCADE, null=True, blank=True) 
    
#     offer_name = models.CharField(max_length=255, default='None') 
#     description = models.TextField(default='None')  
    
#     discount_type = models.CharField(max_length=50, choices=[
#         ('percentage', 'Percentage'),
#         ('fixed', 'Fixed Amount'),
#         ('free_upgrade', 'Free Upgrade')
#     ], default='percentage')  
    
#     discount_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) 
    
#     validity_from = models.DateField(null=True, blank=True)
#     validity_to = models.DateField(null=True, blank=True)

#     minimum_spend = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  
    
#     usage_limit = models.IntegerField(null=True, blank=True) 
#     times_used = models.IntegerField(default=0) 
    
#     status = models.CharField(max_length=50, choices=[
#         ('active', 'Active'), 
#         ('inactive', 'Inactive')
#     ], default='active')  
    
#     created_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
#     modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)

#     promo_codes = models.ManyToManyField(PromoCode, blank=True)

#     def __str__(self):
#         return f'{self.offer_name} - {self.discount_type}'


class HotelTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('Booking Payment', 'Booking Payment'),
        ('Refund', 'Refund'),
        # Add more types if needed
    )
    
    TRANSACTION_STATUSES = (
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
        ('Cancelled', 'Cancelled'),
        ('Refunded', 'Refunded'),
        # Add more statuses if needed
    )
    
    PAYMENT_STATUSES = (
        ('Paid', 'Paid'),
        ('Failed', 'Failed'),
        ('Refunded', 'Refunded'),
        ('Unpaid','Unpaid')
        # Add more statuses if needed
    )


    PAYMENT_METHOD_CHOICES = [
        ('Credit Card', 'Credit Card'),
        ('Debit Card', 'Debit Card'),
        ('PayPal', 'PayPal'),
        ('Bank Transfer', 'Bank Transfer'),
        ('Cash', 'Cash'),
        ('Wallet','Wallet')
        # Add more choices as needed
    ]
    transaction_id = models.CharField(max_length=100)
    transaction_date = models.DateField()
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES)
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPES)
    transaction_amount = models.DecimalField(max_digits=11, decimal_places=3)
    transaction_status = models.CharField(max_length=50, choices=TRANSACTION_STATUSES)
    transaction_reference_no = models.CharField(max_length=100)
    payment_status = models.CharField(max_length=50, choices=PAYMENT_STATUSES)
    payment_gateway = models.CharField(max_length=100)

    created_date = models.DateTimeField(default=timezone.now,null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return self.transaction_id + " - " + self.payment_status
        
class Booking(models.Model):
    PROPERTY_TYPE = [
        ('camp', 'Camp'),
        ('farm', 'Farm'),
        ('tent', 'Tent'),
    ]
    BOOKING_STATUS = [
        ('pending', 'Pending'), # Awaiting vendor approval
        ('booked', 'Booked'), # Vendor confirmed
        ('confirmed', 'Confirmed'), # User paid and confirmed
        ('rejected', 'Rejected'), # Cancelled by vendor
        ('expired', 'Expired'), # Expired because no payment from user
        ('cancelled', 'Cancelled'), # Cancelled either by user or admin
        ('completed', 'Completed'), # Completed
        ('check-in', 'Check-In'), # when customer gets check in 
        ('check-out', 'Check-Out'),
    ]

    CANCELLED_BY = [
        ('vendor', 'Vendor'), # Cancelled by Vendor but not to consider now because as per our current flow, Vendor cannot cancel the booking once confirmed
        ('user', 'User'), # Cancelled by User
        ('admin', 'Admin'), # Cancelled by Admin
    ]

  
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, blank=True, null=True,related_name="hotel_booking")
    user = models.ForeignKey(Userdetails, on_delete=models.CASCADE, null=True)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, null=True)
    booking_fname = models.CharField(max_length=20, null=True)
    booking_lname = models.CharField(max_length=20, null=True)
    booking_email = models.EmailField(max_length=254, null=True)
    booking_mobilenumber = models.CharField(max_length=20, null=True)
    checkin_date = models.DateField()
    checkout_date = models.DateField()
    check_in_time = models.TimeField(null=True)
    check_out_time = models.TimeField(null=True)
    discount_price = models.DecimalField(max_digits=11, decimal_places=3, blank=True, null=True)
    service_fee = models.DecimalField(max_digits=11, decimal_places=3, blank=True, null=True)
    booked_price = models.DecimalField(max_digits=11, decimal_places=3, blank=True, null=True)
    number_of_guests = models.IntegerField()
    adults=models.IntegerField(default=0)
    children=models.IntegerField(default=0)
    number_of_booking_rooms = models.IntegerField(null=True)
    is_my_self = models.BooleanField(default=False, null=True)
    booking_id = models.CharField(max_length=20, null=True)
    booking_date = models.DateField(default=timezone.now)
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPE, blank=True, null=True, default=None)
    promocode_applied = models.CharField(max_length=20, null=True, blank=True)
    discount_percentage_applied = models.CharField(max_length=20, null=True, blank=True)
    # New fields for security token and QR code URL
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=False)
    qr_code_url = models.URLField(max_length=255, blank=True, null=True)
    cancelled_by=models.CharField(max_length=6,null=True,blank=True,choices=CANCELLED_BY,default=None)
    created_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    is_deleted=models.BooleanField(default=False) # Default value will False, the same will be used to archieve past 1 year or specific time period bookings to improve db query performance if required in future
    status=models.CharField(max_length=10,default="pending",choices=BOOKING_STATUS)
    tax_and_services = models.DecimalField(max_digits=11, decimal_places=3, default=0.0, null=True, blank=True)
    meal_price = models.DecimalField(max_digits=11, decimal_places=3, default=0.0, null=True, blank=True)
    meal_tax = models.DecimalField(max_digits=11, decimal_places=3, default=0.0, null=True, blank=True)
    
    def __str__(self) -> str:
        return f'{self.hotel.name} ----->>>>  {self.booking_fname}  ------->>>>>>'
    
    def get_guest_full_name(self):
        """Return the full name of the guest."""
        if self.booking_fname and self.booking_lname:
            return f"{self.booking_fname} {self.booking_lname}"
        elif self.booking_fname:
            return self.booking_fname
        elif self.booking_lname:
            return self.booking_lname
        return "Unknown Guest"
    
class RecentReview(models.Model):
    RATING = (
        (1.0, "1 Rating"),
        (2.0, "2 Rating"),
        (3.0, "3 Rating"),
        (4.0, "4 Rating"),
        (5.0, "5 Rating"),
    )
    booking = models.ForeignKey(Booking,on_delete=models.CASCADE,null=True)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE,null=True)
    rating = models.DecimalField(null=True, blank=True, choices=RATING,max_digits=2, decimal_places=1,default=0.0)
    username = models.CharField(max_length=255,null=True, blank=True)
    date = models.DateTimeField(null=True)
    review_text = models.TextField(null=True, blank=True)    
    respond = models.TextField(null=True, blank=True)
    
    created_date = models.DateTimeField(default=timezone.now,null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)


class CommissionSlab(models.Model):
    from_amount = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    to_amount = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    
    created_by = models.ForeignKey(User, related_name='commission_created', on_delete=models.SET_NULL, null=True)
    modified_by = models.ForeignKey(User, related_name='commission_modified', on_delete=models.SET_NULL, null=True)
    created_date = models.DateTimeField(default=timezone.now) 
    modified_date = models.DateTimeField(auto_now=True) 

    def __str__(self):
        return f"From {self.from_amount} to {self.to_amount}: {self.commission_amount}"
    
class Bookedrooms(models.Model):
    STATUS_CHOICES = [
        ('confirmed', 'confirmed'),
        ('pending', 'pending'),
        ('cancelled', 'cancelled'),
        ('completed','completed')
    ]
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=True,related_name="booked_rooms")
    room = models.ForeignKey(RoomManagement, on_delete=models.CASCADE, null=True)
    meal_type_id=models.ForeignKey(MealPrice,on_delete=models.CASCADE,null=True)
    booked_room_price = models.DecimalField(max_digits=11, decimal_places=3, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    no_of_rooms_booked=models.IntegerField(default=1,null=True,blank=True)
    
    def __str__(self) -> str:
        return f'{self.booking.booking_fname} ----->>>>  {self.room.room_types.room_types} ----->>>>  {self.booking.hotel.name}'
    
class WeekendPrice(models.Model):
    room = models.OneToOneField(RoomManagement, on_delete=models.CASCADE, related_name='weekend_price')
    weekend_price = models.DecimalField(max_digits=11, decimal_places=3, default=0.0)
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(default=timezone.now, blank=True)
    modified_at = models.DateTimeField(auto_now=True, blank=True)

    def __str__(self):
        return f"Weekend Price for {self.room} ({self.get_status_display()})"

    def is_active(self):
        """Returns True if the weekend price is active."""
        return self.status == 'active'


class Favorites(models.Model):
    user = models.ForeignKey(Userdetails, on_delete=models.CASCADE, null=True)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, null=True)
    is_liked = models.BooleanField(default=True)
    created_date = models.DateTimeField(default=timezone.now, null=True, blank=True)

    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self) -> str:
        return f'{self.user.user.first_name} ------->   {self.hotel.name}'


class Cancelbooking(models.Model):
    user = models.ForeignKey(Userdetails, on_delete=models.CASCADE, null=True)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=True)
    reason = models.CharField(max_length=200,blank=True,null=True,default=None)

    created_date = models.DateTimeField(default=timezone.now, null=True, blank=True)

    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    def __str__(self) -> str:
        return f'{self.user.user.first_name} ------->   {self.booking.hotel.name} ------->   {self.booking.booked_rooms}'
class HotelAcceptedPayment(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    slug=models.SlugField(unique=True,null=True,blank=True)
    hotel = models.OneToOneField(Hotel, on_delete=models.CASCADE, null=True)
    created_by = models.ForeignKey(VendorProfile, related_name='hotel_accpt_payment_created', on_delete=models.SET_NULL, null=True)
    modified_by = models.ForeignKey(VendorProfile, related_name='hotel_accpt_payment_modified', on_delete=models.SET_NULL, null=True)    
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    payment_types=models.ManyToManyField(PaymentType,related_name="hotel_payment_types_set")
    is_deleted=models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(self, 'hotel')
        super().save(*args, **kwargs)


    def __str__(self) -> str:
        return f'{self.hotel.name}'
    


    
from django.core.validators import MinValueValidator, MaxValueValidator 

class HotelTax(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='hotel_taxes')
    tax = models.ForeignKey(Tax, on_delete=models.CASCADE, related_name='hotel_taxes')
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0.00), MaxValueValidator(100.00)]
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active", db_index=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        VendorProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hotel_taxes_created"
    )
    modified_by = models.ForeignKey(
        VendorProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hotel_taxes_modified"
    )
    created_date = models.DateTimeField(default=timezone.now)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.tax and self.tax.name: 
            return f"{self.tax.name} - {self.percentage}%" if self.percentage else f"{self.tax.name}"
        return super().__str__()

    class Meta: 
        verbose_name_plural = "Hotel Taxes" 
        constraints = [ 
            models.UniqueConstraint(fields=["hotel", "tax"], name="unique_hotel_tax") 
        ]

class MealTax(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("deleted", "Deleted"),
    )

    room = models.ForeignKey(RoomManagement, on_delete=models.CASCADE, related_name='meal_taxes')
    name = models.CharField(max_length=100)  
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0.00), MaxValueValidator(100.00)]
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active", db_index=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        VendorProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="meal_taxes_created"
    )
    modified_by = models.ForeignKey(
        VendorProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="meal_taxes_modified"
    )
    created_date = models.DateTimeField(default=timezone.now)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.room.room_types.room_types} - {self.name} - {self.percentage}%"

    class Meta:
        verbose_name_plural = "Meal Taxes"
        constraints = [
            models.UniqueConstraint(fields=["room", "name"], name="unique_meal_tax")
        ]

class RefundPolicyCategory(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    name=models.CharField(max_length=50,null=True,unique=True)
    name_arabic=models.CharField(max_length=50,null=True,unique=True)
    is_deleted=models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="category_created_by")
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="category_modified_by")
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    status=models.CharField(max_length=10,default="active",choices=STATUS_CHOICES)

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    @classmethod
    def get_active_categories(cls):
        """Fetch all active refund policy categories."""
        return cls.objects.filter(status="active", is_deleted=False)


class RefundPolicy(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    code=models.CharField(max_length=12,null=True,unique=True)
    category=models.ForeignKey(RefundPolicyCategory,on_delete=models.SET_NULL, null=True, blank=True)
    name=models.CharField(max_length=50,null=True,unique=True)
    title=models.CharField(max_length=75,null=True,unique=True)
    title_arabic=models.CharField(max_length=75,null=True,unique=True)
    is_refundable=models.BooleanField(default=False)
    is_deleted=models.BooleanField(default=False)
    is_validity_specific=models.BooleanField(default=False)
    is_percentage_specific=models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="policy_created_by")
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="policy_modified_by")
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    status=models.CharField(max_length=10,default="active",choices=STATUS_CHOICES)

    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"

class RoomRefundPolicy(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    policy=models.ForeignKey(RefundPolicy,on_delete=models.SET_NULL, null=True, blank=True)
    room=models.OneToOneField(RoomManagement,on_delete=models.CASCADE,null=True)
    validity=models.DurationField(null=True,blank=True)
    percentage=models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage value (e.g., 10.50 for 10.50%)",null=True,blank=True)
    is_deleted=models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="room_refund_created_by")
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="room_refund_modified_by")
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    status=models.CharField(max_length=10,default="active",choices=STATUS_CHOICES)

    def __str__(self):
        return f"{self.room} - {self.policy.name if self.policy else 'No Policy'}"


class HotelBookingTransaction(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('in-active', 'In-Active'),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(Userdetails, on_delete=models.SET_NULL, null=True)
    modified_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"Booking Transaction {self.id}"


class VendorTransaction(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('in-active', 'In-Active'),
    ]

    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, related_name="vendor_transaction")
    vendor = models.ForeignKey(VendorProfile, on_delete=models.SET_NULL, null=True, related_name="vendor_transactions")
    
    base_price = models.DecimalField(max_digits=11, decimal_places=3)  # Room price only
    total_tax = models.DecimalField(max_digits=11, decimal_places=3)  # Taxes applied
    meal_price = models.DecimalField(max_digits=11, decimal_places=3, default=0.00, null=True, blank=True)  
    meal_tax = models.DecimalField(max_digits=11, decimal_places=3, default=0.00, null=True, blank=True)  
    discount_applied = models.DecimalField(max_digits=11, decimal_places=3, default=0.00)
    vendor_earnings = models.DecimalField(max_digits=11, decimal_places=3, default=0.00)  # Vendor's net revenue

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(Userdetails, on_delete=models.SET_NULL, null=True)
    modified_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"Vendor Transaction for {self.transaction.transaction_id if self.transaction else 'N/A'}"

    class Meta:
        indexes = [
            models.Index(fields=['transaction']),
            models.Index(fields=['vendor']),
        ]
