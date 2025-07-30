import json
import os
import re
import uuid
import logging
from datetime import date, datetime, timedelta
from django.http import Http404
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db.models import Q, Count
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import activate
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from chalets.models import Chalet, ChaletBooking, ChaletImage, ChaletMealPrice, ChaletRecentReview, ChaletTransaction, ChaletWeekendPrice, PropertyManagement, chaletDocument,OwnerName
from common.utils import create_notification, payment_gateway
from commonfunction import booking_filters, report_data_frame, transaction_list_filter, xlsxwriter_styles,get_lat_long
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.timezone import now
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db import IntegrityError, transaction
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from decimal import Decimal
from common.customdecorator import vendor_required
from user.models import User, VendorProfile
from common.utils import create_notification
from common.models import AdminTransaction, Amenity, Categories, ChaletType, City, Country, PolicyCategory, PolicyName, State, Tax, PaymentTypeCategory,PaymentType,RefundTransaction,Transaction
from vendor.models import Bookedrooms, Booking, CommissionSlab, Hotel, HotelDocument, HotelImage, HotelTax, Roomtype, HotelTransaction,HotelType
from chalets.models import Chalet, ChaletBooking, ChaletImage, ChaletMealPrice, ChaletRecentReview, ChaletTax, ChaletTransaction, ChaletWeekendPrice, PropertyManagement, chaletDocument, Promotion, ChaletAcceptedPayment
from django.views.decorators.cache import cache_control
from common.models import PaymentTypeCategory,PaymentType 
from common.function import create_transaction, create_vendor_transaction, generate_transaction_id, create_chalet_booking_transaction
from vendor.function import get_city_name


logger = logging.getLogger('lessons')
# Create your views here.

@csrf_exempt
def test_template(request):
    payment_gateway()
    logger.info("Test template started")
    template = "booking-aggregator-email.html"
    payment_id = None
    trandata = None
    error = None
    error_text = None
    if request.method == 'POST':
        # Handle POST data
        payment_id = request.POST.get('paymentId')
        trandata = request.POST.get('trandata')
        error = request.POST.get('error')
        error_text = request.POST.get('errorText')
        resource_key = "43432221238243432221238243432221"  # 32-byte resource key (bytes format)
        iv = "PGKEYENCDECIVSPC"  # 16-byte IV (bytes format)
        if not payment_id:
            if request.body:
                try:
                    data = request.POST  # Automatically parses URL-encoded data into a QueryDict
                    logger.info(f"Parsed POST data: {data}")
                    print(data)
                
                    # Extract values from the data
                    payment_id = data.get('paymentid')
                    trackid = data.get('trackid')
                    error = data.get('Error')
                    error_text = data.get('ErrorText')

                    logger.info(f"Payment ID: {payment_id}, Track ID: {trackid}, Error: {error}, Error Text: {error_text}")
                    if data.get("trandata"):
                        print(f"Trandata found. Trandata : {data.get('trandata')}")
                        try:
                            from common.utils import decrypt_aes
                            from urllib.parse import unquote

                            print("Started decrypting")
                            decrypted_trandata = decrypt_aes(data.get("trandata"), resource_key, iv)
                            parsed_data=None
                            url_decoded_data=None
                            if decrypted_trandata:
                                if isinstance(decrypted_trandata, list):
                                    parsed_data=decrypted_trandata
                                elif isinstance(decrypted_trandata, str):
                                    url_decoded_data = unquote(decrypted_trandata)
                                else:
                                    raise ValueError(f"Unexpected type after decryption: {type(decrypted_trandata)}")

                            

                                # If it’s still a JSON string, parse it into a Python object
                                if parsed_data and url_decoded_data:
                                    try:
                                        parsed_data = json.loads(url_decoded_data)
                                        print(f"Parsed data. Data : {parsed_data}")
                                    except json.JSONDecodeError as e:
                                        print(f"JSON Parsing Error: {e}")
                                else:
                                    print(f"Parsed data. Data : {parsed_data}")
                            print(f"Decrypted data. Data : {decrypted_trandata}")
                        except Exception as e:
                            print(f"Exception occured in decrypting payload. Exception : {e}")
                    else:
                        print("Trandata not found")
                    # print(f"Request Body. : {request.body}")
                    # data = json.loads(request.body)
                    # if data:
                    #     logger.info(f"Data fetched. Data : {data}")
                    #     payment_id = data.get('paymentId')
                    #     trandata = data.get('trandata')
                    #     error = data.get('error')
                    #     error_text = data.get('errorText')
                    # else:
                    #     logger.info(f"No data after loading JSON in test_template. Data : {data}")
                except Exception as e:
                    logger.info(f"Exception occured in test_template post method while loading json. Exception : {e}")
            else:
                print(f"Request body is empty. Body: {request.body}, request.POST : {request.POST}")
                
    elif request.method == 'GET':
        # Handle GET data (if applicable)
        payment_id = request.GET.get('paymentId')
        trandata = request.GET.get('trandata')
        error = request.GET.get('error')
        error_text = request.GET.get('errorText')
    
    print(request.GET)
    logo_name="email-logo.png"
    logo_path=f"{getattr(settings, 'STATIC_URL','https://storage.1929way.app:9000/1929way-testserver/static/')}images/{logo_name}"
    # aggregator_emails = getattr(settings, 'AGGREGATOR_EMAILS', [
    #     'vishnu.pk@codesvera.com',
    #     'developer@codesvera.com'
    # ])
    # Initialize data dictionary
    data = {
        'check_in': None,
        'check_out': None,
        'customer_name': None,
        'booking_id': None,
        'customer_contact': None,
        'rooms': [],
        'rooms_count': None,
        'guests': None,
        'vendor_name': None,
        'vendor_contact': None,
        'vendor_email': None,
        'property_name': None,
        'property_address': None,
        'action_url': None, 
        'logo_url':logo_path,
        'action_url':"test",
        'paymentId': payment_id,
        'trandata': trandata,
        'error': error,
        'errorText': error_text,
    }
    return render(request,template,data)

class ChaletRegister(View):
    def get(self, request, category):
        user_language = request.LANGUAGE_CODE
        activate(user_language)
        get_chalet_type = ChaletType.objects.filter(status = "active")
        return render(
            request,
            "chalets_accounts/registration_chalet.html",
            context={
                "chalet_type":get_chalet_type,
                "category": category,
                "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
            },
        )

    def post(self, request, category):
        try:
            logger.info("Received POST request for chalet registration.")
            form_data = {key: request.POST.get(key) for key in [
                "chaletName", "chaletNameArabic", "chaletOwnerName", "chaletOwnerArabicName",
                "chaletOwnerEmail", "officenumber", "password1", "password2",
                "hotelAddress", "stateProvince", "city", "country", "gsmnumber",
                "locality","Accountno", "BankName","Accountholder", 
                "crnumber", "vatnumber", "expiry", "About", "polices",
                "about_arabic", "polices_arabic","chalet_type"
            ]}
            chalet_images = request.FILES.getlist("chalet_images[]")
            logo_image = request.FILES.get("logo_image")

            errors = self.validate_form(form_data)

            if errors:
                return render(request, "chalets_accounts/registration_chalet.html", {
                    "category": category, "errors": errors,
                    "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
                })

            if VendorProfile.objects.filter(user__email=form_data["chaletOwnerEmail"], user__is_vendor=True).exists():
                logger.info(f"Email {form_data['chaletOwnerEmail']} already registered as a vendor.")
                return render(request, "chalets_accounts/registration_chalet.html", {
                    "category": category, "resend_modal": True,
                    "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
                })

            if not chalet_images:
                errors["chalet_images"] = _( "Chalet image is required.")
            if not logo_image:
                errors["logo_image"] = _( "Logo image is required.")

            if errors:
                return render(request, "chalets_accounts/registration_chalet.html", {
                    "category": category, "errors": errors,
                    "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
                })

            with transaction.atomic():
                try:
                    user = User.objects.create_user(
                        username=str(uuid.uuid4())[:15],
                        first_name=form_data["chaletOwnerName"],
                        email=form_data["chaletOwnerEmail"],
                        password=form_data["password1"],
                        is_vendor=True
                    )
                except IntegrityError as e:
                    logger.error(f"Error creating user: {e}")
                    raise Exception(f"Error creating user: {e}")

                try:
                    vendor_profile = VendorProfile.objects.create(
                        user=user,
                        name=form_data["chaletOwnerName"],
                        contact_number=form_data["officenumber"],
                        gsm_number=form_data["gsmnumber"],
                    )
                except IntegrityError as e:
                    logger.error(f"Error creating vendor profile: {e}")
                    raise Exception(f"Error creating vendor profile: {e}")

                try:
                    country, _ = Country.objects.get_or_create(name=form_data["country"])
                    print("Country : ",country)
                    state, _ = State.objects.get_or_create(country=country, name=form_data["stateProvince"])
                    print("State : ",state)
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
                    print("City : ",city)
                except IntegrityError as e:
                    logger.error(f"Error creating location hierarchy: {e}")
                    raise Exception(f"Error creating location hierarchy: {e}")
                #validate owner name if it exist or not
                try:
                    chalet_owner = OwnerName.objects.filter(
                        owner_name=form_data["chaletOwnerName"],
                        owner_name_arabic=form_data["chaletOwnerArabicName"]
                    ).first()

                    if not chalet_owner:
                        chalet_owner = OwnerName.objects.create(
                            owner_name=form_data["chaletOwnerName"],
                            owner_name_arabic=form_data["chaletOwnerArabicName"]
                        )
                except Exception as e:
                    logger.error(f"Exception occurred at hotel owner name fetch portion: {str(e)}")
                    chalet_owner = None 
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
                    chalettype = ChaletType.objects.get(id=form_data["chalet_type"])
                    chalet = Chalet.objects.create(
                        chalet_type = chalettype,
                        vendor=vendor_profile,
                        name=form_data["chaletName"],
                        name_arabic=form_data["chaletNameArabic"],
                        owner_name_arabic=form_data["chaletOwnerArabicName"],
                        address=form_data["hotelAddress"],
                        country=country, city=city, state=state,
                        cr_number=form_data["crnumber"],
                        vat_number=form_data["vatnumber"],
                        date_of_expiry=form_data["expiry"],
                        office_number=form_data["officenumber"],
                        logo=logo_image,
                        about_property=form_data["About"],
                        policies=form_data["polices"],
                        locality=form_data["locality"],
                        account_no=form_data["Accountno"],
                        bank=form_data["BankName"],
                        account_holder_name=form_data["Accountholder"],
                        about_property_arabic=form_data["about_arabic"],
                        policies_arabic=form_data["polices_arabic"],
                        owner_name=chalet_owner,
                        latitude = lat,
                        longitude = long
                    )
                except IntegrityError as e:
                    logger.error(f"Error creating chalet: {e}")
                    raise Exception(f"Error creating chalet: {e}")

                try:
                    category_obj, _ = Categories.objects.get_or_create(category=category)
                    chalet.category.add(category_obj)
                except IntegrityError as e:
                    logger.error(f"Error adding category to chalet: {e}")
                    raise Exception(f"Error adding category to chalet: {e}")

                try:
                    ChaletImage.objects.bulk_create([ChaletImage(chalet=chalet, image=image) for image in chalet_images])
                except IntegrityError as e:
                    logger.error(f"Error creating chalet images: {e}")
                    raise Exception(f"Error creating chalet images: {e}")

                try:
                    self.send_registration_email(chalet)
                except Exception as e:
                    logger.error(f"Error sending registration email: {e}")
                    raise Exception(f"Error sending registration email: {e}")

                return redirect('/vendor/login/?registration-success')

        except IntegrityError as e:
            logger.error(f"Database IntegrityError: {e}")
            return render(request, 'accounts/404.html', {"error": _( "There was an error processing your request.")})
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return render(request, 'accounts/404.html', {"error": _( "An unexpected error occurred, please try again.")})

    def validate_form(self, form_data):
        errors = {}
        if not form_data["chaletOwnerEmail"]:
            errors["chaletOwnerEmail"] = _( "This field is required.")
        elif not self.is_valid_email(form_data["chaletOwnerEmail"]):
            errors["chaletOwnerEmail"] = _( "Enter a valid email address.")

        if not self.is_valid_phone(form_data["officenumber"]):
            errors["officenumber"] = _( "Enter a valid phone number.")

        required_fields = ["chaletName", "chaletOwnerName", "stateProvince", "city", "country", "password1", "password2"]
        for field in required_fields:
            if not form_data.get(field):
                errors[field] = _( "This field is required.")

        password1 = form_data.get("password1")
        password2 = form_data.get("password2")

        if password1 != password2:
            errors["passwords"] = _( "Passwords do not match.")
        elif len(password1) < 8:
            errors["passwords"] = _( "Password must be at least 8 characters long.")

        return errors

    def is_valid_email(self, email):
        try:
            validate_email(email)
            return True
        except ValidationError:
            return False

    def is_valid_phone(self, phone):
        return re.match(r"^\+?[1-9]\d{1,14}$", phone)

    def send_registration_email(self, chalet):
        try:
            superusers = User.objects.filter(is_superuser=True)
            superuser_emails = [superuser.email for superuser in superusers]
            context = {"chalet_name": chalet.name, "chalet_address": chalet.address}
            message = render_to_string("accounts/chalet_registration_notification.html", context)
            send_mail(
                "New Chalet Registration Notification",
                "",
                settings.EMAIL_HOST_USER,
                superuser_emails,
                html_message=message,
            )
            logger.info("Sent registration notification email to superusers.")
        except Exception as e:
            logger.error(f"Error in sending registration email: {e}")

