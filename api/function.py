import logging
import random
import uuid
import re
from datetime import date,datetime,timedelta
from decimal import Decimal,ROUND_DOWN
from django.db.models import Q, Min,Sum
from django.utils.timezone import now
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from Bookingapp_1969 import settings
from twilio.rest import Client
from user.models import WalletTransaction,OnlineWalletTansaction
from vendor.models import Hotel, HotelTax,RoomManagement,Bookedrooms,HotelAcceptedPayment,RoomRefundPolicy,RefundPolicy,MealPrice,MealTax
from chalets.models import Chalet, ChaletTax,Promotion,ChaletAcceptedPayment
from common.models import Transaction,PaymentType
from django.db.models import OuterRef, Subquery

logger = logging.getLogger('lessons')
# from vendor.models import RecentReview


def send_email(request, user, first_name):
    get_otp = otp_generator()
    request.session['otp'] = get_otp
    subject = f'One Time Password (OTP) for email verifiction'
    recipient_list = [user.email]
    
    context = {
        'otp':get_otp,
        'user_id':user.id,
        'first_name':first_name,
        'user_email': user.email
    }
    print(context,"======context=======")
    html_content = render_to_string('email_verification.html', context)
    
    try:
        for recipient_email in recipient_list:
            email = EmailMessage(
                'OTP Verification',  
                html_content,  
                settings.EMAIL_HOST_USER,
                [recipient_email]  
            )
            email.content_subtype = 'html'  
            email.send()
            print(email,"========++++++++++++")
            
    except Exception as e:
        print(e,"================++++++++++")
    
    return context, get_otp

def send_sms_otp(mobile_number, otp):
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        body=f'Your OTP code is {otp}',
        from_=f'+1{settings.TWILIO_PHONE_NUMBER}',
        to=f'+91{mobile_number}'
    )
    return message
def otp_generator():
    start_int = 1000
    end_int = 10000
    random_number = random.randint(start_int, end_int)
    return random_number
    


def format_name(name):
    formatted_name = re.sub(r'(?<!^)(?=[A-Z0-9])', ' ', name)
    return formatted_name


def discount_cal(get_promotion,total_rooms_price_with_tax):
    if get_promotion.discount_percentage:
        discount_percentage = get_promotion.discount_percentage
        if discount_percentage:
            discount_amount = total_rooms_price_with_tax * (discount_percentage / 100)
            total_rooms_price_with_tax -= discount_amount
            return total_rooms_price_with_tax
    else:
        print(total_rooms_price_with_tax)
        discount_value = get_promotion.discount_value
        if discount_value:
            total_rooms_price_with_tax -= discount_value
            return total_rooms_price_with_tax


def check_promocode_validity(get_promotion,return_status,message, request):
    language = request.GET.get("lang","en")
    if not get_promotion:
        logger.info(f"This PromoCode is not applicable")
        return_status = True
        message['message'] = "This PromoCode is not applicable" if language == "en" else "رمز الخصم هذا غير قابل للتطبيق."
    elif get_promotion.max_uses < 1:
        return_status = True
        logger.info(f"Promo Code limit has been completed")
        message['message'] = "Promo Code limit has been completed" if language == "en" else "تم الوصول إلى الحد الأقصى لاستخدام رمز الخصم."
    elif get_promotion.end_date < date.today():
        return_status = True
        logger.info(f"Promocode validity hasd expired")
        message['message'] = "Promocode validity hasd expired" if language == "en" else "انتهت صلاحية رمز الخصم."
    elif get_promotion.start_date > date.today():
        return_status = True
        logger.info(f"Promocode is not yet valid for this date. PLease wait we will update you")
        message['message'] = "Promocode is not yet valid for this date. PLease wait we will update you" if language == "en" else "رمز الخصم غير صالح لهذا التاريخ بعد. يرجى الانتظار، وسنقوم بإبلاغك."
    return return_status,message
def delete_booking(get_booked_rooms,booking):
    """
    Reverts room availability for the selected booked rooms."""
    try:
        for booked_room in get_booked_rooms:
            booked_room.room.availability = True
            booked_room.room.save()
            booked_room.save()
        booking.delete()
        return True
    except Exception as e:
        logger.error(f"Error while deleting booking: {e}")
        return False

def create_wallet_transaction(wallet, transaction_type, amount):
    """
    Helper function to create a transaction and update the wallet balance.
    """
    # Generate a unique transaction ID
    transaction_id = str(uuid.uuid4())
    amount = Decimal(str(amount))
    wallet.balance = Decimal(str(wallet.balance))

    # Create a new transaction record
    WalletTransaction.objects.create(
        wallet=wallet,
        transaction_id=transaction_id,
        transaction_type=transaction_type,
        amount=amount
    )

    # Update the wallet balance based on transaction type
    if transaction_type == 'credit':
        wallet.balance += amount
    elif transaction_type == 'debit':
        wallet.balance -= amount

    wallet.save()

    return transaction_id, wallet.balance



