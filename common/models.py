from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from .function import generate_unique_slug
from django.utils.translation import gettext_lazy as _
from user.models import Userdetails
from deep_translator import GoogleTranslator

User = get_user_model()

import logging
logger = logging.getLogger('lessons')

class Country(models.Model):
    name = models.CharField(max_length=50, null=True)
    tax = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    currency = models.CharField(max_length=10, null=True,blank=True)

    
    CURRENCY_MAP = {
          # North America
        "united states": "USD",  # United States Dollar
        "canada": "CAD",  # Canadian Dollar
        "mexico": "MXN",  # Mexican Peso

        # Europe
        "united kingdom": "GBP",  # British Pound Sterling
        "germany": "EUR",  # Euro
        "france": "EUR",  # Euro
        "italy": "EUR",  # Euro
        "spain": "EUR",  # Euro
        "netherlands": "EUR",  # Euro
        "sweden": "SEK",  # Swedish Krona
        "norway": "NOK",  # Norwegian Krone
        "switzerland": "CHF",  # Swiss Franc
        "russia": "RUB",  # Russian Ruble
        "poland": "PLN",  # Polish Zloty
        "hungary": "HUF",  # Hungarian Forint
        "romania": "RON",  # Romanian Leu
        "czech republic": "CZK",  # Czech Koruna
        "bulgaria": "BGN",  # Bulgarian Lev
        "ukraine": "UAH",  # Ukrainian Hryvnia
        "georgia": "GEL",  # Georgian Lari
        "armenia": "AMD",  # Armenian Dram
        "azerbaijan": "AZN",  # Azerbaijani Manat

        # Asia
        "india": "INR",  # Indian Rupee
        "china": "CNY",  # Chinese Yuan
        "japan": "JPY",  # Japanese Yen
        "south korea": "KRW",  # South Korean Won
        "indonesia": "IDR",  # Indonesian Rupiah
        "malaysia": "MYR",  # Malaysian Ringgit
        "singapore": "SGD",  # Singapore Dollar
        "thailand": "THB",  # Thai Baht
        "vietnam": "VND",  # Vietnamese Dong
        "philippines": "PHP",  # Philippine Peso
        "pakistan": "PKR",  # Pakistani Rupee
        "bangladesh": "BDT",  # Bangladeshi Taka
        "sri lanka": "LKR",  # Sri Lankan Rupee
        "nepal": "NPR",  # Nepalese Rupee
        "maldives": "MVR",  # Maldivian Rufiyaa
        "kazakhstan": "KZT",  # Kazakhstani Tenge
        "uzbekistan": "UZS",  # Uzbekistani Som
        "turkmenistan": "TMT",  # Turkmenistani Manat
        "kyrgyzstan": "KGS",  # Kyrgyzstani Som
        "tajikistan": "TJS",  # Tajikistani Somoni
        "taiwan": "TWD",  # New Taiwan Dollar
        "hong kong": "HKD",  # Hong Kong Dollar
        "mongolia": "MNT",  # Mongolian Tögrög
        "macau": "MOP",  # Macanese Pataca

        # Middle East and North Africa
        "saudi arabia": "SAR",  # Saudi Riyal
        "united arab emirates": "AED",  # UAE Dirham
        "qatar": "QAR",  # Qatari Riyal
        "kuwait": "KWD",  # Kuwaiti Dinar
        "oman": "OMR",  # Omani Rial
        "bahrain": "BHD",  # Bahraini Dinar
        "jordan": "JOD",  # Jordanian Dinar
        "egypt": "EGP",  # Egyptian Pound
        "morocco": "MAD",  # Moroccan Dirham
        "lebanon": "LBP",  # Lebanese Pound
        "iraq": "IQD",  # Iraqi Dinar
        "algeria": "DZD",  # Algerian Dinar
        "tunisia": "TND",  # Tunisian Dinar
        "yemen": "YER",  # Yemeni Rial
        "syria": "SYP",  # Syrian Pound
        "libya": "LYD",  # Libyan Dinar
        "sudan": "SDG",  # Sudanese Pound
        "israel": "ILS",  # Israeli New Shekel
        "turkey": "TRY",  # Turkish Lira

        # Africa
        "nigeria": "NGN",  # Nigerian Naira
        "south africa": "ZAR",  # South African Rand
        "kenya": "KES",  # Kenyan Shilling
        "ghana": "GHS",  # Ghanaian Cedi
        "ethiopia": "ETB",  # Ethiopian Birr
        "tanzania": "TZS",  # Tanzanian Shilling

        # Oceania
        "australia": "AUD",  # Australian Dollar
        "new zealand": "NZD",  # New Zealand Dollar
        "fiji": "FJD",  # Fijian Dollar
        "papua new guinea": "PGK",  # Papua New Guinean Kina

        # South America
        "brazil": "BRL",  # Brazilian Real
        "argentina": "ARS",  # Argentine Peso
        "chile": "CLP",  # Chilean Peso
        "colombia": "COP",  # Colombian Peso
        "peru": "PEN",  # Peruvian Sol

        # Central America and the Caribbean
        "cuba": "CUP",  # Cuban Peso
        "dominican republic": "DOP",  # Dominican Peso
        "jamaica": "JMD",  # Jamaican Dollar
        "haiti": "HTG",  # Haitian Gourde
        "panama": "PAB",  # Panamanian Balboa
    }

    def save(self, *args, **kwargs):
        if self.name:
            normalized_name = self.name.lower()
            if not self.currency and normalized_name in self.CURRENCY_MAP:
                self.currency = self.CURRENCY_MAP[normalized_name]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name

