import datetime
from decimal import Decimal,ROUND_DOWN
import random
from django.template.defaultfilters import slugify
import logging
logger = logging.getLogger('lessons')



def generate_unique_slug(instance, target_field, slug_field='slug'):
    """
    Generates a unique slug based on the target field (e.g., 'name').

    Args:
        instance: The model instance to which the slug is being assigned.
        target_field (str): The name of the field to base the slug on (e.g., 'name').
        slug_field (str): The name of the field where the slug will be saved (default is 'slug').

    Returns:
        str: The unique slug.
    """
    # Get the value of the target field (e.g., 'name')
    target_value = getattr(instance, target_field)
    
    # Generate a base slug from the target field
    base_slug = slugify(target_value)
    
    # Ensure the slug is unique
    unique_slug = base_slug
    counter = 1
    while instance.__class__.objects.filter(**{slug_field: unique_slug}).exists():
        unique_slug = f"{base_slug}-{counter}"
        counter += 1

    return unique_slug

def create_transaction(transaction_id, ref_id, amount, payment_type, user):
    """
    Creates a new transaction entry in the Transaction table.
    
    :param transaction_id: Unique transaction ID
    :param ref_id: Reference ID (e.g., WALLET{booking.id})
    :param amount: Transaction amount
    :param payment_type: PaymentType instance
    :param user: User who created the transaction
    :return: Created Transaction object
    """
    from common.models import Transaction
    transaction = Transaction.objects.create(
        transaction_id=transaction_id,
        ref_id=ref_id,
        amount=amount,
        payment_type=payment_type,
        created_by=user,
        modified_by=user,
        status='active'
    )
    return transaction

def create_hotel_booking_transaction(booking, transaction, user):
    """
    Creates a new HotelBookingTransaction entry linking a transaction to a booking.
    
    :param booking: Hotel Booking instance
    :param transaction: Transaction instance
    :param user: User who created the entry
    :return: Created HotelBookingTransaction object
    """
    from vendor.models import HotelBookingTransaction
    hotel_booking_transaction = HotelBookingTransaction.objects.create(
        booking=booking,
        transaction=transaction,
        created_by=user
    )
    return hotel_booking_transaction


def create_chalet_booking_transaction(booking, transaction, user):
    """
    Creates a new ChaletBookingTransaction entry linking a transaction to a chalet booking.
    
    :param booking: Chalet Booking instance
    :param transaction: Transaction instance
    :param user: User who created the entry
    :return: Created ChaletBookingTransaction object
    """
    from chalets.models import ChaletBookingTransaction
    chalet_booking_transaction = ChaletBookingTransaction.objects.create(
        booking=booking,
        transaction=transaction,
        created_by=user
    )
    return chalet_booking_transaction


def generate_transaction_id():
    """Generate a unique transaction ID with date and timestamp."""
    now = datetime.datetime.now()
    date_part = now.strftime("%Y%m%d") 
    timestamp_part = now.strftime("%H%M%S%f")  
    random_part = random.randint(1000, 9999)  

    return f"TRN{date_part}{timestamp_part}{random_part}"


def create_vendor_transaction(transaction, vendor, base_price, total_tax, discount_applied, vendor_earnings, user, meal_price=None, meal_tax=None):
    """
    Creates a new VendorTransaction entry linking a transaction to a vendor.
    
    :param transaction: Transaction instance
    :param vendor: VendorProfile instance
    :param base_price: Base price of the booking (room price only)
    :param total_tax: Total tax applied
    :param meal_price: Meal price (if applicable)
    :param meal_tax: Meal tax (if applicable)
    :param discount_applied: Discount applied on booking
    :param vendor_earnings: Vendor's net revenue after deductions
    :param user: User who created the entry
    :return: Created VendorTransaction object
    """
    from vendor.models import VendorTransaction

    vendor_transaction_data = {
        "transaction": transaction,
        "vendor": vendor,
        "base_price": base_price,
        "total_tax": total_tax,
        "discount_applied": discount_applied or 0.00,
        "vendor_earnings": vendor_earnings or 0.00,
        "created_by": user
    }

    # Conditionally add meal_price and meal_tax if they are passed
    if meal_price is not None:
        vendor_transaction_data["meal_price"] = meal_price
    if meal_tax is not None:
        vendor_transaction_data["meal_tax"] = meal_tax

    vendor_transaction = VendorTransaction.objects.create(**vendor_transaction_data)
    
    return vendor_transaction


