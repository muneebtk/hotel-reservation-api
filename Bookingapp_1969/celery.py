import os
import logging
from celery import Celery
from celery.schedules import crontab

from django.utils import timezone
from datetime import datetime, time
from datetime import timedelta
from datetime import datetime, timedelta
from django.utils.timezone import now




# from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Bookingapp_1969.settings")
app = Celery("Bookingapp_1969")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

logger = logging.getLogger('lessons')

@app.task(name='completed_booking')  
def update_completed_bookings():   
    from vendor.models import Hotel, Booking, RoomManagement
    from chalets.models import Chalet, ChaletBooking, Promotion
    hotels = Hotel.objects.all()  
    chalets = Chalet.objects.all()
    now = timezone.now()  
    logger.info("Current time: %s", now)
    try:
        if hotels:
            for hotel in hotels:
                checkin_time = hotel.checkin_time
                checkout_time = hotel.checkout_time

                if checkin_time and checkout_time:

                    bookings = Booking.objects.filter(
                        hotel=hotel,
                        checkout_date__lte=now.date()
                    )
                    logger.info("Hotel ID %s: Found %d bookings to process", hotel.id, bookings.count())

                    total_completed = 0  
                    for booking in bookings:
                        logger.info("Processing booking ID %s for hotel ID %s", booking.id, hotel.id)


                        # Calculate the full checkout datetime based on booking's checkout_date and hotel's checkout_time
                        hotel_checkout_datetime = timezone.make_aware(
                            timezone.datetime.combine(booking.checkout_date, checkout_time)
                        )
                        logger.info("Booking ID %s: Checkout datetime %s", booking.id, hotel_checkout_datetime)


                        if now.date() >= booking.checkout_date:
                            logger.info("Current time is past checkout time for booking ID %s", booking.id)
                            if booking.status == "check-in":
                                booking.status = "completed"
                                booked_rooms = booking.booked_rooms.filter(status__in=['Confirmed','confirmed'])  
                                logger.info("Booking ID %s: Found %d booked rooms with status 'Confirmed'", booking.id, booked_rooms.count())

                                if booked_rooms.exists(): 
                                    # Update the availability of associated rooms to True
                                    logger.info(f"\n\n booked_rooms: {booked_rooms}\n\n")
                                    logger.info("Found %d booked rooms to update for booking ID %s", booked_rooms.count(), booking.id)
                                    room_ids = booked_rooms.values_list('room_id', flat=True)  # Get IDs of affected rooms
                                    RoomManagement.objects.filter(id__in=room_ids).update(availability=True)
                                    logger.info("Set availability to True for rooms: %s", list(room_ids))
                                    updated_count = booked_rooms.update(status='completed')
                                    total_completed += updated_count
                                    booking.save()
                                    logger.info("Updated %d booked rooms to 'completed' for booking ID %s", updated_count, booking.id)
                                    
                                else:
                                    logger.info("No booked rooms to update for booking ID %s.", booking.id)
                            else:
                                logger.info("No bookings to update for booking ID %s.", booking.id)
                    if total_completed > 0:
                        logger.info("Updated %d booked rooms to 'completed' for hotel ID %s.", total_completed, hotel.id)
                    else:
                        logger.info("No booked rooms to update for hotel ID %s.", hotel.id)
                else:
                    logger.warning("Hotel ID %s: Check-in or check-out time is not set.", hotel.id)
        else:
            logger.info(f"No hotels found")
    except Exception as e:
        logger.info(f"\nUpdate completed booking. Exception raised for hotel. Exception: {e}\n")
    try:
        logger.info(f"\n\n\n\n <------------- Enter for chalet ---------------->>>>>\n\n\n")
        if chalets:
            for chalet in chalets:
                checkin_time = chalet.checkin_time
                checkout_time = chalet.checkout_time
                if checkin_time and checkout_time:

                    chalet_bookings = ChaletBooking.objects.filter(
                        chalet=chalet,
                        status="check-in",
                        checkout_date__lte=now.date()
                    )
                    logger.info("chalet ID %s: Found %d bookings to process", chalet.id, chalet_bookings.count())
                    if chalet_bookings:
                        total_completed = 0
                        updated_count = 0
                        for booking in chalet_bookings:
                            logger.info("Processing booking ID %s for chalet ID %s", booking.id, chalet.id)
                            # Calculate the full checkout datetime based on booking's checkout_date and hotel's checkout_time
                            chalet_checkout_datetime = timezone.make_aware(
                                timezone.datetime.combine(booking.checkout_date, checkout_time)
                            )
                            logger.info("Booking ID %s: Checkout datetime %s", booking.id, chalet_checkout_datetime)
                            logger.info(f"\nnow >= chalet_checkout_datetime: {now.date() >= booking.checkout_date}\n ------> \n{now.date()}---> type: {type(now.date())} ----> \n{booking.checkout_date} ---> type: {type(booking.checkout_date)}")
                            if now.date() >= booking.checkout_date:
                                logger.info("Current time is past checkout time for booking ID %s", booking.id)

                                if booking.status in ['check-in', 'Check-In']:
                                    logger.info("Booking ID %s: Found %d booked chalet with status 'Check-In'", booking.id)
                                    booking.status = 'completed'
                                    booking.save()
                                    updated_count += updated_count
                                    total_completed += updated_count
                                    logger.info("Updated %d booked chalet to 'completed' for booking ID %s", updated_count, booking.id)
                                else:
                                    logger.info("No booked chalets to update for booking ID %s.", booking.id)
                        if total_completed > 0:
                            logger.info("Updated %d booked rooms to 'completed' for chalet ID %s.", total_completed, chalet.id)
                        else:
                            logger.info("No booked rooms to update for chalet ID %s.", chalet.id)
                    else:
                        logger.info(f"No bookings ")
                else:
                    logger.warning("chalet ID %s: Check-in or check-out time is not set.", chalet.id)
        else:
            logger.info(f"No hotels found")
    except Exception as e:
        logger.info(f"\nUpdate completed booking. Exception raised for Chalet. Exception: {e}\n")

