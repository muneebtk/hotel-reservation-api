from django.urls import path
from django.contrib.auth.views import LogoutView
from django.conf.urls.static import static
from Bookingapp_1969 import settings
from .views import *
urlpatterns = [
    path('privacy-policy/', PrivacyPolicyView.as_view(), name='privacy-policy'),
    path('terms-and-conditions/', TermsAndConditionView.as_view(), name='privacy-policy'),
    path('about-us/', AboutUsView.as_view(), name='privacy-policy'),
]