class HotelRegister(View):

    def get(self, request, category):
        user_language = request.LANGUAGE_CODE
        activate(user_language)
        hotel_rating = Hotel.HOTEL_RATING
        hotel_types=HotelType.objects.filter(status='active')
        # if category == "hotel_categories":
        #     return render(
        #         request,
        #         template_name="chalets_accounts/hotel_registration.html",
        #         context={
        #             "category": category,
        #             "hotel_rating": hotel_rating,
        #             "GOOGLE_MAPS_API_KEY":settings.GOOGLE_MAPS_API_KEY,
        #             "hotel_types":  hotel_types
        #         },
        #     )
        user=request.user
        user_details = get_object_or_404(VendorProfile, user=request.user)
        hotel=Chalet.objects.filter(vendor=user_details.id).first()

        return render(
            request,
            template_name="chalets_accounts/hotel_registration.html",
            context={
                "category": category,
                "hotel_rating": hotel_rating,
                "GOOGLE_MAPS_API_KEY":settings.GOOGLE_MAPS_API_KEY,
                "hotel_types":  hotel_types,
                'pre_filled_fields': {
                'hotelOwnerName': request.user.first_name,
                'hotelOwnerEmail': request.user.email,
                'owner_name_arabic': hotel.owner_name_arabic if hotel else '',
                
                # Add other fields that should be pre-filled
            }
            },
        )

    def post(self, request, category):
        try:
            logger.info("Received POST request for chalet owner registration.")
            form_data = {key: request.POST.get(key) for key in [
                "hotelOwnerName", "officenumber", "hotelName", "hotelAddress",
                "country", "city", "stateProvince", "roomnumber", "hotelrating",
                "crnumber", "vatnumber", "expiry", "logo_image", "locality",
                "buildingnumber", "About", "polices", "hotelNameArabic",
                "hotelOwnerNameArabic", "about_arabic",
                "polices_arabic", "Accountno", "BankName","Accountholder","hotel_type"
            ]}
            hotel_images = request.FILES.getlist("hotel_images[]")
            supporting_documents = request.FILES.getlist("supportingDocuments[]")

            # print(f"\n\n\n\n\n {form_data['hotelrating']} \n\n\n\n")
            # hotelListType = ["Hotel", "Hotels", "hotel", "hotels" ,"HOTEL", "HOTELS"]
            # if form_data['hotel_type'] in hotelListType:
            #     if form_data['hotelrating'] == "" or form_data['hotelrating'] is None:
            #         errors['hotelrating'] = f"Hotel rating is required when hotel type is '{form_data['hotel_type']}'."

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
                    "chalets_accounts/hotel_registration.html",
                    {"category": category, "errors": errors, "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY},
                )
            
            try:
                with transaction.atomic():
                    try:
                        user = request.user
                        # user.first_name = form_data["hotelOwnerName"]
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
                            owner_name= hotel_owner,
                            latitude= lat,
                            longitude=long 
                        )
                        logger.info("hotel created")
                    except Exception as e:
                        logger.error(f"Error creating hotel record: {e}")
                        raise

                    try:
                        category_obj, _ = Categories.objects.get_or_create(category=category)
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
                "chalets_accounts/hotel_registration.html",
                {"category": category, "registration_success": True, "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY},
            )

        except Exception as e:
            logger.error(f"An error occurred during registration: {e}")
            return render(
                request,
                "chalets_accounts/hotel_registration.html",
                {"category": category, "registration_success": False, "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY},
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

class Pendingview(View):
    def get(self,request):
        user = VendorProfile.objects.get(user=request.user)
        logger.info(f"VendorProfile retrieved for user: {request.user.id}")
        chalet_id = request.GET.get('chalet_id')
        logger.info(f" chalet id is ---{chalet_id}")
        if chalet_id:
            selected_chalet= get_object_or_404(Chalet, id=chalet_id, vendor=user.id)
        else:
            selected_chalet= Chalet.objects.filter(vendor=user.id).first() 
        return render(request,'chalets_accounts/pending_hotel.html',context={'selected_chalet':selected_chalet})

@method_decorator(login_required(login_url='loginn'), name='dispatch')
@method_decorator(cache_control(no_cache=True, must_revalidate=True, no_store=True), name='dispatch')
class AmenitiesAddView( View):
    def get(self, request):
        try:
            user = VendorProfile.objects.get(user=request.user)
            chalet_id = request.GET.get("chalet_id")  # Get chalet_id from URL parameter
            print("Chalet ID from URL parameter:", chalet_id)  # Debug: Print chalet_id

            if chalet_id:
                chalet = Chalet.objects.filter(id=chalet_id, vendor=user.id).first()
                if chalet:
                    if chalet.approval_status == "rejected":
                        messages.error(request, _('Chalet was rejected.'))
                        if "meal_prices" in request.session:
                            del request.session["meal_prices"]
                            logger.info("Meal prices session data cleared.")
                        return redirect('loginn')
                    
                    if chalet.post_approval:
                        messages.info(request, _('Chalet post approval already completed. Redirecting to the dashboard.'))
                        return redirect("dashboard_overviews")

                    request.session["selected_chalet_id"] = chalet.id  # Save chalet_id in session
                else:
                    return render(request, 'chalets_accounts/404.html')
            else:
                chalet = Chalet.objects.filter(vendor=user.id).first()
                if chalet:
                    if chalet.approval_status == "rejected":
                        messages.error(request, _('Chalet was rejected.'))
                        if "meal_prices" in request.session:
                            del request.session["meal_prices"]
                            logger.info("Meal prices session data cleared.")
                        return redirect('loginn')
                    request.session["selected_chalet_id"] = chalet.id

            if chalet is None:
                return render(request, 'chalets_accounts/404.html')
            
            # # Check if the vendor has other chalets
            chalet_count = Chalet.objects.filter(vendor=user.id).count()
            has_other_chalets = chalet_count > 1 

            
        except VendorProfile.DoesNotExist:
            return render(request, 'chalets_accounts/404.html')

        amenities = Amenity.objects.filter(
            amenity_type="Property_amenity", status="True"
        )

        return render(request, "chalets_accounts/amenties.html", 
                    context = {"amenities": amenities,
                            "has_other_chalets": has_other_chalets
                    }
        )

    def post(self, request):
        amenities = request.POST.getlist("amenities_checked")
        request.session["amenities"] = amenities
        print("amneties",amenities)
        chalet_id = request.session["selected_chalet_id"]
        return JsonResponse({"next_url": f"/chalets/price/?chalet_id={chalet_id}"})

@method_decorator(login_required(login_url='loginn'), name='dispatch')
class BackSelectedAmmenities(View):
    def get(self, request):
        try:
            user = VendorProfile.objects.get(user=request.user)
            chalet_id = request.session.get("selected_chalet")

            if chalet_id:
                chalet = Chalet.objects.filter(id=chalet_id, vendor=user.id).first()
            else:
                chalet = Chalet.objects.filter(vendor=user.id).first()
                if chalet:
                    request.session["selected_chalet"] = chalet.id

            if chalet is None:
                return render(request, 'chalets_accounts/404.html')

        except VendorProfile.DoesNotExist:
            return render(request, 'chalets_accounts/404.html')

        selected_amenities = request.session.get("amenities", [])
        print(selected_amenities)
        number_of_guest = request.session.get("numberOfGuest", "")
        total_price = request.session.get("totalPrice", "")
        Chalet_id= chalet.id
        # payment_types=request.session.get("selectedPayments", [])


        response_data = {
            "selected_amenities": selected_amenities,
            "number_of_guest": number_of_guest,
            "total_price": total_price,
            "chalet_id":Chalet_id,
            #  "payment_types":payment_types
        }

        return JsonResponse(response_data)

@method_decorator(login_required(login_url='loginn'), name='dispatch')
@method_decorator(cache_control(no_cache=True, must_revalidate=True, no_store=True), name='dispatch')
class PriceAddView(View):
    def get(self, request):
        try:
            user = VendorProfile.objects.get(user=request.user)
            chalet_id = request.GET.get("chalet_id")
            request.session["selected_chalet"] = chalet_id

            if chalet_id:
                chalet = Chalet.objects.filter(id=chalet_id, vendor=user.id).first()
                Payment_ctg=PaymentTypeCategory.objects.filter(status ='active')

                if chalet:
                    if chalet.approval_status == "rejected":
                        messages.error(request, _('Chalet was rejected.'))
                        if "meal_prices" in request.session:
                            del request.session["meal_prices"]
                            logger.info("Meal prices session data cleared.")
                        return redirect('loginn')
                    
                    if chalet.post_approval:
                        messages.info(request, _('Chalet post approval already completed. Redirecting to the dashboard.'))
                        return redirect("dashboard_overviews")
            else:
                chalet = Chalet.objects.filter(vendor=user.id).first()
                if chalet:
                    if chalet.approval_status == "rejected":
                        messages.error(request, _('Chalet was rejected.'))
                        if "meal_prices" in request.session:
                            del request.session["meal_prices"]
                            logger.info("Meal prices session data cleared.")
                        return redirect('loginn')
                    request.session["selected_chalet"] = chalet.id

            if chalet is None:
                return render(request, 'chalets_accounts/404.html')

            # Fetch active taxes
            taxes = Tax.objects.filter(status="active", is_deleted=False)

            # Fetch existing HotelTax or ChaletTax records for pre-filling
            if chalet:
                existing_taxes = ChaletTax.objects.filter(chalet=chalet, status="active", is_deleted=False)
                tax_percentage_map = {ct.tax_id: ct.percentage for ct in existing_taxes}

            # Attach existing percentages to taxes
            for tax in taxes:
                tax.percentage = tax_percentage_map.get(tax.id, None)

            context = {
                'taxes': taxes,
                'Payment_ctg': Payment_ctg
            }

        except VendorProfile.DoesNotExist:
            return render(request, 'chalets_accounts/404.html')

        return render(request, "chalets_accounts/price.html",context)

    def post(self, request):
        meals = request.POST.getlist("meal")
        payment_ctg=request.POST.getlist("payment_category")

        meal_prices = {}
        for meal in meals:
            price = request.POST.get(meal)
            meal_prices[meal] = price
        request.session["meal_prices"] = meal_prices

        number_of_guests= request.POST.get("number_of_guests")
        if number_of_guests:
            request.session["number_of_guests"] = number_of_guests

        total_amount = request.POST.get("total_price")
        if total_amount:
            request.session["total_amount"] = total_amount
        # Save weekend price
            weekend_price_value = request.POST.get("weekend_price")
            if weekend_price_value:
                request.session["weekend_price"] = weekend_price_value

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

        if payment_ctg:
            request.session["payment_mode"]=payment_ctg
            logger.info(f"added payment mode , {payment_ctg}")

        return JsonResponse({"next_url": "/chalets/final/"})

@method_decorator(login_required(login_url='loginn'), name='dispatch')
class BackSelectedPrice(View):
    def get(self, request):
        try:
            user = VendorProfile.objects.get(user=request.user)
            chalet_id = request.session.get("selected_chalet")

            if chalet_id:
                chalet = Chalet.objects.filter(id=chalet_id, vendor=user.id).first()
            else:
                chalet = Chalet.objects.filter(vendor=user.id).first()
                if chalet:
                    request.session["selected_chalet"] = chalet.id

            if chalet is None:
                return render(request, 'chalets_accounts/404.html')

        except VendorProfile.DoesNotExist:
            return render(request, 'chalets_accounts/404.html')

        selected_price = request.session.get("meal_prices", {})

        total_price = request.session.get("total_amount", {})

        print(total_price,"========total_price======4=====")
        number_of_guests = request.session.get("number_of_guests", {})
        print(number_of_guests,"=========number_of_guests====5======= ")
        payment_types=request.session.get("payment_mode", {})
        weekend_price=request.session.get("weekend_price", {})
        print("payment:",payment_types)
        Chalet_id= chalet.id


        return JsonResponse({
            "selected_price": selected_price,
            "total_price": total_price,
            "number_of_guests": number_of_guests,
            "payment_types":payment_types,
            "weekend_price":weekend_price,
            "chalet_id":Chalet_id,
        })

@method_decorator(login_required(login_url='loginn'), name='dispatch')
@method_decorator(cache_control(no_cache=True, must_revalidate=True, no_store=True), name='dispatch')
class FinalStepView(View):
    def get(self, request):
        try:
            user = VendorProfile.objects.get(user=request.user)
            chalet_id = request.session.get("selected_chalet")
            print(f"id:{chalet_id}")

            if chalet_id:
                chalet = Chalet.objects.filter(id=chalet_id, vendor=user.id).first()
                if chalet:
                    if chalet.approval_status == "rejected":
                        messages.error(request, _('Chalet was rejected.'))
                        if "meal_prices" in request.session:
                            del request.session["meal_prices"]
                            logger.info("Meal prices session data cleared.")
                        return redirect('loginn')
                    
                    if chalet.post_approval:
                        print(f"approve status :{chalet.post_approval}")
                        messages.info(request, _('Chalet post approval already completed. Redirecting to the dashboard.'))
                        return redirect("dashboard_overviews")
            else:
                chalet = Chalet.objects.filter(vendor=user.id).first()
                if chalet:
                    if chalet.approval_status == "rejected":
                        messages.error(request, _('Chalet was rejected.'))
                        if "meal_prices" in request.session:
                            del request.session["meal_prices"]
                            logger.info("Meal prices session data cleared.")
                        return redirect('loginn')
                    request.session["selected_chalet"] = chalet.id

            if chalet is None:
                return render(request, 'chalets_accounts/404.html')

        except VendorProfile.DoesNotExist:
            return render(request, 'chalets_accounts/404.html')
        
        super_admins = User.objects.filter(is_superuser=True)
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

        context={
            'chalet_images':chalet,
            "policy_categories": filtered_policy_categories,
            "id_policy": id_policy,
            "has_identity_proof": has_identity_proof ,
            "chalet_id":chalet_id
            }

        
        return render(request, "chalets_accounts/final_step.html",
            context=context)

    def post(self, request):
        try:
            logger.info(f"POST request initiated by user: {request.user} at {timezone.now()}")

            user = VendorProfile.objects.get(user=request.user)
            logger.info(f"Vendor profile retrieved for user {request.user.id}")

            chalet_id = request.session.get("selected_chalet")
            
            logger.info(f"Selected chalet ID from session: {chalet_id}")

            try:
                chalet = Chalet.objects.filter(id=chalet_id, vendor=user.id).first()
                if chalet is None:
                    logger.error(f"Chalet with ID {chalet_id} not found for vendor {user.id}")
                    return render(request, 'chalets_accounts/404.html')
                else:
                    if chalet.approval_status == "rejected":
                        messages.error(request, _('Chalet was rejected.'))
                        return redirect('loginn')
            except Chalet.DoesNotExist:
                logger.error(f"Chalet with ID {chalet_id} does not exist for vendor {user.id}")
                return render(request, 'chalets_accounts/404.html')
                

            checkin = request.POST.get("checkin")
            checkout = request.POST.get("checkout")
            logger.info(f"Check-in time: {checkin}, Check-out time: {checkout}")

            selected_policy_ids = request.POST.getlist("policy-checkbox")
            selected_id_proof_ids = request.POST.getlist("id-proof")
            if isinstance(chalet.post_policies, str):
                chalet.post_policies = ""
                logger.info(f"Chalet policies cleared (string)")

            elif isinstance(chalet.post_policies, (list, dict, set)):
                chalet.post_policies.clear()
                logger.info(f"Chalet policies cleared (list/dict/set)")


            selected_guests_number = request.session.get("number_of_guests",{})
            selected_total_amount = request.session.get("total_amount",{})
            selected_ids = set(selected_policy_ids + selected_id_proof_ids)
            logger.info(f"Selected policy IDs: {selected_ids}")
            
            for policy_id in selected_ids:
                try:
                    policy = PolicyName.objects.get(id=policy_id)
                    chalet.post_policies.add(policy.policy_category)
                    logger.info(f"Added policy {policy.policy_category} to chalet {chalet.id}")

                    # Save the policy name
                    chalet.post_policies_name.add(policy)  # Add the policy name to the chalet
                    logger.info(f"Added policy name {policy} to hotel: {chalet.id}")

                except PolicyName.DoesNotExist:
                    logger.error(f"PolicyName with ID {policy_id} does not exist")

            selected_amenities = request.session.get("amenities", [])
            logger.info(f"Selected amenities: {selected_amenities}")
            
            for amenity_name in selected_amenities:
                amenity, created = Amenity.objects.get_or_create(amenity_name=amenity_name, amenity_type="Property_amenity")
                chalet.amenities.add(amenity)
                logger.info(f"Added amenity {amenity_name} to chalet {chalet_id}")

            selected_price = request.session.get("meal_prices", {})
            logger.info(f"Selected meal prices: {selected_price}")

            # Always create the "No meals" price object
            no_meal_price = ChaletMealPrice(meal_type='no meals', price=0.00, chalet=chalet)
            no_meal_price.save()
            logger.info(f"Added no meals price to hotel: {chalet.id}")
            
            for meal_type, price in selected_price.items():
                price_value = float(price)
                if price_value > 0: 
                    meal_price = ChaletMealPrice(meal_type=meal_type, price=price, chalet=chalet)
                    meal_price.save()
                    logger.info(f"Added meal price {meal_type}: {price} to chalet: {chalet.id}")
                else:
                    logger.info(f"Skipped adding meal price {meal_type}: {price} for chalet: {chalet.id} (price is 0)")

            selected_image_id = request.POST.get("highlight_image")
            if selected_image_id:
                chalet.chalet_images.update(is_main_image=False)
                ChaletImage.objects.filter(id=selected_image_id).update(is_main_image=True)
                logger.info(f"Updated main image for chalet {chalet_id} to image {selected_image_id}")
            # Retrieve weekend price from the session
            weekend_price = request.session.get("weekend_price")
            logger.info(f"Weekend price from session: {weekend_price}")

            # Save or update the weekend price
            if weekend_price is not None:
                chalet_weekend_price, created = ChaletWeekendPrice.objects.get_or_create(
                    chalet=chalet,  # The related Chalet instance
                    defaults={"weekend_price": float(weekend_price)}
                )
                if not created:
                    chalet_weekend_price.weekend_price = float(weekend_price)
                    chalet_weekend_price.save()

                logger.info(f"Weekend price set for chalet {chalet_id}: {weekend_price}")
             #save payment_accepted_methods
            try:
                payment_types=request.session.get("payment_mode", [])
                if payment_types:
                    logger.info(f"Selected payment types: {payment_types}")
                    if 'All' in payment_types:
                        paymenttype=PaymentType.objects.all()
                        chalet_payment_accepted, created = ChaletAcceptedPayment.objects.get_or_create(chalet=chalet, created_by=user, modified_by=user) 
                        chalet_payment_accepted.payment_types.set(paymenttype)
                        chalet_payment_accepted.save()
                    else:
                        paymenttype = PaymentType.objects.filter(category_id__in=payment_types)
                        wallet_payment_types = PaymentType.objects.filter(category__name__iexact="Wallet")
                        chalet_payment_accepted, created = ChaletAcceptedPayment.objects.get_or_create(chalet=chalet, created_by=user, modified_by=user) 
                        chalet_payment_accepted.payment_types.set(paymenttype | wallet_payment_types)
                        chalet_payment_accepted.save()
                    del request.session["payment_mode"]
            except Exception as e:
                logger.error(f"Error processing payment types: {e}")

             # Retrieve tax data from session and save it
            tax_data = request.session.get("tax_data", {})
            for tax_id, tax_percentage in tax_data.items():
                tax = Tax.objects.get(id=tax_id)
                if chalet:
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

            # Retrieve tax data from session and save it
            tax_data = request.session.get("tax_data", {})
            for tax_name_slug, tax_percentage in tax_data.items():
                tax_name = tax_name_slug.replace("-", " ").title()  # Convert slug back to name
                if chalet:
                    Tax.objects.create(chalet=chalet, tax_name=tax_name, tax_percentage=tax_percentage, is_active=True)

            # Clear tax data from session after saving
            request.session.pop("tax_data", None)

            chalet.checkin_time = checkin
            chalet.checkout_time = checkout
            chalet.post_approval = True
            chalet.number_of_guests=selected_guests_number
            chalet.total_price=selected_total_amount
            chalet.save()
            logger.info(f"Chalet {chalet_id} checkin/checkout times updated and marked for post-approval")

            if "meal_prices" in request.session:
                del request.session["meal_prices"]
                logger.info("Meal prices session data cleared")

            categories = chalet.category.all()
            category_names = [category.category for category in categories]
            logger.info(f"Chalet categories: {category_names}")

            if "CHALET" in category_names:
                logger.info(f"Redirecting to 'dashboard_overviews' for chalet {chalet_id}")
                return redirect(f'/chalets/dashboard_overview?chalet_id={chalet_id}')
            else:
                logger.info(f"Redirecting to 'dashboard' for chalet {chalet_id}")
                return redirect(f'/chalets/dashboard_overview?chalet_id={chalet_id}')

        except Exception as e:
            logger.info(f"An error occurred: {e}", exc_info=True)
            return render(request, 'chalets_accounts/404.html')

class ChaletApproveView(View):
    def get(self, request, *args, **kwargs):
        id = kwargs.get("pk")
        hotel = Chalet.objects.get(id=id)
        return render(
            request,
            template_name="chalets_accounts/chalet_approval.html",
            context={"data": hotel},
        )

    def post(self, request, *args, **kwargs):
        id = kwargs.get("pk")
        approve_status = request.POST.get("approved_status")
        print(approve_status, "========approve_status============")
        hotel = Chalet.objects.get(id=id)
        hotel_owner_email = request.POST.get("email")
        rejection_remark = request.POST.get("remark", "")
        if approve_status == "True":
            subject = "Chalet Approval Notification"
            message = render_to_string(
                "chalets_accounts/chalet_approval_notification.html",
                {"hotel_name": hotel.name},
            )
        else:
            subject = "Chalet Disapproval Notification"
            message = render_to_string(
                "chalets_accounts/chalet_disapproval_notification.html",
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

class DashboardOverview(View):
    def get(self, request):
        if not request.user.is_authenticated:
            request.session.flush()
            return redirect('loginn')

        user_language = request.LANGUAGE_CODE
        activate(user_language)

        try:
            user = VendorProfile.objects.get(user=request.user)
            chalets = Chalet.objects.filter(vendor=user.id).select_related('vendor')

            if not chalets.exists():
                return redirect('loginn')

            approved_chalets = chalets.filter(approval_status="approved")
            if not approved_chalets.exists():
                if chalets.filter(approval_status="rejected").exists():
                    messages.error(request, _('Your chalet was rejected.'))
                    return redirect('loginn')

            chalet_id = request.GET.get('chalet_id')
            selected_chalet = approved_chalets.first() if not chalet_id else get_object_or_404(Chalet, id=chalet_id, vendor=user.id)

            if selected_chalet.approval_status != "approved":
                return render(request, 'chalets_accounts/pending_hotel.html')

            if not selected_chalet.post_approval:
                return redirect(f'/chalets/ammenities/?chalet_id={selected_chalet.id}')

            visitor_statistics = self.get_visitor_statistics(selected_chalet)
            reservation_statistics = self.get_reservation_statistics(selected_chalet)

            latest_booking = ChaletBooking.objects.filter(chalet=selected_chalet).order_by("-id")[:5]
            bookings, page = self.paginate_bookings(latest_booking, request)

            today = now().date()

            # Aggregated stats for bookings
            booking_stats = ChaletBooking.objects.filter(chalet=selected_chalet).aggregate(
                total=Count('id'),
                cancel_count=Count('id', filter=Q(status__in=["cancelled","rejected","expired"])),
                confirmed_count=Count('id', filter=Q(status__in=["confirmed","check-in"])),
                daily_count=Count('id', filter=Q(booking_date=today))
            )

            # Count bookings with reviews
            bookings_with_reviews = ChaletRecentReview.objects.filter(
                chalet=selected_chalet
            ).values('chalet_id').distinct().count()

            # Calculated Ratings
            total = booking_stats['total'] or 1  # Avoid division by zero
            cancel_rating = f"{(booking_stats['cancel_count'] / total) * 100:.2f}%"
            confirmed_rating = f"{(booking_stats['confirmed_count'] / total) * 100:.2f}%"
            review_rate = f"{(bookings_with_reviews / total) * 100:.2f}%"
            adr_rates = f"{(booking_stats['daily_count'] / total) * 100:.2f}%"

            return render(
                request,
                template_name="chalets_accounts/dashboard_chalets.html",
                context={
                    "booking_data": bookings,
                    "chalets": chalets,
                    "selected_chalet": selected_chalet,
                    "LANGUAGES": settings.LANGUAGES,
                    "visitor_statistics": visitor_statistics,
                    "reservation_statistics": reservation_statistics,
                    "cancel_count": booking_stats['cancel_count'],
                    "cancel_rating": cancel_rating,
                    "confirmed_count": booking_stats['confirmed_count'],
                    "confirmed_rating": confirmed_rating,
                    "adr": booking_stats['daily_count'],
                    "adr_rates": adr_rates,
                    "review_count": bookings_with_reviews,
                    "review_rating": review_rate,
                },
            )
        except VendorProfile.DoesNotExist:
            return render(request, 'chalets_accounts/404.html')

    def get_visitor_statistics(self, selected_chalet):
        current_year = now().year
        bookings_per_month = ChaletBooking.objects.filter(
            chalet=selected_chalet,
            booking_date__year=current_year
        ).values_list('booking_date__month').annotate(count=Count('id'))

        visitor_statistics = [0] * 12
        for month, count in bookings_per_month:
            visitor_statistics[month - 1] = count
        return visitor_statistics

    def get_reservation_statistics(self, selected_chalet):
        today = now().date()
        start_of_week = today - timedelta(days=today.weekday())

        weekly_bookings = ChaletBooking.objects.filter(
            chalet=selected_chalet,
            booking_date__gte=start_of_week
        ).values_list('booking_date', 'status').annotate(count=Count('id'))

        reservation_statistics = {
            "new_bookings": [0] * 7,
            "confirmed_bookings": [0] * 7,
            "cancelled_weekly": [0] * 7
        }

        for date, status, count in weekly_bookings:
            day_index = (date - start_of_week).days
            if status == 'pending':
                reservation_statistics["new_bookings"][day_index] = count
            elif status in ['confirmed','check-in']:
                reservation_statistics["confirmed_bookings"][day_index] = count
            elif status == 'cancelled' or status == 'rejected' or status == 'expired':
                reservation_statistics["cancelled_weekly"][day_index] = count

        return reservation_statistics

    def paginate_bookings(self, latest_booking, request):
        paginator = Paginator(latest_booking, 10)
        page = request.GET.get('page')

        try:
            bookings = paginator.page(page)
        except PageNotAnInteger:
            bookings = paginator.page(1)
        except EmptyPage:
            bookings = paginator.page(paginator.num_pages)

        return bookings, page



class chaletViewAllButton(View):
    def get(self, request):
        user_language = request.LANGUAGE_CODE
        activate(user_language)
        try:
            chalet_id = request.GET.get('chalet_id')
            user = VendorProfile.objects.get(user=request.user)
            logger.info(f"requested chalet id is ----- {chalet_id}")
            if chalet_id:
                chalet = Chalet.objects.get(vendor=user.id,id=chalet_id )
            else:
                chalet = Chalet.objects.filter(vendor=user.id).first()

        except (VendorProfile.DoesNotExist, Chalet.DoesNotExist):
            logger.info("user not found")
            return render(request,'chalets_accounts/404.html')
            # return redirect('loginn')
        latest_booking = ChaletBooking.objects.filter(chalet=chalet).order_by("-id")
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
            template_name="chalets_accounts/dashboard_chalets.html",
            context={"booking_data":  booking_paginated},
        )


@method_decorator(vendor_required, name='dispatch')
class ChaletUserManagement(View):
    def get(self, request, *args, **kwargs):
        logger.info(f"\n\n------->>>>> get request inside ChaletUserManagement View <<<<<<<-------\n\n\n")
        context = {}
        template = "chalets_accounts/chalet_booking_view.html"
        try:
            id = kwargs.get("pk")
            if not id:
                raise ValueError("Booking ID is missing in the request.")

            try:
                booking = ChaletBooking.objects.get(id=id)
            except ChaletBooking.DoesNotExist:
                logger.info(f"\n\nBooking is not available for ID: {id}\n\n")
                return render(request, 'chalets_accounts/404.html', {"error": _("Booking not found")}) 
            
            user = request.user.vendor_profile

            chalet = Chalet.objects.filter(vendor=user, id=booking.chalet.id).first()
            if chalet:
                if not chalet.post_approval:
                    logger.info(f"Chalet {chalet.id} requires post-approval steps.")
                    return redirect(f'/chalets/ammenities/?chalet_id={chalet.id}')
                elif chalet.approval_status == "approved":
                    amenities = chalet.amenities.all() if chalet else []
                    status = booking.status
                    booking_transaction = getattr(booking.transaction, 'payment_status', "Transaction is unavailable")
                    payment_method_name = booking.transaction.payment_type.name if booking.transaction and booking.transaction.payment_type else "Transaction is unavailable"
                    
                    today = date.today()
                    reminder = (booking.checkin_date - today) == timedelta(days=1)
                    get_commission = CommissionSlab.objects.filter(
                            from_amount__lte=chalet.total_price,
                            to_amount__gte=chalet.total_price,
                            status='active'
                        ).first()
                    logger.info(f"\n\nget_commission: {get_commission}\n\n")
                    if get_commission:
                        base_price_commission = chalet.total_price + get_commission.commission_amount
                    else:
                        base_price_commission = chalet.total_price
                    base_price = booking.booked_price + booking.discount_price - (booking.tax_and_services)

                    # Calculate admin commission and total gateway fee
                    if booking.transaction:
                        admin_transaction = AdminTransaction.objects.filter(transaction=booking.transaction).first()
                        if admin_transaction:
                            admin_commission = admin_transaction.admin_commission-admin_transaction.admin_gateway_fee
                            gateway_fee = admin_transaction.gateway_fee
                          
                            total_gateway_fee = gateway_fee
                        else:
                            admin_commission = None
                            total_gateway_fee = None
                    else:
                        admin_commission = None
                        total_gateway_fee = None

                    context={
                            'base_price_commission': base_price_commission,
                            "booking": booking,
                            "chalet": chalet,
                            "amenities": amenities,
                            "selected_chalet": chalet,
                            "chalets": [chalet] if chalet else [],
                            "LANGUAGES": settings.LANGUAGES,
                            "today": today,
                            "status": status,
                            "booking_transaction_status": booking_transaction,
                            "payment_method_name": payment_method_name,
                            "reminder": reminder,
                            "base_price": base_price,
                            "admin_commission": admin_commission,
                            "total_gateway_fee": total_gateway_fee,
                        }
                    return render(
                        request,
                        template_name=template,
                        context=context,
                    )
                else:
                    if chalet.approval_status == "rejected":
                        messages.error(request, _('Your chalet was rejected.'))
                        return redirect('loginn')
                    else:
                        messages.error(request, _('Your chalet is pending approval.'))
                        return render(request, 'chalets_accounts/pending_hotel.html')
            else:
                logger.warning(f"Vendor {user} attempted to access an unauthorized booking.")
                return HttpResponseForbidden(_("You are not authorized to view this booking."))

        except ValueError as ve:
            logger.error(f"ValueError occurred: {ve}")
            return render(request, 'chalets_accounts/404.html', {"error": str(ve)})

        except Exception as e:
            logger.exception(f"An unexpected error occurred: {e}")
            return render(request, 'chalets_accounts/404.html', {"error": _("An unexpected error occurred.")})

class ChaletUsermanagementEdit(View):
    def get(self, request, *args, **kwargs):
        id = kwargs.get("pk")
        try:
            booking = ChaletBooking.objects.get(id=id)
            data = {
                "guest_name": booking.booking_fname,
                "contact_number": booking.booking_mobilenumber,
                "check_in": booking.checkin_date,
                "check_out": booking.checkout_date,
                "status": booking.status,
            }
            print(data)
            return JsonResponse(data)
        except:
            logger.info("chaletbooking not found")
            return render(request, 'chalets_accounts/404.html')

    def post(self, request, *args, **kwargs):
        id = kwargs.get("pk")
        booking = Bookedrooms.objects.get(id=id)
        booking.booking.booking_fname = request.POST.get("guest_name")
        booking.booking.booking_mobilenumber = request.POST.get("contact_number")
        booking.booking.checkin_date = request.POST.get("check_in_date")
        booking.booking.checkout_date = request.POST.get("check_out_date")
        booking.status = request.POST.get("booking_status")
        print(request.POST.get("property_types"))
        booking.booking.property_type = request.POST.get("property_types")
        booking.save()
        booking.booking.save()

        return JsonResponse({"message": _("Booking updated successfully")})


class chaletUploadImagesView(View):
    def post(self, request, pk):
        booking_management = get_object_or_404(Bookedrooms, id=pk)
        property_type = booking_management.booking.property_type
        # Retrieve multiple images from request.FILES
        images = request.FILES.getlist("images[]")
        print(images)

        if images:
            # image_obj = PropertyImage.objects.filter(
            #     hotel=booking_management.hotel
            # )
            # image_obj.delete()

            # for image_file in images:

            #     # roomtype_instance.images.image.save(image_file.name, image_file, save=True)
            #     new_image = PropertyImage.objects.create(
            #         hotel=booking_management.hotel,
            #         property_image=image_file,
            #     )
            #     print(
            #         new_image.hotel, new_image.property_image, "++++++++++++++++++++++"
            #     )
            return JsonResponse({"message": _("Images uploaded successfully")}, status=200)
        else:
            return JsonResponse({"error": _("No images provided")}, status=400)


@method_decorator(csrf_exempt, name="dispatch")
class ChaletManageBookingView(View):
    def post(self, request, *args, **kwargs):
        booking_id = request.POST.get("id")
        action = request.POST.get("action")

        if not booking_id or not action:
            return JsonResponse({"success": False, "error": _("Invalid data")})
        try:
            booking = ChaletBooking.objects.get(id=booking_id)
        except booking.DoesNotExist:
            return JsonResponse({"success": False, "error": _("Booking not found")})

        if action == "cancel":
            if booking.status != "rejected":
                booking.status = "rejected"
                booking.chalet.is_booked = False
                booking.save()
                booking.chalet.save()
                try:
                    message = f"{booking.chalet.name} has rejected your booking"
                    message_arabic = f"{booking.chalet.name} قد رفض حجزك"
                    notification = create_notification(user=booking.user.user, notification_type="booking_reject",message=message,message_arabic=message_arabic,source="chalet", chalet_booking=booking)
                    logger.info(f"\n\n notification obj for reject chalet booking by vendor for user has been created -------> {notification} \n\n")
                except Exception as e:
                        logger.info(f"\n\n Exception raised in Creating notification in reject chalet booking by vendor. Exception: {e} \n\n")
                        return JsonResponse({'messgae':_('Something went wrong')})
                if booking.booking_email:
                    print(booking.booking_email,"===========================")
                    subject = "Booking Cancellation"
                    message = "<p>Your booking has been rejected.</p>"
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
                logger.info(f"\n\nBooking is already rejected\n\n")
                return JsonResponse({"success": False,'error':_("Booking is already rejected")}) 

        elif action == "send_reminder":
            if booking.booking_email:
                subject = "Booking Reminder"
                message = "<p>This is a reminder for your booking at our chalet.</p>"
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
                    transaction.transaction_status = "pending"
                    transaction.save()
                    booking.transaction=transaction
                    booking.save()
                    logger.info(f"\n\n Transaction created: {transaction} \n\n")

                    #Create Chalet Booking Transaction
                    chalet_booking_transaction = create_chalet_booking_transaction(
                        booking=booking,
                        transaction=transaction,
                        user=booking.user
                    )
                    logger.info(f"\n\n Chalet Booking Transaction created: {chalet_booking_transaction} \n\n")
                    # Create Vendor Transaction after Hotel Booking Transaction
                    try:
                        base_price = booking.booked_price+booking.discount_price-(booking.tax_and_services)
                        vendor_transaction = create_vendor_transaction(
                            transaction=transaction,
                            vendor=booking.chalet.vendor,
                            base_price=base_price,
                            total_tax=booking.tax_and_services,
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

@method_decorator(vendor_required, name='dispatch')
class ChaletBookings(View):
    def get(self, request, *args, **kwargs):
        chalet = None
        context={}
        confirmed_bookings = None
        template = "chalets_accounts/chalet_booking_management.html"

        # Activate user language
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
            user = request.user.vendor_profile
            logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")

            # Get all chalets for the authenticated user to display in the navbar
            all_chalets = Chalet.objects.filter(vendor=user,status="active")

            # Get selected chalet or default to the first one
            chalet_id = request.GET.get('chalet_id')
            logger.info(f"Requested chalet ID: {chalet_id}")
            if chalet_id:
                chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user,status="active")

            if chalet:
                # Check chalet approval status
                if not chalet.post_approval:
                    logger.info(f"Chalet {chalet.id} requires post-approval steps.")
                    return redirect(f'/chalets/ammenities/?chalet_id={chalet.id}')
                elif chalet.approval_status == "approved":
                    confirmed_bookings = ChaletBooking.objects.filter(
                        chalet=chalet, checkout_date__gte=current_date, status__in=["pending","booked","confirmed","check-in"]
                    ).order_by("-id")
                    logger.info(f"Fetched {confirmed_bookings.count()} confirmed bookings for chalet: {chalet.id}")

                    # Fetch counts for past and canceled bookings
                    past_bookings_count = ChaletBooking.objects.filter(
                        chalet=chalet, checkout_date__lte=current_date, status__in=["completed"]
                    ).count()
                    cancelled_bookings_count = ChaletBooking.objects.filter(
                        chalet=chalet, status__in=["cancelled","rejected","expired"]
                    ).count()

                    # Filter bookings by date range and status
                    from_date = request.GET.get('fromDate')
                    to_date = request.GET.get('toDate')
                    # status_type = request.POST.getlist('statusType')
                    # status_type = request.POST.get('statusType')
                    status_type = request.GET.get('statusType', '')  # Get the 'data' parameter from the URL
                    
                    print(f"\n\n\n\n\n\n\n\n\n\n\n\n{status_type}\n\n\n\n\n\n\n\n\n\n")
                    print(f"\n\n\n\n\n\n\n\n\n\n\n\n{confirmed_bookings}\n\n\n\n\n\n\n\n\n\n")
                    
                    logger.info(f"Initial confirmed bookings count: {confirmed_bookings.count()}")
                    if from_date and to_date:
                        confirmed_bookings = confirmed_bookings.filter(
                            checkin_date__gte=from_date, checkout_date__lte=to_date
                        ).order_by("-id")
                        logger.info(f"Filtered bookings count after applying fromDate and toDate: {confirmed_bookings.count()}")
                    if from_date:
                        confirmed_bookings = confirmed_bookings.filter(checkin_date__gte=from_date).order_by("-id")
                        logger.info(f"Filtered bookings count after applying fromDate only: {confirmed_bookings.count()}")
                    if to_date:
                        confirmed_bookings = confirmed_bookings.filter(checkout_date__lte=to_date).order_by("-id")
                        logger.info(f"Filtered bookings count after applying toDate only: {confirmed_bookings.count()}")

                    if status_type and status_type != "Status Type":
                        confirmed_bookings = confirmed_bookings.filter(status=status_type).order_by("-id")
                        logger.info(f"Filtered bookings count after applying statusType: {confirmed_bookings.count()}")

                    # Pagination
                    logger.info(f"Before paginated data : {confirmed_bookings.count()}")
                    print(f"\n\n\n\n\n\n\n\n\n Before paginated data : {confirmed_bookings} \n\n\n\n\n\n\n\n\n")
                    paginator = Paginator(confirmed_bookings, 15)
                    page = request.GET.get('page', 1)
                    try:
                        bookings_page = paginator.page(page)
                        logger.info(f"Paginated bookings - Page: {bookings_page}")
                    except PageNotAnInteger:
                        logger.warning("Page not an integer. Defaulting to page 1.")
                        bookings_page = paginator.page(1)
                    except EmptyPage:
                        logger.warning("Page out of range. Displaying last page.")
                        bookings_page = paginator.page(paginator.num_pages)

                    # Prepare context
                    context = {
                        "booking_data": bookings_page,
                        "bookings_page_length": len(confirmed_bookings),
                        "selected_chalet": chalet,
                        "chalets": all_chalets,
                        "past": past_bookings_count,
                        "cancelled": cancelled_bookings_count,
                        "LANGUAGES": settings.LANGUAGES,
                    }
                    return render(
                        request, template, context=context
                    )

                else:
                    if chalet.approval_status == "rejected":
                        messages.error(request, _('Your chalet was rejected.'))
                        return redirect('loginn')
                    else:
                        messages.error(request, _('Your chalet is pending approval.'))
                        return render(request, 'chalets_accounts/pending_hotel.html')
            else:
                logger.info(f"Chalet not found")
                return redirect('loginn')
        except Chalet.DoesNotExist:
            logger.error(f"Chalet not found for vendor: {request.user.id} with chalet ID: {chalet_id}")
            messages.error(request, _("Chalet not found."))
            return redirect('loginn')
        except Exception as e:
            print(f"\n\n\n\n\n\n\n\n\n\n\n\n{e}\n\n\n\n\n\n\n\n\n\n")
            logger.exception(f"Unexpected error in ChaletBookingView: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')

    def post(self, request, *args, **kwargs):
        try:
            logger.info("Processing POST request for ChaletBookingView.")

            from_date = request.POST.get("from_date")
            to_date = request.POST.get("to_date")
            # status_type = request.POST.getlist('status_type')
            status_type = request.POST.get('status_type')
            chalet_id = request.POST.get('chalet_id')
            booking_section = request.POST.get("active_button_id")
            print(f"\n\n\n\n\n\n\n\n\n\n\nstatus_type------>>>>>>>>>>>>>-------{status_type}\n\n\n\n\n\n\n\n")
            logger.info(f"POST parameters received - From Date: {from_date}, To Date: {to_date}, Status Type: {status_type}, Chalet ID: {chalet_id}, Active Button: {booking_section}")

            # Fetch vendor profile
            user = VendorProfile.objects.get(user=request.user)
            logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")

            # Fetch the chalet
            chalet = Chalet.objects.filter(id=chalet_id, vendor=user.id).first()
            if not chalet:
                logger.warning(f"No chalet found for vendor {user.id} with ID {chalet_id}")
                return render(request, "chalets_accounts/chalet_booking_management.html", {"error": _("Chalet not found.")})
            logger.info(f"Chalet found: {chalet.id} ({chalet.name})")

            bookings = ChaletBooking.objects.filter(chalet=chalet.id).order_by("-id")
            logger.info(f"Initial bookings fetched: {bookings.count()}")

            # Filter bookings based on section
            if booking_section == "upcoming_bookings_btn":
                bookings = bookings.filter(checkout_date__gte=timezone.now().date(), status__in=["pending","booked","confirmed","check-in"]).order_by("-id")
                logger.info(f"Filtered bookings for 'upcoming_bookings_btn': {bookings.count()}")
            elif booking_section == "past_bookings_btn":
                bookings = bookings.filter(checkout_date__lte=timezone.now().date(),status__in=["completed"]).order_by("-id")
                logger.info(f"Filtered bookings for 'past_bookings_btn': {bookings.count()}")
            else:
                bookings = bookings.filter(status__in=["cancelled","rejected","expired"]).order_by("-id")
                logger.info(f"Filtered bookings for 'cancelled_bookings_btn': {bookings.count()}")

            # Filter by date range
            if from_date and to_date:
                bookings = bookings.filter(checkin_date__gte=from_date, checkout_date__lte=to_date)
                logger.info(f"Filtered bookings by date range ({from_date} to {to_date}): {bookings.count()}")
            elif from_date:
                bookings = bookings.filter(checkin_date__gte=from_date)
                logger.info(f"Filtered bookings by 'from_date' ({from_date}): {bookings.count()}")
            elif to_date:
                bookings = bookings.filter(checkout_date__lte=to_date)
                logger.info(f"Filtered bookings by 'to_date' ({to_date}): {bookings.count()}")

            # Filter by status type
            if status_type and status_type != "Status Type":
                bookings = bookings.filter(status=status_type)
                logger.info(f"Filtered bookings by status type ({status_type}): {bookings.count()}")

            # Pagination
            page = request.GET.get('page', 1)
            paginator = Paginator(bookings, 15)
            try:
                bookings_page = paginator.page(page)
                logger.info(f"Paginated bookings - Page: {page}")
            except PageNotAnInteger:
                bookings_page = paginator.page(1)
                logger.warning("Page not an integer. Defaulting to page 1.")
            except EmptyPage:
                bookings_page = paginator.page(paginator.num_pages)
                logger.warning("Page out of range. Displaying last page.")

            # Render response
            logger.info("Rendering chalet booking management page with filtered bookings.")
            return render(
                request,
                "chalets_accounts/chalet_booking_management.html",
                {"booking_data": bookings_page},
            )
        except VendorProfile.DoesNotExist:
            logger.error(f"VendorProfile not found for user: {request.user.id} ({request.user.username})")
            return render(request, "chalets_accounts/chalet_booking_management.html", {"error": _("Vendor profile not found.")})
        except Exception as e:
            logger.exception(f"Unexpected error in ChaletBookingView POST: {e}")
            return render(request, "chalets_accounts/chalet_booking_management.html", {"error": _("An unexpected error occurred.")})

    

class ChaletBookingDetail(View):
    def get(self, request, *args, **kwargs):
        booking_detail_id = kwargs.get("pk")
        try:
            booking_details = Bookedrooms.objects.get(pk=booking_detail_id)
           
            data = {
                "guest_name": booking_details.booking.booking_fname,
                "contact_number": booking_details.booking.booking_mobilenumber,
                "property_type": booking_details.booking.property_type,
                "check_in": booking_details.booking.checkin_date,
                "check_out": booking_details.booking.checkout_date,
                "status": booking_details.status,
            }
            return JsonResponse(data)
        except Booking.DoesNotExist:
            logger.info("Booking not found")
            return render(request, 'chalets_accounts/404.html')
    def post(self, request, *args, **kwargs):
        booking_detail_id = kwargs.get("pk")
        booking_details = get_object_or_404(Bookedrooms, pk=booking_detail_id)

        booking_details.booking.booking_fname = request.POST.get("guest_name")
        booking_details.booking.booking_mobilenumber = request.POST.get("contact_number")

        booking_details.booking.checkin_date = request.POST.get("check_in_date")
        booking_details.booking.checkout_date = request.POST.get("check_out_date")
        booking_details.status = request.POST.get("booking_status")
        booking_details.booking.property_type = request.POST.get("property_type")
        booking_details.save()
        booking_details.booking.save()
        return JsonResponse({"message": _("Booking updated successfully")})


class ChaletPastBookingsView(View):
    def get(self, request):
        try:
            logger.info("Processing GET request for ChaletPastBookingsView.")
        
            current_date = timezone.now().date()

            # Fetch chalet ID and retrieve the chalet object
            chalet_id = request.GET.get('chalet_id')
            if not chalet_id:
                logger.warning("Chalet ID is missing in the GET request.")
                return render(request, "chalets_accounts/chalet_booking_management.html", {"error": _("Chalet ID is required.")})

            chalet = Chalet.objects.filter(id=chalet_id).first()
            if not chalet:
                logger.warning(f"Chalet not found for ID: {chalet_id}")
                return render(request, "chalets_accounts/chalet_booking_management.html", {"error": _("Chalet not found.")})

            logger.info(f"Chalet retrieved successfully: ID={chalet.id}, Name={chalet.name}")

            # Fetch bookings for the chalet
            bookings = ChaletBooking.objects.filter(chalet=chalet.id)
            logger.info(f"Total bookings found for Chalet ID {chalet_id}: {bookings.count()}")

            # Filter for past bookings
            past_bookings = bookings.filter(checkout_date__lte=current_date,status__in=["completed"]).order_by("-id")
            logger.info(f"Filtered past bookings: {past_bookings.count()} (Current date: {current_date})")
            
            try:
                past_bookings = booking_filters(request,logger,past_bookings)
            except Exception as e:
                logger.info(f"\n\n function booking_filters inside ChaletPastBooking View: {past_bookings}")
            # Pagination
            page = request.GET.get('page', 1)
            paginator = Paginator(past_bookings, 15)
            try:
                booking_data = paginator.page(page)
                logger.info(f"Paginated past bookings - Page: {page}")
            except PageNotAnInteger:
                booking_data = paginator.page(1)
                logger.warning("Page not an integer. Defaulting to page 1.")
            except EmptyPage:
                booking_data = paginator.page(paginator.num_pages)
                logger.warning("Page out of range. Displaying last page.")

            # Render response
            logger.info("Rendering chalet booking management page with past bookings.")
            return render(
                request,
                "chalets_accounts/chalet_booking_management.html",
                {"booking_data": booking_data},
            )
        except Exception as e:
            logger.exception(f"Unexpected error in ChaletPastBookingsView GET: {e}")
            return render(request, "chalets_accounts/chalet_booking_management.html", {"error": _("An unexpected error occurred.")})


class ChaletCancelledAppointmentsView(View):
    def get(self, request):
        try:
            logger.info("Processing GET request for ChaletCancelledAppointmentsView.")

            # Fetch chalet ID from request and validate
            chalet_id = request.GET.get('chalet_id')
            if not chalet_id:
                logger.warning("Chalet ID is missing in the GET request.")
                return render(request, "chalets_accounts/chalet_booking_management.html", {"error": _("Chalet ID is required.")})

            # Retrieve chalet object
            chalet = Chalet.objects.filter(id=chalet_id).first()
            if not chalet:
                logger.warning(f"Chalet not found for ID: {chalet_id}")
                return render(request, "chalets_accounts/chalet_booking_management.html", {"error": _("Chalet not found.")})

            logger.info(f"Chalet retrieved successfully: ID={chalet.id}, Name={chalet.name}")

            # Fetch all bookings for the chalet
            bookings = ChaletBooking.objects.filter(chalet=chalet.id)
            logger.info(f"Total bookings found for Chalet ID {chalet_id}: {bookings.count()}")

            # Filter cancelled appointments
            cancelled_appointments = bookings.filter(status__in=["cancelled","rejected","expired"]).order_by("-id")
            logger.info(f"Filtered cancelled appointments: {cancelled_appointments.count()}")
            
            try:
                cancelled_appointments = booking_filters(request,logger,cancelled_appointments)
            except Exception as e:
                logger.info(f"\n\n function booking_filters inside ChaletCancelledBooking View: {cancelled_appointments}")

            # Pagination
            page = request.GET.get('page', 1)
            paginator = Paginator(cancelled_appointments, 15)
            try:
                booking_data = paginator.page(page)
                logger.info(f"Paginated cancelled appointments - Page: {page}")
            except PageNotAnInteger:
                booking_data = paginator.page(1)
                logger.warning("Page not an integer. Defaulting to page 1.")
            except EmptyPage:
                booking_data = paginator.page(paginator.num_pages)
                logger.warning("Page out of range. Displaying last page.")

            # Render response
            logger.info("Rendering chalet booking management page with cancelled appointments.")
            return render(
                request,
                "chalets_accounts/chalet_booking_management.html",
                {"booking_data": booking_data},
            )
        except Exception as e:
            logger.exception(f"Unexpected error in ChaletCancelledAppointmentsView GET: {e}")
            return render(request, "chalets_accounts/chalet_booking_management.html", {"error": _("An unexpected error occurred.")})


class ChaletTransactionDetails(View):
    def get(self, request):
        if not request.user.is_authenticated:
            request.session.flush()  
            return redirect('loginn')  
         
        user_language = request.LANGUAGE_CODE
        activate(user_language)
        try:
            user = VendorProfile.objects.get(user=request.user)
        except (VendorProfile.DoesNotExist):
            logger.info("user  doesnot exist at the chalet-transaction section")
            return render(request, 'chalets_accounts/404.html')        
        category = Categories.objects.get(category="CHALET")
        chalets = Chalet.objects.filter(vendor=user.id)
        if not chalets.filter(approval_status="approved").exists():
            if chalets.filter(approval_status="rejected").exists():
                messages.error(request, _('Your chalet was rejected.'))
                return redirect('loginn')

        # Get the selected chalet ID from request
        chalet_id = request.GET.get('chalet_id')
        logger.info(f"----chaletid { chalet_id }")
        if chalet_id:
            selected_chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id)
        else:
            selected_chalet = chalets.first()  # Default to the first chalet if none selected

        # Check approval status of the selected chalet
        if selected_chalet.approval_status != "approved":
            return render(request, 'chalets_accounts/pending_hotel.html')

        if not selected_chalet.post_approval:
            return redirect(f'/chalets/ammenities/?chalet_id={selected_chalet.id}')  # Redirect with chalet_id

        # Fetch transactions only for the selected chalet
        transactions = ChaletBooking.objects.filter(
            chalet=selected_chalet.id,
        ).select_related('transaction').prefetch_related('transaction__vendor_transaction','transaction__admin_transaction').order_by('-modified_date')
        transaction_status = Transaction.TRANSACTION_STATUS_CHOICES

        # Attach first booking information to each transaction
        # for transaction in transactions:
        #     transaction.first_booking = transaction.bookings.first() if transaction.bookings.exists() else None

        page = request.GET.get('page', 1)
        paginator = Paginator(transactions, 15) 
        try:
            transactions_page = paginator.page(page)
        except PageNotAnInteger:
            transactions_page = paginator.page(1)
        except EmptyPage:
            transactions_page = paginator.page(paginator.num_pages)

        payment_choices = list(PaymentType.objects.filter(status='active', is_deleted=False)
                       .exclude(name__isnull=True)
                       .exclude(name="")
                       .values_list('name', flat=True))
        if isinstance(payment_choices[0], str):  # If it's a list of strings, convert it to tuples
            payment_choices = [(choice, choice) for choice in payment_choices]  
        context = {
            "bookings": transactions_page,
            "payment_choices": payment_choices,
            "chalets": chalets,
            "transaction_status":transaction_status,
            "selected_chalet": selected_chalet,
            "show_pagination": paginator.num_pages > 1, 
            "LANGUAGES": settings.LANGUAGES
        }
        return render(
            request,
            template_name="chalets_accounts/chalet_transaction_detail.html",
            context=context,
        )


    def post(self, request):
        page = request.POST.get('page', 1)
        from_date = request.POST.get("from_date")
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
        except (VendorProfile.DoesNotExist):
            logger.info("user  doesnot exist at the chalet-transaction section")
            return render(request,'accounts/404.html')
        category = Categories.objects.get(category="CHALET")
        chalet_id = request.GET.get('chalet_id')
        logger.info(f"----chaletid { chalet_id }")
        if chalet_id:
           chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id)
        else:
            chalet = Chalet.objects.filter(vendor=user.id, category=category).first()
        logger.info(f"-----{chalet}")
        transactions = ChaletBooking.objects.filter(
            chalet=chalet.id,
        ).select_related('transaction').prefetch_related('transaction__vendor_transaction','transaction__admin_transaction').order_by('-modified_date')
        transactions = transaction_list_filter(transactions = transactions, from_date = from_date,  to_date = to_date, payment_method = payment_method, transaction_status=transaction_status, booking_status=booking_status)
      
        
        payment_choices = list(PaymentType.objects.filter(status='active', is_deleted=False)
                       .exclude(name__isnull=True)
                       .exclude(name="")
                       .values_list('name', flat=True))
        if isinstance(payment_choices[0], str):  # If it's a list of strings, convert it to tuples
            payment_choices = [(choice, choice) for choice in payment_choices]   
        paginator = Paginator(transactions, 15) 
        try:
            transactions_page = paginator.page(page)
        except PageNotAnInteger:
            transactions_page = paginator.page(1)
        except EmptyPage:
            transactions_page = paginator.page(paginator.num_pages)
        context = {"bookings": transactions_page, "payment_choices": payment_choices}
        return render(
            request,
            template_name="chalets_accounts/chalet_transaction_detail.html",
            context=context,
        )


@method_decorator(vendor_required, name='dispatch')          
class ChaletCheckPromoCodeUniqe(View):
    def post(self, request):
        try:
            logger.info("Checking the post request in promocodeunique")
            promo_code = request.POST.get('promo_code')
            chalet_id= request.POST.get('chalet_id')
            if promo_code and chalet_id:
                logger.info(f"chalet:{chalet_id}")
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                print(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                chalet = Chalet.objects.filter(vendor=user.id,id=chalet_id).first()
                if not chalet :
                    logger.warning(f"No chalet found for vendor {user.id}")
                    messages.error(request, _("No chalet found. Please try again."))
                    return redirect('loginn') 
                else:
                    logger.info("chalet found")
                    try:
                        get_promocode = Promotion.objects.filter(chalet=chalet,promo_code=promo_code)
                        if get_promocode:
                            logger.info(f"Promocode is not Unique")
                            return JsonResponse({'exists': True})
                        else:
                            logger.info(f"Promocode is Unique")
                    except Promotion.DoesNotExist:
                        logger.info(f"Promocode is Unique")
            else:
                logger.warning(f"No promocode received for ChaletOfferPromotion ")
                return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("Chalet promocode and chalet id Needed.")}) 
        except Exception as e:
            logger.exception(f"Unexpected error in ChaletReviewRatingView: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')
    
@method_decorator(vendor_required, name='dispatch')          
class ChaletOfferPromotions(View):
    template_name = "chalets_accounts/chalet_offer_promotion.html"
    def get(self, request):
        chalet = None
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
            user = request.user.vendor_profile
            logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")

            # Get all chalets for the authenticated user to display in the navbar
            all_chalets = Chalet.objects.filter(vendor=user,status="active")

            # Get selected chalet or default to the first one
            chalet_id = request.GET.get('chalet_id')
            print('chalet',chalet_id)
            logger.info(f"Requested chalet ID: {chalet_id}")
            if chalet_id:
                chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id)
                print('chalet found',chalet)
            if chalet:
                # Check chalet approval status
                if not chalet.post_approval:
                    logger.info(f"Chalet {chalet.id} requires post-approval steps.")
                    return redirect(f'/chalets/ammenities/?chalet_id={chalet_id}')
                elif chalet.approval_status == "approved":
                    promo = Promotion.objects.filter(Q(chalet=chalet) | Q(multiple_chalets=chalet),status='active',category="common").order_by('-id')
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
                            "chalets": all_chalets,
                            "selected_chalet": chalet,
                            "LANGUAGES": settings.LANGUAGES
                        },
                    )
                else:
                    if chalet.approval_status == "rejected":
                        messages.error(request, _('Your chalet was rejected.'))
                        return redirect('loginn')
                    else:
                        messages.error(request, _('Your chalet is pending approval.'))
                        return render(request, 'chalets_accounts/pending_hotel.html')
        except Chalet.DoesNotExist:
            logger.error(f"Chalet not found for vendor: {request.user.id} with chalet ID: {chalet_id}")
            messages.error(request, _("Chalet not found."))
            return redirect('loginn')
        except Exception as e:
            logger.exception(f"Unexpected error in ChaletReviewRatingView: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')    



  # Redirect with chalet_id

    def post(self, request):
        try:
            logger.info("Processing POST request for ChaletreviewRatingView.")
            offer_name = request.POST.get('offer_name')
            description = request.POST.get('description')
            category = request.POST.get('category')
            start_date = request.POST.get('validity_from')
            chalet_id = request.GET.get('chalet_id')
            end_date = request.POST.get('validity_to')
            discount_percentage = request.POST.get('discount_percentage')
            discount_percentage = discount_percentage if discount_percentage and discount_percentage.strip() != "" else None
            logger.info(f"POST parameters received - Offer Name: {offer_name},Description: {description},: Category :{category},  Start Date: {start_date},  End Date: {end_date},Chalet-ID :{chalet_id}")
            user = request.user.vendor_profile
            logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
            print(f"VendorProfile found for user: {request.user.id} ({request.user.username})")

            # Fetch the chalet
            chalet = Chalet.objects.filter(id=chalet_id, vendor=user.id).first()
            if not chalet:
                logger.warning(f"No chalet found for vendor {user.id} with ID {chalet_id}")
                messages.error(request, _("No chalet found. Please try again."))
                return redirect('loginn') 
            else:
                logger.info(f"Chalet found: {chalet.id} ({chalet.name})")  
                
                # Initialize fields based on category
                minimum_spend= request.POST.get('minimum_spend') if category == 'common' else None
                promo_code = request.POST.get('promo_code') if category == 'promo_code' else None
                max_uses = request.POST.get('max_uses') if category == 'promo_code' else None
                targeted_type = request.POST.get('targeted_type') if category == 'targeted_offers' else None
                occasion_name = request.POST.get('occasion_name') if category == 'seasonal_event' else None
                points_required = request.POST.get('points_required') if category == 'loyalty_program' else None
                targeted_type = targeted_type if targeted_type and targeted_type.strip() != "" else 'common'
                promo_validity_from = request.POST.get('promo_validity_from') if category == 'promo_code' else None
                promo_validity_to = request.POST.get('promo_validity_to') if category == 'promo_code' else None
                
            # Initialize date variables
                start_date_value = None
                end_date_value = None
                # Validate and parse date formats if provided
                if category == "promo_code":
                    logger.info("selected category is PROMO CODE")
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
                    logger.info(f"Promo code validity starts from:{start_date_value} to:{ end_date_value} ")
                else:
                    logger.info(f"selected category is {category}")
                    if start_date:  # Check if start_date is not empty
                        try:
                            start_date_value = datetime.strptime(start_date, '%Y-%m-%d').date()
                        except ValueError:
                            raise ValidationError("Start date must be in YYYY-MM-DD format.")
                    
                    if end_date:  # Check if end_date is not empty
                        try:
                            end_date_value = datetime.strptime(end_date, '%Y-%m-%d').date()
                        except ValueError:
                            raise ValidationError("End date must be in YYYY-MM-DD format.")

                # Creating a new Promotion instance
                promotion = Promotion(
                    title=offer_name,
                    category=category,
                    description=description,
                    discount_percentage=discount_percentage,
                    promo_code=promo_code,
                    max_uses=max_uses,
                    occasion_name=occasion_name,
                    points_required=points_required,
                    chalet= chalet,
                    start_date=start_date_value,  
                    end_date=end_date_value,
                    minimum_spend=minimum_spend, 
                    promotion_type = targeted_type,
                    source='chalet'
                )

                promotion.save()
                return JsonResponse({"message": _("Offer saved successfully.")})

        except Exception as e:
            logger.exception(f"Unexpected error in ChaletBookingView POST: {e}")
            return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("An unexpected error occurred.")})
