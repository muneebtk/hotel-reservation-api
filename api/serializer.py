import os
import re
import logging
import phonenumbers
from collections import defaultdict
from decimal import Decimal
from urllib.parse import urljoin
from rest_framework.exceptions import ValidationError
from django.db import DatabaseError
from django.utils.timezone import now
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from datetime import date, datetime, timedelta
from django.db.models import Avg, Q, Count,Min,F,Sum
from dj_rest_auth.registration.serializers import SocialLoginSerializer
from api.function import _calculate_average_price, calculate_hotel_price, get_discounted_price_for_property, get_discounted_price_for_room,get_payment_details,calculate_minimum_hotel_price
from rest_framework import serializers
from Bookingapp_1969 import settings
from api.function import get_available_rooms
from user.models import Userdetails
from vendor.models import  HotelImage, HotelType, MealPrice, Roomtype,Hotel,RoomManagement,RecentReview,CommissionSlab, RoomImage,Bookedrooms, Booking,Favorites,Cancelbooking,RoomRefundPolicy
from common.models import Amenity,PolicyName,Categories
from chalets.models import ChaletRecentReview,Chalet,ChaletImage,Comparison,Featured,ChaletFavorites, CancelChaletBooking,Promotion,ChaletBooking,Notification


logger = logging.getLogger(__name__)


class RegisteruserSerializer(serializers.ModelSerializer):
    username = serializers.CharField(allow_null=True, max_length=50, required=False)
    first_name = serializers.CharField(allow_null=True, max_length=50, required=False)
    last_name = serializers.CharField(allow_null=True, max_length=50, required=False)
    email = serializers.EmailField(allow_blank=True)
    contact_number = serializers.CharField(max_length=15, required=False, allow_blank=True)
    dial_code=serializers.CharField(required=False, allow_blank=True, allow_null=True)
    iso_code=serializers.CharField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(allow_null=True, max_length=20, required=False)
    confirm_password = serializers.CharField(allow_null=True, max_length=20, required=False)
    referral_token = serializers.CharField(allow_null=True, max_length=70, required=False)
    fcmToken = serializers.CharField(max_length=255, required=False, allow_blank=True)

    class Meta:
        model = Userdetails
        fields = ['username', 'first_name', 'last_name', 'email', 'contact_number', 'password', 'confirm_password', 'referral_token', 'fcmToken','dial_code','iso_code']
       
         
        
class Emailverifivation(serializers.Serializer):
    otp = serializers.IntegerField(required=False)
    stored_otp = serializers.IntegerField(required=False)
    stored_email = serializers.EmailField(required=False)
        
class LoginUserSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True)
    device_name = serializers.CharField(required=False, allow_blank=True)  
    platform = serializers.CharField(required=False, allow_blank=True) 
    fcmToken = serializers.CharField(max_length=255, required=False, allow_blank=True)
        
class CategoryListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categories
        fields = '__all__'
        
class HotelSearchSerializer(serializers.Serializer):
    latitude = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)
    city_name = serializers.CharField(required=False, allow_blank=True)
    hotel_name = serializers.CharField(required=False, allow_blank=True)
    checkin_date = serializers.DateField(required=False, allow_null=True)
    checkout_date = serializers.DateField(required=False, allow_null=True)
    checkin_time = serializers.TimeField(required=False, allow_null=True)
    checkout_time = serializers.TimeField(required=False, allow_null=True)
    room = serializers.IntegerField(required=False, default=0)
    adults = serializers.IntegerField(required=False, default=1)  # New field for adults
    children = serializers.IntegerField(required=False, default=0)  # New field for children
    members = serializers.IntegerField(required=False, default=0)  # Optional: Total number of people if needed
    property_type = serializers.CharField(required=False, allow_blank=True)
    sorted = serializers.CharField(required=True)
    filter = serializers.DictField(
        child=serializers.ListField(
            child=serializers.CharField()
        ),
        required=False
    )
    priceRange = serializers.ListField(
        child=serializers.DecimalField(max_digits=11, decimal_places=3),
        required=False,
        allow_empty=True
    )

    def validate_priceRange(self, value):
        if value and len(value) != 2:
            raise serializers.ValidationError("Price range should contain exactly two values (min and max).")
        return value

class HotelArabSerializer(serializers.Serializer):
    hotel_id = serializers.SerializerMethodField()
    hotel_name = serializers.SerializerMethodField()
    hotel_address = serializers.SerializerMethodField()
    price_per_night = serializers.SerializerMethodField()
    # room_types = serializers.SerializerMethodField()
    hotel_image = serializers.SerializerMethodField()
    avguserrating = serializers.SerializerMethodField()
    hotel_rating = serializers.SerializerMethodField()
    avalibale_room_types = serializers.SerializerMethodField()
    best_offers_common  = serializers.SerializerMethodField()
    compare=serializers.SerializerMethodField()
    is_favorite=serializers.SerializerMethodField()
    hoteltype = serializers.SerializerMethodField()
    city_name=serializers.SerializerMethodField()
    
    
    
    def get_hoteltype(self, obj):
        hotel_type_dict = {}
        if obj and obj.hotel_type and obj.hotel_type.status == "active":
            hotel_type_dict['type'] = obj.hotel_type.arabic_name
            hotel_type_dict['icon'] = urljoin(settings.MEDIA_URL, str(obj.hotel_type.icon))
        else:
            hotel_type_dict = {"type": None, "icon": None}
        return hotel_type_dict
    
    def get_best_offers_common(self, obj):
        logger.info(f"enter inside best_offers_common")
        get_promotion_discount_percentage =  Promotion.objects.filter(
                Q(hotel=obj) | Q(multiple_hotels__in=[obj]),
                category="common",
                discount_percentage__isnull=False,
                status="active",
                start_date__lte=now().date(),
                end_date__gte=now().date()
                
            ).order_by("-discount_percentage").first()
        if get_promotion_discount_percentage:
            logger.info(f"get_promotion_discount_percentage: {get_promotion_discount_percentage}")
            discount_cal = (Decimal(get_promotion_discount_percentage.discount_percentage) / Decimal(100)) * Decimal(min(self.get_price_per_night(obj)))
            logger.info(f"discount_cal: {discount_cal}")
            if get_promotion_discount_percentage:
                data = {
                    "promotion_id":get_promotion_discount_percentage.id,
                    "title":get_promotion_discount_percentage.title,
                    "description":get_promotion_discount_percentage.description,
                    "discount_percentage":get_promotion_discount_percentage.discount_percentage,
                    "start_date":get_promotion_discount_percentage.start_date,
                    "end_date":get_promotion_discount_percentage.end_date,
                    "minimum_spend":get_promotion_discount_percentage.minimum_spend,
                    "statue":get_promotion_discount_percentage.status,
                    "source":get_promotion_discount_percentage.source,
                    "discounted_price": Decimal(f"{min(self.get_price_per_night(obj)) - discount_cal:.3f}")

                }
                logger.info(f"data: {data}")
                return data
        else:
            return None
    
    def get_hotel_id(self, obj):
        return obj.id
    
    def get_hotel_name(self, obj): 
        return obj.name_arabic
    
    def get_hotel_address(self, obj):
        return obj.address
    def get_compare(self,obj):
        user = self.context['request'].user 
        if user.id is not None:
            logger.info(f"\n\n\n\nuser -----> {user} ------> {user.id}\n\n\n")
            userdetail=Userdetails.objects.filter(user=user.id).first()
            logger.info(f"\n\n\nuserdetail -------> {userdetail}\n\n\n")
            comparison = Comparison.objects.filter(hotel=obj.id,user=userdetail.id, status="active").exists()
            return comparison
        else:
            return None
    def get_price_per_night(self, obj):
        logger.info("Inside get_price_per_night...")
        request = self.context.get('request')
        if not request:
            logger.warning("Request context is missing.")
            return None

        try:
            # Parse session data
            checkin_date = datetime.strptime(request.session.get('checkin_date'), "%Y-%m-%d").date()
            checkout_date = datetime.strptime(request.session.get('checkout_date'), "%Y-%m-%d").date()
            members = request.session.get('members')
            rooms_required = request.session['rooms']
            print(f"members is --- {members} and rooms required is --- {rooms_required}")
            logger.info(f"Session data -> Checkin: {checkin_date}, Checkout: {checkout_date}, Members: {members}, Rooms Required: {rooms_required}")

            # Call the price calculation function
            price_result = calculate_minimum_hotel_price(
                hotel_id=obj.id,
                calculation_logic="average_price",
                checkin_date=checkin_date,
                checkout_date=checkout_date,
                members=members,
                rooms_required=rooms_required,
            )


            if "error" in price_result:
                logger.error(f"Price calculation error: {price_result['error']}")
                return None

            calculated_price = price_result.get("calculated_price")
            logger.info(f"Calculated average price for hotel {obj.id}: {calculated_price}")
            return [calculated_price]  # Return as a list for consistency

        except Exception as e:
            logger.error(f"Error in get_price_per_night: {str(e)}")
            return None
    
    def get_hotel_image(self, obj):
        hotel_image = HotelImage.objects.filter(hotel = obj.id, is_main_image = True)
        image_path = []
        count = 0
        
        for image in hotel_image:
            if count < len(hotel_image):
                image_url = urljoin(settings.MEDIA_URL, str(image.image))
                image_path.append(image_url)
                count += 1
            else:
                break
                
        return image_path
    
    def get_avguserrating(self, obj):
        reviews = RecentReview.objects.filter(hotel = obj).aggregate(Avg('rating', default=0)).get('rating__avg')
        return reviews
    def get_hotel_rating(self, obj):
        return obj.hotel_rating
    def get_city_name(self, obj):
        try:
            if obj.city.arabic_name:
                return obj.city.arabic_name
            else:
                return None
        except Exception as e:
            logger.error(f"An exception occured at the get_city_name function as {e}")
    
    def get_avalibale_room_types(self, obj):
        get_room_obj = RoomManagement.objects.filter(hotel=obj,status="active")
        roomtype_list = []
        for room in get_room_obj:
            roomtype_list.append(room.room_types.room_types)
            
        return roomtype_list
    
    def get_is_favorite(self,obj):
        user = self.context['request'].user
        if user.id is not None:
            logger.info(f"user:{user}")
            userdetail=Userdetails.objects.filter(user=user.id).first()
            logger.info(f"userdetail:{userdetail}")
            get_favorites = Favorites.objects.filter(hotel=obj.id,user=userdetail.id,is_liked=True).exists()
            return  get_favorites
        else:
            return None
        
