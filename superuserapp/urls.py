from django.urls import path
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView
from superuserapp.views import *

urlpatterns = [
    
   

    path("booking/",SuperUserBookingView.as_view(),name="super_booking"),
    path('hotel/',SuperHotelListView.as_view(),name="super_hotel_table_list"),
    path('hotel/approval/<int:pk>/',HotelApprovalView.as_view(),name="super_hotel_approval"),
    path('hotel/<int:pk>/',HotelDetailEditView.as_view(),name='hotel_edit'),
    path('approval/<int:pk>/',ChaletApproveView.as_view(),name="super_chalet_approval"),
    path("transaction_detail",SuperTransactionDetailView.as_view(),name="super_transaction_detail"),
    path("amenity_list",AmenityListView.as_view(),name="amenity_list"),
    path('amenity_edit/<int:pk>/', AmenityEditView.as_view(), name='amenity_edit'),
    path('check-email/', check_email_exists, name='check_email_exists'),
    path('dashboard/', DashboardView.as_view(), name='dashboard_overview'),
    path('view/',ViewAllButton.as_view(),name="view"),
    path('save-hotel-details/', SaveHotelDetailView.as_view(), name='save_hotel_details'),
    path('add-amenity/',add_amenity_to_hotel, name='add_amenity_to_hotel'),

    path('add-policy/', AddPolicyView.as_view(), name='add_policy'),
    path('save-policy/', save_policy, name='save_policy'),
    path('get_policy_data/<int:category_id>/', GetPolicyDataView.as_view(), name='get_policy_data'),
    path('update_policy_data/', update_policy_data, name='update_policy_data'),
    path('delete_policy/<int:category_id>/',DeletePolicy.as_view(),name='delete_policy'),

    path('commission/',CommissionListView.as_view(),name='commission_list'),
    path('commission_edit/<int:pk>/',CommisionEditView.as_view(),name='commission_edit'),
    path('delete-commission/<int:pk>/',DeleteCommissionslabView.as_view(),name='delete_commission'),
    path('user-management/',UserManagementView.as_view(),name='user-management'),
    path('toggle-user-status/', ToggleUserStatusView.as_view(), name='toggle_user_status'),
    path('review&rating/',ReviewAndRating.as_view(),name="review_rating"),
    path('offers/',SuperUserOffer.as_view(),name="superuser_offers"),
    path('offers/<int:pk>/', SuperUserOfferPromotionsDetailView.as_view(), name='superuser_offers_detail'),
    path('offers/filter/', SuperUserOfferFilterView.as_view(), name='superuser_offer_filter'),
    path('offerdelete/<int:pk>/', SuperUserOfferDeleteView.as_view(), name='superuser_offer_delete'),
    path('room-types-management/',RoomTypesManagementView.as_view(),name='room_types_management'),

    path('chalet-type/', ChaletTypeView.as_view(), name='chalet_type'),
    path('chalet_type/<int:pk>/',ChaletTypeDetail.as_view(), name='chalet_type_details'),
    path('search_chalet_types/', ChaletTypeSearch.as_view(), name='chalet_type_search'),
    path('chalet_type_name_exist/', chalet_type_check_name, name='chalet_type_check_name'),
    path('hotel-type/', HotelTypeView.as_view(), name='hotel_type'),
    path('hotel_type/<int:pk>/', HotelTypeDetail.as_view(), name='hotel_edit'),
    path('search_hotel_types/', HotelTypeSearch.as_view(), name='hotel_edit'),
    path("hotel-type/check-name/", hotel_type_check_name, name="hotel_type_check_name"),
    path("edit-admin/<int:user_id>/", EditAdminView.as_view(), name='edit-admin'),
    path("delete-admin/", delete_admin, name="delete_admin"),
    
    path("admin-transaction-excel-download", AdminTransactionExcelDownloadView.as_view(), name='admin_transaction_excel_download'),
    path('user_management_excel_download',UsermanagementExcelDownload.as_view(), name='user_management_excel_download')
   
    

]