@method_decorator(vendor_required, name='dispatch')          
class ChaletOfferPromotionsDetailView(View):
    def get(self, request, *args, **kwargs):
        try:
            logger.info("Processing GET request for ChaletOfferPromotionsDetailView.")
            offer_id = kwargs.get("pk")
            chalet_id = kwargs.get("chalet_id")
            if offer_id and chalet_id:
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                print(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                chalet = Chalet.objects.filter(vendor=user.id,id=chalet_id).first()
                if not chalet :
                    logger.warning(f"No chalet found for vendor {user.id}")
                    messages.error(request, _("No chalet found. Please try again."))
                    return redirect('loginn') 
                else:
                    try:
                        logger.info(f"Chalet found: {chalet.id} ({chalet.name})")  
                        offer = Promotion.objects.get(pk=offer_id)
                        data = {
                        "offer_name": offer.title,
                            "description": offer.description,
                            "category":offer.category,
                            "discount_percentage": offer.discount_percentage,  
                            "minimum_spend":offer.minimum_spend,
                            "validity_from": offer.start_date,
                            "validity_to": offer.end_date,
                            "promo_code":offer.promo_code,
                            "max_uses":offer.max_uses,
                            "targeted_offer_type":offer.promotion_type,
                            "occasion_name":offer.occasion_name,
                            "points_required":offer.points_required
                        }
                        return JsonResponse(data)
                    except Promotion.DoesNotExist:
                        logger.info("promotion not found")
                        return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("Chalet Offerpromotion ID doesn't exist.")}) 
            else:
                logger.warning(f"No ID received for ChaletOfferPromotion ")
                return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("Chalet Offerpromotion ID Needed.")}) 
        except Exception as e:
            logger.exception(f"Unexpected error in  ChaletOfferPromotionsDetailView {e}")
            return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("An unexpected error occurred.")})
    def post(self, request, *args, **kwargs):
        try:
            logger.info("Processing POST request for ChaletOfferPromotionsDetailView.")
            offer_id = kwargs.get("pk")
            chalet_id = kwargs.get("chalet_id")
            if offer_id and chalet_id:
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                print(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                chalet = Chalet.objects.filter(vendor=user.id,id= chalet_id).first()
                if not chalet :
                    logger.warning(f"No chalet found for vendor {user.id}")
                    messages.error(request, _("No chalet found. Please try again."))
                    return redirect('loginn') 
                else:
                    try:
                        logger.info(f"Chalet found: {chalet.id} ({chalet.name})")  
                        promotion = get_object_or_404(Promotion, pk=offer_id)
                        offer_name = request.POST.get('offer_name')
                        description = request.POST.get('description')
                        category = request.POST.get('category')
                        start_date = request.POST.get('validity_from')
                        end_date = request.POST.get('validity_to')
                        discount_percentage = request.POST.get('discount_percentage')
                        discount_percentage = discount_percentage if discount_percentage and discount_percentage.strip() != "" else None
                        logger.info(f"POST parameters received - Offer Name: {offer_name},Description: {description},: Category :{category},  Start Date: {start_date},  End Date: {end_date}")

                      
                        

                        minimum_spend = request.POST.get('minimum_spend') if category == 'common' else None
                        promo_code = request.POST.get('promo_code') if category == 'promo_code' else None
                        max_uses = request.POST.get('max_uses') if category == 'promo_code' else None
                        targeted_type = request.POST.get('targeted_type') if category == 'targeted_offers' else None
                        occasion_name = request.POST.get('occasion_name') if category == 'seasonal_event' else None
                        points_required = request.POST.get('points_required') if category == 'loyalty_program' else None
                        targeted_type = targeted_type if targeted_type and targeted_type.strip() != "" else 'common'
                        promo_validity_from = request.POST.get('promo_validity_from') if category == 'promo_code' else None
                        promo_validity_to = request.POST.get('promo_validity_to') if category == 'promo_code' else None
                        start_date_value = None
                        end_date_value = None
                        if category == "promo_code":
                            logger.info(f"selected category is PROMO CODE")
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
                        promotion.promotion_type = targeted_type

                        promotion.save()
                        logger.info("promotion saved succesfully")

                        return JsonResponse({"message": _("Offer saved successfully.")})
                    except Promotion.DoesNotExist:
                        logger.info("promotion not found")
                        return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("Chalet Offerpromotion ID doesn't exist.")})
            else:
                logger.warning(f"No ID received for ChaletOfferPromotion ")
                return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("Chalet Offerpromotion ID Needed.")}) 
        
        except Exception as e:
            logger.exception(f"Unexpected error in  ChaletOfferPromotionsDetailView POST: {e}")
            return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("An unexpected error occurred.")})


