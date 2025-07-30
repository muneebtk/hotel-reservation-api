from django.urls import path
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView
from Bookingapp_1969 import settings
from vendor.views import *

urlpatterns = [

    path('set_language/', SetLanguageView.as_view(), name='set_language'),
    path('login/', LoginView.as_view(), name='loginn'),
    path('pending/',PendingTemplateView.as_view(),name='pending'),
    path('pending_approval/',PendingApprovalTemplateView.as_view(),name='pending_approval'),

    path('logout/', LogoutView.as_view(next_page='loginn'), name='logout'),
    path('advertisment/', AdvertismentPageView.as_view(), name='advertisment'),
    path('advertisment/hotel/', HotelAdvertismentPageView.as_view(), name='advertisment_hotel'),

    path('chalet_check/', ChaletExistView.as_view(), name='chalet_check'),
    path('hotel_check/', HotelExistView.as_view(), name='hotel_check'),

    path('forgotpassword/',ForgotPasswordView.as_view(),name='Forgot_password'),
    path('password/reset/<uidb64>/<token>/',PasswordResetConfirmView.as_view(),name='password_reset_confirm'),


    path('check-email/', check_email_exists, name='email_exist'),
    path('hotel-register/<str:category>/', Register.as_view(), name='register_category'),
    path('register/<str:category>/', RgisterChaletview.as_view(), name='register'),

    path('ammenities/add/',AmenitiesaddView.as_view(),name="add_ammenities"),
    path('ammenities/add/back/',BackSelectedAmmenities.as_view(),name="back_add_ammenities"),
    path('price/add/',PriceAddView.as_view(),name="add_price"),
    path('price/add/back/',BackSelectedPrice.as_view(),name="back_add_price"),
    path('final/step/',FinalStepView.as_view(),name="final_step"),

    path("logout/", LogoutView.as_view(), name="logout"),
    path("dashboard/",DashboardView.as_view(),name="dashboard"),
    path("ViewAll/Booking/",ViewAllButton.as_view(),name="view_all"),

    path("booking/",BookingView.as_view(),name="booking"),
    path('hotel/table/list/',HotelListView.as_view(),name="hotel_table_list"),
    path('hotel/approval/<int:pk>/',HotelApprovalView.as_view(),name="hotel_approval"),

    path("book_detail/<int:pk>/",BookingDetail.as_view(),name="booking_detail"),
    path('past-bookings/', PastBookingsView.as_view(), name='past_bookings'),
    path('cancelled-appointments/', CancelledAppointmentsView.as_view(), name='cancelled_appointments'),


    path("room/",RoomManagementView.as_view(),name='roommanagement'),
    path("roommangement/booking/",RoomManagementBookedRoom.as_view(),name="roomanagement_booked"),
    path("roommanagement/add/",RoomManagementAddView.as_view(),name="room_add"),
    path("roommanagement/edit/<int:pk>/",RoomManagementEditview.as_view(),name="room_edit"),
    path("roommanagement/delete/<int:pk>/",RoomManagementDelete.as_view(),name="room_remove_view"),
    path('get-refund-policies/', get_refund_policies, name='get_refund_policies'),
    path("transaction/",TransactionDetailView.as_view(),name="transaction_detail"),
    # path("promocode/",PromoCodeView.as_view(),name="promocode"),
    # path("promocode/edit/<int:pk>/",PromoCodeEdit.as_view(),name="promo_edit"),
    # path("promocode/delete/<int:pk>/",PromoCodeDelete.as_view(),name="promo_remove"),
    # path("promocode/filter/",PromoCodeFilters.as_view(),name="promocode_filter"),




    path('offer/', OfferManagement.as_view(), name='offer_management'),
    path('api/offers/<int:pk>/', OfferDetailView.as_view(), name='offer_detail'),
    path('api/deleteoffer/<int:pk>/', OfferDeleteView.as_view(), name='offer_delete'),
    path('save_offer/filter/', OfferFilterView.as_view(), name='offer_filter'),
    path('promocode_exist/',CheckPromoCodeUniqe.as_view(),name='hotelpromocodeunique'),

    path('refund/', RefundCancellationView.as_view(), name='refund_cancellation_list'),
    path('review/',ReviewAndRating.as_view(),name="review_rating_vendor"),
    path('review/respond/<int:pk>/',ReviewRespondView.as_view(),name="review_respond"),
    path('review/edit/<int:pk>/', ReviewEditView.as_view(),name='edit_review_respond'),



    path("booking/<int:pk>/",usermanagement.as_view(),name="user"),
    path('manage-booking/', ManageBookingView.as_view(), name='manage-booking'),
    path('upload_images/<int:pk>/', UploadImagesView.as_view(), name='upload_images'),

    path("room/view/edit/<int:pk>/",UsermanagementEdit.as_view(),name="user_edit"),
    path('set_language/', SetLanguageView.as_view(), name='set_language'),


    path('password-reset/<int:id>/<str:token>/',MobileappPasswordResetConfirmView.as_view(),name='password_reset'),

    path('request-amenity/', RequestAmenityView.as_view(), name='request_amenity'),

    path('room/<int:pk>/', RoomDetailView.as_view(), name='view_room'),
    path('upload-room-images/', RoomImageUploadView.as_view(), name='upload_room_images'),
    path('fetch-room-data/', fetch_room_data, name='fetch_room_data'),
    path('upload-single-room-image/', RoomSingleImageUploadView.as_view(), name='upload_single_room_image'),



    path('edit_hotel/', EditHotelView.as_view(), name='edit_hotel'),
    path('edit_detail/', EditHotelDetailView.as_view(), name='edit_detail'),
    path('edit-amenity/',edit_amenity_to_hotel, name='edit_amenity_to_hotel'),
    
    path('edit_policy/', EditHotelPolicyView.as_view(), name='edit_hotel_policy'),
    path('get_policy_data/<int:category_id>/', PolicyDataView.as_view(), name='get_policy_data'),
    path('save_policy/', save_policy, name='save_policy'),
    path('update_policy_data/', update_policy_data, name='update_policy_data'),
    path('unread-notifications/', unread_notifications, name='unread_notifications'),
    path('delete_policy/<int:policycategoryID>/', DeletePolicyView.as_view(), name='edit_hotel_policy'),
    path('booking/verify/<uuid:token>/', verify_booking, name='verify-booking'),
    path('room-type-management/',RoomTypeManagement.as_view(),name="room_type_management"),
    # path('room-type-management/<int:pk>/', RoomTypeDetail.as_view(), name='room_type_detail'),
    # path('get_room/<int:pk>/', GetRoom.as_view(), name='get_room'),
    path("hotel-transaction-excel-download", HotelTransactionExcelDownloadView.as_view(), name='hotel_transaction_excel_download'),
    
    path("retrive-roomtype-details", RetriveRoomtypeDetails.as_view(), name='retrive_roomtype_details'),
    path("add_hotels", AddHotels.as_view(), name='add_hotel')

    


    

]+static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
