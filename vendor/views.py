import json
import re
import uuid
import requests
import logging
import os 
from decimal import Decimal,InvalidOperation
from datetime import datetime,date,time
from django.utils.timezone import make_aware
from django.http import Http404
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.exceptions import MultipleObjectsReturned
from django.core.mail import EmailMessage, send_mail
from django.core.validators import EmailValidator, validate_email
from django.db.models import Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import activate
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import IntegrityError, transaction
from django.db.models import Count,Sum
from django.db.models.functions import TruncMonth,TruncWeek,TruncDay
from django.utils.timezone import now
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import timedelta
from calendar import month_abbr
from common.customdecorator import vendor_required
from common.utils import create_notification
from commonfunction import booking_filters, report_data_frame, transaction_list_filter, xlsxwriter_styles,get_lat_long
from user.models import  User, Userdetails, VendorProfile
from helpers.mixins import CustomLoginRequiredMixin
from vendor.models import Amenity, Categories, City, CommissionSlab, Country, Hotel, HotelDocument, HotelImage, HotelTax, MealPrice, MealTax, PolicyCategory, PolicyName, RecentReview, RoomManagement, Roomtype, RoomImage, State, HotelTransaction, WeekendPrice,Bookedrooms, Booking,HotelAcceptedPayment,HotelType,RefundPolicyCategory,RefundPolicy,RoomRefundPolicy
from chalets.models import Chalet, ChaletImage, ChaletTax, chaletDocument,Promotion,Notification
from common.models import AdminTransaction, ChaletType, PaymentTypeCategory,PaymentType,Transaction,RefundTransaction,OwnerName
from django.views.decorators.cache import cache_control
from common.models import Tax
from langdetect import detect
from vendor.function import format_validity, get_roomtype_availability,get_city_name,save_image,populate_missing_coordinates
from common.function import create_hotel_booking_transaction, create_vendor_transaction, generate_transaction_id,create_transaction
from concurrent.futures import ThreadPoolExecutor


logger = logging.getLogger('lessons')


class SetLanguageView(View):
    def post(self, request, *args, **kwargs):
        language_code = request.POST.get("language_code")
        if language_code in dict(settings.LANGUAGES).keys():
            request.session["django_language"] = language_code
            activate(language_code)
            return JsonResponse({"success": True})
        else:
            return JsonResponse({"success": False, "error": _("Invalid language code")})


class LoginView(View):
    def get(self, request):
        message = request.GET.get("message", "")
        category_list = Categories.CATEGORIES
        # check_names=set_city()
        check_lat_long=populate_missing_coordinates()
        # user_details = Userdetails.objects.filter(operating_system__isnull=True, user__is_vendor=False)
        # for users in user_details:
        #     if users.operating_system is None:
        #         users.operating_system = "IOS"
        #         users.save()
        # print("user details are: ",user_details)
        # Check if "registration-success" exists as a query parameter in the URL
        registration_success = "registration-success" in request.GET

        return render(
            request,
            "accounts/vendor_login.html",
            context={
                "category_list": category_list,
                "LANGUAGES": settings.LANGUAGES,
                "registration_success": registration_success,
            },
        )


    def post(self, request):
        email = request.POST.get("email")
        password = request.POST.get("password")
        category_list = Categories.CATEGORIES

        logger.info(f"Received email: {email}")


        email_validator = EmailValidator()
        try:
            email_validator(email)
        except ValidationError as e:
            logger.info(f"Invalid email format for: {email}, Error: {str(e)}")
            messages.error(request, _("Invalid email format!"))
            return render(request, "accounts/vendor_login.html", {
                "emailformat": True,
                "category_list": category_list,
                "LANGUAGES": settings.LANGUAGES
            })

        try:
            logger.info(f"Attempting to authenticate email: {email}")
            users = User.objects.filter(email=email,is_deleted=False)
            
            if not users:
                logger.info(f"No user found with email: {email}")
                messages.error(request, _("No user found with this email."))
                return render(request, "accounts/vendor_login.html", {
                    "category_list": category_list,
                    "notification_messages": messages.get_messages(request),
                    "LANGUAGES": settings.LANGUAGES
                })
            
            for user in users:
                logger.info(f"User found: {user.username}, Active: {user.is_active}, Superuser: {user.is_superuser}, Staff: {user.is_staff}")
                
                if user.is_superuser:
                    logger.info(f"Superuser detected: {user.username}")
                    authenticated_user = authenticate(request, username=user.username, password=password)
                    logger.info(f"Authenticated user: {authenticated_user}, Username: {user.username}")
                    
                    if authenticated_user is not None:
                        login(request, authenticated_user)
                        logger.info(f"Super Admin login successful for: {user.username}")
                        messages.success(request, _("Welcome Super Admin!"))
                        return redirect("dashboard_overview")
                    else:
                        logger.info(f"Super Admin login successful for: {user.username}")
                        messages.error(request, _("Invalid credentials for Super Admin!"))
                        return render(request, "accounts/vendor_login.html", {
                            "category_list": category_list,
                            "notification_messages": messages.get_messages(request),
                            "LANGUAGES": settings.LANGUAGES
                        })
                elif hasattr(user, 'vendor_profile') and user.vendor_profile.category in ["admin", "superadmin"]:
                    logger.info(f"Vendor Admin detected: {user.username} with role {user.vendor_profile.category}")

                    try:
                        existing_user = User.objects.get(email=user.email,is_deleted=False)
                    except User.DoesNotExist:
                        existing_user = None

                    if existing_user:
                        if not existing_user.is_active:
                            logger.warning(f"Inactive admin login attempt: {user.username}")
                            messages.error(request, _("Your account has been deactivated. Please contact the administrator."))
                            return render(request, "accounts/vendor_login.html", {
                                "category_list": category_list,
                                "notification_messages": messages.get_messages(request),
                                "LANGUAGES": settings.LANGUAGES
                            })

                        # Authenticate only if user exists
                        authenticated_user = authenticate(request, username=existing_user.email, password=password)

                        if authenticated_user is not None:
                            login(request, authenticated_user)
                            logger.info(f"Vendor Admin login successful for: {user.username}")
                            messages.success(request, _("Welcome Admin!"))
                            return redirect("dashboard_overview")
                        else:
                            logger.error(f"Authentication failed for vendor admin: {user.username}")
                            messages.error(request, _("Invalid credentials for Admin!"))

                    else:
                        logger.error(f"No user found with email: {user.email}")
                        messages.error(request, _("Invalid credentials for Admin!"))

                    return render(request, "accounts/vendor_login.html", {
                        "category_list": category_list,
                        "notification_messages": messages.get_messages(request),
                        "LANGUAGES": settings.LANGUAGES
                    })


        except Exception as e:
            logger.info(f"An error occurred during superuser authentication: {str(e)}")
            pass


        try:
            logger.info(f"Checking for vendor profile for email: {email}")
            vendor_profile = VendorProfile.objects.get(user__email=email,user__is_vendor=True)
        except VendorProfile.DoesNotExist:
            logger.info(f"No vendor profile found for email: {email}")
            messages.error(request, _("Email or Password is incorrect!"))
            return render(request, "accounts/vendor_login.html", {
                "category_list": category_list,
                "LANGUAGES": settings.LANGUAGES,
                "notification_messages": messages.get_messages(request)
            })
        except MultipleObjectsReturned:
            logger.info(f"Multiple vendor profiles found for email: {email}")
            messages.error(request, _("Multiple vendor profiles found with this email. Please contact support."))
            return render(request, "accounts/vendor_login.html", {
                "category_list": category_list,
                "notification_messages": messages.get_messages(request),
                "LANGUAGES": settings.LANGUAGES
            })


        authenticated_user = authenticate(request, username=vendor_profile.user.username, password=password)
        logger.info(f"Authenticated vendor: {authenticated_user}")

        if authenticated_user is not None:
            login(request, authenticated_user)
            logger.info(f"Vendor login successful for: {vendor_profile.user.username}")

            hotels = Hotel.objects.filter(vendor=vendor_profile.id)
            chalets = Chalet.objects.filter(vendor=vendor_profile.id)

            # Check if any hotel or chalet is approved
            has_approved_hotel = hotels.filter(approval_status='approved').exists()
            has_approved_chalet = chalets.filter(approval_status='approved').exists()

            if has_approved_hotel or has_approved_chalet:
                # Determine post-approval for redirection
                post_approved_hotel = hotels.filter(approval_status='approved', post_approval=True).exists()
                post_approved_chalet = chalets.filter(approval_status='approved', post_approval=True).exists()

                if post_approved_hotel and post_approved_chalet:
                    messages.success(request, _("Login successful!"))
                    return redirect("dashboard_overviews")  # Both have post-approval
                elif post_approved_hotel:
                    messages.success(request, _("Login successful!"))
                    return redirect("dashboard")  # Only hotel post-approved
                elif post_approved_chalet:
                    messages.success(request, _("Login successful!"))
                    return redirect("dashboard_overviews")  # Only chalet post-approved
                else:
                    # Redirect to the appropriate amenities page if post-approval is missing
                    if has_approved_hotel:
                        messages.success(request, _("Login successful!"))
                        return redirect("add_ammenities")  
                    if has_approved_chalet:
                        messages.success(request, _("Login successful!"))
                        return redirect("chalet_ammenities")  # Chalet needs post-approval

            # No approved properties found
            # messages.error(request, "Neither hotel nor chalet is approved!")
            if hotels.exists() and not has_approved_hotel:
                messages.error(request, _("Your hotel is not approved!"))
            elif chalets.exists() and not has_approved_chalet:
                messages.error(request, _("Your chalet is not approved!"))
            else:
                messages.error(request, _("Neither hotel nor chalet is approved!"))
    
            return render(request, "accounts/vendor_login.html", {
                "category_list": category_list,
                "notification_messages": messages.get_messages(request),
                "LANGUAGES": settings.LANGUAGES
            })
        else:
            messages.error(request, _("Invalid E-mail or Password"))
            return render(request, "accounts/vendor_login.html", {
                "category_list": category_list,
                "notification_messages": messages.get_messages(request),
                "LANGUAGES": settings.LANGUAGES
            })  
    


class PendingTemplateView(View):

    def get(self, request):
        return render(request,'accounts/pending.html')

class PendingApprovalTemplateView(View):

    def get(self, request):
        user = VendorProfile.objects.get(user=request.user)
        logger.info(f"VendorProfile retrieved for user: {request.user.id}")
        hotel_id = request.GET.get('hotel_id')
        logger.info(f" hotel id is ---{hotel_id}")
        if hotel_id:
            selected_hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
        else:
            selected_hotel= Hotel.objects.filter(vendor=user.id).first() 
        return render(request,'accounts/pending_approval.html',context={'selected_hotel':selected_hotel})

class AdvertismentPageView(View):

    def get(self,request):
        return render(request,'accounts/ad_page.html')

class HotelAdvertismentPageView(View):

    def get(self,request):
        return render(request,'accounts/ad_page_hotel.html')

class ChaletExistView(View):

    def get(self, request):
        try:
            user = VendorProfile.objects.get(user=request.user)
            chalets = Chalet.objects.filter(vendor=user.id)
            if chalets.filter(approval_status='approved').exists():
                if chalets.filter(approval_status='approved', post_approval=True).exists():
                    return JsonResponse({'approved': True})
                else:
                    return JsonResponse({'Post_approval': True})

            elif chalets.filter(approval_status='pending').exists():
                return JsonResponse({'pending': True})
            elif chalets.filter(approval_status='rejected').exists():
                return JsonResponse({'rejected': True})
            else:
                return JsonResponse({'advertisement': True})

        except VendorProfile.DoesNotExist:
            logger.info("vendor profile doesn't found")
            return render(request, 'accounts/404.html')


class HotelExistView(View):

    def get(self,request):
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel = Hotel.objects.filter(vendor=user.id).first()
            if hotel:               
                if hotel.approval_status == 'pending':
                    return JsonResponse({'pending': True})
                elif hotel.approval_status == 'approved':
                    if hotel.post_approval == True:
                        return JsonResponse({'approved': True})
                    else:
                        return JsonResponse({'Post_approval': True})
                else:
                    return JsonResponse({'rejected': True})
            else:
                return JsonResponse({'advertisement': True})

        except VendorProfile.DoesNotExist:
            logger.info("vendor profile doesn't found")
            return render(request, 'accounts/404.html')


def check_email_exists(request):
    email = request.GET.get("email", None)
    response = {"exists": VendorProfile.objects.filter(user__email=email).exists()}
    return JsonResponse(response)


class Register(View):
    def get(self, request, category):
        user_language = request.LANGUAGE_CODE
        activate(user_language)
        hotel_types=HotelType.objects.filter(status='active')
        return render(
            request,
            "accounts/registration_form.html",
            context={
                "category": category,
                "room_type": Roomtype.objects.all(),
                "hotel_types":  hotel_types,
                "hotel_rating": Hotel.HOTEL_RATING,
                "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
            },
        )

    def post(self, request, category):
        try:
            logger.info("Received POST request for hotel registration.")
            form_data = {key: request.POST.get(key) for key in [
                "hotelOwnerName", "officenumber", "hotelName", "hotelAddress",
                "country", "city", "stateProvince", "roomnumber", "hotelrating", 
                "crnumber", "vatnumber", "expiry", "gsmnumber", "hotelOwnerEmail", 
                "password1", "password2", "logo_image", "locality", "Accountholder", 
                "About", "polices", "hotelNameArabic", "hotelOwnerNameArabic", 
                "about_arabic", "polices_arabic", "Accountno", "BankName","hotel_type"
            ]}
            hotel_images = request.FILES.getlist("hotel_images[]")
            supporting_documents = request.FILES.getlist("supportingDocuments[]")
            print(f"\n\n\n\n\n {form_data['hotelrating']} \n\n\n\n")
            print("Before validation")
            errors = self.validate_form(form_data)

            if errors:
                return render(request, "accounts/registration_form.html", {"category": category, "errors": errors})

            if VendorProfile.objects.filter(user__email=form_data["hotelOwnerEmail"], user__is_vendor=True).exists():
                logger.info(f"Email {form_data['hotelOwnerEmail']} already registered as a vendor.")
                return render(request, "accounts/registration_form.html", {"category": category, "resend_modal": True})

            if not hotel_images:
                errors["hotel_images"] = _("Hotel image is required.")
            if not supporting_documents:
                errors["supporting_documents"] = _("Supporting document is required.")
            
            print(f"\n\n\n\n\n {form_data['hotelrating']} \n\n\n\n")
            hotelListType = ["Hotel", "Hotels", "hotel", "hotels" ,"HOTEL", "HOTELS"]
            if form_data['hotel_type'] in hotelListType:
                if form_data['hotelrating'] == "" or form_data['hotelrating'] is None:
                    errors['hotelrating'] = _("Hotel rating is required when hotel type is '%(hotel_type)s'.") % { 'hotel_type': form_data['hotel_type'] }
            
            
            if errors:
                return render(request, "accounts/registration_form.html", {"category": category, "errors": errors})

            
            with transaction.atomic():
                
                try:
                    user = User.objects.create_user(
                        username=str(uuid.uuid4())[:15], 
                        first_name=form_data["hotelOwnerName"],
                        email=form_data["hotelOwnerEmail"],
                        password=form_data["password1"],
                        is_vendor=True,
                        is_deleted=False
                    )
                except IntegrityError as e:
                    logger.error(f"Error creating user: {e}")
                    raise Exception(f"Error creating user: {e}")
                
                try:
                    vendor_profile = VendorProfile.objects.create(
                        user=user,
                        name=form_data["hotelOwnerName"],
                        contact_number=form_data["officenumber"],
                        gsm_number=form_data["gsmnumber"],
                    )
                except IntegrityError as e:
                    logger.error(f"Error creating vendor profile: {e}")
                    raise Exception(f"Error creating vendor profile: {e}")
                try:
                    country, _ = Country.objects.get_or_create(name=form_data["country"])
                    state, _ = State.objects.get_or_create(country=country, name=form_data["stateProvince"])
                    def is_arabic(text):
                        return any('\u0600' <= c <= '\u06FF' for c in text)
                    city_name = form_data["city"]
                    if is_arabic(city_name):
                        arabic_name=city_name
                        english_name=get_city_name(city_name,state.name,country.name,'en')
                        logger.info("city name is arabic")
                    else:
                        english_name=city_name
                        arabic_name=get_city_name(city_name,state.name,country.name,'ar')
                    print("english and arabic name of the city is: ", english_name, arabic_name)
                    city, _ = City.objects.get_or_create(state=state, name=english_name, arabic_name=arabic_name)
                except IntegrityError as e:
                    logger.error(f"Error creating location hierarchy: {e}")
                    raise Exception(f"Error creating location hierarchy: {e}")
                hotel_type=None
                try:
                    hotel_type_value=request.POST.get('hotel_type')
                    if hotel_type_value:
                        hotel_type=HotelType.objects.get(id=hotel_type_value)
                    else:
                        logger.error("Hotel type not found")
                except Exception as e:
                    logger.error(f"Exception ocuured at hotel type fetch portion : {str(e)} ")
                #validate owner name if it exist or not
                try:
                    hotel_owner = OwnerName.objects.filter(
                        owner_name=form_data["hotelOwnerName"],
                        owner_name_arabic=form_data["hotelOwnerNameArabic"]
                    ).first()

                    if not hotel_owner:
                        hotel_owner = OwnerName.objects.create(
                            owner_name=form_data["hotelOwnerName"],
                            owner_name_arabic=form_data["hotelOwnerNameArabic"]
                        )
                except Exception as e:
                    logger.error(f"Exception occurred at hotel owner name fetch portion: {str(e)}")
                    hotel_owner = None 

               # Get hotel latitude and longitude
                try:
                    lat, long = get_lat_long(
                    form_data.get("hotelAddress", ""),
                    form_data.get("city", ""),
                    form_data.get("stateProvince", ""),
                    form_data.get("country", "")
                    )

                    if lat is not None and long is not None:
                        logger.info(f"Fetched coordinates: latitude={lat}, longitude={long}")
                    else:
                        logger.warning("Could not fetch valid coordinates. Received None.")

                except Exception as e:
                    logger.error(f"Error fetching coordinates: {str(e)}")
                    lat = None
                    long = None


                try:
                    hotel = Hotel.objects.create(
                        vendor=vendor_profile,
                        hotel_rating=form_data["hotelrating"],
                        name=form_data["hotelName"].replace(' ', ''),  # Handle spaces in hotel name
                        address=form_data["hotelAddress"],
                        country=country, city=city, state=state,
                        number_of_rooms=form_data["roomnumber"],
                        rooms_available=form_data["roomnumber"],
                        cr_number=form_data["crnumber"],
                        vat_number=form_data["vatnumber"],
                        date_of_expiry=form_data["expiry"],
                        office_number=form_data["officenumber"],
                        logo=request.FILES.get("logo_image"),
                        about_property=form_data["About"],
                        hotel_policies=form_data["polices"],
                        locality=form_data["locality"],
                        account_no=form_data["Accountno"],
                        owner_name=hotel_owner,
                        bank=form_data["BankName"],
                        account_holder_name=form_data["Accountholder"],
                        name_arabic=form_data["hotelNameArabic"],
                        owner_name_arabic=form_data["hotelOwnerNameArabic"],
                        about_property_arabic=form_data["about_arabic"],
                        hotel_policies_arabic=form_data["polices_arabic"],
                        hotel_type=hotel_type,
                        latitude= lat,
                        longitude=long 
                    )
                except IntegrityError as e:
                    logger.error(f"Error creating hotel: {e}")
                    raise Exception(f"Error creating hotel: {e}")
                try:
                    category_obj, _ = Categories.objects.get_or_create(category=category)
                    hotel.category.add(category_obj)
                except IntegrityError as e:
                    logger.error(f"Error adding category to hotel: {e}")
                    raise Exception(f"Error adding category to hotel: {e}")

                try:
                    HotelImage.objects.bulk_create([HotelImage(hotel=hotel, image=image) for image in hotel_images])
                    HotelDocument.objects.bulk_create([HotelDocument(hotel=hotel, document=document) for document in supporting_documents])
                except IntegrityError as e:
                    logger.error(f"Error creating hotel images/documents: {e}")
                    raise Exception(f"Error creating hotel images/documents: {e}")
                try:
                    self.send_registration_email(hotel)
                except Exception as e:
                    logger.error(f"Error sending registration email: {e}")
                    raise Exception(f"Error sending registration email: {e}")
                print("\n\n\n\n\n\n   Hotel Has been created \n\n\n\n\n\n\n")
                return redirect('/vendor/login/?registration-success')

        except IntegrityError as e:
            logger.error(f"Database IntegrityError: {e}")
            return render(request, 'accounts/404.html', {"error": _("There was an error processing your request.")})
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return render(request, 'accounts/404.html', {"error": _("An unexpected error occurred, please try again.")})

    def validate_form(self, form_data):
        errors = {}
        if not form_data["hotelOwnerEmail"]:
            errors["hotelOwnerEmail"] = _("This field is required.")
        elif not self.is_valid_email(form_data["hotelOwnerEmail"]):
            errors["hotelOwnerEmail"] = _("Enter a valid email address.")

        if not self.is_valid_phone(form_data["officenumber"]):
            errors["officenumber"] = _("Enter a valid phone number.")

        required_fields = ["expiry"]
        for field in required_fields:
            if not form_data.get(field):
                errors[field] = _("This field is required.")
        
        password1 = form_data.get("password1")
        password2 = form_data.get("password2")
        
        if password1 != password2:
            errors["passwords"] = _("Passwords do not match.")
        elif len(password1) < 8:
            errors["passwords"] = _("Password must be at least 8 characters long.")
        print("Error:", errors)
        return errors

    def is_valid_email(self, email):
        try:
            validate_email(email)
            return True
        except ValidationError:
            return False

    def is_valid_phone(self, phone):
        return re.match(r"^\+?[1-9]\d{1,14}$", phone)

    def send_registration_email(self, hotel):
        try:
            superusers = User.objects.filter(is_superuser=True,is_deleted=False)
            superuser_emails = [superuser.email for superuser in superusers]
            context = {"hotel_name": hotel.name, "hotel_address": hotel.address}
            message = render_to_string("accounts/hotel_registration_notification.html", context)
            send_mail(
                "New Hotel Registration Notification",
                "",
                settings.EMAIL_HOST_USER,
                superuser_emails,
                html_message=message,
            )
            logger.info("Sent registration notification email to superusers.")
        except Exception as e:
            logger.error(f"Error in sending registration email: {e}")

class RgisterChaletview(View):

    def get(self, request, category):
        get_chalet_type = ChaletType.objects.filter(status = "active")
        user=request.user
        user_details = get_object_or_404(VendorProfile, user=request.user)
        hotel=Hotel.objects.filter(vendor=user_details.id).first()
        return render(
            request,
            template_name="accounts/chalet_register.html",
            context={"chalet_type":get_chalet_type,"category": category,"GOOGLE_MAPS_API_KEY":settings.GOOGLE_MAPS_API_KEY,
                'pre_filled_fields': {
                'hotelOwnerName': request.user.first_name,
                'hotelOwnerEmail': request.user.email,
                'owner_name_arabic': hotel.owner_name_arabic if hotel else '',
                
                # Add other fields that should be pre-filled
            }}
        )

    def post(self, request, category):
        def validate_required_fields(fields):
            errors = {}
            for field, value in fields.items():
                if not value:
                    errors[field] = _("This field is required.")
            return errors

        def validate_phone_field(phone):
            errors = {}
            phone_pattern = re.compile(r"^\+?[1-9]\d{1,14}$")
            if not phone:
                errors["officenumber"] = _("This field is required.")
            elif not phone_pattern.match(phone):
                errors["officenumber"] = _("Enter a valid phone number.")
            return errors

        def create_or_get_location(country_name, state_name, city_name):
            country, _ = Country.objects.get_or_create(name=country_name)
            state, _ = State.objects.get_or_create(country=country, name=state_name)
            def is_arabic(text):
                return any('\u0600' <= c <= '\u06FF' for c in text)
            if is_arabic(city_name):
                arabic_name=city_name
                english_name=get_city_name(city_name,state.name,country.name,'en')
                logger.info("city name is arabic")
            else:
                english_name=city_name
                arabic_name=get_city_name(city_name,state.name,country.name,'ar')
                logger.info("city name is english")
            print("english and arabic name of the city is: ", english_name, arabic_name)
            city, _ = City.objects.get_or_create(state=state, name=english_name, arabic_name=arabic_name)
            return country, state, city

        def send_registration_email(chalet):
            try:
                superusers = User.objects.filter(is_superuser=True,is_deleted=False)
                superuser_emails = [superuser.email for superuser in superusers]
                context = {"chalet_name": chalet.name, "chalet_address": chalet.address}
                subject = "New Chalet Registration Notification"
                message = render_to_string("accounts/chalet_registration_notification.html", context)
                send_mail(subject, "", settings.EMAIL_HOST_USER, superuser_emails, html_message=message)
            except Exception as e:
                print(e, "Error in sending registration email")

        # Extract POST data
        post_data = {field: request.POST.get(field, '') for field in [
            'chaletName', 'chaletNameArabic', 'chaletOwnerName', 'chaletOwnerArabicName',
            'officenumber', 'hotelAddress', 'stateProvince', 'city', 'country',
            'locality', "Accountno", "BankName","Accountholder",
            'crnumber', 'expiry', 'vatnumber', 'About', 'polices', 'logo_image', 'chalet_images', 'supportingDocuments',
            'about_arabic','polices_arabic','chalet_type'
        ]}

        post_data["chalet_images"] = request.FILES.getlist("chalet_images[]")
        post_data["supportingDocuments"] = request.FILES.getlist("supportingDocuments[]")
        post_data["logo_image"] = request.FILES.get("logo_image")

        errors = {}
        errors.update(validate_phone_field(post_data["officenumber"]))
        # Validate only required fields (excluding optional fields)
        required_fields = {k: v for k, v in post_data.items() if k not in [
           'crnumber', 'about_arabic', 'polices_arabic','locality','About', 'polices',
            "Accountno", "BankName","Accountholder", 'vatnumber', 'expiry' # Include other optional fields here
        ]}
        try:
            chalet_owner = OwnerName.objects.filter(
                owner_name=post_data["chaletOwnerName"],
                owner_name_arabic=post_data["chaletOwnerArabicName"]
            ).first()

            if not chalet_owner:
                chalet_owner = OwnerName.objects.create(
                    owner_name=post_data["chaletOwnerName"],
                    owner_name_arabic=post_data["chaletOwnerArabicName"]
                )
        except Exception as e:
            logger.error(f"Exception occurred at hotel owner name fetch portion: {str(e)}")
            chalet_owner = None 
        try:
            lat, long = get_lat_long(
                post_data.get("hotelAddress", ""),
                post_data.get("city", ""),
                post_data.get("stateProvince", ""),
                post_data.get("country", "")
            )

            if lat is not None and long is not None:
                logger.info(f"Fetched coordinates: latitude={lat}, longitude={long}")
            else:
                logger.warning("Could not fetch valid coordinates. Received None.")
        except Exception as e:
            logger.error(f"Error fetching coordinates: {str(e)}")
            lat = None
            long = None
                
        if not errors:
            user = User.objects.get(
                username=request.user,is_deleted=False)
            # user.first_name=post_data["chaletOwnerName"]
            user.save()

            user_details = VendorProfile.objects.get(
                user=user
            )
            country, state, city = create_or_get_location(
                post_data["country"], post_data["stateProvince"], post_data["city"]
            )
            chalettype = ChaletType.objects.get(id=post_data["chalet_type"])
            chalet = Chalet.objects.create(
                vendor=user_details,
                name=post_data["chaletName"],
                name_arabic=post_data["chaletNameArabic"],
                owner_name_arabic= post_data["chaletOwnerArabicName"],
                chalet_type=chalettype,
                address=post_data["hotelAddress"],
                country=country,
                city=city,
                state=state,
                cr_number=post_data["crnumber"],
                vat_number=post_data["vatnumber"],
                date_of_expiry=None,
                office_number=post_data["officenumber"],
                logo=post_data["logo_image"],
                about_property=post_data["About"],
                policies=post_data["polices"],
                locality=post_data["locality"],
                account_no=post_data["Accountno"],
                bank=post_data["BankName"],
                account_holder_name=post_data["Accountholder"],
                about_property_arabic = post_data["about_arabic"],
                policies_arabic = post_data["polices_arabic"],
                owner_name= chalet_owner,
                latitude= lat,
                longitude=long 
            )
            category_obj, _ = Categories.objects.get_or_create(category=category)
            chalet.category.add(category_obj)

            for chalet_image in post_data["chalet_images"]:
                ChaletImage.objects.create(chalet=chalet, image=chalet_image)

            for document in post_data["supportingDocuments"]:
                chaletDocument.objects.create(chalet=chalet, document=document)
            send_registration_email(chalet)
            return render(request, "accounts/chalet_register.html", {"category": category, "registration_success": True})

        return render(request, "accounts/chalet_register.html", {"category": category, "errors": errors})