@method_decorator(vendor_required, name='dispatch')          
class ChaletOfferPromotionsDeleteView(View):
    def delete(self, request, *args, **kwargs):
        try:
            offer_id = kwargs.get("pk") 
            chalet_id = kwargs.get("chalet_id")
            if offer_id and chalet_id:
                logger.info(f"chalet:{chalet_id}")
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                print(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                chalet = Chalet.objects.filter(vendor=user.id,id=chalet_id).first()
                if not chalet :
                    logger.warning(f"No chalet found for vendor {user.id}")
                    messages.error(request, _("No chalet found. Please try again."))
                    return redirect('loginn') 
                else:
                    try:
                        offer = Promotion.objects.get(pk=offer_id)
                        offer.status='deleted'
                        offer.save()
                        logger.info(f"promotion ID: {offer_id} deleted successfully")  
                        return JsonResponse({"message": _("Offer deleted successfully")})                 
                    except Promotion.DoesNotExist:
                        logger.info("promotion not found")
                        return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("Chalet Offerpromotion ID doesn't exist.")})
            else:
                logger.warning(f"No ID received for ChaletOfferPromotion ")
                return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("Chalet Offerpromotion ID Needed.")}) 
        
        except Exception as e:
            logger.exception(f"Unexpected error in  ChaletOfferPromotionsDetailView POST: {e}")
            return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("An unexpected error occurred.")})
@method_decorator(vendor_required, name='dispatch')          
class ChaletOfferPromotionsFilterView(View):
    def get(self, request):
        try:
            logger.info("Processing GET request for ChaletOfferPromotionsFilterView.")
            discount = request.GET.get("discount")
            chalet_id = request.GET.get('chalet_id')
            page = request.GET.get('page', 1)  
            if discount:
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                print(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                chalet = Chalet.objects.filter(vendor=user.id,id=chalet_id).first()
                if not chalet :
                    logger.warning(f"No chalet found for vendor {user.id}")
                    messages.error(request, _("No chalet found. Please try again."))
                    return redirect('loginn') 
                else:  
                    logger.info(f"Chalet found")
                    try:          
                        promo = Promotion.objects.filter(Q(chalet=chalet) | Q(multiple_chalets=chalet),status='active',category=discount).order_by('-id')
                        paginator = Paginator(promo, 10)
                        try:
                            offers = paginator.page(page)
                        except PageNotAnInteger:
                            offers = paginator.page(1)  
                        except EmptyPage:
                            offers = paginator.page(paginator.num_pages) 
                        return render(
                            request,
                            template_name="chalets_accounts/chalet_offer_promotion.html",
                            context={"offers": offers, "discount": discount},
                        )
                    except Promotion.DoesNotExist:
                        logger.info("promotion not found")
                        return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("Chalet Offerpromotion doesn't exist.")})
            else:
                logger.warning(f"Discount needed")
                return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("Discount Needed.")}) 
        except Exception as e:
            logger.exception(f"Unexpected error in  ChaletOfferPromotionsDetailView POST: {e}")
            return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("An unexpected error occurred.")})

    def post(self, request):
        try:
            discount = request.POST.get("discount")
            chalet_id = request.POST.get('chalet_id')
            page = request.POST.get('page', 1)  
            if discount:
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                print(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                chalet = Chalet.objects.filter(vendor=user.id,id=chalet_id).first()
                if not chalet :
                    logger.warning(f"No chalet found for vendor {user.id}")
                    messages.error(request, _("No chalet found. Please try again."))
                    return redirect('loginn') 
                else:  
                    try:          
                        promo = Promotion.objects.filter(Q(chalet=chalet) | Q(multiple_chalets=chalet),status='active')
                        promo = promo.filter(category=discount).order_by('-id')
                        paginator = Paginator(promo, 10)
                        try:
                            offers = paginator.page(page)
                        except PageNotAnInteger:
                            offers = paginator.page(1)  
                        except EmptyPage:
                            offers = paginator.page(paginator.num_pages) 
                        return render(
                            request,
                            template_name="chalets_accounts/chalet_offer_promotion.html",
                            context={"offers": offers, "discount": discount},
                        )
                    except Promotion.DoesNotExist:
                        logger.info("promotion not found")
                        return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("Chalet Offerpromotion doesn't exist.")})
            else:
                logger.warning(f"Discount needed")
                return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("Discount Needed.")}) 
        
        except Exception as e:
            logger.exception(f"Unexpected error in  ChaletOfferPromotionsDetailView POST: {e}")
            return render(request, "chalets_accounts/chalet_offer_promotion.html", {"error": _("An unexpected error occurred.")})



