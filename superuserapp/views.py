from itertools import chain
import os
import json
import logging
from datetime import datetime, timedelta
from calendar import month_abbr
from django.contrib.auth.decorators import login_required   
from django.shortcuts import redirect, render, get_object_or_404
from django.views import View
from django.utils.translation import activate
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db.models import Count,Sum
from django.db.models.functions import TruncMonth,TruncWeek,TruncDay
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from decimal import Decimal
from commonfunction import combine_bookings, report_data_frame, transaction_list_filter, xlsxwriter_styles,user_data_frame
from user.models import VendorProfile,Userdetails,Wallet
from common.models import City, Country,Categories, Amenity,State, Tax,PaymentType,PaymentTypeCategory, Transaction
from helpers.mixins import CustomLoginRequiredMixin
from common.models import User,ChaletType
from common.customdecorator import vendor_required,super_admin_required
from common.emails import send_email
import re
from urllib.parse import unquote
from chalets.models import Chalet, ChaletBooking,ChaletRecentReview, ChaletTax,PolicyCategory, PolicyName,Promotion,ChaletAcceptedPayment
from vendor.models import Booking,Bookedrooms, Hotel, HotelDocument, HotelImage, HotelTax, MealPrice,RecentReview, RoomManagement, Roomtype, HotelTransaction,CommissionSlab,HotelType,HotelAcceptedPayment
from django.utils.translation import gettext as _

logger = logging.getLogger('lessons')
def check_email_exists(request):
    email = request.GET.get('email', '')
    exists = User.objects.filter(email=email).exists()
    return JsonResponse({'exists': exists})

class SetLanguageView(View):
    def post(self, request, *args, **kwargs):
        language_code = request.POST.get("language_code")
        if language_code in dict(settings.LANGUAGES).keys():
            request.session["django_language"] = language_code
            activate(language_code)
            return JsonResponse({"success": True})
        else:
            return JsonResponse({"success": False, "error": _("Invalid language code")})
                
@method_decorator(super_admin_required, name='dispatch')
class SuperHotelListView(CustomLoginRequiredMixin, View):
    def get(self, request):
        try:
            category = Categories.objects.get(category="HOTEL")
            hotels = Hotel.objects.filter(category=category).order_by("-id")
        except Categories.DoesNotExist:
            category = None
            hotels = Hotel.objects.none()
            logger.info("hotels not found at super user hotellist")
        page = request.GET.get('page', 1)  
        paginator = Paginator(hotels, 15)
        try:
            hotels_paginated = paginator.page(page)
        except PageNotAnInteger:
             hotels_paginated = paginator.page(1)  
        except EmptyPage:
            hotels_paginated = paginator.page(paginator.num_pages) 


        categories = Categories.objects.all().order_by("id")
         
        
        return render(request, "superuser/register_view_table.html", {
            "hotel_data":  hotels_paginated,
            "categories": categories,
            "LANGUAGES": settings.LANGUAGES,
        })

    def post(self, request):
        
        from_date = request.POST.get("from_date")
        to_date = request.POST.get("to_date")
        category_type = request.POST.get("category_type")
        approved = request.POST.get("approved")
        print(from_date,to_date,category_type,approved)
        page = request.POST.get('page', 1)   
        print("request received for page no",page)


        hotels = Hotel.objects.all()
        chalets = Chalet.objects.all()

        if category_type:
            category = Categories.objects.get(category=category_type)
            if category.category == "HOTEL":
                hotels = hotels.filter(category=category).order_by("-id")
            else:
                hotels = chalets.filter(category=category).order_by("-id")

        if approved:
            hotels = hotels.filter(approval_status = approved).order_by("-id")

        if from_date and to_date:
            hotels = hotels.filter(date_of_expiry__range=[from_date, to_date]).order_by("-id")
        elif from_date:
            hotels = hotels.filter(date_of_expiry__gte=from_date).order_by("-id")
        elif to_date:
            hotels = hotels.filter(date_of_expiry__lte=to_date).order_by("-id")
        paginator = Paginator(hotels, 15)
        try:
            hotels_paginated = paginator.page(page)
        except PageNotAnInteger:
             hotels_paginated = paginator.page(1)  
        except EmptyPage:
            hotels_paginated = paginator.page(paginator.num_pages) 
        print(hotels_paginated)
        return render(request, "superuser/register_view_table.html", {"hotel_data": hotels_paginated})


