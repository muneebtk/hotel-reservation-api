import uuid
from datetime import datetime
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

from user.models import VendorProfile,Userdetails,Wallet
from common.models import Country,State,City,Amenity,Categories,PolicyCategory, PolicyName,PaymentType, ChaletType, Tax, Transaction,OwnerName
from vendor.models import Hotel,Booking,Roomtype
from vendor.function import generate_unique_slug

User = get_user_model()

# Create your models here.
class Chalet(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )
    chalet_type = models.ForeignKey(ChaletType, on_delete=models.SET_NULL, null=True, blank=True)
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, null=True)
    category = models.ManyToManyField(Categories)
    office_number = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=200, null=True, blank=True)
    address = models.CharField(max_length=300, null=True, blank=True)
    country = models.ForeignKey(
        Country, on_delete=models.CASCADE, null=True, blank=True
    )
    city = models.ForeignKey(City, on_delete=models.CASCADE, null=True, blank=True)
    state = models.ForeignKey(State, on_delete=models.CASCADE, null=True, blank=True)
    cr_number = models.CharField(max_length=30, null=True, blank=True)
    vat_number = models.CharField(max_length=30, null=True, blank=True)
    date_of_expiry = models.DateField(null=True, blank=True)
    logo = models.ImageField(upload_to="chalet_logos/", null=True, blank=True)
    chalet_id = models.CharField(max_length=20, null=True, blank=True)
    owner_name=models.ForeignKey(OwnerName, on_delete=models.CASCADE, null=True, blank=True)


    # New fields
    about_property = models.TextField(null=True, blank=True)
    policies = models.TextField(null=True, blank=True)
    locality = models.CharField(max_length=100, null=True, blank=True)
    # building_number = models.CharField(max_length=50, null=True, blank=True)
    amenities = models.ManyToManyField(Amenity, blank=True)
    post_approval = models.BooleanField(default=False)
    post_policies = models.ManyToManyField(PolicyCategory, blank=True)
    post_policies_name = models.ManyToManyField(PolicyName, blank=True)
    checkin_time = models.TimeField(null=True)
    checkout_time = models.TimeField(null=True)
    commission_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    approval_status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="pending"
    )

    # New fields for Arabic translations
    name_arabic = models.CharField(max_length=200, null=True, blank=True)
    owner_name_arabic = models.CharField(max_length=200, null=True, blank=True)
    # locality_arabic = models.CharField(max_length=100, null=True, blank=True)
    about_property_arabic = models.TextField(null=True, blank=True)
    policies_arabic = models.TextField(null=True, blank=True)

    created_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    is_booked = models.BooleanField(default=False)  # New field
    STATUSES=(
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("deleted", "Deleted"),
    )
    status = models.CharField(max_length=20,choices=STATUSES,default='active')

    number_of_guests = models.PositiveIntegerField(null=True, blank=True) 
    total_price = models.DecimalField(max_digits=11, decimal_places=3, null=True, blank=True)  
    account_no=models.BigIntegerField(null=True, blank=True)
    account_holder_name=models.CharField(max_length=50 , null=True, blank=True)
    bank=models.CharField(max_length=100,null=True,blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    
    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.chalet_id:  
            last_chalet = Chalet.objects.order_by('id').last()
            next_id = 1 if not last_chalet else last_chalet.id + 1
            self.chalet_id = f"CHL{next_id:04d}" 
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
    @property
    def current_price(self):
        """
        Return the current price for the chalet.
        If today is Friday or Saturday, return the weekend price if it exists and is active.
        Otherwise, return the total_price.
        """
        today = datetime.now().weekday()  # 0 = Monday, ..., 4 = Friday, 5 = Saturday
        if today in (3, 4):  # Friday or Thursday
            # Check if a weekend price exists and is active
            if hasattr(self, 'weekend_price') and self.weekend_price.is_active:
                return self.weekend_price.weekend_price
        # Default to total_price if no valid weekend price exists
        return self.total_price

def chalet_image_path(instance, filename):
    chalet_name = instance.chalet.name[:50] if instance.chalet else "default"  # Shorten the chalet name
    return f"chalet_images/{chalet_name}/{filename}"

def chalet_document_path(instance, filename):
    chalet_name = instance.chalet.name[:50] if instance.chalet else "default"  # Shorten the chalet name
    return f"chalet_documents/{chalet_name}/{filename}"

class ChaletImage(models.Model):
    chalet = models.ForeignKey(
        Chalet, related_name="chalet_images", on_delete=models.CASCADE, null=True
    )
    image = models.ImageField(upload_to=chalet_image_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_main_image = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for {self.chalet.name}"

class chaletDocument(models.Model):
    chalet = models.ForeignKey(
        Chalet,
        related_name="chalet_attached_documents",
        on_delete=models.CASCADE,
        null=True,
    )
    document = models.FileField(upload_to=chalet_document_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Document for {self.chalet.name}"


class PropertyManagement(models.Model):
    chalet = models.ForeignKey(
        Chalet, on_delete=models.CASCADE, related_name="room_managements", null=True
    )
    # number_of_room = models.IntegerField(null=True, blank=True)

    room_number = models.CharField(max_length=10, null=True, blank=True) 
    room_name = models.CharField(max_length=255, null=True, blank=True) 

    number_of_bathroom = models.IntegerField(null=True, blank=True)
    number_of_bed = models.IntegerField(null=True, blank=True)
    total_occupency = models.IntegerField(null=True, blank=True)
    # price_per_night = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amenities = models.ManyToManyField(Amenity, blank=True)
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("deleted", "Deleted"),
    ]

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="active",
    )

    created_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.chalet.name} ----->>>>"