# class ChaletPromoCode(View):
#     def get(self, request):
#         if not request.user.is_authenticated:
#             request.session.flush()  
#             return redirect('loginn')
        
#         try:
#             user = VendorProfile.objects.get(user=request.user)
#             chalet = Chalet.objects.filter(vendor=user.id)
#             if not chalet.filter(approval_status="approved").exists():
#                 if chalet.filter(approval_status="rejected").exists():
#                     messages.error(request, 'Your chalet was rejected.')
#                     return redirect('loginn')
#         except VendorProfile.DoesNotExist:
#             return redirect('loginn')  
#         except Chalet.DoesNotExist:
#             messages.error(request, 'No chalet found for this vendor.')
#             return redirect('loginn')  
#         chalet_id = request.GET.get('chalet_id')
#         chalets = Chalet.objects.filter(vendor=user.id)
        
#         if chalet_id:
#             selected_chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id)
#         else:
#             selected_chalet = chalets.first()
        
#         promo_obj = PromoCode.objects.filter(chalet=selected_chalet)
#         discount_data = promo_obj.distinct("discount_percentage")

#         # Check approval status of the selected chalet
#         if selected_chalet.approval_status != "approved":
#             return render(request, 'chalets_accounts/pending_hotel.html')       

#         if not selected_chalet.post_approval:
#             return redirect(f'/chalets/ammenities/?chalet_id={selected_chalet.id}')  # Redirect with chalet_id    

#         return render(
#             request,
#             template_name="chalets_accounts/chalet_manage_promo_code.html",
#             context={
#                 "promo_data": promo_obj,
#                 "discount_data": discount_data,
#                 "chalets": chalets,
#                 "selected_chalet": selected_chalet,
#                 "LANGUAGES": settings.LANGUAGES,
#             }
#         )


#     def post(self, request):

#         user = VendorProfile.objects.get(user=request.user)
#         hotel = Chalet.objects.filter(vendor=user.id).first()
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
#         print(promo_obj)

#         return redirect("chalet_promo_code")


# class ChaletPromoCodeEdit(View):
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

#         return redirect("chalet_promo_code")


# class ChaletPromoCodeDelete(View):
#     def post(self, request, *args, **kwargs):
#         id = kwargs.get("pk")
#         PromoCode.objects.get(id=id).delete()
#         return redirect("chalet_promo_code")


# class ChaletPromoCodeFilters(View):
#     def post(self, request):
#         from_date = request.POST.get("from_date")
#         to_date = request.POST.get("to_date")
#         discount = request.POST.get("discount")
#         print(from_date, to_date, discount)

#         user = VendorProfile.objects.get(user=request.user)
#         hotel = Chalet.objects.filter(vendor=user.id).first()
#         promo_obj = PromoCode.objects.filter(hotel=hotel)
#         # category = Categories.objects.get(category="CHALET")
#         # hotel= Hotel.objects.filter(category=category).values_list("id", flat=True)
#         # print(hotel)
#         # promo_obj = PromoCode.objects.filter(hotel_id__in=hotel)

#         if from_date and to_date:

#             promo_obj = promo_obj.filter(
#                 Q(validity_from__lte=to_date) & Q(validity_to__gte=from_date)
#             )

#         elif from_date:
#             print(from_date)
#             promo_obj = promo_obj.filter(validity_to__gte=from_date)

#         elif to_date:
#             print(to_date)
#             promo_obj = promo_obj.filter(validity_from__lte=to_date)

#         elif discount:
#             promo_obj = promo_obj.filter(discount_percentage=discount)

#         return render(
#             request,
#             template_name="chalets_accounts/chalet_manage_promo_code.html",
#             context={"promo_data": promo_obj},
#         )

@method_decorator(vendor_required, name='dispatch')
class ChaletRefundCancellation(View):
    def get(self, request, *args, **kwargs):
        user = request.user.vendor_profile
        chalets = Chalet.objects.filter(vendor=user)
        if not chalets.filter(approval_status="approved").exists():
            if chalets.filter(approval_status="rejected").exists():
                messages.error(request, _('Your chalet was rejected.'))
                return redirect('loginn')
        chalet_id = request.GET.get('chalet_id')
        if chalet_id:
            selected_chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id)
        else:
            selected_chalet = chalets.first()
        logger.info(f"-----{selected_chalet}")
        booking_transactions = ChaletBooking.objects.filter(
            chalet=selected_chalet
        ).values_list("transaction_id", flat=True)
        page = request.GET.get("page", 1)

        logger.info(f"Chalet Booking Transactions: {booking_transactions}")

        refund_transactions = RefundTransaction.objects.filter(transaction_id__in=booking_transactions).order_by("-id")

        logger.info(f"Chalet Refund Transactions: {refund_transactions}")

        payment_choices = PaymentType.objects.filter(is_deleted=False, status="active").values("name", "name_arabic")

        transaction_choices = RefundTransaction.REFUND_STATUS_CHOICES

        # Check approval status of the selected chalet
        if selected_chalet.approval_status != "approved":
            return render(request, 'chalets_accounts/pending_hotel.html')   
        
        if not selected_chalet.post_approval:
            return redirect(f'/chalets/ammenities/?chalet_id={selected_chalet.id}')  # Redirect with chalet_id   
        paginator = Paginator(refund_transactions, 15)
        try:
            refund_trans = paginator.page(page)
        except PageNotAnInteger:
            refund_trans = paginator.page(1)  
        except EmptyPage:
            refund_trans = paginator.page(paginator.num_pages)  
        
            
        return render(
            request,
            "chalets_accounts/chalet_refund_and_cancellation.html",
            {
                "refunds": refund_trans,
                "booking_source": payment_choices,
                "cancel_status": transaction_choices,
                "chalets": chalets,
                "selected_chalet": selected_chalet,
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

        # Logging for debugging
        logger.info(f"Converted from_date: {from_date}, Type: {type(from_date)}")
        logger.info(f"Converted to_date: {to_date}, Type: {type(to_date)}")

        user = request.user.vendor_profile
        chalets = Chalet.objects.filter(vendor=user)
        if not chalets.filter(approval_status="approved").exists():
            if chalets.filter(approval_status="rejected").exists():
                messages.error(request, _('Your chalet was rejected.'))
                return redirect('loginn')
        chalet_id = request.GET.get('chalet_id')
        if chalet_id:
            selected_chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id)
        else:
            selected_chalet = chalets.first()
        logger.info(f"-----{selected_chalet}")
        booking_transactions = ChaletBooking.objects.filter(
            chalet=selected_chalet
        ).values_list("transaction_id", flat=True)

        logger.info(f"Chalet Booking Transactions: {booking_transactions}")

        refunds = RefundTransaction.objects.filter(transaction__in=booking_transactions).order_by("-id")

        refund_details = refunds.values("id", "created_at", "transaction", "refund_status")
        logger.info(f"Refund Details (Before Filtering): {list(refund_details)}")

        if from_date and to_date:
            refunds = refunds.filter(created_at__range=[from_date, to_date])
        elif from_date:
            refunds = refunds.filter(created_at__gte=from_date)
        elif to_date:
            refunds = refunds.filter(created_at__lte=to_date)

        refunds = refunds.distinct()

        # Apply additional filters
        if cancel_status:
            refunds = refunds.filter(refund_status=cancel_status)

        if booking_source:
            refunds = refunds.filter(transaction__payment_type__name=booking_source)

        # Log final count of refunds after filtering
        logger.info(f"Total refunds found (after filters): {refunds.count()}")
        paginator = Paginator(refunds, 10)
        try:
            refund_trans = paginator.page(page)
        except PageNotAnInteger:
            refund_trans = paginator.page(1)  
        except EmptyPage:
            refund_trans = paginator.page(paginator.num_pages) 

        return render(
            request,
            template_name="chalets_accounts/chalet_refund_and_cancellation.html",
            context={"refunds": refund_trans},
        )

@method_decorator(vendor_required, name='dispatch')
class ChaletReviewRatings(View):
    def get(self, request): 
        chalet = None
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
            user = request.user.vendor_profile
            logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")

            # Get all chalets for the authenticated user to display in the navbar
            all_chalets = Chalet.objects.filter(vendor=user,status="active")

            # Get selected chalet or default to the first one
            chalet_id = request.GET.get('chalet_id')
            print('chalet',chalet_id)
            logger.info(f"Requested chalet ID: {chalet_id}")
            if chalet_id:
                chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id)
                print('chalet found',chalet)

            if chalet:
                # Check chalet approval status
                if not chalet.post_approval:
                    logger.info(f"Chalet {chalet.id} requires post-approval steps.")
                    return redirect(f'/chalets/ammenities/?chalet_id={chalet_id}')
                elif chalet.approval_status == "approved":
                    reviews = ChaletRecentReview.objects.filter(chalet=chalet).order_by("-date")
                    ratings = ChaletRecentReview.RATING
                    # Pagination
                    page = request.GET.get('page', 1)
                    paginator = Paginator(reviews, 10) 
                    try:
                        review_page = paginator.page(page)
                    except PageNotAnInteger:
                        review_page  = paginator.page(1)
                    except EmptyPage:
                        review_page  = paginator.page(paginator.num_pages)
                    context = {
                        "selected_chalet": chalet,
                        "ratings": ratings,
                        "chalets": all_chalets,
                        "reviews": review_page ,
                        "LANGUAGES": settings.LANGUAGES,
                    }
                    return render(
                        request, "chalets_accounts/chalet_review_rating.html", context=context
                    )
                else:
                    if chalet.approval_status == "rejected":
                        messages.error(request, _('Your chalet was rejected.'))
                        return redirect('loginn')
                    else:
                        messages.error(request, _('Your chalet is pending approval.'))
                        return render(request, 'chalets_accounts/pending_hotel.html')
        except Chalet.DoesNotExist:
            logger.error(f"Chalet not found for vendor: {request.user.id} with chalet ID: {chalet_id}")
            messages.error(request, _("Chalet not found."))
            return redirect('loginn')
        except Exception as e:
            logger.exception(f"Unexpected error in ChaletReviewRatingView: {e}")
            messages.error(request, _("An unexpected error occurred. Please try again."))
            return redirect('loginn')    

    def post(self, request):
        reviews=None
        try:
            logger.info("Processing POST request for ChaletreviewRatingView.")
            page = request.POST.get('page', 1)
            from_date_s = request.POST.get("from_date")
            chalet_id = request.POST.get('chalet_id')
            to_date_p = request.POST.get("to_date")
            review_rating = request.POST.get("review_rating")
            logger.info(f"POST parameters received - From Date: {from_date_s}, To Date: {to_date_p}, Page: {page},  review_rating: {review_rating},  Chalet ID: {chalet_id}")
            from_date=None 
            to_date=None
            if from_date_s:
                from_date = timezone.make_aware(datetime.strptime(from_date_s, "%Y-%m-%d"))
            if  to_date_p:
                to_date = timezone.make_aware(datetime.strptime(to_date_p, "%Y-%m-%d")) + timedelta(days=1) - timedelta(seconds=1)
            user = request.user.vendor_profile
            logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
            print(f"VendorProfile found for user: {request.user.id} ({request.user.username})")

            # Fetch the chalet
            chalet = Chalet.objects.filter(id=chalet_id, vendor=user.id).first()
            if not chalet:
                logger.warning(f"No chalet found for vendor {user.id} with ID {chalet_id}")
                messages.error(request, _("No chalet found. Please try again."))
                return redirect('loginn') 

            logger.info(f"Chalet found: {chalet.id} ({chalet.name})")  

            reviews = ChaletRecentReview.objects.filter(chalet=chalet.id).order_by("-date")
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
                paginator = Paginator(reviews, 10) 
                try:
                    review_page = paginator.page(page)
                    logger.info(f"Paginated bookings - Page: {page}")
                except PageNotAnInteger:
                    review_page  = paginator.page(1)
                    logger.warning("Page not an integer. Defaulting to page 1.")
                except EmptyPage:
                    review_page  = paginator.page(paginator.num_pages)
                    logger.warning("Page out of range. Displaying last page.")

                ratings = ChaletRecentReview.RATING
                return render(
                    request,
                    "chalets_accounts/chalet_review_rating.html",
                    {"reviews":  review_page, "ratings": ratings},
                )
            else:
                logger.warning(f"review not found")
                return render(request, "chalets_accounts/chalet_review_rating.html", {"error": _("Review Not found.")})

        except Exception as e:
            logger.exception(f"Unexpected error in ChaletBookingView POST: {e}")
            return render(request, "chalets_accounts/chalet_review_rating.html", {"error": _("An unexpected error occurred.")})

@method_decorator(vendor_required, name='dispatch')
class ChaletReviewRespondView(View):
    def post(self, request, *args, **kwargs):
        try:
            logger.info("Processing POST request for ChaletReviewRespondView.")
            id = kwargs.get("pk")
            if id:
                logger.info(f" Chalet review Id received :{id}")
                respond_text = request.POST.get("respond")
                logger.info(f"Vendor Response received :{respond_text}") 
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                print(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                chalet_id = request.GET.get('chalet_id')
                if chalet_id:
                    chalet = Chalet.objects.get(vendor=user.id,id=chalet_id)                
                else:
                    chalet = Chalet.objects.filter(vendor=user.id).first()
                if not chalet :
                    logger.warning(f"No chalet found for vendor {user.id}")
                    messages.error(request, _("No chalet found. Please try again."))
                    return redirect('loginn') 
                else:
                    logger.info(f"Chalet found: {chalet.id} ({chalet.name})") 
                    try:
                        review = ChaletRecentReview.objects.get(id=id)
                        review.respond = respond_text
                        review.save()
                        return JsonResponse({"message": _("Review response posted successfully")})     
                    except ChaletRecentReview.DoesNotExist:
                        logger.warning(f"No chaletrecentreview for vendor {user.id}")
                        return render(request, "chalets_accounts/chalet_review_rating.html", {"error": _("Chalet review not found.")}) 
            else:
                logger.warning(f"No ID received for ChaletRecentReview ")
                return render(request, "chalets_accounts/chalet_review_rating.html", {"error": _("Chalet review ID Needed.")}) 
        except Exception as e:
            logger.exception(f"Unexpected error in ChaletReviewrespondView POST: {e}")
            return render(request, "chalets_accounts/chalet_review_rating.html", {"error": _("An unexpected error occurred.")})   
        
@method_decorator(vendor_required, name='dispatch')
class ReviewEditView(View):
    def get(self, request, *args, **kwargs):
        try:
            logger.info("Processing GET request for ReviewEditView.")
            review_id = kwargs.get("pk")  
            if review_id:
                logger.info(f" Chalet review Id received :{ review_id}")
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                chalet_id = request.GET.get('chalet_id')
                if chalet_id:
                    chalet = Chalet.objects.get(vendor=user.id,id=chalet_id)                
                else:
                    chalet = Chalet.objects.filter(vendor=user.id).first()
                if not chalet :    
                    logger.warning(f"No chalet found for vendor {user.id}")
                    messages.error(request, _("No chalet found. Please try again."))
                    return redirect('loginn') 
                else:
                    logger.info(f"Chalet found: {chalet.id} ({chalet.name})") 
                    try:
                        review =  ChaletRecentReview.objects.get(id=review_id) 
                        data = {
                            "review_text": review.respond,
                        }
                        return JsonResponse(data)  
                    except ChaletRecentReview.DoesNotExist:
                        logger.warning(f"No chaletrecentreview for vendor {user.id}")
                        return render(request, "chalets_accounts/chalet_review_rating.html", {"error": _("Chalet review not found.")})
            else:
                logger.warning(f"No ID received for ChaletRecentReview ")
                return render(request, "chalets_accounts/chalet_review_rating.html", {"error": _("Chalet review ID Needed.")}) 
        except Exception as e:
            logger.exception(f"Unexpected error in ChaletReviewrespondView POST: {e}")
            return render(request, "chalets_accounts/chalet_review_rating.html", {"error": _("An unexpected error occurred.")})   
        
    def post(self, request, *args, **kwargs):
        try:
            logger.info("Processing POST request for ReviewEditView.")
            id = kwargs.get("pk")
            if id:
                logger.info(f" Chalet review Id received :{id}")
                respond_text = request.POST.get("respond")
                logger.info(f"Vendor Response received :{respond_text}") 
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                chalet_id = request.GET.get('chalet_id')
                if chalet_id:
                    chalet = Chalet.objects.get(vendor=user.id,id=chalet_id)                
                else:
                    chalet = Chalet.objects.filter(vendor=user.id).first()
                if not chalet :
                    logger.warning(f"No chalet found for vendor {user.id}")
                    messages.error(request, _("No chalet found. Please try again."))
                    return redirect('loginn') 
                else:
                    logger.info(f"Chalet found: {chalet.id} ({chalet.name})") 
                    try:
                        review = ChaletRecentReview.objects.get(id=id)
                        review.respond = respond_text
                        review.save()
                        logger.info(f"Response edited successfully") 
                        return JsonResponse({"message": _("Review response edited successfully")})
                    except:
                        logger.warning(f"No chaletrecentreview for vendor {user.id}")
                        return render(request, "chalets_accounts/chalet_review_rating.html", {"error": _("Chalet review not found.")}) 
            else:
                logger.warning(f"No ID received for ChaletRecentReview ")
                return render(request, "chalets_accounts/chalet_review_rating.html", {"error": _("Chalet review ID Needed.")}) 
        except Exception as e:
            logger.exception(f"Unexpected error in ChaletReviewrespondView POST: {e}")
            return render(request, "chalets_accounts/chalet_review_rating.html", {"error": _("An unexpected error occurred.")})    

             
    def delete(self, request, *args, **kwargs):
        try:
            logger.info("Processing POST request for ReviewEditView.")
            review_id = kwargs.get("pk")
            if review_id:
                logger.info(f" Chalet review Id received :{review_id}")
                user = request.user.vendor_profile
                logger.info(f"VendorProfile found for user: {request.user.id} ({request.user.username})")
                chalet_id = request.GET.get('chalet_id')
                if chalet_id:
                    chalet = Chalet.objects.get(vendor=user.id,id=chalet_id)                
                else:
                    chalet = Chalet.objects.filter(vendor=user.id).first()
                if not chalet :
                    logger.warning(f"No chalet found for vendor {user.id}")
                    messages.error(request, _("No chalet found. Please try again."))
                    return redirect('loginn')  
                else:
                    logger.info(f"Chalet found: {chalet.id} ({chalet.name})") 
                    try:
                        review =  ChaletRecentReview.objects.get(id=review_id) 
                        review.respond=None
                        review.save()
                        logger.info(f"Response Deleted successfully") 
                        return JsonResponse({"message": _("Review response deleted successfully")})
                    except:
                        logger.warning(f"No chaletrecentreview for vendor: {user.id}")
                        return render(request, "chalets_accounts/chalet_review_rating.html", {"error": _("Chalet review not found.")})
            else:
                logger.warning(f"No ID received for ChaletRecentReview ")
                return render(request, "chalets_accounts/chalet_review_rating.html", {"error": _("Chalet review ID Needed.")}) 
        except Exception as e:
            logger.exception(f"Unexpected error in ChaletReviewrespondView POST: {e}")
            return render(request, "chalets_accounts/chalet_review_rating.html", {"error": _("An unexpected error occurred.")})    



class PropertyView(View):
    def get(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            request.session.flush()  
            return redirect('loginn') 
        
        try:
            user = VendorProfile.objects.get(user=request.user)
            chalets = Chalet.objects.filter(vendor=user.id)
            if not chalets.filter(approval_status="approved").exists():
                if chalets.filter(approval_status="rejected").exists():
                    messages.error(request, _('Your chalet was rejected.'))
                    return redirect('loginn')

            chalet_id = request.GET.get('chalet_id')
            logger.info(f"-------{chalet_id}")
            selected_chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id) if chalet_id else chalets.first()

            if selected_chalet.approval_status != "approved":
                return render(request, 'chalets_accounts/pending_hotel.html')        

            if not selected_chalet.post_approval:
                return redirect(f'/chalets/ammenities/?chalet_id={selected_chalet.id}')   

            room = PropertyManagement.objects.filter(chalet=selected_chalet)
            page = request.GET.get('page', 1)
            paginator = Paginator(room, 15) 
            try:
                rooms = paginator.page(page)
                logger.info(f"Paginated bookings - Page: {page}")
            except PageNotAnInteger:
                rooms = paginator.page(1)
                logger.warning("Page not an integer. Defaulting to page 1.")
            except EmptyPage:
                rooms = paginator.page(paginator.num_pages)
                logger.warning("Page out of range. Displaying last page.")


            context = {
                "chalets": chalets,
                "selected_chalet": selected_chalet,
                "rooms": rooms,
                "LANGUAGES": settings.LANGUAGES,
            }

            return render(request, 'chalets_accounts/property.html', context)
        
        except VendorProfile.DoesNotExist:
            logger.error("VendorProfile not found for user %s", request.user)
            return render(request, 'chalets_accounts/404.html')        
        except Chalet.DoesNotExist:
            logger.error("Chalet not found for user %s", request.user)
            return render(request, 'chalets_accounts/404.html')

    def post(self, request, *args, **kwargs):
        try:
            number_of_bed = int(request.POST.get('bed_number', 0))
            number_of_bathroom = int(request.POST.get('bathroom_number', 0))
            total_occupency = int(request.POST.get('total_occupency', 0))
            room_name = request.POST.get('room_name')
            room_number= request.POST.get('room_number')

            chalet_id = request.POST.get('chalet_id')
            user = VendorProfile.objects.get(user=request.user)
            chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id)
            room = PropertyManagement(
                chalet=chalet,
                number_of_bed=number_of_bed,
                number_of_bathroom=number_of_bathroom,
                total_occupency=total_occupency,
                room_number= room_number,
                room_name=room_name,
                status="active"
            )
            room.save()
            logger.info("Room created: %s", room)

            return JsonResponse({'status': 'success'}, status=200)
        except Exception as e:
            logger.error("Error creating room: %s", str(e))
            return JsonResponse({'status': 'error', 'errors': str(e)}, status=400)    
        


