from django.urls import path
from django.contrib.auth.views import LogoutView
from django.conf.urls.static import static
from .views import *

urlpatterns = [

    path('test', test_template, name='test-template'),
    path('logout/', LogoutView.as_view(next_page='loginn'), name='logout'),

    path('register/<str:category>/',ChaletRegister.as_view(),name="register_chalet"),
    path('hotelregister/<str:category>/',HotelRegister.as_view(),name="register_hotel"),

    # path('dashboard/',ChaletDashboard.as_view(),name="chalet_dashboard"),
    # path('table/list/',ChaletListView.as_view(),name="chalet_table_list"),
    path('approval/<int:pk>/',ChaletApproveView.as_view(),name="chalet_approval"),
    path('dashboard_overview', DashboardOverview.as_view(), name='dashboard_overviews'),
    path('pending/', Pendingview.as_view(), name='pending_hotel'),

    path('ammenities/',AmenitiesAddView.as_view(),name="chalet_ammenities"),
    path('ammenities/back/',BackSelectedAmmenities.as_view(),name="back_chalet_ammenities"),
    path('price/',PriceAddView.as_view(),name="price"),
    path('price/back/',BackSelectedPrice.as_view(),name="back_price"),
    path('final/',FinalStepView.as_view(),name="final_step_chalet"),

    path("ViewAll/Booking/",chaletViewAllButton.as_view(),name="chalet_view_all"),


    path('chalet_booking',ChaletBookings.as_view(),name='chalet_booking'),
    path('chalet/view/<int:pk>/',ChaletUserManagement.as_view(),name="chalet_user"),
    path('upload_images/<int:pk>/', chaletUploadImagesView.as_view(), name='chalet_upload_images'),
    path("room/view/edit/<int:pk>/",ChaletUsermanagementEdit.as_view(),name="chalets_user_edit"),
    path('manage-booking/', ChaletManageBookingView.as_view(), name='chalet-manage-booking'),


    path('chalet_booking_detail/<int:pk>/',ChaletBookingDetail.as_view(),name='chalet_booking_detail'),
    path('chalet_past-bookings/', ChaletPastBookingsView.as_view(), name='chalet_past-bookings'),
    path('chalet_cancelled-appointments/', ChaletCancelledAppointmentsView.as_view(), name='chalet_cancelled_appointments'),

    path('chalet_transaction',ChaletTransactionDetails.as_view(),name='chalet_transaction'),
    path('chalet_offers/',ChaletOfferPromotions.as_view(),name='chalet_offers'),
    path('chalet_offers/<int:pk>/<int:chalet_id>/', ChaletOfferPromotionsDetailView.as_view(), name='chalet_offers_detail'),
    path('chalet_offers/delete/<int:pk>/<int:chalet_id>/', ChaletOfferPromotionsDeleteView.as_view(), name='chalet_offer_delete'),
    path('chalet_offers/filter/', ChaletOfferPromotionsFilterView.as_view(), name='chalet_offer_filter'),
    path('chalet_promocode_exist/',ChaletCheckPromoCodeUniqe.as_view(),name='chalet_promocodeunique'),
    # path('chalet_promo_code/',ChaletPromoCode.as_view(),name="chalet_promo_code"),
    # path('chalet_promo_code/edit/<int:pk>/',ChaletPromoCodeEdit.as_view(),name="chalet_promo_code_edit"),
    # path('chalet_promo_code/delete/<int:pk>/',ChaletPromoCodeDelete.as_view(),name="chalet_promo_code_delete"),
    # path("chalet_promo_code/filter/",ChaletPromoCodeFilters.as_view(),name="chalet_promo_code_filter"),


    path('chalet_refund',ChaletRefundCancellation.as_view(),name='chalet_refund'),
    path('chalet_review',ChaletReviewRatings.as_view(),name='chalet_review'),
    path('chalet_review/respond/<int:pk>/',ChaletReviewRespondView.as_view(),name="chalet_review_respond"),
    path('review/edit/<int:pk>/', ReviewEditView.as_view(),name='edit_review_respond'),


    path('propertys/', PropertyView.as_view(), name='chalet_property'),
    path('room/delete/<int:room_id>/', delete_room, name='room_remove'),
    path('rooms/edit/<int:pk>/', RoomEditView.as_view(), name='room_edit'),


    path('property/', ChaletManagementView.as_view(), name="chalet_management"),
    path('add-property/', AddChaletView.as_view(), name="add_chalet"),
    path('check-room-name/',check_room_details, name='check_room_details'),


    path('edit_chalet/', EditChaletView.as_view(), name='edit_chalet'),
    path('edit_detail/', EditChaletDetailView.as_view(), name='edit_chalet_detail'),
    path('edit-amenity/',edit_amenity_to_chalet, name='edit_amenity_to_chalet'),



    path('edit_policy/', EditChaletPolicyView.as_view(), name='edit_chalet_policy'),
    path('get_policy_data/<int:category_id>/', PolicyDataView.as_view(), name='get_policy_data'),
    path('save_policy/',save_policy, name='save_policy'),
    path('update_policy_data/', update_policy_data, name='update_policy_data'),
    path('chalet-booked/', ChaletManagementViewBooked.as_view(), name='chalet_booked'),
    path('chalet/<int:pk>/', ChaletDetailView.as_view(), name='view_chalet'),
    path('delete_policy/<int:policycategoryID>/', DeletePolicyView.as_view(), name='edit_hotel_policy'),
    path('booking/verify/<uuid:token>/', verify_booking, name='verify-booking'),
    path('upload-single-chalet-image/', ChaletImageUploadView.as_view(), name='upload_single_chalet_image'),
    path('chalet-info/<int:chalet_id>/', ChaletInfoEdit.as_view(), name='chalet_info'),
    path('chalet-transaction-excel-download/', ChaletTransactionExcelDownloadView.as_view(), name='chalet_tarnsaction_download'),
    path('room_exist/',RoomnumberExistView.as_view(),name='room_exists'),


    


]+static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