class ChaletTransaction(models.Model):
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
    transaction_amount = models.DecimalField(max_digits=10, decimal_places=3)
    transaction_status = models.CharField(max_length=50, choices=TRANSACTION_STATUSES)
    transaction_reference_no = models.CharField(max_length=100)
    payment_status = models.CharField(max_length=50, choices=PAYMENT_STATUSES)
    payment_gateway = models.CharField(max_length=100)

    created_date = models.DateTimeField(default=timezone.now,null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return self.transaction_id + " - " + self.payment_status
    

class ChaletBooking(models.Model):
    
    BOOKING_STATUS = [
        ('pending', 'Pending'), # Awaiting vendor approval
        ('booked', 'Booked'), # Vendor confirmed
        ('confirmed', 'Confirmed'), # User paid and confirmed
        ('rejected', 'Rejected'), # Cancelled by vendor
        ('expired', 'Expired'), # Expired because no payment from user
        ('cancelled', 'Cancelled'), # Cancelled either by user or admin
        ('completed', 'Completed'), # Completed
        ('check-in', 'Check-In'), # when customer gets check in on the hotel
        ('check-out', 'Check-Out'),
    ]
    
    CANCELLED_BY = [
        ('vendor', 'Vendor'), # Cancelled by Vendor but not to consider now because as per our current flow, Vendor cannot cancel the booking once confirmed
        ('user', 'User'), # Cancelled by User
        ('admin', 'Admin'), # Cancelled by Admin
    ]


    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, blank=True, null=True,related_name='bookings'
    )
    user = models.ForeignKey(Userdetails, on_delete=models.CASCADE, null=True)
    chalet = models.ForeignKey(Chalet, on_delete=models.CASCADE, null=True)
    booking_fname = models.CharField(max_length=20, null=True)
    booking_lname = models.CharField(max_length=20, null=True)
    booking_email = models.EmailField(max_length=254, null=True)
    booking_mobilenumber = models.CharField(max_length=20, null=True)
    checkin_date = models.DateField()
    checkout_date = models.DateField()
    check_in_time = models.TimeField(null=True)
    check_out_time = models.TimeField(null=True)
    discount_price = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True
    )
    service_fee = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True
    )
    booked_price = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True
    )
    number_of_guests = models.IntegerField()
    adults=models.IntegerField(default=0)
    children=models.IntegerField( default=0)
    number_of_booking_rooms = models.IntegerField(null=True)
    is_my_self = models.BooleanField(default=False, null=True)
    booking_id = models.CharField(max_length=20, null=True)
    booking_date = models.DateField(default=timezone.now)
    promocode_applied = models.CharField(max_length=20, null=True, blank=True)
    discount_percentage_applied = models.CharField(max_length=20, null=True, blank=True)
    created_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    is_deleted=models.BooleanField(default=False)
    cancelled_by=models.CharField(max_length=6,null=True,blank=True,choices=CANCELLED_BY,default=None)
    status = models.CharField(max_length=20, choices=BOOKING_STATUS, default='pending')
    tax_and_services = models.DecimalField(max_digits=10, decimal_places=3, default=0.0, null=True, blank=True)
    # New fields for security token and QR code URL
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=False)
    qr_code_url = models.URLField(max_length=255, blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.chalet.name} ----->>>>  {self.booking_fname}  ------->>>>>>"

    def get_guest_full_name(self):
        """Return the full name of the guest."""
        if self.booking_fname and self.booking_lname:
            return f"{self.booking_fname} {self.booking_lname}"
        elif self.booking_fname:
            return self.booking_fname
        elif self.booking_lname:
            return self.booking_lname
        return "Unknown Guest"
    def save(self, *args, **kwargs):
        """Automatically generate booking ID only when creating a new object."""
        if not self.pk:  # Object is being created
            super().save(*args, **kwargs)  # Save first to generate a primary key
            self.booking_id = f"CHBK{self.pk}"
            kwargs['force_insert'] = False  # Ensure it's not treated as a new insert
        super().save(*args, **kwargs)  # Save with the booking_id

    