def delete_room(request, room_id):
    if request.method == 'POST':
        try:
            user = VendorProfile.objects.get(user=request.user)
            chalets = Chalet.objects.filter(vendor=user.id)            
            chalet_id = request.GET.get('chalet_id')
            logger.info(f"requested chalet id is {chalet_id}")
            selected_chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id) if chalet_id else chalets.first()
            room = get_object_or_404(PropertyManagement, id=room_id)
            room.delete()
            logger.info("Room deleted: %d", room_id)
        except PropertyManagement.DoesNotExist:
            logger.error("Room not found for id %d", room_id)
            return render(request, 'chalets_accounts/404.html')
    
    return redirect(f'/chalets/propertys/?chalet_id={selected_chalet.id}')        

class RoomEditView(View):
    def get(self, request, pk):
        logger.info("Inside RoomEditView GET method with pk: %d", pk)
        try:
            room = get_object_or_404(PropertyManagement, pk=pk)
            logger.info("Room found: %s", room)
        except PropertyManagement.DoesNotExist:
            logger.error("Room not found with pk: %d", pk)
            return render(request, 'chalets_accounts/404.html')        
        data = {
            'room_number': room.room_number,
            'room_name': room.room_name,
            'number_of_bathroom': room.number_of_bathroom,
            'total_occupency': room.total_occupency,
            'number_of_bed': room.number_of_bed,
        }
        return JsonResponse(data)
    
    def post(self, request, pk):
        try:
            room = get_object_or_404(PropertyManagement, pk=pk)
            room.room_number = request.POST.get('room_number')
            room.room_name = request.POST.get('room_name')
            room.number_of_bathroom = request.POST.get('bathroom_number')
            room.total_occupency = request.POST.get('total_occupency')
            room.number_of_bed = request.POST.get('bed_number')

            room.save()
            logger.info("Room updated: %s", room)
            return JsonResponse({'success': True})
        except PropertyManagement.DoesNotExist:
            logger.error("Room not found for pk: %d", pk)
            return render(request, 'chalets_accounts/404.html')        
        except Exception as e:
            logger.error("Error updating room: %s", str(e))
            return JsonResponse({'error': _('Error updating room')}, status=500)
class ChaletManagementView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            request.session.flush()  # Clear the session
            return redirect('loginn')

        user_language = request.LANGUAGE_CODE
        activate(user_language)

        try:
            user = VendorProfile.objects.get(user=request.user)
            chalets = Chalet.objects.filter(vendor=user.id)

            # If no chalets exist, show an error
            if not chalets.exists():
                messages.error(request, _('You have no chalets.'))
                return redirect('loginn')

            # Get selected chalet from query parameters or default to first chalet
            chalet_id = request.GET.get('chalet_id')
            selected_chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id) if chalet_id else chalets.first()

            # Check if selected chalet is rejected
            if selected_chalet.approval_status == "rejected":
                messages.error(request, _('Your chalet was rejected.'))
                return redirect('loginn')

            # If selected chalet is not approved
            if selected_chalet.approval_status != "approved":
                return render(request, 'chalets_accounts/pending_hotel.html')

            # Fetch unbooked and active chalets for room_data context
            room_data = Chalet.objects.filter(vendor=user.id, is_booked=False, status='active', approval_status='approved', post_approval=True).order_by("id")
            logger.info(f"Fetched room data for vendor {user.id}: {room_data}")

            # Add chalet-level amenities
            amenities = selected_chalet.amenities.filter(status=True)
            amenities = list(amenities)

            # Process pricing details for unbooked chalets (room_data)
            for chalet in room_data:
                if chalet.total_price is not None:
                    chalet.price_per_night = Decimal(chalet.total_price)
                else:
                    chalet.price_per_night = Decimal('0.00')
                commission_slab = CommissionSlab.objects.filter(
                    from_amount__lte=chalet.price_per_night,
                    to_amount__gte=chalet.price_per_night,
                    status="active"
                    
                ).first()

                chalet.commission_amount = commission_slab.commission_amount if commission_slab else Decimal('0.00')
                chalet.total_chalet_price = chalet.price_per_night + chalet.commission_amount

            # Pagination for room_data
            page = request.GET.get('page', 1)
            paginator = Paginator(room_data, 15)

            try:
                paginated_room_data = paginator.page(page)
            except PageNotAnInteger:
                paginated_room_data = paginator.page(1)
            except EmptyPage:
                paginated_room_data = paginator.page(paginator.num_pages)

            # Fetch rooms and additional data for selected chalet
            rooms = PropertyManagement.objects.filter(chalet=selected_chalet)
            chalet_added = request.session.pop('chalet_added', False)
            context = {
                "chalets": chalets,  # List of chalets for this vendor
                "selected_chalet": selected_chalet,  # The currently selected chalet
                "rooms": rooms,  # Rooms associated with the selected chalet
                "amenities": amenities,  # List of amenities
                "room_data": paginated_room_data,  # Unbooked and active chalets
                "is_available_view": True,  # Indicator for available view
                "LANGUAGES": settings.LANGUAGES,  # Languages from settings
                "chalet_added": chalet_added
            }
            
            return render(request, 'chalets_accounts/chalet_management.html', context)

        except VendorProfile.DoesNotExist:
            logger.error("Vendor profile not found for user %s", request.user)
            return render(request, 'chalets_accounts/404.html')        
        except Chalet.DoesNotExist:
            logger.error("Chalet not found for user %s", request.user)
            return render(request, 'chalets_accounts/404.html')
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return render(request, 'chalets_accounts/404.html')

    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': _('User not authenticated')}, status=401)

        chalet_id = request.POST.get('chalet_id')
        if not chalet_id:
            logger.error("Chalet ID is missing in POST request.")
            return JsonResponse({'error': _('Chalet ID is required')}, status=400)

        # Get the chalet based on the given chalet_id
        try:
            chalet = get_object_or_404(Chalet, id=chalet_id, vendor__user=request.user)
        except Chalet.DoesNotExist:
            logger.error(f"Chalet with ID {chalet_id} not found for vendor {request.user.id}.")
            return JsonResponse({'error': _('Chalet not found')}, status=404)

        try:
            # Update the price per night for the chalet
            price_per_night = request.POST.get('price_per_night')
            if price_per_night:
                chalet.total_price = Decimal(price_per_night)

            # Handling weekend price (either update or create)
            weekend_price_value = request.POST.get('weekend_price')
            if weekend_price_value:
                # Try to get the existing weekend price for this chalet
                weekend_price, created = ChaletWeekendPrice.objects.get_or_create(
                    chalet=chalet,
                )
                
                # Update the weekend price if it exists or was created
                weekend_price.weekend_price = Decimal(weekend_price_value)
                weekend_price.save()  # Save the updated weekend price
            else:
                # Remove existing weekend price if no price is provided
                ChaletWeekendPrice.objects.filter(chalet=chalet).delete()
                chalet.weekend_price = None  # Clear the reference to the weekend price
                logger.info(f"Weekend Price removed for Chalet {chalet.id}.")

                # Assign the updated weekend price instance to the chalet
                chalet.weekend_price = weekend_price

            # Handle images (optional, based on your requirements)
            if 'chalet_images' in request.FILES:
                chalet.images = request.FILES.getlist('chalet_images')

            # Save the updated chalet
            chalet.save()
            logger.info(f"Chalet {chalet.id} updated successfully.")
            return redirect('chalet_management')  # Replace with the actual name of your target URL
        except Exception as e:
            logger.error(f"Error updating chalet {chalet.id}: {e}")
            return redirect('chalet_management') 

class AddChaletView(View):
    def get(self, request):
        # Fetch the user by ID
        try:
            user_details = get_object_or_404(VendorProfile, user=request.user)
        except:
            return redirect('loginn')
        try:
            chalet_id = request.GET.get('chalet_id')
            if chalet_id:
                chalet = Chalet.objects.get(vendor=user_details,id=chalet_id)
            else:
                chalet = Chalet.objects.filter(vendor=user_details).first()
        except:
            return render(request,'accounts/404.html')
        
        get_chalet_type = ChaletType.objects.filter(status = "active")

        # Pre-fill the user's existing details
        context = {
            
            'user': request.user,
            'user_details': user_details,
            "GOOGLE_MAPS_API_KEY":settings.GOOGLE_MAPS_API_KEY,
            "chalet_type":get_chalet_type,
            "chalet": chalet,
            'pre_filled_fields': {
                'chaletOwnerName': request.user.first_name,
                'chaletOwnerEmail': request.user.email,
                'owner_name_arabic': chalet.owner_name_arabic if chalet else '',
                
                # Add other fields that should be pre-filled
            }
        }
        return render(request, "chalets_accounts/add_chalet.html", context)

    def post(self, request):
        # Fetch the user by ID
        try:
            user = VendorProfile.objects.get(user=request.user)
            chalet_id = request.GET.get('chalet_id')
            try:
                if chalet_id:
                    selected_chalet = Chalet.objects.get(vendor=user,id=chalet_id)
                else:
                    selected_chalet = Chalet.objects.filter(vendor=user).first()
            except:
                return render(request,'accounts/404.html')
        except VendorProfile.DoesNotExist as e:
            logger.error(f"User fetch error: {e}")
            return redirect('loginn')

        # Extract POST data
        post_data = {}
        try:
            post_data = {field: request.POST.get(field) for field in [
                'chaletName', 'chaletNameArabic', 'hotelAddress', 'stateProvince', 'city', 'country',
                'gsmnumber', 'locality', 'officenumber','chaletOwnerName',
                'crnumber', 'expiry', 'vatnumber', 'About', 'polices', 'logo_image', 'chalet_images',
                'about_arabic', 'polices_arabic', 'officenumber', 'chaletOwnerArabicName',"Accountno", "BankName","Accountholder"
                ,'chalet_type'
            ]}
            post_data["chalet_images"] = request.FILES.getlist("chalet_images[]")
            post_data["logo_image"] = request.FILES.get("logo_image")
        except Exception as e:
            logger.error(f"Error extracting POST data: {e}")
            return render(request, "chalets_accounts/add_chalet.html", {'errors': {'general': _("Error extracting data.")}})

        # Validation
        errors = {}
        if not post_data['chaletName']:
            errors['chaletName'] = _("This field is required.")
         #validate owner name if it exist or not
        try:
            chalet_owner = OwnerName.objects.filter(
                owner_name= post_data["chaletOwnerName"],
                owner_name_arabic= post_data["chaletOwnerArabicName"]
            ).first()

            if not chalet_owner:
                chalet_owner = OwnerName.objects.create(
                    owner_name= post_data["chaletOwnerName"],
                    owner_name_arabic= post_data["chaletOwnerArabicName"]
                )
        except Exception as e:
            logger.error(f"Exception occurred at hotel owner name fetch portion: {str(e)}")
            chalet_owner = None 

        if not errors:
            try:
                # Wrap database operations in an atomic transaction
                with transaction.atomic():
                    # Create or get location
                    country, _ = Country.objects.get_or_create(name=post_data["country"] )
                    state, _ = State.objects.get_or_create(country=country, name=post_data["stateProvince"])
                    city_name=post_data["city"]
                    def is_arabic(text):
                        return any('\u0600' <= c <= '\u06FF' for c in text)
                    if is_arabic(city_name):
                        arabic_name=city_name
                        english_name=get_city_name(city_name,state.name,country.name,'en')
                        logger.info("city name is arabic")
                    else:
                        english_name=city_name
                        arabic_name=get_city_name(city_name,state.name,country.name,'ar')
                    print("english and arabic name of the city is: ", english_name, arabic_name)
                    city, _ = City.objects.get_or_create(state=state, name=english_name, arabic_name=arabic_name)
                    chalettype = ChaletType.objects.get(id=post_data["chalet_type"])
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
                    # Create Chalet object
                    chalet = Chalet.objects.create(
                        vendor=user,
                        name=post_data["chaletName"],
                        name_arabic=post_data["chaletNameArabic"],
                        address=post_data["hotelAddress"],
                        country=country,
                        chalet_type=chalettype,
                        city=city,
                        state=state,
                        cr_number=post_data["crnumber"],
                        vat_number=post_data["vatnumber"],
                        date_of_expiry=post_data["expiry"],
                        logo=post_data["logo_image"],
                        about_property=post_data["About"],
                        policies=post_data["polices"],
                        locality=post_data["locality"],
                        about_property_arabic=post_data["about_arabic"],
                        policies_arabic=post_data["polices_arabic"],
                        office_number=post_data["officenumber"],
                        owner_name_arabic=post_data["chaletOwnerArabicName"],
                        account_no=post_data["Accountno"],
                        bank=post_data["BankName"],
                        account_holder_name=post_data["Accountholder"],
                        owner_name= chalet_owner,
                        latitude= lat,
                        longitude=long 

                    )

                    # Add category to Chalet
                    category_obj, _ = Categories.objects.get_or_create(category='CHALET')
                    chalet.category.add(category_obj)

                    # Upload chalet images using bulk_create with error handling
                    try:
                        ChaletImage.objects.bulk_create([ChaletImage(chalet=chalet, image=chalet_image) for chalet_image in post_data["chalet_images"]])
                    except Exception as e:
                        logger.error(f"Error uploading chalet images: {e}")
                        errors['general'] = _("An error occurred while uploading images. Please try again.")


                    # Send registration email
                    self.send_registration_email(chalet)
                    request.session['chalet_added'] = True

                return redirect(f'/chalets/property/?chalet_id={selected_chalet.id}')  # Replace with your success page

            except Exception as e:
                logger.error(f"Transaction error: {e}")
                errors['general'] = _("An error occurred during registration. Please try again.")
        
        return render(request, "chalets_accounts/add_chalet.html", {'errors': errors})

    # def create_or_get_location(self, country_name, state_name, city_name, post_office):
    #     try:
    #         country, _ = Country.objects.get_or_create(name=country_name)
    #     except Exception as e:
    #         logger.error(f"Error creating or getting country '{country_name}': {e}")
    #         raise

    #     try:
    #         state, _ = State.objects.get_or_create(country=country, name=state_name)
    #     except Exception as e:
    #         logger.error(f"Error creating or getting state '{state_name}' in country '{country_name}': {e}")
    #         raise

    #     try:
    #         city, _ = City.objects.get_or_create(state=state, name=city_name, postal_code=post_office)
    #     except Exception as e:
    #         logger.error(f"Error creating or getting city '{city_name}' in state '{state_name}': {e}")
    #         raise

    #     return country, state, city


    def send_registration_email(self, chalet):
        try:
            superusers = User.objects.filter(is_superuser=True)
            superuser_emails = [superuser.email for superuser in superusers]
            context = {"chalet_name": chalet.name, "chalet_address": chalet.address}
            subject = "New Chalet Registration Notification"
            message = render_to_string("accounts/chalet_registration_notification.html", context)
            send_mail(subject, "", settings.EMAIL_HOST_USER, superuser_emails, html_message=message)
        except Exception as e:
            print(e, "Error in sending registration email")


def check_room_details(request):
    if request.method == "POST":
        chalet_id = request.POST.get('chalet_id')
        room_number = request.POST.get('room_number')
        
        # room_name_exists = PropertyManagement.objects.filter(room_name=room_name).exists()
        room_number_exists = PropertyManagement.objects.filter(chalet_id=chalet_id, room_number=room_number).exists()
        
        return JsonResponse({
            # 'room_name_exists': room_name_exists,
            'room_number_exists': room_number_exists
        })

    return JsonResponse({'room_name_exists': False, 'room_number_exists': False})
 

class EditChaletView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            request.session.flush()  
            return redirect('loginn')  
        
        try:
            chalet_id = request.GET.get('chalet_id')
            user = VendorProfile.objects.get(user=request.user)
            chalets = Chalet.objects.filter(vendor=user.id)  
            if not chalets.filter(approval_status="approved").exists():
                if chalets.filter(approval_status="rejected").exists():
                    messages.error(request, _('Your chalet was rejected.'))
                    return redirect('loginn')
        except (VendorProfile.DoesNotExist, Chalet.DoesNotExist):
                logger.info("vendor/user not found")
                return render(request, 'chalets_accounts/404.html')
        if chalet_id:
            try:
                selected_chalet = Chalet.objects.get(id=chalet_id, vendor=user.id)
            except Chalet.DoesNotExist:
                logger.info("chalet id doesn't exist")
                return render(request, 'chalets_accounts/404.html')
        else:
            selected_chalet = chalets.first()

        # Check approval status of the selected chalet
        if selected_chalet:
            if selected_chalet.approval_status != "approved":
                return render(request, 'chalets_accounts/pending_hotel.html')    
        else:
            return redirect('loginn')
        if not selected_chalet.post_approval:
            return redirect(f'/chalets/ammenities/?chalet_id={selected_chalet.id}')  
      
        context = {
            "LANGUAGES": settings.LANGUAGES,
            "chalets":chalets, 
            "selected_chalet": selected_chalet,
        }
        return render(request, 'chalets_accounts/edit_chalet.html', context=context)