def create_cash_transaction():
    """
    Helper function to create a transaction .
    """
    # Generate a unique transaction ID
    transaction_id = str(uuid.uid4())
    return transaction_id
def format_validity(validity):
    """Convert the validity duration into total hours."""
    if validity:
        total_seconds = validity.total_seconds()
        total_hours = total_seconds // 3600  # Divide by 3600 seconds (1 hour)
        return int(total_hours)
def Check_payment_type(transaction):
    logger.info(f"Transaction received : {transaction}")
    try:
        transaction_received=transaction
        if transaction_received:
            try:
                get_transaction=Transaction.objects.get(id=transaction_received.id)
                logger.info(f"Transaction found : {get_transaction}")
                PaymentType=get_transaction.payment_type
                if PaymentType.is_refundable =='refundable':
                    logger.info("Transaction done is Refundable")
                    return True
                else:
                    logger.warning("Transaction done is Not Refundable")
                    return False
            except Transaction.DoesNotExist:
                logger.error(f"Transaction not found : {transaction}")
    except Exception as e:
        logger.warning(f"An error occured at fetching transaction: {e}")
    return False
# def Calculate_room_refund(room_price,meal_price,Meal_tax,Hotel_tax,nights,discount):
#     room_price = Decimal(str(room_price))
#     meal_price = Decimal(str(meal_price))
#     Meal_tax = Decimal(str(Meal_tax))
#     Hotel_tax = Decimal(str(Hotel_tax))
#     nights = Decimal(str(nights))
#     discount = Decimal(str(discount))

#     # Calculate base price for the stay
#     base_price = room_price * nights
#     logger.info(f"Base price for {nights} nights is {base_price}")

#     # Calculate discount amount from the base price
#     discount_amount = (base_price * discount) / Decimal("100")
    
#     # Deduct the discount amount from the total base price
#     discounted_amount = base_price - discount_amount

#     # Compute hotel tax
#     taxable_amount = (discounted_amount * Hotel_tax) / Decimal("100")
#     logger.info(f"Taxable amount for hotel is {taxable_amount}")

#     # Total room price after discount and tax
#     total_room_price = discounted_amount + taxable_amount
#     logger.info(f"Total room price is {total_room_price}")

#     # Compute meal price
#     Meal_price = meal_price * nights
#     logger.info(f"Meal price for {nights} nights is {Meal_price}")

#     # Compute meal tax
#     taxable_meal_amount = (Meal_price * Meal_tax) / Decimal("100")
#     total_meal_price = Meal_price + taxable_meal_amount
#     logger.info(f"Total meal price is {total_meal_price} (including tax)")

#     # Calculate total refund amount
#     total_refunded_amount = total_room_price + total_meal_price
#     logger.info(f"Total amount to be refunded is {total_refunded_amount}")

    # return Decimal(str(total_refunded_amount))
def Check_refund_amount(booking,current_time):
    try:
        logger.info(f"Current time is ----{current_time}")
        refund_amount=Decimal(0)
        checkin_date = booking.checkin_date
        check_in_time = booking.check_in_time
        check_out_time=booking.checkout_date
        discount_applied = Decimal(booking.discount_percentage_applied or 0)
        logger.info(f"Discount % applied is {discount_applied}")
        # Logging inputs
        logger.info(f"checkin_date: {checkin_date},check_in_time: {check_in_time},current_time: {current_time}")
        get_booked_room = Bookedrooms.objects.filter(booking=booking)
        logger.info(f"Booked room found: {get_booked_room}")
        # Calculate hotel tax
        tax_percentage = HotelTax.objects.filter(
            hotel=booking.hotel , status="active", is_deleted=False
        ).aggregate(total_tax=Sum('percentage'))['total_tax'] or Decimal(0)
        logger.info(f"Tax percentage for hotel is  {tax_percentage}")
        nights = (check_out_time - checkin_date).days
        logger.info(f" Total nights is -- {nights}")
        for i in get_booked_room:
            get_room=i.room
            if get_room:
                logger.info(f"Room found: {get_room}")
                get_refund_policy=RoomRefundPolicy.objects.filter(room=get_room,status='active').first()
                if get_refund_policy:
                    policy=get_refund_policy.policy
                    logger.info(f"policy found:{policy}")
                    if policy.is_refundable == True:     #check if it has refund available or not
                        logger.info(f"Booked room :{get_room}  has refund available policy")
                        checkin_datetime = datetime.combine(checkin_date, check_in_time)
                        logger.info(f"checkin_datetime: {checkin_datetime}")
                        # Calculate time difference
                        time_difference = checkin_datetime - current_time
                        logger.info(f"time_difference: {time_difference}")
                        if policy.is_validity_specific: #check if it is free-cancellation at any time /hour based refund
                            validity=get_refund_policy.validity
                            logger.info(f"-----{validity}in room")
                            logger.info(f"Booked room : {get_room} has  hour based refund of : {validity} hours")
                            if time_difference >= validity:
                                # meal_price=i.meal_type_id.price or Decimal(0)
                                # base_price=i.booked_room_price-meal_price or Decimal(0)
                                # logger.info(f"base_price for room {get_room} is {base_price}")
                                # logger.info(f"meal_price for room {get_room} is {meal_price}")
                                # meal_tax = MealTax.objects.filter(room=get_room).first()
                                # if meal_tax:
                                #     tax_meal = meal_tax.percentage or Decimal(0)
                                #     logger.info(tax_meal)
                                # else:
                                #     tax_meal = Decimal(0)
                                # new_refund=Calculate_room_refund(base_price,meal_price,tax_meal,tax_percentage,nights,discount_applied)
                                refund_amount += booking.booked_price
                            else:
                                logger.warning(f"Can't avail refund for room :{get_room}. Refund eligibility was {validity} hours before check-in.")
                        else:
                            logger.info(f"Booked room :{get_room} has free cancellation at any time policy")
                            logger.info(f" current time----{current_time}")
                            logger.info(f" checkin time----{checkin_datetime}")
                            if current_time < checkin_datetime:
                                # meal_price=i.meal_type_id.price or Decimal(0)
                                # base_price=i.booked_room_price-meal_price or Decimal(0)
                                # logger.info(f"base_price for room {get_room} is {base_price}")
                                # logger.info(f"meal_price for room {get_room} is {meal_price}")
                                # meal_tax = MealTax.objects.filter(room=get_room).first()
                                # if meal_tax:
                                #     tax_meal = meal_tax.percentage or Decimal(0)
                                #     logger.info(tax_meal)
                                # else:
                                #     tax_meal = Decimal(0)
                                # new_refund=Calculate_room_refund(base_price,meal_price,tax_meal,tax_percentage,nights,discount_applied)
                                refund_amount += booking.booked_price                            
                            else:
                                logger.warning(f"Can't avail refund for room : {get_room}. You have passed the check in time :{checkin_datetime}.")
                    else:
                        logger.info(f"Booked room : {get_room} has no refund policy ")            
    except Exception as e:
        logger.error(f"Error in checking refund amount: {e}")
    logger.info(f"Final total refund_amount: {refund_amount}")
    decimal_value = Decimal(str(refund_amount)).quantize(Decimal('0.000'), rounding=ROUND_DOWN)
    return decimal_value
    