def update_transaction_status(transaction_id, transaction_status, payment_type_name):
    """
    Updates the transaction status and payment type given the transaction_id, new status, and payment type name.
    The payment type check is case-insensitive.
    """
    from common.models import Transaction, PaymentType
    try:
        transaction = Transaction.objects.get(transaction_id=transaction_id)

        # Validate transaction status
        if transaction_status not in dict(Transaction.TRANSACTION_STATUS_CHOICES):
            return False  # Invalid status
        
        # Fetch the payment type (case-insensitive)
        try:
            payment_type = PaymentType.objects.get(name__iexact=payment_type_name, status='active', is_deleted=False)
        except PaymentType.DoesNotExist:
            return False  # Payment type not found

        # Update transaction status and payment type
        transaction.transaction_status = transaction_status
        transaction.payment_type = payment_type
        transaction.save(update_fields=['transaction_status', 'payment_type', 'modified_at'])

        return True  # Success

    except Transaction.DoesNotExist:
        return False  # Transaction not found

from django.db.models import F
from django.utils.timezone import now
def _truncate_to_three_decimal_places(value):
        """Helper function to truncate a value to exactly three decimal places without rounding up."""
        if isinstance(value, (Decimal, float, int)):
            return Decimal(value).quantize(Decimal('0.000'), rounding=ROUND_DOWN)
        return value

def update_vendor_earnings(transaction_id, card_type):
    
    """
    Updates the vendor_earnings field in VendorTransaction based on transaction_id and card_type.
    Deducts the payment processing fee (1.5% for debit, 2.5% for credit) and commission.
    """
    from common.models import AdminTransaction
    from vendor.models import VendorTransaction, CommissionSlab, Booking
    from chalets.models import ChaletBooking
    try:
        vendor_transaction = VendorTransaction.objects.get(transaction__transaction_id=transaction_id)
        
        # Calculate total amount
        total_amount = (
            vendor_transaction.base_price +
            vendor_transaction.total_tax +
            (vendor_transaction.meal_price or 0) +
            (vendor_transaction.meal_tax or 0) -
            vendor_transaction.discount_applied
        )

        # Determine fee percentage based on card type
        if card_type.lower() == 'credit':
            fee_percentage = Decimal('2.5')
            admin_gateway_fee_percentage = Decimal('0.7') # updated commission amount for admin after bank reduved credit card charges from 2% to 1.7% earlier it was 0.5
        elif card_type.lower() == 'debit':
            fee_percentage = Decimal('1.5')
            admin_gateway_fee_percentage = Decimal('0.5')
        elif card_type.lower() in ['wallet', 'cash']:
            fee_percentage = Decimal('0')  # No payment gateway charge
            admin_gateway_fee_percentage = Decimal('0')
        else:
            return False  # Invalid card type

        # Calculate fee amount
        fee_amount = (Decimal(fee_percentage) / Decimal(100)) * total_amount
        logger.info(f"feeamount is ----{fee_amount}")
        admin_gateway_fee = (Decimal(admin_gateway_fee_percentage) / Decimal('100')) * total_amount
        
        # Check if this is a regular booking or chalet booking
        booking = Booking.objects.filter(transaction=vendor_transaction.transaction).first()
        chalet_booking = ChaletBooking.objects.filter(transaction=vendor_transaction.transaction).first()
        
        if booking:
            booking_id = booking.id
            booking_type = 'room'
        elif chalet_booking:
            booking_id = chalet_booking.id
            booking_type = 'chalet'
        else:
            return False  # No booking found

        
        discount_price = vendor_transaction.discount_applied
        
        commission_result = calculate_commission_by_booking(booking_id, discount_price, booking_type)
        print(f"\n\n\n\n\n\n\n\n\n\n\n {commission_result}\n\n\n\n\n\n\n\n\n\n\n\n")
        commission_amount = commission_result.get("total_commission", Decimal(0))

        # commission_price_range = vendor_transaction.base_price + (vendor_transaction.meal_price or 0)
        # # Fetch commission amount based on base_price
        # commission_amount = CommissionSlab.objects.filter(
        #     from_amount__lte=commission_price_range,
        #     to_amount__gte=commission_price_range,
        #     status='active'
        # ).values_list('commission_amount', flat=True).first() or 0  # Default to 0 if no commission found

        # Calculate vendor earnings
        vendor_earnings = total_amount - (fee_amount + commission_amount)
        admin_commission = admin_gateway_fee + commission_amount
        # Update vendor earnings
        vendor_transaction.vendor_earnings = vendor_earnings
        vendor_transaction.save(update_fields=['vendor_earnings', 'modified_at'])

        # Update or create AdminTransaction
        admin_transaction, created = AdminTransaction.objects.update_or_create(
            transaction=vendor_transaction.transaction,
            defaults={
                'gateway_fee':_truncate_to_three_decimal_places(fee_amount),
                'admin_gateway_fee': _truncate_to_three_decimal_places(admin_gateway_fee),
                'admin_commission': _truncate_to_three_decimal_places(admin_commission),
                'modified_at': now(),
            }
        )


        return True  # Success

    except VendorTransaction.DoesNotExist:
        return False  # VendorTransaction not found