class ChaletMealPrice(models.Model):
    meal_type_choices = [
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('dinner', 'Dinner'),
    ]
    
    meal_type = models.CharField(max_length=10, choices=meal_type_choices)
    price = models.DecimalField(max_digits=7, decimal_places=3)
    chalet = models.ForeignKey(Chalet,on_delete=models.CASCADE, null=True)
    created_date = models.DateTimeField(default=timezone.now,null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    def __str__(self) -> str:
        return f"{self.chalet.name}-{self.meal_type}-{self.price}"


class ChaletRecentReview(models.Model):
    RATING = (
        (1.0, "1 Rating"),
        (2.0, "2 Rating"),
        (3.0, "3 Rating"),
        (4.0, "4 Rating"),
        (5.0, "5 Rating"),
    )
    chalet_booking = models.ForeignKey(ChaletBooking,on_delete=models.CASCADE,null=True)
    chalet = models.ForeignKey(Chalet,on_delete=models.CASCADE,null=True)
    rating = models.DecimalField(null=True, blank=True, choices=RATING,max_digits=2, decimal_places=1,default=0.0)
    username = models.CharField(max_length=255,null=True, blank=True)
    date = models.DateTimeField(null=True)
    review_text = models.TextField(null=True, blank=True)    
    respond = models.TextField(null=True, blank=True)
    
    created_date = models.DateTimeField(default=timezone.now,null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)

    
class ChaletFavorites(models.Model):
    user = models.ForeignKey(Userdetails, on_delete=models.CASCADE, null=True)
    chalet = models.ForeignKey(Chalet, on_delete=models.CASCADE, null=True)
    is_liked = models.BooleanField(default=True)
    created_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self) -> str:
        return f'{self.user.user.first_name} ------->   {self.chalet.name}'

class CancelChaletBooking(models.Model):
    user = models.ForeignKey(Userdetails, on_delete=models.CASCADE, null=True)
    booking = models.ForeignKey(ChaletBooking, on_delete=models.CASCADE, null=True)
    reason = models.CharField(max_length=200, blank=True, null=True, default=None)

    created_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.user.user.first_name} -------> {self.booking.chalet.name} -------> {self.booking.booking_fname}"