def Check_refund_eligibility(booking, today_time):
    try:
        checkin_date = booking.checkin_date
        check_in_time = booking.check_in_time
        booked_price = booking.booked_price

        # Logging inputs
        logger.info(f"checkin_date: {checkin_date}")
        logger.info(f"check_in_time: {check_in_time}")
        logger.info(f"booked_price: {booked_price}")
        logger.info(f"today_time: {today_time}")

        # Combine date and time to create a datetime object for check-in
        checkin_datetime = datetime.combine(checkin_date, check_in_time)
        logger.info(f"checkin_datetime: {checkin_datetime}")

        # Calculate time difference
        time_difference = checkin_datetime - today_time
        logger.info(f"time_difference: {time_difference}")

        if time_difference >= timedelta(hours=24):
            refund_amount = booked_price
            refund_percentage = 100
            logger.info("Condition met: Full refund (100%)")
        elif time_difference >= timedelta(hours=0):  
            # Partial refund (80%)
            refund_amount = booked_price * Decimal('0.8')
            refund_percentage = 80
            logger.info("Condition met: Partial refund (80%)")
        elif today_time > checkin_datetime:
            # No refund
            refund_amount =Decimal('0.00')
            refund_percentage = 0
            logger.info("Condition met: No refund")
        else:
            refund_amount = Decimal('0.00')
            refund_percentage = 0
            logger.warning("Fallback case reached: No conditions met")

        logger.info(f"Refund calculated: Amount={refund_amount}, Percentage={refund_percentage}")
        return refund_amount, refund_percentage

    except Exception as e:
        logger.error(f"Error in refund calculation: {e}")
        raise



def amount_validity(amount,return_status,message):
    print(type(amount))
    if amount is None or amount == "":
        return_status = True
        logger.info(f"Amount should not be empty")
        message['message'] = "Amount should not be empty"
    elif amount < 1:
        return_status = True
        logger.info(f"Please enter amount greater than Zero")
        message['message'] = "Please enter amount greater than Zero"
    elif isinstance(amount, (str)):
        return_status = True
        logger.info(f"Amount is not valid")
        message['message'] = "Amount is not valid"
    return return_status, message