@method_decorator(super_admin_required, name='dispatch')
class HotelApprovalView(CustomLoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        try:
            user = VendorProfile.objects.get(user=request.user, user__is_superuser=True)
        except VendorProfile.DoesNotExist:
            return render(request, "superuser/404.html")
        

        hotel = get_object_or_404(Hotel, id=kwargs.get("pk"))
        # Fetch active taxes
        taxes = Tax.objects.filter(status="active", is_deleted=False)

        # Fetch existing HotelTax or ChaletTax records for pre-filling
        if hotel:
            existing_taxes = HotelTax.objects.filter(hotel=hotel, status="active", is_deleted=False)
            tax_percentage_map = {ht.tax_id: ht.percentage for ht in existing_taxes}
        
        for tax in taxes:
            tax.percentage = tax_percentage_map.get(tax.id, None)
        if hotel:
            hotel_payment = HotelAcceptedPayment.objects.filter(hotel=hotel.id)

            selected_payment_types = PaymentType.objects.filter(
                hotel_payment_types_set__in=hotel_payment, status="active"
            )

            selected_categories = list(
                selected_payment_types.values("category__name", "category__name_arabic").distinct()
            )

            logger.info(selected_categories)
        images = hotel.hotel_images.all()
        documents = hotel.attached_documents.all()
        return render(request, "superuser/hotel_approval_table.html", {
            "data": hotel,
            "images": images,
            "documents": documents,
            "taxes": taxes,
            "selected_categories": selected_categories,
            "LANGUAGES": settings.LANGUAGES,
        })

    def post(self, request, *args, **kwargs):
        hotel = get_object_or_404(Hotel, id=kwargs.get("pk"))
        approve_status = request.POST.get("approved_status")
        hotel_owner_email = request.POST.get("email")
        rejection_remark = request.POST.get("remark", "")
        logger.info(f"approve_status:{approve_status},hotel_owner_email:{hotel_owner_email},rejection_remark:{rejection_remark}")
        hotel_id = f"HTL{hotel.id:04d}"  
        hotel.hotel_id = hotel_id

        if approve_status == "approved":
            logger.info("Enter inside approve status is TRUE")
            hotel.approval_status = approve_status
            subject = 'Hotel Approval Notification'
            message = render_to_string('accounts/hotel_approval_notification.html', {
                'hotel_name': hotel.name,
            })
        else:
            hotel.approval_status = approve_status
            subject = 'Hotel Disapproval Notification'
            message = render_to_string('accounts/hotel_disapproval_notification.html', {
                'hotel_name': hotel.name,
                'rejection_remark': rejection_remark,
            })

        try:
            if subject and settings.EMAIL_HOST_USER and hotel_owner_email and message:
                logger.info(f"preparing email, from mail in superuser page: {settings.EMAIL_HOST_USER}, recipient_list: {hotel_owner_email}")
                logger.info(f"inside mail variable conditrion but before send mail")
                send_mail(subject, 'Hotel approval', settings.EMAIL_HOST_USER, [hotel_owner_email], html_message=message, fail_silently=False)
                logger.info(f"mail has been send successfully")
            else:
                print(subject, settings.EMAIL_HOST_USER, hotel_owner_email, message)
                logger.info(f"email sending failed due to miss-attribute  ------> {subject}, {settings.EMAIL_HOST_USER}, {hotel_owner_email}")
        except Exception as e:
            logger.info(f"failed to send email, Exception raised: {e}")
        hotel.save()
        return JsonResponse({"message": _("Hotel status updated successfully."), "approved": hotel.approval_status})


@method_decorator(super_admin_required, name='dispatch')
class ChaletApproveView(CustomLoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        
        hotel = get_object_or_404(Chalet, id=kwargs.get("pk"))
        # Fetch active taxes
        taxes = Tax.objects.filter(status="active", is_deleted=False)

        # Fetch existing HotelTax or ChaletTax records for pre-filling
        if hotel:
            existing_taxes = ChaletTax.objects.filter(chalet=hotel, status="active", is_deleted=False)
            tax_percentage_map = {ht.tax_id: ht.percentage for ht in existing_taxes}
        

        # Attach existing percentages to taxes
        for tax in taxes:
            tax.percentage = tax_percentage_map.get(tax.id, None)
        if hotel:
            chalet_payment = ChaletAcceptedPayment.objects.filter(chalet=hotel.id)

            selected_payment_types = PaymentType.objects.filter(
                chalet_payment_types_set__in=   chalet_payment, status="active"
            )

            selected_categories = list(
                selected_payment_types.values("category__name", "category__name_arabic").distinct()
            )

        images = hotel.chalet_images.all()
        documents = hotel.chalet_attached_documents.all()
        return render(request, "superuser/chalet_approval.html", {
            "data": hotel,
            "images": images,
            "documents": documents,
            "taxes": taxes,
            "selected_categories": selected_categories,
            "LANGUAGES": settings.LANGUAGES,

        })

    def post(self, request, *args, **kwargs):
        hotel = get_object_or_404(Chalet, id=kwargs.get("pk"))
        approve_status = request.POST.get("approved_status")
        hotel_owner_email = request.POST.get("email")
        rejection_remark = request.POST.get("remark", "")
        commission_percentage = request.POST.get("commission_percentage")

        hotel_id = f"CHL{hotel.id:04d}"  
        hotel.chalet_id = hotel_id

        if approve_status == "approved":
            hotel.approval_status = approve_status
            hotel.commission_percentage = float(commission_percentage) if commission_percentage else None
            subject = 'Chalet Approval Notification'
            message = render_to_string('chalets_accounts/chalet_approval_notification.html', {
                'hotel_name': hotel.name,
                'commission_percentage': commission_percentage,
            })
        else:
            hotel.approval_status = approve_status
            subject = 'Chalet Disapproval Notification'
            message = render_to_string('chalets_accounts/chalet_disapproval_notification.html', {
                'hotel_name': hotel.name,
                'rejection_remark': rejection_remark,
            })

        try:
            send_mail(subject, '', settings.EMAIL_HOST_USER, [hotel_owner_email], html_message=message)
        except Exception as e:
            print(f"Error sending email: {e}")

        hotel.save()
        return JsonResponse({"message": _("Hotel status updated successfully."), "approved": hotel.approval_status})


@method_decorator(super_admin_required, name='dispatch')
class SuperUserBookingView(CustomLoginRequiredMixin, View):
    def get(self, request):
        try:
            logger.info(f"SuperUserBookingView GET request initiated by user: {request.user}")
            activate(request.LANGUAGE_CODE)
            current_date = timezone.now().date()
            bookings = Booking.objects.all().order_by('-id')
            category = Categories.objects.get(category="HOTEL")
            hotels = Hotel.objects.filter(category=category)
            bookings = bookings.filter(hotel__in=hotels)
            categories = Categories.objects.all().order_by("id")
            page = request.GET.get('page', 1)  
            paginator = Paginator(bookings, 15)
            logger.info(f"Paginating bookings: requested page {page}, total bookings {bookings.count()}")
            try:
                bookings_paginated = paginator.page(page)
                logger.info(f"Page {page} loaded successfully.")
            except PageNotAnInteger:
               bookings_paginated = paginator.page(1)  
               logger.warning(f"Invalid page number: {page}. Defaulting to page 1.")
            except EmptyPage:
                bookings_paginated = paginator.page(paginator.num_pages) 
                logger.warning(f"Page {page} out of range. Defaulting to last page {paginator.num_pages}.")

            logger.info(f"Showing {len(bookings_paginated.object_list)} bookings on page {page}.")
            logger.info(f"Fetched {bookings.count()} bookings.")
            return render(request, "superuser/booking_management.html", {
                "booking_data": bookings_paginated,
                "categories": categories,
                "LANGUAGES": settings.LANGUAGES,
            })
        except Exception as e:
            logger.info(f"error in the superadmin booking {e}")
            return render(request, 'superuser/404.html', {"error_message": str(e)})

    def post(self, request):
        try:
            logger.info(f"SuperUserBookingView POST request initiated by user: {request.user}")
            page = request.POST.get('page', 1)
            from_date = request.POST.get("from_date")
            to_date = request.POST.get("to_date")
            category_type = request.POST.get("category_Type")
            status = request.POST.get("status_type")

            bookings = ""
            if category_type:
                logger.info(f"Filtering bookings for category: {category_type}")
                category = Categories.objects.get(category=category_type)
                print(category, "==========category============")

                if category.category == "HOTEL":
                    # Ensure Booking is filtered using Hotel objects
                    hotels = Hotel.objects.all()
                    bookings = Booking.objects.filter(hotel__in=hotels).order_by('-id')
                else:
                    # Ensure Booking is filtered using Chalet objects
                    chalets = Chalet.objects.all()
                    bookings = ChaletBooking.objects.filter(chalet__in=chalets).order_by('-id')

                print(bookings, "========bookings")

            if from_date and to_date:
                logger.info(f"Filtering bookings from {from_date} to {to_date}")
                bookings = bookings.filter(checkin_date__gte=from_date, checkout_date__lte=to_date)
            elif from_date:
                logger.info(f"Filtering bookings from {from_date}")
                bookings = bookings.filter(checkin_date__gte=from_date)
            elif to_date:
                logger.info(f"Filtering bookings until {to_date}")
                bookings = bookings.filter(checkout_date__lte=to_date)

            if status and category.category == "HOTEL":
                logger.info(f"Filtering bookings by status: {status}")
                bookings = bookings.filter(status__iexact=status)
            elif status and category.category == "CHALET":
                logger.info(f"Filtering chalet bookings by status: {status}")
                bookings = bookings.filter(status__iexact=status)
            logger.info(f"Filtered bookings count: {bookings.count()}")
            paginator = Paginator(bookings, 15)
            logger.info(f"Paginating filtered bookings: requested page {page}, total bookings {bookings.count()}")
            try:
                bookings_paginated = paginator.page(page)
                logger.info(f"Page {page} loaded successfully.")
            except PageNotAnInteger:
                bookings_paginated = paginator.page(1)
                logger.warning(f"Invalid page number: {page}. Defaulting to page 1.")
            except EmptyPage:
                bookings_paginated = paginator.page(paginator.num_pages)
                logger.warning(f"Page {page} out of range. Defaulting to last page {paginator.num_pages}.")
            logger.info(f"Showing {len(bookings_paginated.object_list)} bookings on page {page}.")
        except Exception as e:
            logger.info(f"error in the superadmin booking search",e)
            return render(request, 'superuser/404.html', {"error_message": str(e)})
       
        return render(request, "superuser/booking_management.html", {"booking_data": bookings_paginated})
    
@method_decorator(super_admin_required, name='dispatch')
class SuperTransactionDetailView(CustomLoginRequiredMixin, View):
    def get(self, request):
        page = request.GET.get('page', 1)
        print(f"page========={page}")
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")
        payment_method = request.GET.get("payment_method")
        transaction_status = request.GET.get("transaction_status")
        booking_status = request.GET.get("booking_status")
        name_search = request.GET.get("Name_search")
        transaction_id = request.GET.get("transaction_id")
        hotel_booking = Booking.objects.select_related('transaction').prefetch_related('transaction__vendor_transaction','transaction__admin_transaction').order_by('-modified_date')
        chalet_booking = ChaletBooking.objects.select_related('transaction').prefetch_related('transaction__vendor_transaction','transaction__admin_transaction').order_by('-modified_date')
        transactions = sorted(
                chain(hotel_booking, chalet_booking),
                key=lambda x: x.modified_date,
                reverse=True
            )
        logedin_user = "admin"
        transactions = transaction_list_filter(transactions, from_date,  to_date, payment_method, transaction_status, booking_status, name_search, transaction_id,logedin_user)
        # activate(request.LANGUAGE_CODE)
        # transactions = Transaction.objects.filter(Q(hotel_booking__isnull=False) | Q(bookings__isnull=False)).order_by('-modified_at')
        payment_choices = list(PaymentType.objects.filter(status='active', is_deleted=False)
                       .exclude(name__isnull=True)
                       .exclude(name="")
                       .values_list('name', flat=True))
        if isinstance(payment_choices[0], str):  # If it's a list of strings, convert it to tuples
            payment_choices = [(choice, choice) for choice in payment_choices]
        transaction_status = Transaction.TRANSACTION_STATUS_CHOICES
        booking_status = Booking.BOOKING_STATUS
        categories = Categories.objects.all().order_by("id")

        # Pagination logic
        page = request.GET.get('page', 1)
        paginator = Paginator(transactions, 15) 

        try:
            paginated_transactions = paginator.page(page)
        except PageNotAnInteger:
            paginated_transactions = paginator.page(1)
        except EmptyPage:
            paginated_transactions = paginator.page(paginator.num_pages)
        print("paginated_transactions",paginated_transactions)


        return render(request, 'superuser/transaction_detail.html', {
            'transactions': transactions,
            'payment_choices': payment_choices,
            'categories': categories,
            'booking_status':booking_status,
            'transaction_status': transaction_status,
            'paginated_transactions': paginated_transactions,
            "LANGUAGES": settings.LANGUAGES,
        })

    


@method_decorator(super_admin_required, name='dispatch')
class AmenityListView(CustomLoginRequiredMixin, View):
    def get(self, request):
        status_filter = request.GET.get('status')
        try:
            amenities = Amenity.objects.all()

            if status_filter == "active":
                amenities = amenities.filter(status=True)
            elif status_filter == "inactive":
                amenities = amenities.filter(status=False)
        except Exception as e:
            logger.error(f"Error retrieving amenities: {e}")
            return render(request, "superuser/500.html")

        for amenity in amenities:
            try:
                display_type = amenity.get_amenity_type_display()
                amenity.formatted_amenity_type = display_type.replace('_', ' ').title() if display_type else 'Unknown'
            except Exception as e:
                logger.warning(f"Error processing amenity {amenity.id}: {e}")
                amenity.formatted_amenity_type = 'Unknown'

        try:
            paginator = Paginator(amenities, 15)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)
        except Exception as e:
            logger.error(f"Error paginating amenities: {e}")
            return render(request, "superuser/404.html")

        return render(
            request, 
            "superuser/manage_amenity.html", 
            {
                'page_obj': page_obj,
                'amenities': page_obj.object_list,
                "LANGUAGES": settings.LANGUAGES,
                "selected_status": status_filter,
            }
        )

    def post(self, request, *args, **kwargs):
        try:
            amenity_name = request.POST.get('amenity_name')
            amenity_name_arabic = request.POST.get('amenity_name_arabic')
            amenity_type = request.POST.get('amenity_type')
            status = request.POST.get('status')
            hotel_owner_email = request.POST.get('admin_email')
            icon_file = request.FILES.get('icon')

            if not amenity_name or not amenity_name_arabic:
                logger.error("Amenity name or Arabic name is missing.")
                return JsonResponse({'error': _('Amenity name and Arabic name are required')}, status=400)

            if Amenity.objects.filter(amenity_name__iexact=amenity_name).exists():
                logger.warning(f"Amenity with name '{amenity_name}' already exists.")
                return JsonResponse({'error': _('Amenity with this name already exists')}, status=400)

            elif Amenity.objects.filter(amenity_name_arabic__iexact=amenity_name_arabic).exists():
                logger.warning(f"Amenity with Arabic name '{amenity_name_arabic}' already exists.")
                return JsonResponse({'error': _('Amenity with this Arabic name already exists')}, status=400)
            amenity =None
            try:
                logger.info("Validation completed creating amenity object")
                amenity = Amenity.objects.create(
                    amenity_name=amenity_name,
                    amenity_name_arabic=amenity_name_arabic,
                    amenity_type=amenity_type,
                    status=(status == 'Active'),
                    icon=icon_file
                )
            except Exception as e:
                logger.error(f"Exception occured while creating the amenity. Exception :{e}")
                return JsonResponse({'error': _('Failed to create amenity. Please try again later.')}, status=500)

            if not amenity:
                logger.error("Amenity creation returned None. Email will not be sent.")
                return JsonResponse({'error': _('Amenity creation failed. Email not sent.')}, status=500)

            
            logger.info(f"Amenity '{amenity_name}' created successfully with ID {amenity.id}.")
            if hotel_owner_email:
                logger.info("Preparing to send mail to hotel owner")
                subject = 'Amenity added successfully!'
                html_content = render_to_string('accounts/amenity_approval_email.html', {'amenity_name': amenity_name})
                try:
                    send_email(subject=subject, html=html_content, recipients=[hotel_owner_email])
                    logger.info(f"Email sent successfully to {hotel_owner_email}.")
                except Exception as e:
                    logger.error(f"Error sending email to {hotel_owner_email}: {e}")
                    return JsonResponse({'error': _('Amenity created but email notification failed.')}, status=500)
            else:
                logger.info("Email not sent because hotel owner email not found.")
            
            return JsonResponse({'message': _('Amenity added successfully!'), 'amenity_id': amenity.id})
        
        except Exception as e:
            logger.error(f"Error occurred while processing the request: {e}")
            return JsonResponse({'error': _('An unexpected error occurred, please try again later.')}, status=500)

@method_decorator(super_admin_required, name='dispatch')
class AmenityEditView(CustomLoginRequiredMixin,View):
    def get(self, request, pk):
        try:
            amenity = get_object_or_404(Amenity, pk=pk)
        except Amenity.DoesNotExist:
            logger.error(f"Amenity with ID {pk} does not exist.")
            return JsonResponse({'error': _('Amenity not found')}, status=404)

        data = {
            'amenity_id': amenity.id,
            'amenity_name': amenity.amenity_name,
            'amenity_name_arabic': amenity.amenity_name_arabic,
            'amenity_type': amenity.amenity_type,
            'status': 'Active' if amenity.status else 'Inactive',
            'icon_url': amenity.icon.url if amenity.icon else None,
        }
        return JsonResponse(data)

    def post(self, request, pk):
        try:
            amenity = get_object_or_404(Amenity, pk=pk)
        except Amenity.DoesNotExist:
            logger.error(f"Amenity with ID {pk} does not exist for update.")
            return JsonResponse({'error': _('Amenity not found')}, status=404)
        
        new_amenity_name = request.POST.get('amenity_name')
        amenity_name_arabic = request.POST.get('amenity_name_arabic')

        if not new_amenity_name or not amenity_name_arabic:
            logger.error("Missing amenity name or Arabic name for update.")
            return JsonResponse({'error': _('Amenity name and Arabic name are required')}, status=400)
        
        existing_amenity = Amenity.objects.filter(
            amenity_name__iexact=new_amenity_name
        ).exclude(pk=pk).first()

        existing_amenity_ar = Amenity.objects.filter(
            amenity_name_arabic__iexact=amenity_name_arabic
        ).exclude(pk=pk).first()

        if existing_amenity:
            logger.warning(f"Amenity with name '{new_amenity_name}' already exists.")
            return JsonResponse({'error': _('Amenity with this name already exists.')}, status=400)
        if existing_amenity_ar:
            logger.warning(f"Amenity with Arabic name '{amenity_name_arabic}' already exists.")
            return JsonResponse({'error': _('Amenity with this Arabic name already exists.')}, status=400)

        amenity.amenity_name = new_amenity_name
        amenity.amenity_name_arabic = amenity_name_arabic
        amenity.amenity_type = request.POST.get('amenity_type')
        amenity.status = request.POST.get('status') == 'Active'

        if request.FILES.get('icon'):
            amenity.icon = request.FILES['icon']
        
        try:
            amenity.save()
            logger.info(f"Amenity with ID {amenity.id} updated successfully.")
        except Exception as e:
            logger.error(f"Error saving amenity with ID {amenity.id}: {e}")
            return JsonResponse({'error': _('Failed to update amenity')}, status=500)

        return JsonResponse({'message': _('Amenity updated successfully!')})
    


@method_decorator(super_admin_required, name='dispatch')
class CommissionListView(CustomLoginRequiredMixin, View):
    def get(self, request):
        try:
            commission = CommissionSlab.objects.filter(status='active')
        except Exception as e:
            logger.error(f"Error retrieving commission slabs: {e}")
            return render(request, "superuser/500.html")

        return render(request, "superuser/commission.html", {
            'commissions': commission,
            "LANGUAGES": settings.LANGUAGES,
        })

    def post(self, request, *args, **kwargs):
        try:
            from_amount = request.POST.get('fromamount')
            to_amount = request.POST.get('toamount')
            commission = request.POST.get('commission')

            from_amount_decimal = Decimal(from_amount)
            to_amount_decimal = Decimal(to_amount)

            if CommissionSlab.objects.exclude(status='inactive').filter(
                Q(from_amount__lte=from_amount_decimal, to_amount__gte=from_amount_decimal) |
                Q(from_amount__lte=to_amount_decimal, to_amount__gte=to_amount_decimal) |
                Q(from_amount__gte=from_amount_decimal, to_amount__lte=to_amount_decimal)
            ).exists():
                logger.info("Overlapping commission range detected")
                return JsonResponse({'error': _('Commission slab with overlapping range already exists')}, status=400)

            if CommissionSlab.objects.exclude(status='inactive').filter(
                Q(commission_amount=commission) &
                Q(from_amount=from_amount_decimal, to_amount=to_amount_decimal)
            ).exists():
                logger.info("Duplicate commission slab detected")
                return JsonResponse({'error': _('A commission slab with these exact values already exists')}, status=400)

            commissions = CommissionSlab.objects.create(
                from_amount=from_amount_decimal,
                to_amount=to_amount_decimal,
                commission_amount=commission,
            )
            logger.info(f"New commission slab created with ID: {commissions.id}")
            return JsonResponse({'message': _('Commission added successfully!'), 'amenity_id': commissions.id})

        except Exception as e:
            logger.error(f"Error adding commission slab: {e}")
            return JsonResponse({'error': _('An error occurred while adding the commission slab')}, status=500)


@method_decorator(super_admin_required, name='dispatch')
class CommisionEditView(CustomLoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            commission = get_object_or_404(CommissionSlab, pk=pk)
            data = {
                'commission_id': commission.id,
                'from_amount': commission.from_amount,
                'to_amount': commission.to_amount,
                'commission': commission.commission_amount,
            }
            return JsonResponse(data)
        except Exception as e:
            logger.error(f"Error retrieving commission slab with ID {pk}: {e}")
            return JsonResponse({'error': _('Error retrieving commission slab')}, status=500)

    def post(self, request, pk):
        try:
            commission = get_object_or_404(CommissionSlab, pk=pk)
            to_amount = request.POST.get('edittoamount')
            from_amount = request.POST.get('editfromamount')
            commission_amount = request.POST.get('editcommission')

            to_amount_decimal = Decimal(to_amount)
            from_amount_decimal = Decimal(from_amount)
            commission_amount_decimal = Decimal(commission_amount)

            if (commission.from_amount == from_amount_decimal and 
                commission.to_amount == to_amount_decimal and 
                commission.commission_amount == commission_amount_decimal):
                logger.info(f"No changes made to commission slab ID {pk}")
                return JsonResponse({'message': _('No changes made, but commission slab saved successfully')})

            if CommissionSlab.objects.exclude(status='inactive').filter(
                Q(from_amount__lte=from_amount_decimal, to_amount__gte=from_amount_decimal) |
                Q(from_amount__lte=to_amount_decimal, to_amount__gte=to_amount_decimal) |
                Q(from_amount__gte=from_amount_decimal, to_amount__lte=to_amount_decimal)
            ).exclude(pk=pk).exists():
                logger.info("Overlapping commission range detected during update")
                return JsonResponse({'error': _('Commission slab with overlapping range already exists')}, status=400)

            if CommissionSlab.objects.exclude(status='inactive').filter(
                from_amount=from_amount_decimal,
                to_amount=to_amount_decimal
            ).exclude(pk=pk).exists():
                logger.info("Duplicate commission slab detected during update")
                return JsonResponse({'error': _('A commission slab with these exact values already exists')}, status=400)

            commission.to_amount = to_amount_decimal
            commission.from_amount = from_amount_decimal
            commission.commission_amount = commission_amount_decimal
            commission.save()

            logger.info(f"Commission slab ID {pk} updated successfully")
            return JsonResponse({'message': _('Commission updated successfully!')})

        except Exception as e:
            logger.error(f"Error updating commission slab ID {pk}: {e}")
            return JsonResponse({'error': _('An error occurred while updating the commission slab')}, status=500)



class DeleteCommissionslabView(CustomLoginRequiredMixin, View):
    def post(self, request, pk):
        commission = get_object_or_404(CommissionSlab, pk=pk)
        commission.status='inactive'
        commission.save()
        return JsonResponse({'message': _('commission deleted successfully!')})


@method_decorator(super_admin_required, name='dispatch')
class DashboardView(CustomLoginRequiredMixin, View):
    def get(self, request):
        user_language = request.LANGUAGE_CODE
        activate(
            user_language
        )  # This line may not be necessary if middleware handles it


        current_year = now().year
        all_months = [f"{month_abbr[i]} {current_year}" for i in range(1, 13)]

        monthly_bookings = (
            Booking.objects.annotate(month=TruncMonth('booking_date'))
            .values('month')
            .annotate(total_bookings=Count('id'))
            .order_by('month')
        )

        month_data = {
            entry['month'].strftime("%b %Y"): entry['total_bookings']
            for entry in monthly_bookings
        }
       
        data_monthly = [month_data.get(month, 0) for month in all_months]
        categories_monthly = all_months
        

        today = now().date()
        start_of_week = today - timedelta(days=today.weekday())  
        end_of_week = start_of_week + timedelta(days=6) 
        
        daily_bookings = (
            Booking.objects.filter(booking_date__range=[start_of_week, end_of_week],status__in=["confirmed","check-in"])
            .annotate(day=TruncDay('booking_date'))
            .values('day')
            .annotate(total_bookings=Count('id'))
            .order_by('day')
        )
        pending_bookings = (
            Booking.objects.filter(booking_date__range=[start_of_week, end_of_week],status="pending")
            .annotate(day=TruncDay('booking_date'))
            .values('day')
            .annotate(total_bookings=Count('id'))
            .order_by('day')
        )
        cancelled_bookings = (
            Booking.objects.filter(booking_date__range=[start_of_week, end_of_week],status__in=["cancelled","rejected","expired"])
            .annotate(day=TruncDay('booking_date'))
            .values('day')
            .annotate(total_bookings=Count('id'))
            .order_by('day')
        )

        days_of_week = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        categories_weekly = days_of_week
        confirmed_weekly = [0] * 7 
        for entry in daily_bookings:
            day_of_week = entry['day'].weekday()
            confirmed_weekly[day_of_week] = entry['total_bookings']

        pending_weekly = [0] * 7 
        for entry in pending_bookings:
            day_of_week = entry['day'].weekday()
            pending_weekly[day_of_week] = entry['total_bookings']
        
        cancelled_weekly = [0] * 7 
        for entry in cancelled_bookings:
            day_of_week = entry['day'].weekday()
            cancelled_weekly[day_of_week] = entry['total_bookings']

        latest_booking = Booking.objects.all().order_by("-id")[:5]
        latest_chalet_booking = ChaletBooking.objects.all().order_by("-id")[:5]
        latest_chalet_hotel_booking = combine_bookings(latest_booking,latest_chalet_booking,sort=True)
        
        
        cancel_count_hotel = Booking.objects.filter(status__in=["cancelled","expired"]).count()
        cancel_count_chalet = ChaletBooking.objects.filter(status__in=["cancelled","expired"]).count()
        cancel_count = cancel_count_hotel + cancel_count_chalet
        
        total_hotel_booking = Booking.objects.all().distinct().count() 
        total_chalet_booking = ChaletBooking.objects.all().count()
        total = total_hotel_booking + total_chalet_booking
        
        confirmed_count_hotel = Booking.objects.filter(status__icontains="Confirmed").count()
        confirmed_count_chalet = ChaletBooking.objects.filter(status__icontains="Confirmed").count()
        confirmed_count = confirmed_count_hotel + confirmed_count_chalet
        
        hotel_booking_review = RecentReview.objects.values('booking').count()
        chalet_booking_review = ChaletRecentReview.objects.values('chalet_booking').count()
        bookings_with_reviews = hotel_booking_review + chalet_booking_review
        
        hotel_daily_count = Booking.objects.filter(booking_date=today).count()
        chalet_daily_count = ChaletBooking.objects.filter(booking_date=today).count()
        daily_count = hotel_daily_count + chalet_daily_count

        if total > 0:  
            cancel_rating = (cancel_count / total) * 100
            formatted_cancel_rating = f"{cancel_rating:.2f}%"  

            confirmed_rating = (confirmed_count / total) *100
            formatted_confirm_rating = f"{confirmed_rating:.2f}%" 

            review_rate = (bookings_with_reviews / total) * 100

            adr_rates = (daily_count/total)*100
            formatted_adr_rates = f"{adr_rates:.2f}%" 

        else:
            formatted_cancel_rating = "0.00%"
            formatted_confirm_rating = "0.00%"
            review_rate = 0
            formatted_adr_rates = "0.00%" 

        formatted_review_rate = f"{review_rate:.2f}%"
        
        from datetime import date
        from babel.dates import format_date
        from django.utils.translation import get_language
        current_language = get_language()
        today = date.today()
        arabic_date = format_date(today, format='full', locale='ar')
        
        total_rooms_booked = (
            Bookedrooms.objects
            .filter(
                booking__checkin_date__lte=today,
                booking__checkout_date__gt=today,
                booking__is_deleted=False,
                status__in=['pending','confirmed']

            )
            .aggregate(total_rooms=Sum('no_of_rooms_booked'))
        )
        
        total_rooms_booked_today = total_rooms_booked['total_rooms'] or 0
        
        total_rooms = RoomManagement.objects.filter(status="active").aggregate(total=Sum('number_of_rooms'))['total'] or 0
        # total_rooms_booked_as_of_today = (
        #     Bookedrooms.objects.filter(
        #         booking__checkin_date__lte=today,
        #         booking__checkout_date__gt=today,
        #         booking__is_deleted=False,
        #         status='confirmed'
        #     )
        #     .aggregate(total_rooms=Sum('no_of_rooms_booked'))['total_rooms'] or 0
        # )

        # logger.info("booked room as of today", total_rooms_booked_as_of_today)
        available_rooms=total_rooms- total_rooms_booked_today #available rooms as of today
        if current_language == "ar":
            today_date = self.convert_to_arabic_numerals(arabic_date)
        else:
            today_date = today
        total_chalets= Chalet.objects.filter(status="active",post_approval=True,approval_status='approved').count()
        booked_chalets_today = ChaletBooking.objects.filter(
                            checkin_date__lte=today,
                            checkout_date__gt=today ,
                            status__in=['pending','booked','confirmed','check-in']
                        ).values('chalet').count()
        # booked_chalets_as_of_today=ChaletBooking.objects.filter(
        #                     checkin_date__lte=today,
        #                     checkout_date__gt=today,
        #                     status__in=['booked','confirmed','check-in']
        #                 ).values('chalet').count()
        availble_chalets=total_chalets- booked_chalets_today  #available Chalets as of today  
        total_ios_users = Userdetails.objects.filter(operating_system = "IOS").count()
        total_andriod_users = Userdetails.objects.filter(operating_system = "Android").count()
        print(total_rooms_booked_today,"==================",total_rooms)
        return render(
            request,
            template_name="superuser/dashboard_overview.html",
            context={"booking_data": latest_chalet_hotel_booking,
                      'monthly':categories_monthly,
                      'monthly_data':data_monthly,
                      'weekly':categories_weekly,
                      'weekly_data':confirmed_weekly,
                      'pending_weekly':pending_weekly,
                      'cancelled_weekly':cancelled_weekly,
                      "cancel_count":cancel_count,
                      'cancel_rating':formatted_cancel_rating,
                      'confirmed_count':confirmed_count,
                      'confirmed_rating':formatted_confirm_rating,
                      'adr':daily_count,
                      'adr_rates':formatted_adr_rates,
                      'review_count':bookings_with_reviews,
                      'today':today_date,
                      'total_rooms_booked_today':total_rooms_booked_today,
                      'total_rooms':available_rooms,
                      'total_chalets': availble_chalets,
                       "LANGUAGES": settings.LANGUAGES,
                      'review_rating':formatted_review_rate,
                      'total_ios_users':total_ios_users,
                      'total_chalets_booked': booked_chalets_today,
                      'total_andriod_users':total_andriod_users}
                      
                      
        )
    def convert_to_arabic_numerals(self, text):
        mapping = {
            '0': '٠', '1': '١', '2': '٢', '3': '٣', '4': '٤',
            '5': '٥', '6': '٦', '7': '٧', '8': '٨', '9': '٩'
        }
        return ''.join(mapping.get(char, char) for char in text)




@method_decorator(super_admin_required, name='dispatch')
class ViewAllButton(CustomLoginRequiredMixin, View):
    def get(self, request):
        user_language = request.LANGUAGE_CODE
        try:
            activate(user_language)
            logger.info(f"Activated user language: {user_language}")
        except Exception as e:
            logger.error(f"Error while activating user language: {e}")

        current_date = now().date()
        try:
            user =  request.user.vendor_profile
            logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})")
            print(f"VendorProfile found for superadminr: {request.user.id}, ({request.user.username})")
            logger.info(f"Current date: {current_date}")
            if user:
                latest_booking = Booking.objects.all().order_by("-id")
                latest_chalet_booking = ChaletBooking.objects.all().order_by("-id")
                latest_chalet_hotel_booking = combine_bookings(latest_booking,latest_chalet_booking,sort=True)
                page = request.GET.get('page', 1)
                paginator = Paginator(latest_chalet_hotel_booking, 15)
                try:
                    booking_paginated = paginator.page(page)
                    logger.info(f"requested page is :{page}")
                except PageNotAnInteger:
                    logger.exception("Invalid page number; defaulting to page 1.")
                    booking_paginated = paginator.page(1)
                except EmptyPage:
                    logger.exception("Page out of range; showing last page.")
                    booking_paginated = paginator.page(paginator.num_pages)
                return render(
                    request,
                    template_name="superuser/dashboard_overview.html",
                    context={"booking_data": booking_paginated},
                )
            else:
                messages.error(request, "User Not Found")
                return redirect('loginn')

        except Exception as e:
            logger.exception(f"Unexpected error in superadmin -Review and rating view: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')

class HotelDetailEditView(LoginRequiredMixin,View):
    login_url = 'loginn' 
    redirect_field_name = 'next'
    def get(self, request, *args, **kwargs):
        activate(request.LANGUAGE_CODE)
        id = kwargs.get('pk')
        hotel = Hotel.objects.get(id=id)
        print(hotel,"========hotel============")
        meal_prices = MealPrice.objects.filter(hotel=hotel)
        meal_prices_dict = {meal_price.meal_type: meal_price.price for meal_price in meal_prices}
        images = hotel.hotel_images.all().order_by('uploaded_at')
        first_image = images.first() if images.exists() else None
        remaining_images = images.exclude(id=first_image.id) if first_image else images
        amenities = hotel.amenities.all()
        documents = hotel.attached_documents.all()
        hotel_rating = Hotel.HOTEL_RATING

        document_data = [
            {
                'url': doc.document.url,
                'filename': os.path.basename(doc.document.name)
            }
            for doc in documents
        ]


        return render(
            request,
            'superuser/hotel_detail_edit.html',
            {
                "LANGUAGES": settings.LANGUAGES,
                'hotel': hotel,
                'meal_prices': meal_prices_dict,
                "first_image": first_image,
                "remaining_images": remaining_images,
                'amenities': amenities,
                'documents': documents,
                'documents': document_data,
                'hotel_rating':hotel_rating
            }
        )


class SaveHotelDetailView(LoginRequiredMixin,View):
    login_url = 'loginn' 
    redirect_field_name = 'next'
    def post(self, request):
        print("Starting to save hotel details...")

        hotel_id = request.POST.get('hotel_id')
        print(f"Hotel ID received: {hotel_id}")

        # Retrieve the hotel object
        hotel = get_object_or_404(Hotel, id=hotel_id)
        print(f"Hotel object retrieved: {hotel}")

        try:
            # Extract data from the request
            hotel_name = request.POST.get('hotel_name')
            hotel_owner = request.POST.get('hotel_owner')
            hotel_email = request.POST.get('hotel_email')
            office_number = request.POST.get('officenumber')
            hotel_address = request.POST.get('hotel_address')
            state = request.POST.get('state')
            city = request.POST.get('city')
            country = request.POST.get('country')
            gsm_number = request.POST.get('gsmnumber')
            locality = request.POST.get('locality')
            building_no = request.POST.get('bulidingno')
            postal_code = request.POST.get('postal')
            number_of_rooms = request.POST.get('rooms')
            room_type = request.POST.get('room_type')
            hotel_rating = request.POST.get('rating')
            cr_number = request.POST.get('crnumber')
            date_of_expiry= request.POST.get('expiry')
            vat_number = request.POST.get('vatnumber')
            about_property = request.POST.get('about_property')
            hotel_policies = request.POST.get('hotel_policies')
            breakfast_price = request.POST.get('breakfast-price')
            lunch_price = request.POST.get('lunch-price')
            dinner_price = request.POST.get('dinner-price')
            selected_rating = request.POST.get('hotelrating')


            image_sources = request.POST.get('image_sources')
            document_sources = request.POST.get('document_sources')
            logo_source = request.POST.get('logo_source')
            amenity_ids = request.POST.get('amentity_ids')



            print("image_sources:", image_sources)
            print("document_sources:", document_sources)
            print("logo_source:", logo_source)
            print("amenities_list:", amenity_ids)  


            try:
                # Handle logo image
                if logo_source:
                    hotel.logo.delete()
                    hotel.logo=logo_source
                    hotel.save()
                    print("Updated logo")

                # Delete existing images
                hotel.hotel_images.all().delete()
                # print("Deleted existing hotel images")

                # Save new images
                if image_sources:
                    for image in json.loads(image_sources):
                        HotelImage.objects.create(hotel=hotel,image=image)
                        print("Saved new hotel images")

                # Delete existing documents
                hotel.attached_documents.all().delete()
                # print("Deleted existing hotel documents")

                # Save new documents
                if document_sources:
                    for document in json.loads(document_sources):
                        # print(document,"=========")
                        HotelDocument.objects.create(hotel=hotel, document=document)
                        print("Saved new hotel documents")

                # Update amenities
                if amenity_ids:
                    amenities_ids = json.loads(amenity_ids)
                    hotel.amenities.clear()  # Clear existing amenities
                    for amenity_id in amenities_ids:
                        amenity = get_object_or_404(Amenity, id=amenity_id)
                        hotel.amenities.add(amenity)
                    print("Updated hotel amenities")

            except Exception as e:
                print(f"Error: {e}")
            
            # Debug: Log received values
            print(f"Hotel Name: {hotel_name}")
            print(f"Hotel Owner: {hotel_owner}")
            print(f"Hotel Email: {hotel_email}")
            print(f"Office Number: {office_number}")
            print(f"Hotel Address: {hotel_address}")
            print(f"State: {state}")
            print(f"City: {city}")
            print(f"Country: {country}")
            print(f"GSM Number: {gsm_number}")
            print(f"Locality: {locality}")
            print(f"Building No: {building_no}")
            print(f"Postal Code: {postal_code}")
            print(f"Number of Rooms: {number_of_rooms}")
            print(f"Room Type: {room_type}")
            print(f"Hotel Rating: {hotel_rating}")
            print(f"CR Number: {cr_number}")
            print(f"VAT Number: {vat_number}")
            print(f"About Property: {about_property}")
            print(f"Hotel Policies: {hotel_policies}")
            print(f"Breakfast Price: {breakfast_price}")
            print(f"Lunch Price: {lunch_price}")
            print(f"Dinner Price: {dinner_price}")

            try:
                country, created = Country.objects.get_or_create(name=country)
                state, created = State.objects.get_or_create(
                    country=country, name=state
                )
                city, created = City.objects.get_or_create(
                    state=state, name=city, postal_code=postal_code
                )
            except Exception as e:
                print(e,"=====================")    

            hotel = get_object_or_404(Hotel, id=hotel_id)
            vendor = hotel.vendor
            if vendor:
                Userdetails_obj = vendor
                print(f"Userdetails object retrieved: {Userdetails_obj}")
                Userdetails_obj.gsm_number = gsm_number
                Userdetails_obj.save()

                if Userdetails_obj.user:
                    Userdetails_obj.user.first_name = hotel_owner
                    Userdetails_obj.user.email= hotel_email
            else:
                print("No Userdetails associated with this hotel.")

            def parse_price(price_str):
                if price_str and price_str.strip().lower() != 'n/a':
                    try:
                        return Decimal(price_str)
                    except ValueError:
                        return None
                return None

            # Save meal prices
            try:
                if breakfast_price is not None:
                    MealPrice.objects.update_or_create(
                        hotel=hotel,
                        meal_type='breakfast',
                        defaults={'price': parse_price(breakfast_price)}
                    )

                if lunch_price is not None:
                    MealPrice.objects.update_or_create(
                        hotel=hotel,
                        meal_type='lunch',
                        defaults={'price': parse_price(lunch_price)}
                    )

                # Handle dinner price
                if dinner_price is not None:
                    MealPrice.objects.update_or_create(
                        hotel=hotel,
                        meal_type='dinner',
                        defaults={'price': parse_price(dinner_price)}
                    )
    
            except Exception as e:
                print(e,"=========e=================")


            hotel.name = hotel_name
            hotel.office_number = office_number
            hotel.address = hotel_address
            hotel.locality = locality
            hotel.building_number = building_no
            hotel.hotel_rating = hotel_rating
            hotel.cr_number = cr_number
            hotel.vat_number = vat_number
            hotel.about_property = about_property
            hotel.hotel_policies = hotel_policies
            hotel.state=state
            hotel.city=city
            hotel.date_of_expiry= date_of_expiry
            hotel.hotel_rating= selected_rating
            hotel.save()

            return JsonResponse({'message': _('Hotel details saved successfully.')},status=200)

        except Exception as e:
            print(f"An error occurred: {e}")
            return JsonResponse({'error': str(e)}, status=500)
@login_required
def add_amenity_to_hotel(request):
    if request.method == "POST":
        hotel_id = request.POST.get("hotel_id")
        amenity_name = request.POST.get("amenity_name")
        amenity_icon = request.FILES.get("icon")

        hotel = get_object_or_404(Hotel, id=hotel_id)

        amenity, created = Amenity.objects.get_or_create(
            amenity_name=amenity_name,
            defaults={'icon': amenity_icon}
        )

        if not created and Amenity.objects.filter(amenity_name=amenity_name).exists():
            return JsonResponse({"error": _("Amenity with this name already exists")}, status=400)

        response_data = {
            "id": amenity.id,
            "name": amenity.amenity_name,
            "icon_url": amenity.icon.url if amenity.icon else "{% static 'icons/default_amenity_icon.png' %}"
        }

        return JsonResponse({"success": _("Amenity added"), "amenity": response_data}, status=200)

    return JsonResponse({"error": _("Invalid request")}, status=400)

@method_decorator(super_admin_required, name='dispatch')
class AddPolicyView(LoginRequiredMixin, View):
    login_url = 'loginn' 
    redirect_field_name = 'next'

    def get(self, request):
        try:
            logger.info(f"User {request.user.id} is accessing AddPolicyView.")
            logger.info(f"User is superuser: {request.user.is_superuser}")

            if request.user.is_superuser:
                try:
                    policies = PolicyCategory.objects.filter(created_by=request.user)
                    logger.info(f"Fetched {policies.count()} policies for superuser {request.user.id}.")
                except Exception as e:
                    logger.error(f"Error fetching policies for superuser {request.user.id}: {e}", exc_info=True)
                    policies = []
            else:
                logger.info(f"User {request.user.id} is not a superuser. No policies available.")
                policies = []

            if not policies:
                logger.warning(f"No policies found for user {request.user.id}.")
            
            context = {
                'policies': policies,
                "LANGUAGES": settings.LANGUAGES
            }
            return render(request, 'superuser/add_policy.html', context=context)
        except Exception as e:
            logger.error(f"An error occurred while processing AddPolicyView for user {request.user.id}: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': _('An unexpected error occurred.')}, status=500)

 
@login_required
def save_policy(request):
    if request.method == 'POST':
        category = request.POST.get('category')
        policies = request.POST.getlist('policies[]')

        if not category:
            logger.warning("Category is missing from the request.")
            return JsonResponse({'status': 'error', 'message': _('Category is required')}, status=400)
        
        if any(policy == '' for policy in policies):
            logger.warning("One or more policies are empty.")
            return JsonResponse({'status': 'error', 'message': _('Policies cannot be empty')}, status=400)

        try:
            policy_category = PolicyCategory.objects.filter(name=category, created_by=request.user)

            if not policy_category:
                logger.info(f"Creating new Policy Category: {category} for user: {request.user}")
                policy_category = PolicyCategory.objects.create(
                    name=category, 
                    created_by=request.user, 
                    policy_type='common'
                )
                
                for policy in policies:
                    if policy:
                        try:
                            PolicyName.objects.create(
                                policy_category=policy_category, 
                                title=policy, 
                                created_by=request.user,
                                policy_type='common'
                            )
                            logger.info(f"Policy '{policy}' created under category '{category}'")
                        except Exception as e:
                            logger.error(f"Error creating policy '{policy}': {e}")
                    
                logger.info(f"Policy Category '{category}' and associated policies created successfully.")
                return JsonResponse({'status': 'success', 'message': _('Policies Created Successfully')}, status=200)
            
            logger.info(f"Policy Category '{category}' already exists for user: {request.user}")
            return JsonResponse({'status': 'success', 'message': _('Policy Category Already Exists')}, status=200)

        except Exception as e:
            logger.error(f"An unexpected error occurred while saving the policy. Exception : {e}")
            return JsonResponse({'status': 'error', 'message': _('An error occurred while saving the policy')}, status=500)

    logger.warning(f"Invalid request method: {request.method} for save_policy endpoint")
    return JsonResponse({'status': 'error', 'message': _('Invalid request method')}, status=400)

class GetPolicyDataView(LoginRequiredMixin,View):
    login_url = 'loginn' 
    redirect_field_name = 'next'
    def get(self, request, category_id):
        try:
            logger.info(f"Fetching policy data for category_id: {category_id}")
            category = PolicyCategory.objects.get(id=category_id)
            logger.info(f"Category found: {category.name}")

            policies = PolicyName.objects.filter(policy_category=category, created_by=request.user)
            
            if not policies.exists():
                logger.warning(f"No policies found for category: {category.name} created by user {request.user.id}")
                return JsonResponse({'error': _('No policies found for category %(category)s created by you.') % {'category': category.name}}, status=404)

            policies_data = list(policies.values('title'))

            data = {
                'category_name': category.name,
                'policies': policies_data
            }

            logger.info(f"Successfully fetched policy data for category: {category.name} created by user {request.user.id}")
            return JsonResponse(data)

        except PolicyCategory.DoesNotExist:
            logger.error(f"Policy category with id {category_id} does not exist.")
            return JsonResponse({'error': _('Category not found')}, status=404)

        except Hotel.DoesNotExist:
            logger.error("Hotel not found while processing policies.")
            return render(request, "superuser/404.html")

        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching policy data, Exception: {e}", exc_info=True)
            return JsonResponse({'error': _('An error occurred while fetching policy data')}, status=500)

@login_required
def update_policy_data(request):
    try:
        logger.info("Starting update policy data process.")
        data = json.loads(request.body.decode('utf-8'))
        category_name = data.get('category_name')
        policies = data.get('policies', [])
        category_id = data.get('category_id')

        if not category_name or not category_id:
            logger.error("Category name or category ID is missing in the request data.")
            return JsonResponse({'status': 'error', 'message': _('Category name and category ID are required.')}, status=400)

        logger.info(f"Processing category: {category_name} with ID: {category_id}")

        category = get_object_or_404(PolicyCategory, id=category_id)
        logger.info(f"Found category: {category.name}")

        category.policy_category = category_name
        category.save()
        logger.info(f"Category name updated to: {category_name}")

        PolicyName.objects.filter(policy_category=category).delete()
        logger.info(f"Deleted existing policies for category: {category_name}")

        for policy_name in policies:
            if policy_name:
                policy, created = PolicyName.objects.get_or_create(policy_category=category, title=policy_name, created_by=request.user)
                if created:
                    logger.info(f"Created new policy: {policy_name}")
                    message = _("Successfully added new policy '%(policy_name)s' to %(category)s.") % {'policy_name': policy_name, 'category': category }
                else:
                    logger.warning(f"Policy  already exists for this category.")
                    message = _("Policy '%(policy_name)s' already exists in category '%(category)s', no new policy added.") % {'policy_name': policy_name, 'category': category }

        return JsonResponse({'status': 'success', 'message': message})

    except PolicyCategory.DoesNotExist:
        logger.error(f"Policy category with ID {category_id} does not exist.")
        return JsonResponse({'status': 'error', 'message': _('Category not found.')}, status=404)

    except Exception as e:
        logger.error(f"An unexpected error occurred in update_policy_data. Exception : {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


class DeletePolicy(View):
    def post(self, request, category_id):
        try:
            category = get_object_or_404(PolicyCategory, id=category_id)
            if category is None:
                logger.warning(f"PolicyCategory with id {category_id} is None.")
                return JsonResponse({'error': 'Policy Category not found'}, status=404)
            logger.info(f"Deleting PolicyCategory with id {category.id} and name {category.name}")

            category.delete()
            logger.info(f"PolicyCategory and name {category.name} deleted successfully")
            return JsonResponse({'message': _('PolicyCategory has been deleted successfully'), 'status': True})

        except PolicyCategory.DoesNotExist:
            logger.error(f"PolicyCategory with id {category_id} does not exist.")
            return JsonResponse({'error': _('PolicyCategory not found')}, status=404)
        
        except Exception as e:
            logger.error(f"An error occurred while deleting PolicyCategory. Exception : {e}")
            return JsonResponse({'error': _('An unexpected error occurred')}, status=500)


@method_decorator(super_admin_required, name='dispatch')
class UserManagementView(CustomLoginRequiredMixin, View):
    def get(self, request):
        """Handles GET request for user management."""
        try:
            name = request.GET.get('name', '').strip()
            status = request.GET.get('status', '').strip()
            os = request.GET.get('os', '').strip()

            logger.info("Fetching user list - Name: %s, Status: %s, OS: %s", name, status, os)

            # Base user query (excluding vendors and superusers)
            user_query = Q(is_vendor=False, is_superuser=False)

            # VendorProfile user query (only admin or superadmin vendors)
            vendor_query = Q(vendor_profile__category__in=['admin', 'superadmin'])

            # Apply name filter
            name_query = Q()
            if name:
                name_parts = name.split()
                for part in name_parts:
                    name_query |= Q(first_name__icontains=part) | Q(last_name__icontains=part) | Q(username__icontains=part)

            # Apply status filter
            status_query = Q()
            if status == 'active':
                status_query = Q(is_active=True)
            elif status == 'inactive':
                status_query = Q(is_active=False)

            # Apply OS filter
            os_query = Q()
            if os:
                os_query = Q(user_details__operating_system__iexact=os)

            # Combine queries for both normal users and vendor-admin users
            users = User.objects.filter((user_query | vendor_query) & name_query & status_query & os_query).distinct().order_by("id")

            logger.info("Users found: %d", users.count())

            # Paginate results
            paginator = Paginator(users, 15)
            page_number = request.GET.get('page', 1)
            page_obj = paginator.get_page(page_number)
            for user in page_obj.object_list:
                userdetails = getattr(user, 'user_details', None)
                
                if userdetails:
                    # Booking count
                    hotel_booking_count = Booking.objects.filter(user=userdetails).count()
                    chalet_booking_count = ChaletBooking.objects.filter(user=userdetails).count()
                    total_booking_count = hotel_booking_count + chalet_booking_count
                    user.booking_count = total_booking_count if total_booking_count > 0 else 'N/A'

                    # Wallet balance
                    try:
                        wallet = Wallet.objects.get(user=userdetails)
                        user.wallet_balance = wallet.balance
                    except Wallet.DoesNotExist:
                        user.wallet_balance = 'N/A'

                    try:
                        User_detail=Userdetails.objects.get(user= user)
                        contact_number =  User_detail.contact_number or ""
                        dial_code = User_detail.dial_code or ""
                        if contact_number.startswith('+'):
                            user.phone_number = contact_number
                        else:
                            if contact_number and dial_code:
                                user.phone_number = f"{dial_code}{contact_number}"
                        user.created_date=User_detail.created_date
                    except Userdetails.DoesNotExist:
                        user.phone_number = 'N/A'
                        user.created_date ='N/A'

                else:
                    user.booking_count = 'N/A'
                    user.wallet_balance = 'N/A'
                    user.phone_number = 'N/A'
         
            return render(request, 'superuser/user_management.html', {
                'page_obj': page_obj,
                "LANGUAGES": settings.LANGUAGES,
                'request': request
            })

        except Exception as e:
            logger.error("Error in UserManagementView GET: %s", str(e), exc_info=True)
            return JsonResponse({"error": _("An error occurred while fetching users.")}, status=500)

    def post(self, request):
        """Handles AJAX POST request to create an admin user."""
        try:
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            email = request.POST.get("email", "").strip().lower()
            password = request.POST.get("password", "")
            confirm_password = request.POST.get("confirm_password", "")
            is_active = request.POST.get("is_active", "").lower() == "true"

            logger.info("Creating new admin user - Email: %s, Active: %s", email, is_active)

            errors = {}

            if not first_name or not re.match(r'^[A-Za-z\s]+$', first_name):
                errors["first_name"] = _("First name can only contain letters and spaces.")
            
            if not last_name or not re.match(r'^[A-Za-z\s]+$', last_name):
                errors["last_name"] = _("Last name can only contain letters and spaces.")

            if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                errors["email"] = _("Please enter a valid email address.")

            if len(password) < 8 or not re.search(r"[A-Z]", password) or not re.search(r"[a-z]", password) or not re.search(r"\d", password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
                errors["password"] = _("Password must be at least 8 characters and include uppercase, lowercase, a number, and a special character.")

            if password != confirm_password:
                errors["confirm_password"] = _("Passwords do not match.")

            if User.objects.filter(email=email).exists():
                errors["email"] = _("Email is already registered.")

            if errors:
                logger.warning("Validation errors while creating user: %s", errors)
                return JsonResponse({"errors": errors}, status=400)

            # Create user
            user = User.objects.create(
                username=email,  
                first_name=first_name,
                last_name=last_name,
                email=email,
                is_active=is_active
            )
            user.set_password(password)
            user.save()

            # Create vendor profile
            VendorProfile.objects.create(
                user=user,
                name=f"{first_name} {last_name}",
                category="admin"
            )

            logger.info("Admin user created successfully: %s", email)
            return JsonResponse({"success": _("New admin has been added successfully.")}, status=201)

        except Exception as e:
            logger.error("Error in UserManagementView POST: %s", str(e), exc_info=True)
            return JsonResponse({"error": _("An error occurred while creating the admin user.")}, status=500)

class ToggleUserStatusView(CustomLoginRequiredMixin, View):
    def post(self, request):
        user_id = request.POST.get('user_id')
        if not user_id:
            return JsonResponse({"error": "User ID not provided"}, status=400)

        try:
            user = User.objects.get(id=user_id)
            user.is_active = not user.is_active  # Toggle status
            user.save()
            return JsonResponse({"status": "success", "is_active": user.is_active})
        except User.DoesNotExist:
            return JsonResponse({"error": _("User not found")}, status=404)
    
@method_decorator(super_admin_required, name='dispatch')
class ReviewAndRating(CustomLoginRequiredMixin, View):
    def get(self, request):
        user_language = request.LANGUAGE_CODE
        try:
            activate(user_language)
            logger.info(f"Activated user language: {user_language}")
        except Exception as e:
            logger.error(f"Error while activating user language: {e}")

        current_date = now().date()
        logger.info(f"Current date: {current_date}")
        try:
            user =  request.user.vendor_profile        
            if user:       
                logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})")
                print(f"VendorProfile found for superadminr: {request.user.id} ({request.user.username})")
                reviews = RecentReview.objects.all().order_by("-date")
                reviews_type = 'hotel'
                ratings = RecentReview.RATING
                #pagination
                page = request.GET.get('page', 1)  
                paginator = Paginator(reviews, 15)
                try:
                    review_paginated = paginator.page(page)
                    logger.info(f"Paginated review - Page: { review_paginated }")
                except PageNotAnInteger:
                    review_paginated = paginator.page(1)  
                    logger.warning("Page not an integer. Defaulting to page 1.")
                except EmptyPage:
                    review_paginated = paginator.page(paginator.num_pages) 

                return render(
                    request, 
                    "superuser/review_rating.html", 
                    {"reviews":  review_paginated, "ratings": ratings ,'reviews_type' : reviews_type,"LANGUAGES": settings.LANGUAGES}
                )
            else:
                messages.error(request, "User not found")
                return redirect('loginn')

        except Exception as e:
            logger.exception(f"Unexpected error in superadmin -Review and rating view: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')
        
    def post(self,request):
        try:
            logger.info("Processing POST request for ReviewAndRating.")            
            page = request.POST.get('page', 1)  
            from_date_s = request.POST.get("from_date")
            to_date_s = request.POST.get("to_date")
            review_rating = request.POST.get("review_rating")
            category=request.POST.get("category")
            logger.info(f"POST parameters received - From Date: {from_date_s}, To Date: {to_date_s}, Page: {page},  review_rating: {review_rating} ,Category:{category}")
            from_date = None
            to_date = None
            #fetch user profile
            user =  request.user.vendor_profile               
            logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})")   
            if from_date_s:
                from_date = timezone.make_aware(datetime.strptime(from_date_s, "%Y-%m-%d"))
            if to_date_s:
                to_date = timezone.make_aware(datetime.strptime(to_date_s, "%Y-%m-%d")) + timedelta(days=1) - timedelta(seconds=1)
            if category :
                if category =='HOTEL':
                    reviews = RecentReview.objects.all()
                    reviews_type = 'hotel'

                    if from_date and to_date and review_rating:
                        reviews = reviews.filter(
                            date__range=[from_date, to_date], rating=review_rating
                        ).order_by("-date")

                    elif from_date and to_date:
                        reviews = reviews.filter(date__gte=from_date, date__lte=to_date).order_by("-date")
                        for i in reviews:
                            print(i.date)
                    elif from_date and review_rating:
                        reviews = reviews.filter(date__gte=from_date, rating=review_rating).order_by("-date")

                    elif to_date and review_rating:
                        reviews = reviews.filter(date__lte=to_date, rating=review_rating).order_by("-date")

                    elif from_date:
                        reviews = reviews.filter(date__gte=from_date).order_by("-date")

                    elif to_date:
                        reviews = reviews.filter(date__lte=to_date).order_by("-date")

                    elif review_rating:
                        reviews = reviews.filter(rating=review_rating).order_by("-date")
                    paginator = Paginator(reviews, 15)
                    try:
                        review_paginated = paginator.page(page)
                    except PageNotAnInteger:
                        review_paginated = paginator.page(1)  
                    except EmptyPage:
                        review_paginated = paginator.page(paginator.num_pages) 

                    ratings = RecentReview.RATING
                    return render(
                        request, 
                    "superuser/review_rating.html", 
                    {"reviews": review_paginated, "ratings": ratings ,'reviews_type' : reviews_type,"LANGUAGES": settings.LANGUAGES}
                    )
                else:
                    reviews = ChaletRecentReview.objects.all()
                    reviews_type = 'chalet'

                    if from_date and to_date and review_rating:
                        reviews = reviews.filter(
                            date__range=[from_date, to_date], rating=review_rating
                        ).order_by("-date")

                    elif from_date and to_date:
                        reviews = reviews.filter(date__range=[from_date, to_date]).order_by("-date")

                    elif from_date and review_rating:
                        reviews = reviews.filter(date__gte=from_date, rating=review_rating).order_by("-date")

                    elif to_date and review_rating:
                        reviews = reviews.filter(date__lte=to_date, rating=review_rating).order_by("-date")

                    elif from_date:
                        reviews = reviews.filter(date__gte=from_date).order_by("-date")

                    elif to_date:
                        reviews = reviews.filter(date__gte=to_date).order_by("-date")

                    elif review_rating:
                        reviews = reviews.filter(rating=review_rating).order_by("-date")
                    paginator = Paginator(reviews, 15)
                    try:
                        review_paginated = paginator.page(page)
                    except PageNotAnInteger:
                        logger.warning("Invalid page number; defaulting to page 1.")
                        review_paginated = paginator.page(1)  
                    except EmptyPage:
                        logger.warning("Page out of range; showing last page.")
                        review_paginated = paginator.page(paginator.num_pages) 

                    ratings = RecentReview.RATING
                    return render(
                        request, 
                    "superuser/review_rating.html", 
                    {"reviews": review_paginated, "ratings": ratings ,'reviews_type' : reviews_type,"LANGUAGES": settings.LANGUAGES}
                    )
            else:
                logger.error("category Not found")
                return render(request,"superuser/review_rating.html", {"error": "Category Not found"})

        except Exception as e:
            logger.exception(f"Unexpected error in superadmin -Review and rating view: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')
          
                
@method_decorator(super_admin_required, name='dispatch')
class SuperUserOffer(View):
    template_name = "superuser/superuser_offers.html"

    def get(self, request):
        user_language = request.LANGUAGE_CODE
        try:
            activate(user_language)
            logger.info(f"Activated user language: {user_language}")
        except Exception as e:
            logger.error(f"Error while activating user language: {e}")

        current_date = now().date()
        logger.info(f"Current date: {current_date}")
        try:
            user =  request.user.vendor_profile               
            logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})")
            if user:
                try:
                    hotels = Hotel.objects.all()
                    chalets = Chalet.objects.all()
                    offers = Promotion.objects.filter(source='admin', status='active', category="common").order_by('-id')
                    logger.info(f"Retrieved {offers.count()} offers, {hotels.count()} hotels, and {chalets.count()} chalets.")
                except Exception as e:
                    logger.error("Error retrieving hotels, chalets, or offers.")
                    messages.error(request, _("Error retrieving hotels, chalets, or offers.."))
                    return redirect('loginn')
                promotion_types = Promotion.PROMOTION_TYPE_CHOICES
                page = request.GET.get('page', 1)
                paginator = Paginator(offers, 15)
                try:
                    offers_paginated = paginator.page(page)
                except PageNotAnInteger:
                    logger.warning("Invalid page number; defaulting to page 1.")
                    offers_paginated = paginator.page(1)
                except EmptyPage:
                    logger.warning("Page out of range; showing last page.")
                    offers_paginated = paginator.page(paginator.num_pages)

                return render(
                    request,
                    self.template_name,
                    {
                        "offers": offers_paginated,
                        "LANGUAGES": settings.LANGUAGES,
                        "promotion_types": promotion_types,
                        "hotels": hotels,
                        "chalets": chalets,
                    },
                )
            else:
                messages.error(request, _("User not found"))
                return redirect('loginn')

        except Exception as e:
            logger.exception(f"Unexpected error in superadmin -offer page{e}")
            messages.error(request, _("User not found ."))
            return redirect('loginn')
        

    def post(self, request):
        try:
            logger.info("Processing Post request at Superuseroffer")
            offer_name = request.POST.get('offer_name')
            description = request.POST.get('description')
            category = request.POST.get('category')
            start_date = request.POST.get('validity_from')
            end_date = request.POST.get('validity_to')
            discount_percentage = request.POST.get('discount_percentage') or None

            selected_hotels_raw = request.POST.getlist('selected_hotels')
            logger.info(selected_hotels_raw)
            selected_chalets_raw = request.POST.getlist('selected_chalets')
            logger.info(selected_chalets_raw)
            try:
                user =  request.user.vendor_profile               
                logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})")
                if user:
                    selected_hotels = [hotel.split(':')[1].strip() for hotel in selected_hotels_raw if ':' in hotel]
                    selected_chalets = [chalet.split(':')[1].strip() for chalet in selected_chalets_raw if ':' in chalet]

                    logger.info(f"Selected hotels: {selected_hotels}")
                    logger.info(f"Selected chalets: {selected_chalets}")

                    # Date parsing
                    def parse_date(date_str, date_type):
                        if date_str:
                            try:
                                return datetime.strptime(date_str, '%Y-%m-%d').date()
                            except ValueError:
                                logger.error(f"Invalid {date_type} date format: {date_str}. Expected YYYY-MM-DD.")
                                raise ValidationError(f"{date_type.capitalize()} date must be in YYYY-MM-DD format.")
                        return None

                    start_date_value = parse_date(start_date, "start")
                    end_date_value = parse_date(end_date, "end")

                    # Category-specific fields
                    promo_code = request.POST.get('promo_code') if category == 'promo_code' else None
                    max_uses = request.POST.get('max_uses') if category == 'promo_code' else None
                    targeted_type = request.POST.get('targeted_type', 'common')
                    minimum_spend = request.POST.get('minimum_spend') if category == 'common' else None
                    occasion_name = request.POST.get('occasion_name') if category == 'seasonal_event' else None
                    points_required = request.POST.get('points_required') if category == 'loyalty_program' else None
                    promo_validity_from = request.POST.get('promo_validity_from') if category == 'promo_code' else None
                    promo_validity_to = request.POST.get('promo_validity_to') if category == 'promo_code' else None
                    if category == "promo_code":
                        if promo_validity_from:
                            try:
                                start_date_value = datetime.strptime(promo_validity_from, '%Y-%m-%d').date()
                            except ValueError:
                                raise ValidationError("Start date must be in YYYY-MM-DD format.")
                    
                        if promo_validity_to:
                            try:
                                end_date_value = datetime.strptime(promo_validity_to, '%Y-%m-%d').date()
                            except ValueError:
                                raise ValidationError("End date must be in YYYY-MM-DD format.")


                    promotion = Promotion(
                        title=offer_name,
                        category=category,
                        description=description,
                        discount_percentage=discount_percentage,
                        promo_code=promo_code,
                        max_uses=max_uses,
                        occasion_name=occasion_name,
                        points_required=points_required,
                        start_date=start_date_value,
                        end_date=end_date_value,
                        minimum_spend=minimum_spend,
                        promotion_type=targeted_type,
                        source='admin',
                    )

                    try:
                        promotion.save()
                        logger.info(f"Promotion '{offer_name}' saved successfully.")
                    except Exception as e:
                        logger.error(f"Failed to save promotion '{offer_name}'.")
                        return redirect(reverse("superuser_offers"))

                    for hotel_id in selected_hotels:
                        try:
                            hotel = Hotel.objects.get(id=hotel_id)
                            promotion.multiple_hotels.add(hotel)
                            logger.info(f"Hotel {hotel.id} added to promotion {promotion.id}.")
                        except Hotel.DoesNotExist:
                            logger.error(f"Hotel with ID {hotel_id} does not exist.")

                    for chalet_id in selected_chalets:
                        try:
                            chalet = Chalet.objects.get(id=chalet_id)
                            promotion.multiple_chalets.add(chalet)
                            logger.info(f"Chalet {chalet.id} added to promotion {promotion.id}.")
                        except Chalet.DoesNotExist:
                            logger.error(f"Chalet with ID {chalet_id} does not exist.")

                    logger.info(f"Promotion '{offer_name}' creation successful. Redirecting to 'superuser_offers'.")
                    return redirect('superuser_offers')
            except:
                logger.exception(f"Unexpected error in superadmin -offer page{e}")
                messages.error(request, _("User not found ."))
                return redirect('loginn')
        except Exception as e:
            logger.exception(f"Unexpected error in superadmin -offer page{e}")
            messages.error(request, _("Unexpected error in superadmin -offer page"))
            return redirect('loginn')