class HotelSerializer(serializers.Serializer):
    hotel_id = serializers.SerializerMethodField()
    is_favorite=serializers.SerializerMethodField()
    hotel_name = serializers.SerializerMethodField()
    hotel_address = serializers.SerializerMethodField()
    price_per_night = serializers.SerializerMethodField()
    # room_type = serializers.SerializerMethodField()
    compare=serializers.SerializerMethodField()
    hotel_image = serializers.SerializerMethodField()
    avguserrating = serializers.SerializerMethodField()
    hotel_rating = serializers.SerializerMethodField()
    avalibale_room_types = serializers.SerializerMethodField()
    best_offers_common  = serializers.SerializerMethodField()
    hoteltype = serializers.SerializerMethodField()
    city_name=serializers.SerializerMethodField()
    
    def get_hoteltype(self, obj):
        hotel_type_dict = {}
        try:
            if obj and obj.hotel_type and obj.hotel_type.status == "active":
                hotel_type_dict['type'] = obj.hotel_type.name
                hotel_type_dict['icon'] = urljoin(settings.MEDIA_URL, str(obj.hotel_type.icon))
            else:
                hotel_type_dict = {"type": None, "icon": None}
        except Exception as e:
            logger.error(f"An exception occured at the get_hoteltype function as {e}")
        return hotel_type_dict
        
    
    def get_best_offers_common(self, obj):
        try:
            logger.info(f"enter inside best_offers_common")
            get_promotion_discount_percentage = Promotion.objects.filter(
                Q(hotel=obj) | Q(multiple_hotels__in=[obj]),
                category="common",
                discount_percentage__isnull=False,
                status="active",
                start_date__lte=now().date(),
                end_date__gte=now().date()

            ).order_by("-discount_percentage").first()
            if get_promotion_discount_percentage:
                logger.info(f"get_promotion_discount_percentage: {get_promotion_discount_percentage}")
                discount_cal = (Decimal(get_promotion_discount_percentage.discount_percentage) / Decimal(100)) * Decimal(min(self.get_price_per_night(obj)))
                logger.info(f"discount_cal: {discount_cal}")
                if get_promotion_discount_percentage:
                    data = {
                        "promotion_id":get_promotion_discount_percentage.id,
                        "title":get_promotion_discount_percentage.title,
                        "description":get_promotion_discount_percentage.description,
                        "discount_percentage":get_promotion_discount_percentage.discount_percentage,
                        "start_date":get_promotion_discount_percentage.start_date,
                        "end_date":get_promotion_discount_percentage.end_date,
                        "minimum_spend":get_promotion_discount_percentage.minimum_spend,
                        "statue":get_promotion_discount_percentage.status,
                        "source":get_promotion_discount_percentage.source,
                        "discounted_price": Decimal(f"{min(self.get_price_per_night(obj)) - discount_cal:.3f}")

                    }
                    logger.info(f"data: {data}")
                    return data
                else:
                    return None
        except Exception as e:
            logger.error(f"An exception occured at the get_best_offers_common function as {e}")
            return None

    def get_compare(self,obj):
        try:
            user = self.context['request'].user
            if user.id is not None:
                logger.info(f"\n\n\n if user.id is not None: ------------>>>>>>>>>>>>>>\n\n\n")
                logger.info(f"\n\n\n\nuser -----> {user} ------>\n\n\n")
                userdetail=Userdetails.objects.filter(user=user.id).first()
                logger.info(f"\n\n\nuserdetail -------> {userdetail}\n\n\n")
                comparison = Comparison.objects.filter(hotel=obj.id,user=userdetail.id, status="active").exists()
                return comparison
            else:
                return None
        except Exception as e:
            logger.error(f"An exception occured at the  get_compare function as {e}")
            return None

    def get_is_favorite(self,obj):
        try:
            user = self.context['request'].user
            if user.id is not None:
                logger.info(f"user:{user}")
                userdetail=Userdetails.objects.filter(user=user.id).first()
                logger.info(f"userdetail:{userdetail}")
                get_favorites = Favorites.objects.filter(hotel=obj.id,user=userdetail.id,is_liked=True).exists()
                return  get_favorites
            else:
                return None
        except Exception as e:
            logger.error(f"An exception occured at the  get_is_favorite function as {e}")
            return None

    
    def get_hotel_id(self, obj):
        try:
            logger.info(f"inside get_hotel_id ----->>>>>>>>>>>>>>>>>>>>>>>>>")
            return obj.id
        except Exception as e:
            logger.error(f"An exception occured at the  get_hotel_id function as {e}")
            return None
    
    def get_hotel_name(self, obj):
        try:
            logger.info(f"inside get_hotel_name ----->>>>>>>>>>>>>>>>>>>>>>>>>")
            return obj.name
        except Exception as e:
            logger.error(f"An exception occured at the  get_hotel_name function as {e}")
            return None
    def get_city_name(self, obj):
        try:
            return obj.city.name
        except Exception as e:
            logger.error(f"An exception occured at the get_city_name function as {e}")
    
    
    def get_hotel_address(self, obj):
        try:
            logger.info(f"inside get_hotel_address ----->>>>>>>>>>>>>>>>>>>>>>>>>")
            return obj.address
        except Exception as e:
            logger.error(f"An exception occured at the  get_hotel_addres function as {e}")
            return None
    
    def get_price_per_night(self, obj):
        logger.info("Inside get_price_per_night...")
        request = self.context.get('request')
        if not request:
            logger.warning("Request context is missing.")
            return None

        try:
            # Parse session data
            checkin_date = datetime.strptime(request.session.get('checkin_date'), "%Y-%m-%d").date()
            checkout_date = datetime.strptime(request.session.get('checkout_date'), "%Y-%m-%d").date()
            members = request.session.get('members')
            rooms_required = request.session['rooms']
            print(f"members is --- {members} and rooms required is --- {rooms_required}")
            logger.info(f"Session data -> Checkin: {checkin_date}, Checkout: {checkout_date}, Members: {members}, Rooms Required: {rooms_required}")

            # Call the price calculation function
            price_result = calculate_minimum_hotel_price(
                hotel_id=obj.id,
                calculation_logic="average_price",
                checkin_date=checkin_date,
                checkout_date=checkout_date,
                members=members,
                rooms_required=rooms_required,
            )


            if "error" in price_result:
                logger.error(f"Price calculation error: {price_result['error']}")
                return None

            calculated_price = price_result.get("calculated_price")
            logger.info(f"Calculated average price for hotel {obj.id}: {calculated_price}")
            return [calculated_price]  # Return as a list for consistency

        except Exception as e:
            logger.error(f"Error in get_price_per_night: {str(e)}")
            return None

    
    def get_hotel_image(self, obj):
        try:
            logger.info(f"inside get_hotel_image ----->>>>>>>>>>>>>>>>>>>>>>>>>")
            hotel_image = HotelImage.objects.filter(hotel = obj.id, is_main_image = True)
            print(hotel_image)
            image_path = []
            count = 0
            logger.info(f"hotel_image: {hotel_image}")
            print(f"hotel_image: {hotel_image}")
            for image in hotel_image:
                if count < len(hotel_image):
                    image_url = urljoin(settings.MEDIA_URL, str(image.image))
                    image_path.append(image_url)
                    count += 1
                else:
                    break
                    
            return image_path
        except Exception as e:
            logger.error(f"An exception occured at the  get_hotel_image function as: {e}")
            return None
    
    def get_avguserrating(self, obj):
        try:
            logger.info(f"inside get_avguserrating ----->>>>>>>>>>>>>>>>>>>>>>>>>")
            reviews = RecentReview.objects.filter(hotel = obj).aggregate(Avg('rating', default=0)).get('rating__avg')
            return round(reviews,1)
        except Exception as e:
            logger.error(f"An exception occured at the  get_avguserrating function as: {e}")
            return None
    def get_hotel_rating(self, obj):
        try:
            logger.info(f"inside get_hotel_rating ----->>>>>>>>>>>>>>>>>>>>>>>>>")
            return obj.hotel_rating
        except Exception as e:
            logger.error(f"An exception occured at the  get_hotel_rating function as: {e}")
            return None
        
        
    def get_avalibale_room_types(self, obj):
        try:
            logger.info(f"inside get_avalibale_room_types ----->>>>>>>>>>>>>>>>>>>>>>>>>")
            get_room_obj = RoomManagement.objects.filter(hotel=obj, status="active")
            roomtype_list = []
            for room in get_room_obj:
                roomtype_list.append(room.room_types.room_types)
                
            return roomtype_list
        except Exception as e:
            logger.error(f"An exception occured at the  get_avalibale_room_types function as: {e}")
            return None
        
    
    
# class PropertyDetails(serializers.ModelSerializer):
#     class Meta:
#         model = Hotel
#         fields = '__all__'


class PropertyDetails(serializers.ModelSerializer):
    vendor_first_name = serializers.SerializerMethodField()
    hotel_name = serializers.SerializerMethodField()
    city_name = serializers.SerializerMethodField()
    country_name = serializers.SerializerMethodField()
    state_name = serializers.SerializerMethodField()
    locality = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    roomtype_name = serializers.SerializerMethodField()
    aminity_name = serializers.SerializerMethodField()
    hotel_image = serializers.SerializerMethodField()
    policies = serializers.SerializerMethodField()
    cancellation_policy = serializers.SerializerMethodField()
    number_of_reviews = serializers.SerializerMethodField()
    number_of_ratings = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()
    numbers_of_total_1_star = serializers.SerializerMethodField()
    numbers_of_total_2_star = serializers.SerializerMethodField()
    numbers_of_total_3_star = serializers.SerializerMethodField()
    numbers_of_total_4_star = serializers.SerializerMethodField()
    numbers_of_total_5_star = serializers.SerializerMethodField()
    avg_rating_last_6_months = serializers.SerializerMethodField()
    country_tax = serializers.SerializerMethodField()
    country_currency = serializers.SerializerMethodField()
    about_property = serializers.SerializerMethodField()
    hotel_policies  = serializers.SerializerMethodField()
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()
    number_of_rooms = serializers.SerializerMethodField()
    rooms_available = serializers.SerializerMethodField()
    is_favorite=serializers.SerializerMethodField()
    property_type = serializers.SerializerMethodField()
    class Meta:
        model = Hotel
        fields = ["id","vendor_first_name",'hotel_name',"city_name","country_name","state_name","hotel_image","category_name","roomtype_name","office_number"
                  ,"address","number_of_rooms","rooms_available","hotel_rating","cr_number","vat_number","date_of_expiry",
                  "logo","hotel_id","about_property","policies","cancellation_policy","locality","post_approval","aminity_name",
                  "number_of_reviews","number_of_ratings","reviews","avg_rating","numbers_of_total_1_star","numbers_of_total_2_star","numbers_of_total_3_star"
                  ,"numbers_of_total_4_star","numbers_of_total_5_star","avg_rating_last_6_months","country_tax","country_currency", "hotel_policies", "lat","lng","checkin_time","checkout_time","is_favorite","property_type"]
    def get_number_of_rooms(self, obj):
        """
        Calculate the total number of rooms for the hotel.
        """
        return RoomManagement.objects.filter(hotel=obj, status='active').count()

    def get_rooms_available(self, obj):
        """
        Calculate the number of available rooms for the hotel.
        """
        return RoomManagement.objects.filter(hotel=obj, availability=True, status='active').count()
    def __init__(self, *args, **kwargs):
        context = kwargs.get('context', {})  # Safely get context
        self.language = context.get('request', {}).GET.get('lang', 'en') if context.get('request') else 'en'
        super().__init__(*args, **kwargs)
        
    def get_property_type(self, obj):
        hotel_type_dict = {}
        if obj and obj.hotel_type and obj.hotel_type.status == "active":
            if self.language == "ar":
                hotel_type_dict['type'] = obj.hotel_type.arabic_name
                hotel_type_dict['icon'] = urljoin(settings.MEDIA_URL, str(obj.hotel_type.icon))
                return hotel_type_dict
            elif self.language == "en":
                hotel_type_dict['type'] = obj.hotel_type.name
                hotel_type_dict['icon'] = urljoin(settings.MEDIA_URL, str(obj.hotel_type.icon))
                return hotel_type_dict
            else:
                hotel_type_dict['type'] = obj.hotel_type.name
                hotel_type_dict['icon'] = urljoin(settings.MEDIA_URL, str(obj.hotel_type.icon))
                return hotel_type_dict
        else:
            hotel_type_dict = {"type": None, "icon": None}
            return hotel_type_dict
    def get_lat(self, obj):
        """
        Get latitude  associated with the hotel.
        """
        return obj.latitude if obj.latitude  else None

    def get_lng(self, obj):
        """
        Get longitude associated with the hotel.
        """
        return obj.longitude if obj.longitude  else None
    
    def get_vendor_first_name(self, obj):
        return obj.vendor.user.first_name if obj.vendor and obj.vendor.user else None
    def get_hotel_name(self, obj):
        if self.language == "ar":
            return obj.name_arabic
        elif self.language == "en":
            return obj.name
        else:
            return obj.name
    def get_city_name(self, obj):
        if self.language == "ar":
            return obj.city.arabic_name if obj.city else None
        elif self.language == "en":
            return obj.city.name if obj.city else None
    
    def get_country_name(self, obj):
        return obj.country.name if obj.country else None
    
    def get_state_name(self, obj):
        return obj.state.name if obj.state else None
    
    def get_locality(self, obj):
        return obj.city.name
    
    def get_category_name(self, obj):
        return obj.category.all().values('category') if obj.category.all().values('category') else None
    
    def get_is_favorite(self,obj):
        user = self.context['request'].user
        if user.id is not None:
            logger.info(f"user:{user}")
            userdetail=Userdetails.objects.filter(user=user.id).first()
            logger.info(f"userdetail:{userdetail}")
            get_favorites = Favorites.objects.filter(hotel=obj.id,user=userdetail.id,is_liked=True).exists()
            return  get_favorites
        else:
            return None
    
    def get_roomtype_name(self, obj):
        room_type_list = []
        rooms = RoomManagement.objects.filter(hotel=obj, status='active')
        for room in rooms:
            room_type_list.append(room.room_types.room_types)
        return room_type_list
    
    def get_aminity_name(self, obj):
        aminity =  obj.amenities.all()
        aminity_list = []
        for ami in aminity:
            if ami.amenity_type == "Property_amenity":
                icon_url = urljoin(settings.MEDIA_URL, str(ami.icon))
                if self.language == "ar":
                    amenity_name = ami.amenity_name_arabic if ami.amenity_name_arabic else ami.amenity_name
                elif self.language == "en":
                    amenity_name = ami.amenity_name
                else:
                    amenity_name = ami.amenity_name
                aminity_list.append((amenity_name, icon_url))
        return aminity_list
    
    def get_hotel_image(self, obj):
        hotel_image = HotelImage.objects.filter(hotel = obj.id)
        image_path = []
        count = 0
        
        for image in hotel_image:
            if count < len(hotel_image):
                image_url = urljoin(settings.MEDIA_URL, str(image.image))
                image_path.append(image_url)
                count += 1
            else:
                break
                
        return image_path
    
    def get_policies(self, obj):
        policy_categories = obj.policies.all()
        policy_dict = defaultdict(list)
        for category in policy_categories:
            policy_names = category.policy_names.filter(hotel=obj) 
            for policy_name in policy_names:
                policy_dict[category.name].append(policy_name.title)
        return policy_dict
    
    def get_cancellation_policy(self, obj):
        try:
            cancellation_categories = obj.policies.filter(name__icontains="cancel")
            if cancellation_categories.exists():
                logger.info(f"Cancellation categories found for Chalet: {obj.name} (ID: {obj.id})")
                cancellation_policies = []

                for category in cancellation_categories:
                    policies = category.policy_names.filter(hotel=obj)
                    cancellation_policies.extend([policy.title for policy in policies])
                return cancellation_policies
            else:
                logger.warning(f"No cancellation category found for Chalet: {obj.name} (ID: {obj.id})")

        except Exception as e:
            logger.error(
                f"Error fetching cancellation policies for Chalet: {obj.name} (ID: {obj.id}): {e}",
                exc_info=True,
            )
        return []
    
    def get_number_of_reviews(self, obj):
        return RecentReview.objects.filter(hotel=obj).exclude(review_text__isnull=True).exclude(review_text__exact="").count()

    def get_number_of_ratings(self, obj):
        return RecentReview.objects.filter(hotel=obj).exclude(rating__isnull=True).exclude(rating=0.0).count()

    def get_reviews(self, obj):
        return RecentReview.objects.filter(hotel=obj).exclude(review_text__isnull=True).exclude(review_text__exact="").values(
        'username', 'rating', 'review_text', 'date' ).order_by('-id')[:5]
   


    def get_avg_rating(self, obj):
        avg_rating = RecentReview.objects.filter(hotel=obj).aggregate(
            avg_rating=Avg('rating')
        )['avg_rating']
        return round(avg_rating or 0.0, 1)

    def get_numbers_of_total_star(self, obj, star_rating):
        return RecentReview.objects.filter(hotel=obj, rating=star_rating).count()

    def get_numbers_of_total_1_star(self, obj):
        return self.get_numbers_of_total_star(obj, 1.0)

    def get_numbers_of_total_2_star(self, obj):
        return self.get_numbers_of_total_star(obj, 2.0)

    def get_numbers_of_total_3_star(self, obj):
        return self.get_numbers_of_total_star(obj, 3.0)

    def get_numbers_of_total_4_star(self, obj):
        return self.get_numbers_of_total_star(obj, 4.0)

    def get_numbers_of_total_5_star(self, obj):
        return self.get_numbers_of_total_star(obj, 5.0)

    def get_avg_rating_last_6_months(self, obj):
        
        six_months_ago = timezone.now() - relativedelta(months=6)
        avg_rating = RecentReview.objects.filter(
            hotel=obj, date__gte=six_months_ago
        ).aggregate(avg_rating=Avg('rating'))['avg_rating']
        return round(avg_rating or 0.0, 1)
    
    def get_country_tax(self, obj):
        return obj.country.tax
    
    def get_country_currency(self, obj):
        return obj.country.currency
    
    def get_about_property(self, obj):
        if self.language == "ar":
            return obj.about_property_arabic
        elif self.language == "en":
            return obj.about_property
        else:
            return obj.about_property
    def get_hotel_policies(self, obj):
        if self.language == "ar":
            return obj.hotel_policies_arabic
        elif self.language == "en":
            return obj.hotel_policies
        else:
            return obj.hotel_policies
            