def get_available_rooms(hotel, checkin_date, checkout_date, members, rooms_required, status="active"):
    """
    Returns available rooms for a given hotel and date range, checking if the required number of rooms are available.

    Args:
        hotel (Hotel): The hotel to search rooms for.
        checkin_date (date): Start date of the booking.
        checkout_date (date): End date of the booking.
        members (int): Number of people (children/adults) per room.
        rooms_required (int): Number of rooms the user wants to book.
        status (str): Room status (default is "active").

    Returns:
        QuerySet: Available rooms for the given hotel and criteria.
    """

    # Filter active rooms matching hotel and capacity requirements
    rooms = RoomManagement.objects.filter(
        hotel=hotel,
        number_of_rooms__gte=int(rooms_required),
        status=status
    )
    available_room=[]
    # Exclude rooms already booked during the specified period
    for room in rooms:
        booked_room_no = Bookedrooms.objects.filter(
            room=room,
            booking__checkin_date__lt=checkout_date,
            booking__checkout_date__gt=checkin_date,
            booking__status__in=["pending","booked","confirmed","Confirmed","Booked","Pending","check-in", "Check-In"]
        ).aggregate(total=Sum('no_of_rooms_booked'))['total'] or 0
        rooms_available=room.number_of_rooms - booked_room_no
        if int(rooms_available)>=int(rooms_required):
            if int(rooms_required)* room.total_occupancy >=int(members):
                available_room.append(room.id)
    logger.info(f"the available room ids are {available_room}")
  
    return RoomManagement.objects.filter(id__in=available_room).order_by('price_per_night')



    

def get_available_room(hotel, checkin_date, checkout_date, members, status="active"):
    
    rooms = RoomManagement.objects.filter(
            hotel=hotel,
            total_occupancy__gte=members,
            status=status,
        )

        # Exclude rooms already booked during the specified period
    booked_room_ids = Bookedrooms.objects.filter(
        room__in=rooms,
        booking__checkin_date__lt=checkout_date,
        booking__checkout_date__gt=checkin_date,
        booking__status__in=["pending","booked","confirmed","Confirmed","Booked","Pending","check-in", "Check-In"]
    ).values_list("room_id", flat=True)

    # Return only rooms not booked in the specified period
    available_rooms = rooms.exclude(id__in=booked_room_ids).order_by("price_per_night")
   
    
    return available_rooms

def get_rooms_available(hotel, checkin_date, checkout_date, members, rooms_required, status="active"):
    """
    Returns available rooms for a given hotel and date range, checking if the required number of rooms are available.

    Args:
        hotel (Hotel): The hotel to search rooms for.
        checkin_date (date): Start date of the booking.
        checkout_date (date): End date of the booking.
        members (int): Number of people (children/adults) per room.
        rooms_required (int): Number of rooms the user wants to book.
        status (str): Room status (default is "active").

    Returns:
        QuerySet: Available rooms for the given hotel and criteria.
    """
    
    from vendor.models import RoomManagement, Bookedrooms
    
    from django.db.models import Sum

    # Filter active rooms matching hotel and capacity requirements
    rooms = RoomManagement.objects.filter(
        hotel=hotel,
        status=status
    )

    # Exclude rooms already booked during the specified period
    booked_room_ids = Bookedrooms.objects.filter(
        room__in=rooms,
        booking__checkin_date__lt=checkout_date,
        booking__checkout_date__gt=checkin_date,
        booking__status__in=["pending","booked","confirmed","Confirmed","Booked","Pending","check-in", "Check-In"]
    ).values_list("room_id", flat=True)
    
    # Get available rooms that are not booked during the specified period
    available_rooms = rooms.exclude(id__in=booked_room_ids)
    print(f"Available rooms:----- {available_rooms}")

    if available_rooms.count() >= rooms_required:
        total_occupancy = available_rooms.aggregate(Sum('total_occupancy'))['total_occupancy__sum']
        print(type(total_occupancy) ,"===========", type(members))
        if total_occupancy >= members:
            print(total_occupancy,"=========",rooms)
            # If sufficient capacity, return the required number of rooms
            return available_rooms
        else:
            # If total occupancy is less than members, return all available rooms
            return []
    else:
        # If there are fewer available rooms than required, return all available rooms
        return []


def check_expirity(hotel=None, chalet=None):
  
    if hotel:
        try:
            get_hotel_obj = Hotel.objects.filter(id=hotel.id).first()
            if get_hotel_obj:
                if get_hotel_obj.date_of_expiry < date.today():
                    logger.info(f"\n\nInside check expirity function ----->hotel's expiry date is less than todays date. which is the date has been expired\n\n")
                    return True
                else:
                    return False
        except Exception as e:
            logger.info(f"\n\nInside check expirity function -----> Exception raised. Exception: {e}\n\n")
    if chalet:
        try:
            get_chalet_obj = Chalet.objects.filter(id=chalet.id).first()
            if get_hotel_obj:
                if get_chalet_obj.date_of_expiry < date.today():
                    logger.info(f"\n\nInside check expirity function ----->chalet's expiry date is less than todays date. Which is the date has been expired\n\n")
                    return True
                else:
                    return False
        except Exception as e:
            logger.info(f"\n\nInside check expirity function -----> Exception raised. Exception: {e}\n\n")
    