@method_decorator(super_admin_required, name='dispatch')
class SuperUserOfferPromotionsDetailView(View):
    def get(self, request, *args, **kwargs):
        try:
            logger.info("Processing GET request at offerDetailView")
            offer_id = kwargs.get("pk")
            if offer_id:
                logger.info(f"Offerdetail id received :{offer_id}")
                user = request.user.vendor_profile
                if not user:
                    logger.warning(f"No user found ")
                    return redirect('loginn') 
                else:
                    logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                    try:
                        offer = Promotion.objects.get(pk=offer_id)
                        data = {
                            "offer_name": offer.title,
                            "description": offer.description,
                            "category":offer.category,
                            "discount_percentage": offer.discount_percentage,  
                            "discount_value": offer.discount_value,
                            "minimum_spend":offer.minimum_spend,
                            "validity_from": offer.start_date,
                            "validity_to": offer.end_date,
                            "promo_code":offer.promo_code,
                            "max_uses":offer.max_uses,
                            "targeted_offer_type":offer.promotion_type,
                            "occasion_name":offer.occasion_name,
                            "points_required":offer.points_required,
                            "hotels": list(offer.multiple_hotels.values_list('id', flat=True)),
                            "chalets": list(offer.multiple_chalets.values_list('id', flat=True)),          
                        }
                        logger.info("offer retreived succesfully")
                        return JsonResponse(data)
                    except Promotion.DoesNotExist:
                        logger.info("Promotion doesn't found")
                        return render(request, "accounts/offer_promotion.html", {"error": _(" Offerpromotion ID doesn't exist.")}) 
            else:
                logger.info("Promotion Id Not found")
                return render(request, "accounts/offer_promotion.html", {"error": _(" Offerpromotion ID needed.")})    
        except Exception as e:
            logger.exception(f"Unexpected error in offerDetailView GET: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')  

    def post(self, request, *args, **kwargs):
        try:
            offer_id = kwargs.get("pk")
            if offer_id:
                user =  request.user.vendor_profile       
                if user:  
                    logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})")
      
                    try:
                        logger.info(f"Updating promotion with ID: {offer_id}")
                        promotion = get_object_or_404(Promotion, pk=offer_id)
                        def parse_date(date_str, field_name):
                            if date_str:
                                try:
                                    return datetime.strptime(date_str, '%Y-%m-%d').date()
                                except ValueError:
                                    logger.error(f"Invalid format for {field_name}: {date_str}. Expected YYYY-MM-DD.")
                                    raise ValidationError(f"{field_name} must be in YYYY-MM-DD format.")
                            return None

                        offer_name = request.POST.get('offer_name', '').strip()
                        description = request.POST.get('description', '').strip()
                        category = request.POST.get('category', '').strip()
                        start_date = request.POST.get('validity_from')
                        end_date = request.POST.get('validity_to')
                        discount_percentage = request.POST.get('discount_percentage') or None
                        selected_hotels_raw = request.POST.getlist('selected_hotels[]')
                        selected_chalets_raw = request.POST.getlist('selected_chalets[]')
                        promo_validity_from = request.POST.get('promo_validity_from') if category == 'promo_code' else None
                        promo_validity_to = request.POST.get('promo_validity_to') if category == 'promo_code' else None

                        start_date_value = parse_date(start_date, "Start Date")
                        end_date_value = parse_date(end_date, "End Date")

                        selected_hotels = [
                            hotel.split(':')[1].strip() for hotel in selected_hotels_raw if ':' in hotel
                        ]
                        selected_chalets = [
                            chalet.split(':')[1].strip() for chalet in selected_chalets_raw if ':' in chalet
                        ]

                        logger.info(f"Selected hotels: {selected_hotels}")
                        logger.info(f"Selected chalets: {selected_chalets}")
                        if category == "promo_code":
                            if promo_validity_from:
                                try:
                                    start_date_value = datetime.strptime(promo_validity_from, '%Y-%m-%d').date()
                                except ValueError:
                                    raise ValidationError("Start date must be in YYYY-MM-DD format.")
                        
                            if promo_validity_to:
                                try:
                                    end_date_value = datetime.strptime(promo_validity_to, '%Y-%m-%d').date()
                                except ValueError:
                                    raise ValidationError("End date must be in YYYY-MM-DD format.")


                        # Update promotion fields
                        promotion.title = offer_name
                        promotion.description = description
                        promotion.category = category
                        promotion.start_date = start_date_value
                        promotion.end_date = end_date_value
                        promotion.discount_percentage = discount_percentage
                        promotion.minimum_spend = (
                            request.POST.get('minimum_spend') if category == 'common' else None
                        )
                        promotion.promo_code = (
                            request.POST.get('promo_code') if category == 'promo_code' else None
                        )
                        promotion.max_uses = (
                            request.POST.get('max_uses') if category == 'promo_code' else None
                        )
                        promotion.promotion_type = request.POST.get('targeted_type', 'common')
                        promotion.occasion_name = (
                            request.POST.get('occasion_name') if category == 'seasonal_event' else None
                        )
                        promotion.points_required = (
                            request.POST.get('points_required') if category == 'loyalty_program' else None
                        )

                        try:
                            promotion.save()
                            logger.info(f"Promotion with ID {offer_id} updated successfully.")
                        except Exception as e:
                            logger.error(f"Failed to update promotion with ID {offer_id}: {e}")
                            return JsonResponse({"error": _("Failed to update promotion")}, status=500)

                        current_hotels = promotion.multiple_hotels.all()
                        selected_hotels_ids = set(selected_hotels)

                        hotels_to_remove = current_hotels.exclude(id__in=selected_hotels_ids)
                        for hotel in hotels_to_remove:
                            promotion.multiple_hotels.remove(hotel)
                            logger.info(f"Hotel with ID {hotel.id} removed from promotion {offer_id}.")

                        for hotel_id in selected_hotels_ids:
                            try:
                                hotel = Hotel.objects.get(id=hotel_id)
                                if hotel not in current_hotels:
                                    promotion.multiple_hotels.add(hotel)
                                    logger.info(f"Hotel with ID {hotel_id} added to promotion {offer_id}.")
                            except Hotel.DoesNotExist:
                                logger.warning(f"Hotel with ID {hotel_id} does not exist.")

                        current_chalets = promotion.multiple_chalets.all()
                        selected_chalets_ids = set(selected_chalets)

                        chalets_to_remove = current_chalets.exclude(id__in=selected_chalets_ids)
                        for chalet in chalets_to_remove:
                            promotion.multiple_chalets.remove(chalet)
                            logger.info(f"Chalet with ID {chalet.id} removed from promotion {offer_id}.")

                        for chalet_id in selected_chalets_ids:
                            try:
                                chalet = Chalet.objects.get(id=chalet_id)
                                if chalet not in current_chalets:
                                    promotion.multiple_chalets.add(chalet)
                                    logger.info(f"Chalet with ID {chalet_id} added to promotion {offer_id}.")
                            except Chalet.DoesNotExist:
                                logger.warning(f"Chalet with ID {chalet_id} does not exist.")

                        logger.info(f"Promotion update completed for ID {offer_id}. Redirecting to 'superuser_offers'.")
                        return redirect(reverse("superuser_offers"))

                    except Promotion.DoesNotExist:
                        logger.error(f"Promotion with ID {offer_id} not found.")
                        return render(request, "superuser/superuser_offers.html", {"error": _(" Offerpromotion ID Not found.")}) 
                else:
                    messages.error(request, _("User not found ."))
                    return redirect('loginn')
            else:
                logger.exception(f"Offer id needed")
                return render(request, "superuser/superuser_offers.html", {"error": _(" Offerpromotion ID Needed.")}) 
        except Exception as e:
            logger.exception(f"Unexpected error in superadmin -offer page{e}")
            messages.error(request, _("Unexpected error in superadmin -offer page"))
            return redirect('loginn')