class PropertyDetailsChalet(serializers.ModelSerializer):
    vendor_first_name = serializers.SerializerMethodField()
    city_name = serializers.SerializerMethodField()
    country_name = serializers.SerializerMethodField()
    state_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    property_type = serializers.SerializerMethodField()

    class Meta:
        model = Hotel
        fields = '__all__'

    def get_vendor_first_name(self, obj):
        return obj.vendor.user.first_name if obj.vendor and obj.vendor.user else None
    
    def get_city_name(self, obj):
        return obj.city.name if obj.city else None
    
    def get_country_name(self, obj):
        return obj.country.name if obj.country else None
    
    def get_state_name(self, obj):
        return obj.state.name if obj.state else None
    
    def get_category_name(self, obj):
        return obj.category.all().values('category') if obj.category.all().values('category') else None
    
    def get_property_type(self, obj):
        return obj.property_types.all().values('id','property_types')



        
class RoomlistingSerializer(serializers.ModelSerializer):
    roomtype_name = serializers.SerializerMethodField()
    room_price = serializers.SerializerMethodField()
    breakfast_price = serializers.SerializerMethodField()
    lunch_price = serializers.SerializerMethodField()
    dinner_price = serializers.SerializerMethodField()
    room_images = serializers.SerializerMethodField()
    aminity_name = serializers.SerializerMethodField()
    meals = serializers.SerializerMethodField()
    refund_policy = serializers.SerializerMethodField()
    total_occupancy = serializers.SerializerMethodField()
    available_rooms = serializers.SerializerMethodField()
    class Meta:
        model = RoomManagement
        fields = ["id","roomtype_name","total_occupancy","availability","price_per_night","hotel","meals","room_price",
                  "breakfast_price","lunch_price","dinner_price","availability","room_images","aminity_name","refund_policy", "available_rooms"]
    
    def __init__(self, *args, **kwargs):
        context = kwargs.get('context', {})
        self.language = context.get('request', {}).GET.get('lang', 'en') if context.get('request') else 'en'
        super().__init__(*args, **kwargs)

    def get_total_occupancy(self, obj):
        return obj.total_occupancy
    
    def get_available_rooms(self, obj):
        request = self.context.get('request')
        checkin_date = request.query_params.get('checkin_date')
        checkout_date = request.query_params.get('checkout_date')
        checkin_date_obj = datetime.strptime(checkin_date, '%Y-%m-%d').date()
        checkout_date_obj = datetime.strptime(checkout_date, '%Y-%m-%d').date()
        booked_room_no = Bookedrooms.objects.filter(
            room=obj,
            booking__checkin_date__lt=checkout_date_obj,
            booking__checkout_date__gt=  checkin_date_obj,
            booking__status__in=["pending","booked","confirmed","Confirmed","Booked","Pending","check-in", "Check-In"]
        ).aggregate(total=Sum('no_of_rooms_booked'))['total'] or 0
        rooms_available=obj.number_of_rooms - booked_room_no
        return rooms_available

    def get_roomtype_name(self, obj):
        roomtype_list = []
        roomtypedict = {}
        
        roomtypedict['id'] = obj.room_types.id
        roomtypedict['room_types'] = obj.room_types.room_types
        roomtypedict['room_types_arabic']=obj.room_types.room_types_arabic
        roomtype_list.append(roomtypedict)
        return roomtype_list
    
    def get_room_price(self, obj):
        request = self.context.get('request')
        checkin_date = request.query_params.get('checkin_date')
        checkout_date = request.query_params.get('checkout_date')
        checkin_date_obj = datetime.strptime(checkin_date, '%Y-%m-%d').date()
        checkout_date_obj = datetime.strptime(checkout_date, '%Y-%m-%d').date()
        members = request.query_params.get('members', 1)
        rooms_required = request.query_params.get('rooms', 1)

        # Call the calculate_hotel_price function
        price_details = calculate_hotel_price(
            hotel_id=obj.hotel.id,
            room_id=obj.id,
            calculation_logic="average_price",
            checkin_date=checkin_date_obj,
            checkout_date=checkout_date_obj,
            members=int(members),
            rooms_required=int(rooms_required)
        )

        if "error" in price_details:
            return 0  # Default to 0 if there's an error in price calculation

        return price_details.get('calculated_price', 0)

    def get_breakfast_price(self, obj):
        meals_in_hotel = MealPrice.objects.filter(hotel = obj.hotel)
        for i in meals_in_hotel:
            if i.meal_type == "breakfast":
                breakfast_price = i.price
                return breakfast_price 
            
    def get_meals(self, obj):
        get_meals_type = obj.meals.all()
        get_meals_list = [{'meal_id':get_meals.id,'meal_type':get_meals.meal_type} for get_meals in get_meals_type ]
        return get_meals_list
        
    def get_lunch_price(self, obj):
        meals_in_hotel = MealPrice.objects.filter(hotel = obj.hotel)
        for i in meals_in_hotel:
            if i.meal_type == "lunch":
                lunch_price = i.price
                return lunch_price
    def get_dinner_price(self, obj):
        meals_in_hotel = MealPrice.objects.filter(hotel = obj.hotel)
        for i in meals_in_hotel:
            if i.meal_type == "dinner":
                dinner_price = i.price
                return dinner_price
            
    def get_room_images(self, obj):
        image_paths = []

        room_image_objs = RoomImage.objects.filter(roommanagement=obj)
        count = 0
        
        for image in room_image_objs:
            # print(room_image_objs,"==============",count)
            if count < len(room_image_objs):
                image_url = urljoin(settings.MEDIA_URL, str(image.image))
                image_paths.append(image_url)
                count += 1
            else:
                break

        return image_paths
    
    def get_aminity_name(self, obj):
        aminity = obj.amenities.all()
        aminity_list = []
        for ami in aminity:
            if ami.amenity_type == "Room_amenity":
                icon_url = urljoin(settings.MEDIA_URL, str(ami.icon))
                if self.language == "ar":
                    amenity_name = ami.amenity_name_arabic or ami.amenity_name
                if self.language == "en":
                    amenity_name = ami.amenity_name
                aminity_list.append((amenity_name, icon_url))
        return aminity_list
    
    def get_refund_policy(self, obj):
        refund_policy_data = {}
        room_refund_policy = RoomRefundPolicy.objects.filter(room=obj).first()

        if room_refund_policy:
            refund_policy = room_refund_policy.policy

            category_name = refund_policy.category.name_arabic if self.language == 'ar' else refund_policy.category.name
            policy_title = refund_policy.title_arabic if self.language == 'ar' else refund_policy.title

            validity_in_hours = None
            if room_refund_policy.validity:
                if isinstance(room_refund_policy.validity, timedelta):
                    validity_in_hours = room_refund_policy.validity.total_seconds() / 3600  # Convert to hours

            if validity_in_hours:
                if self.language == 'ar':
                    validity_text = f"المبالغ المستردة متاحة قبل {int(validity_in_hours)} ساعة من وقت الوصول"
                else:
                    validity_text = f"Refund available {int(validity_in_hours)} hours before check-in time"
                
                policy_title = f"{validity_text}"

            if refund_policy.is_refundable:
                cancellation_and_refund = {
                    'refund_type': category_name,
                    'title': policy_title,
                    'hour': int(validity_in_hours) if validity_in_hours is not None else room_refund_policy.validity
                }
            else:
                cancellation_and_refund = {
                    'refund_type': category_name,
                    'title': policy_title,
                }

            refund_policy_data = cancellation_and_refund

        return refund_policy_data

class RoomtypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Roomtype
        fields = '__all__'
        
        
class UserSerializer(serializers.ModelSerializer):
    firstname = serializers.SerializerMethodField()
    lastname = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    class Meta:
        model = Userdetails
        fields = ['firstname','lastname','email','contact_number']
    def get_firstname(self, obj):
        return obj.user.first_name
    def get_lastname(self, obj):
        return obj.user.last_name
    def get_email(self, obj):
        return obj.user.email
        


class RoomSerializer(serializers.Serializer):  # Change to ModelSerializer if you have a Room model
    room_id = serializers.IntegerField(required=True)
    price = serializers.FloatField(required=True)
    meal_id=serializers.IntegerField(required=True)
class RoombookingSerializer(serializers.ModelSerializer):
    room = RoomSerializer(many=True)  # Use the nested RoomSerializer
    total_amount = serializers.DecimalField(max_digits=11, decimal_places=3)
    promocode_applied = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)
    discount_percentage_applied = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)
    booking_mobilenumber = serializers.CharField(max_length=15)
    tax_and_services = serializers.DecimalField(max_digits=11, decimal_places=3, required=False, allow_null=True)
    meal_tax = serializers.DecimalField(max_digits=11, decimal_places=3, required=False, allow_null=True)
    meal_price = serializers.DecimalField(max_digits=11, decimal_places=3, required=False, allow_null=True)
    count=serializers.IntegerField(required=False, allow_null=True)
    class Meta:              
        model = Booking
        fields = [
            'room',
            'booking_fname',
            'booking_lname',
            'booking_email',
            'booking_mobilenumber',
            'is_my_self',
            'discount_price',
            'service_fee',
            'total_amount',
            'checkin_date',
            'checkout_date',
            'number_of_guests',
            'number_of_booking_rooms',
            'promocode_applied',
            'discount_percentage_applied',
            'adults',
            'children',
            'tax_and_services',
            'meal_tax',
            'meal_price',
            'count'
        ]

    
    # def validate_booking_mobilenumber(self, value):
    #     try:
    #         parsed_number = phonenumbers.parse(value, None)
    #         print(parsed_number)
    #         if not phonenumbers.is_valid_number(parsed_number):
    #             raise ValidationError({"message": "Invalid phone number."})
    #     except phonenumbers.NumberParseException:
    #         raise ValidationError({"message": "Invalid phone number format."})
        
    #     return value
class WalletPaymentSerializer(serializers.Serializer):
    total_amount = serializers.DecimalField(max_digits=11, decimal_places=3, required=False)
    payment_type = serializers.CharField(max_length=15)
    category=serializers.CharField(max_length=15)
    def validate_total_amount(self, value):
        if value <= 0 or value is None:
            raise serializers.ValidationError("The total amount must be greater than 0.")
        return value
    def validate_payment_type(self, value):
        if value is None:
            raise serializers.ValidationError("The payment type needed")
        return value
    def validate_category(self,value):
        if value not in ["Hotel", "Chalet"]:
            raise serializers.ValidationError("The category should be either Hotel or Chalet")
        return value


class ReviewBookingSerializer(serializers.ModelSerializer):
    hotel_name = serializers.SerializerMethodField()
    room_types = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = ['id','booking_fname','booking_lname','booking_email','booking_mobilenumber','checkin_date','checkout_date','number_of_guests',
                  'number_of_booking_rooms','hotel_name','room_types']
        
    def get_hotel_name(self, obj):
        return obj.hotel.name
    
    def get_room_types(self,obj):
        room_types =  obj.room.room_types.room_types
        return room_types

    
    
