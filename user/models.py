from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils import timezone
from django.db.models import Q

class User(AbstractUser):
    is_vendor = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    email = models.EmailField(unique=False)
    

    # Add related_name attributes to avoid conflicts
    groups = models.ManyToManyField(
        Group,
        related_name='custom_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='custom_user_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email', 'is_vendor'],
                condition=Q(is_deleted=False),
                name='unique_email_for_vendor_not_deleted'
            )
        ]

class Userdetails(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_details', null=True)
    contact_number = models.CharField(max_length=15, null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, blank=True)
    image = models.ImageField(upload_to='profile_images/', null=True, blank=True) 
    operating_system = models.CharField(max_length=50, null=True, blank=True)
    dial_code=models.CharField(max_length=50,null=True,blank=True,default='+968')
    iso_code=models.CharField(max_length=10, null=True,blank=True,default='OM')
    firebase_token = models.CharField(max_length=255, null=True, blank=True) 
    created_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return self.user.username if self.user else "No User"

class VendorProfile(models.Model):
    CATEGORY_CHOICES = [
        ('admin', 'Admin'),
        ('superadmin', 'Super Admin'),
        ('vendor', 'Vendor'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_profile')
    name = models.CharField(max_length=100, null=True, blank=True)
    contact_number = models.CharField(max_length=15, null=True, blank=True)
    gsm_number = models.CharField(max_length=15, null=True, blank=True) 
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='vendor')

    def __str__(self):
        return f"{self.user.username} - {self.get_category_display()}" if self.user else "No User"

class Storeotp(models.Model):
    LOGIN_TYPE = [
        ('mobile_otp', 'mobile_otp'),
        ('email_otp', 'email_otp')
    ]
    user = models.ForeignKey(Userdetails, on_delete=models.CASCADE, null=True)
    otp = models.IntegerField(null=True, blank=True)
    catogory = models.CharField(max_length=10, choices=LOGIN_TYPE, null=True, blank=True)
    created_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)

class Wallet(models.Model):
    STATUS = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )
    user = models.OneToOneField(Userdetails, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=11, decimal_places=3, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=15, choices=STATUS,null=True, blank=True)
    
    def __str__(self):
        return f"User: {self.user} ----- >  Balance: {self.balance}"

class WalletTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    )

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    transaction_id = models.CharField(max_length=36, unique=True)
    transaction_type = models.CharField(max_length=6, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=11, decimal_places=3)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.transaction_id}"
    
class OnlineWalletTansaction(models.Model):
    TRANSACTION_TYPES = (
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    )

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    transaction_id = models.CharField(max_length=36, unique=True)
    transaction_type = models.CharField(max_length=6, choices=TRANSACTION_TYPES)
    total_amount = models.DecimalField(max_digits=11, decimal_places=3)
    user_amount = models.DecimalField(max_digits=11, decimal_places=3,null=True, blank=True)
    bank_charge = models.DecimalField(max_digits=11, decimal_places=3,null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)



class Referral(models.Model):
    referrer = models.ForeignKey(Userdetails, on_delete=models.CASCADE, related_name='sent_referrals')
    token = models.CharField(max_length=64)  # Unique token for tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, default='pending')  # pending, successful, etc.
    referee = models.ForeignKey(Userdetails, on_delete=models.SET_NULL, null=True, blank=True, related_name='referral_from')

    class Meta:
        
        unique_together = ('referrer', 'referee')
    def __str__(self):
        return f"Referral from {self.referrer.username} to {self.referee.username if self.referee else 'Unknown'}"