@method_decorator(super_admin_required, name='dispatch')        
class SuperUserOfferFilterView(View):
    template_name = "superuser/superuser_offers.html"
    def get(self, request):
        try:
            logger.info("processing GET request at the  SuperUserOfferFilterView")
            discount = request.GET.get("discount")
            page = request.GET.get("page", 1)  
            if discount and page:
                user =  request.user.vendor_profile     
                if user:  
                    try:
                        offers = Promotion.objects.filter(source='admin',status='active')
                        if discount:
                            offers = offers.filter(category=discount).order_by('-id')
                        else:
                            logger.info("error in fetching discount at superusers offer section")
                            return render(request, 'superuser/404.html') 
                        paginator = Paginator(offers, 15)
                        try:
                            offers_paginated = paginator.page(page)
                        except PageNotAnInteger:
                            offers_paginated = paginator.page(1)  
                        except EmptyPage:
                            offers_paginated = paginator.page(paginator.num_pages) 
                        return render(
                            request,
                            self.template_name,
                            context={
                                "offers":  offers_paginated ,
                                "discount": discount 
                            },
                        )
                    except Promotion.DoesNotExist:
                        logger.info("offer not found")
                        return render(request, "accounts/offer_promotion.html", {"error": _("Promotion Not exist.")})  
                else:
                    messages.error(request, _("User not found ."))
                    return redirect('loginn')
        except Exception as e:
            logger.exception(f"Unexpected error in SuperUserOfferFilterView GET: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn') 
    def post(self, request):
        try:
            logger.info("processing POST request at the  SuperUserOfferFilterView")
            discount = request.POST.get("discount")
            page = request.POST.get("page", 1)  
            if discount and page:
                user =  request.user.vendor_profile     
                if user:  
                    try:
                        offers = Promotion.objects.filter(source='admin',status='active')
                        if discount:
                            offers = offers.filter(category=discount).order_by('-id')
                        else:
                            logger.info("error in fetching discount at superusers offer section")
                            return render(request, 'superuser/404.html') 
                        paginator = Paginator(offers, 15)
                        try:
                            offers_paginated = paginator.page(page)
                        except PageNotAnInteger:
                            offers_paginated = paginator.page(1)  
                        except EmptyPage:
                            offers_paginated = paginator.page(paginator.num_pages) 
                        return render(
                            request,
                            self.template_name,
                            context={
                                "offers":  offers_paginated ,
                                "discount": discount 
                            },
                        )
                    except Promotion.DoesNotExist:
                        logger.info("offer not found")
                        return render(request, "accounts/offer_promotion.html", {"error": _("Promotion Not exist.")})  
                else:
                    messages.error(request, _("User not found ."))
                    return redirect('loginn')
        except Exception as e:
            logger.exception(f"Unexpected error in SuperUserOfferFilterVieW POST: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn') 
@method_decorator(super_admin_required, name='dispatch')
class SuperUserOfferDeleteView(View):
    def delete(self, request, *args, **kwargs):
        try:
            logger.info("Delete request processing at the OfferDeleteView")
            offer_id = kwargs.get("pk")
            user =  request.user.vendor_profile   
            if user: 
                logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})")   
                try:
                    offer = Promotion.objects.get(pk=offer_id)
                    offer.status = 'deleted'
                    offer.save()
                    logger.info(f"Promotion:{offer} deleted succesfully")
                    return JsonResponse({"message": _("Offer deleted successfully")})
                except Promotion.DoesNotExist:
                    logger.info("offer not found")
                    return render(request, "accounts/offer_promotion.html", {"error": _("Promotion Not exist.")})   
            else:
                logger.info("User Id Not found")
                messages.error(request, _("vendor profile not found"))
                return redirect('loginn')         
        except Exception as e:
            logger.exception(f"Unexpected error in offermanagement POST: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn') 
        
        
@method_decorator(super_admin_required, name='dispatch')
class RoomTypesManagementView(View):
    def get(self, request):
        """ Fetch and display filtered room types with pagination """
        name_query = request.GET.get("name", "").strip()
        status_filter = request.GET.get("status", "all").strip()
        page_number = request.GET.get("page", 1)  # Get the page number from request

        # Start with all room types
        room_types = Roomtype.objects.all()

        if name_query:
            room_types = room_types.filter(room_types__icontains=name_query) | room_types.filter(room_types_arabic__icontains=name_query)

        if status_filter and status_filter != "all":
            room_types = room_types.filter(status=status_filter)

        # Apply pagination
        paginator = Paginator(room_types, 15)  # Show 10 room types per page
        page_obj = paginator.get_page(page_number)

        return render(request, 'superuser/room_type.html', {
            'LANGUAGES': settings.LANGUAGES,
            'request': request,
            'page_obj': page_obj,  # Pass paginated object
            'search_query': name_query,
            'selected_status': status_filter
        })

    def post(self, request):
        """ Handle Add, Edit, and Delete operations """
        action = request.POST.get("action")  # Action type: add, edit, delete

        if action == "add":
            return self.add_room_type(request)
        elif action == "edit":
            return self.edit_room_type(request)
        elif action == "delete":
            return self.delete_room_type(request)
        else:
            return JsonResponse({"error": _("Invalid action!")}, status=400)

    def add_room_type(self, request):
        """ Add a new room type """
        room_types = request.POST.get("room_types")
        room_types_arabic = request.POST.get("room_types_arabic")
        status = request.POST.get("status")

        if Roomtype.objects.filter(room_types=room_types).exists():
            return JsonResponse({"error": _("Room type already exists!")}, status=400)

        Roomtype.objects.create(room_types=room_types, room_types_arabic=room_types_arabic, status=status)
        return JsonResponse({"message": _("Room type added successfully!")})

    def edit_room_type(self, request):
        """ Edit an existing room type """
        room_id = request.POST.get("id")
        room_types = request.POST.get("room_types")
        room_types_arabic = request.POST.get("room_types_arabic")
        status = request.POST.get("status")

        room = get_object_or_404(Roomtype, id=room_id)
        room.room_types = room_types
        room.room_types_arabic = room_types_arabic
        room.status = status
        room.save()

        return JsonResponse({"message": _("Room type updated successfully!")})

    def delete_room_type(self, request):
        """ Delete a room type """
        room_id = request.POST.get("id")
        room = get_object_or_404(Roomtype, id=room_id)
        room.delete()
        return JsonResponse({"message": _("Room type deleted successfully!")})

# Chalet type view
@method_decorator(super_admin_required, name='dispatch')
class ChaletTypeView(View):
    def get(self, request):
        try:
            user =  request.user.vendor_profile   
            page = request.GET.get("page", 1)  
            if user: 
                logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})")  
                try:
                    chalet_types = ChaletType.objects.filter(status__in=["active", "inactive"]).order_by('-id')
                    paginator = Paginator(chalet_types , 15)
                    try:
                       chalet_types  = paginator.page(page)
                    except PageNotAnInteger:
                       chalet_types  = paginator.page(1)  
                    except EmptyPage:
                       chalet_types = paginator.page(paginator.num_pages) 
                    return render(request, 'superuser/chalet_type.html', {
                    'LANGUAGES': settings.LANGUAGES,
                    'request': request,'chalet_type':chalet_types 
                })
                except chalet_types.DoesNotExist:
                    logger.error(f"An exception occured while fetching  ChaletType objects.")
            else:
                logger.info("User Id Not found")
                messages.error(request, _("vendor profile not found"))
                return redirect('loginn')  
        except Exception as e:
            logger.exception(f"Unexpected error in HotelTypeView POST: {e}")

        return render(request, 'superuser/chalet_type.html', {
            'LANGUAGES': settings.LANGUAGES,
            'request': request,
        })
    def post(self,request):
        try:
            logger.info("request received") 
            user =  request.user.vendor_profile   
            if user:
                user_data=request.user
                try:
                    logger.info(f"User Detail  found. User: {user_data})")
                    name = request.POST.get("name")
                    arabic_name = request.POST.get("arabic_name")
                    status = request.POST.get("status", "active")
                    icon_file = request.FILES.get("icon")
                    logger.info(f"Received parameters are name:{name},arabic_name:{arabic_name},status:{status},user:{user}")
                    logger.info("Validation completed, creating ChaletType object")
                    chalet_type = ChaletType.objects.create(name=name,arabic_name=arabic_name,status=status,icon=icon_file,created_by=user_data      
                    ) 
                    if chalet_type:  
                        logger.info(f"Chalet Type created successfully {chalet_type}")
                        return JsonResponse({"message": _("Chalet type created successfully")})
                except Exception as e :
                    logger.exception(f"An exception occured:{e}")
            else:
                logger.info("User Id Not found")
                messages.error(request, _("vendor profile not found"))
                return redirect('loginn')                   
        except Exception as e:
            logger.exception(f"Unexpected error in ChaletTypeView POST: {e}")