class State(models.Model):
    country = models.ForeignKey(Country,on_delete=models.CASCADE,null=True)
    name = models.CharField(max_length=50,null=True)
    
    # def __str__(self) -> str:
    #     return self.name
    def __str__(self) -> str:
        return self.name if self.name else "Unnamed State"

class City(models.Model):
    state = models.ForeignKey(State, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=50, null=True,blank=True)
    # postal_code = models.TextField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    arabic_name = models.CharField(max_length=50, null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.arabic_name and not self.name:
            try:
                self.name = GoogleTranslator(source='ar', target='en').translate(self.arabic_name)
            except Exception as e:
                print(f"Error translating Arabic to English: {e}")
        
        if self.name and not self.arabic_name:
            try:
                self.arabic_name = GoogleTranslator(source='en', target='ar').translate(self.name)
            except Exception as e:
                print(f"Error translating English to Arabic: {e}")
        
        super(City, self).save(*args, **kwargs)


    def __str__(self):
        return self.name if self.name else "Unnamed City"

class Amenity(models.Model):
    AMENITY_TYPE_CHOICES = (
        ("Property_amenity", "Property_amenity"),
        ("Room_amenity", "Room_amenity"),
    )

    amenity_name = models.CharField(max_length=100,unique=True, blank=True, null=True)
    amenity_name_arabic = models.CharField(max_length=100, unique=True, blank=True, null=True)
    amenity_type = models.CharField(max_length=50, choices=AMENITY_TYPE_CHOICES, blank=True, null=True)
    icon = models.FileField(upload_to='amenity_icons/', blank=True, null=True)
    status = models.BooleanField(default=False)
    created_date = models.DateTimeField(default=timezone.now,null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)


    def __str__(self):
        return self.amenity_name if self.amenity_name else ""
    
class Categories(models.Model):
    CATEGORIES = (
        ('HOTEL','hotel_categories'),
        ('CHALET','chalets_categories')
    )
    
    category = models.CharField(max_length=20, null=True, choices=CATEGORIES)

    def __str__(self):
        return self.category
    
class PolicyCategory(models.Model):
    POLICY_CATEGORY_TYPE_CHOICES = [
        ('common', 'Common'), 
        ('vendor', 'Vendor-specific'),
    ]
    STATUS_CHOICES = [ 
    ('active', 'Active'), ('inactive', 'Inactive'), 
    ]
    SCOPE_CHOICES = [
    ('all', 'All'),
    ('hotel', 'Hotel'),
    ('chalet', 'Chalet'),
    ]

    name= models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField( max_length=10, choices=STATUS_CHOICES, default='active')
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default='all')    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    policy_type = models.CharField(max_length=10, choices=POLICY_CATEGORY_TYPE_CHOICES, default='vendor')
    created_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_by = models.ForeignKey( User, on_delete=models.SET_NULL, null=True, blank=True, related_name="deleted_policy_categories")
    def __str__(self):
        return self.name if self.name else ""

class PolicyName(models.Model):
    POLICY_TYPE_CHOICES = [
        ('common', 'Common'),  
        ('vendor', 'Vendor-specific'),    
    ]
    STATUS_CHOICES = [ 
    ('active', 'Active'), ('inactive', 'Inactive'),
    ]
    status = models.CharField( max_length=10, choices=STATUS_CHOICES, default='active')
    policy_category = models.ForeignKey(PolicyCategory, related_name='policy_names', on_delete=models.CASCADE)
    title = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    policy_type = models.CharField(max_length=10, choices=POLICY_TYPE_CHOICES, default='vendor')
    created_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    is_deleted = models.BooleanField(default=False) 
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="deleted_policy_names") 

    def __str__(self):
        return self.title if self.title else ""