@method_decorator(login_required(login_url='loginn'), name='dispatch')
@method_decorator(cache_control(no_cache=True, must_revalidate=True, no_store=True), name='dispatch')
class AmenitiesaddView( View):
    def get(self, request):
        print(type(request.user))
        try:
            if not request.user.is_authenticated:
                return redirect('loginn')
            try:
                user = VendorProfile.objects.get(user=request.user)
                hotel_id = request.GET.get("hotel_id")  
                if hotel_id:
                    logger.info(f"hotel_id  is ---{ hotel_id}")
                    try:
                        hotel = Hotel.objects.filter(id=hotel_id,vendor=user.id).first()
                        if hotel:
                            if hotel.approval_status == "rejected":
                                messages.error(request, _('Hotel was rejected.'))
                                if "meal_prices" in request.session:
                                    del request.session["meal_prices"]
                                    logger.info("Meal prices session data cleared.")
                                return redirect('loginn')
                            if hotel.post_approval:
                                print(f"approve:{hotel.post_approval}")
                                messages.info(request, _('Hotel post approval already completed. Redirecting to the dashboard.'))
                                return redirect("dashboard")
                            request.session["selected_hotel_id"] = hotel.id
                        else:
                            return render(request, 'accounts/404.html')
                    except Hotel.DoesNotExist:
                        hotel = None
                else:
                    try:
                        hotel = Hotel.objects.filter(vendor=user.id).first()
                        if hotel:
                            if hotel.approval_status == "rejected":
                                messages.error(request, _('Hotel was rejected.'))
                                if "meal_prices" in request.session:
                                    del request.session["meal_prices"]
                                    logger.info("Meal prices session data cleared.")
                                return redirect('loginn')
                            if hotel.post_approval:
                                print(f"approve:{hotel.post_approval}")
                                messages.info(request, _('Hotel post approval already completed. Redirecting to the dashboard.'))
                                return redirect("dashboard")
                            request.session["selected_hotel_id"] =  hotel.id
                        else:
                            return render(request, 'accounts/404.html')
                    except Hotel.DoesNotExist:
                        hotel = None

                        
                # try:
                #     chalet = Chalet.objects.filter(vendor=user.id).first()
                #     if chalet:
                #         if chalet.approval_status == "rejected":
                #             messages.error(request, _('Chalet was rejected.'))
                #             return redirect('loginn')
                # except Chalet.DoesNotExist:
                #     chalet = None

                # Check if both hotel and chalet are None
                if hotel is None :
                    return render(request, 'accounts/404.html')

                # Continue with the rest of your view logic here

            except VendorProfile.DoesNotExist:
                return render(request, 'accounts/404.html')



            amenities = Amenity.objects.filter(
                amenity_type="Property_amenity", status="True"
            )
        
            return render(
                request, "accounts/amenties.html", context={"amenities": amenities}
            )
        except :
            return render(request, 'accounts/404.html')

        

    def post(self, request):
        amenities = request.POST.getlist("amenities_checked")
        request.session["amenities"] = amenities
        hotel_id = request.session["selected_hotel_id"]
        logger.info(f"hotel is id ---{ hotel_id}")
        return JsonResponse({"next_url": f"/vendor/price/add/?hotel_id={hotel_id}"})

@method_decorator(login_required(login_url='loginn'), name='dispatch')
class BackSelectedAmmenities(View):
    def get(self, request):
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel_id = request.session.get("selected_hotel_id")
            if hotel_id:
                logger.info(f"hotel_id  is ---{ hotel_id}")
                hotel = Hotel.objects.filter(vendor=user.id,id=hotel_id).first()
            else:
                hotel = Hotel.objects.filter(vendor=user.id).first()            
                
            # try:
            #     chalet = Chalet.objects.filter(vendor=user.id).first()
            # except Chalet.DoesNotExist:
            #     chalet = None

            # Check if both hotel and chalet are None
            if hotel is None:
                return render(request, 'accounts/404.html')

            # Continue with the rest of your view logic here

        except VendorProfile.DoesNotExist:
            return render(request, 'accounts/404.html')
        
        # Clear or update session data as needed
        request.session.pop("meal_prices", None)
        request.session.pop("payment_mode", None)
        hotel_id=hotel.id


        selected_amenities = request.session.get("amenities", [])
        return JsonResponse({"selected_amenities": selected_amenities,"hotel_id":hotel_id})

@method_decorator(login_required(login_url='loginn'), name='dispatch')
@method_decorator(cache_control(no_cache=True, must_revalidate=True, no_store=True), name='dispatch')
class PriceAddView(View):
    def get(self, request):
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel_id = request.GET.get("hotel_id")  
            if hotel_id:
                logger.info(f"hotel_id  is ---{ hotel_id}")
                try:
                    hotel = Hotel.objects.filter(vendor=user.id,id=hotel_id).first()
                    Payment_ctg=PaymentTypeCategory.objects.filter(status ='active')
                    if hotel.approval_status == "rejected":
                        messages.error(request, _('Hotel was rejected.'))
                        if "meal_prices" in request.session:
                            del request.session["meal_prices"]
                            logger.info("Meal prices session data cleared.")
                        elif "payment_mode" in request.session:
                            del request.session["payment_mode"]
                            logger.info("payment_mode session data cleared.")

                        return redirect('loginn')                    
                    if hotel.post_approval:
                        messages.info(request, _('Hotel post approval already completed. Redirecting to the dashboard.'))
                        return redirect("dashboard")
                    request.session["selected_hotel_id"] =   hotel.id                    
                except Hotel.DoesNotExist:
                    hotel = None
            else:
                try:
                    hotel = Hotel.objects.filter(vendor=user.id).first()
                    Payment_ctg=PaymentTypeCategory.objects.filter(status ='active')
                    if hotel.approval_status == "rejected":
                        messages.error(request, _('Hotel was rejected.'))
                        if "meal_prices" in request.session:
                            del request.session["meal_prices"]
                            logger.info("Meal prices session data cleared.")
                        elif "payment_mode" in request.session:
                            del request.session["payment_mode"]
                            logger.info("payment_mode session data cleared.")

                        return redirect('loginn')                    
                    if hotel.post_approval:
                        messages.info(request, _('Hotel post approval already completed. Redirecting to the dashboard.'))
                        return redirect("dashboard")
                    request.session["selected_hotel_id"] =   hotel.id                    
                except Hotel.DoesNotExist:
                    hotel = None
                
            try:
                chalet = Chalet.objects.filter(vendor=user.id).first()
                if chalet:
                    if chalet.approval_status == "rejected":
                        messages.error(request, _('Chalet was rejected.'))
                        return redirect('loginn')
            except Chalet.DoesNotExist:
                chalet = None

            # Check if both hotel and chalet are None
            if hotel is None and chalet is None:
                return render(request, 'accounts/404.html')
            
            # Fetch active taxes
            taxes = Tax.objects.filter(status="active", is_deleted=False)

            # Fetch existing HotelTax or ChaletTax records for pre-filling
            if hotel:
                existing_taxes = HotelTax.objects.filter(hotel=hotel, status="active", is_deleted=False)
                tax_percentage_map = {ht.tax_id: ht.percentage for ht in existing_taxes}
            elif chalet:
                existing_taxes = ChaletTax.objects.filter(chalet=chalet, status="active", is_deleted=False)
                tax_percentage_map = {ct.tax_id: ct.percentage for ct in existing_taxes}

            # Attach existing percentages to taxes
            for tax in taxes:
                tax.percentage = tax_percentage_map.get(tax.id, None)

            context = {
                'taxes': taxes,
                'Payment_ctg': Payment_ctg
            }


            # Continue with the rest of your view logic here


        except :
            return render(request, 'accounts/404.html')

        return render(request, "accounts/price.html", context)
    # def post(self, request):
    #     meals = request.POST.getlist("meal")
    #     meal_prices = {}
    #     for meal in meals:
    #         price = request.POST.get(meal)
    #         meal_prices[meal] = price
    #     request.session["meal_prices"] = meal_prices
    #     return JsonResponse({"next_url": "/vendor/final/step/"})


    def post(self, request):
        try:
            meals = request.POST.getlist("meal")
            logger.info(f"meals : {meals}")
            payment_ctg=request.POST.getlist("payment_category")
            logger.info(f" payment_ctg : {payment_ctg}")
            if not meals and not payment_ctg:
                request.session.pop("meal_prices", None)
                request.session.pop("payment_mode", None)
                return JsonResponse({"next_url": "/vendor/final/step/"})
            
            meal_prices = {}
            for meal in meals:
                price = request.POST.get(meal)
                if price is None or not price.strip():
                    meal_prices[meal] = 0
                else:
                    try:
                        price = float(price)
                    except ValueError:
                        price = 0
                    meal_prices[meal] = price

            # Update session data
            request.session["meal_prices"] = meal_prices
            request.session["payment_mode"]=payment_ctg

            # Store tax data in session
            taxes = Tax.objects.filter(status="active", is_deleted=False)
            tax_data = {}
            for tax in taxes:
                tax_percentage = request.POST.get(f'tax_{tax.id}')
                if tax_percentage:
                    try:
                        tax_data[tax.id] = float(tax_percentage)
                    except ValueError:
                        tax_data[tax.id] = 0  # Default to 0 if invalid

            # Save tax data in session
            request.session["tax_data"] = tax_data
            hotel_id = request.session["selected_hotel_id"]

            return JsonResponse({"next_url": "/vendor/final/step/"})
        except Exception as e:
           return render(request, 'accounts/404.html')

@method_decorator(login_required(login_url='loginn'), name='dispatch')
@method_decorator(cache_control(no_cache=True, must_revalidate=True, no_store=True), name='dispatch')
class BackSelectedPrice(View):
    def get(self, request):
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel_id = request.session.get("selected_hotel_id")
            if hotel_id:
                hotel = Hotel.objects.filter(vendor=user.id,id=hotel_id).first()
            else:
                hotel = Hotel.objects.filter(vendor=user.id).first()

            # try:
            #     chalet = Chalet.objects.filter(vendor=user.id).first()
            # except Chalet.DoesNotExist:
            #     chalet = None

            # Check if both hotel and chalet are None
            if hotel is None:
                return render(request, 'accounts/404.html')

            # Continue with the rest of your view logic here

        except:
            return render(request, 'accounts/404.html')
        hotel_id=hotel.id
        selected_price = request.session.get("meal_prices", {})
        payment_types=request.session.get("payment_mode", {})
        return JsonResponse({"selected_price": selected_price,"payment_types":payment_types,"hotel_id":hotel_id})

@method_decorator(login_required(login_url='loginn'), name='dispatch')
@method_decorator(cache_control(no_cache=True, must_revalidate=True, no_store=True), name='dispatch')
class FinalStepView(View):
    def get(self, request):
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel_id=request.session.get("selected_hotel_id")
            if hotel_id:
                try:
                    hotel = Hotel.objects.get(vendor=user.id,id=hotel_id)
                    if hotel:
                        if hotel.approval_status == "rejected":
                            messages.error(request, _('Hotel was rejected.'))
                            if "meal_prices" in request.session:
                                del request.session["meal_prices"]
                                logger.info("Meal prices session data cleared.")
                            return redirect('loginn')
                        if hotel.post_approval:
                            messages.info(request, _('Hotel post approval already completed. Redirecting to the dashboard.'))
                            return redirect("dashboard")
                except Hotel.DoesNotExist:
                    return render(request, 'accounts/404.html')
            else:
                try:
                    hotel = Hotel.objects.filter(vendor=user.id).first()
                    if hotel:
                        if hotel.approval_status == "rejected":
                            messages.error(request, _('Hotel was rejected.'))
                            if "meal_prices" in request.session:
                                del request.session["meal_prices"]
                                logger.info("Meal prices session data cleared.")
                            return redirect('loginn')
                        if hotel.post_approval:
                            messages.info(request, _('Hotel post approval already completed. Redirecting to the dashboard.'))
                            return redirect("dashboard")
                except Hotel.DoesNotExist:
                    hotel = None


            try:
                chalet = Chalet.objects.filter(vendor=user.id).first()
                if chalet:
                    if chalet.approval_status == "rejected":
                        messages.error(request, _('Chalet was rejected.'))
                        return redirect('loginn')
            except Chalet.DoesNotExist:
                chalet = None

            if hotel is None and chalet is None:
                return render(request, "accounts/404.html")

        except VendorProfile.DoesNotExist:
            return render(request, "accounts/404.html")


        # Filter policy categories and names created by super admin
        super_admins = User.objects.filter(is_superuser=True,is_deleted=False)
        id_policy_category = PolicyCategory.objects.filter(name='Identity Proof',created_by__in=super_admins).first()
        policy_categories = PolicyCategory.objects.exclude(name='Identity Proof').filter(created_by__in=super_admins).prefetch_related('policy_names').all()

        filtered_policy_categories = []
        for category in policy_categories:
            filtered_policy_names = category.policy_names.filter(created_by__in=super_admins)
            filtered_policy_categories.append({
                'category': category,
                'policy_names': filtered_policy_names
            })
        id_policy = id_policy_category.policy_names.filter(created_by__in=super_admins) if id_policy_category else []

        # Check if there are any identity proof policies
        has_identity_proof = bool(id_policy)

        context = {
            "hotel_images": hotel,
            "policy_categories": filtered_policy_categories,
            "id_policy": id_policy,
            "has_identity_proof": has_identity_proof 
            }

        return render(request, "accounts/final_step.html", context=context)

    def post(self, request):
        try:
            logger.info(f"POST request initiated by user: {request.user} at {timezone.now()}")

            user = VendorProfile.objects.get(user=request.user)
            logger.info(f"VendorProfile retrieved for user: {request.user}")
            hotel_id=request.session.get("selected_hotel_id")

            # Retrieve hotel or chalet for the vendor
            try:
                hotel = Hotel.objects.filter(vendor=user.id,id=hotel_id).first()
                if hotel:
                    if hotel.approval_status == "rejected":
                        messages.error(request, _('Hotel was rejected.'))
                        if "meal_prices" in request.session:
                            del request.session["meal_prices"]
                            logger.info("Meal prices session data cleared.")
                        return redirect('loginn')
                logger.info(f"Hotel retrieved for vendor: {user.id}")
                logger.info(f"hotel found is ----{hotel.name}")
            except Hotel.DoesNotExist:
                logger.warning(f"No hotel found for vendor: {user.id}. Trying to fetch chalet.")
                

                try:
                    chalet = Chalet.objects.filter(vendor=user.id).first()
                    if chalet is None:
                        logger.error(f"No chalet found for vendor: {user.id}")
                        return render(request, 'accounts/404.html')
                    else:
                        logger.info(f"Chalet retrieved for vendor: {user.id}")
                        if chalet.approval_status == "rejected":
                            messages.error(request, _('Chalet was rejected.'))
                            return redirect('loginn')
                except Chalet.DoesNotExist:
                    logger.error(f"No chalet found for vendor: {user.id}")
                    return render(request, 'accounts/404.html')

            # Process checkin and checkout times
            checkin = request.POST.get("checkin")
            checkout = request.POST.get("checkout")
            logger.info(f"Checkin: {checkin}, Checkout: {checkout}")


            # Policies and ID proof selection
            selected_policy_ids = request.POST.getlist("policy-checkbox")
            selected_id_proof_ids = request.POST.getlist("id-proof")

            # Clear previous policies
            hotel.policies.clear()
            logger.info(f"Cleared existing policies for hotel: {hotel.id}")

            # Combine selected IDs for both policies and ID proofs
            selected_ids = set(selected_policy_ids + selected_id_proof_ids)
            logger.info(f"Selected policy and ID proof IDs: {selected_ids}")

            for policy_id in selected_ids:
                try:
                    policy = PolicyName.objects.get(id=policy_id)
                    hotel.policies.add(policy.policy_category)
                    logger.info(f"Added policy {policy.policy_category} to hotel: {hotel.id}")

                    # Save the policy name
                    hotel.policies_name.add(policy)  # Add the policy name to the hotel
                    logger.info(f"Added policy name {policy} to hotel: {hotel.id}")

                except PolicyName.DoesNotExist:
                    logger.warning(f"PolicyName with ID {policy_id} does not exist.")

            # Amenities and images
            selected_amenities = request.session.get("amenities", [])
            selected_price = request.session.get("meal_prices", {})
            selected_image_id = request.POST.get("highlight_image")
            
            if selected_image_id:
                hotel.hotel_images.update(is_main_image=False)
                HotelImage.objects.filter(id=selected_image_id).update(is_main_image=True)
                logger.info(f"Updated main image to image ID {selected_image_id} for hotel: {hotel.id}")

            for amenity_name in selected_amenities:
                amenity, created = Amenity.objects.get_or_create(amenity_name=amenity_name, amenity_type="Property_amenity")
                hotel.amenities.add(amenity)
                logger.info(f"Added amenity {amenity_name} to hotel: {hotel.id}")

            # Always create the "No meals" price object
            no_meal_price = MealPrice(meal_type='no meals', price=0.00, hotel=hotel)
            no_meal_price.save()
            logger.info(f"Added no meals price to hotel: {hotel.id}")    
            for meal_type, price in selected_price.items():
                price_value = float(price)
                if price_value > 0: 
                    meal_price = MealPrice(meal_type=meal_type, price=price, hotel=hotel)
                    meal_price.save()
                    logger.info(f"Added meal price {meal_type}: {price} to hotel: {hotel.id}")
                else:
                    logger.info(f"Skipped adding meal price {meal_type}: {price} for hotel: {hotel.id} (price is 0)")
            #save payment_accepted_methods
            try:
                payment_types=request.session.get("payment_mode", [])
                if payment_types:
                    logger.info(f"Selected payment types: {payment_types}")
                    if 'All' in payment_types:
                        paymenttype=PaymentType.objects.all()
                        hotel_payment_accepted, created = HotelAcceptedPayment.objects.get_or_create( hotel=hotel, created_by=user, modified_by=user) 
                        hotel_payment_accepted.payment_types.set(paymenttype)
                        hotel_payment_accepted.save() 
                    else:
                        paymenttype = PaymentType.objects.filter(category_id__in=payment_types)
                        wallet_payment_types = PaymentType.objects.filter(category__name__iexact="Wallet")
                        hotel_payment_accepted, created = HotelAcceptedPayment.objects.get_or_create( hotel=hotel, created_by=user, modified_by=user) 
                        hotel_payment_accepted.payment_types.set(paymenttype | wallet_payment_types)
                        hotel_payment_accepted.save() 
                    del request.session["payment_mode"]
            except Exception as e:
                logger.error(f"Error processing payment types: {e}")
            # Retrieve tax data from session and save it
            tax_data = request.session.get("tax_data", {})
            for tax_id, tax_percentage in tax_data.items():
                tax = Tax.objects.get(id=tax_id)
                if hotel:
                    HotelTax.objects.update_or_create(
                        hotel=hotel,
                        tax=tax,
                        defaults={
                            'percentage': tax_percentage,
                            'status': 'active',
                            'is_deleted': False,
                            'created_by': user,
                        }
                    )
                elif chalet:
                    ChaletTax.objects.update_or_create(
                        chalet=chalet,
                        tax=tax,
                        defaults={
                            'percentage': tax_percentage,
                            'status': 'active',
                            'is_deleted': False,
                            'created_by': user,
                        }
                    )

            # Clear tax data from session after saving
            request.session.pop("tax_data", None)

            # Save hotel details
            hotel.checkin_time = checkin
            hotel.checkout_time = checkout
            hotel.post_approval = True
            hotel.save()
            logger.info(f"Hotel {hotel.id} saved with updated checkin/checkout times and marked for post-approval.")

            # Clean up session data
            if "meal_prices" in request.session:
                del request.session["meal_prices"]
                logger.info("Meal prices session data cleared.")
            # Redirect based on categories
            categories = hotel.category.all()
            category_names = [category.category for category in categories]
            logger.info(f"Hotel categories: {category_names}")

            if "CHALET" in category_names:
                logger.info(f"Redirecting to 'dashboard_overviews' for hotel: {hotel.id}")
                return redirect("dashboard_overviews")
            else:
                logger.info(f"Redirecting to 'dashboard' for hotel: {hotel.id}")
                return redirect(f'/vendor/dashboard/?hotel_id={hotel.id}')

        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)
            return render(request, 'accounts/400.html')

class CustomPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        # Use last_login in the token, which will update when the password is reset
        login_timestamp = '' if user.last_login is None else user.last_login.replace(microsecond=0, tzinfo=None)
        return str(user.pk) + str(timestamp) + str(user.is_active) + str(login_timestamp)

    def check_token(self, user, token):
        """
        Check that a token is valid and has not expired.
        """
        # Check using Django's default method
        if not super().check_token(user, token):
            logger.info("Token failed Django's default check.")
            return False

        # Token validation is handled internally by Django
        logger.info("Token passed Django's default check.")
        return True

custom_token_generator = CustomPasswordResetTokenGenerator()

class ForgotPasswordView(View):
    def get(self, request):
        return render(request, template_name="accounts/forgot_password_email.html")

    def post(self, request):
        email = request.POST.get("email")
        is_resend = request.POST.get("resend")

        try:
            users = User.objects.filter(email=email,is_deleted=False)
            user = users.first()

            if user is None:
                return render(
                    request,
                    "accounts/forgot_password_email.html",
                    {"error": "Email address not found."},
                )

            token = custom_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_link = request.build_absolute_uri(
                reverse(
                    "password_reset_confirm", kwargs={"uidb64": uid, "token": token}
                )
            )
            message = render_to_string(
                "accounts/reset_password_email.html",
                {"user": user, "reset_link": reset_link},
            )

            email = EmailMessage(
                "Password Reset", message, settings.EMAIL_HOST_USER, [email]
            )
            email.content_subtype = "html"
            try:
                email.send()
            except Exception as e:
                logger.error(f"Error sending email: {e}")

            if is_resend:
                return render(
                    request,
                    "accounts/forgot_password_email.html",
                    {"resend_modal": True},
                )
            else:
                return render(
                    request,
                    "accounts/forgot_password_email.html",
                    {"reset_modal": True},
                )

        except User.DoesNotExist:
            return render(
                request,
                "accounts/forgot_password_email.html",
                {"error": _("Email address not found.")},
            )


class PasswordResetConfirmView(View):
    def get(self, request, uidb64, token):
        return render(
            request,
            template_name="accounts/password_rest.html",
            context={"uidb64": uidb64, "token": token},
        )

    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid,is_deleted=False)

            if custom_token_generator.check_token(user, token):
                password1 = request.POST.get("password1")
                password2 = request.POST.get("password2")

                if password1 and password2 and password1 == password2:
                    user.set_password(password1)
                    user.last_login = timezone.now() 
                    user.save()
                    new_uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

                    return render(
                        request,
                        "accounts/password_rest.html",
                        {"uidb64": new_uidb64, "token": token, "reset_success": True},
                    )
                else:
                    return render(
                        request,
                        "accounts/password_rest.html",
                        {
                            "uidb64": uidb64,
                            "token": token,
                            "message": _("Passwords do not match."),
                        },
                    )

            else:
                return render(
                    request,
                    "accounts/password_rest.html",
                    {
                        "uidb64": uidb64,
                        "token": token,
                        "message": _("link expired.Request for new link again"),
                    },
                )

        except (User.DoesNotExist, ValueError, TypeError):
            return render(
                request,
                "accounts/password_rest.html",
                {
                    "uidb64": uidb64,
                    "token": token,
                    "message": _("Invalid token or user ID."),
                },
            )


class HotelListView(View):
    def get(self, request):
        category = Categories.objects.filter(category="HOTEL").first()
        hotel = Hotel.objects.filter(category=category).order_by("-id") if category else Hotel.objects.none()
        categories = Categories.objects.order_by("id").distinct()
        return render(request, "accounts/register_view_table.html", {
            "hotel_data": hotel,
            "categories": categories,
        })

    def post(self, request):
        from_date = request.POST.get("from_date")
        to_date = request.POST.get("to_date")
        category_type = request.POST.get("category_type")
        approved = request.POST.get("approved")

        hotel_queryset = Hotel.objects.all().order_by("-id")

        if category_type:
            category = Categories.objects.filter(category=category_type).first()
            if category:
                hotel_queryset = hotel_queryset.filter(category=category)

        if approved:
            hotel_queryset = hotel_queryset.filter(approved=approved)

        if from_date and to_date:
            hotel_queryset = hotel_queryset.filter(date_of_expiry__range=[from_date, to_date])
        elif from_date:
            hotel_queryset = hotel_queryset.filter(date_of_expiry__gte=from_date)
        elif to_date:
            hotel_queryset = hotel_queryset.filter(date_of_expiry__lte=to_date)

        return render(request, "accounts/register_view_table.html", {
            "hotel_data": hotel_queryset,
        })