@method_decorator(super_admin_required, name='dispatch')
class ChaletTypeDetail(View):
    def get(self, request, *args, **kwargs):
        try:
            logger.info("GET request processing at the HotelTypeDetail")
            Chalettype_id = kwargs.get("pk")
            user =  request.user.vendor_profile   
            if user: 
                logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})")  
                try:
                    Chalet_type_value=ChaletType.objects.get(id=Chalettype_id) 
                    data={
                            "name":   Chalet_type_value.name,
                            "arabic_name":   Chalet_type_value.arabic_name,
                            "icon":   Chalet_type_value.icon.url,
                            "status":  Chalet_type_value.status,           
                        }
                    logger.info("Chalet type retreived succesfully")
                    return JsonResponse(data)
                except ChaletType.DoesNotExist:
                    logger.error(f"Could not fetch Chalet type details.")
                    return JsonResponse({'status': 'error', 'message': _('Chalet type not found')}, status=404)
            else:
                logger.info("User Id Not found")
                messages.error(request, _("vendor profile not found"))
                return redirect('loginn')   
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    def post(self, request, *args, **kwargs):
        try:
            logger.info("Processing Post request at the  ChaletTypeDetail")
            Chalettype_id = kwargs.get("pk")
            user =  request.user.vendor_profile   
            if user: 
                logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})")  
                try:
                    chalet_type = get_object_or_404(ChaletType, id= Chalettype_id)
                    if request.POST.get("name"):
                        chalet_type.name = request.POST["name"]
                    if request.POST.get("name_arabic"):
                        chalet_type.arabic_name = request.POST["name_arabic"]
                    if request.POST.get("status"):
                        chalet_type.status = request.POST["status"]
                    if "icon" in request.FILES:
                        chalet_type.icon = request.FILES["icon"]
                    chalet_type.save()
                    return JsonResponse({'status': 'success', 'message': _('Chalet type updated successfully')})
                except HotelType.DoesNotExist:
                    logger.error(f"Could not fetch Chalet type details.")
                    return JsonResponse({'status': 'error', 'message': _('Chalet type not found')}, status=404)
            else:
                logger.info("User Id Not found")
                messages.error(request, _("vendor profile not found"))
                return redirect('loginn')   
        except Exception as e:
            logger.error(f"An exception occured at the POST method of Chalet type detail view. Exception :{str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    def delete(self, request, *args, **kwargs):
        try:
            logger.info("Processing delete request at the  ChaletTypeDetail")
            Chalettype_id = kwargs.get("pk")
            user =  request.user.vendor_profile   
            if user: 
                logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})") 
                try:
                    chalet_type = ChaletType.objects.get(id=Chalettype_id)
                    if chalet_type:
                        chalet_type.status='deleted'
                        chalet_type.save()
                        return JsonResponse({'status': 'success', 'message': _('Chalet type removed  successfully')})
                except ChaletType.DoesNotExist:
                    logger.error(f"Could not fetch chalet type details.")
                    return JsonResponse({'status': 'error', 'message': _('Chalet type not found')}, status=404)
            else:
                logger.info("User Id Not found")
                messages.error(request, _("vendor profile not found"))
                return redirect('loginn')   
        except Exception as e:
            logger.error(f"An exception occured at the DELETE method of chalet type detail view. Exception :{str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
@method_decorator(super_admin_required, name='dispatch')
class ChaletTypeSearch(View):
    def get(self, request, *args, **kwargs):
        try:
            user =  request.user.vendor_profile  
            if user:
                name_query = request.GET.get("name", "").strip()
                status_query = request.GET.get("status", "all")
                page = request.GET.get("page", 1)  

                chalet_types = ChaletType.objects.filter(status__in=["active", "inactive"]).order_by('-id')
                if name_query:
                    if re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]', name_query):
                        chalet_types = chalet_types.filter(arabic_name__icontains=name_query)
                    else:
                        chalet_types = chalet_types.filter(Q(name__icontains=name_query) | Q(arabic_name__icontains=name_query))

                if status_query != "all":
                    chalet_types = chalet_types.filter(status=status_query)
                paginator = Paginator(chalet_types, 15)
                try:
                    chalet_types = paginator.page(page)
                except PageNotAnInteger:
                    chalet_types = paginator.page(1)  
                except EmptyPage:
                    chalet_types= paginator.page(paginator.num_pages) 
                return render(request, "superuser/chalet_type.html", {"chalet_type": chalet_types})
            else:
                logger.info("User Id Not found")
                messages.error(request, _("vendor profile not found"))
                return redirect('loginn')  
        except Exception as e:
            logger.error(f"An exception occured at the search method of chalet type. Exception :{str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
from urllib.parse import unquote
def chalet_type_check_name(request):
    try:
        logger.info(f"Raw Request Data: {request.GET}")

        name = request.GET.get("name", "").strip()
        arabic_name = unquote(request.GET.get("arabic_name", "").strip())
        chalet_type_id = request.GET.get("chalet_type_id")  

        chalet_type = ChaletType.objects.exclude(id=chalet_type_id) if chalet_type_id else ChaletType.objects.all()

        english_exists = chalet_type.filter(name__iexact=name).exists() if name else False
        arabic_exists = chalet_type.filter(arabic_name__iexact=arabic_name).exists() if arabic_name else False

        return JsonResponse({'english_exists': english_exists, 'arabic_exists': arabic_exists})

    except Exception as e:
        logger.error(f"Error in hotel_type_check_name: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@method_decorator(super_admin_required, name='dispatch')
class HotelTypeView(CustomLoginRequiredMixin, View):
    def get(self, request):
        try:
            user =  request.user.vendor_profile   
            page = request.GET.get("page", 1)  
            if user: 
                logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})")  
                try:
                    hotel_types = HotelType.objects.filter(status__in=["active", "inactive"]).order_by('-id')
                    paginator = Paginator(hotel_types, 15)
                    try:
                       hotel_type = paginator.page(page)
                    except PageNotAnInteger:
                        hotel_type = paginator.page(1)  
                    except EmptyPage:
                        hotel_type= paginator.page(paginator.num_pages) 
                    return render(request, 'superuser/hotel_type.html', {
                    'LANGUAGES': settings.LANGUAGES,
                    'request': request,'hotel_type':hotel_type
                })
                except HotelType.DoesNotExist:
                    logger.error(f"An exception occured at the fetching  HotelType objects.")
            else:
                logger.info("User Id Not found")
                messages.error(request, _("vendor profile not found"))
                return redirect('loginn')  
        except Exception as e:
            logger.exception(f"Unexpected error in HotelTypeView POST: {e}")

    def post(self,request):
        try:
            logger.info("request received") 
            user =  request.user.vendor_profile   
            if user:
                user_data=request.user
                try:
                    logger.info(f"User Detail  found. User: {user_data})")
                    name = request.POST.get("name")
                    arabic_name = request.POST.get("arabic_name")
                    status = request.POST.get("status", "active")
                    icon_file = request.FILES.get("icon")
                    logger.info(f"Received parameters are name:{name},arabic_name:{arabic_name},status:{status},user:{user}")
                    logger.info("Validation completed, creating HotelType object")
                    hotel_type = HotelType.objects.create(name=name,arabic_name=arabic_name,status=status,icon=icon_file,created_by=user_data      
                    ) 
                    if hotel_type:  
                        return JsonResponse({"message": "hotel type created successfully"})
                except Exception as e :
                    logger.exception(f"An exception occured:{e}")
            else:
                logger.info("User Id Not found")
                messages.error(request, _("vendor profile not found"))
                return redirect('loginn')                   
        except Exception as e:
            logger.exception(f"Unexpected error in HotelTypeView POST: {e}")