class EditChaletDetailView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            request.session.flush()  
            return redirect('loginn') 
         
        chalet_id = request.GET.get('chalet_id')
        try:
            user = VendorProfile.objects.get(user=request.user)
            chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id)
        except (VendorProfile.DoesNotExist, Chalet.DoesNotExist):
                logger.info("vendor/user not found")
                return render(request, 'chalets_accounts/404.html')
        try:
            chalet_weekend_price = ChaletWeekendPrice.objects.get(chalet=chalet)
            weekend_price = chalet_weekend_price.weekend_price
        except ChaletWeekendPrice.DoesNotExist:
            weekend_price = None
        meal_prices = ChaletMealPrice.objects.filter(chalet=chalet)
        meal_prices_dict = {meal_price.meal_type: meal_price.price for meal_price in meal_prices}
        images = chalet.chalet_images.all().order_by('uploaded_at')
        first_image = images.filter(is_main_image = True).first() if images.exists() else None
        remaining_images = images.exclude(id=first_image.id) if first_image else images
        amenities = chalet.amenities.filter(status=True)
        documents = chalet.chalet_attached_documents.all()
        # Fetch active taxes
        taxes = Tax.objects.filter(status="active", is_deleted=False)

        # Fetch existing HotelTax or ChaletTax records for pre-filling
        if chalet:
            existing_taxes = ChaletTax.objects.filter(chalet=chalet, status="active", is_deleted=False)
            tax_percentage_map = {ht.tax_id: ht.percentage for ht in existing_taxes}
        

        # Attach existing percentages to taxes
        for tax in taxes:
            tax.percentage = tax_percentage_map.get(tax.id, None)
        Payment_ctg=PaymentTypeCategory.objects.filter(status ='active')
        selected_payments = ChaletAcceptedPayment.objects.filter(chalet=chalet_id )
        selected_payment_types = PaymentType.objects.filter(chalet_payment_types_set__in=selected_payments)
        selected_categories = selected_payment_types.values_list('category__id', flat=True).distinct()
        logger.info(selected_payments )
        logger.info(selected_payment_types )
        logger.info( selected_categories )

        # try:
        #     chalet_accpt=ChaletAcceptedPayment.objects.get(chalet=chalet)
        #     selected_payment_types=chalet_accpt.payment_types.all()
        #     selected_payment_categories=PaymentTypeCategory.objects.filter(paymenttype__in= selected_payment_types).distinct()
        #     logger.info(selected_payment_categories)
        # except Exception as e:
        #     logger.error(f"An occured at the edit chalet get view: {str(e)}",)
        document_data = [
            {
                'id': doc.id,  
                'url': doc.document.url,
                'filename': os.path.basename(doc.document.name)
            }
            for doc in documents
        ]
        all_amenities = Amenity.objects.filter(status=True)
        chalet_types=ChaletType.objects.filter(status='active')



        context = {
            'chalet':chalet,
            'meal_prices': meal_prices_dict,
            "first_image": first_image,
            "remaining_images": remaining_images,
            'amenities': amenities,
            'documents': documents,
            'documents': document_data,
            "LANGUAGES": settings.LANGUAGES,
            "chalets": Chalet.objects.filter(vendor=user.id),
            "selected_chalet": chalet,
            'all_amenities':all_amenities,
            'chalet_taxes': taxes,
            # 'Payment_ctg':selected_payment_categories
            'Payment_ctg': Payment_ctg,
            'selected_categories':  selected_categories,
            'chalet_types': chalet_types,
            'weekend_price':weekend_price
        }

        return render(request, 'chalets_accounts/edit_chalet_detail.html',context=context)
    

    def post(self, request):
        print("Starting to save chalet details...")

        try:
            chalet_id = request.GET.get('chalet_id')
            user = VendorProfile.objects.get(user=request.user)
            chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id)
            if chalet.approval_status == "rejected":
                messages.error(request, 'Hotel was rejected.')
                # return redirect('loginn')
                return JsonResponse({'success': False, 'status': 'not_approved', 'message': _('Chalet is not approved. You need to log out.')})
        except (VendorProfile.DoesNotExist, Chalet.DoesNotExist):
                logger.info("vendor/user not found")
                return render(request, 'chalets_accounts/404.html')

        print(f"chalet object retrieved: {chalet}")

        try:
            # Extract data from the request
            chalet_name = request.POST.get('chalet_name')
            chalet_owner = request.POST.get('chalet_owner')
            chalet_email = request.POST.get('chalet_email')
            office_number = request.POST.get('officenumber')
            chalet_address = request.POST.get('chalet_address')
            state = request.POST.get('state')
            city = request.POST.get('city')
            country = request.POST.get('country')
            gsm_number = request.POST.get('gsmnumber')
            locality = request.POST.get('locality')
            chalet_rating = request.POST.get('rating')
            cr_number = request.POST.get('crnumber')
            date_of_expiry= request.POST.get('expiry')
            vat_number = request.POST.get('vatnumber')
            about_property = request.POST.get('about_property')
            chalet_policies = request.POST.get('chalet_policies')
            breakfast_price = request.POST.get('breakfast-price')
            lunch_price = request.POST.get('lunch-price')
            dinner_price = request.POST.get('dinner-price')

            chalet_name_arabic = request.POST.get('arabic_name')
            chalet_owner_arabic = request.POST.get('chalet_owner_arabic')
            about_property_arabic = request.POST.get('about_property_arabic')
            chalet_policies_arabic = request.POST.get('chalet_policies_arabic')
            account_no=request.POST.get('Accountno')
            account_holder_name=request.POST.get('Accountholder')
            bank=request.POST.get('BankName')
            chalet_type_value=request.POST.get('chalet_type')
            arabic_city=request.POST.get('CityArabic')
            check_in=request.POST.get('chalet_check_in')
            check_out=request.POST.get('chalet_check_out')
            no_of_guests=request.POST.get('chalet_guests')
            total_price=request.POST.get('chalet_price')
            weekend_price=request.POST.get('chalet_weekend_price')


            logo_source = request.POST.get('logo_source')
            amenity_ids = request.POST.get('amentity_ids')
            payment_ctg=request.POST.getlist("payment_category")
            logger.info(payment_ctg)
            existing_document_ids = request.POST.getlist('existing_document_ids')

            logo_source = request.FILES.get('logo_image')
            if chalet.address!=chalet_address  or  chalet.city.name != city or chalet.state.name != state or chalet.country.name != country:
                try:
                    lat, long = get_lat_long(
                        chalet_address,
                        city,
                        state,
                        country
                    )
                    if lat is not None and long is not None:
                        logger.info(f"Fetched coordinates: latitude={lat}, longitude={long}")
                    else:
                        logger.warning("Could not fetch valid coordinates. Received None.")
                        lat = chalet.latitude
                        long = chalet.longitude
                except Exception as e:
                    logger.error(f"Error fetching coordinates: {str(e)}")
                    lat = chalet.latitude
                    long = chalet.longitude
            else:
                lat = chalet.latitude
                long = chalet.longitude

            try:
                if logo_source:
                    chalet.logo.delete()
                    chalet.logo = logo_source
                    chalet.save()

                existing_main_image = request.POST.get('existing_main_image')
                existing_image_ids = request.POST.getlist('existing_image_ids[]')

                # New image data
                new_images = {
                    'main_images': request.FILES.get('main_images'),
                }
                for i in range(1, 5):
                    new_images[f'remaining_images_{i}'] = request.FILES.get(f'remaining_images_{i}')

                existing_images = set(chalet.chalet_images.values_list('id', flat=True))

                existing_image_ids = set(map(int, existing_image_ids))
                if existing_main_image:
                    existing_image_ids.add(int(existing_main_image))

                removed_image_ids = existing_images - existing_image_ids

                # Delete removed images
                chalet.chalet_images.filter(id__in=removed_image_ids).delete()

                for key, image in new_images.items():
                    if image:
                        if key == 'main_images':  
                            # Delete the old main image
                            old_main_image = ChaletImage.objects.filter(chalet=chalet, is_main_image=True).first()
                            if old_main_image:
                                old_main_image.delete()

                            # Create a new main image
                            main_image = ChaletImage.objects.create(chalet=chalet, image=image, is_main_image=True)
                            logger.info(f"Replaced main image: {image.name}")

                        else:
                            remaining_image_key = key.split('_')[-1]
                            if remaining_image_key and f'existing_image_{remaining_image_key}' in request.POST:
                                # Replace an existing additional image
                                image_id_to_replace = request.POST.get(f'existing_image_{remaining_image_key}')
                                ChaletImage.objects.filter(id=image_id_to_replace).delete()
                                logger.info(f"Replaced additional image: {image.name}")

                            ChaletImage.objects.create(chalet=chalet, image=image, is_main_image=False)
                            logger.info(f"Saved new image: {image.name}")

                # Update amenities if provided
                if amenity_ids:
                    amenities_ids = json.loads(amenity_ids)
                    chalet.amenities.clear()
                    for amenity_id in amenities_ids:
                        amenity = get_object_or_404(Amenity, id=amenity_id)
                        amenity.amenity_type = 'Property_amenity'
                        amenity.status = True
                        amenity.save()
                        chalet.amenities.add(amenity)
                    logger.info("Updated chalet amenities")


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

                        # Create or update ChaletTax record
                        chalet_tax, created = ChaletTax.objects.update_or_create(
                            chalet=chalet, tax=tax,
                            defaults={
                                'percentage': tax_percentage,
                                'status': 'active',
                                'created_by': user,
                                'modified_by': user
                            }
                        )

                print('Chalet taxes saved successfully.')
            except Exception as e:
                logger.error(f"Error: {e}")
            
            try:
                country, created = Country.objects.get_or_create(name=country)
                state, created = State.objects.get_or_create(
                    country=country, name=state
                )
                city, created = City.objects.get_or_create(
                    state=state, name=city, arabic_name=arabic_city
                )
                
            except Exception as e:
                logger.error(f"Location data error: {e}")     

            # Check if email already exists in the database, excluding the current user
            if VendorProfile.objects.filter(user__email__exact=chalet_email).exclude(user__id=request.user.id).exists():
                logger.info("\n\n\n\n\n\nEmail already exists\n\n\n\n\n")
                return JsonResponse({'success': False, 'message': _('Email already exists')}, status=400)
         

            vendor = chalet.vendor
            if vendor:
                Userdetails_obj = vendor
                Userdetails_obj.gsm_number = gsm_number
                Userdetails_obj.save()

                if Userdetails_obj.user:
                    # Userdetails_obj.user.first_name = chalet_owner
                    Userdetails_obj.user.email= chalet_email
                    Userdetails_obj.user.save()  

            else:
                logger.warning("No Userdetails associated with this chalet.")

            def parse_price(price_str):
                if price_str and price_str.strip().lower() != 'n/a':
                    try:
                        return Decimal(price_str)
                    except ValueError:
                        return None
                return None
            
            # Create a set of meal types that will be retained
            meal_types_to_keep = {'no meals'}

            # Save meal prices
            try:
                if breakfast_price and float(breakfast_price) > 0:
                    ChaletMealPrice.objects.update_or_create(
                        chalet=chalet,
                        meal_type='breakfast',
                        defaults={'price': parse_price(breakfast_price)}
                    )
                    meal_types_to_keep.add('breakfast')

                if lunch_price and float(lunch_price) > 0:
                    ChaletMealPrice.objects.update_or_create(
                        chalet=chalet,
                        meal_type='lunch',
                        defaults={'price': parse_price(lunch_price)}
                    )
                    meal_types_to_keep.add('lunch')

                # Handle dinner price
                if dinner_price and float(dinner_price) > 0: 
                    ChaletMealPrice.objects.update_or_create(
                        chalet=chalet,
                        meal_type='dinner',
                        defaults={'price': parse_price(dinner_price)}
                    )
                    meal_types_to_keep.add('dinner')

                # Delete all meal prices except those being updated
                ChaletMealPrice.objects.filter(chalet=chalet).exclude(meal_type__in=meal_types_to_keep).delete()
    
            except Exception as e:
                logger.error(f"Meal price update error: {e}")
            if payment_ctg:
                try:
                    chalet_payment_accepted, created = ChaletAcceptedPayment.objects.get_or_create(
                        chalet=chalet,
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

                    wallet_payment_types = PaymentType.objects.filter(category__name__iexact="Wallet")

                    final_payment_types = set(selected_payment_types) | set(wallet_payment_types)

                    chalet_payment_accepted.payment_types.set(final_payment_types)
                    chalet_payment_accepted.save()
                    logger.info("chalets accepted payments saved successfully")
                except Exception as e:
                    logger.error(f"An exception occured while updating chalet accepted payments error: {e}")
            if chalet_type_value:
                chalet_type=None
                logger.info(chalet_type_value)
                try:
                    chalet_type=ChaletType.objects.get(id=chalet_type_value)
                except Exception as e:
                    logger.error(f"Exception ocuured at chalet type fetch portion : {str(e)} ")
            try:
                chaletowner = OwnerName.objects.filter(
                    owner_name=chalet_owner ,
                    owner_name_arabic=chalet_owner_arabic
                ).first()

                if not chaletowner:
                    chaletowner = OwnerName.objects.create(
                        owner_name=chalet_owner ,
                        owner_name_arabic=chalet_owner_arabic
                    )
            except Exception as e:
                logger.error(f"Exception occurred at hotel owner name fetch portion: {str(e)}")
                chaletowner = None 
            logger.info(f"weekend price---{weekend_price}")
            try:
                if weekend_price not in [None, '', 'None']:
                    cleaned_price = str(weekend_price).replace(',', '.').strip()
                    # Convert to Decimal
                    weekend_price_decimal = Decimal(cleaned_price)
                    # Save or update
                    ChaletWeekendPrice.objects.update_or_create(
                        chalet=chalet,
                        defaults={'weekend_price':weekend_price_decimal}
                    )
                    logger.info(f"chalet weekend price created/updated")
                else:
                    # Delete if exists
                    ChaletWeekendPrice.objects.filter(chalet=chalet).delete()
                    logger.info(f"chalet weekend price deleted")
            except Exception as e:
                # Log or handle the error
                logger.error(f"Error occurred while updating ChaletWeekendPrice: {e}")


            cleaned_price = str(total_price).replace(',', '.').strip()
                    # Convert to Decimal
            total_price_decimal = Decimal(cleaned_price)


            chalet.name = chalet_name
            chalet.office_number = office_number
            chalet.address = chalet_address
            chalet.locality = locality
            chalet.cr_number = cr_number
            chalet.vat_number = vat_number
            chalet.about_property = about_property
            chalet.policies = chalet_policies
            chalet.state=state
            chalet.city=city
            chalet.country=country
            chalet.date_of_expiry= date_of_expiry
            chalet.about_property_arabic=about_property_arabic
            chalet.policies_arabic=chalet_policies_arabic
            chalet.name_arabic=chalet_name_arabic
            chalet.owner_name_arabic = chalet_owner_arabic
            chalet.bank=bank
            chalet.account_holder_name=account_holder_name
            chalet.account_no=account_no
            chalet.chalet_type=chalet_type
            chalet.owner_name= chaletowner
            chalet.checkin_time=check_in
            chalet.checkout_time= check_out
            chalet.number_of_guests=no_of_guests
            chalet.total_price=total_price_decimal
            chalet.latitude=lat
            chalet.longitude=long
            chalet.save()
            try:
                subject = "Chalet Details Updated"
                message = f"Chalet details for '{chalet.name}' have been successfully updated."
                from_email = settings.EMAIL_HOST_USER
                
                superusers = User.objects.filter(is_superuser=True)
                superuser_emails = [superuser.email for superuser in superusers]
                send_mail(
                    subject,
                    message,
                    from_email,
                    [chalet_email] + superuser_emails,
                    fail_silently=False,
                )                
                logger.info("\n\n\n\n\nchalet details saved successfully.\n\n\n\n\n\n")
            except Exception as e:
                logger.info(f"\n\nIssue in mail sending in edit chalet. Exception: {e}\n\n")  
            return JsonResponse({'success': True,'message': _('Chalet details saved successfully.'),'chalet_id': chalet.id},status=200)
     

        except Exception as e:
                logger.info(f"An error occurred at the edit chalet view: {e}")
                return render(request, 'chalets_accounts/404.html')            



@login_required
def edit_amenity_to_chalet(request):
    if request.method == "POST":
        try:
            chalet_id = request.POST.get("chalet_id")
            selected_amenities = request.POST.getlist("selected_amenities[]")
            
            logger.info(f"chalet_id: {chalet_id}, selected_amenities: {selected_amenities}")

            if not chalet_id or not selected_amenities:
                logger.warning(f"Missing required fields. chalet_id: {chalet_id}, selected_amenities: {selected_amenities}")
                return JsonResponse({"error": _("At least one amenity must be selected.")}, status=400)

            try:
                amenity_ids = [int(amenity_id) for amenity_id in selected_amenities]
            except ValueError as e:
                logger.error(f"Invalid amenity ID in selected_amenities: {selected_amenities}. Error: {e}")
                return JsonResponse({"error": _("Invalid amenity IDs. IDs must be integers.")}, status=400)

            chalet = get_object_or_404(Chalet, id=chalet_id)

            for amenity_id in amenity_ids:
                try:
                    amenity = get_object_or_404(Amenity, id=amenity_id)

                    if not chalet.amenities.filter(id=amenity.id).exists():
                        chalet.amenities.add(amenity)
                        logger.info(f"Amenity {amenity.id} added to Chalet {chalet.id}")
                    else:
                        logger.info(f"Amenity {amenity.id} already exists in chalet amenities.")
                        continue

                except Exception as e:
                    logger.error(f"Error adding amenity with ID {amenity_id} to chalet: {e}", exc_info=True)
                    return JsonResponse({"error": _("An error occurred while adding amenity.")}, status=500)

            logger.info(f"Amenities added to chalet. Chalet ID: {chalet.id}")

            return JsonResponse({"success": _("Amenities added successfully")}, status=200)

        except Exception as e:
            logger.error(f"Unexpected error in edit_amenity_to_chalet: {e}", exc_info=True)
            return JsonResponse({"error": _("An unexpected error occurred. Please try again later.")}, status=500)

    return JsonResponse({"error": _("Invalid request")}, status=400)


class EditChaletPolicyView(View):
    def get(self, request):
        chalet_id = request.GET.get('chalet_id')
        logger.info(f"Received GET request for chalet_id: {chalet_id} by user: {request.user}")

        if not request.user.is_authenticated:
            logger.warning("User is not authenticated, redirecting to login")
            request.session.flush()  
            return redirect('loginn') 
         
        try:
            logger.info(f"Retrieving VendorProfile for user: {request.user}")
            user = VendorProfile.objects.get(user=request.user)
            logger.info(f"Retrieving chalet for vendor: {user.id}")
            chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id)
            if chalet:
                logger.info(f"Chalet found with ID {chalet.id}")
                if chalet.approval_status == "rejected":
                    logger.warning(f"Chalet {chalet.id} was rejected. Redirecting to pending page.")
                    return render(request,'chalets_accounts/pending_hotel.html')
            else:
                logger.error(f"No chalet found for vendor {user.id} with ID {chalet_id}. Redirecting to login.")
                return redirect('loginn') 

        except (VendorProfile.DoesNotExist, Chalet.DoesNotExist) as e:
            logger.error(f"Error retrieving vendor/user or chalet. Exception : {e}", exc_info=True)
            return render(request, 'chalets_accounts/404.html')        

        try:
            vendor_policies = PolicyCategory.objects.filter(chalet=chalet)
            if vendor_policies.exists():
                logger.info(f"Retrieved {vendor_policies.count()} vendor policies for chalet {chalet.id}")
            else:
                logger.info(f"No vendor policies found for chalet {chalet.id}")

        except Exception as e:
            logger.error(f"Error retrieving vendor policies for chalet {chalet.id}. Exception: {e}", exc_info=True)
            vendor_policies = []

        try:
            common_policies = PolicyCategory.objects.filter(policy_type='common')
            if common_policies.exists():
                logger.info(f"Retrieved {common_policies.count()} common policies")
            else:
                logger.info("No common policies found.")
        except Exception as e:
            logger.error(f"Error retrieving common policies. Exception: {e}", exc_info=True)
            common_policies = []

        try:
            selected_policy_names = chalet.post_policies_name.all()
            logger.info(f"Retrieved {selected_policy_names.count()} selected policy names for chalet {chalet.id}")
        except Exception as e:
            logger.error(f"Error retrieving selected policy names for chalet {chalet.id}: {e}", exc_info=True)
            selected_policy_names = []

        # combine common(admin added policy and vendor added policy for dropdown so that they can easily select category)
        combined_policies = list(common_policies) + list(vendor_policies)
        unique_policies = {policy.name: policy for policy in combined_policies}.values()

        context = {
            'hotel': chalet,
            'policies': vendor_policies,
            'common_policies': unique_policies,
            "LANGUAGES": settings.LANGUAGES, 
            'selected_policy_names': selected_policy_names,
            "chalets": Chalet.objects.filter(vendor=user.id),
            "selected_chalet": chalet,
        }

        return render(request, 'chalets_accounts/accounts/edit_chalet_policy.html', context=context)
    

class PolicyDataView(View):
    def get(self, request, category_id):
        try:
            chalet_id = request.GET.get('chalet_id')
            if not chalet_id:
                logger.error("Chalet ID is missing in the request.")
                return JsonResponse({'status': 'error', 'message': _('Chalet ID is required')}, status=400)

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
                chalet = Chalet.objects.get(id=chalet_id)
                logger.info(f"Chalet '{chalet.name}' (ID: {chalet.id}) retrieved successfully.")
            except Chalet.DoesNotExist:
                logger.error(f"Chalet with ID {chalet_id} does not exist for vendor {user.id}.")
                return JsonResponse({'status': 'error', 'message': _('Chalet not found')}, status=404)

            selected_policy_names = chalet.post_policies_name.filter(
                policy_category=category, is_deleted=False
            ).values('id', 'title')

            data = {
                'category_name': category.name,
                'selected_policies': list(selected_policy_names),
            }
            logger.info(f"Policy data for category '{category.name}' retrieved successfully for chalet '{chalet.name}'.")
            return JsonResponse({'status': 'success', 'data': data}, status=200)

        except Exception as e:
            logger.error(f"An unexpected error occurred in PolicyDataView get function. Exception : {str(e)}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': _('An unexpected error occurred')}, status=500)     

@login_required
def save_policy(request):
    if request.method == 'POST':
        category = request.POST.get('category')
        policies = request.POST.getlist('policies[]')
        chalet_id = request.GET.get('chalet_id')
        try:
            user = VendorProfile.objects.get(user=request.user)
            chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id)
            if chalet.approval_status == "rejected":
                logger.warning(f"Chalet {chalet.id} was rejected. Redirecting to pending page.")
                return render(request, 'chalets_accounts/pending_hotel.html')
            logger.info(f"Retrieved chalet: {chalet.id} for vendor: {user.id}")

        except (VendorProfile.DoesNotExist, Chalet.DoesNotExist) as e:
            logger.error(f"Error retrieving vendor/user or chalet: {e}", exc_info=True)
            return render(request, 'chalets_accounts/404.html')

        # Scenario 1: Check if the category exists as a common category
        try:
            existing_category = PolicyCategory.objects.get(name=category, policy_type='common')
            logger.info(f"Policy category {category} exists as a common category.")
            chalet.post_policies.add(existing_category)
            chalet.save()

            for policy in policies:
                if policy:
                    logger.info(f"Creating policy name {policy} under category {existing_category.name}.")
                    policy_name, created = PolicyName.objects.get_or_create(
                        policy_category=existing_category, 
                        title=policy, 
                        created_by=request.user
                    )

                    if created:
                        logger.info(f"Policy name '{policy}' created successfully.")
                        message = _("Successfully added new policy to %(category)s.") % {"category": category}
                        status = "success"
                    if not chalet.post_policies_name.filter(id=policy_name.id).exists():
                        chalet.post_policies_name.add(policy_name)
                        message = _("Successfully added policy.")
                        status = "success"
                    else:
                        message = _("Policy already exists in this category.")
                        status = "error"

            chalet.save()
            return JsonResponse({'status': status, 'message': message}, status=200)

        except PolicyCategory.DoesNotExist:
            pass

        # Scenario 2: Check if the category exists for the vendor or in common categories
        try:
            existing_vendor_category = PolicyCategory.objects.get(name=category, created_by=request.user)
            logger.info(f"Policy category {category} already exists for vendor {request.user.id}.")
            chalet.post_policies.add(existing_vendor_category)
            chalet.save()
            for policy in policies:
                if policy:
                    logger.info(f"Creating policy name {policy} under vendor category {existing_vendor_category.name}.")
                    policy_name, created = PolicyName.objects.get_or_create(
                        policy_category=existing_vendor_category, 
                        title=policy, 
                        created_by=request.user
                    )

                    if created:
                        logger.info(f"Policy name '{policy}' created successfully.")
                        message = _("Successfully added new policy to %(category)s.") % {"category": category}
                        status = "success"
                    if not chalet.post_policies_name.filter(id=policy_name.id).exists():
                        chalet.post_policies_name.add(policy_name)
                        message = _("Successfully added policy.")
                        status = "success"
                    else:
                        message = _("Policy already exists in this category.")
                        status = "error"

            chalet.save()
            return JsonResponse({'status': status, 'message': message}, status=200)

        except PolicyCategory.DoesNotExist:
            # Create a new vendor-specific category if it doesn't exist
            logger.info(f"Policy category {category} does not exist. Creating a new vendor-specific policy category.")
            get_policy_category = PolicyCategory.objects.create(
                name=category, 
                created_by=request.user,
                policy_type='vendor'
            )
            chalet.post_policies.add(get_policy_category)
            chalet.save()

        # Scenario 3: Create the policy category and related policy names directly
        for policy in policies:
            if policy:
                logger.info(f"Creating policy name {policy} under category {get_policy_category.name}.")
                get_policy_name = PolicyName.objects.create(
                    policy_category=get_policy_category, 
                    title=policy, 
                    created_by=request.user
                )
                if not chalet.post_policies_name.filter(id=get_policy_name.id).exists():
                    chalet.post_policies_name.add(get_policy_name)

        chalet.save()
        logger.info(f"Successfully added policies to chalet {chalet.id}.")
        return JsonResponse({'status': 'success', 'message': _('Policies Created Successfully')}, status=200)