# class RoomDetailsSerializer(serializers.ModelSerializer):
#     room_types_name = serializers.SerializerMethodField()
#     room_images = serializers.SerializerMethodField()

#     class Meta:
#         model = Booking
#         fields = ['room_types_name', 'room_images']

#     def get_room_types_name(self, obj):
#         return obj.room.room_types.first().room_types

#     def get_room_images(self, obj):
#         room_type = obj.room.room_types.first()
#         room_image_obj = RoomImage.objects.filter(roomtype=room_type)
#         for img_obj in room_image_obj:
#             image_path = urljoin(settings.MEDIA_URL, str(img_obj.image))
#             return image_path

class GroupedHotelBookingSerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    hotel_id = serializers.SerializerMethodField()
    hotel_name = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    checkin_date = serializers.SerializerMethodField()
    checkout_date = serializers.SerializerMethodField()
    number_of_guests = serializers.SerializerMethodField()
    number_of_booking_rooms = serializers.SerializerMethodField()
    number_of_morning = serializers.SerializerMethodField()
    number_of_night = serializers.SerializerMethodField()
    booked_price = serializers.SerializerMethodField()
    room_types_name = serializers.SerializerMethodField()
    booking_id = serializers.SerializerMethodField()
    hotel_images = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()
    service_charge = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    tax_amount = serializers.SerializerMethodField()
    booking_fname = serializers.SerializerMethodField()
    booking_lname = serializers.SerializerMethodField()
    booking_email = serializers.SerializerMethodField()
    booking_mobilenumber = serializers.SerializerMethodField()
    user_rating_review = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        # Capture request context
        self.language = kwargs['context']['request'].GET.get('lang', 'en')
        super().__init__(*args, **kwargs)
        
    def get_user_rating_review(self, obj):
        if obj.status == "completed":
            recent_review = RecentReview.objects.filter(hotel=obj.hotel, booking__booking_id=obj.booking_id).first()
            if recent_review:
                data={
                    'rating':recent_review.rating,
                    'review':recent_review.review_text
                }
                return data
            return None
    def get_status(self, obj):
        return obj.status
    def get_id(self, obj):
        return obj.id
    
    def get_hotel_id(self, obj):
        return obj.hotel.id
    
    def get_hotel_name(self, obj):
        if self.language == "ar":
            return obj.hotel.name_arabic
        elif self.language == "en":
            return obj.hotel.name
        else:
            return obj.hotel.name
    
    def get_hotel_images(self, obj):
        image_paths = []
        get_hotel_img_obj = HotelImage.objects.filter(hotel = obj.hotel, is_main_image = True) 
        for img_obj in get_hotel_img_obj:
            image_path = urljoin(settings.MEDIA_URL, str(img_obj.image))
            image_paths.append(image_path)
        return image_paths
    
    def get_main_image(self, obj):
        main_image = HotelImage.objects.filter(hotel=obj.hotel, is_main_image=True).first()
        if main_image:
            return urljoin(settings.MEDIA_URL, str(main_image.image))
        return None
    
    def get_city(self, obj):
        return obj.hotel.city.name
    
    def get_checkin_date(self, obj):
        return obj.checkin_date
    
    def get_checkout_date(self, obj):
        return obj.checkout_date
    
    def get_number_of_guests(self, obj):
        return obj.number_of_guests
    
    def get_number_of_booking_rooms(self, obj):
        room_obj = obj.number_of_booking_rooms
        return room_obj
    
    def get_number_of_morning(self, obj):
        duration = (obj.checkout_date - obj.checkin_date).days
        return max(duration + 1, 0)

    def get_number_of_night(self, obj):
        duration = (obj.checkout_date - obj.checkin_date).days
        return max(duration, 0)
    def get_booked_price(self, obj):
        return obj.booked_price
    
    def get_booking_id(self, obj):
        return obj.booking_id

    def get_booking_fname(self, obj):
        return obj.booking_fname

    def get_booking_lname(self, obj):
        return obj.booking_lname

    def get_booking_email(self, obj):
        return obj.booking_email

    def get_booking_mobilenumber(self, obj):
        return obj.booking_mobilenumber
    
    def get_room_types_name(self, obj):
        object = Bookedrooms.objects.filter(booking=obj).select_related('room')  # Fetch room details in the same query

        room_types_list = []

        for objs in object:
            # Access the room's related fields directly, no need for .values()
            room_types = objs.room.room_types.room_types  # Adjust this based on actual field names

            # If you need related meals, you can prefetch them
            meal_type_list = [meal.meal_type for meal in objs.room.meals.all()]  # Access meals directly
            
            image_paths = []
        
            room_image_objs = RoomImage.objects.filter(roommanagement=objs.room)
            for img_obj in room_image_objs:
                image_path = urljoin(settings.MEDIA_URL, str(img_obj.image))
                image_paths.append(image_path)

            # Append details to the list
            booked_rooms = {
                'room_types': room_types,
                'roommanagement_id': objs.room.id,  # Access room management id directly
                'meal_price_obj': meal_type_list,
                'room_images':image_paths,
                'booked_room_price': objs.booked_room_price
            }
            
            room_types_list.append(booked_rooms)
        return room_types_list
    
    def get_service_charge(self, obj):
        return obj.service_fee
    
    def get_discount_amount(self, obj):
        return obj.discount_price
    
    def get_tax_amount(self, obj):
        return obj.hotel.country.tax
    
class ChaletbookingSerializer(serializers.ModelSerializer):
    total_amount = serializers.DecimalField(max_digits=11, decimal_places=3)
    class Meta:
        model = Booking
        fields = ['booking_fname','booking_lname','booking_email','booking_mobilenumber','is_my_self','total_amount',
                  'checkin_date','checkout_date','number_of_guests']
        
class ForgetpasswordEmailrequestSerializer(serializers.Serializer):
    email = serializers.EmailField(allow_blank=True)
    
class ResetpasswordSerializer(serializers.Serializer):
    password = serializers.CharField(allow_blank=True, max_length=20, required=False)
    confirm_password = serializers.CharField(allow_blank=True, max_length=20, required=False)
    
class GoogleLoginSerializer(SocialLoginSerializer):
    userId = serializers.CharField(required=False, allow_blank=True)
    access_token = serializers.CharField(required=True)
    
class MobileloginSerializer(serializers.Serializer):
    mobile_number = serializers.CharField(required=False, allow_blank=True)

class VerifymobileotpSerializer(serializers.Serializer):
    otp = serializers.IntegerField()
    
class RatingReviewSerializer(serializers.ModelSerializer):
    hotelid = serializers.IntegerField(required=False)
    rating = serializers.DecimalField(max_digits=3, decimal_places=1)
    booking_id = serializers.CharField(required=True)

    class Meta:
        model = RecentReview
        fields = ["hotelid", "rating", "review_text","booking_id"]

class ChaletRatingReviewSerializer(serializers.ModelSerializer):
    chaletid = serializers.IntegerField(required=True)
    rating = serializers.DecimalField(max_digits=3, decimal_places=1,required=True)
    booking_id = serializers.CharField(required=True)

    class Meta:
        model = ChaletRecentReview
        fields = ["chaletid", "rating", "review_text","booking_id"]

    def validate_rating(self, value):
        if value is None:
            raise serializers.ValidationError("Rating is required")
        return value


class FavoritesmanagementSerializer(serializers.ModelSerializer):
    hotel_id = serializers.IntegerField()
    is_liked = serializers.BooleanField()
    class Meta:
        model = Favorites
        fields = ['hotel_id','is_liked']
        
class FavoriteslistSerializer(serializers.ModelSerializer):
    hotelid = serializers.SerializerMethodField()
    hotelname = serializers.SerializerMethodField()
    avgrating = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    hotelimage = serializers.SerializerMethodField()
    price_per_night = serializers.SerializerMethodField()
    property_type = serializers.SerializerMethodField()
    class Meta:
        model = Favorites
        fields = ['hotelid','hotelname','avgrating','city','address','hotelimage','price_per_night','property_type']
        
    def __init__(self, *args, **kwargs):
        # Capture request context
        self.language = kwargs['context']['request'].GET.get('lang', 'en')
        super().__init__(*args, **kwargs)
    
    def get_property_type(self, obj):
        hotel_type_dict = {}
        if obj.hotel and obj.hotel.hotel_type and obj.hotel.hotel_type.status == "active":
            hotel_type_dict['type'] = obj.hotel.hotel_type.arabic_name if self.language == "ar" else  obj.hotel.hotel_type.name
            hotel_type_dict['icon'] = urljoin(settings.MEDIA_URL, str(obj.hotel.hotel_type.icon))
        else:
            hotel_type_dict = {"type": None, "icon": None}
        return hotel_type_dict
        
    def get_hotelid(self,obj):
        return obj.hotel.id
    
    def get_hotelname(self, obj):
        if self.language == "ar":
            return obj.hotel.name_arabic
        elif self.language == "en":
            return obj.hotel.name
        else:
            return obj.hotel.name 
    
    def get_avgrating(self, obj):
        reviews = RecentReview.objects.filter(hotel = obj.hotel).aggregate(Avg('rating', default=0)).get('rating__avg')
        return round(reviews,1)
    
    def get_city(self, obj):
        return obj.hotel.city.name
    
    def get_address(self, obj):
        return obj.hotel.address
    
    def get_hotelimage(self, obj):
        hotel_image = HotelImage.objects.filter(hotel = obj.hotel.id)
        image_path = []
        count = 0
        
        for image in hotel_image:
            if count < len(hotel_image):
                image_url = urljoin(settings.MEDIA_URL, str(image.image))
                image_path.append(image_url)
                count += 1
            else:
                break
                
        return image_path
    def get_price_per_night(self, obj):
        get_price = RoomManagement.objects.filter(hotel=obj.hotel.id, availability=True)
        min_price = get_price.aggregate(Min('price_per_night')).get('price_per_night__min')
        
        if min_price is None:
            return 0
        
        commission_slab = CommissionSlab.objects.filter(
            from_amount__lte=min_price,
            to_amount__gte=min_price,
            status='active'
        ).first()
        
        if commission_slab:
            total_price = min_price + commission_slab.commission_amount
        else:
            total_price = min_price
        
        return total_price

    
class CancelbookingSerializer(serializers.ModelSerializer):
    booking_id = serializers.CharField()
    
    class Meta:
        model = Cancelbooking
        fields = ['booking_id', 'reason']


        
class RatingfilterSerializer(serializers.Serializer):
    rating = serializers.ListField(child = serializers.DecimalField(max_digits=3, decimal_places=1))
        
    
class RecentReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecentReview
        fields = ['rating','username','review_text']

class UserProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', required=True)
    last_name = serializers.CharField(source='user.last_name', required=True)
    email = serializers.EmailField(source='user.email', required=True)
    dob = serializers.DateField(required=False, allow_null=True)
    gender = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    image = serializers.ImageField(required=False, allow_null=True)
    contact_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    dial_code=serializers.CharField(required=False, allow_blank=True, allow_null=True)
    iso_code=serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Userdetails
        fields = ['first_name', 'last_name', 'email','dob','gender','image', 'contact_number','dial_code','iso_code']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not instance.user.first_name:
            data['first_name'] = instance.user.email.split('@')[0]

        return data
    
    def validate_first_name(self, value):
        if not value:
            raise serializers.ValidationError("First name cannot be empty.")
        if not re.match(r'^[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFFA-Za-z\s]+$', value):
            raise serializers.ValidationError("First name must contain only alphabetic characters (English or Arabic).")
        return value

    def validate_last_name(self, value):
        if not value:
            raise serializers.ValidationError("Last name cannot be empty.")
        if not re.match(r'^[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFFA-Za-z\s]+$', value):
            raise serializers.ValidationError("Last name must contain only alphabetic characters (English or Arabic).")
        return value

    # def validate_email(self, value):
    #     if not value:
    #         raise serializers.ValidationError("Email cannot be empty.")
    #     if not re.match(r"[^@]+@[^@]+\.[^@]+", value):
    #         raise serializers.ValidationError("Enter a valid email address.")
    #     return value

    def validate_dob(self, value):
        if value:
            if value > date.today():
                raise serializers.ValidationError("Date of birth cannot be in the future.")
            if not isinstance(value, date):
                raise serializers.ValidationError("Date of birth must be a valid date.")
        return value

    def validate_gender(self, value):
        if value and not re.match(r'^[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFFA-Za-z]+$', value):
            raise serializers.ValidationError("Gender must contain only alphabetic characters (English or Arabic).")
        return value

    def validate_image(self, value):
        if value:
            if not value.name.lower().endswith(('.jpg', '.jpeg', '.png')):
                raise serializers.ValidationError("Image must be a .jpg, .jpeg, or .png file.")
        return value
    def validate_contact_number(self, value):
        pattern = r'^\+?[1-9]\d{3,15}$'
        if value and not re.match(pattern, value):
            raise serializers.ValidationError("Invalid  contact number.")
        return value
    
    def validate_dial_code(self, value):
        """
        Validates that the dial code starts with '+' followed by 1–4 digits.
        Examples: +91, +968, +1
        """
        pattern = r'^\+\d{1,4}$'
        if value and not re.match(pattern, value):
            raise serializers.ValidationError("Invalid dial code. Format should be like '+968'.")
        return value
    
    def validate_iso_code(self, value):
        """
        Validates that the ISO code is 2 or 3 uppercase alphabetic letters.
        Examples: OM, AE, IN, USA
        """
        pattern = r'^[A-Z]{2,4}$'
        if value and not re.match(pattern, value):
            raise serializers.ValidationError("Invalid ISO code. Should be 2 or 4 uppercase letters (e.g., 'OM').")
        return value

    
    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        for inst in instance:
            user = inst.user
            logger.info(f"{user}-----------------useruseruseruser")
            user.first_name = user_data.get('first_name', user.first_name)
            user.last_name = user_data.get('last_name', user.last_name)
            # user.email = user_data.get('email', user.email)
            user.save()
            inst.dob = validated_data.get('dob', inst.dob)
            inst.gender = validated_data.get('gender', inst.gender)
            inst.image = validated_data.get('image', inst.image)
            inst.contact_number=validated_data.get('contact_number', inst.contact_number)
            inst.dial_code=validated_data.get('dial_code', inst.dial_code)
            inst.iso_code=validated_data.get('iso_code', inst.iso_code)
            inst.save()

        return inst
    
