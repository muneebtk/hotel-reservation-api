import json
import re
import uuid
import ast
from django.conf import settings
import requests
import logging
import qrcode
import phonenumbers

from django.http import Http404
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.db.models import Q, Count, Min, Max,Sum,Avg,Case, When
from django.shortcuts import get_object_or_404
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.core.validators import EmailValidator, validate_email
from django.utils.translation import override
from django.utils.timezone import now
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import DatabaseError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import serializers
from rest_framework.exceptions import ValidationError, NotFound, APIException
from rest_framework.viewsets import ModelViewSet
from rest_framework.pagination import PageNumberPagination
from rest_framework import filters
from rest_framework.permissions import AllowAny
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation,ROUND_DOWN
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
from allauth.socialaccount.providers.apple.views import AppleOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView
from dj_rest_auth.registration.serializers import SocialLoginSerializer
from django_filters import rest_framework as django_filters
from io import BytesIO
from django.shortcuts import redirect, render
from django.views import View
from phonenumbers import NumberParseException
from Bookingapp_1969.celery import update_booking_status, update_chaletbooking_status
from api.utils import calculate_commission, create_wallet_transaction, generate_qr_code, generate_qr_code_chalet, generate_referral_token
from common.permissions import AllowEndUserOnly
from common.utils import create_notification, send_firebase_notification, payment_gateway
from common.emails import notify_booking_aggregator
from api.function import calculate_hotel_price, generate_track_id, get_discounted_price_for_property,amount_validity, check_promocode_validity, create_wallet_transaction, discount_cal, get_available_room, get_available_rooms, otp_generator, send_email, send_sms_otp,delete_booking,Check_refund_eligibility,get_payment_details,create_cash_transaction,Check_payment_type,Check_refund_amount,calculate_minimum_hotel_price,Check_current_room_availability,backup_function_payment,bank_charge_calculation
from user.models import *
from chalets.models import Chalet, ChaletBooking, ChaletRecentReview, ChaletTax,ChaletTransaction,Promotion,Comparison,Featured,Notification,ChaletFavorites,CancelChaletBooking
from api.serializer import (BookingCalculationSerializer, BookingDetailModelSerializer, ChaletBookingDetailModelSerializer, HotelArabSerializer, NotificationSerialiser, PaymentStatusResponseSerializer, RegisteruserSerializer, 
                            Emailverifivation,LoginUserSerializer,HotelSearchSerializer,HotelSerializer,PropertyDetails,RoomlistingSerializer, RoomtypeSerializer,UserSerializer,RoombookingSerializer,
                            GroupedHotelBookingSerializer,ForgetpasswordEmailrequestSerializer,ResetpasswordSerializer,MobileloginSerializer,VerifymobileotpSerializer,RatingReviewSerializer,
                            ChaletRatingReviewSerializer,FavoritesmanagementSerializer,FavoriteslistSerializer,CancelbookingSerializer,RatingfilterSerializer,RecentReviewSerializer,UserProfileSerializer,
                            ChaletModelSerializer,ChaletBookingSerializer,ChaletFavoritesmanagementSerializer,ChaletFavoriteslistSerializer,GroupedChaletBookingSerializer,ChaletBookingCancelSerializer,
                            ChaletSearchSerializer,PromoCodeSerializer,PromotionSerializer,DailyDealSerializer,CheckpromoSerializer,ComparisonSerializer,CompareSerializer,Featuredserializer,WalletPaymentSerializer,
                            Refund_Serializer,PaymentDetailsSerializer)
from common.models import   Amenity, Country,Categories,RefundTransaction
from vendor.models import *
from urllib.parse import urljoin
from common.function import generate_transaction_id, update_transaction_status, update_vendor_earnings
from django.db.models import OuterRef, Subquery
from collections import defaultdict
from vendor.function import detect_lang
from commonfunction import get_nearby_hotels,get_nearby_chalets
logger = logging.getLogger('lessons')


def get_average_rating(hotel):
    avg_rating = RecentReview.objects.filter(Q(hotel=hotel)).aggregate(Avg('rating')).get('rating__avg')
    return avg_rating if avg_rating is not None else Decimal('Infinity')

