from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from user.models import *

# Register your models here.
UserAdmin.fieldsets += (
    ('Custom Fields', {'fields': ('is_vendor', 'is_deleted')}),
)

UserAdmin.list_display += ('is_vendor', 'is_deleted')
UserAdmin.list_filter += ('is_vendor', 'is_deleted')
admin.site.register(User, UserAdmin)
admin.site.register(Userdetails)
admin.site.register(VendorProfile)
admin.site.register(Storeotp)
admin.site.register(Referral)
admin.site.register(Wallet)
admin.site.register(WalletTransaction)
admin.site.register(OnlineWalletTansaction)