class HotelApprovalView(View):
    def get(self, request, *args, **kwargs):
        id = kwargs.get("pk")
        try:
            hotel = Hotel.objects.get(id=id)
            return render(
                request,
                template_name="accounts/hotel_approval_table.html",
                context={"data": hotel},
            )
        except:
            logger.info("id not exist")
            return render(request,'accounts/404.html')


    def post(self, request, *args, **kwargs):
        id = kwargs.get("pk")
        approve_status = request.POST.get("approved_status")
        hotel = Hotel.objects.get(id=id)
        hotel_owner_email = request.POST.get("email")
        rejection_remark = request.POST.get("remark", "")

        if approve_status == "True":
            subject = "Hotel Approval Notification"
            message = render_to_string(
                "accounts/hotel_approval_notification.html", {"hotel_name": hotel.name}
            )
        else:
            subject = "Hotel Disapproval Notification"
            message = render_to_string(
                "accounts/hotel_disapproval_notification.html",
                {"hotel_name": hotel.name, "rejection_remark": rejection_remark},
            )

        try:
            send_mail(
                subject,
                "",
                settings.EMAIL_HOST_USER,
                [hotel_owner_email],
                html_message=message,
                fail_silently=False,
            )
        except Exception as e:
            print(e, "error not sending email")

        hotel.approved = approve_status
        hotel.save()

        return JsonResponse({"message": _("Hotel status updated successfully.")})


class BookingView(View):
    def get(self, request):
        logger.info(f"\n\nGET------------->>>>>>>>>>>>>>>\n\n")
        # Check if the user is authenticated
        if not request.user.is_authenticated:
            logger.warning("Unauthenticated user attempted to access booking management.")
            request.session.flush()
            return redirect('loginn')

        # Set user language
        user_language = request.LANGUAGE_CODE
        activate(user_language)

        # Get the current date
        current_date = timezone.now().date()

        try:
            # Fetch VendorProfile for the logged-in user
            user = VendorProfile.objects.get(user=request.user)
            logger.info(f"VendorProfile retrieved for user: {request.user.id}")

            # Fetch the associated hotel for the vendor
            hotels = Hotel.objects.filter(vendor=user.id).select_related('vendor')
            hotel_id = request.GET.get('hotel_id')
            logger.info(f" hotel id is ---{hotel_id}")
            if hotel_id:
                selected_hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                selected_hotel= Hotel.objects.filter(vendor=user.id).first() 
            logger.info(f"selected hotel is {selected_hotel}")
            if selected_hotel:
                logger.info(f"Hotel found for vendor: {user.id}, Hotel ID: { selected_hotel.id}")
                if  selected_hotel.approval_status == "rejected":
                    logger.warning(f"Hotel { selected_hotel.id} was rejected for vendor {user.id}. Redirecting to login.")
                    messages.error(request, _('Hotel was rejected.'))
                    return redirect('loginn')
            else:
                logger.warning(f"No hotel found for vendor: {user.id}. Redirecting to login.")
                return redirect('loginn')

        except VendorProfile.DoesNotExist:
            logger.error(f"VendorProfile does not exist for user: {request.user.id}")
            return render(request, 'accounts/404.html')

        except Exception as e:
            logger.exception("An unexpected error occurred while fetching VendorProfile or Hotel.")
            return render(request, 'accounts/404.html', {"error": "An unexpected error occurred."})

        try:
            # Fetch booking data
            booking_data = []
            booking = Booking.objects.filter(
                hotel= selected_hotel,
                checkout_date__gte=current_date,
                status__in=["pending","booked","confirmed","check-in"]
            ).order_by("-id")

            cancelled = Booking.objects.filter(
                hotel= selected_hotel,
                status__in=["cancelled","rejected","expired"]
            ).order_by("-id")

            past = Booking.objects.filter(
                hotel= selected_hotel,
                checkout_date__lte=current_date,
                status__in=["completed"]
            ).order_by("-id")

            
            fromDate = request.GET.get('fromDate')
            toDate = request.GET.get('toDate')
            statusType = request.GET.get('statusType', '')  # Get the 'data' parameter from the URL

            print(f"\n\n\n\n\n\n\n\n\n\n\n\n{statusType}\n\n\n\n\n\n\n\n\n\n")
            activeButtonId = request.GET.get('activeButtonId')
            room_type = request.GET.get("room_type")
            print(statusType)
            if fromDate and toDate:
                booking = booking.filter(checkin_date__gte=fromDate, checkout_date__lte=toDate)
                logger.info(f"Filtered bookings by date range ({fromDate} to {toDate}): {booking.count()}")
            elif fromDate:
                booking = booking.filter(checkin_date__gte=fromDate)
                logger.info(f"Filtered bookings by 'from_date' ({fromDate}): {booking.count()}")
            elif toDate:
                booking = booking.filter(checkout_date__lte=toDate)
                logger.info(f"Filtered bookings by 'to_date' ({toDate}): {booking.count()}")

            if room_type and room_type != "Room Type":
                booking = booking.filter(
                    booked_rooms__room__room_types__room_types=room_type
                )
            # Filter by status type
            if statusType and statusType != "Status Type":
                booking = booking.filter(status=statusType)
            print(booking,"___________________________________")
            logger.info(f"Filtered bookings by status type ({statusType}): {booking.count()}")
            
            logger.info(f"\n\n\n\nfromDate:{fromDate}, toDate:{toDate}, statusType:{statusType}, activeButtonId\n\n\n\n")
            # Paginate booking data
            page = request.GET.get("page", 1)
            paginator = Paginator(booking, 15)
            try:
                booking_instances = paginator.page(page)
            except PageNotAnInteger:
                logger.warning(f"Invalid page number: {page}. Defaulting to page 1.")
                booking_instances = paginator.page(1)
            except EmptyPage:
                logger.warning(f"Page number {page} exceeds total pages. Showing last page.")
                booking_instances = paginator.page(paginator.num_pages)

            # Process booking instances
            for booking_instance in booking_instances:
                booked_rooms = booking_instance.booked_rooms.all()
                print(booked_rooms,"===================")
                room_type_names = []
               

                for booked_room in booked_rooms:
                    room_type_names.append(booked_room.room.room_types.room_types)

                room_type_str = ", ".join(room_type_names)
                
                booking_data.append({
                    "booking": booking_instance,
                    "room_types": room_type_str
                   
                })
            
            # Fetch room types
            room_type_obj = Roomtype.objects.all()

        except Exception as e:
            logger.info(f"\n\n\n\n\n\n\n\n Exception raised in BookingView. Exception: {e} \n\n\n\n\n\n\n\n\n\n")
            logger.exception("An error occurred while processing booking data.")
            return render(request, 'accounts/404.html', {"error": _("An error occurred while processing booking data.")})
        
        # Render the template with context data
        print(booking_data)
        return render(
            request,
            template_name="accounts/booking_management.html",
            context={
                "booking_instances_len":len(booking),
                "booking_data": booking_data,
                "booking_instances":booking_instances,
                "hotel":  selected_hotel,
                "room_type": room_type_obj,
                'past': past,
                "selected_hotel":selected_hotel,
                "hotels": hotels,
                "cancelled": cancelled,
                "page_range": paginator.page_range,
                "current_page": booking_instances,
                "LANGUAGES": settings.LANGUAGES
            },
        )

    def post(self, request):
        logger.info(f"\n\POST------------->>>>>>>>>>>>>>>\n\n")
        try:
            from_date = request.POST.get("from_date")
            to_date = request.POST.get("to_date")
            room_type = request.POST.get("room_type")
            status_type = request.POST.get('status_type')
            
            active_button_id = request.POST.get("active_button_id")
            print("\n\n\n\n\n\n\n\n\n",from_date,to_date,room_type,status_type,active_button_id,"\n\n\n\n\n\n\n\n\n\n\n\n\n\n-----------------")
            try:
                user = VendorProfile.objects.get(user=request.user)
                hotel_id = request.GET.get('hotel_id')
                logger.info(f" hotel id is ---{hotel_id}")
                if hotel_id:
                    hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
                else:
                    hotel= Hotel.objects.filter(vendor=user.id).first() 
                    # hotel = Hotel.objects.filter(vendor=user.id)
            except (VendorProfile.DoesNotExist, Hotel.DoesNotExist) as e:
                logger.error(f"VendorProfile or Hotel does not exist: {e}")
                return render(request, 'accounts/404.html', status=404)

            bookings_instance = Booking.objects.filter(hotel=hotel).order_by("-id")

            booking_section = request.POST.get("active_button_id")
            current_date = timezone.now().date()

            if booking_section == "upcoming_bookings_btn":
                bookings_instance = bookings_instance.filter(
                    checkout_date__gte=current_date,
                    status__in=["pending","booked","confirmed","check-in"]
                ).order_by("-id")
            elif booking_section == "past_bookings_btn":
                bookings_instance = bookings_instance.filter(checkout_date__lte=current_date,status__in=["completed"]).order_by("-id")
            else:
                bookings_instance = bookings_instance.filter(
                    status__in=["cancelled","rejected","expired"]
                ).order_by("-id")

            if from_date and to_date:
                bookings_instance = bookings_instance.filter(
                    checkin_date__gte=from_date, checkout_date__lte=to_date
                )
            elif from_date:
                bookings_instance = bookings_instance.filter(checkin_date__gte=from_date)
            elif to_date:
                bookings_instance = bookings_instance.filter(checkout_date__lte=to_date)

            if room_type and room_type != "Room Type":
                bookings_instance = bookings_instance.filter(
                    booked_rooms__room__room_types__room_types=room_type
                )

            if status_type and status_type != "Status Type":
                bookings_instance = bookings_instance.filter(
                    status=status_type
                )
            print(bookings_instance,"**********************")
            page = request.GET.get("page", 1)
            print(page)
            paginator = Paginator(bookings_instance, 15)
            try:
                bookings = paginator.page(page)
            except PageNotAnInteger:
                logger.warning("Page number is not an integer. Defaulting to page 1.")
                bookings = paginator.page(1)
            except EmptyPage:
                logger.warning("Page number exceeds total pages. Showing the last page.")
                bookings = paginator.page(paginator.num_pages)

            booking_data = []
            for booking_instance in bookings:
                booked_rooms = booking_instance.booked_rooms.all()
                room_type_names = []
                statuses = set()

                for booked_room in booked_rooms:
                    room_type_names.append(booked_room.room.room_types.room_types)
                    statuses.add(booked_room.status)
                    

                room_type_str = ", ".join(room_type_names)
                print(room_type_str,"===================")
                status_str = ", ".join(statuses)

                booking_data.append({
                    "booking": booking_instance,
                    "room_types": room_type_str,
                    "statuses": status_str,
                })
            return render(
                request,
                "accounts/booking_management.html",
                context={
                    "booking_data": booking_data,
                    "page_range": paginator.page_range,
                    "current_page": bookings,
                },
            )

        except Exception as e:
            logger.exception(f"An unexpected error occurred in the POST method: {e}")
            return render(request, 'accounts/500.html', status=500)



class PastBookingsView(View):
    def get(self, request):
        current_date = timezone.now().date()
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first() 
            logger.info(f"hotel founded :{  hotel}")
        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
            logger.info("vendor/ hotel profile doesn't exist")
            return render(request,'accounts/404.html')
            # return redirect('loginn')

        bookings = Booking.objects.filter(hotel=hotel,checkout_date__lte=current_date,status__in=["completed"]).order_by("-id")

        try:
            bookings = booking_filters(request,logger,bookings)
        except Exception as e:
            logger.info(f"\n\n function booking_filters inside HotelPastBooking View: {bookings}, Exception: {e}")
       
        page = request.GET.get("page", 1)
        paginator = Paginator(bookings, 15)  
        try:
            booking_instances = paginator.page(page)
        except PageNotAnInteger:
            booking_instances = paginator.page(1)
        except EmptyPage:
            booking_instances = paginator.page(paginator.num_pages)
        booking_data = []
        for booking_instance in booking_instances :
            booked_rooms = booking_instance.booked_rooms.all()
            room_type_names = []
               

            for booked_room in booked_rooms:
                room_type_names.append(booked_room.room.room_types.room_types)

            room_type_str = ", ".join(room_type_names)
        

            booking_data.append({
                "booking": booking_instance,
                "room_types": room_type_str
            })

        return render(
            request, "accounts/booking_management.html", {"booking_data": booking_data,"current_page": booking_instances}
        )


class CancelledAppointmentsView(View):
    def get(self, request):
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first() 
            logger.info(f"hotel founded :{  hotel}")

        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
            logger.info("error in fetching the user and hotel")
            return render(request,'accounts/404.html')
            # return redirect('loginn')
        booking_data = []
        booking_instances = Booking.objects.filter(hotel=hotel,status__in=["cancelled","rejected","expired"]).order_by("-id")
        try:
            booking_instances = booking_filters(request,logger,booking_instances)
            print(booking_instances)
        except Exception as e:
            logger.info(f"\n\n function booking_filters inside HotelPastBooking View: {booking_instances}")
        page = request.GET.get("page", 1)
        paginator = Paginator(booking_instances, 15) 
        try:
            bookings = paginator.page(page)
        except PageNotAnInteger:
            bookings = paginator.page(1)
        except EmptyPage:
            bookings = paginator.page(paginator.num_pages)
        for booking_instance in bookings:
            booked_rooms = booking_instance.booked_rooms.all()
            room_type_names = []

            for booked_room in booked_rooms:
                room_type_names.append(booked_room.room.room_types.room_types)

            room_type_str = ", ".join(room_type_names)
            room_type_obj = Roomtype.objects.all()

            booking_data.append({
                "booking": booking_instance,
                "room_types": room_type_str
            })



        return render(
            request,
            "accounts/booking_management.html",
            {"booking_data": booking_data,"current_page": bookings},
        )


class BookingDetail(View):
    def get(self, request, *args, **kwargs):
        print("++++++++++++++++++++++++++++++++++++++++++")
        booking_detail_id = kwargs.get("pk")
        print(booking_detail_id)
        try:
            booking_details = Bookedrooms.objects.get(pk=booking_detail_id)
            room_management = booking_details.room
            print(room_management,"===========================")
            room_type_names = [room_type.room_types.room_types for room_type in room_management]
            print(room_type_names)
            data = {
                "guest_name": booking_details.booking.booking_fname,
                "contact_number": booking_details.booking.booking_mobilenumber,
                "room_type": room_type_names,
                "check_in": booking_details.booking.checkin_date,
                "check_out": booking_details.booking.checkout_date,
                "status": booking_details.status,
            }

            return JsonResponse(data)
        except Booking.DoesNotExist:
            logger.info("booking doesn't exist")
            return render(request, 'accounts/404.html')

    def post(self, request, *args, **kwargs):

        booking_detail_id = kwargs.get("pk")
        booking_details = get_object_or_404(Bookedrooms, pk=booking_detail_id)
        status = request.POST.get("booking_status")
        if status == "cancelled":
            booking_details.room.availability = True
        elif status == "Confirmed":
            
            booking_details.room.availability = False
        booking_details.status =  status

        booking_details.save()
        booking_details.booking.save()
        booking_details.room.save()
        try:
            customer_email = booking_details.booking.booking_email
            super_admin_email = settings.SUPER_ADMIN_EMAIL 
        
            email_subject = 'Booking Details Updated'
            email_message = f"""
            Dear {booking_details.booking.booking_fname},

            Your booking details have been updated successfully. Here are the updated details:
            - Guest Name: {booking_details.booking.booking_fname}
            - Contact Number: {booking_details.booking.booking_mobilenumber}
            - Check-in Date: {booking_details.booking.checkin_date}
            - Check-out Date: {booking_details.booking.checkout_date}
            - Status: {booking_details.status}

            Thank you,
            Hotel Management
            """
            recipients = [customer_email, super_admin_email]

            # Send email to all recipients
            send_mail(
                email_subject,
                email_message,
                settings.EMAIL_HOST_USER,
                recipients,
                fail_silently=False,
            ) 
        except Exception as e:
            print("error in sending email",e)
        return JsonResponse({"message": _("Booking updated successfully")})




@method_decorator(vendor_required, name='dispatch')
class usermanagement(View):
    def get(self, request, *args, **kwargs):
        template = "accounts/booking_view.html"
        context = {}
        room_type_names = {}
        statuses = set()
        total_price = 0
        try:
            booking_id = kwargs.get("pk")
            if not booking_id:
                raise ValueError("Booking ID is missing in the request.")
            # Activate language preference
            user_language = request.LANGUAGE_CODE
            try:
                activate(user_language)
                logger.info(f"Activated user language: {user_language}")
            except Exception as e:
                logger.error(f"Error while activating user language: {e}")
            booking = get_object_or_404(Booking, id=booking_id)

            # Ensure booking has a valid transaction
            if booking.transaction:
                admin_transaction = AdminTransaction.objects.filter(transaction=booking.transaction).first()
                
                if admin_transaction:
                    admin_commission = admin_transaction.admin_commission-admin_transaction.admin_gateway_fee
                    gateway_fee = admin_transaction.gateway_fee
                    
                    
                    # Calculate total gateway fee
                    total_gateway_fee = gateway_fee
                else:
                    admin_commission = None
                    total_gateway_fee = None  # No admin transaction found
            else:
                admin_commission = None
                total_gateway_fee = None  # No transaction linked

            print("Admin Commission:", admin_commission)
            print("Total Gateway Fee:", total_gateway_fee)


            # Get the vendor profile and associated hotel
            
            user = request.user.vendor_profile
            logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
            hotels = Hotel.objects.filter(vendor=user.id).select_related('vendor')
            hotel = Hotel.objects.filter(vendor=user, id=booking.hotel.id).first()
            if hotel:
                if booking.hotel != hotel:
                    messages.error(request, _('You do not have permission to view this booking.'))
                    return redirect('loginn')
                elif not hotel.post_approval:
                    logger.info(f"Hotel {hotel.id} requires post-approval steps.")
                    return redirect(f'/vendor/ammenities/add/')
                elif hotel.approval_status == "approved": 
                    booked_rooms = booking.booked_rooms.all()
                    print(booked_rooms)
                    for booked_room in booked_rooms:
                        room = booked_room.room
                        statuses.add(booked_room.status)
                        print(booked_room, "booked_room")
                        
                  
                        room_type = room.room_types  
                
                        if room_type.room_types not in room_type_names:
                            room_type_names[room_type.room_types] = set()  
                    
                        room_type_names[room_type.room_types].update(room.amenities.all())
                        get_commission = CommissionSlab.objects.filter(
                                from_amount__lte=room.price_per_night,
                                to_amount__gte=room.price_per_night,
                                status='active'
                            ).first()
                        commission_amount = get_commission.commission_amount if get_commission else 0
                        total_price += (room.price_per_night + commission_amount)
                    status = booking.status
                    booking_transaction = getattr(booking.transaction, 'payment_status', "Transaction is unavailable")
                    payment_method = getattr(booking.transaction, 'payment_method', "Transaction is unavailable")
                    today = date.today()
                    reminder = (booking.checkin_date - today) == timedelta(days=1)
                    payment_method_name = booking.transaction.payment_type.name if booking.transaction and booking.transaction.payment_type else "Transaction is unavailable"
                    base_price = booking.booked_price + booking.discount_price - (booking.meal_price + booking.tax_and_services + booking.meal_tax)
                    context = {
                        "payment_method":payment_method,
                        "booking_transaction":booking_transaction,
                        "booking": booking,
                        "hotel": hotel,
                        "today":today,
                        "selected_hotel":hotel,
                        "hotels":  hotels,
                        "status":status,
                        "room_type_names": room_type_names,
                        "statuses": ", ".join(statuses),
                        "total_price": total_price,
                        "LANGUAGES": settings.LANGUAGES,
                        "reminder": reminder,
                        "base_price": base_price,
                        "payment_method_name": payment_method_name,
                        "admin_commission" : admin_commission,
                        "total_gateway_fee": total_gateway_fee,
                        
                    }
                    print(booking)
                    return render(
                        request,
                        template_name=template,
                        context=context
                    )
                else:
                    if hotel.approval_status == "rejected":
                        messages.error(request, _('Your Hotel was rejected.'))
                        return redirect('loginn')
                    else:
                        messages.error(request, _('Your Hotel is pending approval.'))
                        return render(request, 'chalets_accounts/pending_hotel.html')
            else:
                return redirect('loginn')
        except ValueError as ve:
            logger.error(f"ValueError occurred: {ve}")
            return render(request, 'chalets_accounts/404.html', {"error": str(ve)})

        except Exception as e:
            logger.exception(f"An unexpected error occurred: {e}")
            return render(request, 'chalets_accounts/404.html', {"error": _("An unexpected error occurred.")})
       
        
        


class UsermanagementEdit(View):
    def get(self, request, *args, **kwargs):
        id = kwargs.get("pk")
        try:
            booking = Bookedrooms.objects.get(id=id)
        except:
            logger.info("id doesn't exist")
            return render(request,'accounts/404.html')
        room_management = booking.room
        room_types = room_management.room_types.all()
        room_type_names = [room_type.room_types for room_type in room_types]
        data = {
            "guest_name": booking.booking.booking_fname,
            "contact_number": booking.booking.booking_mobilenumber,
            "room_type": room_type_names,
            "check_in": booking.booking.checkin_date,
            "check_out": booking.booking.checkout_date,
            "status": booking.status,
        }
        return JsonResponse(data)

    def post(self, request, *args, **kwargs):
        id = kwargs.get("pk")
        try:
            booking = Bookedrooms.objects.get(id=id)
        except:
            logger.info("id doesn't exist")
            return render(request,'accounts/404.html')
        booking.booking.booking_fname = request.POST.get("guest_name")
        booking.booking.booking_mobilenumber = request.POST.get("contact_number")
        booking.booking.checkin_date = request.POST.get("check_in_date")
        booking.booking.checkout_date = request.POST.get("check_out_date")
        status = request.POST.get("booking_status")
        booking.status = status
        if status == "cancelled":
            booking.room.availability = True
        booking.save()
        booking.booking.save()
        room_type_names = request.POST.get("room_types").split(",")
        room_types = Roomtype.objects.filter(room_types__in=room_type_names)
  
        try:
            if room_types.exists():
                booking.room.room_types.set(room_types)
                booking.room.save()
            else:
                print("No matching room types found")
        except Exception as e:
            print(e, "======== Error updating room types")


        try:
            customer_email =  booking.booking.booking_email
            super_admin_email = settings.SUPER_ADMIN_EMAIL 
        
            email_subject = 'Booking Details Updated'
            email_message = f"""
            Dear {booking.booking.booking_fname},

            Your booking details have been updated successfully. Here are the updated details:
            - Guest Name: {booking.booking.booking_fname}
            - Contact Number: {booking.booking.booking_mobilenumber}
            - Room Type: {', '.join(room_type_names)}
            - Check-in Date: {booking.booking.checkin_date}
            - Check-out Date: {booking.booking.checkout_date}
            - Status: {booking.status}

            Thank you,
            Hotel Management
            """

            # Send email to customer
            send_mail(
                email_subject,
                email_message,
                settings.EMAIL_HOST_USER,
                [customer_email],
                fail_silently=False,
            )

            send_mail(
                email_subject,
                email_message,
                settings.EMAIL_HOST_USER,
                [super_admin_email],
                fail_silently=False,
            )     
        except Exception as e:
            print("error in sending email",e)



        return JsonResponse({"message": _("Booking updated successfully")})
    
class CheckPromoCodeUniqe(View):
    def post(self, request):
        user = VendorProfile.objects.get(user=request.user)
        hotel_id = request.GET.get('hotel_id')
        if hotel_id:
            hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
        else:
            hotel= Hotel.objects.filter(vendor=user.id).first() 
        promo_code = request.POST.get('promo_code')
        try:
            get_promocode = Promotion.objects.filter(hotel=hotel,promo_code=promo_code)
            print(get_promocode,"===================")
            if get_promocode:
                return JsonResponse({'exists': True})
        except Promotion.DoesNotExist:
            logger.info(f"Promocode is Unique")