class AmenitySerializer(serializers.ModelSerializer):
    amenity_name = serializers.SerializerMethodField()
    icon_url = serializers.SerializerMethodField()
    class Meta:
        model = Amenity
        fields = ['amenity_name', 'icon_url']

    def get_amenity_name(self, obj):
        lang = self.context.get('request', {}).GET.get('lang', 'en')
        return obj.amenity_name_arabic if lang == 'ar' else obj.amenity_name
    def get_icon_url(self, obj):
        request = self.context.get('request')
        if obj.icon and request is not None:
            return request.build_absolute_uri(obj.icon.url)
        return None

class ChaletImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChaletImage
        fields = ['image', 'is_main_image'] 
        
class ChaletModelSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    state_name = serializers.CharField(source='state.name', read_only=True)
    name = serializers.SerializerMethodField()
    city_name = serializers.SerializerMethodField()
    category_names = serializers.SerializerMethodField()
    amenities = AmenitySerializer(many=True, read_only=True)
    chalet_images = ChaletImageSerializer(many=True, read_only=True)
    main_image = serializers.SerializerMethodField()
    offers = serializers.SerializerMethodField()
    promo_codes = serializers.SerializerMethodField()
    cancellation_policy = serializers.SerializerMethodField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    price = serializers.SerializerMethodField()
    review_data = serializers.SerializerMethodField()
    post_policies = serializers.SerializerMethodField()
    is_favorite=serializers.SerializerMethodField()
    property_type = serializers.SerializerMethodField()
    about_property = serializers.SerializerMethodField()
    about_policies = serializers.SerializerMethodField()


    class Meta:
        model = Chalet
        # fields = '__all__'
        exclude = ['policies']
    def __init__(self, *args, **kwargs):
        context = kwargs.get('context', {})
        self.language = context.get('request', {}).GET.get('lang', 'en') if context.get('request') else 'en'
        print(self.language)
        super().__init__(*args, **kwargs)
        if 'total_price' in self.fields:
            self.fields.pop('total_price')
        self.fields['price'] = serializers.SerializerMethodField()

    def get_about_property(self, obj):
        if self.language == "ar":
            return obj.about_property_arabic
        elif self.language == "en":
            return obj.about_property
        return obj.about_property
    def get_latitude(self,obj) :
        if obj.latitude:
            return obj.latitude
        else:
            return None
    def get_longitude(self,obj):
        if obj.longitude:
            return obj.longitude
        else:
            return None
    def get_about_policies(self, obj):
        if self.language == "ar":
            return obj.policies_arabic
        elif self.language == "en":
            return obj.policies
        return obj.policies

    def get_property_type(self, obj):
        chalet_type_dict = {}
        if obj and obj.chalet_type and obj.chalet_type.status == "active":
            chalet_type_dict['type'] = obj.chalet_type.arabic_name if self.language == "ar" else  obj.chalet_type.name
            chalet_type_dict['icon'] = urljoin(settings.MEDIA_URL, str(obj.chalet_type.icon))
        else:
            chalet_type_dict = {"type": None, "icon": None}
        return chalet_type_dict
    def get_name(self, obj):
        if obj is None:
            return None
        
        try:
            if self.language == "ar":
                return obj.name_arabic
            elif self.language == "en":
                return obj.name
            return obj.name
        except AttributeError as e:
            logger.info(f"Error retrieving name: {e}")
            return "Unnamed Chalet"
    def get_city_name(self, obj):
        if obj is None:
            return None
        try:
            if self.language == "ar":
                return obj.city.arabic_name
            elif self.language == "en":
                return obj.city.name
        except AttributeError as e:
            logger.info(f"Error retrieving name: {e}")
            return "Unnamed Chalet"

    def get_category_names(self, obj):
        if obj is None:
            return []
        try:
            return [category.category for category in obj.category.all()]
        except AttributeError as e:
            logger.info(f"Error retrieving categories: {e}")
            return []

    def get_main_image(self, obj):
        if obj is None:
            return None
        try:
            main_image = obj.chalet_images.filter(is_main_image=True).first()
            if main_image:
                request = self.context.get('request')
                if request is not None:
                    return request.build_absolute_uri(main_image.image.url)
                return main_image.image.url
            return None
        except AttributeError as e:
            logger.info(f"Error retrieving main image: {e}")
            return None

    def get_offers(self, obj):
        if obj is None:
            offers = []
        try:
            current_date = timezone.now().date()
            promotions = Promotion.objects.filter(
                Q(chalet=obj) | Q(multiple_chalets__in=[obj]),
                promo_code__isnull=True,
                start_date__lte=current_date,
                end_date__gte=current_date,
                status="active"
            )
            return [
                {
                    'promo_id': promo.id,
                    'title': promo.title,
                    'description': promo.description,
                    'promotion_type': promo.promotion_type,
                    'discount_percentage': promo.discount_percentage,
                    'start_date': promo.start_date,
                    'end_date': promo.end_date,
                    'discount_value': promo.discount_value,
                    'status': promo.status
                }
                for promo in promotions
            ]
        except DatabaseError as e:
            logger.info(f"Database error while fetching offers: {e}")
        except AttributeError as e:
            logger.info(f"Error retrieving offers: {e}")
        return offers

    def get_promo_codes(self, obj):
        promo_codes = [] 
        if obj is None:
            return promo_codes
        
        try:
            current_date = timezone.now().date()
            promo_objects = Promotion.objects.filter(
                Q(chalet=obj) | Q(multiple_chalets__in=[obj]),
                promo_code__isnull=False,
                start_date__lte=current_date,
                end_date__gte=current_date,
                status="active"
            )
            promo_codes = [
                {
                    'promo_id': code.id,
                    'title': code.title,
                    'description': code.description,
                    'discount_percentage': code.discount_percentage,
                    'discount_value': code.discount_value,
                    'start_date': code.start_date,
                    'end_date': code.end_date,
                    'code': code.promo_code,
                    'status': code.status
                }
                for code in promo_objects
            ]
        except DatabaseError as e:
            logger.info(f"Database error while fetching promo codes: {e}")
        except AttributeError as e:
            logger.info(f"Error retrieving promo codes: {e}")
        
        return promo_codes
    def get_is_favorite(self,obj):
        user = self.context['request'].user
        if user.id is not None:
            logger.info(f"user:{user}")
            userdetail=Userdetails.objects.filter(user=user.id).first()
            logger.info(f"userdetail:{userdetail}")
            get_favorites =ChaletFavorites.objects.filter(chalet=obj.id,user=userdetail.id,is_liked=True).exists()
            return  get_favorites
        else:
            return None
    
    def get_cancellation_policy(self, obj):
        if obj is None:
            return []
        try:
            cancellation_categories = obj.post_policies.filter(name__icontains="cancel")
            if cancellation_categories.exists():
                logger.info(f"Cancellation categories found for Chalet: {obj.name} (ID: {obj.id})")
                cancellation_policies = []

                for category in cancellation_categories:
                    policies = category.policy_names.filter(chalet=obj)
                    cancellation_policies.extend([policy.title for policy in policies])

                return cancellation_policies

            else:
                logger.warning(f"No cancellation category found for Chalet: {obj.name} (ID: {obj.id})")

        except Exception as e:
            logger.error(
                f"Unexpected error occurred while fetching cancellation policy for Chalet: {obj.name} (ID: {obj.id}), Exception: {e}",
                exc_info=True,
            )

        return []  # Return an empty list if no policies are found or an error occurs


    def get_price(self, obj):
        try:
            request = self.context.get('request')  # Get the request context
            checkin_date = request.query_params.get('checkin_date') if request else None
            checkout_date = request.query_params.get('checkout_date') if request else None

            if checkin_date and checkout_date:
                # Parse dates
                try:
                    checkin_date_obj = datetime.strptime(checkin_date, '%Y-%m-%d').date()
                    checkout_date_obj = datetime.strptime(checkout_date, '%Y-%m-%d').date()

                    if checkin_date_obj >= checkout_date_obj:
                        logger.error("Checkin date (%s) is not before checkout date (%s).", checkin_date_obj, checkout_date_obj)
                        return None  # Or return some default value
                    # Calculate average price using the provided function
                    return calculate_hotel_price(
                        chalet_id=obj.id,
                        property='chalet',
                        checkin_date=checkin_date_obj,
                        checkout_date=checkout_date_obj
                    ).get("calculated_price")
                except ValueError as e:
                    logger.error(f"Invalid date format provided for price calculation: {e}")
                    return obj.total_price  # Fallback to default price
            else:
                logger.info("Checkin or checkout date not provided. Using default logic for price.")
                # Use existing logic to get discounted price
                discounted_price = get_discounted_price_for_property(obj.id, "chalet")
                if discounted_price:
                    return discounted_price
        except Exception as e:
            logger.error(f"Unexpected error in get_price: {e}", exc_info=True)
        return obj.total_price  # Fallback to total_price if all else fails

    def get_review_data(self, obj):
        """
        Fetch review and rating statistics for the chalet.
        """
        reviews = ChaletRecentReview.objects.filter(chalet=obj)
        total_reviews = reviews.count()
        total_ratings = reviews.exclude(rating__isnull=True).count()
        avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0.0

        # Calculate star-based counts
        star_counts = {
            f'numbers_of_total_{int(star)}_star': reviews.filter(rating=star).count()
            for star in range(1, 6)
        }

        # Calculate the average rating for the last 6 months
        six_months_ago = timezone.now() - timedelta(days=180)
        avg_rating_last_6_months = (
            reviews.filter(date__gte=six_months_ago).aggregate(avg=Avg('rating'))['avg'] or 0.0
        )

        review_list = reviews.values('username', 'date', 'review_text', 'rating')

        return {
            "number_of_reviews": total_reviews,
            "number_of_ratings": total_ratings,
            "reviews": list(review_list),
            "avg_rating": round(avg_rating, 1),
            **star_counts,
            "avg_rating_last_6_months": round(avg_rating_last_6_months, 1),
        }

    def get_post_policies(self, obj):
        try:
            policy_categories = obj.post_policies.all()
            policy_dict = defaultdict(list)
            for category in policy_categories:
                policy_names = category.policy_names.filter(chalet=obj)
                for policy_name in policy_names:
                    policy_dict[category.name].append(policy_name.title)
            
            return policy_dict
        except AttributeError as e:
            logger.error(f"Error fetching chalet policies: {e}")
            return {}

class ChaletBookingSerializer(serializers.ModelSerializer):
    promocode_applied = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    discount_percentage_applied = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    class Meta:
        model = ChaletBooking
        fields = '__all__'
        read_only_fields=['booking_id'] 
    def validate(self, data):
        members = data.get('number_of_guests')
        adults = data.get('adults')
        children = data.get('children', 0)  
        if members is None or members <= 0:
            raise serializers.ValidationError("The number of guests must be greater than zero.")
        if adults is None or adults <= 0:
            raise serializers.ValidationError("The number of adults must be greater than zero.")
        if children < 0:
            raise serializers.ValidationError("The number of children cannot be negative.")
        if members != adults + children:
            raise serializers.ValidationError(
                "The total number of guests must equal the sum of adults and children."
            )
        return data
    
    def create(self, validated_data):
        if 'booking_date' not in validated_data:
            validated_data['booking_date'] = date.today()
        return super().create(validated_data)

class ChaletFavoritesmanagementSerializer(serializers.ModelSerializer):
    chalet_id=serializers.IntegerField()
    class Meta:
        model = ChaletFavorites
        fields = ['chalet_id', 'is_liked']