def get_discounted_price_for_property(property_id, property_type):
    """
    Fetches the discounted price for a hotel or chalet if a daily deal exists.

    Args:
        property_id (int): The ID of the hotel or chalet.
        property_type (str): The type of the property, either 'hotel' or 'chalet'.

    Returns:
        float: The discounted price if a deal exists, or the original price for hotels if no deal is found.
               For chalets, it returns None if no deal is found.
    """
    try:
        current_date = now().date()

        # Filter promotions for the current date and matching property
        promotion_query = Promotion.objects.filter(
            Q(start_date__lte=current_date) &
            Q(end_date__gte=current_date) &
            Q(category="common") &
            Q(discount_percentage__isnull=False) &
            Q(status="active")
        )

        if property_type == "hotel":
            promotion_query = promotion_query.filter(hotel__id=property_id)
        elif property_type == "chalet":
            promotion_query = promotion_query.filter(chalet__id=property_id)
        else:
            raise ValueError("Invalid property type. Expected 'hotel' or 'chalet'.")

        # Get the first promotion that matches the query
        promotion = promotion_query.first()

        # Calculate the original price
        if property_type == "hotel":

            # Fetch all rooms for the hotel
            rooms = Hotel.objects.get(id=property_id).room_managements.all()

            # Get the current day
            today = datetime.now().weekday()  # 0 = Monday, ..., 5 = Friday, 6 = Saturday

            # Calculate the lowest price dynamically
            lowest_price = None
            for room in rooms:
                # Use weekend price if today is Thursday or Friday and weekend price is active
                if today in (3, 4) and hasattr(room, 'weekend_price') and room.weekend_price.is_active():
                    price = room.weekend_price.weekend_price
                else:
                    price = room.price_per_night

                # Update the lowest price
                if lowest_price is None or price < lowest_price:
                    lowest_price = price

            # Set original price
            original_price = lowest_price if lowest_price is not None else 0


            # If no promotion found, return the original price
            if not promotion:
                return original_price
        elif property_type == "chalet":
            if promotion:
                original_price = promotion.chalet.current_price
            else:
                return None
        else:
            return None

        # Calculate the discounted price
        if promotion and promotion.discount_percentage and original_price:
            discount_amount = (promotion.discount_percentage / 100) * original_price
            discounted_price = original_price - discount_amount
            return discounted_price

        return original_price

    except Exception as e:
        # Handle exceptions if needed
        return None


    except Exception as e:
        logger.error(f"Error fetching discounted price for property ID {property_id}: {e}")
        return None

def get_discounted_price_for_room(room_id):
    try:
        current_date = now().date()

        # Fetch the room and its associated hotel
        room = RoomManagement.objects.get(id=room_id)
        hotel = room.hotel
        original_price = room.current_price

        # Filter active promotions for the room's hotel
        promotion_query = Promotion.objects.filter(
            Q(start_date__lte=current_date) &
            Q(end_date__gte=current_date) &
            Q(category="common") &
            Q(discount_percentage__isnull=False) &
            Q(status="active") &
            (Q(hotel=hotel) | Q(multiple_hotels=hotel))
        ).first()

        # Apply discount if a promotion exists
        if promotion_query and promotion_query.discount_percentage:
            discount_amount = (promotion_query.discount_percentage / 100) * original_price
            discounted_price = original_price - discount_amount
            return discounted_price

        return original_price

    except RoomManagement.DoesNotExist:
        logger.error(f"Room with ID {room_id} does not exist.")
        return None
    except Exception as e:
        logger.error(f"Error fetching discounted price for room ID {room_id}: {e}")
        return None


def update_room_availability(booking):
    
    booked_rooms = Bookedrooms.objects.filter(booking=booking)
    for room in booked_rooms:
        room.status = "cancelled"
        room.room.availability = True
        room.room.save()
        room.save()
        logger.info(f"Room ID {room.room.id} availablity has been updated to True.")
        message = f"Room availablity has been updated to True"
    return message
def get_payment_details(type,category,language='en'):
    try:
        if type == 'hotel':
            try:
                payment_detail = HotelAcceptedPayment.objects.get(hotel=category)
                print(f"Found accepted payment details for {payment_detail.hotel}")
                logger.info(f"Found accepted payment details for {payment_detail.hotel}")
            except Exception as e:
                logger.error(f"An error occured at the hotel details fetching at the HotelAcceptedPayment , {str(e)} ")
                print(f"\n\n\n\n\n An error occured at the hotel details fetching at the HotelAcceptedPayment , {str(e)} \n\n\n\n\n")
        elif type=='chalet':
            try:
                payment_detail=ChaletAcceptedPayment.objects.get(chalet=category)
                logger.info(f"Found accepted payment details for {payment_detail.chalet}")
            except Exception as e:
                logger.error(f"An error occured at the Chalet details fetching at the HotelAcceptedPayment , {str(e)} ")
        structured_data = {}
        print(f"\n\n\n\n\n payment_detail: {payment_detail} \n\n\n\n\n")
        payment_types = payment_detail.payment_types.all()
        refundable_translation = {
            "refundable": "قابل للاسترداد",
            "non-refundable": "غير قابل للاسترداد"
        }

        for i in payment_types:
            # Select name based on language
            category_name = i.category.name_arabic if language == 'ar' else i.category.name
            payment_method_name = i.name_arabic if language == 'ar' else i.name
            is_refundable = refundable_translation[i.category.is_refundable] if language == 'ar' else i.category.is_refundable

            if category_name in structured_data:
                structured_data[category_name]["payment_methods"].append(payment_method_name)
            else:
                structured_data[category_name] = {
                    "category": category_name,
                    "is_refundable": is_refundable,
                    "payment_methods": [payment_method_name]
                }

        return list(structured_data.values())


    except Exception as e:
        logger.error(f"an exception occured at get_payment_details function:{str(e)}")
        
        