@method_decorator(vendor_required, name='dispatch')
class OfferManagement(View):
    template_name = "accounts/offer_promotion.html"
    def get(self, request):
        logger.info("Processing GET request at offermanagement")
        try:
            hotel = None
            user_language = request.LANGUAGE_CODE
            try:
                activate(user_language)
                logger.info(f"Activated user language: {user_language}")
            except Exception as e:
                logger.error(f"Error while activating user language: {e}")

            current_date = now().date()
            logger.info(f"Current date: {current_date}")
            # Get the vendor profile
            user = request.user.vendor_profile
            hotels = Hotel.objects.filter(vendor=user.id).select_related('vendor')
            logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first() 
            if hotel:
                logger.info(f"Hotel found for user: {request.user.id} ")
                if hotel.approval_status == "approved":
                    promo = Promotion.objects.filter(Q(hotel=hotel) | Q(multiple_hotels=hotel),status='active', category="common").order_by('-id')
                    logger.info(f"Promotion found for the hotel {hotel.id},promo :{promo}")
                    promotion_types = Promotion.PROMOTION_TYPE_CHOICES
                    page = request.GET.get('page', 1)  
                    paginator = Paginator(promo, 15)
                    try:
                        offers = paginator.page(page)
                    except PageNotAnInteger:
                        offers = paginator.page(1)  
                    except EmptyPage:
                        offers = paginator.page(paginator.num_pages) 
                    return render(
                        request,
                        self.template_name,
                        {
                            "offers": offers,
                            "hotel": hotel,
                            "LANGUAGES": settings.LANGUAGES,
                            "promotion_types": promotion_types,
                            "hotels": hotels,
                            "selected_hotel":hotel,
                        },
                    )
                elif not hotel.post_approval:
                        logger.info(f"Hotel {hotel.id} requires post-approval steps.")
                        return redirect(f'/vendor/ammenities/add/?hotel_id=hotel_id')   
                else:
                    if hotel.approval_status == "rejected":
                        messages.error(request, _('Hotel was rejected.'))
                        return redirect('loginn')  
                    else:
                        messages.error(request, _('Your Hotel is  in pending approval.'))
                        return render(request, 'accounts/pending_approval.html')
        except(Hotel.DoesNotExist):
            logger.info("hotel doesn't find at the vendoroffer section")
            messages.error(request, _("Hotel Not Found."))
            return redirect('loginn')
        except Exception as e:
            logger.exception(f"Unexpected error in offermanagement GET: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')             


    def post(self, request):
        try:
            logger.info("Processing POST request at offermanagement")
            offer_name = request.POST.get('offer_name')
            description = request.POST.get('description')
            category = request.POST.get('category')
            start_date = request.POST.get('validity_from')
            end_date = request.POST.get('validity_to')
            discount_percentage = request.POST.get('discount_percentage')
            discount_value = request.POST.get('discount_value')
            discount_percentage = discount_percentage if discount_percentage and discount_percentage.strip() != "" else None
            discount_value = discount_value if discount_value and discount_value.strip() != "" else None
            logger.info(f"POST parameters received - Offer Name: {offer_name},Description: {description},: Category :{category}")
            # Get the vendor profile
            user = request.user.vendor_profile
            logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first() 
            if not hotel:
                logger.warning(f"No Hotel found for vendor {user.id} ")
                return redirect('loginn') 
            else:
                logger.info(f"Hotel found {hotel}")
            
                minimum_spend= request.POST.get('minimum_spend') if category == 'common' else None
                promo_code = request.POST.get('promo_code') if category == 'promo_code' else None
                max_uses = request.POST.get('max_uses') if category == 'promo_code' else None
                promo_validity_from = request.POST.get('promo_validity_from') if category == 'promo_code' else None
                promo_validity_to = request.POST.get('promo_validity_to') if category == 'promo_code' else None
                targeted_type = request.POST.get('targeted_type') if category == 'targeted_offers' else None
                occasion_name = request.POST.get('occasion_name') if category == 'seasonal_event' else None
                points_required = request.POST.get('points_required') if category == 'loyalty_program' else None
                targeted_type = targeted_type if targeted_type and targeted_type.strip() != "" else 'common'
                start_date_value = None
                end_date_value = None

                
                if category == "promo_code":
                    logger.info("selected category is promo_code")
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
                else:
                    logger.info(f"selected category is {category}")
                    if start_date:
                        try:
                            start_date_value = datetime.strptime(start_date, '%Y-%m-%d').date()
                        except ValueError:
                            raise ValidationError("Start date must be in YYYY-MM-DD format.")
                
                    if end_date:
                        try:
                            end_date_value = datetime.strptime(end_date, '%Y-%m-%d').date()
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
                    hotel=hotel,
                    start_date=start_date_value,  
                    end_date=end_date_value,
                    minimum_spend=minimum_spend, 
                    discount_value=discount_value,
                    promotion_type = targeted_type,
                    source='hotel'
                )

                promotion.save()
                logger.info(f"promotion :{category} saved successfully for hotel {hotel} ")

                return redirect('offer_management') 
        
        except Exception as e:
            logger.exception(f"Unexpected error in offermanagement POST: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')  
        


@method_decorator(vendor_required, name='dispatch')
class OfferDetailView(View):
    def get(self, request, *args, **kwargs):
        try:
            logger.info("Processing GET request at offerDetailView")
            offer_id = kwargs.get("pk")
            if offer_id:
                logger.info(f"Offerdetail id received :{offer_id}")
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                hotel_id = request.GET.get('hotel_id')
                if hotel_id:
                    hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
                else:
                    hotel= Hotel.objects.filter(vendor=user.id).first() 
                if not hotel:
                    logger.warning(f"No Hotel found for vendor {user.id} ")
                    return redirect('loginn') 
                else:
                    logger.info(f"Hotel found : {hotel} ")
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
                        return render(request, "accounts/offer_promotion.html", {"error": " Offerpromotion ID doesn't exist."}) 
            else:
                logger.info("Promotion Id Not found")
                return render(request, "accounts/offer_promotion.html", {"error": " Offerpromotion ID needed."})    
        except Exception as e:
            logger.exception(f"Unexpected error in offerDetailView GET: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')  
        
            
    def post(self, request, *args, **kwargs):
        try:
            logger.info("Processing Post request at Offerdetailview")
            offer_id = kwargs.get("pk")
            if offer_id:
                logger.info(f"Offerdetail id received :{offer_id}")
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                hotel_id = request.GET.get('hotel_id')
                if hotel_id:
                    hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
                else:
                    hotel= Hotel.objects.filter(vendor=user.id).first() 
                if not hotel:
                    logger.warning(f"No Hotel found for vendor {user.id} ")
                    return redirect('loginn') 
                else:
                    logger.info(f"Hotel found : {hotel} ")
                    try:
                        promotion = get_object_or_404(Promotion, pk=offer_id)
                        logger.info(f"Promotion found :{promotion.id}")
                        offer_name = request.POST.get('offer_name')
                        description = request.POST.get('description')
                        category = request.POST.get('category')
                        start_date = request.POST.get('validity_from')
                        end_date = request.POST.get('validity_to')
                        discount_percentage = request.POST.get('discount_percentage')
                        discount_value = request.POST.get('discount_value')
                        logger.info(f"POST parameters received - Offer Name: {offer_name},Description: {description},Category :{category},  Start Date: {start_date},  End Date: {end_date},Discount :{discount_percentage}")
                        discount_percentage = discount_percentage if discount_percentage and discount_percentage.strip() != "" else None
                        discount_value = discount_value if discount_value and discount_value.strip() != "" else None

                        start_date_value = None
                        end_date_value = None

                        if start_date:
                            try:
                                start_date_value = datetime.strptime(start_date, '%Y-%m-%d').date()
                            except ValueError:
                                raise ValidationError("Start date must be in YYYY-MM-DD format.")
                        
                        if end_date:
                            try:
                                end_date_value = datetime.strptime(end_date, '%Y-%m-%d').date()
                            except ValueError:
                                raise ValidationError("End date must be in YYYY-MM-DD format.")

                        minimum_spend = request.POST.get('minimum_spend') if category == 'common' else None
                        promo_code = request.POST.get('promo_code') if category == 'promo_code' else None
                        max_uses = request.POST.get('max_uses') if category == 'promo_code' else None
                        targeted_type = request.POST.get('targeted_type') if category == 'targeted_offers' else None
                        occasion_name = request.POST.get('occasion_name') if category == 'seasonal_event' else None
                        points_required = request.POST.get('points_required') if category == 'loyalty_program' else None
                        targeted_type = targeted_type if targeted_type and targeted_type.strip() != "" else 'common'
                        promo_validity_from = request.POST.get('promo_validity_from') if category == 'promo_code' else None
                        promo_validity_to = request.POST.get('promo_validity_to') if category == 'promo_code' else None
                        if category == 'common' and minimum_spend:
                            if not minimum_spend.isdigit():
                                raise ValidationError("Minimum spend must be a whole number without decimal points.")
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

                        promotion.title = offer_name
                        promotion.category = category
                        promotion.description = description
                        promotion.discount_percentage = discount_percentage
                        promotion.promo_code = promo_code
                        promotion.max_uses = max_uses
                        promotion.occasion_name = occasion_name
                        promotion.points_required = points_required
                        promotion.start_date = start_date_value
                        promotion.end_date = end_date_value
                        promotion.minimum_spend = minimum_spend
                        promotion.discount_value = discount_value
                        promotion.promotion_type = targeted_type
                        promotion.save()
                        logger.info(f"promotion :{category} edited successfully for hotel :{hotel} ")
                        return JsonResponse({"message": _("Offer updated successfully")})
                    except Promotion.DoesNotExist:
                        logger.info("Promotion doesn't found")
                        return render(request, "accounts/offer_promotion.html", {"error": _(" Offerpromotion ID doesn't exist.")}) 
            else:
                logger.info("Promotion Id Not found")
                return render(request, "accounts/offer_promotion.html", {"error": " Offerpromotion ID needed."})  
        except Exception as e:
            logger.exception(f"Unexpected error in offermanagement POST: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')  


@method_decorator(vendor_required, name='dispatch')
class OfferDeleteView(View):
    def delete(self, request, *args, **kwargs):
        try:
            logger.info("Delete request processing at the OfferDeleteView")
            offer_id = kwargs.get("pk")
            if offer_id:
                logger.info(f"Offerdetail id received :{offer_id}")
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                hotel_id = request.GET.get('hotel_id')
                if hotel_id:
                    hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
                else:
                    hotel= Hotel.objects.filter(vendor=user.id).first() 
                if not hotel:
                    logger.warning(f"No Hotel found for vendor {user.id} ")
                    return redirect('loginn') 
                else:
                    logger.info(f"Hotel found : {hotel} ")
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
                logger.info("Promotion Id Not found")
                return render(request, "accounts/offer_promotion.html", {"error": _(" Offerpromotion ID needed.")})  
        except Exception as e:
            logger.exception(f"Unexpected error in offermanagement POST: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')  
        
@method_decorator(vendor_required, name='dispatch')
class OfferFilterView(View):
    template_name = "accounts/offer_promotion.html"
    def get(self, request):
        try:
            page = request.GET.get("page", 1)
            discount = request.GET.get("discount")
            if discount and page:
                logger.info(f"received get request for page:{page} and discount :{discount}")
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                hotel_id = request.GET.get('hotel_id')
                if hotel_id:
                    hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
                else:
                    hotel= Hotel.objects.filter(vendor=user.id).first() 
                if not hotel:
                    logger.warning(f"No Hotel found for vendor {user.id} ")
                    return redirect('loginn') 
                else:
                    logger.info(f"Hotel found {hotel}")
                    try:
                        promo = Promotion.objects.filter(Q(hotel=hotel) | Q(multiple_hotels__in=[hotel]),status='active')
                        logger.info(f"promotion found for hotel:{hotel} promotion:{promo}")
                        offer = promo.filter(category=discount).order_by('-id')
                        paginator = Paginator(offer, 15)
                        try:
                            offers = paginator.page(page)
                        except PageNotAnInteger:
                            offers = paginator.page(1)  
                        except EmptyPage:
                            offers = paginator.page(paginator.num_pages) 

                        return render(
                            request,
                            self.template_name,
                            context={
                                "offers": offers,
                                "discount": discount 
                            }
                        )
                    except Promotion.DoesNotExist:
                        logger.info("offer not found")
                        return render(request, "accounts/offer_promotion.html", {"error": _("Promotion Not exist.")}) 
            else:
                logger.info("Discount not found")
                return render(request, "accounts/offer_promotion.html", {"error": _("Discount Needed.")}) 
        except Exception as e:
            logger.exception(f"Unexpected error in offermanagement POST: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')  
        
        

    def post(self, request):
        try:
            page = request.POST.get("page", 1)
            discount = request.POST.get("discount")
            if discount and page:
                logger.info(f"received get request for page:{page} and discount :{discount}")
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                hotel_id = request.GET.get('hotel_id')
                if hotel_id:
                    hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
                else:
                    hotel= Hotel.objects.filter(vendor=user.id).first() 
                if not hotel:
                    logger.warning(f"No Hotel found for vendor {user.id} ")
                    return redirect('loginn') 
                else:
                    logger.info(f"Hotel found {hotel}")
                    try:
                        promo = Promotion.objects.filter(Q(hotel=hotel) | Q(multiple_hotels__in=[hotel]),status='active')
                        logger.info(f"promotion found for hotel:{hotel} promotion:{promo}")
                        offer = promo.filter(category=discount).order_by('-id')
                        paginator = Paginator(offer, 15)
                        try:
                            offers = paginator.page(page)
                        except PageNotAnInteger:
                            offers = paginator.page(1)  
                        except EmptyPage:
                            offers = paginator.page(paginator.num_pages) 

                        return render(
                            request,
                            self.template_name,
                            context={
                                "offers": offers,
                                "discount": discount 
                            }
                        )
                    except Promotion.DoesNotExist:
                        logger.info("offer not found")
                        return render(request, "accounts/offer_promotion.html", {"error": _("Promotion Not exist.")}) 
            else:
                logger.info("Discount not found")
                return render(request, "accounts/offer_promotion.html", {"error": _("Discount Needed.")}) 
        except Exception as e:
            logger.exception(f"Unexpected error in offermanagement POST: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')  

class RefundCancellationView(View):
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            request.session.flush()  # Clear the session
            return redirect('loginn')
        
        user_language = request.LANGUAGE_CODE
        activate(user_language)

        try:
            user = VendorProfile.objects.get(user=request.user)
            hotels = Hotel.objects.filter(vendor=user.id).select_related('vendor')
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first() 
            if hotel:
                if hotel.approval_status == "rejected":
                    messages.error(request, _('Hotel was rejected.'))
                    return redirect('loginn')
            else:
                return redirect('loginn')
        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
                logger.info("user/vendor doesn't found")
                return render(request,'accounts/404.html')            
                # return redirect('loginn')

       # Get all transactions related to bookings for a specific hotel
        page = request.GET.get("page", 1)
        bookings = Booking.objects.filter(hotel=hotel.id).values_list("transaction_id", flat=True)

        logger.info(f"Booking Transactions: {bookings}")

        # Fetch all RefundTransactions related to these transactions
        refund_transactions = RefundTransaction.objects.filter(transaction_id__in=bookings).order_by("-id")

        logger.info(f"Refund Transactions: {refund_transactions}")

        payment_choices = PaymentType.objects.filter(is_deleted=False, status='active').values('name', 'name_arabic')
        transaction_choices = RefundTransaction.REFUND_STATUS_CHOICES
        paginator = Paginator(refund_transactions, 15)
        try:
            refund_trans = paginator.page(page)
        except PageNotAnInteger:
            refund_trans = paginator.page(1)  
        except EmptyPage:
            refund_trans = paginator.page(paginator.num_pages) 

        return render(
            request,
            "accounts/refund_and_cancellation.html",
            {
                "refunds":  refund_trans,
                "booking_source": payment_choices,
                "cancel_status": transaction_choices,
                "hotel": hotel,
                "hotels": hotels,
                "selected_hotel":hotel,
                "LANGUAGES": settings.LANGUAGES
            },
        )

    def post(self, request, *args, **kwargs):
        page = request.POST.get("page", 1)
        from_date_s = request.POST.get("from_date")
        to_date_s = request.POST.get("to_date")
        cancel_status = request.POST.get("cancel_status")
        booking_source = request.POST.get("booking_source")
        from_date = datetime.strptime(from_date_s, "%Y-%m-%d").date() if from_date_s else None
        to_date = datetime.strptime(to_date_s, "%Y-%m-%d").date() if to_date_s else None
        hotel_id = request.GET.get('hotel_id')

        # Logging for debugging
        logger.info(f"Converted from_date: {from_date}, Type: {type(from_date)}")
        logger.info(f"Converted to_date: {to_date}, Type: {type(to_date)}")
        try:
            user = VendorProfile.objects.get(user=request.user)
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first() 
        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
            logger.info("User/Vendor not found")
            return render(request, "accounts/404.html")

        booking_transactions = Booking.objects.filter(hotel=hotel).values_list("transaction", flat=True)

        refunds = RefundTransaction.objects.filter(transaction__in=booking_transactions).order_by("-id")
        logger.info(f"refunds: {refunds} ")
        refund_details = refunds.values("id", "created_at", "transaction", "refund_status")
        logger.info(f"Refund Details: {list(refund_details)}")


        bookings = Booking.objects.filter(transaction__in=booking_transactions)

        

        # Apply date filters on refunds based on 'created_at'
        if from_date and to_date:
           refunds = refunds.filter(created_at__range=[from_date, to_date])
        elif from_date:
            refunds = refunds.filter(created_at__gte=from_date)
        elif to_date:
            refunds = refunds.filter(created_at__lte=to_date)



        # Ensure we are getting unique refund transactions
        refunds = refunds.filter(transaction__in=bookings.values_list("transaction", flat=True)).distinct()

        # Apply additional filters
        if cancel_status:
            refunds = refunds.filter(refund_status=cancel_status)

        if booking_source:
            refunds = refunds.filter(transaction__payment_type__name=booking_source)

        # Log and render
        logger.info(f"Total refunds found (after distinct): {refunds.count()}")
        paginator = Paginator(refunds, 15)
        try:
            refund_trans = paginator.page(page)
        except PageNotAnInteger:
            refund_trans = paginator.page(1)  
        except EmptyPage:
            refund_trans = paginator.page(paginator.num_pages) 

        return render(
            request,
            template_name="accounts/refund_and_cancellation.html",
            context={"refunds": refund_trans},
        )




class DashboardView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            request.session.flush()  # Clear the session
            return redirect('loginn')  

        user_language = request.LANGUAGE_CODE
        activate(
            user_language
        ) 

        try:
            user = VendorProfile.objects.get(user=request.user)
            hotels = Hotel.objects.filter(vendor=user.id).select_related('vendor')
           
        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
                logger.info("user/vendor doesn't found")
                return render(request,'accounts/404.html')            
                # return redirect('loginn')
        hotel_id = request.GET.get('hotel_id')
        try:
            if hotel_id:
                selected_hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                selected_hotel= Hotel.objects.filter(vendor=user.id).first() 
        except:
            return render(request,'accounts/404.html') 
        logger.info(f"hotel founded :{  selected_hotel}")
        if selected_hotel:
            if selected_hotel.approval_status == "rejected":
                messages.error(request, _('Hotel was rejected.'))
                return redirect('loginn')
            elif selected_hotel.approval_status == "pending":
                return render(request,'accounts/pending_approval.html',context={'selected_hotel':selected_hotel})  
            elif not selected_hotel.post_approval:
                return redirect(f'/vendor/ammenities/add/?hotel_id={selected_hotel.id}')

       
              

        current_year = now().year
        all_months = [f"{month_abbr[i]} {current_year}" for i in range(1, 13)]

        monthly_bookings = (
            Booking.objects.filter(hotel=selected_hotel).annotate(month=TruncMonth('booking_date'))
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
            Booking.objects.filter(hotel=selected_hotel,booking_date__range=[start_of_week, end_of_week],status__in=["confirmed","check-in"])
            .annotate(day=TruncDay('booking_date'))
            .values('day')
            .annotate(total_bookings=Count('id'))
            .order_by('day')
        )
        pending_bookings = (
            Booking.objects.filter(hotel=selected_hotel,booking_date__range=[start_of_week, end_of_week],status="pending")
            .annotate(day=TruncDay('booking_date'))
            .values('day')
            .annotate(total_bookings=Count('id'))
            .order_by('day')
        )
        cancelled_bookings = (
            Booking.objects.filter(hotel=selected_hotel,booking_date__range=[start_of_week, end_of_week],status__in=["cancelled","rejected","expired"])
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

        latest_booking = Bookedrooms.objects.filter(booking__hotel=selected_hotel).order_by("-id")[:5]

        cancel_count = Booking.objects.filter(hotel=selected_hotel,status__in=["cancelled","rejected","expired"]).count()
        total = Booking.objects.filter(hotel=selected_hotel).count() 
        confirmed_count = Booking.objects.filter(hotel=selected_hotel,status__in=["confirmed", "check-in"]).count()
        bookings_with_reviews = RecentReview.objects.filter(hotel=selected_hotel).values('booking').count()
        daily_count = Booking.objects.filter(hotel=selected_hotel,booking_date=today).count()

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

        # Pagination logic
        page = request.GET.get("page", 1)
        paginator = Paginator(latest_booking, 15)  # 5 bookings per page

        try:
            latest_booking_paginated = paginator.page(page)
        except PageNotAnInteger:
            latest_booking_paginated = paginator.page(1)
        except EmptyPage:
            latest_booking_paginated = paginator.page(paginator.num_pages)

        index = latest_booking_paginated.number - 1
        max_index = len(paginator.page_range)
        start_index = index - 3 if index >= 3 else 0
        end_index = index + 3 if index <= max_index - 3 else max_index
        page_range = list(paginator.page_range)[start_index:end_index]

        return render(
            request,
            template_name="accounts/dashboard_overview.html",
            context={"booking_data": latest_booking_paginated,
                      "hotels": hotels,
                       "page_range": page_range,  
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
                      'review_rating':formatted_review_rate,
                      'selected_hotel':selected_hotel,
                      "LANGUAGES": settings.LANGUAGES
                      },
        )


class ViewAllButton(View):
    def get(self, request):
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel_id = request.GET.get('hotel_id')
            logger.info(f" hotel id is ---{hotel_id}")
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first() 
        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
                logger.info("user/vendor doesn't found")
                return render(request,'accounts/404.html')            
                # return redirect('loginn')

        latest_booking = Bookedrooms.objects.filter(booking__hotel=hotel).order_by("-id")
        page = request.GET.get('page', 1)  
        paginator = Paginator(latest_booking, 15)
        try:
            booking_paginated = paginator.page(page)
        except PageNotAnInteger:
            booking_paginated = paginator.page(1)  
        except EmptyPage:
            booking_paginated = paginator.page(paginator.num_pages) 
        return render(
            request,
            template_name="accounts/dashboard_overview.html",
            context={"booking_data": booking_paginated},
        )

class RoomManagementView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            request.session.flush()
            return redirect('loginn')

        user_language = request.LANGUAGE_CODE
        activate(user_language)

        try:
            user = VendorProfile.objects.get(user=request.user)
            hotels = Hotel.objects.filter(vendor=user.id).select_related('vendor')
            hotel_id = request.GET.get('hotel_id')
            try:
                if hotel_id:
                    hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
                else:
                    hotel= Hotel.objects.filter(vendor=user.id).first() 
            except:
                return render(request, 'accounts/404.html')
            if hotel:
                if hotel.approval_status == "rejected":
                    messages.error(request, _('Hotel was rejected.'))
                    return redirect('loginn')
            else:
                return redirect('loginn')
        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
            logger.info("User/vendor not found")
            return render(request, 'accounts/404.html')

        # Fetch active and available rooms
        room_obj = RoomManagement.objects.filter(
            hotel=hotel.id, status='active'
        ).order_by("id")
        logger.info(room_obj)
        today = date.today()
        get_room= get_roomtype_availability(hotel,today)
        logger.info(f"---------{get_room}")
        booked_map = {entry['room']: entry['total_booked'] for entry in  get_room}
        logger.info(booked_map)
        
        room_types_obj = Roomtype.objects.filter(status='active')  
        room_type = [
            {
                'room_type': obj.room_types,  
                'id': obj.id,
                'room_type_arabic':obj.room_types_arabic
            }
            for obj in room_types_obj
        ]
        room_types_obj=RoomManagement.objects.select_related('room_types').filter(hotel=hotel,status__iexact="active")


        # Fetch amenities
        amenities = list(hotel.amenities.filter(amenity_type="Room_amenity", status=True))
        room_amenities = Amenity.objects.filter(amenity_type="Room_amenity", status=True)

        for amenity in room_amenities:
            if amenity not in amenities:
                amenities.append(amenity)

        print("Amenities Retrieved:", amenities)  # Debugging output

        # Fetch meal choices
        meal_choices_obj = MealPrice.objects.filter(hotel=hotel)
        meal_choices = [meal_choices.meal_type.capitalize() for meal_choices in meal_choices_obj]

        # Calculate total room price (including commission)
        for room in room_obj:
            room.price_per_night = Decimal(room.price_per_night)
            commission_slab = CommissionSlab.objects.filter(
                from_amount__lte=room.price_per_night,
                to_amount__gte=room.price_per_night,
                status="active"
            ).first()
            room.commission_amount = commission_slab.commission_amount if commission_slab else Decimal('0.00')
            room.total_room_price = room.price_per_night + room.commission_amount
        # RefundPolicyCategory
        refundpolicycategories=RefundPolicyCategory.objects.filter(status='active').order_by('-id')
        refundpolicies = RefundPolicy.objects.filter(status='active')  
        # Pagination
        page = request.GET.get('page', 1)
        paginator = Paginator(room_obj, 15)

        try:
            rooms = paginator.page(page)
        except PageNotAnInteger:
            rooms = paginator.page(1)
        except EmptyPage:
            rooms = paginator.page(paginator.num_pages)
        for room in rooms.object_list:
            total = room.number_of_rooms or 0
            booked = booked_map.get(room.id, 0)
            room.available_rooms = max(0, total - booked)
            room.booked_rooms=booked

        # Context data
        context = {
            "room_data": rooms,
            "room_type": room_type,
            "amenities": amenities,
            'room_types_obj':room_types_obj,
            "hotel": hotel,
            "hotels": hotels,
            "selected_hotel":hotel,
            "is_available_view": True,
            "LANGUAGES": settings.LANGUAGES,
            "meals_choices": meal_choices,
            "page_range": paginator.page_range,
            "current_page": rooms,
            "refundpolicycategories": refundpolicycategories,
            "refundpolicies": refundpolicies
        }

        return render(
            request,
            template_name="accounts/room_management.html",
            context=context,
        )
    def post(self, request):
        room_obj = RoomManagement.objects.none()  # Initialize as an empty queryset
        try:
            roomtype_value = request.POST.get("roomtype_value")
            active_btn = request.POST.get("active_btn_id")
            search_date= request.POST.get("search_date")
            logger.info(active_btn)
            logger.info(search_date)
            user = VendorProfile.objects.get(user=request.user)
            hotels = Hotel.objects.filter(vendor=user.id).select_related('vendor')
            hotel_id = request.GET.get('hotel_id')
            logger.info(f"hotel requested id is ---{  hotel_id }")
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first() 
            room_list = []
            get_room= get_roomtype_availability(hotel,search_date)
            logger.info(f"---------{get_room}")
            booked_map = {entry['room']: entry['total_booked'] for entry in  get_room}
            logger.info(booked_map)
            if active_btn == "available_btn":
                is_available_view = True
                room_obj = RoomManagement.objects.filter(
                    hotel=hotel.id,  status="active"
                ).order_by("id")
            # elif active_btn == "booked_btn":
            #     try:
            #         is_available_view = False
            #         bookings = Booking.objects.filter(hotel=hotel.id, status__in=["pending", "booked", "confirmed","check-in"])
            #         logger.info(f"bookings----{bookings}")
            #         booked_rooms = Bookedrooms.objects.filter(booking__in=bookings).values_list("room_id", flat=True)
            #         room_obj = RoomManagement.objects.filter(
            #             hotel=hotel.id, id__in=booked_rooms, status="active", availability=False
            #         ).order_by("id")
                # except Exception as e:
                #     print(e)
                #     room_obj = RoomManagement.objects.none()

            # Apply room type filter
            if roomtype_value and roomtype_value != "Room Type":
                room_obj = room_obj.filter(room_types__id=roomtype_value)
            print(f"\n\n\n\n\n\n\n\n {room_obj} \n\n\n\n\n\n\n")
            # Handle pagination
            page = request.GET.get('page', 1)
            paginator = Paginator(room_obj, 15)

            try:
                rooms = paginator.page(page)
            except PageNotAnInteger:
                rooms = paginator.page(1)
            except EmptyPage:
                rooms = paginator.page(paginator.num_pages)

            # Add room details to list
            for room in list(rooms):
                room.price_per_night = Decimal(room.price_per_night)  

                commission_slab = CommissionSlab.objects.filter(
                    from_amount__lte=room.price_per_night,
                    to_amount__gte=room.price_per_night,
                    status="active"
                ).first()
                #calculating the avilable rooms on the date based
                total = room.number_of_rooms or 0
                booked = booked_map.get(room.id, 0)
                room.available_rooms = max(0, total - booked)
                room.booked_rooms=booked
                if commission_slab:
                    room.commission_amount = commission_slab.commission_amount
                else:
                    room.commission_amount = Decimal('0.00')  

                room.total_room_price = room.price_per_night + room.commission_amount 

                try:
                    weekend_price = str(room.weekend_price.weekend_price)
                except AttributeError:
                    weekend_price = "Not specified"
                
                room_list.append({
                    "id": room.id,
                    "roomtypes": room.room_types.room_types,
                    "roomtypes_arabic":room.room_types.room_types_arabic,
                    "number_of_rooms": room.number_of_rooms,
                    "booked_rooms": room.booked_rooms,
                    "occupancy": room.total_occupancy,
                    "available_rooms":room.available_rooms,
                    "price":  str(room.price_per_night),
                    "commission_amount": str(room.commission_amount), 
                    "total_room_price": str(room.total_room_price),
                    "weekend_price": weekend_price,
                    "is_available_view": is_available_view,
                     
                })
  
            return JsonResponse({
                "rooms": room_list,
                "has_next": rooms.has_next(),
                "has_previous": rooms.has_previous(),
                "num_pages": rooms.paginator.num_pages,
                "current_page": rooms.number,
                "selected_roomtype": roomtype_value,
                "active_btn_id": active_btn,
            })
        except Exception as e:
            print(e, "=========================")  
            return JsonResponse({"error": _("An error occurred. Please try again later.")}, status=500)
        
def get_refund_policies(request):
    category_id = request.GET.get('category_id')
    logger.info("Received request")
    if category_id:
        try:
            policies = RefundPolicy.objects.filter(category_id=category_id, status="active", is_deleted=False).values(
                'id', 'name', 'title', 'is_refundable', 'is_validity_specific', 'is_percentage_specific','title_arabic',
            )
            # logger.info(f"policies found :{policies}")
            return JsonResponse(list(policies), safe=False)
        except RefundPolicy.DoesNotExist:
            logger.info("No refund policy")
    return JsonResponse({'error': _('Invalid category ID')}, status=404)



class RoomManagementBookedRoom(View):
    def get(self, request):
        if not request.user.is_authenticated:
            request.session.flush()
            return redirect('loginn') 
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel = Hotel.objects.filter(vendor=user.id).first()
        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
                logger.info("user/vendor doesn't found")
                return render(request,'accounts/404.html')            
                # return redirect('loginn')

        bookings = Bookedrooms.objects.filter(
            booking__hotel=hotel.id, booking__status__in = ["pending","booked","confirmed","check-in"]
        ).values_list("room_id", flat=True)
        room_obj = RoomManagement.objects.filter(
            hotel=hotel.id, id__in=bookings,status="active"
        ).order_by("id")
        
        for room in room_obj:
            room.price_per_night = Decimal(room.price_per_night)
            commission_slab = CommissionSlab.objects.filter(
                from_amount__lte=room.price_per_night,
                to_amount__gte=room.price_per_night,
                status="active"
            ).first()
            if commission_slab:
                room.commission_amount = commission_slab.commission_amount
            else:
                room.commission_amount = Decimal('0.00')
            room.total_room_price = room.price_per_night + room.commission_amount

        page = request.GET.get('page', 1)
        paginator = Paginator(room_obj, 15)  # Show 2 rooms per page

        try:
            rooms = paginator.page(page)
        except PageNotAnInteger:
            rooms = paginator.page(1)
        except EmptyPage:
            rooms = paginator.page(paginator.num_pages)


        return render(request, "accounts/room_management.html", {
            "room_data": rooms,
            "is_available_view": False,
        })





class RoomManagementAddView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            request.session.flush()
            return redirect('loginn') 
        room_type = request.GET.get("room_type")
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                selected_hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                selected_hotel= Hotel.objects.filter(vendor=user.id).first()  
            logger.info(f"hotel founded :{  selected_hotel}")
        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
                logger.info("user/vendor doesn't found")
                return render(request,'accounts/404.html')
        try:
            if room_type:
                room_obj = (
                    RoomManagement.objects.filter(
                        hotel=selected_hotel.id, room_types__room_types=room_type
                    )
                    .order_by("id")
                    .first()
                )
                room_datas = {
                    "price_per_night": room_obj.price_per_night,
                    "amenities": list(
                        room_obj.amenities.values_list("amenity_name", flat=True)
                    ),
                }
            return JsonResponse(room_datas)
        except RoomManagement.DoesNotExist:
            logger.info("room id not found")
            return render(request,'accounts/404.html')       
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    def post(self, request):
        if not request.user.is_authenticated:
            request.session.flush()
            return redirect('loginn')

        # Extract data from POST request
        logger.info("request received for add room")
        number_of_rooms = request.POST.get("number_of_rooms")
        logger.info("\n\n\n\n\n\n\n",number_of_rooms,"======================number_of_rooms===============================\n\n\n\n\n")
        adults = request.POST.get("adults")
        logger.info("\n\n\n\n\n\n\n",adults,"===========================adults==========================\n\n\n\n\n")
        children = request.POST.get("children")
        print("\n\n\n\n\n\n\n",children,"==========================children===========================\n\n\n\n\n")
        price_per_night = request.POST.get("pice_per_night")  
        print("\n\n\n\n\n\n\n",price_per_night,"===================price_per_night==================================\n\n\n\n\n")
        room_type = request.POST.get("roomtypes")
        print("\n\n\n\n\n\n\n",room_type,"=========================room_type============================\n\n\n\n\n")
        amenities = request.POST.getlist("amenities")
        print("\n\n\n\n\n\n\n",amenities,"==========================amenities===========================\n\n\n\n\n")
        total_occupancy = int(adults) + int(children)
        print("\n\n\n\n\n\n\n",total_occupancy,"====================total_occupancy=================================\n\n\n\n\n")
        weekend_price = request.POST.get("weekend_price")
        print("\n\n\n\n\n\n\n",weekend_price,"======================weekend_price===============================\n\n\n\n\n")
        meal_tax_percentage = request.POST.get("meal_tax")  # New Meal Tax Input
        print("\n\n\n\n\n\n\n",meal_tax_percentage,"================meal_tax_percentage=====================================\n\n\n\n\n")
        user = VendorProfile.objects.get(user=request.user)
        print("\n\n\n\n\n\n\n",user,"===============================user======================\n\n\n\n\n")
        hotel_id = request.GET.get('hotel_id')
        logger.info(f"hotel_id -- { hotel_id } ")
        if hotel_id:
            hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
        else:
            hotel= Hotel.objects.filter(vendor=user.id).first()  
        print("\n\n\n\n\n\n\n",hotel,"===========================hotel==========================\n\n\n\n\n")
        images = request.FILES.getlist("standard_images-add")
        print(f"\n\n\n\n\n\n\n images==========={images}\n\n\n\n\n\n\n\n")
        meals = request.POST.getlist("meals")
        refund_policies_json = request.POST.get("refund_policies", "[]")
        logger.info(refund_policies_json)

        # Process meal choice
        meal_choice = 'no meals' if not meals else [meal.lower() for meal in meals]

        try:
            # Fetch the room type
            room_type_obj = Roomtype.objects.get(id=room_type)

            # Create RoomManagement object
            room_manage_obj = RoomManagement.objects.create(
                hotel=hotel,
                total_occupancy=total_occupancy,
                adults=adults,
                children=children,
                price_per_night=price_per_night,
                room_types=room_type_obj
            )
            room_manage_obj.number_of_rooms = number_of_rooms
            room_manage_obj.save()
            # Add meals to the room
            roommeals_obj = MealPrice.objects.filter(meal_type__in=meal_choice, hotel=hotel)
            room_manage_obj.meals.add(*roommeals_obj)
            logger.info("meals obj created")

            # Add images to the room
            logger.info("image procesing started")
            if images:
                logger.info("image found")
                with ThreadPoolExecutor(max_workers=5) as executor:
                    for image_file in images:
                        executor.submit(save_image, image_file, room_manage_obj)
                logger.info("image added")
                # for image_file in images:
                #     new_image = RoomImage.objects.create(
                #         image=image_file
                #     )
                #     room_manage_obj.image.add(new_image)
            else:
                logger.info("Image not found")
                get_room_obj = RoomManagement.objects.filter(
                        room_types=room_type_obj
                    ).first()
                if get_room_obj:
                    get_room_image = get_room_obj.image.all()
                    for room_image in get_room_image:
                        room_manage_obj.image.add(room_image)
            logger.info("Image added")
            # Add amenities to the room
            for amenity in amenities:
                amenity_obj, created = Amenity.objects.get_or_create(
                    amenity_name=amenity,
                )
                room_manage_obj.amenities.add(amenity_obj)
            logger.info("amenities added")

            # Save the weekend price if provided
            logger.info("weekend price processing started")
            if weekend_price == "Not specified":
                pass
            elif weekend_price:
                weekend_price_decimal = Decimal(weekend_price)
                weekend_price_obj, created = WeekendPrice.objects.update_or_create(
                    room=room_manage_obj,
                    defaults={
                        'weekend_price': weekend_price_decimal,
                        'status': 'active',
                    }
                )
                logger.info(f"Weekend Price {'created' if created else 'updated'} for Room {room_manage_obj.room_types.room_types}.")

            # Save Meal Tax if provided
            if meal_tax_percentage:
                meal_tax_decimal = Decimal(meal_tax_percentage)
                MealTax.objects.create(
                    room=room_manage_obj,
                    name=f"Meal Tax for Room {room_manage_obj.room_types.room_types}",
                    percentage=meal_tax_decimal,
                    status="active",
                    created_by=user
                )
                logger.info(f"Meal Tax {meal_tax_percentage}% added to Room {room_manage_obj.room_types.room_types}.")
            #save refund details
            # Save refund details
            refund_policies = json.loads(refund_policies_json)
            User = request.user

            for policy in refund_policies:
                selected_category = policy.get("selected_category")
                policy_id = policy.get("policy_id")
                validity_str = policy.get("validity")  # Validity is fetched only for refundable policies
                percentage = policy.get("percentage")

                logger.info(selected_category)
                logger.info(policy_id)

                validity = None  # Default to None   

                if selected_category:
                    try:
                        refund_category = RefundPolicyCategory.objects.get(id=selected_category)
                        logger.info(refund_category.name)

                        if refund_category.name.lower() == 'no refund':
                            # Handle the "no refund" case
                            selected_policy = RefundPolicy.objects.filter(category=refund_category).first()
                            if selected_policy:
                                room_refund_policy_obj = RoomRefundPolicy.objects.create(
                                    policy=selected_policy,
                                    room=room_manage_obj,
                                    created_by=User,
                                    modified_by=User,
                                    status='active'
                                ) 
                                logger.info(f"{room_refund_policy_obj} Created Successfully") 
                        else:
                            validity_str = policy.get("validity")  
                            if validity_str:
                                try:
                                    hours = int(validity_str)
                                    validity = timedelta(hours=hours)
                                except ValueError:
                                    logger.error(f"Invalid validity value received: {validity_str}")    

                            selected_policy = RefundPolicy.objects.get(id=policy_id)
                            if selected_policy:
                                room_refund_policy_obj = RoomRefundPolicy.objects.create(
                                    policy=selected_policy,
                                    room=room_manage_obj,
                                    created_by=User,
                                    validity=validity,  # validity is only included for refundable policies
                                    modified_by=User,
                                    status='active'
                                ) 
                                logger.info(f"{room_refund_policy_obj} Created Successfully")   
                    except Exception as e:
                        logger.error(f"An exception occurred at the room refund creation: {str(e)}")

        except Roomtype.DoesNotExist:
            logger.info(f"\n\nRoomtype ID {room_type} is not found\n\n")
            return render(request, 'accounts/404.html')

        return redirect(f"/vendor/room/?hotel_id={hotel_id}")


class RoomManagementEditview(View):
    def get(self, request, *args, **kwargs):
        logger.info("request received")
        id = kwargs.get("pk")
        try:
            room_obj = RoomManagement.objects.get(id=id)
        except:
            logger.info("room id not found")
            return render(request,'accounts/404.html')
        meal_obj=room_obj.meals.all()
        meal_data = [meal.meal_type for meal in meal_obj] 
           # RefundPolicyCategory
        room_refund_policy = RoomRefundPolicy.objects.filter(room=room_obj, is_deleted=False).select_related('policy').first()

        if room_refund_policy and room_refund_policy.policy:
            refund_policy = room_refund_policy.policy
            refund_policy_id= refund_policy.id
            refund_policy_category_id = refund_policy.category.id if refund_policy.category else None
            refund_policy_category_name = refund_policy.category.name if refund_policy.category else None
            # room_refund_policy=room_refund_policy.title
            validity = room_refund_policy.validity
            formatted_validity = format_validity(validity) 
            logger.info(formatted_validity)
            logger.info( refund_policy_category_id)
            logger.info(refund_policy_id)
            
        else:
            refund_policy = None
            refund_policy_category_id = None
            refund_policy_category_name = None
            formatted_validity = "Not provided"
            refund_policy_id=None
        weekend_price = getattr(room_obj, "weekend_price", None)
        print(weekend_price)
        if weekend_price:
            weekend_price = weekend_price.weekend_price
        else:
            weekend_price = 0.0
        print(weekend_price)
        room_datas = {
            "roomtypes": room_obj.room_types.room_types,
            "roomtypes_id": room_obj.room_types.id,
            "number_of_rooms": room_obj.number_of_rooms,
            "total_occupancy": room_obj.total_occupancy,
            "pice_per_night": room_obj.price_per_night,
            "meal_data": meal_data,
            "amenities": list(room_obj.amenities.filter(status=True).values_list("amenity_name", flat=True)),
            "adult":room_obj.adults,
            "childrens":room_obj.children,
            "weekend_price":weekend_price,
            "meal_tax": room_obj.meal_taxes.first().percentage if room_obj.meal_taxes.exists() else None,
            "refund_policy": refund_policy.name if refund_policy else None,
            "refund_policy_category":   refund_policy_category_name,
            "validity":    formatted_validity,  
            "validity_required": refund_policy.is_validity_specific if refund_policy else False,
            "percentage_required": refund_policy.is_percentage_specific if refund_policy else False,
            "refund_policy_category_id":refund_policy_category_id,
            "refund_policy_id":refund_policy_id
        }
        print(f"\n\n\n\n    {room_datas} \n\n\n\n")
        return JsonResponse(room_datas)

    def post(self, request, *args, **kwargs):
        print(request.POST.get("roomtypes"))
        id = kwargs.get("pk")
        try:
            # Update room details
            get_roomtype = Roomtype.objects.get(id=request.POST.get("roomtype_id"))
            try:
                room_obj = RoomManagement.objects.get(id=id,room_types=get_roomtype)
                room_obj.room_types = get_roomtype
                room_obj.number_of_rooms = request.POST.get("number_of_rooms")
                room_obj.price_per_night = request.POST.get("pice_per_night")
                room_obj.adults = request.POST.get("adults")
                room_obj.children = request.POST.get("children")
                room_obj.total_occupancy = int(request.POST.get("adults")) + int(request.POST.get("children"))
                refund_policies_json = request.POST.get("refund_policies", "[]")
                logger.info(refund_policies_json)
                # Update meals
                mealsedit = request.POST.getlist("mealsedit")
                if not mealsedit:
                    meals = 'no meals'
                else:
                    meals = [meal.lower() for meal in mealsedit]
                roommeals_obj = MealPrice.objects.filter(meal_type__in=meals, hotel=room_obj.hotel)
                room_obj.meals.set(roommeals_obj)

                # Update amenities
                selected_amenity_labels = request.POST.getlist("amenitiesedit")
                selected_amenities = Amenity.objects.filter(
                    amenity_name__in=selected_amenity_labels
                )
                room_obj.amenities.set(selected_amenities)

                # Save room details
                room_obj.room_types.save()
                room_obj.save()

                # Handle meal tax
                meal_tax_percentage = request.POST.get("meal_tax")  # Extract meal tax percentage
                if meal_tax_percentage:
                    meal_tax_decimal = Decimal(meal_tax_percentage)
                    meal_tax_obj, created = MealTax.objects.update_or_create(
                        room=room_obj,
                        defaults={
                            'percentage': meal_tax_decimal,
                            'status': 'active',  # Set status to active
                        }
                    )
                    print(f"Meal Tax {'created' if created else 'updated'} for Room {room_obj.room_types.room_types}.")
                else:
                    # Remove existing meal tax if no percentage is provided
                    MealTax.objects.filter(room=room_obj).delete()
                    print(f"Meal Tax removed for Room {room_obj.room_types.room_types}.")

                # Handle weekend price
                weekend_price = request.POST.get("weekend_price")  # Extract weekend price
                if weekend_price:
                    weekend_price_decimal = Decimal(weekend_price)
                    weekend_price_obj, created = WeekendPrice.objects.update_or_create(
                        room=room_obj,
                        defaults={
                            'weekend_price': weekend_price_decimal,
                            'status': 'active',  # Set status to active
                        }
                    )
                    print(f"Weekend Price {'created' if created else 'updated'} for Room {room_obj.room_types.room_types}.")
                else:
                    # Remove existing weekend price if no price is provided
                    WeekendPrice.objects.filter(room=room_obj).delete()
                    print(f"Weekend Price removed for Room {room_obj.room_types.room_types}.")
                if refund_policies_json:
                    try:
                        room_refund, created = RoomRefundPolicy.objects.get_or_create(room=room_obj)
                        refund_policies = json.loads(refund_policies_json)

                        for policy in refund_policies:
                            selected_category = policy.get("selected_category")
                            policy_id = policy.get("policy_id")
                            validity_str = policy.get("validity")  # Validity is fetched only for refundable policies

                            logger.info(selected_category)
                            logger.info(policy_id)

                            validity = None  # Default to None   
                            if selected_category:
                                try:
                                    refund_category = RefundPolicyCategory.objects.get(id=selected_category,status='active')
                                    logger.info(refund_category.name)
                                    if refund_category.name.lower() == 'no refund':
                                        selected_policy = RefundPolicy.objects.filter(category=refund_category,status='active').first()
                                        if selected_policy:
                                            room_refund.policy=selected_policy
                                            room_refund.validity=validity
                                            room_refund.save()
                                            logger.info(f"{ room_refund} Edited Successfully") 
                                    else:
                                        validity_str = policy.get("validity")  
                                        if validity_str:
                                            try:
                                                hours = int(validity_str)
                                                validity = timedelta(hours=hours)
                                            except ValueError:
                                                logger.error(f"Invalid validity value received: {validity_str}")    

                                        selected_policy = RefundPolicy.objects.get(id=policy_id)
                                        if selected_policy:
                                            room_refund.policy=selected_policy
                                            room_refund.validity=validity
                                            room_refund.save()
                                            logger.info(f"{ room_refund} Edited Successfully") 
                                except Exception as e:
                                    logger.error(f"An exception at the room-refund edit part: {str(e)}")
                    except Exception as e:
                        logger.error(f"An exception while fetching room : {str(e)}")
            except (RoomManagement.DoesNotExist):
                logger.info(f"\n\nRoom is not available\n\n")
                return render(request, 'accounts/404.html')
        except (Roomtype.DoesNotExist):
            logger.info(f"\n\nRoom and room type is not available\n\n")
            return render(request, 'accounts/404.html')

        return redirect(f"/vendor/room/?hotel_id={room_obj.hotel.id}")


class RoomManagementDelete(View):
    def get(self, request, *args, **kwargs):
        room_id = kwargs.get("pk")
        try:
            room = RoomManagement.objects.get(id=room_id)
            room.status = 'deleted'
            hotel_id=room.hotel.id
            room.save()
            if room:
                try:
                    room_refund=RoomRefundPolicy.objects.get(room=room)
                    room_refund.status='inactive'
                    room_refund.save()
                    logger.info(f"{room_refund} deleted successfully")
                    
                except Exception as e:
                    logger.info(f"an exception occured when deleting the room refund policies :{str(e)}")
        except:
            logger.info("room id not found")
            return render(request,'accounts/404.html')
        return redirect(f"/vendor/room/?hotel_id={hotel_id}")

class TransactionDetailView(View):
    def get(self, request):

        if not request.user.is_authenticated:
            request.session.flush()  
            return redirect('loginn') 
        
        user_language = request.LANGUAGE_CODE
        activate(user_language)

        try:
            user = VendorProfile.objects.get(user=request.user)
            hotels = Hotel.objects.filter(vendor=user.id).select_related('vendor')
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first()  
            if hotel:
                if hotel.approval_status == "rejected":
                    messages.error(request, _('Hotel was rejected.'))
                    return redirect('loginn')
            else:
                return redirect('loginn')
        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
            logger.info("user doesnot exist at the transaction section of vendor")
            return render(request,'accounts/404.html')
            # return redirect('loginn')

        transactions = Booking.objects.filter(
            hotel=hotel.id,
        ).select_related('transaction').prefetch_related('transaction__vendor_transaction','transaction__admin_transaction').order_by('-modified_date')
        print(transactions,"=============================")
        page = request.GET.get('page', 1)  
        transaction_status = Transaction.TRANSACTION_STATUS_CHOICES
        logger.info(transactions)
        payment_choices = list(PaymentType.objects.filter(status='active', is_deleted=False)
                       .exclude(name__isnull=True)
                       .exclude(name="")
                       .values_list('name', flat=True))
        if isinstance(payment_choices[0], str):  # If it's a list of strings, convert it to tuples
            payment_choices = [(choice, choice) for choice in payment_choices]        
        paginator = Paginator(transactions, 15)  
        print(transactions)

        try:
            paginated_transactions = paginator.page(page)
        except PageNotAnInteger:
            paginated_transactions = paginator.page(1)
        except EmptyPage:
            paginated_transactions = paginator.page(paginator.num_pages)  

        return render(
            request,
            "accounts/transaction_detail.html",
            {
                "bookings": paginated_transactions,
                "transaction_status":transaction_status,
                "payment_choices": payment_choices,
                "hotel": hotel,
                "hotels": hotels,
                "LANGUAGES": settings.LANGUAGES,
                "hotels": hotels,
                "selected_hotel":hotel
            },
        )

    def post(self, request):
        if not request.user.is_authenticated:
            request.session.flush()  
            return redirect('loginn')
        page = request.POST.get('page', 10) 
        logger.info(f"request received for page:{page}") 
        from_date = request.POST.get("from_date")
        logger.info(from_date)
        to_date = request.POST.get("to_date")
        payment_method = request.POST.get("payment_method")
        transaction_status = request.POST.get("transaction_status")
        booking_status = request.POST.get("booking_status")
      
        if from_date:
            from_date = timezone.make_aware(datetime.strptime(from_date, "%Y-%m-%d"))
            logger.info(f"Processed from_date: {from_date}")

        if to_date:
            to_date = timezone.make_aware(datetime.strptime(to_date, "%Y-%m-%d")) + timedelta(days=1) - timedelta(microseconds=1)
            logger.info(f"Adjusted to_date (end of day): {to_date}")
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first()  

        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
            logger.info("user/vendor doesn't exist at the post method of transaction section at the vendor ")
            return render(request,'accounts/404.html')
            # return redirect('loginn')

        transactions = Booking.objects.filter(
            hotel=hotel.id,
        ).select_related('transaction').prefetch_related('transaction__vendor_transaction','transaction__admin_transaction').order_by('-modified_date')
        transactions = transaction_list_filter(transactions = transactions, from_date = from_date,  to_date = to_date, payment_method = payment_method, transaction_status=transaction_status, booking_status=booking_status)
      
        logger.info(f"Filtered transactions count: {transactions.count()}")
        paginator = Paginator(transactions, 15)  
        print(transactions)
        try:
            paginated_transactions = paginator.page(page)
        except PageNotAnInteger:
            paginated_transactions = paginator.page(1)
        except EmptyPage:
            paginated_transactions = paginator.page(paginator.num_pages)  

        payment_choices = list(PaymentType.objects.filter(status='active', is_deleted=False)
                       .exclude(name__isnull=True)
                       .exclude(name="")
                       .values_list('name', flat=True))
        if isinstance(payment_choices[0], str):  # If it's a list of strings, convert it to tuples
            payment_choices = [(choice, choice) for choice in payment_choices]         
        return render(
            request,
            "accounts/transaction_detail.html",
            {"bookings": paginated_transactions, "payment_choices": payment_choices},
        )


# class PromoCodeView(View):
#     def get(self, request):
#         if not request.user.is_authenticated:
#             request.session.flush()  # Clear the session
#             return redirect('loginn') 
        
#         user_language = request.LANGUAGE_CODE
#         activate(user_language)

#         try:
#             user = VendorProfile.objects.get(user=request.user)
#             hotel = Hotel.objects.filter(vendor=user.id).first()
#             if hotel.approval_status == "rejected":
#                 messages.error(request, 'Hotel was rejected.')
#                 return redirect('loginn')
#         except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
#             return render(request,'accounts/404.html')

#         promo_obj = PromoCode.objects.filter(hotel=hotel)
#         if promo_obj:
#             return render(
#                 request,
#                 template_name="accounts/manage_promo_code.html",
#                 context={
#                     "promo_data": promo_obj,
#                     "hotel": hotel,
#                     "LANGUAGES": settings.LANGUAGES,
#                 },
#             )
#         return render(
#             request,
#             template_name="accounts/manage_promo_code.html",
#             context={"hotel": hotel,"LANGUAGES": settings.LANGUAGES},
#         )

#     def post(self, request):

#         user = VendorProfile.objects.get(user=request.user)
#         hotel = Hotel.objects.filter(vendor=user.id).first()
#         code_name = request.POST.get("code_name")
#         discount_percentage = request.POST.get("discount_percentage")
#         validity_from = request.POST.get("validity_from")
#         validity_to = request.POST.get("validity_to")
#         usage_limits = request.POST.get("usage_limits")
#         applicable = request.POST.get("applicable")

#         promo_obj, created = PromoCode.objects.get_or_create(
#             hotel=hotel,
#             code_name=code_name,
#             discount_percentage=discount_percentage,
#             validity_from=validity_from,
#             validity_to=validity_to,
#             usage_limits=usage_limits,
#             applicable=applicable,
#         )

#         return redirect("promocode")


# class PromoCodeEdit(View):
#     def get(self, request, *args, **kwargs):
#         id = kwargs.get("pk")
#         promo_obj = PromoCode.objects.get(id=id)
#         promo_data = {
#             "code_name": promo_obj.code_name,
#             "discount_percentage": promo_obj.discount_percentage,
#             "validity_from": promo_obj.validity_from,
#             "validity_to": promo_obj.validity_to,
#             "usage_limits": promo_obj.usage_limits,
#             "applicable": promo_obj.applicable,
#         }
#         return JsonResponse(promo_data)

#     def post(self, request, *args, **kwargs):
#         id = kwargs.get("pk")
#         promo_obj = PromoCode.objects.get(id=id)

#         code_name = request.POST.get("code_name")
#         discount_percentage = request.POST.get("discount_percentage")
#         validity_from = request.POST.get("validity_from")
#         # validity_from = datetime.strptime(validity_from,'%Y-%m-%d')
#         validity_to = request.POST.get("validity_to")
#         # validity_to = datetime.strptime(validity_to,'%Y-%m-%d')
#         usage_limits = request.POST.get("usage_limits")
#         applicable = request.POST.get("applicable")

#         promo_obj.code_name = code_name
#         promo_obj.discount_percentage = discount_percentage
#         promo_obj.validity_from = validity_from
#         promo_obj.validity_to = validity_to
#         promo_obj.usage_limits = usage_limits
#         promo_obj.applicable = applicable
#         promo_obj.save()

#         return redirect("promocode")


# class PromoCodeDelete(View):
#     def post(self, request, *args, **kwargs):
#         id = kwargs.get("pk")
#         PromoCode.objects.get(id=id).delete()
#         return redirect("promocode")


# class PromoCodeFilters(View):
#     def post(self, request):
#         from_date = request.POST.get("from_date")
#         to_date = request.POST.get("to_date")
#         discount = request.POST.get("discount")

#         user = VendorProfile.objects.get(user=request.user)
#         hotel = Hotel.objects.filter(vendor=user.id).first()
#         promo_obj = PromoCode.objects.filter(hotel=hotel)

#         if from_date and to_date:

#             promo_obj = promo_obj.filter(
#                 Q(validity_from__lte=to_date) & Q(validity_to__gte=from_date)
#             )

#         elif from_date:
#             promo_obj = promo_obj.filter(validity_to__gte=from_date)

#         elif to_date:
#             promo_obj = promo_obj.filter(validity_from__lte=to_date)

#         elif discount:
#             promo_obj = promo_obj.filter(discount_percentage=discount)

#         return render(
#             request,
#             template_name="accounts/manage_promo_code.html",
#             context={"promo_data": promo_obj},
#         )

@method_decorator(vendor_required, name='dispatch')
class ReviewAndRating(View):
    def get(self, request):
        hotel = None
        user_language = request.LANGUAGE_CODE
        try:
            activate(user_language)
            logger.info(f"Activated user language: {user_language}")
        except Exception as e:
            logger.error(f"Error while activating user language: {e}")

        current_date = now().date()
        logger.info(f"Current date: {current_date}")

        try:
             # Get the vendor profile
            try:
                user = request.user.vendor_profile
            except:
                return redirect('loginn') 
            logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
            hotels = Hotel.objects.filter(vendor=user.id).select_related('vendor')
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first()  
            logger.info(f"hotel founded :{ hotel}")
            if hotel:
                logger.info(f"Hotel found for user: {request.user.id} ")
                if hotel.approval_status == "approved":
                    reviews = RecentReview.objects.filter(hotel=hotel).order_by("-date")
                    ratings = RecentReview.RATING
                    page = request.GET.get('page', 1)  
                    #pagination
                    paginator = Paginator(reviews, 15)
                    try:
                        review_paginated = paginator.page(page)
                        logger.info(f"Paginated review - Page: {page}")
                    except PageNotAnInteger:
                        review_paginated = paginator.page(1)  
                        logger.warning("Page not an integer. Defaulting to page 1.")
                    except EmptyPage:
                        review_paginated = paginator.page(paginator.num_pages) 
                        logger.warning("Page out of range. Displaying last page.")
                    context={"reviews":  review_paginated, "ratings": ratings, "hotel": hotel,"LANGUAGES": settings.LANGUAGES,"hotels": hotels,"selected_hotel":hotel}
                    return render(request,"accounts/review_rating.html",context=context, 
                ) 
                elif not hotel.post_approval:
                    logger.info(f"Hotel {hotel.id} requires post-approval steps.")
                    return redirect(f'/vendor/ammenities/add/?hotel_id={hotel_id}')   
                else:
                    if hotel.approval_status == "rejected":
                        messages.error(request, _('Hotel was rejected.'))
                        return redirect('loginn')  
                    else:
                        messages.error(request, 'Your Hotel is  in pending approval.')
                        return render(request, 'accounts/pending_approval.html')           
                        
        except (Hotel.DoesNotExist):
            logger.info("hotel doesn't find at the vendor-review section")
            messages.error(request, _("Hotel Not Found."))
            return redirect('loginn')
        except Exception as e:
            logger.exception(f"Unexpected error in HotelReviewRatingView GET: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')            

    def post(self, request):
        reviews=None
        try:
            logger.info("Processing POST request for HotelreviewRatingView.")            
            page = request.POST.get('page', 1)  
            from_date_s= request.POST.get("from_date")
            to_date_s = request.POST.get("to_date")
            review_rating = request.POST.get("review_rating")
            hotel_id = request.GET.get('hotel_id')
            logger.info(f"POST parameters received - From Date: {from_date_s}, To Date: {to_date_s}, Page: {page},  review_rating: {review_rating}")
            from_date = None
            to_date = None
            if from_date_s:
                from_date = timezone.make_aware(datetime.strptime(from_date_s, "%Y-%m-%d"))
                logger.info(f"from_date:{from_date}")
            if to_date_s:
                to_date = timezone.make_aware(datetime.strptime(to_date_s, "%Y-%m-%d")) + timedelta(days=1) - timedelta(seconds=1)
            #fetch vendor profile
            user = request.user.vendor_profile
            logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
            #fetch hotel
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first()              
            if not hotel:
                logger.warning(f"No Hotel found for vendor {user.id} ")
                return redirect('loginn') 
            else:               
                logger.info(f"Hotel found for user: {request.user.id} Hotel: {hotel.name}")
                reviews = RecentReview.objects.filter(hotel=hotel).order_by("-date")
                # reviews = RecentReview.objects.all()
                if reviews:
                    if from_date and to_date and review_rating:
                        reviews = reviews.filter(
                            date__range=[from_date, to_date], rating=review_rating
                        )

                    elif from_date and to_date:
                        reviews = reviews.filter(date__range=[from_date, to_date])

                    elif from_date and review_rating:
                        reviews = reviews.filter(date__gte=from_date, rating=review_rating)

                    elif to_date and review_rating:
                        reviews = reviews.filter(date__lte=to_date, rating=review_rating)

                    elif from_date:
                        reviews = reviews.filter(date__gte=from_date)

                    elif to_date:
                        reviews = reviews.filter(date__gte=to_date)

                    elif review_rating:
                        reviews = reviews.filter(rating=review_rating)

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
                        "accounts/review_rating.html",
                        {"reviews": review_paginated, "ratings": ratings},
                    )
                else:
                    logger.warning(f"review not found")
                    return render(request,"accounts/review_rating.html", {"error": _("Review not found.")})
        except Exception as e:
            logger.exception(f"Unexpected error in  HotelReviewRatingView POST: {e}")
            return render(request,"accounts/review_rating.html", {"error": _("An unexpected error occurred.")})

@method_decorator(vendor_required, name='dispatch')
class ReviewRespondView(View):
    def post(self, request, *args, **kwargs):
        try:
            logger.info("Processing POST request for ReviewRespondView.")            
            id = kwargs.get("pk")
            if id:
                logger.info(f"ID received for received for recent-review :{ id } ")                           
                respond_text = request.POST.get("respond")
                logger.info(f"Response receceived for recentreview :{ respond_text } ")                           
                #fetch vendor profile
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                #fetch hotel
                hotel_id = request.GET.get('hotel_id')
                if hotel_id:
                    hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
                else:
                    hotel= Hotel.objects.filter(vendor=user.id).first()  
                if not hotel:
                    logger.warning(f"No Hotel found for vendor {user.id} ")
                    return redirect('loginn') 
                else:
                    logger.info(f"Hotel found for user: {request.user.id} Hotel: {hotel.name}")
                    try:
                        review = RecentReview.objects.get(id=id)
                        review.respond = respond_text
                        review.save()
                        return JsonResponse({"message": _("Offer updated successfully")})
                    except RecentReview.DoesNotExist:
                        logger.error(f" RecentReview not found for user: {request.user.id} ({request.user.username})")
                        return render(request, "accounts/review_rating.html", {"error": _(" RecentReview not found.")})
            else:
                logger.error(f"RecentReview ID Needed")
                return render(request, "accounts/review_rating.html", {"error": _(" RecentReview ID not found.")})
        except Exception as e:
            logger.exception(f"Unexpected error in  HotelReviewRespondView POST: {e}")
            return render(request,"accounts/review_rating.html", {"error": _("An unexpected error occurred.")})
          
@method_decorator(vendor_required, name='dispatch')
class ReviewEditView(View):
    def get(self, request, *args, **kwargs):
        try:
            logger.info("Processing GET request for ReviewEditView.") 
            review_id = kwargs.get("pk")  
            if review_id:
                logger.info(f"ID received for received for recent-review :{ review_id } ")  
                #fetch vendor profile
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                #fetch hotel
                hotel_id = request.GET.get('hotel_id')
                if hotel_id:
                    hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
                else:
                    hotel= Hotel.objects.filter(vendor=user.id).first()  
                if not hotel:
                    logger.warning(f"No Hotel found for vendor {user.id} ")
                    return redirect('loginn')   
                else:   
                    logger.info(f"Hotel found for user: {request.user.id} Hotel: {hotel.name}")                   
                    try:
                        review = RecentReview.objects.get(id=review_id) 
                        data = {
                            "review_text": review.respond,
                        }
                        return JsonResponse(data)  
                    except RecentReview.DoesNotExist:
                        logger.error(f"Review with ID {review_id} not found.")
                        return render(request, "accounts/review_rating.html", {"error": _(" RecentReview not found.")})
        except Exception as e:
            logger.exception(f"Unexpected error in  HotelReviewEditView GET: {e}")
            return render(request,"accounts/review_rating.html", {"error": _("An unexpected error occurred.")})
    def post(self, request, *args, **kwargs):
        try:
            logger.info("Processing POST request for ReviewEditView.") 
            id = kwargs.get("pk")
            if id:
                logger.info(f"ID received for received for recent-review :{ id } ")  
                respond_text = request.POST.get("respond")
                logger.info(f"Response receceived for recentreview :{ respond_text } ")                           
                #fetch vendor profile
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                #fetch hotel
                hotel_id = request.GET.get('hotel_id')
                if hotel_id:
                    hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
                else:
                    hotel= Hotel.objects.filter(vendor=user.id).first()  
                if not hotel:
                    logger.warning(f"No Hotel found for vendor {user.id} ")
                    return redirect('loginn') 
                else:
                    logger.info(f"Hotel found for user: {request.user.id} Hotel: {hotel.name}")                   
                    try:
                        review = RecentReview.objects.get(id=id)
                        review.respond = respond_text
                        review.save()
                        logger.info(f"Recentreview with id: {id} edited successfully")                           
                        return redirect("review_rating_vendor") 
                    except RecentReview.DoesNotExist:
                        logger.error(f"Review with ID {id} not found.")
                        return render(request, "accounts/review_rating.html", {"error": _(" RecentReview not found.")})
            else:
                logger.error(f"RecentReview ID Needed")
                return render(request, "accounts/review_rating.html", {"error": _(" RecentReview ID not found.")})
        except Exception as e:
            logger.exception(f"Unexpected error in  HotelReviewEditView POST: {e}")
            return render(request,"accounts/review_rating.html", {"error": _("An unexpected error occurred.")})                
            
    def delete(self, request, *args, **kwargs):
        try:
            logger.info("Processing DELETE request for ReviewEditView.") 
            review_id = kwargs.get("pk") 
            if review_id:
            #fetch vendor profile
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                #fetch hotel
                hotel_id = request.GET.get('hotel_id')
                if hotel_id:
                    hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
                else:
                    hotel= Hotel.objects.filter(vendor=user.id).first()  
                if not hotel:
                    logger.warning(f"No Hotel found for vendor {user.id} ")
                    return redirect('loginn')  
                else:
                    logger.info(f"Hotel found for user: {request.user.id} Hotel: {hotel.name}")                   
                    try:
                        review = RecentReview.objects.get(id=review_id) 
                        review.respond=None
                        review.save()
                        logger.info(f"Recentreview with id: {id} deleted successfully")                           
                        return JsonResponse({"message": _("Review response deleted successfully")})
                    except RecentReview.DoesNotExist:
                        logger.error(f"Review with ID {id} not found.")
                        return render(request, "accounts/review_rating.html", {"error": _(" RecentReview not found.")})
            else:
                logger.error(f"RecentReview ID Needed")
                return render(request, "accounts/review_rating.html", {"error": _(" RecentReview ID not found.")})
        except Exception as e:
            logger.exception(f"Unexpected error in  HotelReviewEditView DELETE: {e}")
            return render(request,"accounts/review_rating.html", {"error": _("An unexpected error occurred.")})


@method_decorator(csrf_exempt, name="dispatch")
class ManageBookingView(View):
    def post(self, request, *args, **kwargs):

        booking_id = request.POST.get("id")
        action = request.POST.get("action")

        if not booking_id or not action:
            return JsonResponse({"success": False, "error": _("Invalid data")})

        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return JsonResponse({"success": False, "error": _("Booking not found")})

          


        if action == "cancel":
            if booking.status != "rejected":
                booking.status = "rejected"
                booking.save()
                booked_rooms = booking.booked_rooms.all()
                for booked_room in booked_rooms:
                    booked_room.status = "cancelled"
                    booked_room.room.availability = True
                    booked_room.room.save()
                    booked_room.save()
                try:
                    message = f"{booking.hotel.name} has rejected your booking"
                    message_arabic = f"{booking.hotel.name} قد رفض حجزك"
                    notification = create_notification(user=booking.user.user, notification_type="booking_reject",message=message,message_arabic=message_arabic,source="hotel", related_booking=booking)
                    logger.info(f"\n\n notification obj for reject booking by vendor for user has been created -------> {notification} \n\n")
                except Exception as e:
                        logger.info(f"\n\n Exception raised in Creating notification in reject hotel booking by vendor. Exception: {e} \n\n")
                        return JsonResponse({'messgae':_('Something went wrong')})
            

                if booking.booking_email:
                    subject = "Booking Cancellation"
                    message = render_to_string(
                        "accounts/booking_cancellation_email.html", {"booking": booking}
                    )
                    superusers = User.objects.filter(is_superuser=True,is_deleted=False)
                    superuser_emails = [superuser.email for superuser in superusers]
                    recipient_list = [booking.booking_email] + superuser_emails
                    try:
                        send_mail(
                        subject,
                        "",
                        settings.EMAIL_HOST_USER,
                        recipient_list,
                        html_message=message,
                        fail_silently=False,
                    )
                    except Exception as e:
                        print(f"Failed to send cancellation email: {str(e)}")
                return JsonResponse({"success": True})
            else:
                logger.info(f"\n\nBooking is already rejected\n\n")
                return JsonResponse({"success": False,'error':_("Booking is already cancelled")}) 

        elif action == "send_reminder":
            if booking.booking_email:
                subject = "Booking Reminder"
                message = render_to_string("accounts/booking_reminder_email.html")
                send_mail(
                    subject,
                    "",
                    settings.EMAIL_HOST_USER,
                    [booking.booking_email],
                    html_message=message,
                    fail_silently=False,
                )
                return JsonResponse({"success": True})
            else:
                return JsonResponse(
                    {"success": False, "error": _("No email found for this booking")}
                )
        elif action == "check-in":
            if booking.status == "confirmed":
                trans=booking.transaction.id
                logger.info(f"transaction id : {trans}")
                try:
                    fetch_transaction =Transaction.objects.filter(id=trans).first()
                    if fetch_transaction:
                        logger.info(f"transaction found :{fetch_transaction}")
                        if fetch_transaction.payment_type.name=='Cash'and fetch_transaction.transaction_status=='pending':
                            fetch_transaction.transaction_status='completed'
                            fetch_transaction.save()
                            booking.status = "check-in"
                            booking.save()
                            logger.info("The booking status gets updated to check-in and transaction gets changed into completed")
                        else:
                            booking.status = "check-in"
                            booking.save()
                            logger.info("The booking status gets updated to check-in")
                        return JsonResponse({"success": True})
                except:
                        return JsonResponse(
                            {"success": False, "error": _("Couldn't fetch the transaction details")}
                       )
            else:
                logger.error("only confirmed bookings gets changed into check in ")
                return JsonResponse(
                    {"success": False, "error": _("only confirmed bookings gets changed into check in")}
                )
        
        elif action == "approve":
            if booking.status == "pending":
                booking.status = "booked"
                booking.save()
                booked_rooms = booking.booked_rooms.all()
                for booked_room in booked_rooms:
                    booked_room.status = "confirmed"
                    booked_room.save()

                # Create a Transaction obj
                try:
                    transaction_id = generate_transaction_id()
                    transaction = create_transaction(
                        transaction_id=transaction_id,
                        ref_id="", 
                        amount=booking.booked_price,
                        payment_type=None,
                        user=booking.user.user
                    )
                    
                    #status to 'pending' after creation
                    transaction.status = "pending"
                    transaction.save()
                    booking.transaction=transaction
                    booking.save()
                    logger.info(f"\n\n Transaction created: {transaction} \n\n")

                    #Create Hotel Booking Transaction
                    hotel_booking_transaction = create_hotel_booking_transaction(
                        booking=booking,
                        transaction=transaction,
                        user=booking.user
                    )
                    logger.info(f"\n\n Hotel Booking Transaction created: {hotel_booking_transaction} \n\n")
                    # Create Vendor Transaction after Hotel Booking Transaction
                    try:
                        base_price = booking.booked_price+booking.discount_price-(booking.meal_price+booking.tax_and_services+booking.meal_tax)
                        vendor_transaction = create_vendor_transaction(
                            transaction=transaction,
                            vendor=booking.hotel.vendor,
                            base_price=base_price,
                            total_tax=booking.tax_and_services,
                            meal_price=booking.meal_price,
                            meal_tax=booking.meal_tax,
                            discount_applied=booking.discount_price,
                            vendor_earnings=None,
                            user=booking.user
                        )
                        logger.info(f"\n\n Vendor Transaction created: {vendor_transaction} \n\n")
                    except Exception as e:
                        logger.error(f"Vendor Transaction creation failed: {e}")
                        return JsonResponse({"success": False, "error": _("Vendor Transaction creation failed")})
                except Exception as e:
                    logger.error(f"Transaction creation failed: {e}")
                    return JsonResponse({"success": False, "error": _("Transaction creation failed")})

                logger.info(f"\n\n {booking.booking_id} has been approved \n\n")
                return JsonResponse({"success": True})
            else:
                logger.info(f"\n\n Only Pending status can be approved \n\n")
                return JsonResponse({"success": False, "error": _("Only Pending status can be approved")})
        return JsonResponse({"success": False, "error": _("Invalid action")})


class UploadImagesView(View):
    def post(self, request, pk):
        booking_management = get_object_or_404(Bookedrooms, id=pk)
        room_management_obj = booking_management.room

        # Retrieve multiple images from request.FILES
        images = request.FILES.getlist("images[]")

        if images:
            roomtype_instance = room_management_obj.room_types.first()
            image_obj = RoomImage.objects.filter(
                hotel=room_management_obj.hotel, roomtype=roomtype_instance
            )
            img_len = len(images)
            for image_file in images:
                new_image = RoomImage.objects.create(
                    hotel=room_management_obj.hotel,
                    roomtype=roomtype_instance,
                    image=image_file,
                )
            return JsonResponse({"message": _("Images uploaded successfully")}, status=200)
        else:
            return JsonResponse({"error": _("No images provided")}, status=400)


class MobileappPasswordResetConfirmView(View):
    def get(self, request, id, token):
        context = {"id": id, "token": token}
        return render(request, "accounts/mobileapppasswordreset.html", context)


class RequestAmenityView(View):
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            request.session.flush()  
            return redirect('loginn')
        amenity_name = request.POST.get("amenity_name")
        purpose = request.POST.get("purpose")
        user = VendorProfile.objects.get(user=request.user)
        user_email = user.user.email
        superusers = User.objects.filter(is_superuser=True,is_deleted=False)
        superuser_emails = [superuser.email for superuser in superusers]
        email_subject = "New Amenity Request"
        email_body = render_to_string(
            "accounts/request_amentity_email.html",
            {"amenity_name": amenity_name, "purpose": purpose,"request_user":user_email},
        )
     
        try:
            print("Sending email...")
            send_mail(
                email_subject,
                "",
                settings.EMAIL_HOST_USER,
                superuser_emails,
                html_message=email_body,
            )
            print("Email sent successfully.")
        except Exception as e:
            print(f"Failed to send email: {e}")

        return JsonResponse({"success": True})

class RoomDetailView(View):
    template_name = 'accounts/room_management_view.html'

    def get(self, request, pk):
        if not request.user.is_authenticated:
            request.session.flush()  
            return redirect('loginn')
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotels = Hotel.objects.filter(vendor=user.id).select_related('vendor')
            hotel_id = request.GET.get('hotel_id')
            selected_hotel= Hotel.objects.filter(vendor=user.id).first() if not hotel_id else get_object_or_404(Hotel, id=hotel_id)
            room = RoomManagement.objects.get(id=pk, hotel=selected_hotel)
        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist, RoomManagement.DoesNotExist):
                logger.info("user/vendor doesn't found")
                return render(request,'accounts/404.html')
        print("=======================")
        room_refund_policy = None
        meal_choices = room.meals.all()
        meal_types = [meal.meal_type for meal in meal_choices]

        # Fetch the single meal tax for the room
        meal_tax = MealTax.objects.filter(room=room, status="active").first()
        meal_tax_percentage = meal_tax.percentage if meal_tax else None 

        amenities = room.amenities.filter(status=True,amenity_type="Room_amenity")
        r_amenities =[]
        
        room_amenities = Amenity.objects.filter(
            amenity_type="Room_amenity", status=True
        )
        for amenity in room_amenities:
            r_amenities.append(amenity)
        # images_to_remove = list(room.image.all().order_by('id'))[:-5]
        # for img in images_to_remove:
        #     room.image.remove(img)
        room_type_images = room.image.all().order_by('id')
        
        price = room.price_per_night
        commission_slab = CommissionSlab.objects.filter(from_amount__lte=price, to_amount__gte=price, status='active').first()
        
        if commission_slab:
            commission_amount = commission_slab.commission_amount
        else:
            commission_amount = Decimal('0.00')
        total_price = price + commission_amount
        rooms_obj = Roomtype.objects.all()
        room_type = [
                        {
                            'id': obj.id,
                            'room_type': obj.room_types
                        }
                            for obj in rooms_obj
                    ]
        refundpolicycategories = RefundPolicyCategory.objects.filter(status='active',is_deleted=False).order_by('-id')


        refund_category = RefundPolicyCategory.objects.filter(name='Refund Available',status='active',is_deleted=False).first()

        if refund_category:
            refundpolicies = RefundPolicy.objects.filter(category=refund_category,status='active',is_deleted=False)
        else:
            refundpolicies = []

        room_refund_policy = RoomRefundPolicy.objects.filter(room=room , is_deleted=False,status='active').select_related('policy').first()
        formatted_validity = None 
        refund_policy_category_name = None 
        refund_policy_name = None
        refund_policy_category_arabic = None
        refund_policy_arabic = None
        if room_refund_policy :
            refund_policy = room_refund_policy.policy
            refund_policy_name= refund_policy.title
            refund_policy_arabic=refund_policy.title_arabic
            refund_policy_category_name = refund_policy.category.name if refund_policy.category else None
            refund_policy_category_arabic=refund_policy.category.name_arabic if refund_policy.category else None
            room_refund_policy=room_refund_policy
            # logger.info(formatted_validity)
            # logger.info(f" refund policy_category:   {refund_policy_category_name}")
            # logger.info(refund_policy_name)
            if refund_policy_category_name.lower() == 'no refund':
                refund_policy_name=None
                refund_policy_arabic=None
            validity = room_refund_policy.validity
            # logger.info(validity)
            if validity:
                formatted_validity = format_validity(validity)
            # logger.info(f"validity:{formatted_validity}")
        context = {
            'room': room,
            'amenities': amenities,
            'room_amenities':r_amenities,
            'room_type_images': room_type_images,
            'commission_amount': commission_amount,
            'total_price': total_price,
            "room_type": room_type,
            "hotel":selected_hotel,
            "LANGUAGES": settings.LANGUAGES,
            'meals': [meal.meal_type for meal in MealPrice.objects.filter(hotel=selected_hotel)],
            'meal_choices':meal_types,
            'meal_tax_percentage':meal_tax_percentage,
            'refundpolicycategories': refundpolicycategories,
            'refundpolicies': refundpolicies,
            'refund_policy_category_name':refund_policy_category_name,
            'refund_policy_name':  refund_policy_name,
            'refund_policy_category_arabic':refund_policy_category_arabic,
            'refund_policy_arabic': refund_policy_arabic,
            'refund_validity':formatted_validity,
            "hotels": hotels,
            "selected_hotel":selected_hotel
        }
        return render(request, self.template_name, context)


class RoomImageUploadView(View):
    def post(self, request, *args, **kwargs):
        room_id = request.POST.get('id')
        room = get_object_or_404(RoomManagement, id=room_id)
        
        files = request.FILES.getlist('images[]')
        if not files:
            return JsonResponse({'error': _('No files provided.')}, status=400)
        
        room.roomtype_images.all().delete()
        
        errors = []
        for file in files:
            if file.size > 500 * 1024:  
                errors.append(_("'%(file_name)s' exceeds the maximum size of 500 KB.") % {'file_name': file.name})
                continue
            if file.content_type not in ['image/jpeg', 'image/png']:
                errors.append(_("'%(file_name)s' is not a valid file type.") % {'file_name': file.name})
                continue
            
            roomtype = Roomtype.objects.first()  # Replace with actual logic if necessary
            
            # Save the new image for each Roomtype
            for roomtype in room.room_types.all():
                RoomImage.objects.create(
                    room_management=room,
                    roomtype=roomtype,
                    image=file
                )
        
        if errors:
            return JsonResponse({'errors': errors}, status=400)
        
        return JsonResponse({'message': _('Files uploaded successfully.')})

@login_required
def fetch_room_data(request):
    room_id = request.GET.get('id')
    room = RoomManagement.objects.filter(id=room_id).first()
    if room:
        roomtype_ids = room.room_types.values_list('id', flat=True)
        room_types = Roomtype.objects.all().values('id', 'room_types')  # Ensure 'room_types' is correct
        data = {
            'number_of_rooms': room.number_of_rooms,
            'roomtype_id': list(roomtype_ids),
            'total_occupency': room.total_occupency,
            'price_per_night': room.price_per_night,
            'amenities': list(room.amenities.values_list('amenity_name', flat=True)),
            'room_types': list(room_types) 
        }
        return JsonResponse(data)
    else:
        return JsonResponse({'error': _('Room not found')}, status=404)



class RoomSingleImageUploadView(View):
    def post(self, request, *args, **kwargs):
        try:
            room_type_id = request.POST.get('room_type_id')
            image_id = request.POST.get('image_id')
            file = request.FILES.get('image')

            # Validate file presence
            if not file:
                logger.warning("No file provided in the request.")
                return JsonResponse({'error': _('No file provided.')}, status=400)

            # Validate file size
            if file.size > 500 * 1024:  # 500 KB
                logger.warning(f"File size exceeds the limit: {file.size} bytes.")
                return JsonResponse({'error': _('File exceeds the maximum size of 500 KB.')}, status=400)

            # Validate file type
            if file.content_type not in ['image/jpeg', 'image/png']:
                logger.warning(f"Invalid file type: {file.content_type}.")
                return JsonResponse({'error': _('Only JPEG and PNG files are allowed.')}, status=400)

           # Get the room and room image
            room_type = Roomtype.objects.get(id=room_type_id)
            try:
                room = RoomManagement.objects.get(room_types=room_type)
                room_image = RoomImage.objects.get(id=image_id)
                    
                if not room.image.filter(id=room_image.id).exists():
                    room.image.add(room_image)

                # Update the image file for RoomImage
                room_image.image = file
                room_image.save()
                logger.info(f"Image successfully uploaded for Room ID {room.id}, Image ID {image_id} and Room Type: {room_type.room_types}")
                return JsonResponse({'message': _('Image uploaded successfully.')})
            except RoomManagement.DoesNotExist:
                logger.error(f"Room type: {room_type.room_types}.")
                return JsonResponse({'error': _('Room not found.')}, status=404)
        except Roomtype.DoesNotExist:
            logger.error(f"Room type not found with ID: {room_type.room_types}.")
            return JsonResponse({'error': _('Room not found.')}, status=404)

        except RoomImage.DoesNotExist:
            logger.error(f"RoomImage not found with ID: {image_id} for Room type: {room_type.room_types}.")
            return JsonResponse({'error': _('Room type image not found.')}, status=404)

        except Exception as e:
            logger.exception(f"Unexpected error occurred: {str(e)}")
            return JsonResponse({'error': _('An unexpected error occurred.')}, status=500)

class EditHotelView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            request.session.flush()  # Clear the session
            return redirect('loginn')  
        
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotels = Hotel.objects.filter(vendor=user.id).select_related('vendor')
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first()  
            if hotel:
                if hotel.approval_status == "rejected":
                    messages.error(request, _('Hotel was rejected.'))
                    return redirect('loginn')
            else:
                return redirect('loginn')
        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
                logger.info("user/vendor doesn't found")
                return render(request,'accounts/404.html')
        context={
              "LANGUAGES": settings.LANGUAGES,
              "hotel":hotel,
                "hotels": hotels,
                "selected_hotel":hotel
        }
        return render(request, 'accounts/edit_hotel.html',context=context)


class EditHotelDetailView(View):
    def get(self, request):

        if not request.user.is_authenticated:
            request.session.flush()  # Clear the session
            return redirect('loginn')  
        
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotels = Hotel.objects.filter(vendor=user.id).select_related('vendor')
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first()  
            if hotel:
                if hotel.approval_status == "rejected":
                    messages.error(request, _('Hotel was rejected.'))
                    return redirect('loginn')
            else:
                return redirect('loginn')
        except (Userdetails.DoesNotExist, Hotel.DoesNotExist):
            logger.info("user/vendor doesn't found")
            return render(request,'accounts/404.html')
        # Fetch active taxes
        taxes = Tax.objects.filter(status="active", is_deleted=False)

        # Fetch existing HotelTax or ChaletTax records for pre-filling
        if hotel:
            existing_taxes = HotelTax.objects.filter(hotel=hotel, status="active", is_deleted=False)
            tax_percentage_map = {ht.tax_id: ht.percentage for ht in existing_taxes}
        

        # Attach existing percentages to taxes
        for tax in taxes:
            tax.percentage = tax_percentage_map.get(tax.id, None)
        meal_prices = MealPrice.objects.filter(hotel=hotel)
        meal_prices_dict = {meal_price.meal_type: meal_price.price for meal_price in meal_prices}
        images = hotel.hotel_images.all().order_by('uploaded_at')
        first_image = images.filter(is_main_image=True).first() if images.exists() else None
        remaining_images = images.exclude(id=first_image.id) if first_image else images
        amenities = hotel.amenities.filter(amenity_type="Property_amenity",status=True)
        all_amenities = Amenity.objects.filter(amenity_type="Property_amenity",status=True)
        print(amenities,"=====================")
        documents = hotel.attached_documents.all()
        hotel_rating = Hotel.HOTEL_RATING
        Payment_ctg = PaymentTypeCategory.objects.filter(status='active')

        selected_payments = HotelAcceptedPayment.objects.filter(hotel=hotel)

        selected_payment_types = PaymentType.objects.filter(
            hotel_payment_types_set__in=selected_payments  # Use the correct related name
        )

        selected_categories = selected_payment_types.values_list('category__id', flat=True).distinct()

        logger.info(f"Selected Payments: {selected_payments}")
        logger.info(f"Selected Payment Types: {selected_payment_types}")
        logger.info(f"Selected Categories: {selected_categories}")




        document_data = [
            {
                'id': doc.id,  
                'url': doc.document.url,
                'filename': os.path.basename(doc.document.name)
            }
            for doc in documents
        ]
        hotel_types=HotelType.objects.filter(status='active')

        context = {
            'hotel':hotel,
            'meal_prices': meal_prices_dict,
            "first_image": first_image,
            "remaining_images": remaining_images,
            'amenities': amenities,
            'documents': documents,
            'documents': document_data,
            'hotel_rating':hotel_rating,
            "LANGUAGES": settings.LANGUAGES,
            'all_amenities':all_amenities,
            'hotel_taxes': taxes,
            'Payment_ctg': Payment_ctg,
            'selected_categories':  selected_categories,
            'hotel_types':hotel_types,
            "hotels": hotels,
            "selected_hotel":hotel
        }

        return render(request, 'accounts/edit_hotel_detail.html',context=context)
    

    def post(self, request):
        print("Starting to save hotel details...")
        if not request.user.is_authenticated:
            request.session.flush()  
            return redirect('loginn')
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first()  
            if hotel:
                if hotel.approval_status == "rejected":
                    messages.error(request, _('Hotel was rejected.'))
                    # return redirect('loginn')
                    return JsonResponse({'success': False, 'status': 'not_approved', 'message': _('Hotel is not approved. You need to log out.')})
            else:
                return redirect('loginn')
        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
            logger.info("user/vendor doesn't exist")
            return render(request,'accounts/404.html')

        logger.info(f"\n\nHotel object retrieved: {hotel}\n\n")
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
            locality = request.POST.get('locality','')
            hotel_rating = request.POST.get('rating')
            cr_number = request.POST.get('crnumber')
            date_of_expiry= request.POST.get('expiry')
            vat_number = request.POST.get('vatnumber','')
            about_property = request.POST.get('about_property')
            hotel_policies = request.POST.get('hotel_policies')
            breakfast_price = request.POST.get('breakfast-price')
            lunch_price = request.POST.get('lunch-price')
            dinner_price = request.POST.get('dinner-price')
            selected_rating = request.POST.get('hotelrating')
            hotel_name_arabic = request.POST.get('arabic_name')
            hotel_owner_arabic = request.POST.get('hotel_owner_arabic','')
            about_property_arabic = request.POST.get('about_property_arabic','')
            hotel_policies_arabic = request.POST.get('hotel_policies_arabic','')
            logo_source = request.POST.get('logo_source')
            amenity_ids = request.POST.get('amentity_ids')
            account_no=request.POST.get('Accountno')
            account_holder_name=request.POST.get('Accountholder')
            bank=request.POST.get('BankName')
            arabic_city=request.POST.get('CityArabic')
            check_in=request.POST.get('hotel_check_in')
            check_out=request.POST.get('hotel_check_out')
            # Handle existing documents
            existing_document_ids = request.POST.getlist('existing_document_ids')
            submitted_documents = request.FILES.getlist('documents[]')

            logo_source = request.FILES.get('logo_image')
            payment_ctg=request.POST.getlist("payment_category")
            hotel_type_value=request.POST.get('hotel_type')
            if hotel.address!=hotel_address or  hotel.city.name != city or hotel.state.name != state or hotel.country.name != country:
                try:
                    lat, long = get_lat_long(
                        hotel_address,
                        city,
                        state,
                        country
                    )
                    if lat is not None and long is not None:
                        logger.info(f"Fetched coordinates: latitude={lat}, longitude={long}")
                    else:
                        logger.warning("Could not fetch valid coordinates. Received None.")
                        lat = hotel.latitude
                        long = hotel.longitude   
                except Exception as e:
                    logger.error(f"Error fetching coordinates: {str(e)}")
                    lat = hotel.latitude
                    long = hotel.longitude   
            else:
                lat = hotel.latitude
                long = hotel.longitude   

            try:
                if logo_source:
                    hotel.logo.delete()
                    hotel.logo=logo_source
                    hotel.save()


                existing_main_image = request.POST.get('existing_main_image')
                existing_image_ids = request.POST.getlist('existing_image_ids[]')

                # New image data
                new_images = {
                    'main_images': request.FILES.get('main_images'),
                }
                for i in range(1, 5): 
                    new_images[f'remaining_images_{i}'] = request.FILES.get(f'remaining_images_{i}')

                # Fetch existing images from the database
                existing_images = set(hotel.hotel_images.values_list('id', flat=True))

                # Convert to a set for comparison
                existing_image_ids = set(map(int, existing_image_ids))
                if existing_main_image:
                    existing_image_ids.add(int(existing_main_image))

                # Calculate which images need to be removed (i.e., images not in the updated form)
                removed_image_ids = existing_images - existing_image_ids

                # Delete the images that are removed from the form
                hotel.hotel_images.filter(id__in=removed_image_ids).delete()

                # Save new or replaced images
                for key, image in new_images.items():
                    if image:
                        if key == 'main_images': 
                            # Delete the old main image
                            old_main_image = HotelImage.objects.filter(hotel=hotel, is_main_image=True).first()
                            if old_main_image:
                                old_main_image.delete()

                            # Create a new main image
                            main_image = HotelImage.objects.create(hotel=hotel, image=image, is_main_image=True)
                            logger.info(f"Replaced main image: {image.name}")
                        else:
                            # Replace additional images
                            remaining_image_key = key.split('_')[-1]
                            if remaining_image_key and f'existing_image_{remaining_image_key}' in request.POST:
                                # Replace an existing image
                                image_id_to_replace = request.POST.get(f'existing_image_{remaining_image_key}')
                                HotelImage.objects.filter(id=image_id_to_replace).delete()  # Delete the old image
                                logger.info(f"Replaced additional image: {image.name}")

                        
                            # Save the new image
                            HotelImage.objects.create(hotel=hotel, image=image)
                            logger.info(f"Saved new image: {image.name}")
                        
                existing_document_ids = request.POST.getlist('existing_document_ids')
                submitted_documents = request.FILES.getlist('documents[]')
                if submitted_documents:
                    for document in hotel.attached_documents.all():
                        if str(document.id) not in existing_document_ids:
                            document.delete()
                            logger.info(f"Deleted document with ID: {document.id}")



                    for uploaded_document in submitted_documents:
                        HotelDocument.objects.create(hotel=hotel, document=uploaded_document)
                        logger.info(f"Saved new document: {uploaded_document.name}")

                if amenity_ids:
                    amenities_ids = json.loads(amenity_ids)
                    hotel.amenities.clear()  
                    for amenity_id in amenities_ids:
                        amenity = get_object_or_404(Amenity, id=amenity_id)
                        amenity.amenity_type = 'Property_amenity'
                        amenity.status = True
                        amenity.save()
                        hotel.amenities.add(amenity)
                    logger.info("Updated hotel amenities")

            except Exception as e:
                logger.error(f"Error: {e}")
            try:
                # Extract and process taxes
                for tax in Tax.objects.all():
                    tax_percentage = request.POST.get(f'tax_percentage_{tax.id}')
                    if tax_percentage is not None:
                        tax_percentage = Decimal(tax_percentage)
                        if tax_percentage < 0 or tax_percentage > 100:
                            print(f'Invalid percentage for {tax.name}.')
                            continue  # Skip processing this tax

                        # Create or update HotelTax record
                        hotel_tax, created = HotelTax.objects.update_or_create(
                            hotel=hotel, tax=tax,
                            defaults={
                                'percentage': tax_percentage,
                                'status': 'active',
                                'created_by': user,
                                'modified_by': user
                            }
                        )

                print('Hotel taxes saved successfully.')
            except Exception as e:
                logger.error(f"Error: {e}")
            try:
                country, created = Country.objects.get_or_create(name=country)
                state, created = State.objects.get_or_create(
                    country=country, name=state
                )
               
                city, created = City.objects.get_or_create(
                    state=state, name=city, arabic_name= arabic_city
                )
                logger.info(f"city ----{city}")
            except Exception as e:
                logger.error(f"Location data error: {e}")    

            # Check if email already exists in the database, excluding the current user
            if VendorProfile.objects.filter(user__email__exact=hotel_email).exclude(user__id=request.user.id).exists():
                logger.info(f"\n\nEmail already exists\n\n")
                return JsonResponse({'success': False, 'message': _('Email already exists')}, status=400)
          
            vendor = hotel.vendor
            
            if vendor:
                Userdetails_obj = vendor
                Userdetails_obj.gsm_number = gsm_number
                Userdetails_obj.save()

                if Userdetails_obj.user:
                    # Userdetails_obj.user.first_name = hotel_owner
                    Userdetails_obj.user.email= hotel_email
                    Userdetails_obj.user.save()  

            else:
                logger.warning("No Userdetails associated with this hotel.")

            def parse_price(price_str):
                if price_str and price_str.strip().lower() != 'n/a':
                    try:
                        normalized_price_str = price_str.replace(',', '.')
                        return Decimal(normalized_price_str)
                    except (ValueError, InvalidOperation) as e:
                        logger.error(f"Error parsing price: '{price_str}' - Exception: {e}")
                        return None
                return None


             # Create a set of meal types that will be retained
            meal_types_to_keep = {'no meals'}


            # Save meal prices
            try:
                # Update or create breakfast price if provided
                if breakfast_price:
                    normalized_price= parse_price(breakfast_price)
                    if normalized_price > 0:
                        MealPrice.objects.update_or_create(
                            hotel=hotel,
                            meal_type='breakfast',
                            defaults={'price':normalized_price}
                        )
                        meal_types_to_keep.add('breakfast')

                # Update or create lunch price if provided
                if lunch_price :
                    normalized_price= parse_price(lunch_price)
                    if normalized_price>0:
                        MealPrice.objects.update_or_create(
                            hotel=hotel,
                            meal_type='lunch',
                            defaults={'price':normalized_price}
                        )
                        meal_types_to_keep.add('lunch')

                # Only update/create dinner price if it's provided
                if dinner_price: 
                    normalized_price= parse_price(dinner_price)
                    MealPrice.objects.update_or_create(
                        hotel=hotel,
                        meal_type='dinner',
                        defaults={'price':normalized_price}
                    )
                    meal_types_to_keep.add('dinner')
                # Delete all meal prices except those being updated
                MealPrice.objects.filter(hotel=hotel).exclude(meal_type__in=meal_types_to_keep).delete()

            except Exception as e:
                logger.error(f"Meal price update error: {e}")
            if payment_ctg:
                try:
                    hotel_payment_accepted, created = HotelAcceptedPayment.objects.get_or_create(
                        hotel=hotel,
                        defaults={
                            "created_by": user,  # Set the user who creates it
                            "modified_by": user,  # Assuming `user` is the current logged-in user
                            "status": "active",
                        }
                    )

                    wallet_payment_types = PaymentType.objects.filter(category__name__iexact="Wallet")

                    if "All" in payment_ctg:
                        selected_payment_types = PaymentType.objects.filter(status="active")
                    else:
                        selected_payment_types = PaymentType.objects.filter(category_id__in=payment_ctg)

                    final_payment_types = set(selected_payment_types) | set(wallet_payment_types)

                    hotel_payment_accepted.payment_types.set(final_payment_types)
                    hotel_payment_accepted.save()
                    logger.info("Hotel accepted payments saved successfully")
                except Exception as e:
                    logger.error(f"An exception occurred while updating Hotel accepted payments: {e}")
            if hotel_type_value:
                hotel_type=None
                logger.info(hotel_type_value)
                try:
                    hotel_type=HotelType.objects.get(id=hotel_type_value)
                except Exception as e:
                    logger.error(f"Exception ocuured at hotel type fetch portion : {str(e)} ")
            try:
                Hotel_owner = OwnerName.objects.filter(
                    owner_name=request.POST.get('hotel_owner'),
                    owner_name_arabic=hotel_owner_arabic
                ).first()

                if not Hotel_owner:
                    Hotel_owner = OwnerName.objects.create(
                        owner_name=request.POST.get('hotel_owner'),
                        owner_name_arabic=hotel_owner_arabic
                    )
            except Exception as e:
                logger.error(f"Exception occurred at hotel owner name fetch portion: {str(e)}")
                Hotel_owner = None 



            hotel.name = hotel_name
            hotel.office_number = office_number
            hotel.address = hotel_address
            hotel.locality = locality
            hotel.hotel_rating = hotel_rating
            hotel.cr_number = cr_number
            hotel.vat_number = vat_number
            hotel.about_property = about_property
            hotel.hotel_policies = hotel_policies
            hotel.state=state
            hotel.city=city
            hotel.date_of_expiry= date_of_expiry
            hotel.hotel_rating= selected_rating
            hotel.about_property_arabic=about_property_arabic
            hotel.hotel_policies_arabic=hotel_policies_arabic
            hotel.name_arabic=hotel_name_arabic
            hotel.owner_name=Hotel_owner
            hotel.owner_name_arabic = hotel_owner_arabic
            hotel.bank=bank
            hotel.account_holder_name=account_holder_name
            hotel.account_no=account_no
            hotel.hotel_type=hotel_type
            hotel.checkin_time=check_in
            hotel.checkout_time= check_out
            hotel.latitude=lat
            hotel.longitude=long
            hotel.save()

            try:
                # Prepare email content
                subject = "Hotel Details Updated"
                message = f"Hotel details for '{hotel.name}' have been successfully updated."
                from_email = settings.EMAIL_HOST_USER
                
                superusers = User.objects.filter(is_superuser=True,is_deleted=False)
                superuser_emails = [superuser.email for superuser in superusers]
                
                send_mail(
                    subject,
                    message,
                    from_email,
                    [hotel_email] + superuser_emails,
                    fail_silently=False,
                )

                logger.info("Hotel details saved successfully.")
            except Exception as e:
                logger.info(f"\n\nIssue in mail sending in edit hotel. Exception: {e}\n\n")
            return JsonResponse({'success': True,'message': _('Hotel details saved successfully.')},status=200)


        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return JsonResponse({'error': str(e)}, status=500)

class EditHotelPolicyView(View):
    def get(self, request):
        logger.info("Accessing EditHotelPolicyView.")
        if not request.user.is_authenticated:
            logger.warning("Unauthenticated user attempted to access EditHotelPolicyView.")
            request.session.flush()
            return redirect('loginn')
        
        try:
            logger.info(f"Retrieving VendorProfile for user: {request.user}")
            user = VendorProfile.objects.get(user=request.user)
            hotels = Hotel.objects.filter(vendor=user.id).select_related('vendor')
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel= Hotel.objects.filter(vendor=user.id).first()  
            if hotel:
                logger.info(f"Hotel found for vendor {user.id}: {hotel.name}")
                if hotel.approval_status == "rejected":
                    logger.warning(f"Hotel {hotel.id} was rejected. Redirecting to login.")
                    messages.error(request, _('Hotel was rejected.'))
                    return redirect('loginn')
            else:
                logger.error(f"No hotels found for vendor {user.id}. Redirecting to login.")
                return redirect('loginn')

        except VendorProfile.DoesNotExist:
            logger.error(f"VendorProfile not found for user: {request.user}. Rendering 404.")
            return render(request, 'accounts/404.html')

        except Hotel.DoesNotExist:
            logger.error(f"No Hotel found for VendorProfile of user: {request.user}. Rendering 404.")
            return render(request, 'accounts/404.html')

        except Exception as e:
            logger.exception(f"Unexpected error occurred in EditHotelPolicyView.get: {str(e)}")
            return render(request, 'accounts/404.html')

        try:
            logger.info(f"Retrieving vendor-specific policies for hotel {hotel.id}.")
            vendor_policies = PolicyCategory.objects.filter(hotel=hotel)
            if vendor_policies.exists():
                logger.info(f"Retrieved {vendor_policies.count()} vendor policies for hotel {hotel.id}")
            else:
                logger.info(f"No vendor-specific policies found for hotel {hotel.id}.")

        except Exception as e:
            logger.error(f"Error retrieving vendor policies for hotel {hotel.id}. Exception: {e}", exc_info=True)
            vendor_policies = []

        try:
            logger.info("Retrieving common policies.")
            common_policies = PolicyCategory.objects.filter(policy_type='common')
            if common_policies.exists():
                logger.info(f"Retrieved {common_policies.count()} common policies.")
            else:
                logger.info("No common policies found.")

        except Exception as e:
            logger.error(f"Error retrieving common policies. Exception: {e}", exc_info=True)
            common_policies = []

        try:
            logger.info(f"Retrieving selected policy names for hotel {hotel.id}.")
            selected_policy_names = hotel.policies_name.all()
            logger.info(f"Retrieved {selected_policy_names.count()} selected policy names.")
        except Exception as e:
            logger.error(f"Error retrieving selected policy names for hotel {hotel.id}. Exception: {e}", exc_info=True)
            selected_policy_names = []

        # Combine common policies and vendor policies for dropdown
        combined_policies = list(common_policies) + list(vendor_policies)
        unique_policies = {policy.name: policy for policy in combined_policies}.values()

        context = {
            'hotel': hotel,
            'policies': vendor_policies,
            'common_policies': unique_policies,
            'selected_policy_names': selected_policy_names,
            'LANGUAGES': settings.LANGUAGES,
            "hotels": hotels,
            "selected_hotel":hotel
        }

        logger.info(f"Rendering EditHotelPolicyView for hotel {hotel.id}.")
        return render(request, 'accounts/edit_hotel_policy.html', context=context)

class PolicyDataView(View):
    def get(self, request, category_id):
        try:
            if not request.user.is_authenticated:
                logger.warning("Unauthenticated access attempt.")
                request.session.flush()
                return redirect('loginn')

            try:
                category = PolicyCategory.objects.get(id=category_id)
                logger.info(f"Policy category '{category.name}' retrieved successfully.")
            except PolicyCategory.DoesNotExist:
                logger.error(f"Policy category with ID {category_id} does not exist.")
                return JsonResponse({'status': 'error', 'message': _('Policy category not found')}, status=404)

            try:
                user = VendorProfile.objects.get(user=request.user)
                logger.info(f"Vendor profile for user {request.user.id} retrieved successfully.")
            except VendorProfile.DoesNotExist:
                logger.error(f"Vendor profile not found for user {request.user.id}.")
                return JsonResponse({'status': 'error', 'message': _('Vendor profile not found')}, status=404)

            try:
                hotel_id = request.GET.get('hotel_id')
                logger.info(f"requested hotel_id is --{hotel_id}")
                if hotel_id:
                    hotel = get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
                else:
                    hotel = Hotel.objects.filter(vendor=user.id).first()
                logger.info(f"Hotel '{hotel.name}' (ID: {hotel.id}) retrieved successfully.")
            except Hotel.DoesNotExist:
                logger.error(f"Hotel does not exist for vendor {user.id}.")
                return JsonResponse({'status': 'error', 'message': _('Hotel not found')}, status=404)

            selected_policy_names = hotel.policies_name.filter(
                policy_category=category, is_deleted=False
            ).values('id', 'title')

            data = {
                'category_name': category.name,
                'selected_policies': list(selected_policy_names),
            }
            logger.info(f"Policy data for category '{category.name}' retrieved successfully for hotel '{hotel.name}'.")
            return JsonResponse({'status': 'success', 'data': data}, status=200)

        except Exception as e:
            logger.error(f"An unexpected error occurred in PolicyDataView get function. Exception: {str(e)}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': _('An unexpected error occurred')}, status=500)

@login_required
def save_policy(request):
    if request.method == 'POST':
        category = request.POST.get('category')
        policies = request.POST.getlist('policies[]')
        try:
            # Retrieve vendor profile and hotel
            user = VendorProfile.objects.get(user=request.user)
            hotel_id = request.GET.get('hotel_id')
            logger.info(f"requested hotel_id is --{hotel_id}")
            if hotel_id:
                hotel = get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel = Hotel.objects.filter(vendor=user.id).first()            
            if not hotel:
                logger.error(f"No hotel found for vendor {user.id}.")
                return JsonResponse({'status': 'error', 'message': _('Hotel not found.')}, status=404)

            if hotel.approval_status == "rejected":
                logger.warning(f"Hotel {hotel.id} was rejected.")
                messages.error(request, _('Hotel was rejected.'))
                return redirect('loginn')

            logger.info(f"Hotel found for vendor {user.id}: {hotel.name}")

        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist) as e:
            logger.error(f"Error retrieving vendor/user or hotel: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': _('Vendor or hotel not found.')}, status=404)

        # Scenario 1: Check if the category exists as a common category
        try:
            existing_category = PolicyCategory.objects.get(name=category, policy_type='common')
            logger.info(f"Policy category '{category}' exists as a common category.")
            hotel.policies.add(existing_category)
            hotel.save()

            for policy in policies:
                if policy:
                    logger.info(f"Creating policy name '{policy}' under common category '{existing_category.name}'.")
                    policy_name, created = PolicyName.objects.get_or_create(
                        policy_category=existing_category, 
                        title=policy, 
                        created_by=request.user
                    )
                    if created:
                        logger.info(f"Policy name '{policy}' created successfully.")
                        message = _("Successfully added new policy to %(category)s.") % {'category': category}
                        status = "success"
                    if not hotel.policies_name.filter(id=policy_name.id).exists():
                        hotel.policies_name.add(policy_name)
                        message = _("Successfully added policy to %(category)s.") % {'category': category}
                        status = "success"
                    else:
                        message = _("Policy already exists in this category.")
                        status = "error"

            hotel.save()
            return JsonResponse({'status': status, 'message': message}, status=200)

        except PolicyCategory.DoesNotExist:
            pass

        # Scenario 2: Check if the category exists for the vendor
        try:
            existing_vendor_category = PolicyCategory.objects.get(name=category, created_by=request.user)
            logger.info(f"Policy category '{category}' already exists for vendor {request.user.id}.")
            hotel.policies.add(existing_vendor_category)
            hotel.save()

            for policy in policies:
                if policy:
                    logger.info(f"Creating policy name '{policy}' under vendor category '{existing_vendor_category.name}'.")
                    policy_name, created = PolicyName.objects.get_or_create(
                        policy_category=existing_vendor_category, 
                        title=policy, 
                        created_by=request.user
                    )
                    if created:
                        logger.info(f"Policy name '{policy}' created successfully.")
                        message = _("Successfully added new policy to %(category)s.") % {'category': category}
                        status = "success"
                    if not hotel.policies_name.filter(id=policy_name.id).exists():
                        hotel.policies_name.add(policy_name)
                        message = _("Successfully added policy to %(category)s.") % {'category': category}
                        status = "success"
                    else:
                        message = _("Policy already exists in this category.")
                        status = "error"

            hotel.save()
            return JsonResponse({'status': status, 'message': message}, status=200)

        except PolicyCategory.DoesNotExist:
            # Scenario 3: Create a new vendor-specific category if it doesn't exist
            logger.info(f"Policy category '{category}' does not exist. Creating a new vendor-specific policy category.")
            new_category = PolicyCategory.objects.create(
                name=category, 
                created_by=request.user,
                policy_type='vendor'
            )
            hotel.policies.add(new_category)
            hotel.save()

        # Scenario 4: Create the policy category and related policy names directly
        for policy in policies:
            if policy:
                logger.info(f"Creating policy name '{policy}' under category '{new_category.name}'.")
                policy_name, created = PolicyName.objects.get_or_create(
                    policy_category=new_category, 
                    title=policy, 
                    created_by=request.user
                )
                if created:
                    logger.info(f"Policy name '{policy}' created successfully.")
                if not hotel.policies_name.filter(id=policy_name.id).exists():
                    hotel.policies_name.add(policy_name)

        hotel.save()
        logger.info(f"Successfully added policies to hotel {hotel.id}.")
        return JsonResponse({'status': 'success', 'message': _('Policies Created Successfully')}, status=200)

    logger.error("Invalid request method for save_policy.")
    return JsonResponse({'status': 'error', 'message': _('Invalid request method')}, status=400)

@login_required
def edit_amenity_to_hotel(request):
    if request.method == "POST":
        try:
            hotel_id = request.POST.get("hotel_id")
            selected_amenities = request.POST.getlist("selected_amenities[]")
            
            logger.info(f"hotel_id: {hotel_id}, selected_amenities: {selected_amenities}")

            if not hotel_id or not selected_amenities:
                logger.warning(
                    f"Missing required fields. hotel_id: {hotel_id}, selected_amenities: {selected_amenities}"
                )
                return JsonResponse({"error": "At least one amenity must be selected."}, status=400)

            try:
                amenity_ids = [int(amenity_id) for amenity_id in selected_amenities]
            except ValueError as e:
                logger.error(f"Invalid amenity ID in selected_amenities: {selected_amenities}. Error: {e}")
                return JsonResponse({"error": _("Invalid amenity IDs. IDs must be integers.")}, status=400)

            hotel = get_object_or_404(Hotel, id=hotel_id)

            for amenity_id in amenity_ids:
                try:
                    amenity = get_object_or_404(Amenity, id=amenity_id, amenity_type="Property_amenity")
                    if not hotel.amenities.filter(id=amenity.id).exists():
                        hotel.amenities.add(amenity)
                except Exception as e:
                    logger.error(f"Error adding amenity with ID {amenity_id} to hotel: {e}", exc_info=True)
                    return JsonResponse({"error": _("An error occurred while adding amenity.")}, status=500)

            logger.info(f"Amenities added to hotel. Hotel ID: {hotel.id}")

            return JsonResponse({"success": _("Amenities added successfully")}, status=200)

        except Exception as e:
            logger.error(f"Unexpected error in edit_amenity_to_hotel: {e}", exc_info=True)
            return JsonResponse({"error": _("An unexpected error occurred. Please try again later.")}, status=500)

    return JsonResponse({"error": _("Invalid request")}, status=400)

@login_required
def update_policy_data(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        category_name = data.get('category_name')
        policies = data.get('policies', [])
        category_id = data.get('category_id')
        logger.info(f"Received data: {data}")

        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel_id = request.GET.get('hotel_id')
            logger.info(f"requested hotel_id is --{hotel_id}")
            if hotel_id:
                hotel = get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel = Hotel.objects.filter(vendor=user.id).first()

            if hotel.approval_status == "rejected":
                logger.warning(f"Hotel with ID {hotel.id} was rejected.")
                return JsonResponse({'status': 'error', 'message': _('Hotel was rejected.')}, status=403)
        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
            logger.error("Vendor or hotel not found.")
            return JsonResponse({'status': 'error', 'message': _('Vendor or hotel not found.')}, status=404)

        category = get_object_or_404(PolicyCategory, id=category_id)
        logger.info(f"Category found: {category}")

        if category_name:
            category.policy_category = category_name
            category.save()
            logger.info(f"Category name updated to: {category_name}")

        existing_policies = hotel.policies_name.filter(policy_category=category)
        logger.info(f"Existing policies: {list(existing_policies)}")

        # Remove policies that are no longer in the frontend list (only from the current category)
        for policy in existing_policies:
            if not any(policy.title == p.get('value') and policy.id == int(p.get('id')) for p in policies):
                hotel.policies_name.remove(policy)
                logger.info(f"Removed policy: {policy.title} (ID: {policy.id})")

        duplicate_name = ""
        duplicate_found = False

        # Add or update policies based on the frontend list (only for the current category)
        for policy_data in policies:
            if policy_data:
                policy_instance = None

                if policy_data.get('id'):
                    try:
                        policy_instance = PolicyName.objects.get(
                            id=policy_data.get('id'),
                            created_by=request.user
                        )

                        existing_policy = PolicyName.objects.filter(
                            policy_category=category,
                            title=policy_data.get('value'),
                            created_by=request.user
                        ).exclude(id=policy_data.get('id')).first()

                        if existing_policy:
                            duplicate_name = policy_data.get('value')
                            duplicate_found = True
                            logger.warning(f"Duplicate policy found during update: {duplicate_name}")
                            break

                        policy_instance.title = policy_data.get('value')
                        policy_instance.save()
                        hotel.policies_name.add(policy_instance)
                        logger.info(f"Updated policy: {policy_instance}")

                    except PolicyName.DoesNotExist:
                        logger.warning(f"Policy not found with ID: {policy_data.get('id')}")
                        continue

                else:
                    policy_instance = PolicyName.objects.filter(
                        policy_category=category,
                        title=policy_data.get('value'),
                        created_by=request.user
                    ).first()

                    if policy_instance:
                        if hotel.policies_name.filter(
                            policy_category=category,
                            title=policy_data.get('value'),
                            created_by=request.user
                        ).exists():
                            duplicate_name = policy_data.get('value')
                            duplicate_found = True
                            logger.warning(f"Duplicate policy found during creation: {duplicate_name}")
                            break
                        else:
                            hotel.policies_name.add(policy_instance)
                            logger.info(f"Added existing policy: {policy_instance}")
                    else:
                        policy_instance = PolicyName.objects.create(
                            policy_category=category,
                            title=policy_data.get('value'),
                            created_by=request.user
                        )
                        hotel.policies_name.add(policy_instance)
                        logger.info(f"Created and added new policy: {policy_instance}")

            hotel.save()

        if duplicate_found:
            logger.error(f"Duplicate policy detected: {duplicate_name}")
            return JsonResponse({'status': 'error', 'message': _('Policy already exists for this category.')})

        return JsonResponse({'status': 'success', 'message': _('Policies updated successfully.')})

    except Exception as e:
        logger.exception(f"Unexpected error occurred while calling update_policy_data function. Exception: {str(e)}")
        return JsonResponse({'status': 'error', 'message': _('An unexpected error occurred.')}, status=500)

@login_required
def unread_notifications(request):
    if request.method == "POST":
        # Mark notifications as read when clicked
        notification_id = request.POST.get("notification_id")
        if notification_id:
            try:
                notification = Notification.objects.get(id=notification_id, recipient=request.user)
                notification.is_read = True
                notification.save()
                return JsonResponse({"status": "success", "message": _("Notification marked as read")})
            except Notification.DoesNotExist:
                return JsonResponse({"status": "error", "message": _("Notification not found")}, status=404)
    else:
        # Fetch unread notifications for the logged-in user
        notifications = Notification.objects.filter(recipient=request.user, is_read=False).order_by('created_at')
        try:
            notifications_data = [{
                "id": notification.id,
                "message": notification.message,
                "timestamp": notification.created_at,
                "notification_type":notification.notification_type,
                "source":notification.source,
                "hotel_booking":notification.related_booking.id if notification.related_booking is not None else None,
                "chalet_booking":notification.chalet_booking.id if notification.chalet_booking is not None else None
            } for notification in notifications]
            # print(f"\n\n\n\n\n\n\n\n\n\n\n{notifications_data}====================================\n\n\n\n\n\n\n\n\n\n\n\n\n\n")
            return JsonResponse(notifications_data, safe=False)
        except Exception as e:
            print(f"\n\n\n\n\n\n\n\n\n {e} \n\n\n\n\n\n\n\n\n\n")
    
    
class DeletePolicyView(LoginRequiredMixin,View):
    login_url = 'loginn' 
    redirect_field_name = 'next'
    def post(self, request,policycategoryID):
        print(request.user.is_authenticated)
        category = PolicyName.objects.filter(policy_category_id=policycategoryID)
        if request.user.is_authenticated:
            print("===================")
            try:
                user = VendorProfile.objects.get(user=request.user)
                print(user, "===========", user.id)
                hotel_id = request.GET.get('hotel_id')
                if hotel_id:
                    get_hotl= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
                else:
                    get_hotl=Hotel.objects.filter(vendor=user.id).first()
                
                if get_hotl.approval_status == "rejected":
                    messages.error(request, _('Hotel was rejected.'))
                    return redirect('loginn')

                if get_hotl:
                    for policy in category:
                        get_hotl.policies_name.remove(policy)
                    get_hotl.policies.remove(policycategoryID)
                    return JsonResponse({'message':_('PolicyCategory has been delete successfully'),'status':True})
            except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
                return render(request,'accounts/404.html')
        

def verify_booking(request, token):
    try:
        # Try to retrieve the booking with the matching token
        booking = get_object_or_404(Booking, token=token)
    except Http404:
        # If the booking is not found, return a 404 response
        return HttpResponse(_("Booking not found."), status=404)

    # Check if the checkout date has passed
    if booking.checkout_date and booking.checkout_date < now().date():
        # Return an HTTP response indicating the booking has expired
        return HttpResponse(_("The booking's checkout date has already passed."), status=400)

    # Define the actual booking URL
    actual_url = f"{settings.DOMAIN_NAME}/vendor/booking/{booking.id}/"

    # Redirect to the actual booking URL
    return redirect(actual_url)

def error_404_view(request,exception):
    data={
        'message':_('The page you are looking for is not found!'),
        'code':404
    }
    return render(request,"accounts/errors.html",{'error':data},status=404)

def error_500_view(request):
    data={
        'message':_('Internal Server Error'),
        'code':500
    }
    return render(request,"accounts/errors.html",{'error':data},status=500)

def error_403_view(request,exception):
    data={
        'message':_('access to the requested resource is forbidden'),
        'code':403
    }
    return render(request,"accounts/errors.html",{'error':data},status=403)

def error_400_view(request,exception):
    data={
        'message':_('server was unable to process a request due to a client error'),
        'code':400
    }
    return render(request,"accounts/errors.html",{'error':data},status=400)


class RoomTypeManagement(View):
    def get(self, request):
        try:
            get_roomtypes = Roomtype.objects.all()
            roomtypes_list = [{'id': roomtype.id, 'room_type': roomtype.room_types} for roomtype in get_roomtypes]
            return JsonResponse({'roomtypes': roomtypes_list}, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    def post(self, request, *args, **kwargs):
        try:
            # Parse the JSON data from the request body
            data = json.loads(request.body)
            print(data, "=============================")
            
            # Get the room_type from the data
            room_type = data.get('item')
            
            # Create a new Roomtype instance and save to the database
            create_roomtype = Roomtype.objects.create(room_types=room_type)
            
            # Prepare the response data with id and room_type
            response_data = {'success': True, 'id': create_roomtype.id, 'room_type': create_roomtype.room_types}
            
            return JsonResponse(response_data, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
        
# class RoomTypeDetail(View):
#     def put(self, request, pk):
#         try:
#             data = json.loads(request.body)
#             updated_name = data.get('room_type', '').strip()
#             get_roomtype = Roomtype.objects.get(id=pk)
#             get_roomtype.room_types = updated_name
#             get_roomtype.save()
#             response_data = {'success': True, 'id': get_roomtype.id, 'room_type': get_roomtype.room_types}
#             return JsonResponse(response_data, status=200)
#         except Roomtype.DoesNotExist:
#             return JsonResponse({'error': 'RoomType not found'}, status=404)
        
# class GetRoom(View):
#     def get(self, request,pk):
#         try:
#             print(pk,"=======================================pkpkpkpkpkpkpkpkpk")
#             get_room = RoomManagement.objects.get(id=pk)
#             get_roomtypes = Roomtype.objects.filter(roommanagement = get_room)
#             roomtypes_list = [{'id': roomtype.id, 'room_type': roomtype.room_types} for roomtype in get_roomtypes]
#             return JsonResponse({'roomtypes': roomtypes_list}, status=200)
#         except Exception as e:
#             return JsonResponse({'error': str(e)}, status=400)



import pandas as pd
import io
from xlsxwriter.utility import xl_rowcol_to_cell
class HotelTransactionExcelDownloadView(View):
    def get(self, request):
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        payment_method = request.GET.get('payment_method')
        transaction_status = request.GET.get('transaction_status')
        booking_status = request.GET.get('booking_status')
        

        if request.session:
            try:
                lang=request.session["django_language"]
            except Exception as e:
                lang='en'
        else:
            lang='en'
        logger.info(f"requested language session is {lang}")
        
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                hotel = get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                hotel = Hotel.objects.filter(vendor=user.id).first()            
            transactions = Booking.objects.filter(hotel=hotel.id,).select_related('transaction').prefetch_related('transaction__vendor_transaction','transaction__admin_transaction').order_by('-modified_date')
            transactions = transaction_list_filter(transactions = transactions, from_date = from_date,  to_date = to_date, payment_method = payment_method, transaction_status=transaction_status, booking_status=booking_status)
            user = "hotel"
            try:
                data_frame = report_data_frame(transactions,user,lang)
            except Exception as e:
                print(f"\n\n\n\n\n\n\n{e}\n\n\n\n\n\n\n\n\n")
            try:
                if data_frame:
                    logger.info(f"data frame found: {data_frame}")
                    df = pd.DataFrame(data_frame)
                    # Set index to start from 1
                    df.index = df.index + 1  
                    df.reset_index(inplace=True) 
                    if lang=='en':
                        df.rename(columns={'index': 'S.No'}, inplace=True)
                    else:
                        df.rename(columns={'index': 'س.لا'}, inplace=True)                
                    logger.info((df.columns))
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
                        merge_range = f'A1:Y2'
                        filters = []
                        for key, value in request.GET.items():
                            if value.strip():
                                formatted_key = key.replace('_', ' ').title()
                                formatted_value = value.strip().title()
                                filters.append(f"{formatted_key}: {formatted_value}")
                        # Generate the heading dynamically
                        logger.info("before filter")
                        logger.info(df.columns)
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
                        logger.info(enumerate(list(df.columns)))
                        for col_num, column_name in enumerate(df.columns):
                            worksheet.write(2, col_num, column_name, header_format)
                        # Write the data with border format
                        for row_num, row_data in enumerate(df.values, start=3):  # Start from row 3
                            for col_num, cell_value in enumerate(row_data):
                                worksheet.write(row_num, col_num, cell_value, cell_format)
                        
                        for i, col in enumerate(df.columns):
                            df[col] = df[col].astype(str).fillna("")
                            max_length = max(df[col].astype(str).map(len).max(), len(col)) + 2 
                            worksheet.set_column(i, i, max_length)
                else:
                    logger.info(f"Inside else no data found")
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
                        merge_range = f'A1:Y2'
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
                        print(df)
                        print(df.values)
                        for value in df.values:
                            worksheet.merge_range('A3:S4', value[0], toper_formate)

                output.seek(0)
                response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = 'attachment; filename=transactions.xlsx'

                return response
            except Exception as e:
                 logger.error(f"Exception raised in the inside. Exception: {e}")

        except Exception as e:
            logger.error(f"Exception raised in VendorTransactionExcelDownload View. Exception: {e}")
            
class RetriveRoomtypeDetails(View):
    def get(self, request):
        if not request.user.is_authenticated:
            request.session.flush()
            return redirect('loginn') 
        room_type_id = request.GET.get("room_type")
        lang_code = request.GET.get("langCode")
        logger.info(room_type_id)
        logger.info(lang_code)
        try:
            user = VendorProfile.objects.get(user=request.user)
            hotel_id = request.GET.get('hotel_id')
            if hotel_id:
                selected_hotel= get_object_or_404(Hotel, id=hotel_id, vendor=user.id)
            else:
                selected_hotel= Hotel.objects.filter(vendor=user.id).first()  
            try:
                get_room_type_obj = Roomtype.objects.get(id=room_type_id)
                if get_room_type_obj:
                    try:
                        roomobj = RoomManagement.objects.get(hotel= selected_hotel,room_types=get_room_type_obj,status="active")
                        if roomobj:
                            if lang_code == 'en':
                                return JsonResponse({"status":True,"message":"You've already added a room with this room type. Please choose a different room type to create a new room."})
                            else:
                                return JsonResponse({"status":True,"message":"لقد أضفتَ غرفةً بهذا النوع من الغرف. يُرجى اختيار نوع غرفة آخر لإنشاء غرفة جديدة."})

                    except RoomManagement.DoesNotExist:
                        print(f"Roommanagement with roomtype {get_room_type_obj.room_types} doesnt exists")
                        return JsonResponse({"status":False,"message":"No room types found. Please add one"})
            except Roomtype.DoesNotExist:
                print(f"Doesnt exists")
        
        except (VendorProfile.DoesNotExist, Hotel.DoesNotExist):
                # logger.info("user/vendor doesn't found")
                return render(request,'accounts/404.html')
class AddHotels(View):
    def get(self, request):
        user=request.user
        try:
            user_details = get_object_or_404(VendorProfile, user=request.user)
        except:
            return redirect('loginn')
        hotel = Hotel.objects.filter(vendor=user_details).first()
        try:
            hotel_id = request.GET.get('hotel_id')
            selected_hotel= Hotel.objects.filter(vendor=user.id).first() if not hotel_id else get_object_or_404(Hotel, id=hotel_id)
        except:
            return redirect('loginn')
        user_language = request.LANGUAGE_CODE
        activate(user_language)
        hotel_rating = Hotel.HOTEL_RATING
        hotel_types=HotelType.objects.filter(status='active')

        return render(
            request,
            template_name="accounts/add_hotel.html",
            context={
                "hotel_rating": hotel_rating,
                "GOOGLE_MAPS_API_KEY":settings.GOOGLE_MAPS_API_KEY,
                "hotel_types":  hotel_types,
                "selected_hotel":selected_hotel,
                'pre_filled_fields': {
                'hotelOwnerName': request.user.first_name,
                'hotelOwnerEmail': request.user.email,
                'owner_name_arabic': hotel.owner_name_arabic if hotel else '',
                
                # Add other fields that should be pre-filled
            }
            },
        )
    def post(self, request):
        try:
            logger.info("Received POST request for Hotel owner registration.")
            form_data = {key: request.POST.get(key) for key in [
                "hotelOwnerName", "officenumber", "hotelName", "hotelAddress",
                "country", "city", "stateProvince", "roomnumber", "hotelrating",
                "crnumber", "vatnumber", "expiry", "logo_image", "locality",
                "buildingnumber", "About", "polices", "hotelNameArabic",
                "hotelOwnerNameArabic", "about_arabic",
                "polices_arabic", "Accountno", "BankName","Accountholder","hotel_type","hotel_is"
            ]}
            hotel_images = request.FILES.getlist("hotel_images[]")
            supporting_documents = request.FILES.getlist("supportingDocuments[]")

           
            errors = {}
            try:
                errors = self.validate_form(form_data)
                logger.info(errors)
            except Exception as e:
                logger.error(f"Error validating form data: {e}")
                errors["form_validation"] = _("An error occurred while validating the form.")

            if not hotel_images:
                errors["hotel_images"] = _("Hotel image is required.")
            if not supporting_documents:
                errors["supporting_documents"] = _("Supporting document is required.")
            
            if errors:
                logger.error("eroor")
                return render(
                    request,
                       "accounts/add_hotel.html",
                    { "errors": errors, "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY},
                )
            
            try:
                with transaction.atomic():
                    try:
                        user = request.user
                        user.save()
                    except Exception as e:
                        logger.error(f"Error updating user details: {e}")
                        raise

                    try:
                        vendor_profile = VendorProfile.objects.get(user=user)
                    except VendorProfile.DoesNotExist:
                        logger.error("Vendor profile does not exist.")
                        raise
                    except Exception as e:
                        logger.error(f"Error fetching vendor profile: {e}")
                        raise

                    try:
                        country, _ = Country.objects.get_or_create(name=form_data["country"])
                        state, _ = State.objects.get_or_create(country=country, name=form_data["stateProvince"])
                        def is_arabic(text):
                            return any('\u0600' <= c <= '\u06FF' for c in text)
                        city_name = form_data["city"]
                        if is_arabic(city_name):
                            arabic_name=city_name
                            english_name=get_city_name(city_name,state.name,country.name,'en')
                            logger.info("city name is arabic")
                        else:
                            english_name=city_name
                            arabic_name=get_city_name(city_name,state.name,country.name,'ar')
                        print("english and arabic name of the city is: ", english_name, arabic_name)
                        city, _ = City.objects.get_or_create(state=state, name=english_name, arabic_name=arabic_name)
                    except Exception as e:
                        logger.error(f"Error creating or fetching location data: {e}")
                        raise
                    hotel_type_value=form_data["hotel_type"]
                    try:
                        hotel_type_value=request.POST.get('hotel_type')
                        if hotel_type_value:
                            hotel_type=HotelType.objects.get(id=hotel_type_value)
                        else:
                            logger.error("Hotel type not found")
                    except Exception as e:
                        logger.error(f"Exception ocuured at hotel type fetch portion : {str(e)} ")
                       #validate owner name if it exist or not
                    try:
                        hotel_owner = OwnerName.objects.filter(
                            owner_name=form_data["hotelOwnerName"],
                            owner_name_arabic=form_data["hotelOwnerNameArabic"]
                        ).first()

                        if not hotel_owner:
                            hotel_owner = OwnerName.objects.create(
                                owner_name=form_data["hotelOwnerName"],
                                owner_name_arabic=form_data["hotelOwnerNameArabic"]
                            )
                    except Exception as e:
                        logger.error(f"Exception occurred at hotel owner name fetch portion: {str(e)}")
                        hotel_owner = None 
                     # Get hotel latitude and longitude
                    try:
                        lat, long = get_lat_long(
                        form_data.get("hotelAddress", ""),
                        form_data.get("city", ""),
                        form_data.get("stateProvince", ""),
                        form_data.get("country", "")
                        )

                        if lat is not None and long is not None:
                            logger.info(f"Fetched coordinates: latitude={lat}, longitude={long}")
                        else:
                            logger.warning("Could not fetch valid coordinates. Received None.")

                    except Exception as e:
                        logger.error(f"Error fetching coordinates: {str(e)}")
                        lat = None
                        long = None
                    try:
                        hotel = Hotel.objects.create(
                            vendor=vendor_profile,
                            hotel_rating=form_data["hotelrating"],
                            name=form_data["hotelName"].replace(' ', ''),  
                            address=form_data["hotelAddress"],
                            country=country, city=city, state=state,
                            number_of_rooms=form_data["roomnumber"],
                            rooms_available=form_data["roomnumber"],
                            cr_number=form_data["crnumber"],
                            vat_number=form_data["vatnumber"],
                            date_of_expiry=form_data["expiry"],
                            office_number=form_data["officenumber"],
                            logo=request.FILES.get("logo_image"),
                            about_property=form_data["About"],
                            hotel_policies=form_data["polices"],
                            locality=form_data["locality"],
                            name_arabic=form_data["hotelNameArabic"],
                            owner_name_arabic=form_data["hotelOwnerNameArabic"],
                            about_property_arabic=form_data["about_arabic"],
                            hotel_policies_arabic=form_data["polices_arabic"],
                            account_no=form_data["Accountno"],
                            bank=form_data["BankName"],
                            account_holder_name=form_data["Accountholder"],
                            hotel_type=hotel_type,
                            owner_name=hotel_owner,
                            latitude= lat,
                            longitude=long 
                        )
                        logger.info("hotel created")
                    except Exception as e:
                        logger.error(f"Error creating hotel record: {e}")
                        raise

                    try:
                        category_obj, _ = Categories.objects.get_or_create(category='HOTEL')
                        hotel.category.add(category_obj)
                    except Exception as e:
                        logger.error(f"Error adding category to hotel: {e}")
                        raise

                    try:
                        HotelImage.objects.bulk_create([HotelImage(hotel=hotel, image=image) for image in hotel_images])
                    except Exception as e:
                        logger.error(f"Error saving hotel images: {e}")
                        raise

                    try:
                        HotelDocument.objects.bulk_create([HotelDocument(hotel=hotel, document=document) for document in supporting_documents])
                    except Exception as e:
                        logger.error(f"Error saving hotel documents: {e}")
                        raise
                    self.send_registration_email(hotel)
            except Exception as e:
                logger.error(f"Transaction failed: {e}")
                raise
            
            return render(
                request,
                "accounts/add_hotel.html",
                {"registration_success": True,"hotel_id": form_data["hotel_is"], "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY},
            )

        except Exception as e:
            logger.error(f"An error occurred during registration: {e}")
            return render(
                request,
                 "accounts/add_hotel.html",
                {"registration_success": False, "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY},
            )

    def validate_form(self, form_data):
        errors = {}

        if not self.is_valid_phone(form_data["officenumber"]):
            errors["officenumber"] = _("Enter a valid phone number.")

        required_fields = [ "expiry","hotel_type"]
        for field in required_fields:
            if not form_data.get(field):
                errors[field] = _("This field is required.")
        
        return errors

    def is_valid_phone(self, phone):
        return re.match(r"^\+?[1-9]\d{1,14}$", phone)


    def send_registration_email(self, hotel):
        try:
            # Get all superusers' email addresses
            superusers = User.objects.filter(is_superuser=True)
            superuser_emails = [superuser.email for superuser in superusers]

            # Prepare the email context
            context = {
                "hotel_name": hotel.name,
                "hotel_address": hotel.address,
            }

            # Render the email template
            subject = "New Hotel Registration Notification"
            message = render_to_string("accounts/hotel_registration_notification.html", context)
            from_email = settings.EMAIL_HOST_USER

            # Send email with HTML message
            send_mail(
                subject,
                "",  # Leave plain-text message empty since we're using HTML
                from_email,
                superuser_emails,
                html_message=message,
            )
        except Exception as e:
            # Log or handle exceptions if needed
            print(f"Error in sending registration email: {e}")

        