class ChaletFavoriteslistSerializer(serializers.ModelSerializer):
    chalet_id = serializers.SerializerMethodField()
    chalet_name = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    chalet_images = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()  # Added new field for total_price
    property_type = serializers.SerializerMethodField()

    class Meta:
        model = ChaletFavorites
        fields = ['chalet_id', 'chalet_name', 'avg_rating', 'city', 'address', 'chalet_images', 'total_price','property_type']  # Included total_price in fields
        
    def __init__(self, *args, **kwargs):
        # Capture request context
        self.language = kwargs['context']['request'].GET.get('lang', 'en')
        super().__init__(*args, **kwargs)

    def get_property_type(self, obj):
        chalet_type_dict = {}

        if obj.chalet and obj.chalet.chalet_type and obj.chalet.chalet_type.status == "status":
            chalet_type_dict['type'] = obj.chalet.chalet_type.arabic_name if self.language == "ar" else obj.chalet.chalet_type.name
            
            chalet_type_dict['icon'] = urljoin(settings.MEDIA_URL, str(obj.chalet.chalet_type.icon))
        else:
            chalet_type_dict = {"type": None, "icon": None}

        return chalet_type_dict
    
    def get_chalet_id(self, obj):
        return obj.chalet.id

    def get_chalet_name(self, obj):
        if self.language == "ar":
            return obj.chalet.name_arabic
        elif self.language == "en":
            return obj.chalet.name
        else:
            return obj.chalet.name


    def get_avg_rating(self, obj):
        reviews = ChaletRecentReview.objects.filter(chalet=obj.chalet).aggregate(Avg('rating', default=0)).get('rating__avg')
        return reviews

    def get_city(self, obj):
        return obj.chalet.city.name

    def get_address(self, obj):
        return obj.chalet.address

    def get_chalet_images(self, obj):
        chalet_images = ChaletImage.objects.filter(chalet=obj.chalet.id)
        image_path = []
        count = 0

        for image in chalet_images:
            if count < len(chalet_images):
                image_url = urljoin(settings.MEDIA_URL, str(image.image))
                image_path.append(image_url)
                count += 1
            else:
                break

        return image_path

    def get_total_price(self, obj):
        # Assuming 'total_price' is a field in the Chalet model
        base_price = obj.chalet.current_price  
        
        # Calculate commission
        commission_slab = CommissionSlab.objects.filter(
            from_amount__lte=base_price,
            to_amount__gte=base_price,
            status='active'
        ).first()

        if commission_slab:
            total_price_with_commission = base_price + commission_slab.commission_amount
        else:
            total_price_with_commission = base_price  # No commission applied if no slab is found

        return total_price_with_commission

class GroupedChaletBookingSerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    chalet_id = serializers.SerializerMethodField()
    chalet_name = serializers.SerializerMethodField()
    chalet_images = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    checkin_date = serializers.SerializerMethodField()
    checkout_date = serializers.SerializerMethodField()
    number_of_guests = serializers.SerializerMethodField()
    booked_price = serializers.SerializerMethodField()
    booking_id = serializers.SerializerMethodField()
    service_charge = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    tax_amount = serializers.SerializerMethodField()
    booking_fname = serializers.SerializerMethodField()
    booking_lname = serializers.SerializerMethodField()
    booking_email = serializers.SerializerMethodField()
    booking_mobilenumber = serializers.SerializerMethodField()
    user_rating_review = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    
    def __init__(self, *args, **kwargs):
        # Capture request context
        self.language = kwargs['context']['request'].GET.get('lang', 'en')
        super().__init__(*args, **kwargs)
    def get_user_rating_review(self, obj):
            if obj.status == "completed":
                recent_review = ChaletRecentReview.objects.filter(chalet=obj.chalet, chalet_booking__booking_id=obj.booking_id).first()
                if recent_review:
                    data={
                        'rating':recent_review.rating,
                        'review':recent_review.review_text
                    }
                    return data
                return None
    def get_chalet_id(self, obj):
        return obj.chalet.id

    def get_id(self, obj):
        return obj.id

    def get_status(self, obj):
        return obj.status
    
    def get_chalet_name(self, obj):
        if self.language == "ar":
            return obj.chalet.name_arabic
        elif self.language == "en":
            return obj.chalet.name
        else:
            return obj.chalet.name

    def get_chalet_images(self, obj):
        image_paths = []
        chalet_images = ChaletImage.objects.filter(chalet=obj.chalet)
        for img in chalet_images:
            image_paths.append(urljoin(settings.MEDIA_URL, str(img.image)))
        return image_paths

    def get_city(self, obj):
        return obj.chalet.city.name

    def get_checkin_date(self, obj):
        return obj.checkin_date

    def get_checkout_date(self, obj):
        return obj.checkout_date

    def get_number_of_guests(self, obj):
        return obj.number_of_guests

    def get_booked_price(self, obj):
        return obj.booked_price

    def get_booking_id(self, obj):
        return obj.booking_id

    def get_service_charge(self, obj):
        return obj.service_fee

    def get_discount_amount(self, obj):
        return obj.discount_price

    def get_tax_amount(self, obj):
        return obj.chalet.country.tax

    def get_booking_fname(self, obj):
        return obj.booking_fname

    def get_booking_lname(self, obj):
        return obj.booking_lname

    def get_booking_email(self, obj):
        return obj.booking_email

    def get_booking_mobilenumber(self, obj):
        return obj.booking_mobilenumber

class ChaletBookingCancelSerializer(serializers.ModelSerializer):
    booking_id=serializers.CharField()
    class Meta:
        model = CancelChaletBooking
        fields = ['booking_id','reason']
class Refund_Serializer(serializers.Serializer):
    category=serializers.CharField(max_length=15)
    def validate_category(self,value):
        if value not in ["Hotel", "Chalet"]:
            raise serializers.ValidationError("The category should be either Hotel or Chalet")
        return value




class ChaletSearchSerializer(serializers.Serializer):
    latitude = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)
    city_name = serializers.CharField(required=False, allow_blank=True)
    chalet_name = serializers.CharField(required=False, allow_blank=True)
    checkin_date = serializers.DateField(required=False)
    checkout_date = serializers.DateField(required=False)
    rooms = serializers.IntegerField(required=False)  # Number of rooms
    members = serializers.IntegerField(required=False)  # Number of adults
    rating = serializers.IntegerField(required=False)  # Rating filter (5, 4, 3, etc.)
    amenities = serializers.ListField(
        child=serializers.CharField(), required=False
    )  # List of amenities
    sorted = serializers.CharField(required=True)  # Sorting key (rating, price, etc.)
    filter = serializers.DictField(
        child=serializers.ListField(
            child=serializers.CharField()
        ),
        required=False
    )

class PromoCodeSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    chalet_name = serializers.CharField(source='chalet.name', read_only=True)

    class Meta:
        model = Promotion
        fields = ['promo_code','description', 'hotel_name', 'chalet_name']

class PromotionSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    chalet_name = serializers.CharField(source='chalet.name', read_only=True)

    class Meta:
        model = Promotion
        fields = [
            'title',
            'description',
            'promotion_type',
            'discount_percentage',
            'free_night_offer',
            'start_date',
            'end_date',
            'promo_code',
            'hotel_name',
            'chalet_name'
        ]


class DailyDealSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    data_type = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()
    remaining_uses = serializers.SerializerMethodField()
    minimum_spend = serializers.SerializerMethodField()
    promotion_id = serializers.SerializerMethodField()
    property_id = serializers.SerializerMethodField()
    

    class Meta:
        model = Promotion
        fields = [
            'data_type', 'title', 'description', 'discount_percentage', 'image', 'name', 'promotion_id', 'city', 'price',
            'discounted_price', 'remaining_uses', 'minimum_spend', 'property_id'
        ]

    def __init__(self, *args, **kwargs):
        # Capture request context
        self.language = kwargs['context']['request'].GET.get('lang', 'en')
        super().__init__(*args, **kwargs)
        
        
    def get_property_id(self, obj):
        print(obj,"==============")
        if obj.hotel:
            return obj.hotel.id
        elif obj.chalet:
            return obj.chalet.id
        return None
    
    def get_promotion_id(self, obj):
        return obj.id

    def get_image(self, obj):
        if obj.hotel:
            return self.get_hotel_image(obj)
        elif obj.chalet:
            return self.get_chalet_image(obj)
        return None

    def get_chalet_image(self, obj):
        chalet_images = ChaletImage.objects.filter(chalet=obj.chalet, is_main_image = True).first()
        image_path = urljoin(settings.MEDIA_URL, str(chalet_images.image))
        return image_path

    def get_hotel_image(self, obj):
        get_hotel_img_obj = HotelImage.objects.filter(hotel = obj.hotel, is_main_image = True).first()
        image_path = urljoin(settings.MEDIA_URL, str(get_hotel_img_obj.image))
        return image_path

    def get_city(self, obj):
        if obj.hotel:
            return obj.hotel.city.name
        elif obj.chalet:
            return obj.chalet.city.name
        return None

    def get_name(self, obj):
        if self.language == "ar":
            if obj.hotel:
                return obj.hotel.name_arabic
            elif obj.chalet:
                return obj.chalet.name_arabic
            return None
        elif self.language == "en":
            if obj.hotel:
                return obj.hotel.name
            elif obj.chalet:
                return obj.chalet.name
            return None
        else:
            if obj.hotel:
                return obj.hotel.name
            elif obj.chalet:
                return obj.chalet.name
            return None

    def get_data_type(self, obj):
        if obj.hotel:
            return "hotel"
        elif obj.chalet:
            return "chalet"
        return "unknown"

    def get_price(self, obj):
       
        # Check if the object has a hotel
        if obj.hotel:
            rooms = obj.hotel.room_managements.all()  # Get all associated rooms
            today = datetime.now().weekday()  # Determine the current day
            lowest_price = None

            for room in rooms:
                # Determine the price based on the day and weekend price status
                if today in (3, 4) and hasattr(room, 'weekend_price') and room.weekend_price.is_active():
                    price = room.weekend_price.weekend_price
                else:
                    price = room.price_per_night

                # Update the lowest price
                if lowest_price is None or price < lowest_price:
                    lowest_price = price

            return lowest_price if lowest_price is not None else 0

        # Check if the object has a chalet
        elif obj.chalet:
            return obj.chalet.current_price

        # Default return value
        return None


    def get_discounted_price(self, obj):
        original_price = self.get_price(obj)
        if obj.discount_percentage and original_price:
            discount_amount = (obj.discount_percentage / 100) * original_price
            return original_price - discount_amount
        return original_price

    def get_remaining_uses(self, obj):
        return obj.uses_left if obj.uses_left is not None else obj.max_uses

    def get_minimum_spend(self, obj):
        return obj.minimum_spend

    def to_representation(self, instance):
        print(instance,"==============")
        representation = super().to_representation(instance)

        # Conditionally include or remove fields
        if not instance.hotel:
            representation.pop('hotel_name', None)
        if not instance.chalet:
            representation.pop('chalet_name', None)

        return representation
   
    
class RoomDetailSerializer(serializers.Serializer):
    room_id = serializers.IntegerField()
    meal = serializers.CharField(max_length=100, required=False, allow_blank=True)
    meal_type_id = serializers.IntegerField()

class CheckpromoSerializer(serializers.Serializer):
    rooms = RoomDetailSerializer(many=True, required=False)
    chalet = serializers.IntegerField(required=False)
    promocode = serializers.CharField(max_length=100)
    checkin_date = serializers.DateField(required=False, allow_null=True)
    checkout_date = serializers.DateField(required=False, allow_null=True)



class ComparisonSerializer(serializers.ModelSerializer):
    type = serializers.CharField(write_only=True)
    item_id = serializers.IntegerField(write_only=True)
    class Meta:
        model = Comparison
        fields = ['user', 'type', 'item_id', 'created_by', 'modified_by', 'created_date', 'modified_date', 'status']
        read_only_fields = ['user', 'created_by', 'modified_by', 'created_date', 'modified_date', 'status']
    def create(self, validated_data):
        return super().create(validated_data)