from decimal import Decimal
from datetime import datetime

def calculate_hotel_price(hotel_id=None, room_id=None, chalet_id=None, calculation_logic="minimum_price", include_details=False, checkin_date=None, checkout_date=None, members=1, rooms_required=1, property="hotel"):
    from chalets.models import Chalet
    """
    Calculate the price of a hotel or chalet based on various calculation logics and date ranges.

    Args:
        hotel_id (int): The ID of the hotel (optional).
        room_id (int): The ID of a specific room (optional).
        chalet_id (int): The ID of a specific chalet (optional).
        calculation_logic (str): Logic for price calculation (e.g., 'minimum_price', 'average_price').
        include_details (bool): Whether to include tax, commission, and other details.
        checkin_date (str): Check-in date (format: 'YYYY-MM-DD').
        checkout_date (str): Check-out date (format: 'YYYY-MM-DD').
        members (int): Number of members (adults/children).
        rooms_required (int): Number of rooms required.
        property (str): Property type ('hotel' or 'chalet').

    Returns:
        dict: Dictionary containing calculated price and additional details (if requested).
    """
    
    try:
        # Parse dates
        if checkin_date and checkout_date:
            if checkin_date >= checkout_date:
                return {"error": "Check-in date must be earlier than check-out date."}
        else:
            return {"error": "Both check-in and check-out dates are required for price calculation."}

        if property == "chalet" and chalet_id:
            # Directly calculate the average price for the chalet
            calculated_price = _calculate_average_price(
                chalet_id=chalet_id,
                checkin_date=checkin_date,
                checkout_date=checkout_date,
                property=property
            )

            result = {"calculated_price": Decimal(calculated_price)}

            # Include additional details if requested
            if include_details:
                chalet = Chalet.objects.get(id=chalet_id)
                tax = chalet.country.tax if chalet.country and chalet.country.tax else Decimal(0)
                commission_percentage = chalet.commission_percentage or Decimal(0)
                commission_amount = (commission_percentage / 100) * Decimal(calculated_price)

                result.update({
                    "tax": tax,
                    "commission_percentage": commission_percentage,
                    "commission_amount": commission_amount,
                    "total_price": Decimal(calculated_price) + tax + commission_amount,
                })

            return result

        # Fetch the hotel
        hotel = Hotel.objects.get(id=hotel_id)

        if room_id:
            # Fetch the specific room
            room = RoomManagement.objects.get(id=room_id)
            available_rooms = [room]  # Only consider this one room
        else:
            # Fetch all rooms if no room_id is provided
            available_rooms = get_available_room(
                hotel=hotel,
                checkin_date=checkin_date,
                checkout_date=checkout_date,
                members=members
            )
            

        if not available_rooms:
            return {"error": "No rooms available for the given criteria."}

        # Define calculation logic handlers
        calculation_handlers = {
            "minimum_price": lambda rooms: min(room.current_price for room in rooms),
            "maximum_price": lambda rooms: max(room.current_price for room in rooms),
            "average_price": lambda rooms: _calculate_average_price(rooms, checkin_date, checkout_date, property=property),
            "daily_deal_price": lambda rooms: _calculate_daily_deal_price(rooms),
        }

        # Check if the logic is supported
        if calculation_logic not in calculation_handlers:
            return {"error": f"Unknown calculation logic: {calculation_logic}"}

        # Perform the selected calculation
        calculated_price = calculation_handlers[calculation_logic](available_rooms)

        # Prepare the result
        result = {"calculated_price": Decimal(calculated_price)}

        # Include additional details if requested
        if include_details:
            tax = hotel.country.tax if hotel.country and hotel.country.tax else Decimal(0)
            commission_percentage = hotel.commission_percentage or Decimal(0)
            commission_amount = (commission_percentage / 100) * Decimal(calculated_price)

            result.update({
                "tax": tax,
                "commission_percentage": commission_percentage,
                "commission_amount": commission_amount,
                "total_price": Decimal(calculated_price) + tax + commission_amount,
            })

        return result

    except Hotel.DoesNotExist:
        return {"error": "Hotel not found."}
    except Chalet.DoesNotExist:
        return {"error": "Chalet not found."}
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}

from datetime import timedelta


