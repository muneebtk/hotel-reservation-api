from django.contrib import admin

from vendor.models import *
# Register your models here.


admin.site.register(Roomtype)
admin.site.register(Hotel)
admin.site.register(RoomManagement)
# admin.site.register(Offer)
admin.site.register(RecentReview)
# admin.site.register(PromoCode)
admin.site.register(HotelTransaction)
admin.site.register(RoomImage)
admin.site.register(HotelImage)
admin.site.register(HotelDocument)
admin.site.register(MealPrice)
admin.site.register(CommissionSlab)
admin.site.register(Bookedrooms)
admin.site.register(Favorites)
admin.site.register(Cancelbooking)
admin.site.register(HotelAcceptedPayment)
admin.site.register(HotelType)
admin.site.register(HotelTax)
@admin.register(Booking)
@admin.register(MealTax)
class BookingAdmin(admin.ModelAdmin):
    readonly_fields = ('modified_date',)

admin.site.register(RefundPolicyCategory)
admin.site.register(RefundPolicy)
admin.site.register(RoomRefundPolicy)
admin.site.register(WeekendPrice)
admin.site.register(VendorTransaction)