@app.task(name='mark_promotions_inactive')
def mark_promotions_inactive():
    from chalets.models import Promotion
    now = timezone.now().date()  # Get the current date
    logger.info("Marking promotions as inactive. Current date: %s", now)

    # Find promotions whose end_date has passed and are still active
    promotions_to_update = Promotion.objects.filter(
        end_date__lt=now,
        status='active'
    )

    if promotions_to_update.exists():
        logger.info("Found %d promotions to mark as inactive.", promotions_to_update.count())

        # Update promotions' status to 'inactive'
        updated_count = promotions_to_update.update(status='inactive')
        logger.info("Successfully updated %d promotions to 'inactive'.", updated_count)
    else:
        logger.info("No promotions found to mark as inactive.")



@app.task(name='update_booking_status')
def update_booking_status():
    """
    Main function to update booking statuses.
    """
    try:
        update_pending_to_rejected()
    except Exception as e:
        logger.error(f"Error in update_pending_to_rejected: {e}")

    try:
        update_confirmed_to_expired()
    except Exception as e:
        logger.error(f"Error in update_confirmed_to_expired: {e}")

def update_pending_to_rejected():
    from vendor.models import Booking
    """
    Update the status of 'pending' bookings to 'rejected' if they exceed the 10-minute threshold.
    """

    try:
        objs = Booking.objects.filter(is_deleted=False, status="pending")
        for obj in objs:
            try:
                get_created_time = obj.created_date
                if isinstance(get_created_time, str):
                    get_created_time = datetime.fromisoformat(get_created_time)

                dt_plus_10 = get_created_time + timedelta(minutes=10)
                if now() > dt_plus_10:
                    
                    handle_rejection(obj,"hotel")
            except Exception as e:
                logger.error(f"Error processing booking ID {obj.id} in update_pending_to_rejected: {e}")
    except Exception as e:
        logger.error(f"Error fetching pending bookings: {e}")

def handle_rejection(booking,source):
    from api.function import update_room_availability
    """
    Handle the rejection of a booking by updating its status and logging the action.
    """
    
    
    try:
        booking.status = "rejected"
        booking.save()
        if source == "hotel":
            update_room_availability(booking)
        else:
            booking.chalet.is_booked = False
            booking.chalet.save()
            booking.save()
        logger.info(f"Booking ID {booking.id} has been rejected.")
        message = f"Booking is rejected"
        return message
    except Exception as e:
        logger.error(f"Error handling rejection for booking ID {booking.id}: {e}")