def _calculate_average_price(rooms=None, checkin_date=None, checkout_date=None, chalet_id=None, property="hotel"):
    """
    Calculate the average price for rooms based on the selected date range, 
    including promotions if applicable.

    Args:
        rooms (QuerySet): A queryset of RoomManagement instances.
        checkin_date (date): The check-in date.
        checkout_date (date): The check-out date.

    Returns:
        Decimal: The average price across the date range.
    """
    from chalets.models import Chalet
    
    min_total_price = Decimal('Infinity')  # Initialize to a large value
    weekend_days = 0
    normal_days = 0
    room_totals = {}

    current_date = checkin_date
    if property == "chalet" and chalet_id:
        chalet = Chalet.objects.get(id=chalet_id)
        total_days = (checkout_date - checkin_date).days
        chalet_total_price = Decimal(0)  # Total price for the entire date range

        while current_date < checkout_date:
            is_weekend = current_date.weekday() in (3, 4)  # Thursday=3, Friday=4

            # Determine the base price for the chalet
            if is_weekend and hasattr(chalet, 'weekend_price') and chalet.weekend_price:
                base_price = chalet.weekend_price.weekend_price
            else:
                base_price = chalet.total_price

            # Check for promotions applicable on the current date for the chalet
            promotion = Promotion.objects.filter(
                Q(start_date__lte=current_date) &
                Q(end_date__gte=current_date) &
                Q(category="common") &
                Q(discount_percentage__isnull=False) &
                Q(status="active") &
                (Q(chalet=chalet) | Q(multiple_chalets=chalet))
            ).first()

            # # Apply promotion if available
            # if promotion and promotion.discount_percentage:
            #     discount_amount = (promotion.discount_percentage / 100) * base_price
            #     base_price -= discount_amount

            # Accumulate the total price for the date range
            chalet_total_price += base_price

            # Count weekend and normal days
            if is_weekend:
                weekend_days += 1
            else:
                normal_days += 1

            current_date += timedelta(days=1)

        # Calculate the average price per day for the chalet
        average_price = chalet_total_price / total_days

        # # Apply tax
        # tax_percentage = ChaletTax.objects.filter(
        #     chalet=chalet, status="active", is_deleted=False
        # ).aggregate(total_tax=Sum('percentage'))['total_tax'] or Decimal(0)

        # # Apply tax
        # tax_amount = (tax_percentage / 100) * average_price
        # average_price += tax_amount

        return round(average_price, 3)

    
    if not rooms:
        return Decimal(0)

    
    while current_date < checkout_date:
        is_weekend = current_date.weekday() in (3, 4)  # Thursday=3, Friday=4

        for room in rooms:
            room_total_price = room_totals.get(room.id, Decimal(0))  # Current total price for this room

            # Check for promotions applicable on the current date for the room's hotel
            hotel = room.hotel
            promotion = Promotion.objects.filter(
                Q(start_date__lte=current_date) &
                Q(end_date__gte=current_date) &
                Q(category="common") &
                Q(discount_percentage__isnull=False) &
                Q(status="active") &
                (Q(hotel=hotel) | Q(multiple_hotels=hotel))
            ).first()

            # Determine the base price for the room
            if is_weekend and hasattr(room, 'weekend_price') and room.weekend_price:
                base_price = room.weekend_price.weekend_price
            else:
                base_price = room.price_per_night

            # # Apply promotion if available
            # if promotion and promotion.discount_percentage:
            #     discount_amount = (promotion.discount_percentage / 100) * base_price
            #     base_price -= discount_amount

            room_total_price += base_price
            room_totals[room.id] = room_total_price
            

        if is_weekend:
            weekend_days += 1
        else:
            normal_days += 1

        current_date += timedelta(days=1)

    # Find the minimum total price across all rooms
    min_total_price = min(room_totals.values())

    # Calculate the total number of days in the range (inclusive of check-out date)
    total_days = (checkout_date - checkin_date).days

    # Calculate the average price per day for the room with the minimum total price
    average_price = min_total_price / total_days

    # # Apply tax
    # tax_percentage = HotelTax.objects.filter(
    #     hotel=hotel, status="active", is_deleted=False
    # ).aggregate(total_tax=Sum('percentage'))['total_tax'] or Decimal(0)

    # # Apply tax
    # tax_amount = (tax_percentage / 100) * average_price
    # average_price += tax_amount

    return round(average_price, 3)

def _calculate_daily_deal_price(rooms, discount_rate=10):
    """
    Calculate a daily deal price by applying a discount rate to the minimum price.

    Args:
        rooms (QuerySet): A queryset of RoomManagement instances.
        discount_rate (float): The discount rate as a percentage (default is 10%).

    Returns:
        Decimal: The discounted daily deal price.
    """
    if not rooms:
        return Decimal(0)

    # Get the minimum price from available rooms
    minimum_price = min(room.current_price for room in rooms)

    # Apply the discount rate
    discount = (discount_rate / 100) * Decimal(minimum_price)
    return Decimal(minimum_price) - discount



import string
def generate_track_id():
    prefix = "TRK"  # Constant prefix
    random_number = ''.join(random.choices(string.digits, k=10))  # 10-digit random number
    return f"{prefix}{random_number}"


