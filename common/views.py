
from decimal import Decimal
import json
from django.conf import settings
from django.http import JsonResponse
from django.db import connection
import logging
from django.shortcuts import redirect, render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from user.models import Userdetails, Wallet
from api.function import  create_Online_wallet_transaction
from common.utils import create_notification, payment_status

from common.function import update_transaction_status, update_vendor_earnings
from api.views import CreatePayment
from chalets.models import Transaction,ChaletBooking
from vendor.models import Booking

logger = logging.getLogger('lessons')

def health_check(request):
    try:
        # Checking database connection status
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "healthy"}, status=200)

    except Exception as e:
        # If there's any issue (like DB connection), return error as Database connection failed and logging the actual error to logs
        logger.info(f"Exception occured in health_check. Exception : {e}")
        return JsonResponse({"status": "unhealthy", "error": "Database connection failed"}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class PaymentStatusView(View):
    template = "payment-status.html"
    def get(self, request):
        language = request.GET.get('lang', 'en')
        return render(request, self.template,{'language': language})
    def post(self, request):
        
        language = request.GET.get('lang','en')
        decrypted_trandata = payment_status(request)
        print(decrypted_trandata,"=======decrypted_trandata========")
        if decrypted_trandata != "Expired":
            for data in decrypted_trandata:
                booking_id = data.get("udf1")  # Booking ID
                transaction_id = data.get("udf2")  # Transaction ID
                card_type = data.get("cardType")  # Card Type
                # booking = Booking.objects.get(id=booking_id)
                print(f"Booking ID: {booking_id}, Transaction ID: {transaction_id}, Card Type: {card_type}")
                payment_type = "Credit Card" if card_type == "Credit" else "Debit Card"
                if data["result"] == "CAPTURED":
                    try:
                        update_transaction_status(transaction_id=transaction_id, transaction_status="completed", payment_type_name=payment_type)
                        update_vendor_earnings(transaction_id=transaction_id, card_type=card_type)
                        print(f"\n\n\n\n\n\n===================\n\n\n\n\n\n\n\n\n\n")
                        try:
                            transaction = Transaction.objects.get(transaction_id=transaction_id)
                            total_amount = transaction.amount
                            booking = None
                            try:
                                booking = Booking.objects.get(transaction=transaction)
                                hotel = booking.hotel 
                            except Exception as e:
                                try:
                                    booking = ChaletBooking.objects.get(transaction=transaction)
                                    hotel = booking.chalet 
                                except Exception as e:
                                    logger.info(f"Exception occurred in getting booking associated with transaction. Exception : {e}")
                            if booking:
                                print(f"\n\n\n\n\n\n\n{booking}\n\n\n\n\n\n\n\n\n")
                                create_payment_instance = CreatePayment() 
                                property_name = hotel.name
                                booking_id = booking.booking_id
                                message = f"Your booking has been confirmed for the {hotel.__class__.__name__.lower()} {property_name}"
                                message_arabic = f"تم تأكيد حجزك لـ {hotel.__class__.__name__.lower()} {property_name}"
                                notification_type = "booking_new"
                                source = hotel.__class__.__name__.lower()
                                related_booking = booking
                                message_vendor = f"Booking {booking_id} has been confirmed"
                                message_vendorarabic = f"تم تأكيد الحجز {booking_id}"
                                try:
                                    # Attempt to create notification
                                    create_notification(user=related_booking.user.user, notification_type=notification_type, message=message, message_arabic=message_arabic, source=source, related_booking=related_booking)
                                    create_notification(user=hotel.vendor.user, notification_type=notification_type, message=message_vendor, message_arabic=message_vendorarabic, source=source, related_booking=related_booking)
                                except Exception as e:
                                    # Log the error but do not raise it
                                    logger.error(f"Error creating notification: {str(e)}")
                                try:
                                    email_context = create_payment_instance.send_confirmation_email(booking, hotel, total_amount, payment_type)
                                except Exception as e:
                                    logger.info(f"Exception occurred in sending confirmation main. Exception : {e}")
                        except Exception as e:
                            logger.info(f"Exception occurred in sending mail. Exception: {e}")
                        return redirect(f'/common/payment-status?status=success&lang={language}')
                    except Exception as e:
                        logger.error(f"Exception occured while updating transaction status for successfull online payment. Exception: {e}")
                else:
                    try:
                        print(f"Enter elase")
                        update_transaction_status(transaction_id=transaction_id, transaction_status="failed", payment_type_name=payment_type)
                        return redirect(f'/common/payment-status?status=failed&lang={language}')
                    except Exception as e:
                        logger.error(f"Exception occured while updating transaction status for failed online payment. Exception: {e}")
        return redirect(f'/common/payment-status?status=failed&lang={language}') 
@method_decorator(csrf_exempt, name='dispatch')
class WalletPaymentStatusView(View):
    template = "payment-status.html"
    def get(self, request):
        language = request.GET.get('lang', 'en')
        return render(request, self.template,{'language': language})
    def post(self, request):
        user_id=request.GET.get('user_id')
        language = request.GET.get('lang','en')
        decrypted_trandata = payment_status(request, wallet=True)
        amount = decrypted_trandata[0]['amt']
        for data in decrypted_trandata:
            if data["result"] == "CAPTURED":
                try:
                    logger.info("Payment is success")
                    userdetail_id=Userdetails.objects.get(user__id=int(user_id) )
                    user_data=userdetail_id.user
                    wallet = Wallet.objects.get(user=userdetail_id,status="active")
                except Userdetails.DoesNotExist:
                    logger.error("No user details found for the logged-in user.")
                    
                except Wallet.DoesNotExist:
                    wallet = Wallet.objects.create(user=userdetail_id,status="active")
                transaction_id, new_balance = create_Online_wallet_transaction(wallet, "credit",Decimal(str(amount)))
                if transaction_id:
                    try:
                        logger.info(f"user:{user_data}")
                        message = f"{amount} has been added  to your wallet'. Your new balance is {new_balance}"
                        message_arabic = f"تمت إضافة {amount} إلى محفظتك. رصيدك الجديد هو {new_balance}."
                        notification = create_notification(user=user_data, notification_type="add_money_to_wallet",message=message,message_arabic=message_arabic, related_wallet=wallet)
                        logger.info(f"\n\n -------> {amount} has been added  to your wallet'. Your new balance is {new_balance} <------ \n\n")
                        return redirect(f'/common/wallet-payment-status?status=success&user_id={user_id}&lang={language}')
                    except Exception as e:
                        logger.info(f"something went wrong in creating notification for money crediting in wallet. Exception: {e}")
            else:
                return redirect(f'/common/wallet-payment-status?status=failed&user_id={user_id}&lang={language}')
            