class Promotion(models.Model):
    PROMOTION_TYPE_CHOICES = [
        ('early_bird', 'Early Bird'),
        ('last_minute', 'Last Minute'),
        ('long_stay', 'Long Stay'),
        ('weekend', 'Weekend Getaway'),
        ('romantic', 'Romantic Package'),
        ('family', 'Family Package'),
        ('business', 'Business Traveler Offer'),
        ('staycation', 'Staycation Deal'),
        ('group_booking', 'Group Booking Discount'),
        ('loyalty', 'Loyalty Program'),
        ('seasonal', 'Seasonal Promotion'),
        ('spa', 'Spa and Wellness Offer'),
        ('free_night', 'Free Night Offer'),
        ('referral', 'Referral Program'),
        ('special_occasion', 'Special Occasion'),
        ('promo_code', 'Promo Code'),  # New promo code type
        ('common','Common')  
    ]

    CATEGORY_CHOICES = [
        ('common', 'Common Promotion'),
        ('promo_code', 'Promo Code Specific'),
        ('targeted_offers', 'Targeted Offers'),
        ('seasonal_event', 'Seasonal & Special Events'),
        ('loyalty_program', 'Referral & Loyalty Programs'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('deleted', 'Deleted'),
    ]

    SOURCE_CHOICES = [
        ('hotel', 'Hotel'),
        ('chalet', 'Chalet'),
        ('admin', 'Admin'),
    ]



    hotel = models.ForeignKey(Hotel, related_name='promotions', on_delete=models.CASCADE,blank=True,null=True)
    chalet = models.ForeignKey(Chalet, related_name='chalet_promotions', on_delete=models.CASCADE,blank=True,null=True)
    multiple_hotels = models.ManyToManyField(Hotel, related_name='admin_promotions', blank=True)
    multiple_chalets = models.ManyToManyField(Chalet, related_name='admin_chalet_promotions', blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    promotion_type = models.CharField(max_length=50, choices=PROMOTION_TYPE_CHOICES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES,null=True)  # Add category field
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')  # New status field
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='admin')  # New source field


    # Common promotion fields
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    free_night_offer = models.BooleanField(default=False)
    min_nights_stay = models.PositiveIntegerField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Promo code specific fields
    promo_code = models.CharField(max_length=20, null=True, blank=True) 
    max_uses = models.PositiveIntegerField(null=True, blank=True)  
    uses_left = models.PositiveIntegerField(null=True, blank=True)  
    minimum_spend = models.PositiveIntegerField(null=True, blank=True)  


    # Flags for targeted offers
    early_bird = models.BooleanField(default=False)
    last_minute = models.BooleanField(default=False)
    for_families = models.BooleanField(default=False)
    for_couples = models.BooleanField(default=False)
    for_business = models.BooleanField(default=False)
    group_booking = models.BooleanField(default=False)
    loyalty_program = models.BooleanField(default=False)
    referral_program = models.BooleanField(default=False)
    seasonal_offer = models.BooleanField(default=False)
    spa_offer = models.BooleanField(default=False)

    # Seasonal and special event fields
    special_occasion = models.BooleanField(default=False)
    occasion_name = models.CharField(max_length=100, null=True, blank=True)  # For things like Christmas, New Year, etc.

    # Referral and loyalty program fields
    points_required = models.PositiveIntegerField(null=True, blank=True)  # For loyalty programs
    referred_by = models.ForeignKey(VendorProfile, null=True, blank=True, related_name='referrals_made', on_delete=models.SET_NULL)
    discount_value = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    
    def __str__(self) -> str:
        return f"{self.hotel}-{self.category}-{self.discount_percentage}"

class Comparison(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('deleted', 'Deleted'),
    ]
    
    TYPE_CHOICES = [
        ('hotel', 'Hotel'),
        ('chalet', 'Chalet'),
    ]

    user = models.ForeignKey(Userdetails, on_delete=models.CASCADE)  
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, blank=True, null=True)  
    chalet = models.ForeignKey(Chalet, on_delete=models.CASCADE, blank=True, null=True)
    created_by = models.ForeignKey(Userdetails, related_name='created_comparisons', on_delete=models.SET_NULL, null=True)
    modified_by = models.ForeignKey(Userdetails, related_name='modified_comparisons', on_delete=models.SET_NULL, null=True)
    created_date = models.DateTimeField(default=timezone.now)
    modified_date = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)

    def __str__(self):
        return f"Comparison by {self.user} on {self.created_date} - Type: {self.type} - Status: {self.status}"
    