@login_required
def update_policy_data(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        category_name = data.get('category_name')
        policies = data.get('policies', [])
        logger.info(f"Policies from frontend: {policies}")
        category_id = data.get('category_id')
        chalet_id = data.get('chalet_id')
        logger.info(f"Received data: {data}")

        # Validate the vendor and chalet
        try:
            user = VendorProfile.objects.get(user=request.user)
            chalet = get_object_or_404(Chalet, id=chalet_id, vendor=user.id)
            if chalet.approval_status == "rejected":
                logger.warning(f"Chalet with ID {chalet_id} was rejected.")
                return JsonResponse({'status': 'error', 'message': _('Chalet was rejected.')}, status=403)
        except (VendorProfile.DoesNotExist, Chalet.DoesNotExist):
            logger.error("Vendor or chalet not found.")
            return JsonResponse({'status': 'error', 'message': _('Vendor or chalet not found.')}, status=404)

        category = get_object_or_404(PolicyCategory, id=category_id)
        logger.info(f"Category found: {category}")

        if category_name:
            category.name = category_name
            category.save()
            logger.info(f"Category name updated to: {category_name}")

        existing_policies = chalet.post_policies_name.filter(policy_category=category)
        logger.info(f"Existing policies: {list(existing_policies)}")

        # Remove policies that are no longer in the frontend list (only from the current category)
        for policy in existing_policies:
            if not any(policy.title == p.get('value') and policy.id == int(p.get('id')) for p in policies):
                chalet.post_policies_name.remove(policy)
                logger.info(f"Removed policy: {policy.title} (ID: {policy.id})")


        duplicate_name = ""
        duplicate_found = False

        # Add or update policies based on the frontend list (only for the current category)
        for policy_data in policies:
            if policy_data:
                policy_instance = None
                policy_value = policy_data.get('value')

                if policy_data.get('id'):
                    try:
                        policy_instance = PolicyName.objects.get(
                            id=policy_data['id'],
                            created_by=request.user
                        )
                        if policy_instance.title != policy_value:
                            if PolicyName.objects.filter(
                                policy_category=category,
                                title=policy_value,
                                created_by=request.user
                            ).exists():
                                duplicate_name = policy_value
                                duplicate_found = True
                                logger.warning(f"Duplicate policy found when updating: {duplicate_name}")
                                break

                            policy_instance.title = policy_value
                            policy_instance.save()
                            chalet.post_policies_name.add(policy_instance)
                            logger.info(f"Updated policy: {policy_instance}")

                    except PolicyName.DoesNotExist:
                        logger.warning(f"Policy not found with ID: {policy_data.get('id')}")
                        continue
                else:
                    policy_instance = PolicyName.objects.filter(
                        policy_category=category,
                        title=policy_value,
                        created_by=request.user
                    ).first()

                    if policy_instance:
                        if chalet.post_policies_name.filter(
                            policy_category=category,
                            title=policy_value,
                            created_by=request.user
                        ).exists():
                            duplicate_name = policy_value
                            duplicate_found = True
                            logger.warning(f"Duplicate policy found: {duplicate_name}")
                            break
                        else:
                            chalet.post_policies_name.add(policy_instance)
                            logger.info(f"Added existing policy: {policy_instance}")
                    else:
                        policy_instance = PolicyName.objects.create(
                            policy_category=category,
                            title=policy_value,
                            created_by=request.user
                        )
                        chalet.post_policies_name.add(policy_instance)
                        logger.info(f"Created and added new policy: {policy_instance}")

            chalet.save()

        if duplicate_found:
            logger.error(f"Duplicate policy detected: {duplicate_name}")
            return JsonResponse({'status': 'error', 'message': _('Policy already exists for this category.')})

        return JsonResponse({'status': 'success', 'message': _('Policies updated successfully.')})

    except Exception as e:
        logger.exception(f"Unexpected error occurred while calling update_policy_data function. Exception: {str(e)}")
        return JsonResponse({'status': 'error', 'message': _('An unexpected error occurred.')}, status=500)



class ChaletManagementViewBooked(View):
    def get(self, request):
        if not request.user.is_authenticated:
            request.session.flush()  # Clear the session
            return redirect('loginn')

        user_language = request.LANGUAGE_CODE
        activate(user_language)

        try:
            user = VendorProfile.objects.get(user=request.user)
            chalet = Chalet.objects.filter(vendor=user.id).first()
            if chalet.approval_status == "rejected":
                messages.error(request, _('Chalet was rejected.'))
                return redirect('loginn')
        except (VendorProfile.DoesNotExist, Chalet.DoesNotExist):
                logger.info("vendor/user not found")
                return render(request, 'chalets_accounts/404.html')
        chalet_obj = Chalet.objects.filter(vendor=user.id, is_booked=True, status='active').order_by("id")
        amenities = list(chalet.amenities.all())

        # Add chalet-level amenities
        chalet_amenities = Amenity.objects.filter(amenity_type="Chalet_amenity", status=True)
        for amenity in chalet_amenities:
            amenities.append(amenity)

        for chalet in chalet_obj:
            chalet.price_per_night = Decimal(chalet.total_price)
            commission_slab = CommissionSlab.objects.filter(
                from_amount__lte=chalet.price_per_night,
                to_amount__gte=chalet.price_per_night,
                status="active"
            ).first()

            chalet.commission_amount = commission_slab.commission_amount if commission_slab else Decimal('0.00')
            chalet.total_chalet_price = chalet.price_per_night + chalet.commission_amount

        page = request.GET.get('page', 1)
        paginator = Paginator(chalet_obj, 10)

        try:
            chalets = paginator.page(page)
        except PageNotAnInteger:
            chalets = paginator.page(1)
        except EmptyPage:
            chalets = paginator.page(paginator.num_pages)

        context = {
            "room_data": chalets,
            "amenities": amenities,
            "hotel": chalet,
            "is_available_view": False,
            "LANGUAGES": settings.LANGUAGES,
        }

        return render(
            request,
            template_name="chalets_accounts/chalet_management.html",
            context=context,
        )


class ChaletDetailView(View):
    template_name = 'chalets_accounts/chalet_detail_view.html'

    def get(self, request, pk):
        # Ensure user is authenticated
        if not request.user.is_authenticated:
            request.session.flush()
            return redirect('loginn')

        # Get user's language preference and activate it
        user_language = request.LANGUAGE_CODE
        activate(user_language)

        try:
            # Get vendor profile and selected chalet by ID
            user = VendorProfile.objects.get(user=request.user)
            chalets = Chalet.objects.filter(vendor=user.id)
            # Find the selected chalet
            selected_chalet = chalets.filter(id=pk).first()
            if not selected_chalet:
                raise Chalet.DoesNotExist

            # Check approval status
            if selected_chalet.approval_status != "approved":
                return render(request, 'chalets_accounts/pending_hotel.html')

            # Check post-approval steps
            if not selected_chalet.post_approval:
                return redirect(f'/chalets/ammenities/?chalet_id={selected_chalet.id}')
        
        except (VendorProfile.DoesNotExist, Chalet.DoesNotExist):
            logger.info("vendor/chalet not found")
            return render(request, 'chalets_accounts/404.html')
        print(f"selected chal;et is ---- {selected_chalet}")
        # Get related chalet room details
        chalet_room = PropertyManagement.objects.filter(chalet=selected_chalet).first()
        print(f"chalet roommmm -- {chalet_room}")
        if selected_chalet.amenities.all():
            # Get amenities and images
            amenities = selected_chalet.amenities.all()
            print(f"amenitiessss - {selected_chalet.amenities.all()}")
        else:
            amenities = []

        chalet_images = ChaletImage.objects.filter(chalet=selected_chalet)

        # Use the helper method to calculate the commission and total price
        commission_amount, total_price, price_per_night = self.calculate_total_price_with_commission(selected_chalet)

        context = {
            'chalet_room': chalet_room,
            'amenities': amenities,
            'room_type_images': chalet_images,
            'commission_amount': commission_amount,
            'total_price': total_price,
            'price_per_night': price_per_night,
            'selected_chalet': selected_chalet,
            "chalets": chalets,
            'LANGUAGES': settings.LANGUAGES,
        }

        return render(request, self.template_name, context)

    def calculate_total_price_with_commission(self, chalet):
        """
        Helper method to calculate the commission amount and total price for a chalet.
        """
        price_per_night = Decimal(chalet.total_price)

        # Get the commission slab based on the price
        commission_slab = CommissionSlab.objects.filter(
            from_amount__lte=price_per_night,
            to_amount__gte=price_per_night,
            status="active"
        ).first()

        # Calculate the commission amount
        commission_amount = commission_slab.commission_amount if commission_slab else Decimal('0.00')

        # Calculate the total chalet price (price + commission)
        total_chalet_price = price_per_night + commission_amount

        return commission_amount, total_chalet_price, price_per_night


class DeletePolicyView(LoginRequiredMixin, View):
    login_url = 'loginn' 
    redirect_field_name = 'next'

    def post(self, request, policycategoryID):
        if not request.user.is_authenticated:
            logger.warning("User is not authenticated.")
            return redirect('loginn')

        logger.info(f"Attempting to delete policies for category ID: {policycategoryID}.")

        category = PolicyName.objects.filter(policy_category_id=policycategoryID)
        if not category:
            logger.warning(f"No policies found for policy category ID: {policycategoryID}.")
            return JsonResponse({'message': _('No policies found for this category.'), 'status': False}, status=404)

        try:
            user = VendorProfile.objects.get(user=request.user)
            logger.info(f"Vendor profile found for user ID: {request.user.id}, Vendor ID: {user.id}")

            data = json.loads(request.body)
            chalet_id = data.get('chalet_id')
            if not chalet_id:
                logger.warning("Chalet ID not provided in the request body.")
                return JsonResponse({'message': _('Chalet ID is required.'), 'status': False}, status=400)

            try:
                get_chalet = Chalet.objects.get(id=chalet_id)
                logger.info(f"Chalet found: ID {get_chalet.id}, Name {get_chalet.name}")

                if get_chalet.approval_status == "rejected":
                    logger.warning(f"Chalet ID {get_chalet.id} is rejected.")
                    messages.error(request, _('Chalet was rejected.'))
                    return redirect('loginn')

                for policy in category:
                    get_chalet.post_policies_name.remove(policy)
                    logger.info(f"Removed policy {policy.title} from chalet ID {get_chalet.id}.")

                get_chalet.post_policies.remove(policycategoryID)
                logger.info(f"Removed policy category {policycategoryID} from chalet ID {get_chalet.id}.")

                return JsonResponse({'message': _('Policy category has been deleted successfully.'), 'status': True})

            except Chalet.DoesNotExist:
                logger.error(f"Chalet with ID {chalet_id} not found.")
                return JsonResponse({'message': _('Chalet not found.'), 'status': False}, status=404)

        except VendorProfile.DoesNotExist:
            logger.error(f"VendorProfile not found for user ID: {request.user.id}.")
            return render(request, 'chalets_accounts/404.html')

        except Exception as e:
            logger.exception(f"Unexpected error occurred while deleting policy category: {str(e)}")
            return JsonResponse({'message': _('An unexpected error occurred.'), 'status': False}, status=500)           

def verify_booking(request, token):
    try:
        # Try to retrieve the booking with the matching token
        booking = get_object_or_404(ChaletBooking, token=token)
    except Http404:
        # If the booking is not found, return a 404 response
            logger.info("booking not found")
            return render(request, 'chalets_accounts/404.html')
    # Check if the checkout date has passed
    if booking.checkout_date and booking.checkout_date < now().date():
        # Return an HTTP response indicating the booking has expired
        return HttpResponse(_("The booking's checkout date has already passed."), status=400)

    # Define the actual booking URL
    actual_url = f"{settings.DOMAIN_NAME}/chalets/chalet/view/{booking.id}/"

    # Redirect to the actual booking URL
    return redirect(actual_url)


class ChaletImageUploadView(View):
    def post(self, request, *args, **kwargs):
        try:
            chalet_id = request.POST.get('room_id')
            image_id = request.POST.get('image_id')
            file = request.FILES.get('image')

            # Validate that the file is provided
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

            # Validate the chalet
            chalet = get_object_or_404(Chalet, id=chalet_id)

            # Validate the image associated with the chalet
            chalet_image = get_object_or_404(ChaletImage, id=image_id, chalet=chalet)

            # Update the image
            chalet_image.image = file
            chalet_image.save()
            logger.info(f"Image successfully uploaded for Chalet ID {chalet_id}, Image ID {image_id}.")
            return JsonResponse({'message': _('Image uploaded successfully.')})
        
        except Chalet.DoesNotExist:
            logger.error(f"Chalet not found with ID: {chalet_id}.")
            return JsonResponse({'error': _('Chalet not found.')}, status=404)

        except ChaletImage.DoesNotExist:
            logger.error(f"ChaletImage not found with ID: {image_id} for Chalet ID: {chalet_id}.")
            return JsonResponse({'error': _('Chalet image not found.')}, status=404)

        except Exception as e:
            logger.exception(f"Unexpected error occurred: {str(e)}")
            return JsonResponse({'error': _('An unexpected error occurred.')}, status=500)

class ChaletInfoEdit(View):
    def get(self, request, *args, **kwargs):
        chalet_id = kwargs.get('chalet_id')
        
        try:
            chalet = Chalet.objects.get(id=chalet_id)
        except Chalet.DoesNotExist:
            logger.error(f"Chalet with ID {chalet_id} not found.")
            return JsonResponse({'error': _('Chalet not found')}, status=404)
        
        weekend_price = None
        try:
            if hasattr(chalet, 'weekend_price') and chalet.weekend_price.is_active:
                weekend_price = chalet.weekend_price.weekend_price
        except Exception as e:
            logger.error(f"Error retrieving weekend price for Chalet {chalet_id}: {e}")
        
        amenities = chalet.amenities.filter(status=True)
        
        amenities_data = []
        for amenity in amenities:
            amenity_info = {
                'english': amenity.amenity_name,
                'arabic': amenity.amenity_name_arabic if amenity.amenity_name_arabic else amenity.amenity_name
            }
            amenities_data.append(amenity_info)
        
        logger.info(f"Retrieved amenities for Chalet {chalet_id}: {amenities_data}")

        response_data = {
            'chalet_name': chalet.name,
            'total_price': chalet.total_price,
            'weekend_price': weekend_price if weekend_price else "",
            'amenities': amenities_data,
        }

        return JsonResponse(response_data)

    def post(self, request, *args, **kwargs):
        chalet_id = kwargs.get('chalet_id')
        
        try:
            chalet = Chalet.objects.get(id=chalet_id)
        except Chalet.DoesNotExist:
            logger.error(f"Chalet with ID {chalet_id} not found.")
            return JsonResponse({'error': _('Chalet not found')}, status=404)

        price_per_night = request.POST.get('price_per_night')
        weekend_price = request.POST.get('weekend_price')
        amenities = request.POST.getlist('amenitiesedit')

        logger.info(f"Received price per night: {price_per_night}, weekend price: {weekend_price}, amenities: {amenities}")

        try:
            if price_per_night:
                chalet.total_price = price_per_night

            # Handle weekend price
            if weekend_price:
                if hasattr(chalet, 'weekend_price'):
                    chalet.weekend_price.weekend_price = weekend_price
                    chalet.weekend_price.save()
                    logger.info(f"Updated weekend price for Chalet {chalet_id} to {weekend_price}.")
                else:
                    ChaletWeekendPrice.objects.create(chalet=chalet, weekend_price=weekend_price)
                    logger.info(f"Created new weekend price for Chalet {chalet_id} with value {weekend_price}.")
            else:
                # If no weekend price is provided, delete the existing record if it exists
                if hasattr(chalet, 'weekend_price'):
                    chalet.weekend_price.delete()
                    logger.info(f"Deleted weekend price for Chalet {chalet_id} as no value was provided.")

            # Handle amenities
            if amenities:
                selected_amenities = Amenity.objects.filter(amenity_name__in=amenities)
                chalet.amenities.set(selected_amenities)
                logger.info(f"Set amenities for Chalet {chalet_id}: {amenities}")
            else:
                logger.info(f"No amenities selected for Chalet {chalet_id}.")
            
            chalet.save()
            logger.info(f"Updated Chalet {chalet_id} successfully.")
        except Exception as e:
            logger.error(f"Error occurred while updating Chalet {chalet_id}: {e}")
            return JsonResponse({"error": _("An error occurred, please try again later")}, status=500)

        return redirect("chalet_management")
    
    
import pandas as pd
import io
from xlsxwriter.utility import xl_rowcol_to_cell
class ChaletTransactionExcelDownloadView(View):
    def get(self, request):
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        payment_method = request.GET.get('payment_method')
        transaction_status = request.GET.get('transaction_status')
        booking_status = request.GET.get('booking_status')
        
   
        if request.session:
            print("sessionif")
            try:
                lang=request.session["django_language"]
            except Exception as e:
                lang='en'
        else:
            print("sessionelse")
            lang='en'
        logger.info(f"requested language session is:{lang}")
        
        try:
            user = VendorProfile.objects.get(user=request.user)
            chalet_id=request.GET.get('chalet_id')
            logger.info(f"------{chalet_id}")
            if chalet_id:
                chalet =  Chalet.objects.get(vendor=user.id,id=chalet_id)
            else:
                chalet =  Chalet.objects.filter(vendor=user.id).first()
            
            logger.info(f"--------{chalet}")
            transactions = ChaletBooking.objects.filter(
                    chalet=chalet,
                ).select_related('transaction').prefetch_related('transaction__vendor_transaction','transaction__admin_transaction').order_by('-modified_date')
            transactions = transaction_list_filter(transactions = transactions, from_date = from_date,  to_date = to_date, payment_method = payment_method, transaction_status = transaction_status, booking_status = booking_status)
            user = "chalet"
            data_frame = report_data_frame(transactions,user,lang)
            if data_frame:
                df = pd.DataFrame(data_frame)
                # Set index to start from 1
                df.index = df.index + 1  
                df.reset_index(inplace=True) 
                if lang=='en':
                    df.rename(columns={'index': 'S.No'}, inplace=True)
                else:
                    df.rename(columns={'index': 'س.لا'}, inplace=True)
                print(len(df.columns))
                # df.rename(columns={'index': 'S.No'}, inplace=True)
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
            logger.error(f"Exception raised in ChaletTransactionExcelDownload View. Exception: {e}")


class RoomnumberExistView(View):
    def get(self,request):
        user = VendorProfile.objects.get(user=request.user)
        chalet =  Chalet.objects.filter(vendor=user.id).first()
        room_number = request.GET.get('room_number')
        print(f"Received room_number: {room_number}")  
        logger.info(f"Received room_number: {room_number}") 
        try:
            exists = False
            if room_number:
                exists = PropertyManagement.objects.filter( room_number=room_number,chalet=chalet,status="active").exists()
            print(f"Room exists: {exists}")  
            logger.info(f"Room exists: {exists}")  
            return JsonResponse({'exists': exists})
        except Exception as e:
            print(f"Error: {e}") 
            logger.info(f"Error: {e}") 
            return JsonResponse({'exists': False, 'error': str(e)}, status=500)