class RegisterUser(APIView):
    def get(self, request):
        return Response(
            {'message': 'The requested HTTP method is not supported for the requested resource. Please use POST for this endpoint.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def post(self, request):
        data = request.data
        logger.info(f"Request data: {data}")
        serializer = RegisteruserSerializer(data=data)

        if serializer.is_valid(raise_exception=True):
            try:
                logger.info("Serializer is valid. Extracting data.")
                # Extract and validate data
                first_name = serializer.validated_data.get('first_name', '').strip()
                last_name = serializer.validated_data.get('last_name', '').strip()
                email = serializer.validated_data.get('email', '').strip()
                contact_number = serializer.validated_data.get('contact_number', '').strip()
                dial_code=serializer.validated_data.get('dial_code', '').strip()
                iso_code=serializer.validated_data.get('iso_code', '').strip()
                password = serializer.validated_data.get('password', '').strip()
                confirm_password = serializer.validated_data.get('confirm_password', '').strip()
                referral_token = serializer.validated_data.get('referral_token', None)
                firebase_token = serializer.validated_data.get('fcmToken', None)
                logger.info("Validating required fields.")
               # Enforce mandatory fields
                required_fields = {
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'contact_number': contact_number,
                    'password': password,
                    'confirm_password': confirm_password
                }

                missing_fields = [field for field, value in required_fields.items() if not value]

                if missing_fields:
                    logger.info(f"Missing fields: {missing_fields}")
                    return Response(
                        {'message': f"The following fields are required: {', '.join(missing_fields)}."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                logger.info("Validating email format.")
                # Validate email format
                if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,10}$", email):
                    return Response({'message': "Enter a valid email address."}, status=status.HTTP_400_BAD_REQUEST)

                logger.info("Validating phone number format.")
                # Validate phone number format (international)
                try:
                    full_number = f"{dial_code}{contact_number}"
                    logger.info(f"full_number===={full_number}")
                    parsed_phone = phonenumbers.parse(full_number, None)
                    if not phonenumbers.is_valid_number(parsed_phone):
                        return Response({'message': "Enter a valid international phone number."}, status=status.HTTP_400_BAD_REQUEST)
                except NumberParseException:
                    logger.info("Invalid phone number format.")
                    return Response({'message': "Invalid phone number format."}, status=status.HTTP_400_BAD_REQUEST)

                # Validate password match
                if password != confirm_password:
                    return Response({'message': "Passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)
                # Validate password format
                password_pattern = r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@#$%^&+=*]).{8,}$'
                if not re.match(password_pattern, password):
                    return Response(
                        {'message': "Password must be at least 8 characters long and include at least one uppercase letter, one lowercase letter, one digit, and one special character (e.g., @, #, $, etc.)."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Validate name fields (boundary, edge cases)
                if not first_name.isalpha() or len(first_name) > 50:
                    return Response({'message': "First name must contain only letters and be less than 50 characters."}, status=status.HTTP_400_BAD_REQUEST)
                if not last_name.isalpha() or len(last_name) > 50:
                    return Response({'message': "Last name must contain only letters and be less than 50 characters."}, status=status.HTTP_400_BAD_REQUEST)

                # Check if email already exists
                if Userdetails.objects.filter(user__email=email, user__is_active=True, user__is_vendor=False,user__is_deleted=False).exists():
                    logger.info(f"\n\nEmail already exists. Please use a different email or login.\n\n")
                    return Response({'message': 'Email already exists. Please use a different email or login.'}, status=status.HTTP_400_BAD_REQUEST)
                elif User.objects.filter(email=email,is_vendor=False,is_deleted=False).first():
                    if not User.objects.get(email=email,is_vendor=False,is_deleted=False).is_active:
                        logger.info(f"\n\nsame user but email is not verified. So deleting the existing unverified user \n\n")
                        User.objects.get(email=email,is_vendor=False,is_deleted=False).delete()
                
                # Create user
                user_name = str(uuid.uuid4())
                user = User.objects.create_user(
                    username=user_name,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    password=password,
                    is_vendor=False,
                    is_deleted=False
                )
                user.is_active = False
                user.save()

                created = Userdetails.objects.create(user=user, contact_number=contact_number,dial_code=dial_code,iso_code=iso_code,
                                                     firebase_token=firebase_token)

                # Handle referral token
                referral_info = "Not applicable"
                if referral_token:
                    referrer_user = Referral.objects.filter(token=referral_token).first()
                    referral, _ = Referral.objects.get_or_create(
                        token=referral_token,
                        defaults={
                            'referrer': referrer_user,
                            'status': 'pending'
                        }
                    )
                    if referral:
                        referral_user = Userdetails.objects.get(id=referral.referrer.id,user__is_deleted=False)
                        referrer_wallet, _ = Wallet.objects.get_or_create(user=referral_user, status="active")
                        create_wallet_transaction(wallet=referrer_wallet, transaction_type='credit', amount=50)
                        referral.referee = created
                        referral.status = 'successful'
                        referral.save()
                        referral_info = "The referral was successful"
                    else:
                        referral_info = 'Invalid or expired referral token'

                # Send email and store OTP
                context, get_otp = send_email(request, user, first_name)
                Storeotp.objects.create(user=created, otp=get_otp, catogory='email_otp')

                return Response({
                    'message': 'User registered successfully. An OTP has been sent to the registered email. Please verify your email using the OTP.',
                    'data': context,
                    'referral_status': referral_info
                }, status=status.HTTP_200_OK)

            except User.DoesNotExist:
                logger.info("User creation failed.")
                return Response({'message': 'User creation failed. Please check your input and try again.'}, status=status.HTTP_400_BAD_REQUEST)
            except Referral.DoesNotExist:
                logger.info("Referral token is invalid or not found.")
                return Response({'message': 'Referral token is invalid or not found.'}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                logger.info(f"An error occurred: {str(e)}")
                # Return specific error for debugging
                return Response({'message': f"Error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        logger.info("Serializer validation failed.")
        # Return serializer errors
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class ResendEmail(APIView):
    def get(self, request):
        return Response({'message':'The requested HTTP method is not supported for the requested resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used for this endpoint'},status=status.HTTP_405_METHOD_NOT_ALLOWED)
    def post(self, request, email):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return Response({'message': "Enter a valid email address"}, status=status.HTTP_400_BAD_REQUEST)

        user = Userdetails.objects.filter(user__email=email, user__is_active=False, user__is_vendor=False,user__is_deleted=False).first()
        if not user:
            return Response({'message': 'User not found or user is already active'}, status=status.HTTP_404_NOT_FOUND)

        try:
            context, get_otp = send_email(request, user.user, user.user.first_name)
        except Exception as e:
            return Response({'message': 'Failed to send OTP email'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            print(user)
            stored_otp_obj = Storeotp.objects.get(user=user, catogory='email_otp')
            print(stored_otp_obj)
            stored_otp_obj.otp = get_otp
            stored_otp_obj.save()
        except Storeotp.DoesNotExist:
            return Response({'message': 'OTP record not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'message': 'Failed to store OTP'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'message': 'OTP mail resent successfully', 'data': context}, status=status.HTTP_200_OK)



class Emailverifyusinfotp(APIView):
    def get(self, request):
        return Response({'message':'The requested HTTP method is not supported for the requested resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used for this endpoint'},status=status.HTTP_405_METHOD_NOT_ALLOWED)
    def post(self, request):
        data = request.data
        serializer = Emailverifivation(data=data)
        
        if serializer.is_valid(raise_exception=True):
            otp = serializer.validated_data.get('otp')
            stored_email = serializer.validated_data.get('stored_email')
            if not otp:
                return Response({'message': "Please enter the otp"}, status=status.HTTP_400_BAD_REQUEST)

            get_user = Userdetails.objects.filter(user__email=stored_email, user__is_vendor=False,user__is_deleted=False).first()
            if not get_user:
                return Response({'message': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

            try:
                get_otp = Storeotp.objects.get(user=get_user, catogory='email_otp')
            except Storeotp.DoesNotExist:
                return Response({'message': 'OTP not found'}, status=status.HTTP_404_NOT_FOUND)

            if not get_user.user.is_active:
                if otp == get_otp.otp:
                    get_user.user.is_active = True
                    get_user.user.save()
                    return Response({'message': 'Email has been verified'}, status=status.HTTP_200_OK)
                return Response({'message': 'Please enter the correct OTP'}, status=status.HTTP_401_UNAUTHORIZED)
            
            return Response({'message': 'Email is already verified'}, status=status.HTTP_302_FOUND)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginUser(APIView):
    def get(self, request):
        return Response({
            'message': 'The requested HTTP method is not supported for the requested resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used for this endpoint'
        }, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def post(self, request):
        data = request.data
        serializer = LoginUserSerializer(data=data)
        
        if serializer.is_valid(raise_exception=True):
            email = serializer.validated_data.get('email')
            password = serializer.validated_data.get('password')
            device_name = serializer.validated_data.get('device_name')  
            platform = serializer.validated_data.get('platform')
            firebase_token = serializer.validated_data.get('fcmToken')  
            logger.info(f"\n\n\n\n\n firebase_token: {firebase_token} \n\n\n\n\n\n")
            
            if not platform:
                return Response({'message': "Platform name is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            if not email:
                return Response({'message': "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            if not password:
                return Response({'message': "Password is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                return Response({'message': "Enter a valid email address"}, status=status.HTTP_400_BAD_REQUEST)

            user = Userdetails.objects.filter(user__email=email, user__is_vendor=False,user__is_deleted=False).first()
            if not user:
                return Response({
                    'message': 'The email address you entered is not registered with us. Please check the email or sign up for a new account'
                }, status=status.HTTP_404_NOT_FOUND)

            # Check if user is active before verifying the password
            if not user.user.is_active:
                return Response({'message': "Your account is inactive. If you are a new user, please verify your email to activate your account. Otherwise, contact our support team for assistance."}, status=status.HTTP_401_UNAUTHORIZED)

            if user.user.check_password(password):
                if platform:
                    user.operating_system = platform

                user.firebase_token = firebase_token
                user.save()

                refresh = RefreshToken.for_user(user.user)

                # Send Firebase notification
                try:
                    firebase_title = "Welcome Back!"
                    firebase_message = f"Hello {user.user.first_name}, you have successfully logged in."
                    firebase_data = {'type': 'login_success'}
                    logger.info(f"\n\n\n\n\n\n user.firebase_token: {user.firebase_token} \n\n\n\n\n\n\n")
                    if user.firebase_token:
                        firebase_result = send_firebase_notification(
                            device_token=user.firebase_token,
                            title=firebase_title,
                            body=firebase_message,
                            data=firebase_data
                        )
                    else:
                        logger.info(f"\n\n\n\n Firebase token is missing for the user. \n\n\n\n\n")
                        firebase_result = None
                    logger.info(f"Firebase notification for user {user.user.id} with result: {firebase_result}")
                except Exception as e:
                    logger.error(f"Error sending Firebase notification: {e}")
                
                return Response({
                    'message': 'Login successful',
                    'user_id': user.id,
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }, status=status.HTTP_200_OK)
                
            return Response({'message': "Password is wrong. Please check the password"}, status=status.HTTP_400_BAD_REQUEST)

class Forgotpassword_email(APIView):
    def get(self, request):
        return Response({'message':'The requested HTTP method is not supported for the requested resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used for this endpoint'},status=status.HTTP_405_METHOD_NOT_ALLOWED)
    def post(self, request):
        data = request.data
        serializer = ForgetpasswordEmailrequestSerializer(data=data)
        
        if serializer.is_valid(raise_exception=True):
            email = serializer.validated_data.get('email')
            
            if not email:
                return Response({'message': "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                return Response({'message': "Enter a valid email address"}, status=status.HTTP_400_BAD_REQUEST)
            
            user = Userdetails.objects.filter(user__email=email, user__is_active=True, user__is_vendor=False,user__is_deleted=False).first()
            if not user:
                return Response({'message': 'Email is not registered. Kindly recheck the email you have entered'}, status=status.HTTP_404_NOT_FOUND)
            
            try:
                token = default_token_generator.make_token(user.user)
            except Exception as e:
                return Response({'message': 'Failed to generate password reset token'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            reset_url = request.build_absolute_uri(reverse('password_reset', args=[user.user.pk, token]))
            subject = 'Reset your password'
            recipient_list = [email]
            
            context = {
                'reset_url': reset_url,
                'first_name': user.user.first_name
            }
            html_content = render_to_string('password_reset.html', context)
            text_content = strip_tags(html_content)
            
            try:
                for recipient_email in recipient_list:
                    email_message = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [recipient_email])
                    email_message.attach_alternative(html_content, "text/html")
                    email_message.send()
            except Exception as e:
                logger.error(f"Exception raised in Failed to send reset email. Exception {e}")
                return Response({'message': 'Failed to send reset email. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
            return Response({'message': 'Password reset email sent successfully', 'data': context}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
   
class Resetpassword(APIView):
    def get(self, request, id, token):
        return Response({'message':'The requested HTTP method is not supported for the requested resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used for this endpoint'},status=status.HTTP_405_METHOD_NOT_ALLOWED)
    def post(self, request, id, token):
        data = request.data
        serializer = ResetpasswordSerializer(data=data)
        
        if serializer.is_valid(raise_exception=True):
            try:
                user = get_object_or_404(User, pk=id)
            except Http404:
                return Response({'message': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
            
            password = serializer.validated_data.get('password')
            confirm_password = serializer.validated_data.get('confirm_password')
            
            if not password or not confirm_password:
                return Response({'message': 'Password and confirm password are required'}, status=status.HTTP_400_BAD_REQUEST)

            if password != confirm_password:
                return Response({'message': 'Please check the password. Passwords do not match'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                validate_password(password)        
            except Exception as e:
                return Response({'message': e}, status=status.HTTP_400_BAD_REQUEST)
            if default_token_generator.check_token(user, token):
                try:
                    user.set_password(password)
                    user.save()
                    return Response({"message": "Password has been reset."}, status=status.HTTP_200_OK)
                except Exception as e:
                    return Response({'message': 'Failed to reset the password. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response({'message': 'Token is invalid'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

# class Googlesignin(APIView):
#     def get(self, request):
#         return Response({'message':'The requested HTTP method is not supported for the requested resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used for this endpoint'},status=status.HTTP_405_METHOD_NOT_ALLOWED)
#     def post(self, request):
#         serializer = GoogleSignInSerializer(data=request.data)
        
#         if serializer.is_valid():
#             accessToken = serializer.validated_data.get('accessToken')
#             print(accessToken)
            
#             # Verify the access token with Google
#             response = requests.get(f'https://openidconnect.googleapis.com/v1/userinfo?access_token={accessToken}')
#             print(response.status_code)
#             if response.status_code != 200:
#                 return Response({'error': 'Invalid access token'}, status=status.HTTP_400_BAD_REQUEST)

#             user_info = response.json()
#             print(user_info, "==================")
#             email = user_info.get('email')
#             first_name = user_info.get('given_name')
#             last_name = user_info.get('family_name')

#             if not email:
#                 return Response({'error': 'Failed to retrieve email from Google'}, status=status.HTTP_400_BAD_REQUEST)

#             user_name = str(uuid.uuid4())
#             try:
#                 user, created = User.objects.get_or_create(email=email)
#             except Exception as e:
#                 print(e,"==============++++++++++++++++")
#                 return Response({'error': 'Try with different mail'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
#             if created:
#                 try:
#                     user.username = user_name
#                     user.first_name = first_name
#                     user.last_name = last_name
#                     user.set_unusable_password()
#                     user.is_active = True
#                     user.save()
                    
#                     is_vendor = False
#                     Userdetails.objects.create(user=user, is_vendor=is_vendor)
#                 except Exception as e:
#                     return Response({'error': 'Failed to create a new user'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#                 refresh = RefreshToken.for_user(user)
#                 return Response({
#                     'message': 'New User logged in successfully',
#                     'refresh': str(refresh),
#                     'access': str(refresh.access_token),
#                     'user_id': user.id
#                 }, status=status.HTTP_200_OK)
            
#             else:
#                 if user.is_active:
#                     refresh = RefreshToken.for_user(user)
#                     return Response({
#                         'message': 'Existing User logged in successfully',
#                         'refresh': str(refresh),
#                         'access': str(refresh.access_token),
#                         'user_id': user.id
#                     }, status=status.HTTP_200_OK)
#                 else:
#                     return Response({'error': 'User account is inactive'}, status=status.HTTP_403_FORBIDDEN)
        
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GoogleLoginView(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter

    def post(self, request):
        
        # Skip serializer validation if you don't need it
        firebase_token = request.data.get('fcmToken')
        access_token = request.data.get('access_token')
        platform = request.data.get('platform')
        if not access_token:
            return Response({'error': 'Access token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user info from Google
        response = requests.get(f'https://openidconnect.googleapis.com/v1/userinfo?access_token={access_token}')
        if response.status_code != 200:
            return Response({'error': 'Invalid access token'}, status=status.HTTP_400_BAD_REQUEST)
        
        user_info = response.json()
        email = user_info.get('email')
        first_name = user_info.get('given_name')
        last_name = user_info.get('family_name')
        print(user_info, email, first_name, last_name,"=====================")
        if not email:
            return Response({'error': 'Failed to retrieve email from Google'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user exists
        user = User.objects.filter(email=email,is_vendor = False, is_deleted=False).first()
        
        if not user:
            # Create new user if not found
            user_name = str(uuid.uuid4())
            user = User.objects.create(
                email=email,
                username=user_name,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                is_deleted=False
            )
            user.set_unusable_password()
            user.save()
            
            # Create user details
            user_details = Userdetails.objects.create(user=user)
            message = 'New User logged in successfully'
        else:
            user_details = Userdetails.objects.filter(user=user).first()
            message = 'Existing User logged in successfully'
        if platform:
            user_details.operating_system = platform
            user_details.save()
        # Save Firebase token
        if firebase_token:
            user_details.firebase_token = firebase_token
            user_details.save()
        if user.is_active:
            # Generate tokens for the user
            refresh = RefreshToken.for_user(user)

            # Send Firebase notification
            try:
                firebase_title = "Welcome Back!"
                firebase_message = f"Hello {user.first_name}, you have successfully logged in."
                firebase_data = {'type': 'login_success'}
                
                if user_details.firebase_token:
                    firebase_result = send_firebase_notification(
                        device_token=user_details.firebase_token,
                        title=firebase_title,
                        body=firebase_message,
                        data=firebase_data
                    )
                    logger.info(f"Firebase notification for user {user.id} with result: {firebase_result}")
                else:
                    logger.info("Firebase token is missing for the user.")
            except Exception as e:
                logger.error(f"Error sending Firebase notification: {e}")

            return Response({
                'message': message,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user_id': user.id
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'User account is inactive'}, status=status.HTTP_403_FORBIDDEN)
        
class FacebookLoginView(SocialLoginView):
    adapter_class = FacebookOAuth2Adapter

    def post(self, request):
        firebase_token = request.data.get('fcmToken')
        access_token = request.data.get('access_token')
        platform = request.data.get('platform')
        if not access_token:
            return Response({'error': 'Access token is required'}, status=status.HTTP_400_BAD_REQUEST)

        response = requests.get(
            f'https://graph.facebook.com/me?fields=id,email,first_name,last_name&access_token={access_token}'
        )
        if response.status_code != 200:
            return Response({'error': 'Invalid access token'}, status=status.HTTP_400_BAD_REQUEST)

        user_info = response.json()
        email = user_info.get('email')
        first_name = user_info.get('first_name')
        last_name = user_info.get('last_name')

        if not email:
            return Response({'error': 'Failed to retrieve email from Facebook'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user exists
        user = User.objects.filter(email=email, is_vendor=False,is_deleted=False).first()

        if not user:
            # Create new user if not found
            user_name = str(uuid.uuid4())
            user = User.objects.create(
                email=email,
                username=user_name,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                is_deleted=False
            )
            user.set_unusable_password()
            user.save()

            # Create social account
            social_account = SocialAccount.objects.create(
                user=user,
                provider='facebook',
                uid=user_info['id'],
                extra_data=user_info,
            )

            # Create user details
            user_details = Userdetails.objects.create(user=user)
            message = 'New User logged in successfully'
        else:
            user_details = Userdetails.objects.filter(user=user).first()
            message = 'Existing User logged in successfully'
        if platform:
            user_details.operating_system = platform
            user_details.save()
            
        if firebase_token:
            user_details.firebase_token = firebase_token
            user_details.save()

        if user.is_active:
            # Generate tokens for the user
            refresh = RefreshToken.for_user(user)

            # Send Firebase notification
            try:
                firebase_title = "Welcome Back!"
                firebase_message = f"Hello {user.first_name}, you have successfully logged in."
                firebase_data = {'type': 'login_success'}
                
                if user_details.firebase_token:
                    firebase_result = send_firebase_notification(
                        device_token=user_details.firebase_token,
                        title=firebase_title,
                        body=firebase_message,
                        data=firebase_data
                    )
                    logger.info(f"Firebase notification for user {user.id} with result: {firebase_result}")
                else:
                    logger.info("Firebase token is missing for the user.")
            except Exception as e:
                logger.error(f"Error sending Firebase notification: {e}")

            return Response({
                'message': message,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user_id': user.id
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'User account is inactive'}, status=status.HTTP_403_FORBIDDEN)

import jwt
import requests
from jwt.algorithms import RSAAlgorithm
class AppleLoginView(SocialLoginView):
    adapter_class = AppleOAuth2Adapter
    def post(self, request):
        try:
            apple_keys = requests.get("https://appleid.apple.com/auth/keys").json()['keys']
            token = request.data.get('access_token')
            firebase_token = request.data.get('fcmToken')
            first_name = request.data.get('first_name')
            last_name = request.data.get('last_name')
            platform = request.data.get('platform')
            logger.info(f"Token -----{token}")
            logger.info(f"firebase_token -----{firebase_token}")
            logger.info(f"first_name -----{first_name}")

            if not token:
                return Response({'error': 'Access token is required'}, status=status.HTTP_400_BAD_REQUEST)

            header = jwt.get_unverified_header(token)
            key_id = header['kid']
            public_key = next(key for key in apple_keys if key['kid'] == key_id)
            rsa_key = RSAAlgorithm.from_jwk(public_key)

            decoded = jwt.decode(
                token,
                key=rsa_key,
                algorithms=['RS256'],
                audience=settings.SOCIALACCOUNT_PROVIDERS.get('apple').get('APP').get('service_id'),
                issuer='https://appleid.apple.com'
            )

            if not decoded:
                return Response({'error': 'Failed to decode token'}, status=status.HTTP_400_BAD_REQUEST)

            email = decoded.get('email')
            apple_user_id = decoded.get('sub')
            logger.info(f"Decoded email: {email}, Apple UID: {apple_user_id}")

            if not email:
                return Response({'error': 'Email not found in token'}, status=400)

            user = User.objects.filter(email=email, is_vendor=False, is_deleted=False).first()
            if user:
                logger.info(f"----{user}")

            # 💡 Ensure no existing SocialAccount blocks fresh login
            try:
                existing_account = SocialAccount.objects.filter(provider='apple', uid=apple_user_id).first()
                if existing_account:
                    logger.info(f"Deleting existing SocialAccount for UID {apple_user_id}")
                    existing_account.delete()
                    logger.info("socail account deleted")
            except Exception as e:
                logger.info(f"No social account found : {e}")

            if not user:
                logger.info("entered user creation part")
                if not first_name and not last_name:
                    return Response({'error': 'First name and last name are required'}, status=status.HTTP_400_BAD_REQUEST)
                user = User.objects.create(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    username=str(uuid.uuid4()),
                    is_active=True
                )
                user.set_unusable_password()
                user.save()

                SocialAccount.objects.create(
                    user=user,
                    provider='apple',
                    uid=apple_user_id,
                    extra_data=decoded,
                )

                user_details = Userdetails.objects.create(user=user)
                logger.info(f"User created successfully --- {user_details}")
                message = 'New User logged in successfully'
            else:
                try:
                    user_details, created = Userdetails.objects.get_or_create(user=user)
                    if created:
                        logger.info(f"Userdetails created for user {user}")
                    else:
                        logger.info(f"Userdetails already existed --- {user_details}")
                except Exception as e:
                    logger.error(f"Error while getting/creating Userdetails: {e}")


                # 🛠 Recreate SocialAccount if not found (in case it was deleted)
                SocialAccount.objects.get_or_create(
                    user=user,
                    provider='apple',
                    uid=apple_user_id,
                    defaults={'extra_data': decoded}
                )
                message = 'Existing User logged in successfully'
            if platform:
                user_details.operating_system = platform
                user_details.save()
            if firebase_token:
                user_details.firebase_token = firebase_token
                user_details.save()

            if user.is_active:
                refresh = RefreshToken.for_user(user)
                try:
                    firebase_title = "Welcome Back!"
                    firebase_message = f"Hello {user.first_name}, you have successfully logged in."
                    firebase_data = {'type': 'login_success'}

                    if user_details.firebase_token:
                        firebase_result = send_firebase_notification(
                            device_token=user_details.firebase_token,
                            title=firebase_title,
                            body=firebase_message,
                            data=firebase_data
                        )
                        logger.info(f"Firebase notification result: {firebase_result}")
                    else:
                        logger.info("Firebase token missing for user.")
                except Exception as e:
                    logger.error(f"Error sending Firebase notification: {e}")

                return Response({
                    'message': message,
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'user_id': user.id
                }, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'User account is inactive'}, status=status.HTTP_403_FORBIDDEN)

        except Exception as e:
            logger.error(f"Error in Apple login: {e}")
            return Response({'error': 'Failed to authenticate with Apple'}, status=status.HTTP_400_BAD_REQUEST)




class Mobilelogin(APIView):
    def get(self, request):
        return Response({'message':'The requested HTTP method is not supported for the requested resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used for this endpoint'},status=status.HTTP_405_METHOD_NOT_ALLOWED)
    def post(self, request):
        data = request.data
        serializer = MobileloginSerializer(data=data)
        if serializer.is_valid(raise_exception=True):
            mobile_number = serializer.data.get('mobile_number')
            user_name = str(uuid.uuid4())
            is_vendor = False
            user = User.objects.create_user(username=user_name, is_vendor=is_vendor,is_deleted=False)
            user.set_unusable_password()
            user.is_active = False
            user.save()
            created = Userdetails.objects.create(user=user,contact_number = mobile_number)
            if created:
                otp = otp_generator()
                message = send_sms_otp(mobile_number,otp)
                if message:
                    Storeotp.objects.create(user=user, otp=otp, catogory = 'mobile_otp')
                    return Response({'message': 'OTP sms sent successfully','username':user.username}, status=status.HTTP_200_OK)
                return Response({'message': 'OTP sms not sent. Something went wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({'message': 'User is not registered'}, status=status.HTTP_400_BAD_REQUEST)
        
class Verifymobileotp(APIView):
    def get(self, request, username):
        return Response({'message':'The requested HTTP method is not supported for the requested resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used for this endpoint'},status=status.HTTP_405_METHOD_NOT_ALLOWED)
    def post(self, request, username):
        data = request.data
        serializer = VerifymobileotpSerializer(data=data)
        if serializer.is_valid(raise_exception=True):
            otp = serializer.data.get('otp')
            if not otp:
                return Response({'message':'otp is not entred'},status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.filter(username=username,is_deleted=False).first()
            if user.is_active is False:
                get_otp = Storeotp.objects.get(user = user, catogory='mobile_otp')
                if otp == get_otp.otp:
                    user.is_active = True
                    user.save()
                    if user.is_active is True:
                        refresh = RefreshToken.for_user(user)
                        return Response({'message':'otp has been verified and loggedin','refresh': str(refresh),
                        'access': str(refresh.access_token),'user_id':user.id},status=status.HTTP_200_OK)
                return Response({'message':"otp is not matching. Kindly check"},status=status.HTTP_401_UNAUTHORIZED)
            return Response({'message':'email is already verified'},status=status.HTTP_302_FOUND)
        return Response({'message':'Some thing went wrong'},status=status.HTTP_400_BAD_REQUEST)
                    
class Resendmobileotp(APIView):
    def get(self, request, username):
        return Response({'message':'The requested HTTP method is not supported for the requested resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used for this endpoint'},status=status.HTTP_405_METHOD_NOT_ALLOWED)
    def post(self, request, username): 
        user_name = username       
        get_user = User.objects.filter(username = user_name,is_deleted=False).first()
        if get_user.is_active is False:
            get_userdetail = Userdetails.objects.filter(user=get_user).first()
            get_mobilenumber = get_userdetail.contact_number
            otp = otp_generator()
            message = send_sms_otp(get_mobilenumber,otp)
            if message:
                update_otp = Storeotp.objects.get(user = get_user, catogory='mobile_otp')
                update_otp.otp = otp
                update_otp.save()
                return Response({'message': 'OTP sms resent successfully','username':get_user.username}, status=status.HTTP_200_OK)
            return Response({'message': 'OTP sms not sent. Something went wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'message':'mobile number is already verified and active'},status=status.HTTP_302_FOUND)

class CheckAuthentication(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'message': 'User is authenticated', 'user_id': request.user.id}, status=status.HTTP_200_OK)
        


class categoryList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            category = Categories.CATEGORIES
            
            if not category:
                return Response({'message': "Categories data is not available"}, status=status.HTTP_404_NOT_FOUND)
            
            categoryList = [category_val for category_val, category_lab in category]
            
            context = {
                'data': categoryList,
                'message': "Data fetched successfully"
            }
            return Response(context, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({'message': 'Failed to fetch categories data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    

class HotelSearch(APIView):
    permission_classes = [AllowAny]

    def get(self, request, input_string):
        logger.warning("Invalid HTTP method (GET) used on the HotelSearch endpoint.")
        return Response(
            {'message': 'The requested HTTP method is not supported for the requested resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used for this endpoint'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def post(self, request, input_string):
        available_hotels = []
        data = request.data
        logger.info("POST request received on HotelSearch with input_string: %s", input_string)
        language = request.GET.get('lang', 'en')

        # Validate input data
        try:
            serializer = HotelSearchSerializer(data=data)
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error("Validation error: %s", str(e))
            message = "Invalid input data" if language == "en" else "بيانات الإدخال غير صالحة"
            return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)

        
        # Category fetching and creation
        if not input_string:
            logger.error("Input string for category is missing.")
            message = "Category input is required" if language == "en" else "إدخال الفئة مطلوب"
            return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)


        try:
            category_id = Categories.objects.get(category=input_string)
            logger.info("Category %s found in database.", input_string)
        except Categories.DoesNotExist:
            logger.info("Category %s not found. Creating new entry.", input_string)
            Categories.objects.create(category=input_string)
        except DatabaseError as e:
            logger.error("Database error while fetching/creating category: %s", str(e))
            message = "Database error occurred" if language == "en" else "حدث خطأ في قاعدة البيانات"
            return Response({'message': message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        # Extract data from serializer
        logger.info(serializer.data)

        lat= serializer.data.get('latitude')
        long = serializer.data.get('longitude')
        city_name = serializer.data.get('city_name', '').strip()
        hotel_name = serializer.data.get('hotel_name', '').strip()
        checkin_date = serializer.data.get('checkin_date')
        checkout_date = serializer.data.get('checkout_date')
        rooms = serializer.data.get('room', 0)
        members = serializer.data.get('members', 0)
        sort = serializer.data.get('sorted', '')
        filter = serializer.data.get('filter', {})

        # Check if city_name or hotel_name is provided
        if not lat and not hotel_name and not long and not city_name :
            logger.warning("Both lat/long and hotel_name are empty.")
            message = "Hotel or city should not be empty" if language == "en" else "يجب ألا يكون الفندق أو المدينة فارغين"
            return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)


        formated_hotel_name = hotel_name.replace(' ', '')
        is_generic_hotel_word = hotel_name in ['hotel', 'the hotel', 'الفندق', 'فندق']
        # Fetch hotels based on city or hotel name
        try:
            ammenities = Amenity.objects.filter(status=True)
            all_amenities = set(amenity.amenity_name for amenity in ammenities)
            if lat and long:
                nearby_hotels = get_nearby_hotels(lat, long)
                if nearby_hotels:
                    hotel_ids = [hotel.id for hotel, _ in nearby_hotels]
                    preserved_order = Case(*[When(id=pk, then=pos) for pos, pk in enumerate(hotel_ids)])
                    hotel_obj = Hotel.objects.filter(id__in=hotel_ids).order_by(preserved_order)
                    logger.info(f"Hotels after applying distance-based sorting: {[hotel.name for hotel in hotel_obj]}")
                else:
                    hotel_obj=None
                    logger.warning("No hotels found for city ")
                    message = "Hotel or city not available" if language == "en" else "الفندق أو المدينة غير متاحين"
                    return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)
            if not lat and not long:
                if hotel_name:
                    lang=detect_lang(hotel_name)
                    if lang == 'en':
                        filter_conditions = Q(name__icontains=hotel_name) | Q(name__icontains=formated_hotel_name)
                    else:
                        filter_conditions = Q(name_arabic__icontains=hotel_name) | Q(name_arabic__icontains=formated_hotel_name)
                if city_name:
                    logger.info(f"Filtering by city: {city_name}")
                    lang=detect_lang(city_name)
                    if lang == 'en':
                        filter_conditions = Q(city__name__iexact=city_name)
                    else:
                        filter_conditions= Q(city__arabic_name__iexact=city_name)
                if is_generic_hotel_word:
                    filter_conditions |= Q(name__icontains='hotel') | Q(name_arabic__icontains='فندق')


                # Final query with necessary filters
                hotel_obj = Hotel.objects.filter(
                    filter_conditions,
                    approval_status__iexact="approved",
                    post_approval=True,
                    date_of_expiry__gt=date.today()
                )
            
                logger.info("Filtered hotel objects count: %d", hotel_obj.count())
        except DatabaseError as e:
            logger.error("Database error while retrieving hotels: %s", str(e))
            message = "Database error occurred" if language == "en" else "حدث خطأ في قاعدة البيانات"
            return Response({'message': message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        # If no hotels found, return early
        if not hotel_obj.exists():
            logger.warning("No hotels found for city or hotel name")
            message = "Hotel or city not available" if language == "en" else "الفندق أو المدينة غير متاحين"
            return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)


        # Hotel availability and room matching
        if input_string == "HOTEL":
            if checkin_date is None or checkout_date is None:
                logger.error("Checkin or checkout date is missing.")
                message = "Check-in and check-out dates are required." if language == "en" else "تاريخ تسجيل الوصول وتاريخ تسجيل المغادرة مطلوبان."
                return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)

            
            try:
                logger.info(f"Hotels objects before available room --- {hotel_obj}")

                for hotel in hotel_obj:
                    available_rooms = get_available_rooms(
                        hotel=hotel,
                        checkin_date=checkin_date,
                        checkout_date=checkout_date,
                        members=members,
                        rooms_required=rooms
                    )
                    logger.info(f"Available rooms for hotel {hotel.id}: {available_rooms}")

                    # Check if enough rooms are available
                    if len(available_rooms) >=1:
                        available_hotels.append(hotel)
                        logger.info(f"Hotel {hotel.id} has enough rooms available and is added to the results.")
                    
                    logger.info(f"Hotel {hotel.id}: Matched rooms {len(available_rooms)}, Required rooms {rooms}")
            except Exception as e:
                logger.error("Error in room matching logic: %s", str(e))
                message = "Room matching error occurred" if language == "en" else "حدث خطأ في مطابقة الغرفة"
                return Response({'message': message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


            # Filter available hotels based on provided filters
            if available_hotels:
                try:
                    if filter.get('hotelRatings'):
                        rating_values = [rating.split()[0] for rating in filter['hotelRatings']]
                        available_hotels = [hotel for hotel in available_hotels if hotel.hotel_rating in rating_values]

                    if filter.get('guestRatings'):
                        guest_rating_values = [float(rating) for rating in filter.get('guestRatings')]
                        available_hotels = [
                            hotel for hotel in available_hotels
                            if RecentReview.objects.filter(hotel=hotel, rating__in=guest_rating_values).exists()
                        ]

                    if filter.get('propertyAmenities'):
                        amenities_filter = [amenity.capitalize() for amenity in filter['propertyAmenities']]
                        available_hotels = [
                            hotel for hotel in available_hotels
                            if all(amenity in [a.amenity_name.capitalize() for a in hotel.amenities.all()] for amenity in amenities_filter)
                        ]
                except Exception as e:
                    logger.error("Error in filtering logic: %s", str(e))
                    message = "Filtering error occurred" if language == "en" else "حدث خطأ في التصفية"
                    return Response({'message': message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


                # Session data saving
                try:
                    request.session['checkout_date'] = checkout_date
                    request.session['checkin_date'] = checkin_date
                    request.session['rooms'] = rooms
                    request.session['members'] = members
                    request.session.save()
                except Exception as e:
                    logger.error("Failed to save session data: %s", str(e))
                    message = "Failed to save session data" if language == "en" else "فشل في حفظ بيانات الجلسة"
                    return Response({'message': message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


                # Final hotel data processing and sorting
                try:
                    if language == "en":
                        logger.info("Processing available hotels before serializer.")
                        print(f"\n\n\n{available_hotels}\n\n\n")
                        hotel_data = HotelSerializer(available_hotels, many=True, context={"request": request}).data
                    else:
                        hotel_data = HotelArabSerializer(available_hotels, many=True, context={"request": request}).data
                    
                    # Sorting
                    try:
                        if sort == 'PriceLowToHigh':
                            hotel_data = sorted(hotel_data, key=lambda x: x['price_per_night'])
                        elif sort == 'PriceHighToLow':
                            hotel_data = sorted(hotel_data, key=lambda x: x['price_per_night'], reverse=True)
                        elif sort == "Hotelstarrating":
                            hotel_data = sorted(hotel_data, key=lambda x: x['hotel_rating'], reverse=True)
                        logger.info(f"\n\n\n\n\n\n\n ========= {hotel_data} ========= \n\n\n\n\n\n\n")
                    except Exception as e:
                        logger.error("Error in sorting logic: %s", str(e))
                        message = "Sorting error occurred" if language == "en" else "حدث خطأ في الفرز"
                        return Response({'message': message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


                    # Price range filtering
                    try:
                        price_range = serializer.data.get('priceRange', [])
                        if price_range:
                            min_price, max_price = map(Decimal, price_range)
                            hotel_data = [hotel for hotel in hotel_data if min_price <= Decimal(hotel['price_per_night'][0]) <= max_price]
                    except Exception as e:
                        logger.error("Invalid price range: %s", str(e))
                        message = "Invalid price range" if language == "en" else "نطاق السعر غير صالح"
                        return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)


                    # Price per night handling
                    for hotel in hotel_data:
                        logger.info(f"\n\n\n\n\n\n\n ========= hotel{hotel} ========= \n\n\n\n\n\n\n")
                        price_per_night = hotel.get('price_per_night')
                        logger.info(f"\n\n\n\n\n\n\n ========= price_per_night{price_per_night} ========= \n\n\n\n\n\n\n")
                        if isinstance(price_per_night, list) and price_per_night:
                            hotel['price_per_night'] = min(price_per_night)
                        elif isinstance(price_per_night, Decimal):
                            hotel['price_per_night'] = float(price_per_night)
                        logger.info(f"\n\n\n\n\n\n\n ========= hotel['price_per_night']{hotel['price_per_night']} ========= \n\n\n\n\n\n\n")
                except Exception as e:
                    logger.error("Error during final data processing: %s", str(e))
                    message = "Data processing error occurred" if language == "en" else "حدث خطأ في معالجة البيانات"
                    return Response({'message': message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


                return Response(hotel_data, status=status.HTTP_200_OK)

            logger.info("No hotels found matching the criteria.")
            message = "No hotels available for the selected dates" if language == "en" else "لا توجد فنادق متاحة للتواريخ المحددة"
            return Response({'message': message}, status=status.HTTP_404_NOT_FOUND)


        logger.error("Invalid input_string received: %s", input_string)
        message = "Invalid input string" if language == "en" else "سلسلة إدخال غير صالحة"
        return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)



class Propertydetail(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        logger.warning("POST method not allowed on Propertydetail endpoint.")
        return Response(
            {
                'message': 'The requested HTTP method is not supported for the requested resource. '
                           'Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) '
                           'is being used for this endpoint.'
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def get(self, request, pk):
        try:
            logger.info(f"Fetching hotel with ID {pk}")
            hotel_obj = get_object_or_404(
                Hotel,
                pk=pk,
                approval_status__iexact="approved",
                date_of_expiry__gt=date.today()
            )
            logger.info("Hotel found: %s", hotel_obj.name)

            # Calculate minimum room price with commission
            min_price = None

            # Get the active room with the lowest price based on current_price
            room = hotel_obj.room_managements.filter(status='active').first()  # Assuming sorting by current_price dynamically

            if room:
                # Use the dynamic current_price property
                current_price = room.current_price

                # Get the relevant commission slab for the current price
                commission_slab = CommissionSlab.objects.filter(
                    from_amount__lte=current_price,
                    to_amount__gte=current_price,
                    status='active'
                ).first()

                # Add commission to the current price
                if commission_slab:
                    min_price = current_price + commission_slab.commission_amount
                else:
                    min_price = current_price  # Fallback if no commission slab found

            
            # Retrieve check-in and check-out dates from query params or session
            checkin_date = request.query_params.get('checkin_date') or request.session.get('checkin_date')
            logger.info( checkin_date )
            checkout_date = request.query_params.get('checkout_date') or request.session.get('checkout_date')
            members = request.query_params.get('members') or request.session.get('members')
            room_count = request.query_params.get('room') or request.session.get('room')
            if not all([checkout_date, checkin_date, members, room_count]):
                logger.warning(
                    "Incomplete session data: checkin_date=%s, checkout_date=%s, members=%s, room=%s",
                    checkin_date, checkout_date, members, room_count
                )
            if checkin_date and checkout_date:
                checkin_date_obj = datetime.strptime(checkin_date, '%Y-%m-%d').date()
                checkout_date_obj = datetime.strptime(checkout_date, '%Y-%m-%d').date()
                price_result = calculate_minimum_hotel_price(
                hotel_id=hotel_obj.id,
                calculation_logic="average_price",
                checkin_date=checkin_date_obj,
                checkout_date=checkout_date_obj,
                members=members,
                rooms_required= room_count,
            )

            min_price = price_result.get("calculated_price")
            hotel_details = PropertyDetails(hotel_obj, context={"request": request})
            logger.info(f"Hotel details fetched: {hotel_details.data}")
            # discounted_price_hotel = get_discounted_price_for_property(hotel_obj.id, "hotel")
            # print(f"DISCOUNT ---- {discounted_price_hotel}")
            # if discounted_price_hotel is not None:
            #     min_price = discounted_price_hotel

            context = {
                'data': hotel_details.data,
                'checkin_date': checkin_date,
                'checkout_date': checkout_date,
                'members': members,
                'room': room_count,
                'message': 'Data fetched',
                'price': min_price,
                'offers': [],
                'promo_code': []
            }
            current_date = now().date()
            logger.info(f"Current date: {current_date}")

            # Fetch promo codes
            promo_code_promotions = Promotion.objects.filter(
                Q(hotel=hotel_obj) | Q(multiple_hotels__in=[hotel_obj]),
                promo_code__isnull=False,
                start_date__lte=current_date,
                end_date__gte=current_date,
                status="active"
            )
            logger.info(f"Promo code promotions count: {promo_code_promotions.count()}")

            context['promo_code'] = [
                {
                    'promo_id': code.id,
                    'title': code.title,
                    'description': code.description,
                    'discount_percentage': code.discount_percentage,
                    "discount_value": code.discount_value,
                    'code': code.promo_code,
                    'start_date': code.start_date,
                    'end_date': code.end_date,
                    'status': code.status
                }
                for code in promo_code_promotions
            ]

            # Fetch general offers
            promotions = Promotion.objects.filter(
                Q(hotel=hotel_obj) | Q(multiple_hotels__in=[hotel_obj]),
                promo_code__isnull=True,
                start_date__lte=current_date,
                end_date__gte=current_date,
                status="active"
            )
            logger.info(f"General promotions count: {promotions.count()}")

            context['offers'] = [
                {
                    'promo_id': promo.id,
                    'title': promo.title,
                    'description': promo.description,
                    'promotion_type': promo.promotion_type,
                    'discount_percentage': promo.discount_percentage,
                    "discount_value": promo.discount_value,
                    'start_date': promo.start_date,
                    'end_date': promo.end_date,
                    'status': promo.status
                }
                for promo in promotions
            ]

            logger.info(f"\n\n\n\n\nReturning hotel details with promotions. {context} \n\n\n\n\n\n")
            return Response(context, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching property details: {e}")
            return Response({'error': 'Error fetching property details'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RoomListing(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        logger.info("Entered in the RoomListing GET View")
        
        # Fetch session data
        checkout_date = request.query_params.get('checkout_date')
        print(checkout_date)
        checkin_date = request.query_params.get('checkin_date')
        print(checkin_date)
        if checkout_date:
            checkout_date = checkout_date.strip()
        if checkin_date:
            checkin_date = checkin_date.strip()
        members = request.query_params.get('members')
        rooms = request.query_params.get('rooms')
        logger.info(f"\n\n\ncheckout_date: {checkout_date} ------> checkin_date: {checkin_date} -----> members: {members} ----->  rooms : {rooms} \n\n\n")
        if checkin_date is None or checkout_date is None or members is None or rooms is None:
            logger.info("Missing required session data.")
            return Response({'error': 'Missing required session data.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            hotel = Hotel.objects.get(id=pk, date_of_expiry__gt = date.today(), post_approval=True, approval_status="approved")  # Assuming hotel is fetched using its ID
            print(f"hotel retrived is -- {hotel}")
            try:
                available_rooms = get_available_rooms(
                    hotel=hotel,
                    checkin_date=checkin_date,
                    checkout_date=checkout_date,
                    members=members,
                    rooms_required=rooms
                )
                
                room_list = list( available_rooms)
                logger.info(f"room list ---{room_list}")
                logger.info(f"Available rooms for hotel {hotel.id}: {[room.id for room in room_list]}")

                # Return error if no rooms are found
                if not room_list:
                    return Response({'message': 'No rooms available for the selected criteria'}, status=status.HTTP_404_NOT_FOUND)
                serializer_context = {
                        'request': request,  # Ensure request is passed here
                        'checkin_date': checkin_date,
                        'checkout_date': checkout_date,
                        'members': members,
                        'rooms': rooms
                    }
                # Serialize room data
                room_serializer = RoomlistingSerializer(room_list, many=True, context=serializer_context)
                room_data = []
                num_days = (datetime.strptime(checkout_date, "%Y-%m-%d") - datetime.strptime(checkin_date, "%Y-%m-%d")).days

                for room in room_serializer.data:
                    room_price = room.get('room_price', 0) or 0
                    breakfast_price = room.get('breakfast_price', 0) or 0
                    lunch_price = room.get('lunch_price', 0) or 0
                    dinner_price = room.get('dinner_price', 0) or 0
                    total_meal_price = (breakfast_price + lunch_price + dinner_price) * num_days
                    total_amount = room_price + total_meal_price
                    room['total_amount'] = total_amount
                    room_data.append(room)

                # Fetch room type data
                roomtype_queryset = Roomtype.objects.all().values('id', 'room_types')
                roomtype_serializer = RoomtypeSerializer(roomtype_queryset, many=True)


                context = {
                    'room_data': room_data,
                    'roomtype_data': roomtype_serializer.data,
                    'message': 'Room data fetched successfully'
                }
                return Response(context, status=status.HTTP_200_OK)

            except Roomtype.DoesNotExist:
                return Response({'message': 'Room type data not found'}, status=status.HTTP_404_NOT_FOUND)
        except Hotel.DoesNotExist:
            logger.info(f"\n\nGiven hotel is not available in room listing api\n\n")
            return Response({'message':'Hotel is not found'},status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.error(f"Error during RoomListing processing: {e}")
            return Response({'message': 'Something went wrong'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        
        
class Test500ErrorView(APIView):
    def get(self, request):
        raise Exception("This is a test for 500 Internal Server Error")
    
    
    
class Getuserdetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.user.id
        # try:

        userid = User.objects.get(id=user_id,is_deleted=False)
        # except User.DoesNotExist:
        #     return Response({'message': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        user_details = Userdetails.objects.filter(user=userid).first()  # Use .first() to avoid empty queryset issues

        if not user_details:
            return Response({'message': 'User details not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            serializer = UserSerializer(user_details)
        except Exception as e:
            print(f"Serialization error: {e}")
            return Response({'message': 'Error serializing user data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        context = {
            'data': serializer.data,
            'message': 'Data fetched successfully'
        }
        return Response(context, status=status.HTTP_200_OK)


        
class BookRoom(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request, id):
        logger.info("GET method not supported on this endpoint.")
        return Response(
            {'message': 'The requested HTTP method is not supported for the requested resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used for this endpoint'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def post(self, request, id):
        logger.info("Entering BookRoom.post function")
        
        user_obj = request.user.id
        logger.info(f"Request User ID: {user_obj}")

        try:
            userid = User.objects.get(id=user_obj,is_deleted=False)
            logger.info(f"User object found: {userid}")
        except User.DoesNotExist:
            logger.error("User does not exist")
            return Response({'error': "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error while fetching user: {str(e)}")
            return Response({'error': "An unexpected error occurred while fetching user"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            hotel = Hotel.objects.get(id=id, approval_status__iexact="approved",date_of_expiry__gt = date.today(),post_approval=True)
            logger.info(f"Hotel object found: {hotel}")
        except Hotel.DoesNotExist:
            logger.error("Hotel does not exist")
            return Response({'error': "Hotel not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error while fetching hotel: {str(e)}")
            return Response({'error': "An unexpected error occurred while fetching hotel"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        data = request.data
        logger.info(f"Request data: {data}")

        for category_obj in hotel.category.all():
            logger.info(f"Checking category: {category_obj.category}")
            if category_obj.category == "HOTEL":
                logger.info("Category is HOTEL")
                try:
                    serializer = RoombookingSerializer(data=data)
                    if serializer.is_valid():
                        validated_data = serializer.validated_data
                        first_name = validated_data.get('booking_fname')
                        last_name = validated_data.get('booking_lname')
                        email = validated_data.get('booking_email')
                        mobile_no = validated_data.get('booking_mobilenumber')
                        is_my_self = validated_data.get('is_my_self')
                        roomdetail = validated_data.get('room')
                        discount_price = validated_data.get('discount_price')
                        service_fee = validated_data.get('service_fee')
                        total_amount = validated_data.get('total_amount')
                        checkin_date = validated_data.get('checkin_date')
                        checkout_date = validated_data.get('checkout_date')
                        members = validated_data.get('number_of_guests')
                        rooms_booked = validated_data.get('number_of_booking_rooms')
                        count=validated_data.get('count')
                        promocode = validated_data.get('promocode_applied')
                        discount_percentage_applied = validated_data.get('discount_percentage_applied')
                        adults=validated_data.get('adults')
                        children=validated_data.get('children')
                        tax_and_services=validated_data.get('tax_and_services')
                        meal_tax=validated_data.get('meal_tax')
                        meal_price=validated_data.get('meal_price')

                        check_in_time=hotel.checkin_time
                        check_out_time=hotel.checkout_time
                        print(email,"========emailemail")
                        print(promocode,"========promocodepromocode")
                        logger.info("Booking details validated")

                        if children is None:
                            children=0   

                        email_validator = EmailValidator()
                        try:
                            email_validator(email)
                        except ValidationError as e:
                            logger.info(f"Invalid email format for: {email}, Error: {str(e)}")
                            return Response({"message": f"Invalid email format for: {email}"})
                        
                        
                        if checkin_date < date.today():
                            return Response({"message": "Check-in date cannot be in the past."}, status=status.HTTP_406_NOT_ACCEPTABLE)

                        if checkout_date <= checkin_date:
                            return Response({"message": "Check-out date must be after the check-in date."}, status=status.HTTP_406_NOT_ACCEPTABLE)

                        if members is None or members<=0 :
                            logger.error("No: of guests found to be none or less than or equal to zero")
                            return Response({"message": "The number of members must be greater than zero."}, status=status.HTTP_406_NOT_ACCEPTABLE)
                        elif adults is None or adults<=0 :
                            logger.error("No: of adults found to be none or less than or equal to zero")
                            return Response({"message": "The number of adults must be greater than zero."}, status=status.HTTP_406_NOT_ACCEPTABLE)
                        elif children < 0:
                            logger.error("No: of children found to be less than  zero")
                            return Response({"message": "The number of children  must be greater than equal to zero."}, status=status.HTTP_406_NOT_ACCEPTABLE)
                        if adults:
                            if adults and members:
                                if members != int(adults)+int(children):
                                    logger.error("The total number of guests is not equal to the no: of childrens and no: of adults ")
                                    return Response({"message": "The total number of guests must equal to the sum of adults and children."}, status=status.HTTP_406_NOT_ACCEPTABLE)                              
                        else:
                            return Response({"message": "Number of adults needed."}, status=status.HTTP_406_NOT_ACCEPTABLE)                              

                        try:
                            parsed_number = phonenumbers.parse(mobile_no, None)
                            print(parsed_number)
                            if not phonenumbers.is_valid_number(parsed_number):
                                return Response({"message": "Invalid phone number."},status=status.HTTP_406_NOT_ACCEPTABLE)
                        except phonenumbers.NumberParseException:
                            return Response({"message": "Invalid phone number format."},status=status.HTTP_406_NOT_ACCEPTABLE)
                        
                        if not roomdetail :
                            logger.error("Room ID or price is missing")
                            return Response({'error': "Room ID and price not given or passed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                        try:
                            user_details = Userdetails.objects.get(user=userid)
                            logger.info(f"User details object found: {user_details}")
                        except Userdetails.DoesNotExist:
                            logger.error("User details not found")
                            return Response({'error': "User details not found"}, status=status.HTTP_404_NOT_FOUND)
                        except Exception as e:
                            logger.error(f"Unexpected error while fetching user details: {str(e)}")
                            return Response({'error': "An unexpected error occurred while fetching user details"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                        if int(rooms_booked)==int(count):
                            rooms = get_available_rooms(hotel, checkin_date, checkout_date, members,  rooms_booked, status="active")
                            if rooms:   
                                try:
                                    booking = Booking.objects.create(
                                        user=user_details, hotel=hotel, booking_fname=first_name, booking_lname=last_name,
                                        booking_email=email, booking_mobilenumber=mobile_no, checkin_date=checkin_date,
                                        checkout_date=checkout_date, booked_price=total_amount, discount_price=discount_price,
                                        service_fee=service_fee, number_of_guests=members, number_of_booking_rooms=rooms_booked,
                                        is_my_self=is_my_self, promocode_applied=promocode, discount_percentage_applied=discount_percentage_applied,adults=adults,children=children,
                                        check_in_time=check_in_time,check_out_time=check_out_time,tax_and_services=tax_and_services,meal_price=meal_price,meal_tax=meal_tax
                                    )
                                    logger.info(f"Booking object created: {booking}")
                                except IntegrityError as e:
                                    logger.error(f"Integrity error while creating booking: {str(e)}")
                                    return Response({'error': "Booking creation failed due to integrity error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                except Exception as e:
                                    logger.error(f"Unexpected error while creating booking: {str(e)}")
                                    return Response({'error': "An unexpected error occurred while creating booking"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                
                                if booking:
                                    logger.info("Processing rooms for booking")
                                    try:
                                        for room_item in roomdetail:
                                            print(f"\n\n\n\n\n {room_item} \n\n\n\n")
                                            room_obj = RoomManagement.objects.filter(id=room_item.get('room_id'), hotel=hotel)
                                            logger.info(f"Room objects found: {room_obj}")

                                            if not room_obj:
                                                logger.error("Room is not available")
                                                booking.delete()
                                                return Response({'message': "Room is not available"}, status=status.HTTP_404_NOT_FOUND)
                                            room_availability=Check_current_room_availability(room_obj,checkin_date,checkout_date,rooms_booked)
                                            if room_availability:
                                                for room in room_obj:
                                                    print(f"\n\n\n\n\n {room} \n\n\n\n")
                                                    Meal_id=room_item.get('meal_id')
                                                    print(room_item)
                                                    logger.info(Meal_id)
                                                    if Meal_id == 0:
                                                        get_meal_id=MealPrice.objects.filter(meal_type='no meals',hotel=hotel).first()
                                                    else:
                                                        get_meal_id=MealPrice.objects.filter(id=Meal_id).first()
                                                    logger.info(f"Meal id --- {get_meal_id}")
                                                    add_rooms = Bookedrooms.objects.create(
                                                        booking=booking, room=room, booked_room_price=room_item.get('price'),
                                                        meal_type_id=get_meal_id,no_of_rooms_booked=rooms_booked
                                                    )
                                                    add_rooms.room.availability = False
                                                    add_rooms.room.save()
                                                    add_rooms.status = "Confirmed"
                                                    add_rooms.save()
                                                    booking.booking_id = f"BKG{booking.id}"
                                                    booking.save()
                                                    logger.info(f"Room booking saved: {add_rooms}")

                                                    # Generate and save the QR code, then update the booking's qr_code_url
                                                    qr_url = generate_qr_code(booking.id, booking.token)
                                                    booking.qr_code_url = qr_url
                                                    booking.save()                                        
                                                    logger.info(f"QR code generated and saved for booking: {booking.id}")
                                                    try:
                                                        logger.info(f"Preparing data to send to the aggregator for booking ID: {booking.id}")
                                                        notify_booking_aggregator(booking,"hotel")
                                                        logger.info(f"Successfully sent data to the aggregator for booking ID: {booking.id}")
                                                    except Exception as e:
                                                        logger.error(f"Error sending data to the aggregator for booking ID: {booking.id} - {str(e)}", exc_info=True)
                                                return Response({'message':f"Booking created successfully",'id':booking.id}, status=status.HTTP_201_CREATED)
                                            else:
                                                booking.delete()
                                                logger.error("selected room is not available for this moment")
                                                return Response({'message': "Sorry Room is not available at this moment"}, status=status.HTTP_404_NOT_FOUND)
                                    except Exception as e:
                                        logger.error(f"Unexpected error while processing rooms: {str(e)}")
                                        booking.delete()
                                        return Response({'message': "An unexpected error occurred while processing rooms"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                            else:
                                logger.error(f"No rooms are available for booking for this date")
                                return Response({'message': "Sorry rooms are not available for this moment"}, status=status.HTTP_404_NOT_FOUND)
                        else:
                            logger.error(f"The no: of booking rooms and count should be same")
                            return Response({'message': "Error in the no of booked rooms"}, status=status.HTTP_404_NOT_FOUND)

                    else:
                        logger.error(f"Serializer errors: {serializer.errors}")
                        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                except Exception as e:
                    logger.error(f"Unexpected error during booking process: {str(e)}")
                    return Response({'message': "An unexpected error occurred during the booking process"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            elif category_obj.category == "CHALET":
                logger.info("Category is CHALET")
                # Add further handling for CHALET category if required
                pass

class CreatePayment(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):
        logger.info("Entering Walletpayment post function")
        user_obj = request.user.id
        logger.info(f"Request User ID: {user_obj}")
        id = kwargs.get('id')
        language = request.GET.get('lang', 'en')
        try:
            user = User.objects.get(id=user_obj,is_deleted=False)
            user_details = Userdetails.objects.get(user=user)
        except User.DoesNotExist:
            logger.error("User does not exist")
            if language == "en":
                message = "User not found"
            else:
                message = "لم يتم العثور على المستخدم"
            return Response({'error': message}, status=status.HTTP_404_NOT_FOUND)
        except Userdetails.DoesNotExist:
            logger.error("User details not found")
            if language == "en":
                message = "User details not found"
            else:
                message = "لم يتم العثور على تفاصيل المستخدم"
            return Response({'error': message}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error while fetching user details: {str(e)}")
            if language == "en":
                message = "An unexpected error occurred while fetching user details"
            else:
                message = "حدث خطأ غير متوقع أثناء جلب تفاصيل المستخدم"
            return Response({'error': message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        print(f"ID is ------------- {id}")
        data = request.data
        logger.info(f"Request data: {data}")
        serializer = WalletPaymentSerializer(data=data)

        if not serializer.is_valid():
            return Response({'message': serializer.errors}, status=status.HTTP_406_NOT_ACCEPTABLE)

        validated_data = serializer.validated_data
        total_amount = validated_data.get('total_amount')
        payment_type = validated_data.get('payment_type')
        category = validated_data.get('category')

        if payment_type == "Wallet":
            return self.handle_wallet_payment(user_details, category, id, total_amount, request)
        elif payment_type == "Online":
            return self.handle_online_payment(request, data, id, category)
        elif payment_type == "Debit Card":
            logger.info(f"Currently we dont have Debit Card Option.")
            if language == "en":
                message = 'Currently we dont have Debit Card Option.'
            else:
                message = "حاليًا ليس لدينا خيار بطاقة الخصم."
            return Response({'message': message}, status=status.HTTP_404_NOT_FOUND)
        elif payment_type == "Cash":
            return self.handle_cash_payment(user_details, category, id, total_amount, request)
        else:
            if language == "en":
                message = 'Invalid payment type'
            else:
                message = "نوع الدفع غير صالح."
            return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)

    def handle_wallet_payment(self, user_details, category, id, total_amount, request):
        language = request.GET.get('lang', 'en')
        if category == "Hotel":
            return self.process_hotel_booking(user_details, id, total_amount, request, "Wallet")
        elif category == "Chalet":
            return self.process_chalet_booking(user_details, id, total_amount, request, "Wallet")
        else:
            logger.error("The category should be either Hotel or Chalet")
            if language == "en":
                message = 'Please add key as category. The category value should be either Hotel or Chalet.'
            else:
                message = "يرجى إضافة المفتاح كفئة. يجب أن تكون قيمة الفئة إما فندقًا أو شاليهًا."
            return Response({'message': message}, status=status.HTTP_404_NOT_FOUND)

    def handle_cash_payment(self, user_details, category, id, total_amount, request):
        language = request.GET.get('lang', 'en')
        if category == "Hotel":
            return self.process_hotel_booking(user_details, id, total_amount, request, "Cash")
        elif category == "Chalet":
            return self.process_chalet_booking(user_details, id, total_amount, request, "Cash")
        else:
            logger.error("The category should be either Hotel or Chalet")
            if language == "en":
                message = 'Please add key as category. The category value should be either Hotel or Chalet.'
            else:
                message = "يرجى إضافة المفتاح كفئة. يجب أن تكون قيمة الفئة إما فندقًا أو شاليهًا."
            return Response({'message': message}, status=status.HTTP_404_NOT_FOUND)

    def process_hotel_booking(self, user_details, id, total_amount, request, payment_method):
        language = request.GET.get('lang', 'en')
        try:
            booking = Booking.objects.get(id=id)
            transaction_id = booking.transaction.transaction_id if booking.transaction and booking.transaction.transaction_id else "Not available"
            hotel = booking.hotel
            print(f"\n\n\n\n\n\n\n\n {hotel} \n\n\n\n\n\n\n\n")
            payment_details = get_payment_details('hotel', hotel)
            print(f"\n\n\n\n\n\n\n\n   {payment_details} \n\n\n\n\n\n\n\n\n")
            is_valid_payment_method = any(payment_method == category["category"] for category in payment_details)

            if not is_valid_payment_method:
                logger.error("Given payment type or payment method not found")
                if language == "en":
                    message = 'Given payment type or payment method not found'
                else:
                    message = "لم يتم العثور على نوع الدفع أو طريقة الدفع المحددة"
                return Response({'message': message}, status=status.HTTP_404_NOT_FOUND)

            if booking.booked_price != total_amount:
                logger.error("Given total amount have mismatch with the booking amount")
                if language == "en":
                    message = 'Mismatch in the total amount'
                else:
                    message = "عدم تطابق في المبلغ الإجمالي"
                return Response({'message': message}, status=status.HTTP_404_NOT_FOUND)

            if payment_method == "Wallet":
                wallet = Wallet.objects.get(user=user_details, status="active")
                if wallet.balance < total_amount:
                    logger.info("You dont have enough balance for this booking. Kindly keep your wallet amount updated.")
                    if language == "en":
                        message = 'You dont have enough balance for this booking. Kindly keep your wallet amount updated.'
                    else:
                        message = "ليس لديك رصيد كافٍ لهذا الحجز. يرجى تحديث مبلغ محفظتك باستمرار."
                    return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)
                wallet_transaction_id, new_balance = create_wallet_transaction(wallet, "debit", Decimal(total_amount))
                update_transaction_status(transaction_id=transaction_id, transaction_status="completed", payment_type_name="Wallet")
                update_vendor_earnings(transaction_id=transaction_id, card_type="wallet")
                
            elif payment_method == "Cash":
                update_transaction_status(transaction_id=transaction_id, transaction_status="pending", payment_type_name="Cash")
                update_vendor_earnings(transaction_id=transaction_id, card_type="cash")
            else:
                if language == "en":
                    message = 'Invalid payment method'
                else:
                    message = "طريقة الدفع غير صالحة"
                return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)

            self.update_promotion(booking, hotel)
            email_context = self.send_notifications_and_emails(booking, hotel, total_amount, new_balance if payment_method == "Wallet" else None, request, payment_method)
            if language == "en":
                message = 'Payment completed successfully'
            else:
                message = "اكتمل الدفع بنجاح"
            if not email_context:
                logger.info(f"an error occured at sending the email")
                email_context=backup_function_payment(booking,hotel,total_amount)
            return Response({
                'message': message,
                'data': email_context  # Include the email context in the response
            }, status=status.HTTP_200_OK)
           
        except Booking.DoesNotExist:
            logger.error("Booking doesn't found")
            if language == "en":
                message = "Booking doesn't Found"
            else:
                message = "لم يتم العثور على الحجز"
            return Response({'message': message}, status=status.HTTP_404_NOT_FOUND)
        except Wallet.DoesNotExist:
            logger.info("You dont have wallet. Please create a wallet and add money to continue booking or try another payment option")
            if language == "en":
                message = "You dont have wallet. Please create a wallet and add money to continue booking or try another payment option"
            else:
                message = "ليس لديك محفظة. يرجى إنشاء محفظة وإضافة الأموال لمواصلة الحجز أو تجربة خيار دفع آخر"
            return Response({'message': message}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            if language == "en":
                message = "An unexpected error occurred"
            else:
                message = "حدث خطأ غير متوقع"
            return Response({'message': message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    def process_chalet_booking(self, user_details, id, total_amount, request, payment_method):
        language = request.GET.get('lang', 'en')
        try:
            booking = ChaletBooking.objects.get(id=id)
            transaction_id = booking.transaction.transaction_id if booking.transaction and booking.transaction.transaction_id else "Not available"
            chalet = booking.chalet
            payment_details = get_payment_details('chalet', chalet)
            is_valid_payment_method = any(payment_method == category["category"] for category in payment_details)

            if not is_valid_payment_method:
                logger.error("Given payment type or payment method not found")
                if language == "en":
                    message = "Given payment type or payment method not found"
                else:
                    message = "لم يتم العثور على نوع الدفع أو طريقة الدفع المحددة"
                return Response({'message': message}, status=status.HTTP_404_NOT_FOUND)

            if booking.booked_price != total_amount:
                logger.error("Given total amount have mismatch with the booking amount")
                if language == "en":
                    message = "Given total amount have mismatch with the booking amount"
                else:
                    message = "المبلغ الإجمالي المعطى لا يتطابق مع مبلغ الحجز"
                return Response({'message': message}, status=status.HTTP_404_NOT_FOUND)

            if payment_method == "Wallet":
                wallet = Wallet.objects.get(user=user_details, status="active")
                if wallet.balance < total_amount:
                    logger.info("You dont have enough balance for this booking. Kindly keep your wallet amount updated.")
                    if language == "en":
                        message = "You dont have enough balance for this booking. Kindly keep your wallet amount updated."
                    else:
                        message = "ليس لديك رصيد كافٍ لهذا الحجز. يرجى تحديث مبلغ محفظتك باستمرار."
                    return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)
                wallet_transaction_id, new_balance = create_wallet_transaction(wallet, "debit", Decimal(total_amount))
                update_transaction_status(transaction_id=transaction_id, transaction_status="completed", payment_type_name="Wallet")
                update_vendor_earnings(transaction_id=transaction_id, card_type="wallet")
            elif payment_method == "Cash":
                update_transaction_status(transaction_id=transaction_id, transaction_status="pending", payment_type_name="Cash")
                update_vendor_earnings(transaction_id=transaction_id, card_type="Cash")
            else:
                if language == "en":
                    message = "Invalid payment method"
                else:
                    message = "طريقة الدفع غير صالحة"
                return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)

            self.update_promotion(booking, chalet)
            email_context = self.send_notifications_and_emails(booking, chalet, total_amount, new_balance if payment_method == "Wallet" else None, request, payment_method)
            if language == "en":
                message = "Payment completed successfully"
            else:
                message = "اكتمل الدفع بنجاح"
            if not email_context:
                logger.info(f"An error occured at sending the email.--using the backup function")
                email_context=backup_function_payment(booking,chalet,total_amount)
            return Response({
                'message': message,
                'data': email_context  # Include the email context in the response
            }, status=status.HTTP_200_OK)
        except ChaletBooking.DoesNotExist:
            logger.error("Booking doesn't found")
            if language == "en":
                message = 'Booking doesn\'t Found'
            else:
                message = "لم يتم العثور على الحجز"
            return Response({'message': message}, status=status.HTTP_404_NOT_FOUND)
        except Wallet.DoesNotExist:
            logger.info("You dont have wallet. Please create a wallet and add money to continue booking or try another payment option")
            if language == "en":
                message = 'You dont have wallet. Please create a wallet and add money to continue booking or try another payment option'
            else:
                message = "ليس لديك محفظة. يرجى إنشاء محفظة وإضافة الأموال لمواصلة الحجز أو تجربة خيار دفع آخر"
            return Response({'message': message}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            if language == "en":
                message = 'An unexpected error occurred'
            else:
                message = "حدث خطأ غير متوقع"
            return Response({'message': message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    def update_promotion(self, booking, property):
        promocode = booking.promocode_applied
        if promocode:
            promotion = Promotion.objects.filter(**{f'{property.__class__.__name__.lower()}': property}, promo_code=promocode, status="active").first()
            if promotion:
                promotion.max_uses -= 1
                promotion.save()

    def send_notifications_and_emails(self, booking, property, total_amount, new_balance, request, payment_method):
        property_name = property.name
        booking_id = booking.booking_id
        message = f"Your booking has been confirmed for the {property.__class__.__name__.lower()} {property_name}"
        message_arabic = f"تم تأكيد حجزك لـ {property.__class__.__name__.lower()} {property_name}"
        notification_type = "booking_new"
        source = property.__class__.__name__.lower()
        logger.info(f"source----{source}")
        related_booking = booking
        logger.info(f"booking found ---{related_booking}")
        if source == 'chalet':
            try:
                # Attempt to create notification
                create_notification(user=request.user, notification_type=notification_type, message=message, message_arabic=message_arabic, source=source,   chalet_booking=related_booking)
            except Exception as e:
                # Log the error but do not raise it
                logger.error(f"Error creating notification for chalet: {str(e)}")
        elif source == 'hotel':
            try:
                # Attempt to create notification
                create_notification(user=request.user, notification_type=notification_type, message=message, message_arabic=message_arabic, source=source,   related_booking=related_booking)
            except Exception as e:
                # Log the error but do not raise it
                logger.error(f"Error creating notification for hotel: {str(e)}")
        if payment_method == "Wallet":
            message = f"{total_amount} has been deducted from your wallet for your booking in {property_name} of booking id '{booking_id}'. Your new balance is {new_balance}"
            message_arabic = f"{total_amount} تم خصمه من محفظتك لحجزك في {property_name} برقم الحجز '{booking_id}'. رصيدك الجديد هو {new_balance}"
            notification_type = "deduct_money_from_wallet"
            if source == 'chalet':
                try:
                    # Attempt to create notification for wallet deduction
                    create_notification(user=request.user, notification_type=notification_type, message=message, message_arabic=message_arabic, source=source,  chalet_booking=related_booking)
                except Exception as e:
                    # Log the error but do not raise it
                    logger.error(f"Error creating wallet deduction notification for chalet: {str(e)}")
            elif source == 'hotel':
                try:
                    # Attempt to create notification for wallet deduction
                    create_notification(user=request.user, notification_type=notification_type, message=message, message_arabic=message_arabic, source=source,  related_booking=related_booking)
                except Exception as e:
                    # Log the error but do not raise it
                    logger.error(f"Error creating wallet deduction notification for hotel: {str(e)}")
        # Send email (if needed)
        email_context = self.send_confirmation_email(booking, property, total_amount, payment_method)
        return email_context
    def send_confirmation_email(self, booking, property, total_amount, payment_method):
        try:
            subject = f'Your Booking in {property.name.upper()} Confirmed'
            context = {
                'id': booking.id,
                'property_name': property.name.upper(),
                'Booking_Number': booking.booking_id,
                'recipient_name': f"{booking.booking_fname} {booking.booking_lname}",
                'checkin_date': booking.checkin_date,
                'checkout_date': booking.checkout_date,
                'Guests': booking.number_of_guests,
                'transaction_id': booking.transaction.transaction_id if booking.transaction else "N\A" ,
                'total_amount': total_amount,
                'address': property.address,
                'contact_number': booking.booking_mobilenumber,
                'qrcode': booking.qr_code_url,
                'first_name': booking.booking_fname,
                'second_name': booking.booking_lname,
                'email': booking.booking_email,
                'adults': booking.adults,
                'children': booking.children
            }

            html_content = render_to_string(f'chalet_booking_email.html', context)
            text_content = strip_tags(html_content)
            logger.info(f"email of the vendor is ----,{property.vendor.user.email}")
            email = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [booking.booking_email,settings.ADMIN_EMAIL,property.vendor.user.email])
            email.attach_alternative(html_content, "text/html")
            email.send()
            logger.info(f"Confirmation email sent to: {booking.booking_email}")
            return context  # Return the context here
        except Exception as e:
            logger.error(f"Exception occurred in send_confirmation_email function: Exception: {e}")
            return None

    def handle_online_payment(self, request, data,id, category):
        language = request.GET.get('lang', 'en')
        serializer = PaymentDetailsSerializer(data=data)
        if not serializer.is_valid():
            formatted_errors_list = [{'message': value[0]} for key, value in serializer.errors.items()]
            return Response(formatted_errors_list, status=status.HTTP_400_BAD_REQUEST)
        booking = Booking.objects.get(id=id) if category == "Hotel" else ChaletBooking.objects.get(id=id)
        transaction_id = booking.transaction.transaction_id if booking.transaction and booking.transaction.transaction_id else "Not available"
        validated_data = serializer.validated_data
        amount = validated_data.get('amount')
        first_name = validated_data.get('first_name')
        last_name = validated_data.get('last_name')
        email = validated_data.get('email')
        phone_number = validated_data.get('phone_number')

        track_id = generate_track_id()
        domain = request.build_absolute_uri("/")
        trandata_to_encrypt = [{
            "amt": str(amount),
            "action": "1",
            "password": settings.NBO_TRANSPORTAL_PASSWORD,
            "id": settings.NBO_TRANSPORTAL_ID,
            "langid": "en",
            "currencycode": "512",
            "trackId": f"{track_id}",
            "udf5": "UDF5",
            "udf3": "UDF3",
            "udf4": "UDF4",
            "udf1": str(id),
            "udf2": transaction_id,
            "responseURL": f"{domain}common/payment-status?status=&lang={language}",
            "errorURL": settings.NBO_ERROR_URL,
            "billingInfo": {
                "firstName": first_name,
                "lastName": last_name,
                "phoneNumber": phone_number,
                "email": email
            }
        }]

        try:
            payment_obj = payment_gateway(request, trandata_to_encrypt)
            logger.info(f"\n\n\n\n\n\n  payment_obj{payment_obj}\n\n\n\n\n\n")
            if payment_obj:
                payment_id = payment_obj[0]['result'].split(":")[0]
                payment_url = payment_obj[0]['result'].split(":", 1)[1]
                payment_url_id = f"{payment_url}?PaymentID={payment_id}"
                logger.info(f"payment_url_id: {payment_url_id}")
                return Response({'payment_url': payment_url_id}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "Payment Gateway Connection issue"}, status=status.HTTP_400_BAD_REQUEST)  
        except Exception as e:
            logger.info(f"Exception occurred in getting payment_obj. Exception {e}")
            if language == "en":
                message = f"Exception occurred in getting payment_obj. Exception {e}"
            else:
                message = "حدث استثناء في الحصول على كائن الدفع"
            return Response({'message': message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class Bookedlist(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    def post(self, request):
        return Response({'message':'The requested HTTP method is not supported for the requested resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used for this endpoint'},status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def get(self, request):
        try:
            user = request.user
            get_user = User.objects.get(id=user.id,is_deleted=False)
            get_userdetail = get_object_or_404(Userdetails, user=get_user)

            todays_date = datetime.today().strftime('%Y-%m-%d')

            # Upcoming bookings (where checkin_date is today or in the future)
            upcoming_booking = Booking.objects.filter(
                Q(user=get_userdetail) & 
                Q(checkout_date__gte=todays_date) & 
                Q(status__in=["pending","booked","confirmed","check-in"])
            ).order_by('-created_date')
            
            logger.info(f"\n\nupcoming_booking: {upcoming_booking}\n\n")

            completed_booking = Booking.objects.filter(
                Q(user=get_userdetail) & 
                Q(checkout_date__lte=todays_date) & 
                Q(status__iexact="completed")
            ).order_by('-checkout_date')
            logger.info(f"\n\ncompleted_booking: {completed_booking}\n\n")
            # Canceled bookings (regardless of checkin_date)
            canceled_booking = Booking.objects.filter(
                Q(user=get_userdetail) & 
                Q(status__in=["cancelled","rejected","expired"])
            ).order_by('-checkout_date')
            logger.info(f"\n\ncanceled_booking: {canceled_booking}\n\n")
            context = {}

            # Handle upcoming bookings
            if upcoming_booking.exists():
                grouped_serializer = GroupedHotelBookingSerializer(upcoming_booking, context={"request": request}, many=True)
                context['upcoming_data_hotel'] = grouped_serializer.data

            # Handle completed bookings
            if completed_booking.exists():
                grouped_serializer = GroupedHotelBookingSerializer(completed_booking, context={"request": request}, many=True)
                context['Completed_data_hotel'] = grouped_serializer.data

            # Handle canceled bookings
            if canceled_booking.exists():
                grouped_serializer = GroupedHotelBookingSerializer(canceled_booking, context={"request": request}, many=True)
                context['Canceled'] = grouped_serializer.data

            if not context:
                context['message'] = 'No bookings found'
            print(context,"===========")
            return Response(context, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "User does not exist"}, status=status.HTTP_404_NOT_FOUND)

        except Userdetails.DoesNotExist:
            return Response({"error": "User details not found"}, status=status.HTTP_404_NOT_FOUND)

        except ValidationError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": f"An unexpected error occurred:{e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

class Ratingrivew(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        return Response(
            {
                "message": "The requested HTTP method is not supported for the requested resource. Please use POST."
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def post(self, request):
        try:
            user_id = request.user.id
            user = User.objects.get(id=user_id,is_deleted=False)
            user_details = get_object_or_404(Userdetails, user=user)
            data = request.data
            language = request.GET.get('lang', 'en')
            serializer = RatingReviewSerializer(data=data)
            if serializer.is_valid(raise_exception=True):
                booking_id = serializer.validated_data.get("booking_id")
                hotel_id = serializer.validated_data.get("hotelid")
                rating = serializer.validated_data.get("rating")
                review_text = serializer.validated_data.get("review_text")

                # Validate rating
                if not (1.0 <= float(rating) <= 5.0):
                    logger.info(f"\n\n\nRating View. Ratign is not between 1 and 5\n\n\n")
                    if language == "en":
                        message = "Rating must be between 1 and 5."
                    else:
                        message = "يجب أن يكون التقييم بين 1 و 5."
                    return Response(
                        {"message": message},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Validate hotel existence
                try:
                    get_hotel = Hotel.objects.get(id=hotel_id,date_of_expiry__gt = date.today(),post_approval=True,approval_status="approved")
                except Hotel.DoesNotExist:
                    logger.info(f"\n\n\nRating View. Hotel Does not exists\n\n\n")
                    if language == "en":
                        message = "Invalid hotel ID provided."
                    else:
                        message = "تم إدخال معرف فندق غير صالح."
                    return Response(
                        {"message": message},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                # Validate booking existence
                get_booking_obj = Booking.objects.filter(
                    user=user_details, hotel=get_hotel, booking_id=booking_id, booked_rooms__status__in=["cancelled", "completed"]
                )
                if not get_booking_obj.exists():
                    if language == "en":
                        message = "No bookings found for the user."
                    else:
                        message = "لم يتم العثور على أي حجوزات للمستخدم."
                    return Response(
                        {"message": message},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                # Prevent duplicate reviews
                if RecentReview.objects.filter(
                    booking__in=get_booking_obj, hotel=get_hotel, username=user.first_name
                ).exists():
                    if language == "en":
                        message = "You have already submitted a review for this booking."
                    else:
                        message = "لقد قمت بالفعل بإرسال مراجعة لهذا الحجز."
                    return Response(
                        {"message": message},
                        status=status.HTTP_409_CONFLICT,
                    )

                # Create the review
                review = RecentReview.objects.create(
                    booking=get_booking_obj.first(),
                    hotel=get_hotel,
                    rating=rating,
                    username=user.first_name,
                    date=datetime.now(),
                    review_text=review_text,
                )
                if language == "en":
                    message = "Review has been saved successfully."
                else:
                    message = "تم حفظ المراجعة بنجاح.."
                return Response(
                    {
                        "message": message,
                        "review": {
                            "id": review.id,
                            "hotel": review.hotel.name,
                            "rating": review.rating,
                            "review_text": review.review_text,
                            "date": review.date,
                        },
                    },
                    status=status.HTTP_201_CREATED,
                )
            
            if language == "en":
                message = "Invalid data provided."
            else:
                message = "تم إدخال بيانات غير صالحة."

            return Response(
                {"message": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            logger.info(f"\n\n\nException handled in Rating View. Exception: {e}\n\n\n")
            if language == "en":
                message = "An unexpected error occurred."
            else:
                message = "حدث خطأ غير متوقع."
            return Response(
                {"message": message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
  
class Favoritesmanagement(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        user = request.user
        try:
            get_user = User.objects.get(id=user.id,is_deleted=False)
            get_userdetail = Userdetails.objects.get(user=get_user)
            get_favorites = Favorites.objects.filter(user=get_userdetail, is_liked=True)
            if get_favorites.exists():
                serializer = FavoriteslistSerializer(get_favorites, context={"request": request}, many=True)
                logger.info(serializer.data)
                context = {
                    'data':serializer.data,
                    'message': 'data fetched successfully'
                }
                return Response(context,status=status.HTTP_200_OK)
            return Response({'message': 'You don’t have any favorites yet. Start adding your favorite items to see them here!'},status=status.HTTP_404_NOT_FOUND)
        except (User.DoesNotExist, Userdetails.DoesNotExist):
            logger.info(f"User is not present the DB")
            return Response({'message':'user is not found'},status=status.HTTP_404_NOT_FOUND)
    def post(self, request):
        user = request.user
        data = request.data
        get_user = User.objects.get(id=user.id,is_deleted=False)
        get_userdetail = Userdetails.objects.get(user=get_user)
        serializer = FavoritesmanagementSerializer(data=data)

        if serializer.is_valid(raise_exception=True):
            hotel_id = serializer.data.get('hotel_id')
            is_liked = serializer.data.get('is_liked')
            try:
                get_hotel = Hotel.objects.get(id=hotel_id, date_of_expiry__gt = date.today(),post_approval=True,approval_status="approved")
                favorite, created = Favorites.objects.get_or_create(user=get_userdetail, hotel=get_hotel)

                if is_liked:
                    if not favorite.is_liked:
                        favorite.is_liked = True
                        favorite.save()
                        message = 'Hotel added to favorites'
                    else:
                        message = 'Hotel is already in favorites'
                    return Response({'message': message}, status=status.HTTP_200_OK)
                else:
                    if favorite.is_liked:
                        favorite.is_liked = False
                        favorite.save()
                        return Response({'message': 'Hotel removed from favorites'}, status=status.HTTP_200_OK)
                    return Response({'message': "Hotel is not in the user's favorites"}, status=status.HTTP_404_NOT_FOUND)
            except Hotel.DoesNotExist:
                logger.info(f"\n\n Inside Favorite Management ApiView ----> Hotel is not found \n\n")
                return Response({'message':'Hotel is not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'message': 'Something went wrong'}, status=status.HTTP_400_BAD_REQUEST)
    
class CancelbookingView(APIView):
    def get(self, request):
        return Response({'message':'The requested HTTP method is not supported for the requested resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used for this endpoint'},status=status.HTTP_405_METHOD_NOT_ALLOWED)
    def post(self, request):
        print(request.data)
        user = request.user
        print(f"USER is ----{user}")
        get_userdetail = Userdetails.objects.get(user=user,user__is_deleted=False)
        data = request.data
        serializer = CancelbookingSerializer(data=data)
        
        if serializer.is_valid(raise_exception=True):
            booking_id = serializer.data.get('booking_id')
            reason = serializer.data.get('reason')
            
            # Fetch the booking object
            try:
                get_booking_obj = Booking.objects.get(booking_id=booking_id, user=get_userdetail)
                logger.info(f"booking found :{get_booking_obj}")
            except Booking.DoesNotExist:
                return Response({'message': 'Booking not found'}, status=status.HTTP_400_BAD_REQUEST)
            if get_booking_obj.status in ["pending","booked","confirmed"]:
                refund_status = "No refund available for this booking"
                message_arabic = "لا يوجد استرداد متاح لهذا الحجز"
                refund_amount = 0
                if get_booking_obj.status == 'confirmed':
                    #refund amount
                        check_refund_eligible=Check_payment_type(get_booking_obj.transaction)
                        if check_refund_eligible:
                            current_time = datetime.now()
                            refund_amount=Check_refund_amount(get_booking_obj,current_time)
                            logger.info(f"'refund_amount':{ refund_amount}")
                            if refund_amount>0:
                                try:
                                    transaction_received=get_booking_obj.transaction
                                    get_transaction=Transaction.objects.get(id=transaction_received.id)
                                    logger.info(f"Transaction found : {get_transaction}")
                                    PaymentType=get_transaction.payment_type
                                    if PaymentType.name == "Wallet":
                                        logger.info(f"payment type :{PaymentType}")
                                        try:
                                            get_wallet = Wallet.objects.get(user=get_userdetail,status="active")
                                        except Wallet.DoesNotExist:
                                            get_wallet = Wallet.objects.create(user=get_userdetail,status="active",balance=0.00)
                                        if get_wallet:
                                            logger.info(f"Wallet found:{get_wallet}")
                                            try:
                                                refund_transaction = RefundTransaction.objects.create(
                                                           transaction=transaction_received,
                                                            refund_status='Pending',
                                                        processed_date=timezone.now(),
                                                        created_at=timezone.now(),
                                                        reason=reason,
                                                        amount= refund_amount,
                                                        created_by=get_userdetail,
                                                        is_partial_refund=False,
                                                        status='active'                                              
                                                    )
                                                transaction_id, new_balance = create_wallet_transaction(get_wallet, "credit",refund_amount)
                                                logger.info(f"The Wallet-balance for the user {user} is {new_balance} ")
                                                if transaction_id:
                                                    refund_transaction.refund_status='Processed'
                                                    refund_transaction.save()
                                                    refund_status=f"{refund_amount} has refunded to the wallet account."
                                                    message_arabic = f"تم استرداد {refund_amount} إلى حساب المحفظة."
                                                else:
                                                    refund_transaction.refund_status='Rejected'
                                                    refund_transaction.save()
                                            except Exception as e:
                                                logger.error(f"An exception occured while creating refund transaction:{e}")
                                    elif PaymentType.name == "Debit Card" or PaymentType.name == "Credit Card":
                                        logger.info(f"payment type :{PaymentType}")
                                        try:
                                            get_wallet = Wallet.objects.get(user=get_userdetail,status="active")
                                        except Wallet.DoesNotExist:
                                            get_wallet = Wallet.objects.create(user=get_userdetail,status="active",balance=0.00)
                                        if get_wallet:
                                            try:
                                                refund_transaction = RefundTransaction.objects.create(
                                                        transaction=transaction_received,
                                                        refund_status='Pending',
                                                        processed_date=timezone.now(),
                                                        created_at=timezone.now(),
                                                        reason=reason,
                                                        amount= refund_amount,
                                                        created_by=get_userdetail,
                                                        is_partial_refund=False,
                                                        status='active'                                              
                                                    )
                                               
                                                transaction_id, new_balance = create_wallet_transaction(get_wallet, "credit",refund_amount )
                                                logger.info(f"The Wallet-balance for the user {user} is {new_balance} ")
                                                if transaction_id:
                                                    refund_transaction.refund_status='Processed'
                                                    refund_transaction.save()
                                                    refund_status=f"{refund_amount} has refunded to the wallet account."
                                                    message_arabic = f"{refund_amount} تم استرداده إلى حساب المحفظة."
                                                else:
                                                    refund_transaction.refund_status='Rejected'
                                                    refund_transaction.save()
                                            except Exception as e:
                                                logger.error(f"An exception occured while creating refund transaction:{e}")
                                except Transaction.DoesNotExist:
                                        logger.error(f"Transaction not found : {transaction_received}")
                if refund_amount>0:     
                    try:
                        notification = create_notification(user=request.user, notification_type="add_money_to_wallet",message=refund_status,message_arabic=message_arabic,source="hotel", related_booking=get_booking_obj)
                        logger.info(f" notification object for refund amount has been created -------> {notification}")
                    except Exception as e:
                        logger.info(f" Exception raised while Creating notification for refund amount. Exception: {e} ")
                        return Response({'messgae':'Something went wrong'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)    
             #changing  the booking status into cancelled
                get_booking_obj.status = "cancelled"
                get_booking_obj.save()
                booked_rooms = get_booking_obj.booked_rooms.all()
                for booked_room in booked_rooms:
                    if booked_room.status.lower() == "confirmed":
                        booked_room.status = "cancelled"
                        booked_room.room.availability = True
                        booked_room.room.save()
                    booked_room.save()
            
                create, created = Cancelbooking.objects.get_or_create(user=get_userdetail, booking=get_booking_obj, reason=reason)
                if created:
                    try:
                        message = f"You have cancelled your booking for the hotel {get_booking_obj.hotel.name}"
                        message_arabic = f"لقد قمت بإلغاء حجزك في الفندق {get_booking_obj.hotel.name}"
                        notification = create_notification(user=request.user, notification_type="booking_cancel",message=message,message_arabic=message_arabic,source="hotel", related_booking=get_booking_obj)
                        logger.info(f"\n\n notification obj for cancel hotel booking has been created -------> {notification} \n\n")
                    except Exception as e:
                        logger.info(f"\n\n Exception raised in Creating notification in cancel hotel booking. Exception: {e} \n\n")
                        return Response({'messgae':'Somethign went wrong'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                # Send cancellation email
                if get_booking_obj.booking_email:
                    subject = f'Your Booking in {get_booking_obj.hotel.name} Cancelled'
                    from_email = settings.EMAIL_HOST_USER
                    recipient_list = [get_booking_obj.booking_email,settings.ADMIN_EMAIL,get_booking_obj.hotel.get_vendor_email()]
                    
                    context = {
                        'hotel_name': get_booking_obj.hotel.name,
                        'Booking_Number': booking_id,
                        'recipient_name': f"{get_booking_obj.booking_fname} {get_booking_obj.booking_lname}",
                        'first_name': get_booking_obj.booking_fname,
                        'second_name': get_booking_obj.booking_lname,
                        'checkin_date': get_booking_obj.checkin_date,
                        'checkout_date': get_booking_obj.checkout_date,
                        'Guests': get_booking_obj.number_of_guests,
                        'total_amount': get_booking_obj.booked_price,
                        'address': get_booking_obj.hotel.address,
                        'contact_number': get_booking_obj.hotel.office_number,
                        'email': get_booking_obj.booking_email,
                        'Refund': refund_amount,
                        'Refund_status': refund_status
                    }
                    
                    html_content = render_to_string('cancel_booking_email.html', context)
                    text_content = strip_tags(html_content)
                    
                    email = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
                    email.attach_alternative(html_content, "text/html")
                    email.send()
                
                return Response({'message': 'Booking has been cancelled and email sent'}, status=status.HTTP_201_CREATED)
            else:
                return Response({'message':'booking status must be pending, booked, confirmed to cancel the booking'},status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'message': 'Invalid data'}, status=status.HTTP_400_BAD_REQUEST)
   
class Reviewratingfilter(APIView):
    def post(self, request, id):
        return Response({'message':'The requested HTTP method is not supported for the requested resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used for this endpoint'},status=status.HTTP_405_METHOD_NOT_ALLOWED)
    def get(self, request, id):
        data = request.data
        serializer = RatingfilterSerializer(data)
        rating = serializer.data.get('rating')
        try:
            get_hotel_obj = Hotel.objects.get(id=id, date_of_expiry__gt = date.today(),post_approval=True,approval_status="approved")
            print(rating,"========",get_hotel_obj)
            filtered_rating = RecentReview.objects.filter(hotel=get_hotel_obj, rating__in=rating)
            response_data = RecentReviewSerializer(filtered_rating, many=True)
            context = {
                'data':response_data.data,
                'message':'The data has been filtered based on rating'
            }
            return Response({context},status=status.HTTP_200_OK)
        except Hotel.DoesNotExist:
            logger.info(f"\n\n Inside Reviewratingfilter ApiView ----> Hotel is not found \n\n")
            return Response({'message':'Hotel is not found'}, status=status.HTTP_404_NOT_FOUND)
        
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        user = request.user
        logger.info(f"user--------{user.id}")
        try:
            user_details = Userdetails.objects.filter(user__id=user.id,user__is_vendor=False,user__is_deleted=False)
            logger.info(f"user_details--------{user_details}")
            serializer = UserProfileSerializer(user_details, many=True)
            logger.info(f"serializer--------{serializer.data}")
            return Response({'data': serializer.data}, status=status.HTTP_200_OK)
        except Userdetails.DoesNotExist:
            return Response({'message': 'User profile not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(e,"=================")
            return Response({'message': 'An unexpected error occurred. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def put(self, request):
        user = request.user
        try:
            user_details = Userdetails.objects.filter(user__id=user.id, user__is_vendor=False,user__is_deleted=False)
            serializer = UserProfileSerializer(user_details, data=request.data, partial=True)

            if serializer.is_valid():
                serializer.save()
                return Response({'data': serializer.data, 'message': 'Profile updated successfully'}, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Userdetails.DoesNotExist:
            return Response({'message': 'User profile not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.info(f"{e},====================")
            return Response({'message': 'An unexpected error occurred. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request):
        user = request.user
        try:
            user_details = Userdetails.objects.filter(user__id=user.id, user__is_vendor=False,user__is_deleted=False)
            for user in user_details:
                if user.image:
                    user.image.delete()
                    user.image = None
                    user.save()

            return Response({'message': 'Profile image deleted successfully'}, status=status.HTTP_200_OK)
        except Userdetails.DoesNotExist:
            return Response({'message': 'User profile not found'}, status=status.HTTP_404_NOT_FOUND)
        

#api/chalets?search=chalet&city=cityid&status=active
#api/chalets/id

class StandardResultsSetPagination(PageNumberPagination):
     page_size = 10
     page_size_query_param = 'page_size'
     max_page_size = 50

class ChaletModelViewSet(ModelViewSet):
    queryset = Chalet.objects.exclude(status='deleted').select_related('vendor')
    http_method_names = ['get']
    permission_classes = [AllowAny]
    serializer_class = ChaletModelSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, django_filters.DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ('city__name', 'name')
    search_fields = ('name', 'city__name')
    ordering_fields = ('name', 'chalet_id')

    def get_queryset(self):
        logger.info("Entering get_queryset method")
        queryset = super().get_queryset().order_by('chalet_id')
        checkin_date = self.request.query_params.get('checkin_date')
        checkout_date = self.request.query_params.get('checkout_date')
        city_name = self.request.query_params.get('city__name')

        if city_name:
            logger.info("Filtering chalets by city: %s", city_name)
            logger.info("======")
            logger.info(city_name)
            lang=detect_lang(city_name)
            if lang =='en':
                queryset = queryset.filter(city__name__icontains=city_name)
            else:
                queryset = queryset.filter(city__arabic_name__icontains=city_name)
        else:
            logger.warning("City name not provided in query parameters.")

        if checkin_date and checkout_date:
            try:
                checkin_date = datetime.strptime(checkin_date, '%Y-%m-%d').date()
                checkout_date = datetime.strptime(checkout_date, '%Y-%m-%d').date()

                if checkin_date >= checkout_date:
                    logger.error("Checkin date (%s) is not before checkout date (%s).", checkin_date, checkout_date)
                    return queryset.none()

                logger.info("Filtering chalets by date range: %s to %s", checkin_date, checkout_date)
                booked_chalets = ChaletBooking.objects.filter(
                    Q(checkin_date__lt=checkout_date) & Q(checkout_date__gt=checkin_date) & Q(status__in=['confirmed','check-in'])
                ).values_list('chalet_id', flat=True)

                queryset = queryset.exclude(id__in=booked_chalets)

            except ValueError as e:
                logger.error("Invalid date format provided: %s", e)
                return queryset.none()
        else:
            if not checkin_date:
                logger.warning("Checkin date not provided.")
            if not checkout_date:
                logger.warning("Checkout date not provided.")

        return queryset

    def list(self, request, *args, **kwargs):
        logger.info("Chalet list endpoint accessed.")
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)

        lang = request.GET.get('lang', 'en')
        city_name = request.query_params.get('city__name')
        checkin_date = request.query_params.get('checkin_date')
        checkout_date = request.query_params.get('checkout_date')

        if not queryset.exists():
            logger.warning(
                "No chalets found. City: %s, Checkin: %s, Checkout: %s",
                city_name, checkin_date, checkout_date
            )
            if city_name and checkin_date and checkout_date:
                logger.info("Returning response with no chalets available for the given city and date range.")
                return Response(
                    {'message': f"No chalets available in city {city_name} for the selected date range {checkin_date} to {checkout_date}."},
                    status=status.HTTP_404_NOT_FOUND
                )
            elif city_name:
                logger.info("Returning response with no chalets available for the given city.")
                return Response(
                    {'message': f"No chalets available in {city_name}."},
                    status=status.HTTP_404_NOT_FOUND
                )
            elif checkin_date and checkout_date:
                logger.info("Returning response with no chalets available for the given date range.")
                return Response(
                    {'message': f"No chalets available for the selected date range {checkin_date} to {checkout_date}."},
                    status=status.HTTP_404_NOT_FOUND
                )
            else:
                logger.info("Returning response with no chalets available.")
                return Response(
                    {'message': "No chalets available."},
                    status=status.HTTP_404_NOT_FOUND
                )

        if page is not None:
            logger.info("Paginated response returned with %d chalets.", len(page))
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        logger.info("Returning %d chalets in response.", len(queryset))
        return Response(serializer.data)


class ChaletBookingViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = ChaletBooking.objects.all()
    serializer_class = ChaletBookingSerializer

    def create(self, request, *args, **kwargs):
        logger.info("entered the chalet booking view")
        try:
            user = request.user
            data = request.data.copy()
            if 'booked_price' in data:
                try:
                    logger.info(f"booked rommprice is -----{Decimal(data['booked_price']).quantize(Decimal('0.000'))}")
                    data['booked_price'] = Decimal(data['booked_price']).quantize(Decimal('0.000'))
                except (TypeError, ValueError):
                    return Response(
                        {"message": "Invalid price value for booked_price."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            user_details = Userdetails.objects.get(user=user,user__is_deleted=False)
            data['user'] = user_details.id
            chalets = Chalet.objects.filter(id=data['chalet']).first()       
            mobile_no = data.get('booking_mobilenumber')
            email = data.get('booking_email')
            checkin_date  = data.get('checkin_date')
            checkout_date = data.get('checkout_date')
            
            email_validator = EmailValidator()
            try:
                with override('en'):
                    email_validator(email)
            except ValidationError as e:
                logger.info(f"Invalid email format for: {email}, Error: {str(e)}")
                return Response({"message": f"Invalid email format for: {email}"})
            try:
                checkin_date = datetime.strptime(checkin_date, '%Y-%m-%d').date()
                checkout_date = datetime.strptime(checkout_date, '%Y-%m-%d').date()
            except ValueError:
                return Response({"message": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_406_NOT_ACCEPTABLE)
            
            if checkin_date < date.today():
                return Response({"message": "Check-in date cannot be in the past."}, status=status.HTTP_406_NOT_ACCEPTABLE)

            if checkout_date <= checkin_date:
                return Response({"message": "Check-out date must be after the check-in date."}, status=status.HTTP_406_NOT_ACCEPTABLE)
            
            try:
                with override('en'):  # Force error messages to be in English
                    parsed_number = phonenumbers.parse(mobile_no, None)
                    print(parsed_number)
                    if not phonenumbers.is_valid_number(parsed_number):
                        return Response({"message": "Invalid phone number."}, status=status.HTTP_406_NOT_ACCEPTABLE)
            except phonenumbers.NumberParseException:
                with override('en'):  # Ensure consistent language for exception handling
                    return Response({"message": "Invalid phone number format."}, status=status.HTTP_406_NOT_ACCEPTABLE)
            
            if not chalets:
                return Response(
                    {"error": "The selected chalet is not available for booking."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            checkin_date = data.get('checkin_date')
            checkout_date = data.get('checkout_date')
            print("===========")
            # Check if the checkin and checkout dates are in the past
            if checkin_date and checkout_date:
                checkin_date_obj = date.fromisoformat(checkin_date)
                checkout_date_obj = date.fromisoformat(checkout_date)
                today = date.today()
                
                if checkin_date_obj < today or checkout_date_obj < today:
                    return Response(
                        {"message": "Check-in and checkout dates cannot be in the past."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                overlapping_booking = ChaletBooking.objects.filter(
                    chalet=data['chalet'],
                    status__iexact='pending',
                    checkin_date__lt=checkout_date_obj,
                    checkout_date__gt=checkin_date_obj
                ).exists()
                
                if overlapping_booking:
                    return Response(
                        {"message": "The chalet is already booked for the selected dates."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        #    last_booking = ChaletBooking.objects.order_by('id').last()
        #     logger.info("Last Booking: %s", last_booking)
        #     if last_booking:
        #         logger.info("Booking ID: %s", last_booking.booking_id)
        #         booking_id_last = last_booking.booking_id.replace('CHBK', '')
        #         last_id = int(booking_id_last)
        #         new_id = f'CHBK{last_id + 1}'
        #     else:
        #         logger.info("New ID")
        #         new_id = 'CHBK001'
        #     data['booking_id'] = new_id

            serializer = self.get_serializer(data=data)
            if serializer.is_valid(raise_exception=True):
                serializer.save()
            
            self.perform_create(serializer)
            serializer.instance.refresh_from_db()

            chalet = serializer.instance.chalet
            chalet.is_booked = True
            chalet.save()


            booking = serializer.instance
            booking.status = 'pending'
            booking.check_in_time=chalets.checkin_time
            booking.check_out_time=chalets.checkout_time
            # booking.save()
            booked_price = data.get('booked_price')
            print(booking,"==============")
            # QR Code Generation
            qr_url = generate_qr_code_chalet(booking.id, booking.token)
            booking.qr_code_url = qr_url
            booking.save()
            chalet_serializer = ChaletModelSerializer(chalet, context={'request': request})
            headers = self.get_success_headers(serializer.data)
            try:
                logger.info(f"Preparing data to send to the aggregator for booking ID: {booking.id}")
                notify_booking_aggregator(booking,"chalet")
                logger.info(f"Successfully sent data to the aggregator for booking ID: {booking.id}")
            except Exception as e:
                logger.error(f"Error sending data to the aggregator for booking ID: {booking.id} - {str(e)}", exc_info=True)
            return Response(
                {
                    "message": "Chalet booked successfully!",
                    "data": serializer.data,
                    "chalet_images": chalet_serializer.data.get('chalet_images'),
                    "main_image": chalet_serializer.data.get('main_image'),
                    "qrcode": qr_url
                },
                status=status.HTTP_201_CREATED,
                headers=headers
            )        
        except serializers.ValidationError as e:
            error_message = e.detail.get('non_field_errors', [str(e.detail)])[0]
            return Response({'message': error_message}, status=status.HTTP_406_NOT_ACCEPTABLE)        
        except Exception as e:
            logger.info(f"\n\n\n\n\nException in Chalet Booking View: {e}\n\n\n\n\n")
            return Response({'message':f"{e}"},status=status.HTTP_500_INTERNAL_SERVER_ERROR)      

class TopHotelsAPIView(APIView):
    def get(self, request):
        lang = request.GET.get('lang', 'en') 
        # Filter hotels with top bookings and reviews
        top_hotels = Hotel.objects.filter(
            date_of_expiry__gt = date.today(),post_approval=True,approval_status="approved",
            hotel_images__is_main_image=True
        ).annotate(
            total_bookings=Count('room_managements__bookedrooms'),
            avg_rating=Sum('recentreview__rating') / Count('recentreview')
        ).filter(
            total_bookings__gte=10,  # Example threshold for top bookings
            avg_rating__gte=4.0  # Example threshold for top reviews
        ).prefetch_related('hotel_images', 'room_managements')
        
        # Response data
        hotel_data = []
        
        for hotel in top_hotels:
            # Get main image
            main_image = hotel.hotel_images.filter(is_main_image=True).first()

            # Get room details and calculate total price (price_per_night + commission)
            room = hotel.room_managements.filter(status='active').first()
            if room:
                price_per_night = room.current_price

                # Get the relevant commission slab
                commission_slab = CommissionSlab.objects.filter(
                    from_amount__lte=price_per_night,
                    to_amount__gte=price_per_night,
                    status='active'
                ).first()

                # Add commission to price
                if commission_slab:
                    total_price = price_per_night + commission_slab.commission_amount
                else:
                    total_price = price_per_night  # Fallback if no commission slab found

                hotel_data.append({
                    "hotel_id": hotel.hotel_id,
                    "hotel_name": hotel.name if lang == "en" else hotel.name_arabic,
                    "main_image": main_image.image.url if main_image else None,
                    "price": total_price,
                    "avg_rating": hotel.avg_rating,
                    "total_bookings": hotel.total_bookings
                })

        return Response(hotel_data, status=status.HTTP_200_OK)


class TodaysOffersAPIView(APIView):
    def get(self, request, *args, **kwargs):
        lang = request.GET.get('lang', 'en') 
        today = timezone.now().date()
        
        # Filter offers valid for today
        todays_offers = Promotion.objects.filter(
            start_date__lte=today, 
            end_date__gte=today,
            status="active"
        ).select_related('hotel').prefetch_related('hotel__hotel_images', 'hotel__room_managements')

        offers_data = []
        
        for offer in todays_offers:
            hotel = offer.hotel
            if not hotel:
                continue

            # Calculate total bookings and average rating for the hotel
            total_bookings = hotel.room_managements.filter(bookedrooms__isnull=False).count()
            total_rating = hotel.recentreview_set.aggregate(total_rating=Sum('rating'))['total_rating']
            rating_count = hotel.recentreview_set.count()
            avg_rating = total_rating / rating_count if rating_count > 0 else None

            # Get main image for the hotel
            main_image = hotel.hotel_images.filter(is_main_image=True).first()
            image_url = main_image.image.url if main_image else None

            # Construct the offer data
            offer_data = {
                'hotel_name': hotel.name if lang == "en" else hotel.name_arabic,
                'offer_name': offer.title,
                'description': offer.description,
                'discount_type': offer.promotion_type,
                'validity_from': offer.start_date,
                'validity_to': offer.end_date,
                'main_image': image_url,
                'total_bookings': total_bookings,
                'avg_rating': avg_rating,
                'price': self.calculate_price(hotel),  # Reuse the price calculation logic
            }

            offers_data.append(offer_data)

        return Response({'offers': offers_data}, status=status.HTTP_200_OK)

    def calculate_price(self, hotel):
        room_prices = hotel.room_managements.values_list('price', flat=True)
        if room_prices:
            return min(room_prices)
        return None

class ChaletFavoritesmanagement(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        user = request.user
        get_user = User.objects.get(id=user.id,is_deleted=False)
        get_userdetail = Userdetails.objects.get(user=get_user)
        get_favorites = ChaletFavorites.objects.filter(user=get_userdetail, chalet__isnull=False, is_liked=True)
        if get_favorites.exists():
            serializer = ChaletFavoriteslistSerializer(get_favorites,context={'request': request} ,many=True)
            context = {
                'data': serializer.data,
                'message': 'Chalet favorites fetched successfully'
            }
            return Response(context, status=status.HTTP_200_OK)
        return Response({'message': 'You don’t have any chalet favorites yet.'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        user = request.user
        data = request.data
        get_user = User.objects.get(id=user.id,is_deleted=False)
        get_userdetail = Userdetails.objects.get(user=get_user)
        serializer = ChaletFavoritesmanagementSerializer(data=data)

        if serializer.is_valid(raise_exception=True):
            chalet_id = serializer.data.get('chalet_id')
            is_liked = serializer.data.get('is_liked')
            get_chalet = Chalet.objects.get(id=chalet_id, approval_status__iexact="approved")
            favorite, created = ChaletFavorites.objects.get_or_create(user=get_userdetail, chalet=get_chalet)

            if is_liked:
                if not favorite.is_liked:
                    favorite.is_liked = True
                    favorite.save()
                    message = 'Chalet added to favorites'
                else:
                    message = 'Chalet is already in favorites'
                return Response({'message': message}, status=status.HTTP_200_OK)
            else:
                if favorite.is_liked:
                    favorite.is_liked = False
                    favorite.save()
                    return Response({'message': 'Chalet removed from favorites'}, status=status.HTTP_200_OK)
                return Response({'message': "Chalet is not in the user's favorites"}, status=status.HTTP_404_NOT_FOUND)

        return Response({'message': 'Something went wrong'}, status=status.HTTP_400_BAD_REQUEST)

class ChaletBookedList(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        return Response({'message':'The requested HTTP method is not supported for the requested resource.'}, 
                        status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def get(self, request):
        try:
            user = request.user
            get_user = User.objects.get(id=user.id,is_deleted=False)
            get_userdetail = get_object_or_404(Userdetails, user=get_user)

            todays_date = datetime.today().strftime('%Y-%m-%d')

            # Upcoming chalet bookings
            upcoming_booking = ChaletBooking.objects.filter(
                Q(user=get_userdetail) &
                Q(checkout_date__gte=todays_date) &
                Q(status__in=["pending","booked","confirmed","check-in", "Check-In"])
            ).order_by('-created_date')

            # Completed chalet bookings
            completed_booking = ChaletBooking.objects.filter(
                Q(user=get_userdetail) &
                Q(checkout_date__lte=todays_date) &
                Q(status__iexact="completed")
            ).order_by('-checkout_date')

            # Canceled chalet bookings
            canceled_booking = ChaletBooking.objects.filter(
                Q(user=get_userdetail) &
                Q(status__in=["cancelled","rejected","expired"])
            ).order_by('-checkout_date')

            context = {}

            # Handle upcoming bookings
            if upcoming_booking.exists():
                grouped_serializer = GroupedChaletBookingSerializer(upcoming_booking, context={'request': request} ,many=True)
                aggregated_data = self.aggregate_bookings(grouped_serializer.data)
                context['upcoming_data_chalet'] = list(aggregated_data.values())

            # Handle completed bookings
            if completed_booking.exists():
                grouped_serializer = GroupedChaletBookingSerializer(completed_booking, context={'request': request}, many=True)
                aggregated_data = self.aggregate_bookings(grouped_serializer.data)
                context['completed_data_chalet'] = list(aggregated_data.values())

            # Handle canceled bookings
            if canceled_booking.exists():
                grouped_serializer = GroupedChaletBookingSerializer(canceled_booking, context={'request': request}, many=True)
                aggregated_data = self.aggregate_bookings(grouped_serializer.data)
                context['canceled'] = list(aggregated_data.values())

            if not context:
                context['message'] = 'No bookings found'

            return Response(context, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "User does not exist"}, status=status.HTTP_404_NOT_FOUND)

        except Userdetails.DoesNotExist:
            return Response({"error": "User details not found"}, status=status.HTTP_404_NOT_FOUND)

        except ValidationError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": f"An unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def aggregate_bookings(self, serialized_data):
        aggregated_data = {}
        for entry in serialized_data:
            booking_id = entry['booking_id']
            if booking_id not in aggregated_data:
                aggregated_data[booking_id] = {
                    'id':entry['id'],
                    'chalet_id': entry['chalet_id'],
                    'chalet_name': entry['chalet_name'],
                    'chalet_images': entry['chalet_images'],
                    'city': entry['city'],
                    'checkin_date': entry['checkin_date'],
                    'checkout_date': entry['checkout_date'],
                    'number_of_guests': entry['number_of_guests'],
                    'booking_id': entry['booking_id'],
                    'booked_price': entry['booked_price'],
                    'service_charge': entry['service_charge'],
                    'discount_amount': entry['discount_amount'],
                    'tax_amount': entry['tax_amount'],
                    'booking_fname': entry['booking_fname'],
                    'booking_lname': entry['booking_lname'],
                    'booking_email': entry['booking_email'],
                    'booking_mobilenumber': entry['booking_mobilenumber'],
                    'user_rating_review':entry['user_rating_review'],
                    'status':entry['status']
                }
        return aggregated_data

class CancelChaletBookingView(APIView):
    def get(self, request):
        return Response({'message':'The requested HTTP method is not supported for the requested resource. Please use POST for cancellation.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def post(self, request):
        user = request.user
        get_userdetail = Userdetails.objects.get(user=user,user__is_deleted=False)
        data = request.data
        serializer = ChaletBookingCancelSerializer(data=data)

        if serializer.is_valid(raise_exception=True):
            booking_id = serializer.data.get('booking_id')
            reason = serializer.data.get('reason')
            print("booking id and userdetails",booking_id,get_userdetail)

            # Fetch the booking object
            try:
                get_booking_obj = ChaletBooking.objects.get(booking_id=booking_id, user=get_userdetail)
            except ChaletBooking.DoesNotExist:
                return Response({'message': 'Booking not found'}, status=status.HTTP_400_BAD_REQUEST)

            # Cancel the chalet booking
            if get_booking_obj.status.lower() in ["pending","booked","confirmed"]:
                refund_status = "No refund available for this booking"
                message_arabic = "لا يوجد استرداد متاح لهذا الحجز"
                refund_amount = 0
                if  get_booking_obj.status=='confirmed':
                      #refund amount
                    check_refund_eligible=Check_payment_type(get_booking_obj.transaction)
                    if check_refund_eligible:
                        #refund amount
                        current_time = datetime.now()
                        refund_amount, refund_percentage=Check_refund_eligibility(get_booking_obj,current_time)
                        logger.info(f"'refund_amount':{ refund_amount},'refund_percentage':{refund_percentage}")
                        if refund_amount>0:
                            try:
                                transaction_received=get_booking_obj.transaction
                                get_transaction=Transaction.objects.get(id=transaction_received.id)
                                logger.info(f"Transaction found : {get_transaction}")
                                PaymentType=get_transaction.payment_type
                                if PaymentType.name == "Wallet":
                                    logger.info(f"payment type :{PaymentType}")
                                    try:
                                        get_wallet = Wallet.objects.get(user=get_userdetail,status="active")
                                    except Wallet.DoesNotExist:
                                        get_wallet = Wallet.objects.create(user=get_userdetail,status="active",balance=0.00)
                                    if get_wallet:
                                        logger.info(f"Wallet found:{get_wallet}")
                                        try:
                                            refund_transaction = RefundTransaction.objects.create(
                                                        transaction=transaction_received,
                                                        refund_status='Pending',
                                                    processed_date=timezone.now(),
                                                    created_at=timezone.now(),
                                                    reason=reason,
                                                    amount= refund_amount,
                                                    created_by=get_userdetail,
                                                    is_partial_refund=(refund_percentage < 100), 
                                                    status='active'                                              
                                                )
                                            transaction_id, new_balance = create_wallet_transaction(get_wallet, "credit",refund_amount)
                                            logger.info(f"The Wallet-balance for the user {user} is {new_balance} ")
                                            if transaction_id:
                                                refund_transaction.refund_status='Processed'
                                                refund_transaction.save()
                                                refund_status=f"{refund_amount} has refunded to the wallet account."
                                                message_arabic=f"تم رد {refund_amount} إلى حساب المحفظة."
                                            else:
                                                refund_transaction.refund_status='Rejected'
                                                refund_transaction.save()
                                        except Exception as e:
                                            logger.error(f"An exception occured while creating refund transaction:{e}")
                                elif PaymentType.name == "Debit Card" or PaymentType.name == "Credit Card":
                                    logger.info(f"payment type :{PaymentType}")
                                    try:
                                        get_wallet = Wallet.objects.get(user=get_userdetail,status="active")
                                    except Wallet.DoesNotExist:
                                        get_wallet = Wallet.objects.create(user=get_userdetail,status="active",balance=0.00)
                                    if get_wallet:
                                        try:
                                            refund_transaction = RefundTransaction.objects.create(
                                                    transaction=transaction_received,
                                                    refund_status='Pending',
                                                    processed_date=timezone.now(),
                                                    created_at=timezone.now(),
                                                    reason=reason,
                                                    amount= refund_amount,
                                                    created_by=get_userdetail,
                                                    is_partial_refund=(refund_percentage < 100), 
                                                    status='active'                                              
                                                )
                                            
                                            transaction_id, new_balance = create_wallet_transaction(get_wallet, "credit",refund_amount )
                                            logger.info(f"The Wallet-balance for the user {user} is {new_balance} ")
                                            if transaction_id:
                                                refund_transaction.refund_status='Processed'
                                                refund_transaction.save()
                                                refund_status=f"{refund_amount} has refunded to the wallet account."
                                                message_arabic=f"{refund_amount} تم استرداده إلى حساب المحفظة."
                                            else:
                                                refund_transaction.refund_status='Rejected'
                                                refund_transaction.save()
                                        except Exception as e:
                                            logger.error(f"An exception occured while creating refund transaction:{e}")
                            except Transaction.DoesNotExist:
                                    logger.error(f"Transaction not found : {transaction_received}") 
                if refund_amount>0:
                    try:
                        notification = create_notification(user=request.user, notification_type="add_money_to_wallet",message=refund_status,message_arabic=message_arabic,source="chalet", chalet_booking=get_booking_obj)
                        logger.info(f" notification object for refund amount has been created -------> {notification}")
                    except Exception as e:
                        logger.info(f" Exception raised while Creating notification for refund amount. Exception: {e} ")
                        return Response({'messgae':'Something went wrong'},status=status.HTTP_500_INTERNAL_SERVER_ERROR) 
                # cancelling the chalet
                get_booking_obj.status = "cancelled"
                get_booking_obj.chalet.is_booked = False  # Mark the chalet as available again
                get_booking_obj.chalet.save()
                get_booking_obj.save()
                 # Create or update the cancellation record
                create, created = CancelChaletBooking.objects.get_or_create(user=get_userdetail, booking=get_booking_obj, reason=reason)
                if created:
                    message = f"You have cancelled your booking for the chalet {get_booking_obj.chalet.name}"
                    message_arabic = f"لقد قمت بإلغاء حجزك في الشاليه {get_booking_obj.chalet.name}"
                    try:
                        notification = create_notification(user=request.user, notification_type="booking_cancel",message=message,message_arabic=message_arabic,source="chalet", chalet_booking=get_booking_obj)
                        logger.info(f"\n\n notification obj for cancel chalet booking has been created -------> {notification} \n\n")
                    except Exception as e:
                        logger.info(f"\n\n Exception raised in Creating notification in cancel chalet booking. Exception: {e} \n\n")
                        return Response({'messgae':'Somethign went wrong'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                # Send cancellation email inside try-except block
                try:
                    if get_booking_obj.booking_email:
                        subject = f'Your Booking in {get_booking_obj.chalet.name} Cancelled'
                        from_email = settings.EMAIL_HOST_USER
                        recipient_list = [get_booking_obj.booking_email,settings.ADMIN_EMAIL,get_booking_obj.chalet.get_vendor_email()]

                        context = {
                            'chalet_name': get_booking_obj.chalet.name,
                            'Booking_Number': booking_id,
                            'recipient_name': f"{get_booking_obj.booking_fname} {get_booking_obj.booking_lname}",
                            'first_name':get_booking_obj.booking_fname,
                            'second_name':get_booking_obj.booking_lname,
                            'checkin_date': get_booking_obj.checkin_date,
                            'checkout_date': get_booking_obj.checkout_date,
                            'Guests': get_booking_obj.number_of_guests,
                            'total_amount': get_booking_obj.booked_price,
                            'address': get_booking_obj.chalet.address,
                            'contact_number': get_booking_obj.chalet.office_number,
                            'email': get_booking_obj.booking_email,
                            'Refund': refund_amount,
                            'Refund_status': refund_status
                        }

                        html_content = render_to_string('cancel_chalet_booking_email.html', context)
                        text_content = strip_tags(html_content)

                        email = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
                        email.attach_alternative(html_content, "text/html")
                        email.send()

                except Exception as e:
                    # Log the error for debugging purposes 
                    logger.error(f"Failed to send cancellation email: {str(e)}")
                    return Response({
                        'message': 'Booking cancelled, but there was an error sending the email.'
                    }, status=status.HTTP_201_CREATED)

                return Response({'message': 'Booking has been cancelled and email sent'}, status=status.HTTP_201_CREATED)
            else:
                return Response({'message':'booking status must be pending, booked, confirmed to cancel the booking'},status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': 'Invalid data'}, status=status.HTTP_400_BAD_REQUEST)

class Refund_eligibility(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    def post(self, request,id):
        user = request.user
        get_userdetail = Userdetails.objects.get(user=user,user__is_deleted=False)
        category = request.GET.get('category')
        if category == 'Hotel':
            try:
                get_booking_obj = Booking.objects.get(id=id, user=get_userdetail)
                logger.info(f"booking found at Hotel :{get_booking_obj}")
                #refund amount
                if get_booking_obj:
                    if get_booking_obj.status == 'confirmed':
                        check_refund_eligible=Check_payment_type(get_booking_obj.transaction)
                        if check_refund_eligible:
                            current_time = datetime.now()
                            refund_amount=Check_refund_amount(get_booking_obj,current_time)
                            logger.info(f"'refund_amount':{ refund_amount}")
                            if refund_amount>0:
                                return Response({'message': 'Success','refund_amount':refund_amount}, status=status.HTTP_200_OK)
                            else:
                                return Response({'message': 'Success','refund_amount':None }, status=status.HTTP_200_OK)
                        else:
                            return Response({'message': 'You are not eligible for refund'}, status=status.HTTP_200_OK)
                    else:
                        return Response({'message': 'Your Booking is not confirmed yet'}, status=status.HTTP_404_NOT_FOUND)
            except Booking.DoesNotExist:
                return Response({'message': 'Booking not found'}, status=status.HTTP_400_BAD_REQUEST)
        elif category == 'Chalet':     
        # Fetch the booking object
            try:
                get_booking_obj = ChaletBooking.objects.get(id=id, user=get_userdetail)
                if get_booking_obj:
                    logger.info(f"booking found at Chalet :{get_booking_obj}")
                    if get_booking_obj.status == 'confirmed':
                        logger.info(f"Your booking is confirmed")
                        check_refund_eligible=Check_payment_type(get_booking_obj.transaction)
                        if check_refund_eligible:
                            #refund amount
                            current_time = datetime.now()
                            refund_amount, refund_percentage=Check_refund_eligibility(get_booking_obj,current_time)
                            logger.info(f"'refund_amount':{ refund_amount},'refund_percentage':{refund_percentage}")
                            if refund_amount>0:
                                logger.info(f"Refund available for the chalet transaction")
                                return Response({'message': 'Success','refund_amount':refund_amount,'refund_percentage':refund_percentage}, status=status.HTTP_200_OK)
                            else:
                                logger.info(f"No refund for the chalet transaction")
                                return Response({'message': 'Success','refund_amount':None ,'refund_percentage':None}, status=status.HTTP_200_OK)
                        else:
                            logger.info("Your booking is not eligible for refund")
                            return Response({'message': 'You are not eligible for refund'}, status=status.HTTP_200_OK)
                    else:
                        logger.info("Booking is not confirmed yet")
                        return Response({'message': 'Your Booking is not confirmed yet'}, status=status.HTTP_404_NOT_FOUND)
                else:
                    logger.warning(f"No Booking Found")  
                    return Response({'message': 'Booking not found'}, status=status.HTTP_400_BAD_REQUEST)
            
            except ChaletBooking.DoesNotExist:
                logger.warning("No chalet booking")
                return Response({'message': 'Booking not found'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            logger.warning("No Category found")
            return Response({'message': 'Invalid Category'}, status=status.HTTP_400_BAD_REQUEST)

class ChaletReview(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        return Response({
            'message': 'The requested HTTP method is not supported for the requested resource. Please use POST.'
        }, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def post(self, request):
        try:
            user = request.user
            data = request.data
            language = request.GET.get('lang', 'en')
            # Fetch user and user details
            get_user = User.objects.get(id=user.id,is_deleted=False)
            get_userdetail = get_object_or_404(Userdetails, user=get_user)

            # Validate incoming data
            serializer = ChaletRatingReviewSerializer(data=data)
            if serializer.is_valid(raise_exception=True):
                booking_id = serializer.validated_data.get('booking_id')
                chalet_id = serializer.validated_data.get('chaletid')
                rating = serializer.validated_data.get('rating')
                review_text = serializer.validated_data.get('review_text')

                # Validate rating range
                if not (1.0 <= float(rating) <= 5.0):
                    if language == "en":
                        message = "Rating must be between 1 and 5."
                    else:
                        message = "يجب أن يكون التقييم بين 1 و 5."
                    return Response(
                        {"message": message},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Check if chalet exists
                try:
                    get_chalet = Chalet.objects.get(id=chalet_id)
                except Chalet.DoesNotExist:
                    if language == "en":
                        message = "Invalid chalet ID provided."
                    else:
                        message = "تم إدخال معرف شاليه غير صالح."
                    return Response(
                        {"message": message},
                        status=status.HTTP_404_NOT_FOUND
                    )

                # Check if user has valid bookings for the chalet
                get_booking_obj = ChaletBooking.objects.filter(
                    user=get_userdetail,
                    chalet=get_chalet,
                    status__in=['cancelled', 'completed'],
                    booking_id=booking_id
                )
                if not get_booking_obj.exists():
                    if language == "en":
                        message = "No bookings found for the user."
                    else:
                        message = "لم يتم العثور على أي حجوزات للمستخدم."
                    return Response(
                        {"message": message},
                        status=status.HTTP_404_NOT_FOUND
                    )

                # Prevent duplicate reviews
                if ChaletRecentReview.objects.filter(
                    chalet_booking__in=get_booking_obj, 
                    chalet=get_chalet, 
                    username=get_user.first_name
                ).exists():
                    if language == "en":
                        message = "You have already submitted a review for this booking."
                    else:
                        message = "لقد قمت بالفعل بإرسال مراجعة لهذا الحجز."
                    return Response(
                        {"message": message},
                        status=status.HTTP_409_CONFLICT
                    )

                # Create the review
                review = ChaletRecentReview.objects.create(
                    chalet_booking=get_booking_obj.first(),
                    chalet=get_chalet,
                    rating=rating,
                    username=get_user.first_name,
                    date=datetime.now(),
                    review_text=review_text
                )

                # Return success response with review details
                if language == "en":
                    message = "Review has been saved successfully."
                else:
                    message = "تم حفظ المراجعة بنجاح.."
                return Response(
                    {
                        "message": message,
                        "review": {
                            "id": review.id,
                            "chalet": review.chalet.name,
                            "rating": review.rating,
                            "review_text": review.review_text,
                            "date": review.date,
                        }
                    },
                    status=status.HTTP_201_CREATED
                )

            # Handle serializer errors
            if language == "en":
                message = "Invalid data provided."
            else:
                message = "تم إدخال بيانات غير صالحة."
            return Response(
                {"message": message, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        except serializers.ValidationError as e:
            # Explicitly handle validation errors
            print("ValidationError:", e.detail)  # Debugging validation errors
            return Response(
                {"message": "Validation failed.", "errors": e.detail},
                status=status.HTTP_400_BAD_REQUEST
            )

        except User.DoesNotExist:
            return Response({"message": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)

        except Userdetails.DoesNotExist:
            return Response({"message": "User details not found."}, status=status.HTTP_404_NOT_FOUND)

        except Chalet.DoesNotExist:
            return Response({"message": "Chalet not found."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            print("Unexpected error:", e)  # Debugging unexpected errors
            return Response(
                {"message": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class FeaturedChaletsAPIView(APIView):
    def get(self, request):
        language = request.GET.get('lang', 'en')
        # Filter chalets with top bookings and reviews
        top_chalets = Chalet.objects.filter(
            approval_status="approved",
            status='active'  # Ensuring only active chalets
        ).annotate(
            total_bookings=Count('booking_set'),  # Assuming a relation to bookings
            avg_rating=Sum('recentreview__rating') / Count('recentreview')  # Assuming similar reviews model as Hotel
        ).filter(
            total_bookings__gte=5,  # Example threshold for top bookings
            avg_rating__gte=4.0  # Example threshold for top reviews
        ).prefetch_related('amenities')  # Prefetch amenities for each chalet
        
        # Response data
        chalet_data = []
        
        for chalet in top_chalets:
            # Get main image (assuming chalet has a related image model similar to hotels)
            main_image = chalet.chaletimage_set.filter(is_main_image=True).first()

            # Calculate total price (base price + commission)
            price_per_night = chalet.current_price

            # Get the relevant commission slab
            commission_slab = CommissionSlab.objects.filter(
                from_amount__lte=price_per_night,
                to_amount__gte=price_per_night,
                status='active'
            ).first()

            # Add commission to price
            if commission_slab:
                total_price = price_per_night + commission_slab.commission_amount
            else:
                total_price = price_per_night  # Fallback if no commission slab found

            chalet_data.append({
                "chalet_id": chalet.chalet_id,
                "chalet_name": chalet.name if language == "en" else chalet.name_arabic,
                "main_image": main_image.image.url if main_image else None,
                "price": total_price,
                "avg_rating": chalet.avg_rating,
                "total_bookings": chalet.total_bookings,
                "number_of_guests": chalet.number_of_guests
            })

        return Response(chalet_data, status=status.HTTP_200_OK)




class ChaletSearchView(APIView):

    permission_classes = [AllowAny]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        # import pdb;pdb.set_trace()
        logger.info("Received chalet search request.")
        language = request.GET.get('lang', 'en')
        data = request.data
        logger.info(f"Request data: {data}, Language: {language}")
        serializer = ChaletSearchSerializer(data=data)

        if serializer.is_valid(raise_exception=True):
            logger.info("Serializer data is valid.")
            try:
                lat= serializer.data.get('latitude')
                long = serializer.data.get('longitude')
                city_name = serializer.data.get('city_name', '')
                chalet_name = serializer.data.get('chalet_name', '')
                checkin_date = serializer.data.get('checkin_date')
                checkout_date = serializer.data.get('checkout_date')
                members = serializer.data.get('members')
                rating = serializer.data.get('rating', None)
                amenities = serializer.data.get('amenities', [])
                sort = serializer.data.get('sorted', '')
                logger.info(f"Filters - City: {city_name}, Chalet: {chalet_name}, "
                             f"Check-in: {checkin_date}, Check-out: {checkout_date}, "
                             f"Members: {members}, Rating: {rating}, Amenities: {amenities}, Sort: {sort}")

                try:
                    chalet_query = Chalet.objects.filter(
                        approval_status__iexact="approved",
                        post_approval=True,
                        number_of_guests__gte=members
                    ).prefetch_related('amenities', 'chalet_images', 'post_policies__policy_names')
                except Exception as e:
                    logger.error(f"Error fetching chalet query: {e}")

                if not chalet_query.exists():
                    logger.info("No chalets found matching the criteria.")
                    return Response({'message': 'Chalet not found'}, status=status.HTTP_404_NOT_FOUND)

                # Apply filters
                if lat and long:
                    logger.info("The requet received for fetching by city name")
                    nearby_chalets = get_nearby_chalets(lat, long, members)
                    if nearby_chalets:
                        chalet_ids = [chalet.id for chalet, _ in nearby_chalets]  # No reverse
                        preserved_order = Case(*[When(id=pk, then=pos) for pos, pk in enumerate(chalet_ids)])
                        chalet_query = Chalet.objects.filter(id__in=chalet_ids).prefetch_related(
                            'amenities', 'chalet_images', 'post_policies__policy_names'
                        ).order_by(preserved_order)
                        logger.info(f"chalet queries: {chalet_query}")
                    else:
                        chalet_query=None
                        logger.warning("No hotels found for city ")
                        message = "Chalet or city not available" if language == "en" else "الفندق أو المدينة غير متاحين"
                        return Response({'message': message}, status=status.HTTP_400_BAD_REQUEST)
                    
                else:
                    if city_name:
                        logger.info(f"Filtering by city: {city_name}")
                        lang=detect_lang(city_name)
                        if lang == 'en':
                            chalet_query = chalet_query.filter(city__name__iexact=city_name)
                        else:
                            chalet_query = chalet_query.filter(city__arabic_name__iexact=city_name)

                    if chalet_name:
                        logger.info(f"Filtering by chalet name: {chalet_name}")
                        lang=detect_lang(chalet_name)
                        if lang == 'en':
                            chalet_query = chalet_query.filter(name__icontains=chalet_name)
                        else:
                            chalet_query = chalet_query.filter(name_arabic__icontains=chalet_name)
                        

                chalet_query = chalet_query.annotate(
                    avg_rating=Avg('chaletrecentreview__rating'),
                    review_count=Count('chaletrecentreview')
                )

                if rating:
                    logger.info(f"Filtering by rating: <= {rating}")
                    chalet_query = chalet_query.filter(avg_rating__lte=rating)

                if amenities:
                    logger.info(f"Filtering by amenities: {amenities}")
                    chalet_query = chalet_query.filter(amenities__amenity_name__in=amenities).annotate(
                        matching_amenities=Count('amenities')
                    ).filter(matching_amenities=len(amenities))

                if not chalet_query.exists():
                    logger.info("No chalets found after applying all filters.")
                    return Response({'message': 'Chalet not found'}, status=status.HTTP_404_NOT_FOUND)
    
                # Sorting
                # if sort == "lowest_price":
                #     logger.info("Sorting by lowest price.")
                #     chalet_query = chalet_query.order_by('total_price')
                # elif sort == "highest_price":
                #     logger.info("Sorting by highest price.")
                #     chalet_query = chalet_query.order_by('-total_price')
                # elif sort == "rating":
                #     logger.info("Sorting by rating.")
                #     chalet_query = chalet_query.annotate(avg_rating=Avg('recentreview__rating')).order_by('-avg_rating')
                # else:
                #     logger.info("Sorting by created date.")
                    # chalet_query = chalet_query.order_by('created_date')

                # Helper function to get cancellation policies
                def get_cancellation_policy(chalet):
                    try:
                        logger.info(f"Fetching cancellation policy for chalet ID: {chalet.name}")
                        cancellation_categories = chalet.post_policies.filter(name__icontains="cancel")
                        
                        if cancellation_categories.exists():
                            logger.info(f"Cancellation categories found for chalet ID: {chalet.name}")
                            cancellation_policies = []

                            for category in cancellation_categories:
                                policies = category.policy_names.filter(chalet=chalet)
                                cancellation_policies.extend([policy.title for policy in policies])

                            return cancellation_policies
                        else:
                            logger.warning(f"No cancellation category found for chalet ID: {chalet.name}")
                            return []
                    except Exception as e:
                        logger.error(
                            f"Error fetching cancellation policy for chalet ID: {chalet.name}, Exception: {e}",
                            exc_info=True,
                        )
                        return []

                logger.info("Processing chalets...")
                chalet_list = []
                if language == 'en':
                    all_amenities = Amenity.objects.filter(status=True).values_list('amenity_name', flat=True)
                else:
                    all_amenities = Amenity.objects.filter(status=True).values_list('amenity_name_arabic', flat=True)
                logger.info(all_amenities)

                for chalet in chalet_query:
                    try:
                        logger.info(f"Processing chalet: {chalet.id}")
                        # Check if the chalet is booked
                        is_booked = ChaletBooking.objects.filter(
                            chalet=chalet,
                            checkin_date__lt=checkout_date,
                            checkout_date__gt=checkin_date,
                            status__in=["confirmed","check-in"]
                        ).exists()
                        if is_booked:
                            logger.info(f"Chalet {chalet.id} is booked for the selected dates.")
                            continue

                        # Price calculation
                        checkin_date_obj = datetime.strptime(checkin_date, '%Y-%m-%d').date()
                        checkout_date_obj = datetime.strptime(checkout_date, '%Y-%m-%d').date()
                        chalet_price_calculation = calculate_hotel_price(chalet_id=chalet.id,property='chalet',checkin_date=checkin_date_obj,checkout_date=checkout_date_obj)
                        chalet_price = chalet_price_calculation.get("calculated_price")
                        # commission_slab = CommissionSlab.objects.filter(
                        #     from_amount__lte=chalet_price,
                        #     to_amount__gte=chalet_price,
                        #     status='active'
                        # ).first()
                        chalet_price_with_commission = chalet_price 
                        # Apply promotion discount
                        promotion = Promotion.objects.filter(
                            Q(chalet=chalet) | Q(multiple_chalets=chalet), category="common",
                            discount_percentage__isnull=False,
                            status="active",
                            start_date__lte=timezone.now().date(),
                            end_date__gte=timezone.now().date()
                        ).order_by("-discount_percentage").first()

                        discounted_price = chalet_price_with_commission
                        if promotion:
                            discount = (Decimal(promotion.discount_percentage) / Decimal(100)) * chalet_price_with_commission
                            discounted_price -= discount

                        user = request.user
                        userdetail = Userdetails.objects.filter(user=user.id,user__is_deleted=False).first()
                        is_in_comparison = (
                            Comparison.objects.filter(chalet=chalet.id, user=userdetail.id, status="active").exists()
                            if userdetail else False
                        )
                        is_favorite = (ChaletFavorites.objects.filter(chalet=chalet.id,user=userdetail.id,is_liked=True).exists()
                            if userdetail else False
                         )
                        
                        
                        chalet_type_dict = {}
                        if chalet and chalet.chalet_type and chalet.chalet_type.status == "active":
                            chalet_type_dict['type'] = chalet.chalet_type.arabic_name if language ==  "ar" else  chalet.chalet_type.name
                            chalet_type_dict['icon'] = urljoin(settings.MEDIA_URL, str(chalet.chalet_type.icon))
                        else:
                            chalet_type_dict = {"type": None, "icon": None}
                        

                        # Prepare chalet data
                        main_image = chalet.chalet_images.filter(is_main_image=True).first()
                        chalet_list.append({
                            'id': chalet.id,
                            'name': chalet.name_arabic if language == 'ar' else chalet.name,
                            'city': chalet.city.arabic_name if language == 'ar' else chalet.city.name,
                            'rating': chalet.avg_rating,
                            'review_count': chalet.review_count, 
                            'price': chalet_price,
                            'is_favorite': is_favorite,
                            'main_image': main_image.image.url if main_image else None,
                            'amenities': [amenity.amenity_name_arabic  for amenity in chalet.amenities.all()] if language == 'ar' else [amenity.amenity_name for amenity in chalet.amenities.all()] ,
                            'cancellation_policy': get_cancellation_policy(chalet),
                            'comparison': is_in_comparison,
                            'promotion': {
                                "id": promotion.id if promotion else None,
                                "title": promotion.title if promotion else None,
                                "discount_percentage": promotion.discount_percentage if promotion else None,
                                "discounted_price": discounted_price if promotion else None
                            } if promotion else None,
                            'chalettype':chalet_type_dict
                        })
                    except Exception as e:
                        logger.error(f"Error processing chalet {chalet.id}: {e}")
                logger.info(f"Applying sorting: {sort}")

                if sort == "lowest_price":
                    logger.info("Sorting final chalet list by lowest price.")
                    chalet_list.sort(key=lambda x: x['price'])
                elif sort == "highest_price":
                    logger.info("Sorting final chalet list by highest price.")
                    chalet_list.sort(key=lambda x: x['price'], reverse=True)
                elif sort == "rating":
                    logger.info("Sorting final chalet list by rating.")
                    chalet_list.sort(key=lambda x: x.get('rating') or 0, reverse=True)
                else:
                    logger.info("No explicit sort applied on final chalet list.")

                response_data = {
                    'chalets': chalet_list,
                    'available_amenities': list(all_amenities)
                }
                logger.info("Chalet search completed successfully.")
                return Response(response_data, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error during chalet search: {e}")
                return Response({'message': 'Something went wrong'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.warning("Invalid data received in ChaletSearchSerializer.")
        return Response({'message': 'Data from serializer is not valid'}, status=status.HTTP_400_BAD_REQUEST)
   
        
class PromoCodeSearch(APIView):
    def get(self, request, *args, **kwargs):
        hotel_id = request.query_params.get('hotel_id', None)
        chalet_id = request.query_params.get('chalet_id', None)

        hotel_name = None
        chalet_name = None
        current_date = timezone.now().date()


        if hotel_id:
            try:
                hotel = Hotel.objects.get(id=hotel_id)
                hotel_name = hotel.name
            except Hotel.DoesNotExist:
                hotel_name = "Unknown Hotel"

        if chalet_id:
            try:
                chalet = Chalet.objects.get(id=chalet_id)
                chalet_name = chalet.name
            except Chalet.DoesNotExist:
                chalet_name = "Unknown Chalet"

        if hotel_id and chalet_id:
            queryset = Promotion.objects.filter(
                Q(hotel_id=hotel_id) & Q(chalet_id=chalet_id),
                category__in=['promo_code'],
                status="active"
            )
        elif hotel_id:
            queryset = Promotion.objects.filter(
                hotel_id=hotel_id,
                category__in=['promo_code'],
                status="active"
            )
        elif chalet_id:
            queryset = Promotion.objects.filter(
                chalet_id=chalet_id,
                category__in=['promo_code'],
                status="active"
            )
        else:
            queryset = Promotion.objects.filter(
                category__in=['promo_code'],
                status="active"
            )

        if not queryset.exists():
            if hotel_id and chalet_id:
                message = f"No promo codes available for hotel {hotel_name} and chalet {chalet_name}."
            elif hotel_id:
                message = f"No promo codes available for hotel {hotel_name}."
            elif chalet_id:
                message = f"No promo codes available for chalet {chalet_name}."
            else:
                message = "No promo codes available."

            return Response({"message": message}, status=status.HTTP_404_NOT_FOUND)

        serializer = PromoCodeSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class CurrencyConversionAPIView(APIView):
    def get(self, request, *args, **kwargs):
        country_name = request.query_params.get('country', None)
        amount = request.query_params.get('amount', None)

        if not country_name or not amount:
            return Response({"error": "Please provide both 'country' and 'amount'"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = float(amount)
        except ValueError:
            return Response({"error": "Invalid amount format. Please enter a valid number."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            country = Country.objects.get(name__iexact=country_name)
            currency_code = country.currency
        except Country.DoesNotExist:
            return Response({"error": f"No currency found for the country '{country_name}'."}, status=status.HTTP_404_NOT_FOUND)

        base_currency = 'OMR'
        api_url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"

        try:
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            if currency_code not in data['rates']:
                return Response({"error": f"Exchange rate not found for currency '{currency_code}'."}, status=status.HTTP_404_NOT_FOUND)

            conversion_rate = data['rates'][currency_code]
            converted_amount = amount * conversion_rate

            return Response({
                "country": country.name,
                "currency_code": currency_code,
                "amount_in_omr": amount,
                "converted_amount": converted_amount,
                "exchange_rate": conversion_rate
            }, status=status.HTTP_200_OK)

        except requests.RequestException as e:
            return Response({"error": "Failed to retrieve exchange rate data."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TodayOffer(APIView):
    def get(self, request, *args, **kwargs):
        # Fetch today's date
        today = date.today()

        # Fetch promotions with start_date and end_date as today
        today_offers = Promotion.objects.filter(
            start_date=today,
            end_date=today,
            status="active",
            category__in=["common", "promo_code"]
        ).select_related('hotel', 'chalet')

        offers_data = []
        for offer in today_offers:
            # Base data
            offer_data = {
                "id": offer.id,
                "title": offer.title,
                "description": offer.description,
                "start_date": offer.start_date,
                "end_date": offer.end_date,
                "status": offer.status,
                "source": offer.source,
                "promotion_type": offer.promotion_type,
                "category": offer.category,
                "property": offer.hotel.id if offer.hotel else offer.chalet.id if offer.chalet else None,
                "discount_percentage": offer.discount_percentage,
                "free_night_offer": offer.free_night_offer,
                "min_nights_stay": offer.min_nights_stay,
                "promo_code": offer.promo_code,
                "max_uses": offer.max_uses,
                "remaining_uses": offer.uses_left if offer.uses_left is not None else offer.max_uses,
                "minimum_spend": offer.minimum_spend,
            }

            # Conditionally add hotel_name or chalet_name
            if offer.hotel:
                offer_data["hotel_name"] = offer.hotel.name
            if offer.chalet:
                offer_data["chalet_name"] = offer.chalet.name

            offers_data.append(offer_data)

        return Response({"today_offers": offers_data}, status=status.HTTP_200_OK)

class DailyDeals(APIView):
    def get(self, request, *args, **kwargs):
        try:
            current_date = timezone.now().date()
            logger.info(f"Fetching daily deals for date: {current_date}")

            queryset = Promotion.objects.filter(
                Q(start_date__lte=current_date) &
                Q(end_date__gte=current_date) &
                Q(category="common") &
                Q(discount_percentage__isnull=False) &
                Q(status="active")
            ).exclude(
                hotel__isnull=True, chalet__isnull=True
            ).exclude(
                hotel__date_of_expiry__lt=timezone.now().date()
            ).exclude(
                chalet__date_of_expiry__lt=timezone.now().date()
            ).filter(
                    Q(hotel__isnull=False, hotel__room_managements__availability=True, hotel__room_managements__status="active") |
                Q(multiple_hotels__isnull=False) |
                Q(chalet__isnull=False, chalet__is_booked=False, chalet__status="active") |
                Q(multiple_chalets__isnull=False)
            )

            if not queryset.exists():
                logger.info("No daily deals found for today.")
                return Response({"message": "No daily deals available for today."}, status=status.HTTP_404_NOT_FOUND)

            logger.info(f"Found {queryset.count()} daily deal promotions.")

            # Fetch the best deals for hotels
            try:
                best_hotel_queryset = (
                    queryset.filter(hotel__isnull=False)
                    .distinct('hotel')
                    .order_by('hotel', '-discount_percentage')
                )
                logger.info(f"Found {best_hotel_queryset.count()} best hotel deals.")
                best_hotel_data = DailyDealSerializer(best_hotel_queryset, context={'request': request}, many=True).data
            except Exception as e:
                logger.error(f"Error processing best hotel deals: {e}")
                best_hotel_data = []

            # Fetch the best deals for chalets
            try:
                best_chalet_queryset = (
                    queryset.filter(chalet__isnull=False)
                    .distinct('chalet')
                    .order_by('chalet', '-discount_percentage')
                )
                logger.info(f"Found {best_chalet_queryset.count()} best chalet deals.")
                best_chalet_data = DailyDealSerializer(best_chalet_queryset, context={'request': request}, many=True).data
            except Exception as e:
                logger.error(f"Error processing best chalet deals: {e}")
                best_chalet_data = []
            logger.info(f"hotel data :{best_hotel_data}")
            # Construct and return the response
            response_data = {
                "best_hotel": best_hotel_data  + best_chalet_data
            }
            logger.info(f"Successfully processed daily deals.{response_data}")
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Unexpected error in DailyDeals API: {e}")
            return Response({"error": "An unexpected error occurred while fetching daily deals."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)      
    
class CheckPromoCodeView(APIView):
    # permission_classes = [IsAuthenticated]
    # authentication_classes = [JWTAuthentication]

    def post(self, request):
        logger.info(f"\n\nEnter CheckPromoCodeView post request\n\n")
        try:
            data = request.data
            serializer = CheckpromoSerializer(data=data)
        
            if serializer.is_valid(raise_exception=True):
                serialized_room = serializer.data.get('rooms')
                serialized_chalet = serializer.data.get('chalet')
                serialized_promocode = serializer.data.get('promocode')
                serialized_checkin_date = serializer.data.get("checkin_date")
                serialized_checkout_date = serializer.data.get("checkout_date")

                # Global Promo Code Logic
                get_promotion = Promotion.objects.filter(
                    promo_code=serialized_promocode, status="active"
                ).first()

                if serialized_checkin_date == "" or serialized_checkout_date == "":
                    return Response({'message':'checkin date and checkout date are needed.'},status=status.HTTP_400_BAD_REQUEST)
                
                if get_promotion and get_promotion.source == 'admin':
                    total_price = self.calculate_total_price(serialized_room, serialized_chalet,serialized_checkin_date,serialized_checkout_date)
                    total_price_after_discount = self.apply_discount(get_promotion, total_price)

                    logger.info(f"Global PromoCode applied. Total after discount: {total_price_after_discount}")
                    return Response({
                        "message": "Global PromoCode applied successfully.",
                        "promocode":serialized_promocode,
                        "Total after discount": total_price_after_discount
                    }, status=status.HTTP_200_OK)

                # Room-Specific Promo Code Logic
                if serialized_room and serialized_promocode:
                    price_list = []
                    try:
                        checkin_date_obj = datetime.strptime(serialized_checkin_date, '%Y-%m-%d').date()
                        checkout_date_obj = datetime.strptime(serialized_checkout_date, '%Y-%m-%d').date()
                        for rooms in serialized_room:
                            qs = RoomManagement.objects.filter(id=rooms['room_id'])
                            get_room_price = 0
                            if qs:
                                for room in qs:
                                    price_details = calculate_hotel_price(
                                        hotel_id=room.hotel.id,
                                        room_id=room.id,
                                        calculation_logic="average_price",
                                        checkin_date=checkin_date_obj,
                                        checkout_date=checkout_date_obj,
                                    )
                                    print(f"Price details for room {room.id} --- {price_details}")
                                    room_price = price_details.get('calculated_price', 0)  # Get the calculated price
                                    get_room_price += room_price  # Add the room price to the total
                                get_commission_amount = CommissionSlab.objects.filter(
                                    from_amount__lte=get_room_price, to_amount__gte=get_room_price, status="active"
                                ).aggregate(commission_price=Sum('commission_amount')).get('commission_price', 0)

                                # Meal Price
                                if rooms['meal_type_id'] != 0:
                                    for query in qs:
                                        if not query.meals.filter(id=rooms['meal_type_id']).exists():
                                            logger.info(f"Meal not found with ID: {rooms['meal_type_id']}")
                                            return Response({"message": "Meal is not found with this ID"}, status=status.HTTP_404_NOT_FOUND)
                                    get_meal_price = [i.meals.filter(id=rooms['meal_type_id']).aggregate(meal_price=Avg('price')).get('meal_price', Decimal(0.0)) for i in qs]
                                else:
                                    get_meal_price = [Decimal(0.0)]

                                room_with_mealprice = get_meal_price[0] + get_room_price
                                room_with_mealprice_commission = room_with_mealprice + (get_commission_amount or Decimal(0.0))
                                get_tax = [hotel.hotel.country.tax if hotel.hotel.country.tax else Decimal(0.0) for hotel in qs]
                                get_hotel_id = [hotel.hotel.id for hotel in qs]
                                price_list.append(Decimal(room_with_mealprice_commission))
                            else:
                                logger.info(f"Room not found with ID: {rooms['room_id']}")
                                return Response({"message": "Room is not found with this ID"}, status=status.HTTP_404_NOT_FOUND)

                        price = sum(price_list)
                        rooms_price_with_tax = price 
                        print(rooms_price_with_tax)
                        checkin = date.fromisoformat(serialized_checkin_date)
                        checkout = date.fromisoformat(serialized_checkout_date)
                        nights = (checkout - checkin).days
                        total_rooms_price_with_tax = rooms_price_with_tax * nights
                        print(total_rooms_price_with_tax)
                        # Apply Room-Specific Promo Code
                        try:
                            get_hotel_inst = Hotel.objects.get(id=get_hotel_id[0])

                            # Base query: Filter by promo code and active status
                            get_promotion = Promotion.objects.filter(
                                discount_percentage__isnull=False,  
                                hotel=get_hotel_inst,
                                promo_code=serialized_promocode, 
                                status="active"
                            ).first()

                            if not get_promotion:
                                return Response({"message": "This PromoCode is not applicable"}, status=status.HTTP_404_NOT_FOUND)

                            return_status, message = check_promocode_validity(get_promotion, False, {}, request)
                            if return_status:
                                return Response(message, status=status.HTTP_404_NOT_FOUND)

                            # Calculate discount for promo code
                            discount_from_promo_code = (
                                total_rooms_price_with_tax * get_promotion.discount_percentage / 100
                                if get_promotion.discount_percentage else Decimal(0.0)
                            )
                            print(discount_from_promo_code)
                            final_price = total_rooms_price_with_tax - discount_from_promo_code
                            logger.info(f"PromoCode applied with a discount of {discount_from_promo_code}")
                            return Response({
                                "message": "PromoCode applied successfully.",
                                "promocode":serialized_promocode,
                                "Total after discount": final_price
                            }, status=status.HTTP_200_OK)

                        except Hotel.DoesNotExist:
                            logger.info("Hotel not found.")
                            return Response({'message': 'Hotel is not found'}, status=status.HTTP_404_NOT_FOUND)
                        
                    except Exception as e:
                        logger.error(f"Exception: {e}")
                        return Response({'message': 'Something went wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                
                # Chalet-Specific Promo Code Logic
                if serialized_chalet and serialized_promocode:
                    try:
                        get_chalet = Chalet.objects.get(id=serialized_chalet)

                        # Calculate commission
                        commission_amount = CommissionSlab.objects.filter(
                            from_amount__lte=get_chalet.current_price,
                            to_amount__gte=get_chalet.current_price,
                            status="active"
                        ).aggregate(commission_price=Sum('commission_amount')).get('commission_price', 0)
                        get_commission_amount = commission_amount or Decimal(0.0)

                        # Calculate meal price if applicable
                        

                        # Calculate tax
                        get_tax = get_chalet.country.tax if get_chalet.country and get_chalet.country.tax else Decimal(0.0)

                        # Total amount with tax and meal price
                        amount_with_tax = get_chalet.current_price + get_commission_amount + get_tax

                        checkin = date.fromisoformat(serialized_checkin_date)
                        checkout = date.fromisoformat(serialized_checkout_date)
                        nights = (checkout - checkin).days
                        total_amount_with_tax = amount_with_tax * nights
                       

                        # Apply Chalet-Specific Promo Code
                        get_promotion = Promotion.objects.filter(
                            chalet=get_chalet, promo_code=serialized_promocode, status="active",discount_percentage__isnull=False
                        ).first()

                        if not get_promotion:
                            return Response({"message": "This PromoCode is not applicable"}, status=status.HTTP_404_NOT_FOUND)
                        # Validate the promocode
                        return_status, message = check_promocode_validity(get_promotion, False, {}, request)
                        if return_status:
                            return Response(message, status=status.HTTP_404_NOT_FOUND)
                        
                        discount_from_promo_code = (
                                total_amount_with_tax * get_promotion.discount_percentage / 100
                                if get_promotion.discount_percentage else Decimal(0.0)
                            )
                       
                        final_price = total_amount_with_tax - discount_from_promo_code
                        logger.info(f"PromoCode applied with a discount of {discount_from_promo_code}")
                        return Response({
                            "message": "PromoCode applied successfully.",
                            "promocode":serialized_promocode,
                            "Total after discount": final_price
                        }, status=status.HTTP_200_OK)

                    except Chalet.DoesNotExist:
                        logger.info(f"Chalet '{serialized_chalet}' not found.")
                        return Response({'message': 'Chalet is not found'}, status=status.HTTP_404_NOT_FOUND)
            
            else:
                logger.info("Serializer is not valid.")
                return Response({'message': 'Something went wrong'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Exception in CheckPromoCodeView: {e}")
            return Response({'message': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def calculate_total_price(self, rooms, chalet, serialized_checkin_date, serialized_checkout_date):
        """
        Calculate the total price for rooms and chalet, considering weekend pricing and promotions.
        Excludes meals and commission from the calculation.

        Args:
            rooms (list): A list of room dictionaries with 'room_id' and optional 'meal_type_id'.
            chalet (int): Chalet ID (if applicable).
            serialized_checkin_date (str): Check-in date as an ISO string.
            serialized_checkout_date (str): Check-out date as an ISO string.

        Returns:
            Decimal: Total price for the booking.
        """
        price = Decimal(0)

        # Parse check-in and check-out dates
        checkin = date.fromisoformat(serialized_checkin_date)
        checkout = date.fromisoformat(serialized_checkout_date)
        print(f"check in date is -- {checkin} and checkout date is {checkout}")

        if rooms:
            room_totals = {}
            current_date = checkin
            while current_date < checkout:
                is_weekend = current_date.weekday() in (3, 4)  # Thursday=3, Friday=4

                for room in rooms:
                    room_obj = RoomManagement.objects.get(id=room['room_id'])
                    room_total_price = room_totals.get(room_obj.id, Decimal(0))

                    # Determine base price based on weekend or non-weekend
                    base_price = (
                        room_obj.weekend_price.weekend_price
                        if is_weekend and hasattr(room_obj, 'weekend_price') and room_obj.weekend_price
                        else room_obj.price_per_night
                    )


                    # Add daily price to the room's total
                    room_total_price += base_price
                    room_totals[room_obj.id] = room_total_price

                current_date += timedelta(days=1)

            # Sum up all room prices
            price += sum(room_totals.values())

        if chalet:
            chalet_obj = Chalet.objects.get(id=chalet)

            # Initialize the total price for the chalet
            chalet_total_price = Decimal(0)
            current_date = checkin

            # Loop through each day in the date range for the chalet
            while current_date < checkout:
                is_weekend = current_date.weekday() in (3, 4)  # Thursday=3, Friday=4

                # Determine the daily price for the chalet
                if is_weekend and hasattr(chalet_obj, 'weekend_price') and chalet_obj.weekend_price:
                    daily_price = chalet_obj.weekend_price.weekend_price
                else:
                    daily_price = chalet_obj.total_price

                # Add the daily price to the total
                chalet_total_price += daily_price
                current_date += timedelta(days=1)

            # Add the total chalet price to the overall price
            price += chalet_total_price

        
        
        print(f"Total price --- {price}")
        return price


    def apply_discount(self, promotion, total_price):
        discount = (total_price * promotion.discount_percentage) / 100
        return total_price - discount
           


class ComparisonApiView(APIView):
    permission_classes = [AllowEndUserOnly]
    authentication_classes = [JWTAuthentication]
    def get(self, request, property_type):
        
        data={'msg':'Something went wrong',}
        user = request.user
        response_status=status.HTTP_400_BAD_REQUEST
        item_type = property_type
        try:
            if item_type not in ['hotel', 'chalet']:
                return Response({"status": "error", "message": "Type must be either 'hotel' or 'chalet'."}, status=status.HTTP_400_BAD_REQUEST)
            userdetail=Userdetails.objects.get(user=user.id,user__is_deleted=False)
            if userdetail:
                logger.info(f"Userdetail found. Userdetail: {userdetail}")
                try:
                    if item_type == "hotel":
                        comparisons = Comparison.objects.filter(user=userdetail.id, type=item_type, status='active')
                    elif item_type=="chalet":
                        comparisons = Comparison.objects.filter(user=userdetail.id, type=item_type, status='active')
                    logger.info(f"Comparisons found. Comparisons: {comparisons}")
                    if comparisons:
                        serializer = CompareSerializer(comparisons,context={'request': request}, many=True)
                        data['data']=serializer.data
                        data['msg']='Data found'
                        response_status=status.HTTP_200_OK
                    else:
                        data['msg']='Data not found'
                except Comparison.DoesNotExist:
                    logger.info(f"Exception occured in fetching comparisons ")
                    response_status=status.HTTP_404_NOT_FOUND
            else:
                response_status=status.HTTP_404_NOT_FOUND
                data['msg']='comparison not found'
                logger.info(f"comparison not found")
        except Exception as e:
            logger.info(f"Exception occured in comparison view get method. Exception: {e}")
            print(e,"==============")
            data['msg']='User not found'
        logger.info(f"Data in ComparisonApiView Get method. Data: {data}")
        return Response(data, status= response_status)

    
    def post(self, request, property_type):
        logger.info("Post method worked in comparison view.")
        language = request.GET.get('lang', 'en')
        user = request.user
        print(user)
        item_type = property_type
        print(item_type)
        item_id = request.data.get('item_id')
        userid=user.id
        logger.info(f"Payload: item_id-{item_id} item_type- {item_type}  user- {user} ")
        try:
            if item_id and item_type :
                if item_type not in ['hotel', 'chalet']:
                    if language == "en":
                        message = "Type must be either 'hotel' or 'chalet'."
                    else:
                        message = "يجب أن يكون النوع إما 'فندق' أو 'شاليه'."
                    return Response({"status": "error", "message": message}, status=status.HTTP_400_BAD_REQUEST)
                
                if item_type == 'hotel' and not Hotel.objects.filter(id=item_id, approval_status="approved").exists():
                    if language == "en":
                        message = "Hotel with this ID does not exist."
                    else:
                        message = "الفندق بهذا المعرف غير موجود."
                    return Response({"status": "error", "message": message}, status=status.HTTP_400_BAD_REQUEST)
                elif item_type == 'chalet' and not Chalet.objects.filter(id=item_id).exists():
                    if language == "en":
                        message = "Chalet with this ID does not exist."
                    else:
                        message = "الفندق بهذا المعرف غير موجود."
                    return Response({"status": "error", "message": message}, status=status.HTTP_400_BAD_REQUEST)
                try:
                    userdetail_id=Userdetails.objects.get(user__id=userid,user__is_deleted=False)
                    existing_comparisons = Comparison.objects.filter(Q(user=userdetail_id) & (Q(type=item_type)|Q(type=item_type)) & Q(status='active'))
                    if existing_comparisons.count() >= 3:
                        if language == "en":
                            message = "You can only compare up to 3 items."
                        else:
                            message = "يمكنك مقارنة ما يصل إلى 3 عناصر فقط."
                        logger.info(f"You can only compare up to 3 items.")
                        return Response({"status": "error", "message": message}, status=status.HTTP_406_NOT_ACCEPTABLE)
                    elif existing_comparisons.filter((Q(type=item_type) & Q(chalet__id = item_id)) | (Q(type=item_type) & Q(hotel__id = item_id))):
                        if language == "en":
                            message = "item already exists"
                        else:
                            message = "العنصر موجود بالفعل"
                        logger.info(f"{existing_comparisons} ----> already exists")
                        return Response({"status": "error", "message": message}, status=status.HTTP_409_CONFLICT)
                except Userdetails.DoesNotExist:
                    if language == "en":
                        message = "User is not found"
                    else:
                        message = "المستخدم غير موجود"
                    logger.info(f"ERROR 404:  User is not found")
                    return Response({"status": "error", "message": message}, status=status.HTTP_404_NOT_FOUND) 


                comparison_data = {
                    'user':userdetail_id,
                    'created_by': userdetail_id,
                    'modified_by': userdetail_id,
                    'status': 'active',
                    'hotel':None,
                    'chalet':None,
                    'type':None
                }

                if item_type == 'hotel':
                    try:
                        hotel_id=Hotel.objects.get(id=item_id)
                        if hotel_id:
                            comparison_data['hotel'] = hotel_id
                            comparison_data['chalet'] = None  
                            comparison_data['type']='hotel'
                              
                    except Hotel.DoesNotExist:
                        if language == "en":
                            message = "hotel with this ID does not exist"
                        else:
                            message = "الفندق بهذا المعرف غير موجود"
                        logger.info(f"hotel with this ID does not exist") 
                        return Response({"status": "error", "message": message}, status=status.HTTP_404_NOT_FOUND) 
                         
                else:
                    try:
                        chalet_id=Chalet.objects.get(id=item_id)
                        if chalet_id:
                            comparison_data['chalet'] = chalet_id
                            comparison_data['hotel'] = None  
                            comparison_data['type']='chalet'  
                    except Chalet.DoesNotExist:
                        if language == "en":
                            message = "Chalet with this ID does not exist"
                        else:
                            message = "الشاليه بهذا المعرف غير موجود"
                        logger.info(f"Chalet with this ID does not exist")
                        return Response({"status": "error", "message": message}, status=status.HTTP_404_NOT_FOUND)
                comparison = Comparison.objects.create(**comparison_data)
                data = ComparisonSerializer(comparison).data
                if language == "en":
                    message = "Added to Compare"
                else:
                    message = "تمت الإضافة إلى المقارنة."
                return Response({'status':'True','message':message,'data':data}, status=status.HTTP_201_CREATED)
            else:
                if language == "en":
                    message = "id and type needed"
                else:
                    message = "المعرف والنوع مطلوبان."
                return Response({"status": "error", "message": message}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.info(f"Raise Exception ComparisonApiView POST Request. Exception: {e}")
    

    def delete(self, request, property_type):
        language = request.GET.get('lang', 'en')
        item_type = property_type
        item_id = request.data.get('item_id')
        try:
            if item_id and item_type :
                if item_type not in ['hotel', 'chalet']:
                    message = "Type must be either 'hotel' or 'chalet.'" if language == "en" else "يجب أن يكون النوع إما 'فندق' أو 'شاليه'."
                    return Response({"status": "error", "message": message}, status=status.HTTP_400_BAD_REQUEST)
                if item_type == "hotel":
                    try:
                        get_property = Hotel.objects.get(id=item_id)
                    except Hotel.DoesNotExist:
                        message = f"{item_type} with this ID does not exist." if language == "en" else f"{item_type} بهذا المعرف غير موجود."
                        return Response({"status": "error", "message": message}, status=status.HTTP_404_NOT_FOUND)
                elif item_type == "chalet":
                    try:
                        get_property = Chalet.objects.get(id=item_id)
                    except Chalet.DoesNotExist:
                        message = f"{item_type} with this ID does not exist." if language == "en" else f"{item_type} بهذا المعرف غير موجود."
                        return Response({"status": "error", "message": message}, status=status.HTTP_404_NOT_FOUND)
                get_user = Userdetails.objects.filter(user=request.user,user__is_deleted=False).first()
                try:
                    if item_type == "hotel": 
                        get_compare_obj = Comparison.objects.get(type=item_type, hotel=get_property, user=get_user, status="active")
                    elif item_type == "chalet":
                        get_compare_obj = Comparison.objects.get(type=item_type, chalet=get_property, user=get_user, status="active")
                    if get_compare_obj:
                        get_compare_obj.status = "deleted"
                        get_compare_obj.save()
                        logger.info(f"{item_type} removed from your comparision")
                        message = f"{item_type} removed from your comparison." if language == "en" else f"تمت إزالة {item_type} من المقارنة الخاصة بك."
                        return Response({'status':"success", "message":message})
                except Comparison.DoesNotExist:
                    message = f"Comparison of {item_type} - {get_property} by {get_user} does not exist." if language == "en" else f"المقارنة بين {item_type} - {get_property} بواسطة {get_user} غير موجودة."
                    return Response({"status":"error", "message":message})
            else:
                message = "Both fields are mandatory." if language == "en" else "كلا الحقلين مطلوبان."
                return Response({'status':'error','message':message})
        except Exception as e:
            logger.info(f"Exception under ComparisonApiView Delete request. Raise Exception: {e}")

            

       
class AddFundsView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            user_details = Userdetails.objects.get(user__id=request.user.id,user__is_deleted=False)
        except Userdetails.DoesNotExist:
            logger.error("No user details found for the logged-in user.")
            return Response(
                {'error': 'User details not found. Please contact support.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            wallet = Wallet.objects.get(user=user_details, status="active")
        except Wallet.DoesNotExist:
            logger.error(f"No wallet found for user ID {request.user.id}.")
            return Response(
                {'error': 'Wallet not found. Please create a wallet by adding funds.'},
                status=status.HTTP_404_NOT_FOUND
            )
    
        if wallet.balance < 1:
            logger.warning(f"Insufficient balance for user ID {request.user.id}.")
            return Response(
                {"error": "Insufficient balance. Please add funds to your wallet."},
                status=status.HTTP_400_BAD_REQUEST
            )
     
        logger.info(f"User ID {request.user.id} has a balance of {wallet.balance}.")
        return Response(
            {'message': "Success", 'balance': wallet.balance},
            status=status.HTTP_200_OK
        )

    def post(self, request):
        language = request.GET.get('lang', 'en')
        try:
            userdetail_id=Userdetails.objects.get(user__id=request.user.id,user__is_deleted=False)
            wallet = Wallet.objects.get(user=userdetail_id,status="active")
        except Userdetails.DoesNotExist:
            logger.error("No user details found for the logged-in user.")
            return Response({'message':'User details not found. Please contact support.'},status=status.HTTP_400_BAD_REQUEST)
        except Wallet.DoesNotExist:
            wallet = Wallet.objects.create(user=userdetail_id,status="active")
            
        amount = request.data.get("amount")
        lang = request.query_params.get('lang', 'en') 
        
        # Check if amount is provided and is a valid number
        if amount is None:
            return Response({"message": "Amount is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            amount = float(amount)
        except ValueError:
            return Response({"message": "Invalid amount format"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate amount does not exceed 8 digits
        if len(str(int(amount))) > 8:  # Converting to int and string to remove decimals
            return Response({"message": "Amount should not exceed 99999999.00"}, status=status.HTTP_400_BAD_REQUEST)
        if re.search(r"\.\d{4,}", str(amount)):  
            return Response({"message": "Amount should have at most 3 decimal places"},
                            status=status.HTTP_400_BAD_REQUEST)
        
        final_amount= bank_charge_calculation(amount)
        amount = final_amount
        first_name = userdetail_id.user.first_name
        last_name = userdetail_id.user.last_name
        email = userdetail_id.user.email
        phone_number = userdetail_id.contact_number
        logger.info(f"amount:{amount} , first name: {first_name} , email: {email}")
        track_id = generate_track_id()
        domain = request.build_absolute_uri("/")
        logger.info(f"Domain: {domain}")
        user_id=request.user.id
        trandata_to_encrypt = [{
                "amt": str(amount),
                "action": "1",
                "password": settings.NBO_TRANSPORTAL_PASSWORD,
                "id": settings.NBO_TRANSPORTAL_ID,
                "langid":"en",
                "currencycode": "512",
                "trackId": f"{track_id}",
                "udf5":"UDF5",
                "udf3":"UDF3",
                "udf4":"UDF4",
                "udf1":"UDF1",
                "udf2":"UDF2",
                "responseURL": f"{domain}common/wallet-payment-status?status=&user_id={user_id}&lang={language}",
                "errorURL": settings.NBO_ERROR_URL,
                "billingInfo":{
                    "firstName":first_name,
                    "lastName":last_name,
                    "phoneNumber":phone_number,
                    "email":email
                    }
            }]
        try:
            logger.info(f" trandata ecrypted: {trandata_to_encrypt}")
            payment_obj = payment_gateway(request, trandata_to_encrypt,wallet=True)
            if payment_obj:
                logger.info(f" payment objects received from payment gateway function :{ payment_obj}")
                payment_id = payment_obj[0]['result'].split(":")[0]
                payment_url = payment_obj[0]['result'].split(":", 1)[1]
                payment_url_id = f"{payment_url}?PaymentID={payment_id}"
                logger.info(f"payment_url_id: {payment_url_id}")
                return Response({'payment_url':payment_url_id}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "Connection issue"}, status=status.HTTP_400_BAD_REQUEST)                                                  
        except Exception as e:
            print(f"Exception occured in getting payment_obj. Exception {e}")
            logger.info(f"Exception occured in getting payment_obj. Exception {e}")
            return Response({'message':f"Exception occured in getting payment_obj. Exception {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # # Perform transaction to credit the wallet balance using the separated function
        # transaction_id, new_balance = create_transaction(wallet, "credit", int(amount))
        # if transaction_id:
        #     try:
        #         message = f"{amount} has been added  to your wallet'. Your new balance is {new_balance}"
        #         notification = create_notification(user=request.user, notification_type="add_money_to_wallet",message=message, related_wallet=wallet)
        #         logger.info(f"\n\n -------> {amount} has been added  to your wallet'. Your new balance is {new_balance} <------ \n\n")
        #     except Exception as e:
        #         logger.info(f"some thing went wrong in creating notification for money deducting in wallet. Exception: {e}")
        # return Response({
        #     "message": "Funds added successfully", 
        #     "transaction_id": transaction_id, 
        #     "balance": new_balance
        # })
        

class WithdrawFundsView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            userdetail_id=Userdetails.objects.get(user__id=request.user.id,user__is_deleted=False)
            wallet = Wallet.objects.get(user=userdetail_id,status="active")
            
        except Wallet.DoesNotExist:
            return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)

        amount = request.data.get("amount")
        if amount is None or float(amount):
            return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

        if wallet.balance < float(amount):
            return Response({"error": "Insufficient balance"}, status=status.HTTP_400_BAD_REQUEST)

        # Perform transaction to debit the wallet balance using the separated function
        transaction_id, new_balance = create_wallet_transaction(wallet, "debit", float(amount))
        
        return Response({
            "message": "Funds withdrawn successfully", 
            "transaction_id": transaction_id, 
            "balance": new_balance
        })
class featuredview(APIView):
    def get(self, request):
        logger.info("Get method executed in Featured view.")
        data = {}
        try:
            logger.info("Fetching featured objects based on date range.")
            ftr_rq = Featured.objects.filter(valid_from__lte=date.today(), valid_to__gte=date.today())

            if ftr_rq.exists():
                logger.info(f"Featured objects found: {ftr_rq.count()} items : {ftr_rq}")
                serializer = Featuredserializer(ftr_rq, context={'request': request}, many=True)
                logger.info(f"Serialized data: {serializer.data}")
                filtered_data = [item for item in serializer.data if item and item != {}]

                if filtered_data:
                    data['data'] = filtered_data
                    data['msg'] = 'Data found'
                    response_status = status.HTTP_200_OK
                    logger.info("Successfully fetched and serialized featured objects.")
                else:
                    data['msg'] = 'No valid featured data found'
                    response_status = status.HTTP_404_NOT_FOUND
                    logger.warning("No valid featured data found after filtering.")

            else:
                data['msg'] = 'Data not found'
                response_status = status.HTTP_404_NOT_FOUND
                logger.warning("No featured objects found for the given date range.")
            
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}")
            data['msg'] = 'Error occurred while fetching data'
            response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            return Response({"error": "Featured model error", "details": str(e)}, status=response_status)

        return Response(data, status=response_status)

    def post(self, request):
        logger.warning("POST method is not supported in FeaturedView.")
        return Response({
            'message': 'The requested HTTP method is not supported for this resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used.'
        }, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def put(self, request):
        logger.warning("PUT method is not supported in FeaturedView.")
        return Response({
            'message': 'The requested HTTP method is not supported for this resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used.'
        }, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def delete(self, request):
        logger.warning("DELETE method is not supported in FeaturedView.")
        return Response({
            'message': 'The requested HTTP method is not supported for this resource. Please check if the correct HTTP method (GET, POST, PUT, DELETE, etc.) is being used.'
        }, status=status.HTTP_405_METHOD_NOT_ALLOWED)


             
class GenerateReferralTokenAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        
        user = Userdetails.objects.get(user=request.user,user__is_deleted=False)
        try:
            # Generate a new referral token
            referral_token = generate_referral_token(user)  
    
            return Response({
                'message': 'Referral token generated successfully.',
                'token': referral_token
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                'message': 'Failed to generate referral token. Please try again later.',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PromoCodesAPIView(APIView):
    def get(self, request, *args, **kwargs):
        # Fetch all promo codes
        promo_codes = Promotion.objects.filter(
            status="active",
            category="promo_code"
        ).select_related('hotel', 'chalet')

        promo_data = []
        for promo in promo_codes:
            # Logic to handle remaining uses
            remaining_uses = promo.uses_left if promo.uses_left is not None else promo.max_uses

            promo_data.append({
                "id": promo.id,
                "valid_from": promo.start_date,
                "valid_to": promo.end_date,
                "status": promo.status,
                "source": promo.source,
                "property": promo.hotel.id if promo.hotel else promo.chalet.id if promo.chalet else None,
                "code": promo.promo_code,
                "description": promo.description,
                "max_users": promo.max_uses,
                "remaining_uses": remaining_uses,
            })

        return Response({"promo_codes": promo_data}, status=status.HTTP_200_OK)


class BookingCalculationAPIView(APIView):
    def post(self, request):
        if not (data := request.data):
            logger.error("No data provided in the request.")
            return Response({"message": "Invalid data"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = BookingCalculationSerializer(data=data)
        if not serializer.is_valid():
            logger.error("Invalid data received: %s", serializer.errors)
            return Response({"message": "Invalid data"}, status=status.HTTP_400_BAD_REQUEST)
        serialized_room = serializer.data.get("rooms")
        if serialized_room and (count := request.data.get("count", 1)) > 1:
            if len(serialized_room) == 1:
                serialized_room = serialized_room * count
        serialized_chalet = serializer.data.get("chalet")
        promotion_id = serializer.data.get("promotion_id")
        promo_code = serializer.data.get("promocode") 
        serialized_checkin_date = serializer.data.get("checkin_date")
        serialized_checkout_date = serializer.data.get("checkout_date")
        if serialized_room and serialized_chalet:
            logger.warning("Both rooms and chalet data provided; cannot process both simultaneously.")
            return Response(
                {"message": "Cannot calculate for both rooms and chalets simultaneously"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            if serialized_room:
                return self._calculate_room_price(
                    serialized_room, serialized_checkin_date, serialized_checkout_date, promo_code, request
                )
            elif serialized_chalet:
                return self._calculate_chalet_price(
                    serialized_chalet, serialized_checkin_date, serialized_checkout_date, promo_code, request
                )
        except Exception as e:
            logger.error(f"Unexpected error occurred in BookingCalculationAPIView. Exception: {e}")
            return Response(
                {"message": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # def _round_to_two_decimal_places(self, value):
    #     """Helper function to round a value to two decimal places."""
    #     if isinstance(value, (Decimal, float, int)):
    #         return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    #     return value
    def _truncate_to_three_decimal_places(self,value):
        """Helper function to truncate a value to exactly three decimal places without rounding up."""
        if isinstance(value, (Decimal, float, int)):
            return Decimal(value).quantize(Decimal('0.000'), rounding=ROUND_DOWN)
        return value

    def _calculate_room_price(self, rooms, checkin_date, checkout_date, promo_code, request):
        price_list = []
        data = {}
        try:
            for room in rooms:
                qs = RoomManagement.objects.filter(id=room["room_id"])
                if not qs.exists():
                    logger.error(f"Room not found with ID: {room['room_id']}")
                    return Response({"message": "Room not found"}, status=status.HTTP_404_NOT_FOUND)

                room_obj = qs.first()
                hotel = room_obj.hotel
                checkin_date_obj = datetime.strptime(checkin_date, '%Y-%m-%d').date()
                checkout_date_obj = datetime.strptime(checkout_date, '%Y-%m-%d').date()
                price_details = calculate_hotel_price(
                    hotel_id=hotel.id,
                    room_id=room_obj.id,
                    calculation_logic="average_price",
                    checkin_date=checkin_date_obj,
                    checkout_date=checkout_date_obj,
                    include_details=True
                )
                print(f"Room price ---- {price_details}")
                room_price = price_details.get('calculated_price', 0)

                # Calculate meal price and meal tax
                meal_price = Decimal(0.00)
                meal_tax = Decimal(0.0)
                meal_type_id = room.get("meal_type_id")
                if meal_type_id and meal_type_id != 0:
                    meal = room_obj.meals.filter(id=meal_type_id).first()
                    if meal:
                        meal_price = meal.price
                        # Fetch active meal taxes for the room
                        meal_taxes = MealTax.objects.filter(room=room_obj, status="active", is_deleted=False)
                        meal_tax_percentage = meal_taxes.aggregate(total_tax=Sum('percentage'))['total_tax'] or Decimal(0)
                        meal_tax = meal_price * (meal_tax_percentage / 100)

                # Append a tuple of (room_price, meal_price, meal_tax) to price_list
                price_list.append((room_price, meal_price, meal_tax))

            # Calculate hotel tax
            tax_percentage = HotelTax.objects.filter(
                hotel=hotel, status="active", is_deleted=False
            ).aggregate(total_tax=Sum('percentage'))['total_tax'] or Decimal(0)

            # Total room price (without meal-related costs)
            total_room_price_without_meal = sum([room_price for room_price, _, _ in price_list])
            # Total meal price and meal tax
            total_meal_price = sum([meal_price for _, meal_price, _ in price_list])
            total_meal_tax = sum([meal_tax for _, _, meal_tax in price_list])

            nights = (date.fromisoformat(checkout_date) - date.fromisoformat(checkin_date)).days
            print(f"nights is -- {nights}")

            # Calculate base price before tax (only room price)
            cost_of_rooms_price = total_room_price_without_meal * nights

            # Apply discount ONLY to the room price (excluding meal price and meal tax)
            discounted_price, discount, offer_percentage, promo_message, promo_code_applied = self._apply_best_promotion(
                promo_code, total_room_price_without_meal, request, hotel.id, property_type='hotel'
            )

            # Apply hotel tax AFTER discount (only on the discounted room price)
            tax_amount = discounted_price * (tax_percentage / 100)

            # Final price = discounted room price + hotel tax + meal price + meal tax
            final_price = (discounted_price + tax_amount + total_meal_price + total_meal_tax)*nights

            # Prepare response data
            data = {
                "property_price_with_days": self._truncate_to_three_decimal_places(cost_of_rooms_price),
                "tax_and_services": self._truncate_to_three_decimal_places(tax_amount * nights),
                "meal_price": self._truncate_to_three_decimal_places(total_meal_price * nights),
                "meal_tax": self._truncate_to_three_decimal_places(total_meal_tax * nights),
                "total_price_with_tax": self._truncate_to_three_decimal_places(final_price + discount * nights),
                "discount_price": self._truncate_to_three_decimal_places(discount * nights),
                "offer_percentage": self._truncate_to_three_decimal_places(offer_percentage),
                "total_amount_to_be_paid": self._truncate_to_three_decimal_places(final_price),
                "promo_code_applied": promo_code_applied,
                "promo_code": promo_code,
            }

            if promo_message is not None:
                data["message"] = promo_message  # Add message only if it's not None

            logger.info("Room price calculated successfully: %s", data)
            return Response({"message": "Data calculated successfully", "data": data}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error during room price calculation. Exception: {e}")
            return Response(
                {"message": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    def _calculate_chalet_price(self, chalet_id, checkin_date, checkout_date, promo_code, request):
        data = {}
        try:
            chalet = Chalet.objects.get(id=chalet_id)
            
            # Initialize variables for price calculation
            total_price_without_tax = Decimal(0)
            current_date = date.fromisoformat(checkin_date)
            end_date = date.fromisoformat(checkout_date)

            # Loop through each day in the date range
            while current_date < end_date:
                is_weekend = current_date.weekday() in (3, 4)  # Thursday=3, Friday=4
                
                # Determine the daily price (weekend or normal price)
                if is_weekend and hasattr(chalet, 'weekend_price') and chalet.weekend_price:
                    daily_price = chalet.weekend_price.weekend_price
                else:
                    daily_price = chalet.current_price

                # Add the daily price to the total
                total_price_without_tax += daily_price

                # Move to the next day
                current_date += timedelta(days=1)


            # Apply the best promotion (Discount applied before tax)
            discounted_price, discount, offer_percentage, promo_message, promo_code_applied = self._apply_best_promotion(
                promo_code, total_price_without_tax, request,  chalet.id, property_type='chalet'
            )


            # Calculate tax AFTER discount
            tax_percentage = ChaletTax.objects.filter(
                chalet=chalet, status="active", is_deleted=False
            ).aggregate(total_tax=Sum('percentage'))['total_tax'] or Decimal(0)

            tax_amount = discounted_price * (tax_percentage / 100)

            # Final price after tax
            final_price = discounted_price + tax_amount

            # Prepare the response data
            data = {
                "property_price_with_days": self._truncate_to_three_decimal_places(total_price_without_tax),
                "discount_price": self._truncate_to_three_decimal_places(discount),
                "offer_percentage": self._truncate_to_three_decimal_places(offer_percentage),
                "tax_and_services": self._truncate_to_three_decimal_places(tax_amount),
                "total_price_with_tax": self._truncate_to_three_decimal_places(final_price + discount),
                "total_amount_to_be_paid": self._truncate_to_three_decimal_places(final_price),
                "promo_code_applied": promo_code_applied,
                "promo_code": promo_code,
            }
            if promo_message is not None:
                data["message"] = promo_message  # Add message only if it's not None

            logger.info("Chalet price calculated successfully: %s", data)
            return Response({"message": "Data calculated successfully", "data": data}, status=status.HTTP_200_OK)

        except Chalet.DoesNotExist:
            logger.error(f"Chalet not found with ID: {chalet_id}")
            return Response({"message": "Chalet not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error during chalet price calculation. Exception: {e}")
            return Response(
                {"message": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    
    def _apply_best_promotion(self, promo_code, total_price, request, property_id=None, property_type=None):
        """
        Apply the best promotion based on the property type (hotel or chalet).
        Promo codes created by hotel owners can only be used for their specific hotel.

        :param promo_code: The promo code provided by the user (optional).
        :param total_price: The total price before applying promotions.
        :param property_id: The ID of the hotel or chalet (optional).
        :param property_type: The type of property ('hotel' or 'chalet').
        :return: Tuple containing final price, discount, offer percentage, promo message, and promo code applied flag.
        """
        try:
            # Base query for active promotions within the date range and minimum spend
            language = request.GET.get('lang','en')
            applicable_promotions = Promotion.objects.filter(
                status="active",
                start_date__lte=date.today(),
                end_date__gte=date.today(),
                minimum_spend__lte=total_price,
            )
            logger.info(f"----{total_price}")
            logger.info(applicable_promotions)

            # Always include global promotions (admin-created, no hotel or chalet associated)
            global_promotions = applicable_promotions.filter(
                hotel_id__isnull=True, chalet_id__isnull=True, source='admin'
            )

            # Filter property-specific promotions if a property ID and type are provided
            property_specific_promotions = Promotion.objects.none()  # Empty queryset by default
            if property_id and property_type:
                if property_type == 'hotel':
                    global_promotions = applicable_promotions.filter(Q(hotel=property_id) | Q(multiple_hotels=property_id),status='active', category="common")
                    property_specific_promotions = applicable_promotions.filter(
                        Q(hotel_id=property_id) | Q(multiple_hotels__id=property_id))
                elif property_type == 'chalet':
                    global_promotions = applicable_promotions.filter(Q(chalet=property_id) | Q(multiple_chalets=property_id),status='active', category="common")
                    property_specific_promotions = applicable_promotions.filter(
                        Q(chalet_id=property_id) | Q(multiple_chalets__id=property_id))
            logger.info(f"==== global {global_promotions}")
            logger.info(f"==== property {property_specific_promotions}")

            # Combine global and property-specific promotions
            all_promotions = (global_promotions | property_specific_promotions).distinct()
            logger.info(f"======={all_promotions}")

            # Rest of the logic remains the same...
            best_promotion = None
            return_status = False
            message = {}

            promo_applied = False  # Track if the promo code was successfully applied
            promo_message = ""
            promo_code_applied = False  # Boolean flag to indicate if promo code was applied

            if promo_code:
                # Check if the promo code is valid and applicable
                best_promotion = Promotion.objects.filter(
                    promo_code=promo_code, status="active"
                ).first()
                logger.info(f"====={ best_promotion}")

                if best_promotion:
                    # Validate the promo code's scope
                    if best_promotion.source == 'hotel' and property_type == 'hotel':
                        # Promo code created by a hotel owner can only be used for their specific hotel
                        if best_promotion.hotel_id != property_id:
                            promo_message = "This promo code is not valid for the selected hotel." if language == "en" else "رمز الخصم هذا غير صالح للفندق المحدد."
                            best_promotion = None  # Ignore the invalid promo code
                        else:
                            # Promo code is valid for this hotel
                            return_status, message = check_promocode_validity(best_promotion, return_status, message, request)
                            if not return_status:
                                promo_applied = True  # Promo code is valid, so apply it
                                promo_code_applied = True  # Set the boolean flag to True
                    elif best_promotion.source == 'admin':
                        # Admin-created promo codes can be used globally or for specific properties
                        return_status, message = check_promocode_validity(best_promotion, return_status, message, request)
                        if not return_status:
                            promo_applied = True  # Promo code is valid, so apply it
                            promo_code_applied = True  # Set the boolean flag to True
                    elif best_promotion.source == 'chalet' and property_type == 'chalet':
                        # Promo code created by a hotel owner can only be used for their specific hotel
                        if best_promotion.chalet_id != property_id:
                            promo_message = "This promo code is not valid for the selected chalet." if language == "en" else "رمز الخصم هذا غير صالح للفندق المحدد."
                            best_promotion = None  # Ignore the invalid promo code
                        else:
                            # Promo code is valid for this hotel
                            return_status, message = check_promocode_validity(best_promotion, return_status, message, request)
                            if not return_status:
                                promo_applied = True  # Promo code is valid, so apply it
                                promo_code_applied = True  # Set the boolean flag to True
                    else:
                        # Promo code is not applicable (e.g., created by a chalet owner for a hotel)
                        promo_message = "This promo code is not valid for the selected property." if language == "en" else "رمز الخصم هذا غير صالح للعقار المحدد."
                        best_promotion = None  # Ignore the invalid promo code

                else: 
                    promo_message = "Invalid promo code." if language == "en" else "رمز الخصم غير صالح."
                    best_promotion = None  # Ignore the invalid promo code

            # If no valid promo code is applied, find the best applicable promotion
            if not promo_applied:
                best_promotion = all_promotions.order_by("-discount_percentage").first()
                logger.info(f"=====bestpromotion goint to apply ==={best_promotion}")

            if best_promotion:
                final_price = discount_cal(best_promotion, total_price)
                discount = total_price - final_price
                logger.info(f"Best promotion applied: {best_promotion.title}")
                if promo_applied:
                    if language == "en":
                        message = f"Promo code '{promo_code}' applied successfully."
                    else:
                        message = f"تم تطبيق رمز الخصم '{promo_code}' بنجاح."
                    return final_price, discount, best_promotion.discount_percentage, message, promo_code_applied
                elif promo_message:  # If a promo code was provided but not applied
                    return final_price, discount, best_promotion.discount_percentage, f"{promo_message} Best available promotion '{best_promotion.title}' applied.", promo_code_applied
                return final_price, discount, best_promotion.discount_percentage, None, promo_code_applied

            logger.info("No applicable promotion found.")
            message = "No applicable promotion found." if language == "en" else "لم يتم العثور على عرض ترويجي مناسب."
            return total_price, Decimal(0.0), 0, "No applicable promotion found.", promo_code_applied

        except Exception as e:
            logger.error(f"Error during promotion application. Exception: {e}")
            return total_price, Decimal(0.0), 0, "An error occurred while applying the promotion.", False
        
class NotificationAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        user = request.user
        try:
            get_user_notifications = Notification.objects.filter(recipient=user).order_by('-created_at')
            if get_user_notifications:
                serializer = NotificationSerialiser(get_user_notifications, many=True)
                logger.info(f"\n\n--------> serializer data: {serializer.data} <---------\n\n")
                return Response({'message':f"Notification fetched successfully",'data':serializer.data},status=status.HTTP_200_OK)
            logger.info(f"\n\n--------> Notification is not available for logged in user {user} <---------\n\n")
            return Response({'message':f"Notification not found",'data':serializer.data},status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.info(f"<------ \n\nException raised in NotificationAPIView. Exception: {e}\n\n----->" )
            return Response({'message':'Something went wrong'})
        
class BookingDetailApiView(APIView):
    permission_classes = [AllowEndUserOnly]
    authentication_classes = [JWTAuthentication]
    def get(self, request, *args, **kwargs):
        try:
            logger.info(f"\n\nBookingDetailApiView Get method worked \n\n")
            type = request.GET.get('type')
            logger.info(type)
            id = kwargs.get('id')
            booking = None
            if not id:
                logger.info(f"\n\n Id is not passed. Kinldy pass the if in the api")
                return Response({'message':'Id is not passed. kindly pass the ID'},status=status.HTTP_404_NOT_FOUND)
            user = request.user
            # Fetching Userdetail obj
            try:
                user_detail = Userdetails.objects.get(user=user,user__is_deleted=False)
            except Userdetails.DoesNotExist:
                logger.info(f"user Detail is not found. User: {user} ({user.id})")
                return Response({'message':'User Detail not found'},status=status.HTTP_404_NOT_FOUND)
            if type == "hotel":
                #Fetching Booking Obj
                try:
                    booking = Booking.objects.get(id=id, user=user_detail, is_deleted=False)
                    logger.info(booking)
                    serializer = BookingDetailModelSerializer(booking, context={"request": request})
                    logger.info(f"\n\nserialiser -------- {serializer.data}\n\n ")
                    update_booking_status()
                    return Response({'message':'data fetched successfully','data':serializer.data},status=status.HTTP_200_OK)
                except Booking.DoesNotExist:
                    logger.info(f"\n\n Exception occured in hotel fetching Booking obj.\n\n")  
                    return Response({'message':f'Hotel Booking is not for the user. User: {user} ({user.id})'})
            else:
                try:
                    booking = ChaletBooking.objects.get(id=id, user=user_detail, is_deleted=False)
                    serializer = ChaletBookingDetailModelSerializer(booking, context={"request": request})
                    logger.info(f"\n\nserialiser -------- {serializer.data}\n\n ")
                    update_chaletbooking_status()
                    return Response({'message':'data fetched successfully','data':serializer.data},status=status.HTTP_200_OK)
                except ChaletBooking.DoesNotExist:
                    logger.info(f"\n\n Exception occured in fetching chalet Booking obj.\n\n")  
                    return Response({'message':f'Chalet Booking is not for the user. User: {user} ({user.id})'})
        except Exception as e:
            logger.info(f"\n\n Exception occures in get method BookingDetailApiView. Exception: {e}")
            return Response({'message':'Something went wrong.'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        # return Response({'message':'Something went wrong.'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class PaymentsAcceptedApiView(APIView):
    permission_classes = [AllowEndUserOnly]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            logger.info("Payment Detail API View POST is working")

            type = request.data.get('type')
            id = request.data.get('id')
            language = request.query_params.get('lang', 'en')  # Default to English if not provided

            if type not in ['hotel', 'chalet']:
                return Response(
                    {"status": "error", "message": "Type must be either 'hotel' or 'chalet'."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user = request.user
            
            try:
                user_detail = Userdetails.objects.get(user=user,user__is_deleted=False)
            except Userdetails.DoesNotExist:
                logger.info(f"User Detail not found. User: {user} ({user.id})")
                return Response({'message': 'User Detail not found'}, status=status.HTTP_404_NOT_FOUND)

            try:
                if type == 'hotel':
                    item = Hotel.objects.get(id=id)
                    logger.info(f"Hotel found at PaymentDetailApi: {item}") 
                else:  
                    item = Chalet.objects.get(id=id)
                    logger.info(f"Chalet found at PaymentDetailApi: {item}")
            except Exception as e:
                logger.error(f"Error Occurred: {str(e)}")
                return Response({'message': f'{type.capitalize()} Detail not found'}, status=status.HTTP_404_NOT_FOUND)
            payment_details = get_payment_details(type, item,language)
            
            if payment_details:
                return Response({'message': 'Data fetched successfully', 'data': payment_details}, status=status.HTTP_200_OK)
            else:
                return Response({'message': 'Data not found'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.error(f"An Exception occurred: {e}")
            return Response({'message': 'Something went wrong.'}, status=status.HTTP_406_NOT_ACCEPTABLE)



# from django.shortcuts import redirect
# from django.http import HttpResponse
# import user_agents

# class HotelDetailsRedirect(View):
#     def get(self, request, id):
#         hotel_id = id
#         user_agent = user_agents.parse(request.META.get('HTTP_USER_AGENT', ''))

#         # Deep link format for your Flutter app
#         deep_link = f"yourapp://hotel.details/{hotel_id}"

#         # Play Store & App Store links (for users who don't have the app)
#         playstore_link = "https://play.google.com/store/apps/"
#         appstore_link = "https://apps.apple.com/app/"

#         if user_agent.is_mobile:
#             if 'Android' in user_agent.os.family:
#                 # Android Intent to open the app
#                 return redirect(f"intent://hotel.details/{hotel_id}#Intent;scheme=yourapp;package=com.example.yourapp;end;")
#             elif 'iOS' in user_agent.os.family:
#                 # iOS direct deep link
#                 return redirect(deep_link)

#         # If accessed from a desktop or unsupported device
#         return HttpResponse("Please open this link from a mobile device.")


class DeleteAccountAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    def delete(self, request):
        user = request.user
        if user.is_deleted:
            return Response({'message': 'Account already deleted.'}, status=status.HTTP_400_BAD_REQUEST)

        user.is_deleted = True
        user.is_active = False
        user.save()

        return Response({'message': 'Account deleted successfully.'}, status=status.HTTP_200_OK)
    