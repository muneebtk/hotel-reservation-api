import uuid
import qrcode
import logging

from datetime import datetime
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from decimal import Decimal
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
from django.db.models import Sum

from user.models import WalletTransaction,Referral
from vendor.models import CommissionSlab

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)

    if response is None:
        # Log the error for debugging purposes
        logger.info(f"Unhandled exception: {str(exc)}", exc_info=True)
        
        # Create a custom response for unhandled exceptions
        response = Response(
            {
                'error': True,
                'message': 'An internal server error occurred. Please try again later.',
                'status_code': 500
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    return response



def generate_qr_code(booking_id, token):
    """
    Generates a QR code for a booking URL and saves it to the default storage.
    Returns the URL path to the saved QR code image.
    """
    # Create the booking URL
    booking_url = f"{settings.DOMAIN_NAME}/vendor/booking/verify/{token}/"
    
    # Generate the QR code image
    qr = qrcode.make(booking_url)
    qr_image = BytesIO()
    qr.save(qr_image, "PNG")
    qr_image.seek(0)
    
    # Save the QR code image to media storage
    qr_filename = f"bookings/qr_codes/booking_{booking_id}.png"
    qr_path = default_storage.save(qr_filename, ContentFile(qr_image.read()))
    
    # Return the URL path to the saved QR code image
    return default_storage.url(qr_path)


def generate_qr_code_chalet(booking_id, token):
    """
    Generates a QR code for a booking URL and saves it to the default storage.
    Returns the URL path to the saved QR code image.
    """
    # Create the booking URL
    booking_url = f"{settings.DOMAIN_NAME}/chalets/booking/verify/{token}/"
    
    # Generate the QR code image
    qr = qrcode.make(booking_url)
    qr_image = BytesIO()
    qr.save(qr_image, "PNG")
    qr_image.seek(0)
    
    # Save the QR code image to media storage
    qr_filename = f"bookings/qr_codes/booking_{booking_id}.png"
    qr_path = default_storage.save(qr_filename, ContentFile(qr_image.read()))
    
    # Return the URL path to the saved QR code image
    return default_storage.url(qr_path)


def generate_referral_token(user):
    """Generate a unique referral token for a user."""
    token = str(uuid.uuid4())  # Generate a UUID4 token
    referral, created = Referral.objects.get_or_create(referrer=user, defaults={'token': token})
    if not created:
        # Token already exists for the user; return the existing token
        token = referral.token
    return token

def generate_transaction_id(user_id):
    """
    Generates a unique transaction ID.

    Args:
        user_id (int): The ID of the user.

    Returns:
        str: The generated transaction ID in the format TRN-{user_id}-{timestamp}.
    """
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"TRN-{user_id}-{timestamp}"


def create_wallet_transaction(wallet, transaction_type, amount):
    """
    Creates a transaction entry in the WalletTransaction model and updates the wallet balance.

    Args:
        wallet (Wallet): The wallet instance.
        transaction_type (str): The type of transaction ('credit' or 'debit').
        amount (Decimal): The transaction amount.

    Returns:
        WalletTransaction: The created transaction object.
    
    Raises:
        ValueError: If the transaction type is invalid or if there are insufficient funds for a debit transaction.
    """
    if transaction_type not in ['credit', 'debit']:
        raise ValueError("Invalid transaction type. Must be 'credit' or 'debit'.")

    if transaction_type == 'debit' and wallet.balance < amount:
        raise ValueError("Insufficient funds for debit transaction.")

    # Generate transaction ID
    transaction_id = generate_transaction_id(wallet.user.id)

    # Start a database transaction
    with transaction.atomic():
        # Update wallet balance
        if transaction_type == 'credit':
            wallet.balance += amount
        elif transaction_type == 'debit':
            wallet.balance -= amount
        wallet.save()

        # Create a new wallet transaction
        wallet_transaction = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_id=transaction_id,
            transaction_type=transaction_type,
            amount=amount
        )

    return wallet_transaction

def calculate_commission(price):
    """
    Calculate commission based on the price using the CommissionSlab model.
    """
    if price <= 0:
        return Decimal(0.0)

    # Fetch the commission amount from the CommissionSlab model
    commission = CommissionSlab.objects.filter(
        from_amount__lte=price,
        to_amount__gte=price,
        status="active"
    ).aggregate(commission_price=Sum('commission_amount')).get('commission_price', Decimal(0.0))

    return commission or Decimal(0.0)