from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from vendor.models import Hotel
from chalets.models import Chalet
from user.models import VendorProfile


class CustomLoginRequiredMixin(LoginRequiredMixin):
    login_url = '/vendor/login/'
    dashboard_url = '/vendor/dashboard/'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        try:
            user = VendorProfile.objects.get(user=request.user)
            print("User Profile:", user)

            if user.category == "admin" or user.category == "superadmin":
                print("Admin detected, granting access")
                return super().dispatch(request, *args, **kwargs)

            hotel_approved = False
            chalet_approved = False

            try:
                hotel = Hotel.objects.filter(vendor=user.id).first()
                if hotel and hotel.approval_status == "approved":
                    hotel_approved = True
            except Hotel.DoesNotExist:
                pass

            try:
                chalet = Chalet.objects.filter(vendor=user.id).first()
                if chalet and chalet.approval_status == "approved":
                    chalet_approved = True
            except Chalet.DoesNotExist:
                pass
            
            print(f"Hotel Approved: {hotel_approved}")
            print(f"Chalet Approved: {chalet_approved}")

            # if  hotel_approved == False or  chalet_approved == False:
            if (hotel_approved == False and  chalet_approved == True ) or (chalet_approved == False and  hotel_approved == True):
                return redirect(self.dashboard_url)
            
            elif not hotel_approved and not chalet_approved:
                print("Both hotel and chalet are rejected, redirecting to login")
                return redirect(self.login_url)
            
        except VendorProfile.DoesNotExist:
            print(f"VendorProfile does not exist, redirecting to login:{user.username}")
            return redirect(self.login_url)

        return super().dispatch(request, *args, **kwargs)