def update_confirmed_to_expired():
    from vendor.models import Booking

    """
    Update the status of 'booked' bookings to 'expired' if they exceed the 30-minute threshold.
    """

    try:
        objs = Booking.objects.filter(is_deleted=False, status="booked")
        for obj in objs:
            try:
                get_created_time = obj.created_date
                if isinstance(get_created_time, str):
                    get_created_time = datetime.fromisoformat(get_created_time)

                dt_plus_30 = get_created_time + timedelta(minutes=30)
                if now() > dt_plus_30:
                    handle_expired(obj,"hotel")
            except Exception as e:
                logger.error(f"Error processing booking ID {obj.id} in update_booked_to_expired: {e}")
    except Exception as e:
        logger.error(f"Error fetching booked bookings: {e}")

def handle_expired(booking,source):
    from api.function import update_room_availability
    """
    Handle the expiration of a booking by updating its status and logging the action.
    """
    try:
        booking.status = "expired"
        booking.save()
        if source == "hotel":
            update_room_availability(booking)
        else:
            booking.chalet.is_booked = False
            booking.chalet.save()
            booking.save()
        logger.info(f"Booking ID {booking.id} has been marked as expired.")
        message = f"Booking got expired"
        return message
    except Exception as e:
        logger.error(f"Error handling expiration for booking ID {booking.id}: {e}")
        


@app.task(name='update_chaletbooking_status')
def update_chaletbooking_status():
    """
    Main function to update booking statuses.
    """
    try:
        update_chalet_pending_to_rejected()
    except Exception as e:
        logger.error(f"Error in update_pending_to_rejected: {e}")

    try:
        update_chalet_confirmed_to_expired()
    except Exception as e:
        logger.error(f"Error in update_confirmed_to_expired: {e}")

def update_chalet_pending_to_rejected():
    from chalets.models import ChaletBooking 
    """
    Update the status of 'pending' bookings to 'rejected' if they exceed the 10-minute threshold.
    """

    try:
        objs = ChaletBooking.objects.filter(is_deleted=False, status="pending")
        for obj in objs:
            try:
                get_created_time = obj.created_date
                if isinstance(get_created_time, str):
                    get_created_time = datetime.fromisoformat(get_created_time)

                dt_plus_10 = get_created_time + timedelta(minutes=10)
                if now() > dt_plus_10:
                    handle_rejection(obj,"chalet")
            except Exception as e:
                logger.error(f"Error processing booking ID {obj.id} in update_pending_to_rejected: {e}")
    except Exception as e:
        logger.error(f"Error fetching pending bookings: {e}")


def update_chalet_confirmed_to_expired():
    from chalets.models import ChaletBooking 
    """
    Update the status of 'booked' bookings to 'expired' if they exceed the 30-minute threshold.
    """

    try:
        objs = ChaletBooking.objects.filter(is_deleted=False, status="booked")
        for obj in objs:
            try:
                get_created_time = obj.created_date
                if isinstance(get_created_time, str):
                    get_created_time = datetime.fromisoformat(get_created_time)

                dt_plus_30 = get_created_time + timedelta(minutes=30)
                if now() > dt_plus_30:
                    handle_expired(obj,"chalet")
            except Exception as e:
                logger.error(f"Error processing booking ID {obj.id} in update_booked_to_expired: {e}")
    except Exception as e:
        logger.error(f"Error fetching booked bookings: {e}")




# Define the task schedule
app.conf.beat_schedule = {
    "completed_booking": {
        "task": "completed_booking",
        "schedule":crontab(hour=1),
    },
    "mark_promotions_inactive": {
        "task": "mark_promotions_inactive",
        "schedule": crontab(minute=0, hour=0),  # Run daily at midnight
    },
    "update_booking_status": {
        "task": "update_booking_status",
        "schedule": crontab(minute="*/5"),
    },
    "update_chaletbooking_status": {
        "task": "update_chaletbooking_status",
        "schedule": crontab(minute="*/5"),
    },
}

app.conf.timezone = 'UTC'