def calculate_commission_by_booking(booking_id, discount_price, booking_type='room'):
    from decimal import Decimal
    import datetime
    from vendor.models import Bookedrooms, Booking, CommissionSlab
    from chalets.models import ChaletBooking
    try:
        # 1. Fetch the booking
        if booking_type == 'room':
            booking = Booking.objects.get(id=booking_id)
        else:
            booking = ChaletBooking.objects.get(id=booking_id)
    except (Booking.DoesNotExist, ChaletBooking.DoesNotExist):
        return {"error": "Booking not found"}

    total_price = Decimal(0)
    daily_prices = []
    total_rooms = 0  # Total number of rooms booked (for proportional discount)
    current_date = booking.checkin_date
    nights = (booking.checkout_date - booking.checkin_date).days

    if nights <= 0:
        return {"error": "Invalid date range"}

    if booking_type == 'room':
        booked_rooms = Bookedrooms.objects.filter(booking=booking)
    else:
        booked_rooms = []

    for _ in range(nights):
        day_price = Decimal(0)
        room_price_list = []

        if booking_type == 'room':
            for room in booked_rooms:
                if not room.room:
                    continue

                # Base price for one room
                if current_date.weekday() in [3, 4]:  # Thursday & Friday
                    if hasattr(room.room, 'weekend_price') and room.room.weekend_price.is_active():
                        base_price = Decimal(str(room.room.weekend_price.weekend_price))
                    else:
                        base_price = Decimal(str(room.room.price_per_night))
                else:
                    base_price = Decimal(str(room.room.price_per_night))

                # Add meal price if any
                meal_price = Decimal(str(room.meal_type_id.price)) if room.meal_type_id else Decimal(0)
                total_price_for_this_entry = (base_price + meal_price) * room.no_of_rooms_booked

                # Add to overall day price
                day_price += total_price_for_this_entry
                total_rooms += room.no_of_rooms_booked

                # Store each room's price separately for commission calculation
                room_price_list.append({
                    "no_of_rooms": room.no_of_rooms_booked,
                    "unit_price": base_price + meal_price,
                })

        else:
            if booking.chalet:
                if current_date.weekday() in [3, 4]:  # Thursday & Friday
                    weekend_price_obj = booking.chalet.weekend_price
                    if weekend_price_obj and weekend_price_obj.is_active:
                        base_price = Decimal(str(weekend_price_obj.weekend_price))
                    else:
                        base_price = Decimal(str(booking.chalet.total_price))
                else:
                    base_price = Decimal(str(booking.chalet.total_price))

                day_price = base_price  # Whole unit price per night
                total_rooms += 1
                room_price_list.append({
                    "no_of_rooms": 1,
                    "unit_price": base_price,
                })

        daily_prices.append({
            "date": current_date,
            "base_price": day_price,
            "room_prices": room_price_list
        })

        total_price += day_price
        current_date += datetime.timedelta(days=1)

    # Apply proportional discount and compute commission
    total_discount = Decimal(str(discount_price))
    total_commission = Decimal(0)

    for day in daily_prices:
        base_price = day["base_price"]

        if total_price > 0:
            day_discount = (base_price / total_price) * total_discount
        else:
            day_discount = Decimal(0)

        effective_price = max(base_price - day_discount, Decimal(0))
        room_prices = day["room_prices"]

        day_commission = Decimal(0)
        for room in room_prices:
            per_room_price = room["unit_price"]
            room_count = room["no_of_rooms"]

            # Proportional discount on this room's total
            room_total_price = per_room_price * room_count
            if base_price > 0:
                room_discount = (room_total_price / base_price) * day_discount
            else:
                room_discount = Decimal(0)

            effective_room_price = max(room_total_price - room_discount, Decimal(0))
            per_unit_effective_price = effective_room_price / room_count

            # Commission per unit
            commission = CommissionSlab.objects.filter(
                from_amount__lte=per_unit_effective_price,
                to_amount__gte=per_unit_effective_price,
                status='active'
            ).values_list('commission_amount', flat=True).first() or Decimal(0)

            # Total commission for this room entry
            total_commission_for_this_entry = commission * room_count
            day_commission += total_commission_for_this_entry

        total_commission += day_commission

        # Add computed values for the day
        day.update({
            "discount": day_discount,
            "effective_price": effective_price,
            "commission": day_commission
        })

    return {
        "booking_id": booking_id,
        "booking_type": booking_type,
        "nights": nights,
        "total_base_price": total_price,
        "total_discount": total_discount,
        "total_commission": total_commission,
        "daily_details": daily_prices
    }