class PaymentTypeCategory(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    REFUNDABLE_CHOICES = [
        ('refundable', 'Refundable'),
        ('non-refundable', 'Non-Refundable'),
    ]
    slug=models.SlugField(unique=True,null=True,blank=True)
    name=models.CharField(max_length=25,null=True,unique=True)
    name_arabic=models.CharField(max_length=30,null=True,unique=True)
    created_by = models.ForeignKey(User, related_name='created_payment_category', on_delete=models.SET_NULL, null=True)
    modified_by = models.ForeignKey(User, related_name='modified_payment_category', on_delete=models.SET_NULL, null=True)    
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    is_refundable = models.CharField(max_length=15, choices=REFUNDABLE_CHOICES, default='refundable')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    is_deleted=models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            # Use the common slug generation function
            self.slug = generate_unique_slug(self, 'name')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

   
class PaymentType(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    REFUNDABLE_CHOICES = [
        ('refundable', 'Refundable'),
        ('non-refundable', 'Non-Refundable'),
    ]
    slug=models.SlugField(unique=True,null=True,blank=True)
    name=models.CharField(max_length=25,null=True,unique=True)
    name_arabic=models.CharField(max_length=30,null=True,unique=True)
    category = models.ForeignKey(PaymentTypeCategory, on_delete=models.SET_NULL,null=True)
    created_by = models.ForeignKey(User, related_name='created_payment_type', on_delete=models.SET_NULL, null=True)
    modified_by = models.ForeignKey(User, related_name='modified_payment_type', on_delete=models.SET_NULL, null=True)    
    is_refundable = models.CharField(max_length=15, choices=REFUNDABLE_CHOICES, default='refundable')
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    is_deleted=models.BooleanField(default=False)

    
    def save(self, *args, **kwargs):
        try:
            if not self.slug:
                # Use the common slug generation function
                self.slug = generate_unique_slug(self, 'name')
            super().save(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error saving PaymentType: {e}")
            raise  # Re-raise the error after logging it

        
    def __str__(self):
        return self.name

class ChaletType(models.Model):
    STATUS_CHOICES = (
        ("active", _("Active")),
        ("inactive", _("Inactive")),
        ("deleted", _("Deleted")),
    )

    name = models.CharField(max_length=200, unique=True)
    arabic_name = models.CharField(max_length=200, unique=True, default="None")
    icon = models.ImageField(upload_to="chalet_types_icons/", null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='chalet_types_created')
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")

    def __str__(self):
        return self.name


class Tax(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    name = models.CharField(max_length=100, unique=True)
    name_arabic = models.CharField(max_length=100, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='taxes_created')
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active", db_index=True)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name_plural = "Taxes"


class Transaction(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('in-active', 'In-Active'),
    ]
    TRANSACTION_STATUS_CHOICES = [
        ('pending', _("Pending")),
        ('completed', _("Completed")),
        ('failed', _("Failed")),
    ]

    transaction_id = models.CharField(max_length=50, unique=True)
    ref_id = models.CharField(max_length=50, null=True, blank=True)
    amount = models.DecimalField(max_digits=11, decimal_places=3)
    payment_type = models.ForeignKey(PaymentType, on_delete=models.SET_NULL, null=True)
    transaction_status = models.CharField(max_length=10, choices=TRANSACTION_STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="transactions_created")
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="transactions_modified")
    modified_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return self.transaction_id
    

class AdminTransaction(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('in-active', 'In-Active'),
    ]

    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, related_name="admin_transaction")
    gateway_fee = models.DecimalField(max_digits=11, decimal_places=3, default=0.000)  # Payment processing fee
    admin_gateway_fee = models.DecimalField(max_digits=11, decimal_places=3, default=0.000)  # Additional fee by admin
    admin_commission = models.DecimalField(max_digits=11, decimal_places=3, default=0.000)  # Super admin earnings

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(Userdetails, on_delete=models.SET_NULL, null=True)
    modified_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"Admin Transaction for {self.transaction.transaction_id if self.transaction else 'N/A'}"
    @property
    def actual_gateway_fee(self):
        return self.gateway_fee - self.admin_gateway_fee

    class Meta:
        indexes = [
            models.Index(fields=['transaction']),
        ]

class RefundTransaction(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('in-active', 'In-Active'),
    ]
    REFUND_STATUS_CHOICES = [
        ('Pending', 'Pending'), 
        ('Processed', 'Processed'), 
        ('Rejected', 'Rejected')
    ]

    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, related_name="refunds")
    refund_status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='Pending')
    reason = models.TextField(blank=True, null=True)
    processed_date = models.DateTimeField(null=True, blank=True)
    is_partial_refund = models.BooleanField(default=False) 
    amount = models.DecimalField(max_digits=11, decimal_places=3,default=0.0)
   
    created_at = models.DateField(auto_now_add=True)
    created_by = models.ForeignKey(Userdetails, on_delete=models.SET_NULL, null=True)
    modified_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"Refund for {self.transaction.transaction_id if self.transaction else 'N/A'} - {self.refund_status}"

    class Meta:
        indexes = [
            models.Index(fields=['transaction']),
            models.Index(fields=['status']),
        ]


class PaymentGatewayLog(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, related_name="gateway_log")
    gateway_response = models.JSONField()  # Store full API response
    status_code = models.IntegerField()
    success = models.BooleanField(default=False)

    created_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Log for {self.transaction.transaction_id if self.transaction else 'N/A'}"

    class Meta:
        indexes = [
            models.Index(fields=['transaction']),
            models.Index(fields=['status_code']),
        ]

class OwnerName(models.Model):
    owner_name=models.CharField(max_length=200, null=True, blank=True)
    owner_name_arabic = models.CharField(max_length=200, null=True, blank=True)
    def __str__(self):
        return f"{self.owner_name}------{self.owner_name_arabic}"