class Featured(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('deleted', 'Deleted'),
    ]
    
    TYPE_CHOICES = [
        ('hotel', 'Hotel'),
        ('chalet', 'Chalet'),
    ]
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, blank=True, null=True)  
    chalet = models.ForeignKey(Chalet, on_delete=models.CASCADE, blank=True, null=True)
    valid_from=models.DateField(default=timezone.now)
    valid_to=models.DateField(default=timezone.now)
    created_by = models.ForeignKey(VendorProfile, related_name='created_featured', on_delete=models.SET_NULL, null=True)
    modified_by = models.ForeignKey(VendorProfile, related_name='modified_featured', on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    def __str__(self):
        if self.hotel:
            return self.hotel.name  
        elif self.chalet:
            return self.chalet.name 
  



class Notification(models.Model):
    
    NOTIFICATION_TYPES = [
        ('booking_new', 'New Booking'),
        ('booking_cancel', 'Booking Cancellation'),
        ('booking_reject','Booking Rejected'),
        ('booking_modify', 'Booking Modification'),
        ('review_new', 'New Review'),
        ('document_upload', 'Document Uploaded'),
        ('promotion', 'Promotion Update'),
        ('payment', 'Payment/Transaction Update'),
        ('availability', 'Availability Update'),
        ('policy_update', 'Policy Update'),
        ('favorite', 'Added to Favorites'),
        ('admin_report', 'Admin Report'),  # For admin-specific notifications
        ('admin_feedback', 'User Feedback for Admin'),  # For admin-specific notifications
        ('add_money_to_wallet','Add Money To Wallet'),
        ('deduct_money_from_wallet','Deduct Money From Wallet')
    ]
    
    SOURCE_CHOICES = [
        ('hotel', 'Hotel'),
        ('chalet', 'Chalet')
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    message_arabic = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    source = models.CharField(max_length=10, choices=SOURCE_CHOICES,null=True, blank=True)
    related_booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
    chalet_booking = models.ForeignKey(ChaletBooking, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
    related_room = models.ForeignKey(Roomtype, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
    related_promotion = models.ForeignKey(Promotion, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
    related_wallet = models.ForeignKey(Wallet, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")

    def mark_as_read(self):
        self.is_read = True
        self.save()

    def __str__(self):
        user_type = "Vendor" if self.recipient.is_vendor else "Admin"
        return f"{self.get_notification_type_display()} for {self.recipient.first_name} - Read: {self.is_read}"

class ChaletWeekendPrice(models.Model):
    chalet = models.OneToOneField(
        Chalet, on_delete=models.CASCADE, related_name="weekend_price"
    )
    weekend_price = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    is_active = models.BooleanField(default=True)
    created_date = models.DateTimeField(default=timezone.now)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Weekend Price for {self.chalet.name}: {self.weekend_price}"

    def is_active(self):
        """Check if the weekend price is currently active."""
        return self.is_active
class ChaletAcceptedPayment(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    slug=models.SlugField(unique=True,null=True,blank=True)
    chalet = models.OneToOneField(Chalet, on_delete=models.CASCADE, null=True)
    created_by = models.ForeignKey(VendorProfile, related_name='chalet_accpt_payment_created', on_delete=models.SET_NULL, null=True)
    modified_by = models.ForeignKey(VendorProfile, related_name='chalet_accpt_payment_modified', on_delete=models.SET_NULL, null=True)    
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    payment_types=models.ManyToManyField(PaymentType,related_name="chalet_payment_types_set")
    is_deleted=models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(self, 'chalet')
        super().save(*args, **kwargs)


    def __str__(self) -> str:
        return f'{self.chalet.name}'
    
from django.core.validators import MinValueValidator, MaxValueValidator 
class ChaletTax(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    chalet = models.ForeignKey(Chalet, on_delete=models.CASCADE, related_name='chalet_taxes')
    tax = models.ForeignKey(Tax, on_delete=models.CASCADE, related_name='chalet_taxes')
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0.00), MaxValueValidator(100.00)]
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active", db_index=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        VendorProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="chalet_taxes_created"
    )
    modified_by = models.ForeignKey(
        VendorProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="chalet_taxes_modified"
    )
    created_date = models.DateTimeField(default=timezone.now)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.tax and self.tax.name: 
            return f"{self.tax.name} - {self.percentage}%" if self.percentage else f"{self.tax.name}"
        return super().__str__()

    class Meta: 
        verbose_name_plural = "Chalet Taxes" 
        constraints = [ 
            models.UniqueConstraint(fields=["chalet", "tax"], name="unique_chalet_tax") 
        ]
    chalet = models.ForeignKey(Chalet, on_delete=models.CASCADE, related_name='chalet_taxes')
    tax = models.ForeignKey(Tax, on_delete=models.CASCADE, related_name='chalet_taxes')
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Percentage of the tax")
    is_active = models.BooleanField(default=True)
    created_date = models.DateTimeField(default=timezone.now)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tax.name} ({self.tax_percentage}%) for {self.chalet.name}"

    class Meta:
        verbose_name_plural = "Chalet Taxes"
        unique_together = ('chalet', 'tax')


class ChaletBookingTransaction(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('in-active', 'In-Active'),
    ]

    booking = models.ForeignKey(ChaletBooking, on_delete=models.SET_NULL, null=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(Userdetails, on_delete=models.SET_NULL, null=True)
    modified_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"Chalet Booking Transaction {self.id}"
