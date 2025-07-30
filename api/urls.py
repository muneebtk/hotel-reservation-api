from django.urls import path
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from api.views import *

urlpatterns = [
    path('v1/auth/signup',RegisterUser.as_view()),
    path('v1/auth/verify-email',Emailverifyusinfotp.as_view()),
    path('v1/auth/resend-email/<str:email>',ResendEmail.as_view()),
    path('v1/auth/login',LoginUser.as_view()),
    path('v1/auth/google-sign-in/', GoogleLoginView.as_view(), name='google-sign-in'),
    path('v1/auth/facebook-signin/',FacebookLoginView.as_view(),name='facebook-signin'),
    path('v1/auth/apple-signin/', AppleLoginView.as_view(), name='apple-signin'),
    path('v1/auth/mobile-login',Mobilelogin.as_view()),
    path('v1/auth/verify-mobile-otp/<str:username>',Verifymobileotp.as_view()),
    path('v1/auth/resent-mobile-otp/<str:username>',Resendmobileotp.as_view()),
    path('get-email',Forgotpassword_email.as_view()),
    path('reset-password/<int:id>/<str:token>/',Resetpassword.as_view(),name="confirm_password_reset"),
    path('user-detail',Getuserdetail.as_view()),
    path('check-authentication/', CheckAuthentication.as_view(), name='check_authentication'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('user/category',categoryList.as_view()),
    path('<str:input_string>/search',HotelSearch.as_view()),
    path('properties/<int:pk>',Propertydetail.as_view()),
    path('properties/<int:pk>/room-listing',RoomListing.as_view()),
    path('properties/<int:id>/book',BookRoom.as_view()),
    path('booking/<int:id>/pay',CreatePayment.as_view()),
    path('booking/<int:id>',BookingDetailApiView.as_view()),
    path('properties/book-list',Bookedlist.as_view()),
    path('properties/rating-review',Ratingrivew.as_view()),
    path('properties/favorites',Favoritesmanagement.as_view()),
    path('properties/cancel-booking',CancelbookingView.as_view()),
    path('properties/<int:id>/review-rating-filter',Reviewratingfilter.as_view()),
    path('profile/', UserProfileView.as_view()),
    path('test-500/', Test500ErrorView.as_view()),

    path('top-hotels/', TopHotelsAPIView.as_view(), name='top-hotels'),
    path('todays-offers/', TodaysOffersAPIView.as_view(), name='todays_offers'),
    path('chalet-favorites/', ChaletFavoritesmanagement.as_view(), name='chalet_favorites_management'),
    path('chalet/book-list',ChaletBookedList.as_view()),
    path('chalet/cancel-booking',CancelChaletBookingView.as_view()),
    path('chalet/rating-review',ChaletReview.as_view()),
    path('top-chalets/', FeaturedChaletsAPIView.as_view(), name='top-hotels'),
    path('sort-chalets/', ChaletSearchView.as_view()),
    path('search_promocodes/', PromoCodeSearch.as_view(), name='search_promocodes'),
    path('convert_currency/', CurrencyConversionAPIView.as_view(), name='convert_currency'),
    path('today_offer/', TodayOffer.as_view(), name='today-offer'),
    path('daily_deals/', DailyDeals.as_view(), name='daily-deals'),
    path('check-promocode/', CheckPromoCodeView.as_view(), name='check-promocode'),
    path('comparison/<str:property_type>/', ComparisonApiView.as_view(), name='comparison'),
    path('wallet/add-funds/', AddFundsView.as_view(), name='add_funds'),
    path('wallet/withdraw-funds/', WithdrawFundsView.as_view(), name='withdraw_funds'),
    path('featured/',featuredview.as_view(),name='featured'),
    path('generate-referral-token/', GenerateReferralTokenAPI.as_view(), name='generate_referral_token'),
    path('v1/promo-codes/', PromoCodesAPIView.as_view(), name='promo-codes'),
    path('booking-calculation/',BookingCalculationAPIView.as_view(),name='bookingcalculation'),
    path('notification/',NotificationAPIView.as_view(),name='notification'),
    path('booking/<int:id>/refund/eligibility/',Refund_eligibility.as_view(),name='refund_eligibility'),
    path('accepted-payments/', PaymentsAcceptedApiView.as_view(), name='payment_accepted'),
    path('delete-account',DeleteAccountAPIView.as_view(), name='delete_account')
    

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from rest_framework import routers
router = routers.DefaultRouter()
router.register(r'^chalets',ChaletModelViewSet,basename='api-chalets')
router.register(r'^bookings', ChaletBookingViewSet,basename='chalet-booking')
urlpatterns+=router.urls