from django.contrib import admin
from common.models import *

# Register the other models
admin.site.register(Country)
admin.site.register(State)
admin.site.register(City)
admin.site.register(Amenity)
admin.site.register(Categories)
admin.site.register(PolicyCategory)
admin.site.register(PolicyName)
admin.site.register(PaymentType)
admin.site.register(PaymentTypeCategory)
admin.site.register(Tax)
admin.site.register(ChaletType)
admin.site.register(Transaction)
admin.site.register(AdminTransaction)
admin.site.register(RefundTransaction)
admin.site.register(PaymentGatewayLog)
admin.site.register(OwnerName)