@method_decorator(super_admin_required, name='dispatch')
class HotelTypeDetail(View):
    def get(self, request, *args, **kwargs):
        try:
            logger.info("GET request processing at the HotelTypeDetail")
            Hoteltype_id = kwargs.get("pk")
            user =  request.user.vendor_profile   
            if user: 
                logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})")  
                try:
                    Hotel_type_value=HotelType.objects.get(id=Hoteltype_id) 
                    data={
                            "name":   Hotel_type_value.name,
                            "arabic_name":   Hotel_type_value.arabic_name,
                            "icon":  Hotel_type_value.icon.url,
                            "status": Hotel_type_value.status,           
                        }
                    logger.info("Hotel type retreived succesfully")
                    return JsonResponse(data)
                except HotelType.DoesNotExist:
                    logger.error(f"Could not fetch hotel type details.")
                    return JsonResponse({'status': 'error', 'message': _('Hotel type not found')}, status=404)
            else:
                logger.info("User Id Not found")
                messages.error(request, _("vendor profile not found"))
                return redirect('loginn')   
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    def post(self, request, *args, **kwargs):
        try:
            logger.info("Processing Post request at the  HotelTypeDetail")
            Hoteltype_id = kwargs.get("pk")
            user =  request.user.vendor_profile   
            if user: 
                logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})")  
                try:
                    hotel_type = get_object_or_404(HotelType, id=Hoteltype_id)
                    if request.POST.get("name"):
                        hotel_type.name = request.POST["name"]
                    if request.POST.get("name_arabic"):
                        hotel_type.arabic_name = request.POST["name_arabic"]
                    if request.POST.get("status"):
                        hotel_type.status = request.POST["status"]
                    if "icon" in request.FILES:
                        hotel_type.icon = request.FILES["icon"]
                    hotel_type.save()
                    return JsonResponse({'status': 'success', 'message': _('Hotel type updated successfully')})
                except HotelType.DoesNotExist:
                    logger.error(f"Could not fetch hotel type details.")
                    return JsonResponse({'status': 'error', 'message': _('Hotel type not found')}, status=404)
            else:
                logger.info("User Id Not found")
                messages.error(request, _("vendor profile not found"))
                return redirect('loginn')   
        except Exception as e:
            logger.error(f"An exception occured at the POST method of hotel type detail view. Exception :{str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    def delete(self, request, *args, **kwargs):
        try:
            logger.info("Processing delete request at the  HotelTypeDetail")
            Hoteltype_id = kwargs.get("pk")
            user =  request.user.vendor_profile   
            if user: 
                logger.info(f"VendorProfile found for superadmin: {request.user.id} ({request.user.username})") 
                try:
                    hotel_type = HotelType.objects.get(id=Hoteltype_id)
                    if hotel_type:
                        hotel_type.status='deleted'
                        hotel_type.save()
                        return JsonResponse({'status': 'success', 'message': _('Hotel type removed  successfully')})
                except HotelType.DoesNotExist:
                    logger.error(f"Could not fetch hotel type details.")
                    return JsonResponse({'status': 'error', 'message': _('Hotel type not found')}, status=404)
            else:
                logger.info("User Id Not found")
                messages.error(request, _("vendor profile not found"))
                return redirect('loginn')   
        except Exception as e:
            logger.error(f"An exception occured at the DELETE method of hotel type detail view. Exception :{str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
@method_decorator(super_admin_required, name='dispatch')
class HotelTypeSearch(View):
    def get(self, request, *args, **kwargs):
        try:
            user =  request.user.vendor_profile  
            if user:
                name_query = request.GET.get("name", "").strip()
                status_query = request.GET.get("status", "all")
                page = request.GET.get("page", 1)  

                hotel_types = HotelType.objects.filter(status__in=["active", "inactive"]).order_by('-id')
                if name_query:
                    if re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]', name_query):
                        hotel_types = hotel_types.filter(arabic_name__icontains=name_query)
                    else:
                        hotel_types = hotel_types.filter(Q(name__icontains=name_query) | Q(arabic_name__icontains=name_query))
                if status_query != "all":
                    hotel_types = hotel_types.filter(status=status_query)
                paginator = Paginator(hotel_types, 15)
                try:
                    hotel_types = paginator.page(page)
                except PageNotAnInteger:
                    hotel_types = paginator.page(1)  
                except EmptyPage:
                    hotel_types= paginator.page(paginator.num_pages) 
                return render(request, "superuser/hotel_type.html", {"hotel_type": hotel_types})
            else:
                logger.info("User Id Not found")
                messages.error(request, _("vendor profile not found"))
                return redirect('loginn')  
        except Exception as e:
            logger.error(f"An exception occured at the search method of hotel type. Exception :{str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
def hotel_type_check_name(request):
    try:
        logger.info(f"Raw Request Data: {request.GET}")

        name = request.GET.get("name", "").strip()
        arabic_name = unquote(request.GET.get("arabic_name", "").strip())
        hotel_type_id = request.GET.get("hotel_type_id")  

        hotel_type = HotelType.objects.exclude(id=hotel_type_id) if hotel_type_id else HotelType.objects.all()

        english_exists = hotel_type.filter(name__iexact=name).exists() if name else False
        arabic_exists = hotel_type.filter(arabic_name__iexact=arabic_name).exists() if arabic_name else False

        return JsonResponse({'english_exists': english_exists, 'arabic_exists': arabic_exists})

    except Exception as e:
        logger.error(f"Error in hotel_type_check_name: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

class EditAdminView(View):
    def get(self, request, user_id):
        """Fetch admin user details for editing (excluding password)."""
        try:
            logger.info("Fetching details for admin user with ID: %s", user_id)
            user = get_object_or_404(User, id=user_id)

            vendor_profile = VendorProfile.objects.filter(user=user, category__in=['admin', 'superadmin']).first()
            if not vendor_profile:
                logger.warning("User %s is not an admin", user_id)
                return JsonResponse({"error": "User is not an admin."}, status=403)

            return JsonResponse({
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "email": user.email or "",
                "status": user.is_active,
            })

        except Exception as e:
            logger.error("Error fetching admin details for user %s: %s", user_id, str(e), exc_info=True)
            return JsonResponse({"error": _("An error occurred while fetching admin details.")}, status=500)

    def post(self, request, user_id):
        """Update admin user details (password update is optional)."""
        try:
            logger.info("Updating admin user with ID: %s", user_id)
            user = get_object_or_404(User, id=user_id)
            vendor_profile = get_object_or_404(VendorProfile, user=user)

            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            email = request.POST.get("email", "").strip().lower()
            new_password = request.POST.get("password", "").strip()
            is_active = request.POST.get("is_active", "false") == "true"

            logger.info("Received update data - First Name: %s, Last Name: %s, Email: %s,Status: %s",
                        first_name, last_name, email, is_active)

            # Validate email uniqueness
            if email and User.objects.filter(email=email).exclude(id=user.id).exists():
                logger.warning("Email %s is already in use", email)
                return JsonResponse({"error": _("Email is already in use.")}, status=400)

            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.email = email or user.email
            user.is_active = is_active
            user.save()

            vendor_profile.save()

            # Update password only if provided
            if new_password:
                user.set_password(new_password)
                user.save()
                logger.info("Password updated for user ID: %s", user_id)

            logger.info("Admin details updated successfully for user ID: %s", user_id)
            return JsonResponse({"success":  _( "Admin details updated successfully." )}, status=200)

        except Exception as e:
            logger.error("Error updating admin user %s: %s", user_id, str(e), exc_info=True)
            return JsonResponse({"error": _("An error occurred while updating admin details.")}, status=500)
   
@login_required
def delete_admin(request):
    if request.method == "POST":
        admin_id = request.POST.get("admin_id", "").strip()

        if not admin_id:
            logger.warning("Delete admin request received with missing admin_id")
            return JsonResponse({"success": False, "message": _("Admin ID is required.")}, status=400)

        try:
            logger.info("Attempting to delete admin with ID: %s", admin_id)
            user = get_object_or_404(User, id=admin_id)

            if user.is_superuser:
                logger.warning("Attempt to delete a Super Admin (ID: %s) was blocked", admin_id)
                return JsonResponse({"success": False, "message": _("Cannot delete a Super Admin!")}, status=403)

            user.delete()
            logger.info("Admin with ID %s deleted successfully", admin_id)
            return JsonResponse({"success": True, "message": _("Admin deleted successfully.")})

        except Exception as e:
            logger.error("Error deleting admin with ID %s: %s", admin_id, str(e), exc_info=True)
            return JsonResponse({"success": False, "message": _("An error occurred while deleting admin.")}, status=500)

    logger.warning("Invalid request method used for delete_admin: %s", request.method)
    return JsonResponse({"success": False, "message": _("Invalid request.")}, status=400)



import pandas as pd
import io
from xlsxwriter.utility import xl_rowcol_to_cell
class AdminTransactionExcelDownloadView(View):
    def get(self, request):
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        payment_method = request.GET.get('payment_method')
        transaction_status = request.GET.get('transaction_status')
        booking_status = request.GET.get('booking_status')
        name_search = request.GET.get('Name_search')
        transaction_id = request.GET.get('transaction_id')
        if request.session:
            try:
                lang=request.session["django_language"]
            except Exception as e:
                lang='en'
        else:
            lang='en'
        # logger.info(f" requested language session is {lang}")
            
        try:
            hotel_booking = Booking.objects.select_related('transaction').prefetch_related('transaction__vendor_transaction','transaction__admin_transaction').order_by('-modified_date')
            chalet_booking = ChaletBooking.objects.select_related('transaction').prefetch_related('transaction__vendor_transaction','transaction__admin_transaction').order_by('-modified_date')
            transactions = sorted(
                chain(hotel_booking, chalet_booking),
                key=lambda x: x.modified_date,
                reverse=True
            )
            logedin_user = "admin"
            transactions = transaction_list_filter(transactions, from_date,  to_date, payment_method, transaction_status, booking_status, name_search, transaction_id, logedin_user)
            user = "admin"
            data_frame = report_data_frame(transactions,user,lang)
            if data_frame:
                # logger.info(f"data found :{data_frame}")
                df = pd.DataFrame(data_frame)
                # Set index to start from 1
                df.index = df.index + 1  
                df.reset_index(inplace=True) 
                if lang=='en':
                    df.rename(columns={'index': 'S.No'}, inplace=True)
                else:
                    df.rename(columns={'index': 'س.لا'}, inplace=True)
                print(len(df.columns))
                pd.set_option('display.max_colwidth',300) 
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Transaction Details',startrow=2, header=False, index=False)
                    workbook = writer.book
                    worksheet = writer.sheets['Transaction Details']
                    # Add a header format
                    toper_formate, header_format, cell_format = xlsxwriter_styles(workbook)
                    # Write the header row
                    column_letter = xl_rowcol_to_cell(0, len(df.columns)-1)
                    merge_range = f'A1:AC2'
                    filters = []
                    for key, value in request.GET.items():
                        if value.strip():
                            formatted_key = key.replace('_', ' ').title()
                            formatted_value = value.strip().title()
                            filters.append(f"{formatted_key}: {formatted_value}")
                    # Generate the heading dynamically
                    if filters:
                        filter_text = " | ".join(filters)  # Join multiple filters with " | "
                        if lang =='en':
                            worksheet.merge_range(merge_range, f'Transaction Details Report based on {filter_text}', toper_formate)
                        else:
                            worksheet.merge_range(merge_range, f'تقرير تفاصيل المعاملات بناءً على {filter_text}', toper_formate)
                    else:
                        if lang =='en':
                            worksheet.merge_range(merge_range, 'Transaction Details Report', toper_formate)
                        else:
                            worksheet.merge_range(merge_range, 'تقرير تفاصيل المعاملات', toper_formate)

                    for col_num, column_name in enumerate(df.columns):
                        worksheet.write(2, col_num, column_name, header_format)
                    # Write the data with border format
                    for row_num, row_data in enumerate(df.values, start=3):  # Start from row 3
                        for col_num, cell_value in enumerate(row_data):
                            worksheet.write(row_num, col_num, cell_value, cell_format)
                    for i, col in enumerate(df.columns):
                        max_length = max(df[col].astype(str).map(len).max(), len(col)) + 2 
                        worksheet.set_column(i, i, max_length)
            else:
                # logger.info(f"Inside else no data found")
                if lang =='en':
                    df = pd.DataFrame([{'message':'No Data Found'}])
                else:
                    df = pd.DataFrame([{'message':'لم يتم العثور على بيانات'}])

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Transaction Details',startrow=2, header=False, index=False)
                    workbook = writer.book
                    worksheet = writer.sheets['Transaction Details']
                    # Add a header format
                    toper_formate, header_format, cell_format = xlsxwriter_styles(workbook)
                    # Write the header row
                    column_letter = xl_rowcol_to_cell(0, len(df.columns)-1)
                    merge_range = f'A1:AC2'
                    filters = []
                    for key, value in request.GET.items():
                        if value.strip():
                            formatted_key = key.replace('_', ' ').title()
                            formatted_value = value.strip().title()
                            filters.append(f"{formatted_key}: {formatted_value}")
                    # Generate the heading dynamically
                    if filters:
                        filter_text = " | ".join(filters)  # Join multiple filters with " | "
                        if lang =='en':
                            worksheet.merge_range(merge_range, f'Transaction Details Report based on {filter_text}', toper_formate)
                        else:
                            worksheet.merge_range(merge_range, f'تقرير تفاصيل المعاملات بناءً على {filter_text}', toper_formate)
                    else:
                        if lang =='en':
                            worksheet.merge_range(merge_range, 'Transaction Details Report', toper_formate)
                        else:
                            worksheet.merge_range(merge_range, 'تقرير تفاصيل المعاملات', toper_formate)
                    row_num = 3
                    for value in df.values:
                        worksheet.merge_range('A3:S4', value[0], toper_formate)

            output.seek(0)
            response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename=transactions.xlsx'

            return response

        except Exception as e:
            # logger.error(f"Exception raised in AdminTransactionExcelDownload View. Exception: {e}")
            print(e)
class UsermanagementExcelDownload(View):
    def get(self,request):
        try:
            logger.info("request received for the user management excel download")
            name = request.GET.get('name', '').strip()
            status = request.GET.get('status', '').strip()
            os = request.GET.get('os', '').strip()

            if request.session:
                try:
                    lang=request.session["django_language"]
                except Exception as e:
                    lang='en'
            else:
                lang='en'

            logger.info("Fetching user list - Name: %s, Status: %s, OS: %s", name, status, os)

            # Base user query (excluding vendors and superusers)
            user_query = Q(is_vendor=False, is_superuser=False)

            # VendorProfile user query (only admin or superadmin vendors)
            vendor_query = Q(vendor_profile__category__in=['admin', 'superadmin'])

            # Apply name filter
            name_query = Q()
            if name:
                name_parts = name.split()
                for part in name_parts:
                    name_query |= Q(first_name__icontains=part) | Q(last_name__icontains=part) | Q(username__icontains=part)

            # Apply status filter
            status_query = Q()
            if status == 'active':
                status_query = Q(is_active=True)
            elif status == 'inactive':
                status_query = Q(is_active=False)

            # Apply OS filter
            os_query = Q()
            if os:
                os_query = Q(user_details__operating_system__iexact=os)

            # Combine queries for both normal users and vendor-admin users
            users = User.objects.filter((user_query | vendor_query) & name_query & status_query & os_query).distinct().order_by("id")

            logger.info("Users found: %d", users.count())

            data_frame = user_data_frame(users,lang)
            logger.info(f"data frame created {data_frame}")
            if data_frame:
                df = pd.DataFrame(data_frame)
                df.index = df.index + 1  
                df.reset_index(inplace=True) 
                if lang=='en':
                    df.rename(columns={'index': 'S.No'}, inplace=True)
                else:
                    df.rename(columns={'index': 'س.لا'}, inplace=True)
                print(len(df.columns))
                pd.set_option('display.max_colwidth',300) 
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='User Management',startrow=2, header=False, index=False)
                    workbook = writer.book
                    worksheet = writer.sheets['User Management']
                    logger.info(f"worksheet created {worksheet}")
                    # Add a header format
                    toper_formate, header_format, cell_format = xlsxwriter_styles(workbook)
                    # Write the header row
                    column_letter = xl_rowcol_to_cell(0, len(df.columns)-1)
                    merge_range = f'A1:J2'
                    filters = []
                    for key, value in request.GET.items():
                        if value.strip():
                            formatted_key = key.replace('_', ' ').title()
                            formatted_value = value.strip().title()
                            filters.append(f"{formatted_key}: {formatted_value}")
                    # Generate the heading dynamically
                    if filters:
                        filter_text = " | ".join(filters)  # Join multiple filters with " | "
                        if lang =='en':
                            worksheet.merge_range(merge_range, f'User Details Report based on {filter_text}', toper_formate)
                        else:
                            worksheet.merge_range(merge_range, f'تقرير تفاصيل المعاملات بناءً على {filter_text}', toper_formate)
                    else:
                        if lang =='en':
                            worksheet.merge_range(merge_range, 'User Details Report', toper_formate)
                        else:
                            worksheet.merge_range(merge_range, 'تقرير تفاصيل المعاملات', toper_formate)

                    for col_num, column_name in enumerate(df.columns):
                        worksheet.write(2, col_num, column_name, header_format)
                    # Write the data with border format
                    for row_num, row_data in enumerate(df.values, start=3):  # Start from row 3
                        for col_num, cell_value in enumerate(row_data):
                            worksheet.write(row_num, col_num, cell_value, cell_format)
                    for i, col in enumerate(df.columns):
                        max_length = max(df[col].astype(str).map(len).max(), len(col)) + 2 
                        worksheet.set_column(i, i, max_length)
                        

            else:
                # logger.info(f"Inside else no data found")
                if lang =='en':
                    df = pd.DataFrame([{'message':'No Data Found'}])
                else:
                    df = pd.DataFrame([{'message':'لم يتم العثور على بيانات'}])

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='User Management',startrow=2, header=False, index=False)
                    workbook = writer.book
                    worksheet = writer.sheets['User Management']
                    # Add a header format
                    toper_formate, header_format, cell_format = xlsxwriter_styles(workbook)
                    # Write the header row
                    column_letter = xl_rowcol_to_cell(0, len(df.columns)-1)
                    merge_range = f'A1:J2'
                    filters = []
                    for key, value in request.GET.items():
                        if value.strip():
                            formatted_key = key.replace('_', ' ').title()
                            formatted_value = value.strip().title()
                            filters.append(f"{formatted_key}: {formatted_value}")
                    # Generate the heading dynamically
                    if filters:
                        filter_text = " | ".join(filters)  # Join multiple filters with " | "
                        if lang =='en':
                            worksheet.merge_range(merge_range, f'User Details Report based on {filter_text}', toper_formate)
                        else:
                            worksheet.merge_range(merge_range, f'تقرير تفاصيل المستخدم بناءً على {filter_text}', toper_formate)
                    else:
                        if lang =='en':
                            worksheet.merge_range(merge_range, 'User Details Report', toper_formate)
                        else:
                            worksheet.merge_range(merge_range, 'تقرير تفاصيل المستخدم', toper_formate)
                    row_num = 3
                    for value in df.values:
                        worksheet.merge_range('A3:S4', value[0], toper_formate)

            output.seek(0)
            response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename=user_management.xlsx'
            logger.info(f"response found,{response}")

            return response

        except Exception as e:
            logger.error(f"Exception raised in UserMangementExcelDownload View. Exception: {e}")