class CompareSerializer(serializers.ModelSerializer):
    hotel_details=serializers.SerializerMethodField()
    chalet_details=serializers.SerializerMethodField()

    class Meta:
        model = Comparison
        fields = ['hotel_details','chalet_details']
        #read_only_fields = ['user', 'rating', 'main_image', 'rate', 'locality', 'created_by', 'modified_by', 'created_date', 'modified_date', 'status']
        
    def __init__(self, *args, **kwargs):
        # Capture request context
        self.language = kwargs['context']['request'].GET.get('lang', 'en')
        super().__init__(*args, **kwargs)
    
    def get_hotel_details(self, obj):
        if obj.type == 'hotel' and obj.hotel:
            hotel_recent=RecentReview.objects.filter(hotel=obj.hotel.id)
            review_rating=[i.rating for i in hotel_recent]
            if review_rating:
                avg=sum(review_rating)/len(review_rating)
            else:
                avg=0
            room_mng=RoomManagement.objects.filter(hotel=obj.hotel.id)
            price_htl = [i.price_per_night for i in room_mng if i.price_per_night is not None]
            if price_htl:
                price_main = min(price_htl)
            else:
                price_main = 0  # or None, or some default/fallback value
            room_type = [room.room_types.room_types for room in  room_mng]
            hotel_images = HotelImage.objects.filter(hotel=obj.hotel.id, is_main_image=True) 
            hotel_type_dict = {}
            if obj.hotel and obj.hotel.hotel_type and obj.hotel.hotel_type.status == "active":
                hotel_type_dict['type'] = obj.hotel.hotel_type.arabic_name if self.language == "ar" else  obj.hotel.hotel_type.name
                hotel_type_dict['icon'] = urljoin(settings.MEDIA_URL, str(obj.hotel.hotel_type.icon))
            else:
                hotel_type_dict = {"type": None, "icon": None}
            if hotel_images.exists():
                print(room_type,"=============")
                for image in hotel_images:
                    image_url = urljoin(settings.MEDIA_URL, str(image.image))          
                return {
                    'hotel_id':obj.hotel.id,
                    'name': obj.hotel.name if self.language == "en" else obj.hotel.name_arabic,
                    'locality': obj.hotel.city.name,
                    'rating': avg,
                    'price': price_main,
                    'room_type':room_type,
                    'main_image': image_url,
                    'property_type':hotel_type_dict
                }
            else:
                return {
                    'hotel_id':obj.hotel.id,
                    'name': obj.hotel.name if self.language == "en" else obj.hotel.name_arabic,
                    'locality': obj.hotel.city.name,
                    'rating': avg,
                    'price': price_main,
                    'room_type':room_type,
                    'main_image': None,
                    'property_type':hotel_type_dict
                }
        else:
            None
        

    def get_chalet_details(self, obj):
        print('chalet')
        if obj.type == 'chalet' and obj.chalet:
            chalet_recent = ChaletRecentReview.objects.filter(chalet=obj.chalet.id)
            
            review_rating = [i.rating for i in chalet_recent]
            avg = sum(review_rating) / len(review_rating) if review_rating else 0
            
            chalet_images = ChaletImage.objects.filter(chalet=obj.chalet.id, is_main_image=True) 
            logger.info(f"\n\nchalet_images: {chalet_images} ------> inside get comparisoni serialiser\n\n")
            chalet_type_dict = {}
            if obj.chalet and obj.chalet.chalet_type and obj.chalet.chalet_type.status == "active":
                chalet_type_dict['type'] = obj.chalet.chalet_type.arabic_name if self.language == "ar" else  obj.chalet.chalet_type.name
                chalet_type_dict['icon'] = urljoin(settings.MEDIA_URL, str(obj.chalet.chalet_type.icon))
            else:
                chalet_type_dict = {"type": None, "icon": None}
            if chalet_images.exists():
                for image in chalet_images:
                    image_url = urljoin(settings.MEDIA_URL, str(image.image))  
                    logger.info(f"\n\nimage_url: {image_url} ------> inside get comparisoni serialiser\n\n")
                logger.info(f"\n\nimage_url: {image_url} ------> inside get comparisoni serialiser -----> outside the loop\n\n")
                return {
                    'chalets_id': obj.chalet.id,
                    'name': obj.chalet.name if self.language == "en" else obj.chalet.name_arabic,
                    'locality': obj.chalet.city.name,
                    'rating': avg,
                    'price': obj.chalet.total_price,
                    'main_image': image_url,
                    'property_type':chalet_type_dict
                }
            else:
                return {
                    'chalets_id': obj.chalet.id,
                    'name': obj.chalet.name if self.language == "en" else obj.chalet.name_arabic,
                    'locality': obj.chalet.city.name,
                    'rating': avg,
                    'price': obj.chalet.total_price,
                    'main_image': None,
                    'property_type':chalet_type_dict
                }
        return None

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('hotel_details', None)
        representation.pop('chalet_details', None) 
    
        if instance.type == 'hotel' and instance.hotel:
            hotel_details = self.get_hotel_details(instance)
            if hotel_details:
                representation['hotel_id'] = hotel_details['hotel_id']
                representation['name'] = hotel_details['name']
                representation['location'] = hotel_details['locality']
                representation['price'] = hotel_details['price']
                representation['room_type'] = hotel_details['room_type']
                representation['rating'] = hotel_details['rating']
                representation['main_image'] = hotel_details['main_image']
                representation['property_type'] = hotel_details['property_type']
            
        elif instance.type == 'chalet' and instance.chalet:
            print(instance.type)
            chalet_details = self.get_chalet_details(instance)
            if chalet_details:
                representation['chalets_id'] = chalet_details['chalets_id']
                representation['name'] = chalet_details['name']
                representation['location'] = chalet_details['locality']
                representation['price'] = chalet_details['price']
                representation['rating'] = chalet_details['rating']
                representation['main_image'] = chalet_details['main_image']
                representation['property_type'] = chalet_details['property_type']
        
        return representation
class Featuredserializer(serializers.ModelSerializer):
    hotel_details = serializers.SerializerMethodField()
    chalet_details = serializers.SerializerMethodField()

    class Meta:
        model = Featured
        fields = ['hotel_details', 'chalet_details']

    def __init__(self, *args, **kwargs):
        # Capture request context
        self.language = kwargs['context']['request'].GET.get('lang', 'en')
        super().__init__(*args, **kwargs)

    def get_hotel_details(self, obj):
        if obj.type == 'hotel' and obj.hotel and obj.status == 'active':
            try:
                logger.info(f"Fetching hotel details for hotel ID: {obj.hotel.id}")
                featured_in = Featured.objects.get(hotel=obj.hotel.id)
                if featured_in:
                    valid_from = featured_in.valid_from
                    valid_to = featured_in.valid_to
                    if (valid_from and valid_from > date.today()) or (valid_to and valid_to < date.today()):
                        logger.info(f"Hotel {obj.hotel.id} not valid in the current date range.")
                        return None

                # Calculate average rating
                avg = 0
                try:
                    hotel_recent = RecentReview.objects.filter(hotel=obj.hotel.id)
                    review_rating = [i.rating for i in hotel_recent]
                    avg = sum(review_rating) / len(review_rating) if review_rating else 0
                except Exception as e:
                    logger.warning(f"Error calculating hotel rating for hotel {obj.hotel.id}: {e}")

                # Calculate price and commission
                total_price = 0
                try:
                    room_mng = RoomManagement.objects.filter(hotel=obj.hotel.id)
                    price_htl = [i.price_per_night for i in room_mng if i.price_per_night is not None]
                    if price_htl:
                        price_main = min(price_htl)
                        commission_slab = CommissionSlab.objects.filter(
                            from_amount__lte=price_main,
                            to_amount__gte=price_main,
                            status='active'
                        ).first()
                        if commission_slab:
                            total_price = float(price_main) + float(commission_slab.commission_amount)
                        else:
                            total_price = float(price_main)
                    else:
                        total_price=0
                except Exception as e:
                    logger.warning(f"Error calculating price for hotel {obj.hotel.id}: {e}")

                # Get hotel image
                img_url = None
                try:
                    hotel_images = HotelImage.objects.filter(hotel=obj.hotel.id, is_main_image=True)
                    if hotel_images:
                        img_url = hotel_images.first().image.url
                except Exception as e:
                    logger.warning(f"Error fetching hotel image for hotel {obj.hotel.id}: {e}")

                # Check for active offers
                offers = None
                try:
                    offers = Promotion.objects.filter(
                        Q(hotel=obj.hotel.id) | Q(multiple_hotels__in=[obj.hotel.id]),
                        category="common",
                        discount_percentage__isnull=False,
                        status="active",
                        start_date__lte=date.today(),
                        end_date__gte=date.today()
                    ).order_by("-discount_percentage").first()
                except Exception as e:
                    logger.warning(f"Error fetching offers for hotel {obj.hotel.id}: {e}")

                discounted_price = None
                if offers and total_price:
                    try:
                        discount = (float(offers.discount_percentage) / 100) * float(total_price)
                        discounted_price = total_price - discount
                    except Exception as e:
                        logger.warning(f"Error calculating discount for hotel {obj.hotel.id}: {e}")

                return {
                    'id': obj.hotel.id,
                    'name': obj.hotel.name if self.language == "en" else obj.hotel.name_arabic,
                    'locality': obj.hotel.city.name,
                    'rating': avg,
                    'price': total_price,
                    'main_image': img_url,
                    'featured_valid_from': valid_from,
                    'featured_valid_to': valid_to,
                    'type': 'hotel',
                    'status': 'active',
                    'offers': {
                        'id': offers.id,
                        'title': offers.title,
                        'discount_percentage': offers.discount_percentage,
                        'discount_price': discounted_price
                    } if offers else None
                }
            except Exception as e:
                logger.error(f"Error fetching hotel details for hotel ID {obj.hotel.id}: {e}")
                raise serializers.ValidationError(f"Error fetching hotel details: {e}")
        return None

    def get_chalet_details(self, obj):
        if obj.type == 'chalet' and obj.chalet and obj.status == 'active':
            try:
                logger.info(f"Fetching chalet details for chalet ID: {obj.chalet.id}")
                featured_in = Featured.objects.get(chalet=obj.chalet.id)
                if featured_in:
                    valid_from = featured_in.valid_from
                    valid_to = featured_in.valid_to
                    if (valid_from and valid_from > date.today()) or (valid_to and valid_to < date.today()):
                        logger.info(f"Chalet {obj.chalet.id} not valid in the current date range.")
                        return None

                # Calculate average rating
                avg = 0
                try:
                    chalet_recent = ChaletRecentReview.objects.filter(chalet=obj.chalet.id)
                    review_rating = [i.rating for i in chalet_recent]
                    avg = sum(review_rating) / len(review_rating) if review_rating else 0
                except Exception as e:
                    logger.warning(f"Error calculating chalet rating for chalet {obj.chalet.id}: {e}")

                # Get chalet image
                img_url = None
                try:
                    chalet_images = ChaletImage.objects.filter(chalet=obj.chalet.id, is_main_image=True)
                    if chalet_images.exists():
                        img_url = chalet_images.first().image.url
                except Exception as e:
                    logger.warning(f"Error fetching chalet image for chalet {obj.chalet.id}: {e}")

                # Calculate price based on session data
                total_price = 0
                request = self.context.get('request')
                if request:
                    try:
                        # Parse session data
                        checkin_date = datetime.strptime(request.session.get('checkin_date'), "%Y-%m-%d").date()
                        checkout_date = datetime.strptime(request.session.get('checkout_date'), "%Y-%m-%d").date()
                        members = request.session.get('members')
                        rooms_required = request.session['rooms']
                        logger.info(f"Session data -> Checkin: {checkin_date}, Checkout: {checkout_date}, Members: {members}, Rooms Required: {rooms_required}")

                        # Call the price calculation function for chalet
                        price_result = calculate_hotel_price(
                            chalet_id=obj.chalet.id,
                            calculation_logic="average_price",
                            checkin_date=checkin_date,
                            checkout_date=checkout_date,
                            members=members,
                            rooms_required=rooms_required,
                            property="chalet"
                        )

                        if "error" in price_result:
                            logger.error(f"Price calculation error: {price_result['error']}")
                            return None

                        calculated_price = price_result.get("calculated_price")
                        logger.info(f"Calculated average price for chalet {obj.chalet.id}: {calculated_price}")
                        total_price = calculated_price

                    except Exception as e:
                        logger.error(f"Error in price calculation for chalet {obj.chalet.id}: {str(e)}")
                        return None

                # Check for active offers
                offers = None
                try:
                    offers = Promotion.objects.filter(
                        Q(chalet=obj.chalet.id) | Q(multiple_chalets__in=[obj.chalet.id]),
                        category="common",
                        discount_percentage__isnull=False,
                        status="active",
                        start_date__lte=date.today(),
                        end_date__gte=date.today()
                    ).order_by("-discount_percentage").first()
                except Exception as e:
                    logger.warning(f"Error fetching offers for chalet {obj.chalet.id}: {e}")

                discounted_price = None
                if offers and total_price:
                    try:
                        discount = (Decimal(offers.discount_percentage) / Decimal(100)) * total_price
                        discounted_price = total_price - discount
                    except Exception as e:
                        logger.warning(f"Error calculating discount for chalet {obj.chalet.id}: {e}")

                return {
                    'id': obj.chalet.id,
                    'name': obj.chalet.name if self.language == "en" else obj.chalet.name_arabic,
                    'locality': obj.chalet.city.name,
                    'rating': avg,
                    'price': total_price,
                    'main_image': img_url,
                    'featured_valid_from': valid_from,
                    'featured_valid_to': valid_to,
                    'type': 'chalet',
                    'status': 'active',
                    'offers': {
                        'id': offers.id,
                        'title': offers.title,
                        'discount_percentage': offers.discount_percentage,
                        'discount_price': discounted_price
                    } if offers else None
                }
            except Exception as e:
                logger.error(f"Error fetching chalet details for chalet ID {obj.chalet.id}: {e}")
                raise serializers.ValidationError(f"Error fetching chalet details: {e}")
        return None
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('hotel_details', None)
        representation.pop('chalet_details', None)

        if instance.type == 'hotel' and instance.hotel:
            hotel_details = self.get_hotel_details(instance)
            if hotel_details:
                representation.update(hotel_details)

        elif instance.type == 'chalet' and instance.chalet:
            chalet_details = self.get_chalet_details(instance)
            if chalet_details:
                representation.update(chalet_details)

        return representation
    
    
    
class RoomDetailCalculationSerializer(serializers.Serializer):
    room_id = serializers.IntegerField()
    meal = serializers.CharField(max_length=100, required=False, allow_blank=True)
    meal_type_id = serializers.IntegerField()