def Check_current_room_availability(room_obj, checkin_date,checkout_date,rooms_required):
    room=room_obj.first()
    # Exclude rooms already booked during the specified period
    booked_room_no = Bookedrooms.objects.filter(
        room=room,
        booking__checkin_date__lt=checkout_date,
        booking__checkout_date__gt=checkin_date,
        booking__status__in=["pending","booked","confirmed","Confirmed","Booked","Pending","check-in", "Check-In"]
    ).aggregate(total=Sum('no_of_rooms_booked'))['total'] or 0
    rooms_available=room.number_of_rooms  - booked_room_no
    return rooms_available >= int(rooms_required)
       

def calculate_minimum_hotel_price(hotel_id=None, room_id=None, chalet_id=None, calculation_logic="minimum_price", include_details=False, checkin_date=None, checkout_date=None, members=1, rooms_required=1, property="hotel"):
        # Fetch the hotel
        hotel = Hotel.objects.get(id=hotel_id)
        logger.info(f"inside the minimum price function {hotel}")

        if room_id:
            # Fetch the specific room
            room = RoomManagement.objects.get(id=room_id)
            available_rooms = [room]  # Only consider this one room
        else:
            # Fetch all rooms if no room_id is provided
            available_rooms = get_available_rooms(
                hotel=hotel,
                checkin_date=checkin_date,
                checkout_date=checkout_date,
                members=members, rooms_required=rooms_required
            )
            logger.info(get_available_rooms)
            

        if not available_rooms:
            return {"error": "No rooms available for the given criteria."}

        # Define calculation logic handlers
        calculation_handlers = {
            "minimum_price": lambda rooms: min(room.current_price for room in rooms),
            "maximum_price": lambda rooms: max(room.current_price for room in rooms),
            "average_price": lambda rooms: _calculate_average_price(rooms, checkin_date, checkout_date, property=property),
            "daily_deal_price": lambda rooms: _calculate_daily_deal_price(rooms),
        }

        # Check if the logic is supported
        if calculation_logic not in calculation_handlers:
            return {"error": f"Unknown calculation logic: {calculation_logic}"}

        # Perform the selected calculation
        calculated_price = calculation_handlers[calculation_logic](available_rooms)

        # Prepare the result
        result = {"calculated_price": Decimal(calculated_price)}

        # Include additional details if requested
        if include_details:
            tax = hotel.country.tax if hotel.country and hotel.country.tax else Decimal(0)
            commission_percentage = hotel.commission_percentage or Decimal(0)
            commission_amount = (commission_percentage / 100) * Decimal(calculated_price)

            result.update({
                "tax": tax,
                "commission_percentage": commission_percentage,
                "commission_amount": commission_amount,
                "total_price": Decimal(calculated_price) + tax + commission_amount,
            })

        return result
def backup_function_payment(booking,property,total_amount):
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
    return context
def bank_charge_calculation(amount):
    try:
        amount = Decimal(str(amount))
        bank_charge = amount * Decimal('2.0') / Decimal('100')
        logger.info(f"calculated the bank charge for the amount is {bank_charge}")
        final_amount=amount+bank_charge
        final_amount = Decimal(str(final_amount)[:str(final_amount).find('.') + 4])
        logger.info(f"final amount after adding bank charge is {final_amount}")
        return final_amount
    except Exception as e:
        logger.info(f"an error occured at the bank_charge_calculation {e}")
        return None

def calculate_user_amount(amount):
    try:
        amount = Decimal(str(amount))
        logger.info(f"Amount received for calculating the bank charge and user amount is {amount}")
        user_amount = amount * Decimal('100') / Decimal('102')
        user_amount = Decimal(str(user_amount)[:str(user_amount).find('.') + 4])  
        logger.info(f"User amount calculated is {user_amount}")
        bank_charge = amount - user_amount
        bank_charge = Decimal(str(bank_charge)[:str(bank_charge).find('.') + 4])  
        logger.info(f"Bank charge calculated is {bank_charge}")
        return user_amount, bank_charge
    except Exception as e:
        logger.info(f"an error occured at the calculate_user_amount {e}")
        return None, None
def create_Online_wallet_transaction(wallet, transaction_type, amount):
    """
    Helper function to create a transaction and update the wallet balance.
    """
    try:
        # Generate a unique transaction ID
        transaction_id = str(uuid.uuid4())
        amount = Decimal(str(amount))
        wallet.balance = Decimal(str(wallet.balance))
        user_amount,bank_charge=calculate_user_amount(amount)
        # Create a new transaction record
        OnlineWalletTansaction.objects.create(
            wallet=wallet,
            transaction_id=transaction_id,
            transaction_type=transaction_type,
            total_amount=amount,
            user_amount= user_amount,
            bank_charge=bank_charge
        )
        if user_amount is None:
            logger.error("Failed to calculate user amount or bank charge.")
            return None, wallet.balance

        # Update the wallet balance based on transaction type
        if transaction_type == 'credit':
            wallet.balance += user_amount
        elif transaction_type == 'debit':
            wallet.balance -= user_amount

        wallet.save()

        return transaction_id, wallet.balance
    except Exception as e:
        logger.info(f"an error occured at the create_Online_wallet_transaction {e}")
        return None, None
    