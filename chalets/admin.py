from django.contrib import admin
from chalets.models import *
# Register your models here.
admin.site.register(Chalet)
admin.site.register(ChaletImage)
admin.site.register(chaletDocument)
admin.site.register(PropertyManagement)
admin.site.register(ChaletTransaction)
admin.site.register(ChaletBooking)
admin.site.register(ChaletMealPrice)
admin.site.register(ChaletRecentReview)
admin.site.register(ChaletFavorites)
admin.site.register(CancelChaletBooking)
admin.site.register(Promotion)
admin.site.register(Comparison)
admin.site.register(Featured)
admin.site.register(Notification)
admin.site.register(ChaletWeekendPrice)
admin.site.register(ChaletAcceptedPayment)
admin.site.register(ChaletTax)