class BookingCalculationSerializer(serializers.Serializer):
    rooms = RoomDetailCalculationSerializer(many=True, required=False)
    chalet = serializers.IntegerField(required=False)
    promotion_id = serializers.IntegerField(required=False, allow_null=True)
    promocode = serializers.CharField(max_length=100, required=False, allow_blank=True)
    checkin_date = serializers.DateField(required=False, allow_null=True)
    checkout_date = serializers.DateField(required=False, allow_null=True)
    
class NotificationSerialiser(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    property_name = serializers.SerializerMethodField()
    class Meta:
        model = Notification
        fields = ["id","user","notification_type","message","message_arabic","created_at","is_read","source","property_name"]

    
    def get_user(self, obj):
        return obj.recipient.first_name
    
    def get_property_name(self, obj):
        if obj.source == "hotel":
            return obj.related_booking.hotel.name
        elif obj.source == "chalet":
            return obj.chalet_booking.chalet.name
        
class BookingDetailModelSerializer(serializers.ModelSerializer):
    property_details = serializers.SerializerMethodField()
    guest_details = serializers.SerializerMethodField()
    room_type = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    availability_waiting_time = serializers.SerializerMethodField()
    payment_expiry_time = serializers.SerializerMethodField()
    payment_waiting_time = serializers.SerializerMethodField()
    number_of_morning = serializers.SerializerMethodField()
    number_of_night = serializers.SerializerMethodField()
    user_rating_review = serializers.SerializerMethodField()
    checkin_date = serializers.SerializerMethodField()
    checkout_date = serializers.SerializerMethodField()
    tax_amount = serializers.SerializerMethodField()
    meal_tax = serializers.SerializerMethodField()
    meal_price = serializers.SerializerMethodField()
    tax_and_services = serializers.SerializerMethodField()
    class Meta:
        model = Booking
        fields = ['id','status','type','property_details','guest_details','checkin_date','checkout_date','check_in_time','check_out_time','number_of_guests','number_of_booking_rooms',
                  'booking_id','discount_price','service_fee','booked_price','room_type','availability_waiting_time','payment_expiry_time','payment_waiting_time','number_of_morning','number_of_night',
                  'user_rating_review','tax_amount','promocode_applied','discount_percentage_applied','qr_code_url', 'tax_and_services', 'meal_price', 'meal_tax']
        
    
    def __init__(self, *args, **kwargs):
        context = kwargs.get('context', {})  # Safely get context
        self.language = context.get('request', {}).GET.get('lang', 'en') if context.get('request') else 'en'
        super().__init__(*args, **kwargs)
        
    def get_property_details(self, obj):
    # Pass the context explicitly to ChaletModelSerializer
        return PropertyDetails(obj.hotel, context=self.context).data
    
    def get_type(self, obj):
        type = "hotel"
        return type
    
    def get_checkin_date(self, obj):
        date_and_time = f"{obj.checkin_date} {obj.hotel.checkin_time}"
        return date_and_time
    
    def get_checkout_date(self, obj):
        date_and_time = f"{obj.checkout_date} {obj.hotel.checkout_time}"
        return date_and_time
    
    
    def get_guest_details(self, obj):
        guest_details = {}
        guest_details['first_name'] = obj.booking_fname
        guest_details['booking_lname'] = obj.booking_lname
        guest_details['booking_email'] = obj.booking_email
        guest_details['booking_mobilenumber'] = obj.booking_mobilenumber
        return guest_details
    
    from datetime import timedelta

    def get_room_type(self, obj):
        room_details_list = []
        rooms = Bookedrooms.objects.filter(booking_id=obj.id)
        request = self.context.get('request')
        
        if rooms:
            for room in rooms:
                image_obj = RoomImage.objects.filter(roommanagement=room.room).first()

                # Build clickable URL for the image (if the request exists)
                if request and image_obj and image_obj.image:
                    image_url = request.build_absolute_uri(image_obj.image.url)
                else:
                    image_url = None  # If no image or no request, return None

                # Calculate the number of nights
                num_nights = (obj.checkout_date - obj.checkin_date).days  # Ensure dates are valid

                # Calculate the average price for the room
                average_price = _calculate_average_price(
                    rooms=[room.room],  
                    checkin_date=obj.checkin_date,  
                    checkout_date=obj.checkout_date,  
                    property="hotel"  
                )

                # Multiply the average price by the number of nights
                total_price = average_price * num_nights if num_nights > 0 else average_price  # Fallback in case of same-day booking

                room_details = {
                    'id': room.room.id,
                    'room_type': room.room.room_types.room_types,
                    'meals': room.room.meals.all().values_list('meal_type', flat=True).first(),
                    'price_per_night': total_price,  # Now reflecting total price for stay
                    'status': room.room.status,
                    'image': image_url
                }
                room_details_list.append(room_details)

        return room_details_list

    def get_availability_waiting_time(self, obj):
        get_created_time = obj.created_date
        if get_created_time:
            dt = datetime.fromisoformat(str(get_created_time))
            dt_plus_10 = dt + timedelta(minutes=10)
            # Format it to YYYY-MM-DD hh:mm:ss
            availability_waiting_time = dt_plus_10.strftime("%Y-%m-%d %H:%M:%S")
            return availability_waiting_time
        return None
    
    def get_payment_expiry_time(self, obj):
        if obj.status in ["pending","booked","confirmed"]:
            get_crated_time = obj.modified_date
            dt = datetime.fromisoformat(str(get_crated_time))
            dt_plus_30 = dt + timedelta(minutes=30)
            # Format it to YYYY-MM-DD hh:mm:ss
            payment_expiry_time = dt_plus_30.strftime("%Y-%m-%d %H:%M:%S")
            return payment_expiry_time
        return None
    
    def get_payment_waiting_time(self, obj):
        payment_waiting_time = "30 mins"
        return payment_waiting_time
    
    def get_number_of_morning(self, obj):
        duration = (obj.checkout_date - obj.checkin_date).days
        return max(duration + 1, 0)

    def get_number_of_night(self, obj):
        duration = (obj.checkout_date - obj.checkin_date).days
        return max(duration, 0)
    
    def get_user_rating_review(self, obj):
        if obj.status == "completed":
            recent_review = RecentReview.objects.filter(hotel=obj.hotel, booking__booking_id=obj.booking_id).first()
            if recent_review:
                data={
                    'rating':recent_review.rating,
                    'review':recent_review.review_text
                }
                return data
            return None
        
    def get_tax_amount(self, obj):
        return obj.hotel.country.tax

    def get_tax_and_services(self, obj):
        return Decimal(obj.tax_and_services) if hasattr(obj, 'tax_and_services') else None

    def get_meal_tax(self, obj):
        return Decimal(obj.meal_tax) if hasattr(obj, 'meal_tax') else None

    def get_meal_price(self, obj):
        return Decimal(obj.meal_price) if hasattr(obj, 'meal_price') else None

    
    
class ChaletBookingDetailModelSerializer(serializers.ModelSerializer):
    property_details = serializers.SerializerMethodField()
    guest_details = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    availability_waiting_time = serializers.SerializerMethodField()
    payment_expiry_time = serializers.SerializerMethodField()
    payment_waiting_time = serializers.SerializerMethodField()
    number_of_morning = serializers.SerializerMethodField()
    number_of_night = serializers.SerializerMethodField()
    user_rating_review = serializers.SerializerMethodField()
    checkin_date = serializers.SerializerMethodField()
    checkout_date = serializers.SerializerMethodField()
    tax_amount = serializers.SerializerMethodField()
    tax_and_services = serializers.SerializerMethodField()

    class Meta:
        model = ChaletBooking
        fields = [
            'id', 'status', 'type', 'property_details', 'checkin_date', 'checkout_date', 
            'discount_price', 'number_of_guests', 'number_of_booking_rooms', 'booking_id',
            'service_fee', 'booked_price', 'guest_details', 'availability_waiting_time', 
            'payment_expiry_time', 'payment_waiting_time', 'number_of_morning', 
            'number_of_night', 'user_rating_review', 'tax_amount', 'qr_code_url', 
            'tax_and_services'
        ]

    def __init__(self, *args, **kwargs):
        context = kwargs.get('context', {})  # Safely get context
        self.language = context.get('request', {}).GET.get('lang', 'en') if context.get('request') else 'en'
        super().__init__(*args, **kwargs)

    def get_property_details(self, obj):
        # Serialize the chalet object using ChaletModelSerializer
        chalet_data = ChaletModelSerializer(obj.chalet, context=self.context).data

        # Calculate the total price for the booking duration
        
        average_price_per_day = calculate_hotel_price(
            chalet_id=obj.chalet.id,
            property='chalet',
            checkin_date=obj.checkin_date,
            checkout_date=obj.checkout_date
        ).get("calculated_price")

        # Calculate the number of nights
        number_of_nights = (obj.checkout_date - obj.checkin_date).days

        # Calculate the total price by multiplying average price per day by number of nights
        total_price = average_price_per_day * number_of_nights

        # Add the calculated total price to the property_details
        chalet_data['price'] = total_price

        return chalet_data
    
    def get_type(self, obj):
        type = "chalet"
        return type
    
    def get_checkin_date(self, obj):
        date_and_time = f"{obj.checkin_date} {obj.chalet.checkin_time}"
        return date_and_time
    
    def get_checkout_date(self, obj):
        date_and_time = f"{obj.checkout_date} {obj.chalet.checkout_time}"
        return date_and_time
    
    def get_guest_details(self, obj):
        guest_details = {}
        guest_details['first_name'] = obj.booking_fname
        guest_details['booking_lname'] = obj.booking_lname
        guest_details['booking_email'] = obj.booking_email
        guest_details['booking_mobilenumber'] = obj.booking_mobilenumber
        return guest_details
    
    def get_availability_waiting_time(self, obj):
        get_created_time = obj.created_date
        if get_created_time:
            dt = datetime.fromisoformat(str(get_created_time))
            dt_plus_10 = dt + timedelta(minutes=10)
            # Format it to YYYY-MM-DD hh:mm:ss
            availability_waiting_time = dt_plus_10.strftime("%Y-%m-%d %H:%M:%S")
            return availability_waiting_time
        return None
    
    def get_payment_expiry_time(self, obj):
        if obj.status in ["pending","booked","confirmed"]:
            get_crated_time = obj.modified_date
            dt = datetime.fromisoformat(str(get_crated_time))
            dt_plus_30 = dt + timedelta(minutes=30)
            # Format it to YYYY-MM-DD hh:mm:ss
            payment_expiry_time = dt_plus_30.strftime("%Y-%m-%d %H:%M:%S")
            return payment_expiry_time
        return None
    
    def get_payment_waiting_time(self, obj):
        payment_waiting_time = "30 mins"
        return payment_waiting_time
    
    def get_number_of_morning(self, obj):
        duration = (obj.checkout_date - obj.checkin_date).days
        return max(duration + 1, 0)

    def get_number_of_night(self, obj):
        duration = (obj.checkout_date - obj.checkin_date).days
        return max(duration, 0)
    
    def get_user_rating_review(self, obj):
        if obj.status == "completed":
            recent_review = ChaletRecentReview.objects.filter(chalet=obj.chalet,  chalet_booking__booking_id=obj.booking_id).first()
            if recent_review:
                data={
                    'rating':recent_review.rating,
                    'review':recent_review.review_text
                }
                return data
            return None
    
    def get_tax_amount(self, obj):
        return obj.chalet.country.tax
    def get_tax_and_services(self, obj):
        return obj.tax_and_services if hasattr(obj, 'tax_and_services') else None  # Ensure field exists


class PaymentDetailsSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=11, decimal_places=3)
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    email = serializers.EmailField(allow_blank=True)
    phone_number = serializers.CharField(allow_blank=True)

    def validate_amount(self, value):
        if value is None or value == "":
            raise serializers.ValidationError("Amount should not be empty or none")
        return value

    def validate_first_name(self, value):
        if value is None or value.strip() == "":
            raise serializers.ValidationError("First Name should not be empty or none")
        if len(value) > 30:
            raise serializers.ValidationError("First Name should be less than or equal to 30 in char")
        return value

    def validate_last_name(self, value):
        if value is None or value.strip() == "":
            raise serializers.ValidationError("Last Name should not be empty or none")
        if len(value) > 30:
            raise serializers.ValidationError("Last Name should be less than or equal to 30 in char")
        return value

    def validate_email(self, value):
        if value is None or value.strip() == "":
            raise serializers.ValidationError("Email should not be empty or none")
        return value

    def validate_phone_number(self, value):
        if value is None or value.strip() == "":
            raise serializers.ValidationError("Phone Number should not be empty or none")
        if len(value) > 15:
            raise serializers.ValidationError("Phone Number should be less than or equal to 15 in numbers")
        return value
    



class TransactionDataSerializer(serializers.Serializer):
    result = serializers.CharField()
    date = serializers.CharField()
    respDateTime = serializers.CharField()
    ref = serializers.CharField(allow_blank=True, required=False)
    paymentId = serializers.CharField()
    trackId = serializers.CharField()
    udf5 = serializers.CharField()
    amt = serializers.CharField()
    udf3 = serializers.CharField()
    udf4 = serializers.CharField()
    udf1 = serializers.CharField()
    udf2 = serializers.CharField()
    
    
class PaymentStatusResponseSerializer(serializers.Serializer):
    trandata = TransactionDataSerializer(many=True)
    category = serializers.CharField()
    booking_id = serializers.CharField()