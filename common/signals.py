from datetime import datetime
import logging

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from Bookingapp_1969 import settings
from chalets.models import Chalet, ChaletBooking, ChaletImage, PropertyManagement, chaletDocument,Notification
from common.models import RefundTransaction, Transaction
from user.models import  User, VendorProfile
from vendor.models import Amenity, City, Hotel, HotelDocument, HotelImage, MealPrice, RecentReview, RoomManagement, RoomImage,Bookedrooms, Booking   # Import from user app
from common.utils import create_notification, fetch_coordinates_from_api, send_firebase_notification  # Notification helper
from common.emails import notify_booking_aggregator


logger = logging.getLogger('lessons')
channel_layer = get_channel_layer()

# Helper function to notify both the hotel owner and super admin
def notify_super_admin_and_vendor(user, hotel, message, message_arabic, notification_type, is_vendor=False):
    try:
        # Notify Super Admin
        super_admins = User.objects.filter(is_superuser=True)
        for admin in super_admins:
            # Remove the "View More" link for super admins
            admin_message = message
            admin_message_arabic = message_arabic
            if not is_vendor:
                admin_message = message.split('<a href')[0]  # Remove the hyperlink part
                admin_message_arabic = message_arabic.split('<a href')[0]  # Remove the hyperlink part
            
            create_notification(user=admin, notification_type=notification_type, message=admin_message, message_arabic=admin_message_arabic)
            logger.info(f"Notification sent to super admin {admin.email} with message: {admin_message}")

        # Notify Hotel Owner (Vendor)
        if hotel.vendor and hotel.vendor.user:
            # Keep the original message with the "View More" link for vendors
            create_notification(user=hotel.vendor.user, notification_type=notification_type, message=message, message_arabic=message_arabic)
            logger.info(f"Notification sent to vendor {hotel.vendor.user.email} with message: {message}")
    except Exception as e:
        logger.error(f"Error in notify_super_admin_and_vendor: {e}")
# @receiver(post_save, sender=ChaletBooking)
# def notify_booking_status_change(sender, instance, created, **kwargs):
#     """
#     Notify on Booking status update and send WebSocket notification.
#     """
#     try:
#         if created:
#             logger.info(f"New booking created with ID {instance.id}")
#         else:
#             logger.info(f"Booking status updated for ID {instance.id}: {instance.status}")

#             # Notification logic for rejected or cancelled bookings
#             if instance.status in ['rejected', 'cancelled']:
#                 message = f"Booking for '{instance.chalet.name}' has been {instance.status}."
#                 message_arabic = f"تم {instance.status} الحجز لـ '{instance.chalet.name}'."
#                 notification_type = f'booking_{instance.status}'

#                 # Notify super admins and vendors
#                 notify_super_admin_and_vendor(instance.user, instance.chalet, message,message_arabic, notification_type)

#                 logger.info(f"Notification sent for booking {instance.id} with status {instance.status}")

#             # WebSocket notification for status update
#             booking_update = {
#                 'type': 'send_booking_update',
#                 'booking_id': instance.id,
#                 'hotel_name': instance.chalet.name if instance.chalet else "Unknown",
#                 'status': instance.status,
#                 'timestamp': datetime.now().isoformat(),
#             }

#             user_id = instance.user.user.id
#             if user_id:
#                 async_to_sync(channel_layer.group_send)(
#                     f"booking_updates_{user_id}",
#                     booking_update
#                 )
#                 logger.info(f"WebSocket status update sent: {booking_update}")
#             else:
#                 logger.warning("No user associated with this booking, WebSocket not sent.")

#     except Exception as e:
#         logger.error(f"Error in notify_booking_status_change: {e}")


@receiver(post_save, sender=Bookedrooms)
def notify_booked_room_status_change(sender, instance, created, **kwargs):
    """
    Notify on Bookedrooms status change (e.g., cancelled, confirmed, completed) and send Firebase notifications.
    """
    try:
        if created:
            if not instance.room.room_types.room_types or not instance.booking or not instance.booking.hotel:
                logger.warning(f"Bookedrooms instance has incomplete data: Room, Booking, or Hotel is None.")
                return
            
            # Log for a newly created booked room
            logger.info(f"Booked room {instance.room.room_types.room_types} created for booking {instance.booking.id}")
        else:
            if not instance.booking or not instance.booking.hotel or not instance.booking.user:
                logger.warning(f"Bookedrooms instance has incomplete data: Booking, Hotel, or User is None.")
                return
            
            # Firebase notification title and message
            firebase_title = None
            firebase_message = None
            message=None
            message_arabic=None
            firebase_data = {}
            room_count = Bookedrooms.objects.filter(booking=instance.booking).count()
            if room_count > 1:
                logger.info(f"Skipping duplicate notification for booking ID {instance.booking.id}.")
                return

            if instance.booking.status == 'cancelled':
                # Notify for booking cancellation
                message = f"Room booking of '{instance.booking.hotel.name}' has been cancelled."
                message_arabic = f"تم إلغاء حجز الغرفة في '{instance.booking.hotel.name}'."
                notification_type = 'booking_cancelled'
                firebase_title = f"Booking Cancelled"
                firebase_message = f"Your booking for '{instance.booking.hotel.name}' has been cancelled."
                firebase_data = {'type': 'booking_cancelled'}
                logger.info(f"Room booking for Hotel '{instance.booking.hotel.name}' with ID {instance.booking.id} has been cancelled.")
            elif instance.booking.status == 'pending':
                logger.info("pending condition entered")
                # Notify for booking confirmation
                domain = settings.DOMAIN_NAME.rstrip('/')
                message = f"""
                            <h5>New Room Booking Request</h5>
                            <p>
                                A guest has requested to book a '{instance.room.room_types.room_types}' room 
                                from {instance.booking.checkin_date} to {instance.booking.checkout_date}.
                            </p>
                            <a href="{domain}/vendor/booking/{instance.booking.id}" 
                            class="view-more" target="_blank" text-decoration: none;">
                            View More
                            </a>
                            """
                message_arabic = f"""
                                    <h5>طلب حجز غرفة جديد</h5>
                                    <p>
                                        قام أحد الضيوف بطلب حجز غرفة '{instance.room.room_types.room_types}'  
                                        من {instance.booking.checkin_date} إلى {instance.booking.checkout_date}.
                                    </p>
                                    <a href="{domain}/vendor/booking/{instance.booking.id}" 
                                    class="view-more" target="_blank" style="text-decoration: none;">
                                        عرض المزيد
                                    </a>
                                """

                notification_type = 'booking_confirmed'
                firebase_title = f"Booking Confirmed"
                firebase_message = f"Your booking for '{instance.booking.hotel.name}' has been confirmed."
                firebase_data = {'type': 'booking_confirmed'}
                logger.info(f"Room booking for Hotel '{instance.booking.hotel.name}' with ID {instance.booking.id} has been confirmed.")
            elif instance.booking.status == 'completed':
                # Notify for booking completion
                message = f"Room booking for '{instance.booking.hotel.name}' has been completed."
                message_arabic = f"تم إكمال حجز الغرفة في '{instance.booking.hotel.name}'."
                notification_type = 'booking_completed'
                firebase_title = f"Booking Completed"
                firebase_message = f"Your stay at '{instance.booking.hotel.name}' has been marked as completed."
                firebase_data = {'type': 'booking_completed'}
                logger.info(f"Room booking for Hotel '{instance.booking.hotel.name}' with ID {instance.booking.id} has been completed.")

            if message and firebase_title and firebase_message:
                # Send notification to super admin and vendor
                notify_super_admin_and_vendor(instance.booking.user, instance.booking.hotel, message, message_arabic, notification_type, is_vendor=False)

                # Check if the user has a valid Firebase token
                if not instance.booking.user.firebase_token:
                    logger.warning(f"User {instance.booking.user.id} does not have a valid Firebase token.")
                    return

                # Send Firebase notification
                firebase_result = send_firebase_notification(
                    device_token=instance.booking.user.firebase_token,
                    title=firebase_title,
                    body=firebase_message,
                    data=firebase_data
                )
                logger.info(f"Firebase notification sent for user {instance.booking.user.id} with result: {firebase_result}")
    except AttributeError as ae:
        logger.error(f"Attribute error in notify_booked_room_status_change: {ae}")
    except Exception as e:
        logger.error(f"Unexpected error in notify_booked_room_status_change: {e}")

@receiver(post_save, sender=RecentReview)
def notify_review_created(sender, instance, **kwargs):
    hotel_owner = instance.hotel.vendor.user
    message = f"A new review for Hotel - {instance.hotel.name} has been submitted."
    message_arabic = f"تم إرسال مراجعة جديدة للفندق - {instance.hotel.name}."
    create_notification(user=hotel_owner, notification_type='review', message=message,message_arabic=message_arabic)

# New Amenity notifications for all vendors
@receiver(post_save, sender=Amenity)
def notify_new_amenity(sender, instance, created, **kwargs):
    if created:
        message = f"A new amenity '{instance.amenity_name}' has been added."
        message_arabic = f"تمت إضافة وسيلة راحة جديدة '{instance.amenity_name}'."
        notification_type = 'amenity_added'
        
        # Notify all vendors
        for vendor_profile in VendorProfile.objects.all():
            create_notification(user=vendor_profile.user, notification_type=notification_type, message=message,message_arabic=message_arabic)

# Signal for Hotel model changes
@receiver(post_save, sender=Hotel)
def notify_hotel_changes(sender, instance, created, **kwargs):
    if created:
        message = f"New hotel <strong>{instance.name}</strong> has been created."
        message_arabic = f"تم إنشاء فندق جديد <strong>{instance.name}</strong>."
        notification_type = 'hotel_created'
    else:
        message = f"Hotel <strong>{instance.name}</strong> has been updated."
        message_arabic = f"تم تحديث الفندق <strong>{instance.name}</strong>."
        notification_type = 'hotel_updated'
    
    notify_super_admin_and_vendor(None, instance, message,message_arabic, notification_type)

@receiver(post_delete, sender=Hotel)
def notify_hotel_deleted(sender, instance, **kwargs):
    message = f"Hotel '{instance.name}' has been deleted."
    message_arabic = f"تم حذف الفندق '{instance.name}'."
    notification_type = 'hotel_deleted'
    notify_super_admin_and_vendor(None,instance, message,message_arabic, notification_type)

# Signal for HotelImage model changes
@receiver(post_save, sender=HotelImage)
def notify_hotel_image_changes(sender, instance, created, **kwargs):
    message = f"Image for hotel '{instance.hotel.name}' has been {'added' if created else 'updated'}."
    message_arabic = f"تم {'إضافة' if created else 'تحديث'} صورة الفندق '{instance.hotel.name}'."
    notification_type = 'hotel_image_updated'
    notify_super_admin_and_vendor(None,instance.hotel, message,message_arabic, notification_type)

@receiver(post_delete, sender=HotelImage)
def notify_hotel_image_deleted(sender, instance, **kwargs):
    message = f"An image for hotel '{instance.hotel.name}' has been deleted."
    message_arabic = f"تم حذف صورة الفندق '{instance.hotel.name}'."
    notification_type = 'hotel_image_deleted'
    notify_super_admin_and_vendor(None,instance.hotel, message,message_arabic, notification_type)

# Signal for HotelDocument model changes
@receiver(post_save, sender=HotelDocument)
def notify_hotel_document_changes(sender, instance, created, **kwargs):
    message = f"Document for hotel '{instance.hotel.name}' has been {'added' if created else 'updated'}."
    message_arabic = f"تم {'إضافة' if created else 'تحديث'} مستند الفندق '{instance.hotel.name}'."
    notification_type = 'hotel_document_updated'
    notify_super_admin_and_vendor(None,instance.hotel, message,message_arabic, notification_type)

@receiver(post_delete, sender=HotelDocument)
def notify_hotel_document_deleted(sender, instance, **kwargs):
    message = f"A document for hotel '{instance.hotel.name}' has been deleted."
    message_arabic = f"تم حذف مستند الفندق '{instance.hotel.name}'."
    notification_type = 'hotel_document_deleted'
    notify_super_admin_and_vendor(instance.hotel, message,message_arabic, notification_type)

# Signal for MealPrice model changes
@receiver(post_save, sender=MealPrice)
def notify_meal_price_changes(sender, instance, created, **kwargs):
    message = f"Meal price for '{instance.meal_type}' in hotel '{instance.hotel.name}' has been {'added' if created else 'updated'}."
    message_arabic = f"تم {'إضافة' if created else 'تحديث'} سعر الوجبة '{instance.meal_type}' في الفندق '{instance.hotel.name}'."
    notification_type = 'meal_price_updated'
    notify_super_admin_and_vendor(None, instance.hotel, message,message_arabic, notification_type)

@receiver(post_delete, sender=MealPrice)
def notify_meal_price_deleted(sender, instance, **kwargs):
    message = f"Meal price for '{instance.meal_type}' in hotel '{instance.hotel.name}' has been deleted."
    message_arabic = f"تم حذف سعر الوجبة '{instance.meal_type}' في الفندق '{instance.hotel.name}'."
    notification_type = 'meal_price_deleted'
    notify_super_admin_and_vendor(None, instance.hotel, message,message_arabic, notification_type)

# Signal for RoomManagement model changes
@receiver(post_save, sender=RoomManagement)
def notify_room_management_changes(sender, instance, created, **kwargs):
    message = f"Room '{instance.room_types.room_types}' for hotel '{instance.hotel.name}' has been {'added' if created else 'updated'}."
    message_arabic = f"تم {'إضافة' if created else 'تحديث'} الغرفة '{instance.room_types.room_types_arabic}' في الفندق '{instance.hotel.name}'."
    notification_type = 'room_management_updated'
    notify_super_admin_and_vendor(None, instance.hotel, message,message_arabic, notification_type)

@receiver(post_delete, sender=RoomManagement)
def notify_room_management_deleted(sender, instance, **kwargs):
    message = f"Room '{instance.room_types.room_types}' for hotel '{instance.hotel.name}' has been deleted."
    message_arabic = f"تم حذف الغرفة '{instance.room_types.room_types}' في الفندق '{instance.hotel.name}'."
    notification_type = 'room_management_deleted'
    notify_super_admin_and_vendor(None, instance.hotel, message,message_arabic, notification_type)

# Signal for RoomImage model changes
# @receiver(post_save, sender=RoomImage)
# def notify_roomtype_image_changes(sender, instance, created, **kwargs):
#     room_management = RoomManagement.objects.filter(image=instance)
#     for room in room_management:
#         if room and room.hotel:
#             message = f"Room type image for hotel '{room.hotel.name}' has been {'added' if created else 'updated'}."
#             message_arabic = f"تم {'إضافة' if created else 'تحديث'} صورة نوع الغرفة في الفندق '{room.hotel.name}'."
#             notification_type = 'roomtype_image_updated'
#             notify_super_admin_and_vendor(None, room.hotel, message,message_arabic, notification_type)
#         else:
#             # Handle the case where no associated RoomManagement or Hotel is found
#             message = f"A Room type image has been {'added' if created else 'updated'}, but no associated hotel was found."
#             message_arabic = f"تم {'إضافة' if created else 'تحديث'} صورة نوع الغرفة، ولكن لم يتم العثور على فندق مرتبط."
#             notification_type = 'roomtype_image_updated'
#             notify_super_admin_and_vendor(None, None, message,message_arabic,message_arabic, notification_type)

# @receiver(post_delete, sender=RoomImage)
# def notify_roomtype_image_deleted(sender, instance, **kwargs):
#     message = f"Room type image for hotel '{instance.hotel.name}' has been deleted."
#     message_arabic = f"تم حذف صورة نوع الغرفة في الفندق '{instance.hotel.name}'."
#     notification_type = 'roomtype_image_deleted'
#     notify_super_admin_and_vendor(None, instance.hotel, message,message_arabic, notification_type)



# Helper function to send notifications related to chalet
def notify_super_admin_and_vendor_for_chalet(chalet, message, message_arabic, notification_type, is_vendor=False):
    """
    Notify super admins and chalet vendors about booking changes.
    The "View More" hyperlink is hidden for super admins.
    """
    try:
        # Notify Super Admin
        super_admins = User.objects.filter(is_superuser=True)
        for admin in super_admins:
            # Remove the "View More" link for super admins
            admin_message = message
            admin_message_arabic = message_arabic
            if not is_vendor:
                admin_message = message.split('<a href')[0]  # Remove the hyperlink part
                admin_message_arabic = message_arabic.split('<a href')[0]  # Remove the hyperlink part
            
            create_notification(user=admin, notification_type=notification_type, message=admin_message, message_arabic=admin_message_arabic)
            logger.info(f"Notification sent to super admin {admin.email} with message: {admin_message}")

        # Notify Chalet Owner (Vendor)
        if chalet.vendor and chalet.vendor.user:
            # Keep the original message with the "View More" link for vendors
            create_notification(user=chalet.vendor.user, notification_type=notification_type, message=message, message_arabic=message_arabic)
            logger.info(f"Notification sent to vendor {chalet.vendor.user.email} with message: {message}")
    except Exception as e:
        logger.error(f"Error in notify_super_admin_and_vendor_for_chalet: {e}")

@receiver(post_save, sender=ChaletBooking)
def notify_chalet_changes_booking(sender, instance, created, **kwargs):
    """
    Notify on Chalet booking status change (e.g., cancelled, confirmed, completed) and send Firebase notifications.
    """
    logger.info(f"\n\n\n notify_chalet_changes signal function entered \n\n\n\n")
    try:

        logger.info("Signal triggered for ChaletBooking ID %s", instance.id)
        if created:
            if not instance.chalet or not instance.user:
                logger.warning(f"ChaletBooking instance has incomplete data: Chalet or User is None.")
                return
            
            # Log for a newly created chalet booking
            logger.info(f"Chalet booking created for chalet {instance.chalet.name} and user {instance.user.id}")
            if instance.status == 'pending':
                # Notify for booking confirmation
                domain = settings.DOMAIN_NAME.rstrip('/')
                message = f"""
                            <h5>New Chalet Booking Request</h5>
                            <p>
                                A guest has requested to book a '{instance.chalet.name}' Chalet 
                                from {instance.checkin_date} to {instance.checkout_date}.
                            </p>
                            <a href="{domain}/chalets/chalet/view/{instance.id}" 
                            class="view-more" target="_blank" text-decoration: none;">
                            View More
                            </a>
                        """
                message_arabic = f"""
                                    <h5>طلب حجز شاليه جديد</h5>
                                    <p>
                                        قام أحد الضيوف بطلب حجز الشاليه '{instance.chalet.name}'  
                                        من {instance.checkin_date} إلى {instance.checkout_date}.
                                    </p>
                                    <a href="{domain}/chalets/chalet/view/{instance.id}" 
                                    class="view-more" target="_blank" style="text-decoration: none;">
                                        عرض المزيد
                                    </a>
                                """

                notification_type = 'booking_confirmed'
                firebase_title = "Booking Confirmed"
                firebase_message = f"Your booking for the chalet '{instance.chalet.name}' has been confirmed."
                firebase_data = {'type': 'booking_confirmed'}
                logger.info(f"Chalet booking for Chalet '{instance.chalet.name}' with ID {instance.id} has been confirmed.")

        else:
            if not instance.chalet or not instance.user:
                logger.warning(f"ChaletBooking instance has incomplete data: Chalet or User is None.")
                return

            # Firebase notification title and message
            message = None
            message_arabic = None
            firebase_title = None
            firebase_message = None
            firebase_data = {}

            if instance.status == 'cancelled':
                # Notify for booking cancellation
                message = f"Chalet booking for '{instance.chalet.name}' has been cancelled."
                message_arabic = f"تم إلغاء حجز الشاليه '{instance.chalet.name}'."
                notification_type = 'booking_cancelled'
                firebase_title = "Booking Cancelled"
                firebase_message = f"Your booking for the chalet '{instance.chalet.name}' has been cancelled."
                firebase_data = {'type': 'booking_cancelled'}
                logger.info(f"Chalet booking for Chalet '{instance.chalet.name}' with ID {instance.id} has been cancelled.")


            elif instance.status == 'completed':
                # Notify for booking completion
                message = f"Chalet booking for '{instance.chalet.name}' has been completed."
                message_arabic = f"تم إكمال حجز الشاليه '{instance.chalet.name}'."
                notification_type = 'booking_completed'
                firebase_title = "Booking Completed"
                firebase_message = f"Your stay at the chalet '{instance.chalet.name}' has been marked as completed."
                firebase_data = {'type': 'booking_completed'}
                logger.info(f"Chalet booking for Chalet '{instance.chalet.name}' with ID {instance.id} has been completed.")

        if message and firebase_title and firebase_message:
            # Send notification to super admin and vendor
            notify_super_admin_and_vendor_for_chalet(instance.chalet, message, message_arabic, notification_type, is_vendor=False)

            # Check if the user has a valid Firebase token
            if not instance.user.firebase_token:
                logger.warning(f"User {instance.user.id} does not have a valid Firebase token.")
                return

            # Send Firebase notification
            firebase_result = send_firebase_notification(
                device_token=instance.user.firebase_token,
                title=firebase_title,
                body=firebase_message,
                data=firebase_data
            )
            logger.info(f"Firebase notification sent for user {instance.user.id} with result: {firebase_result}")
    except AttributeError as ae:
        logger.error(f"Attribute error in notify_chalet_changes: {ae}")
    except Exception as e:
        logger.error(f"Unexpected error in notify_chalet_changes: {e}")





@receiver(post_save, sender=Booking)
def notify_hotel_changes_booking(sender, instance, created, **kwargs):
    """
    Notify about Hotel booking status changes and send WebSocket notifications.
    """
    try:
        logger.info("\n\n notify_hotel_changes signal function entered \n\n")

        if created:
            logger.info(f"Hotel booking **created** for chalet {instance.hotel.name} and user {instance.user.id}")
        else:
            logger.info(f"Hotel Booking status updated - ID: {instance.id}, New Status: {instance.status}")

        # Construct WebSocket notification payload
        hotel_update = {
            'type': 'send_booking_update',  
            'booking_id': instance.booking_id,
            'hotel_name': instance.hotel.name if instance.hotel else "Unknown",
            'status': instance.status,
            'timestamp': datetime.now().isoformat(),
        }

        # Check if the user exists before sending WebSocket notification
        if instance.user:
            group_name = f"booking_updates_{instance.user.user.id}"  
            logger.info(f"Sending WebSocket notification to group: {group_name} with data: {hotel_update}")

            async_to_sync(channel_layer.group_send)(
                group_name,
                hotel_update
            )

            logger.info("WebSocket notification **successfully sent**!")
        else:
            logger.warning("No user associated with this hotel booking. WebSocket notification not sent.")

    except Exception as e:
        logger.error(f"Error in notify_hotel_changes_booking: {e}", exc_info=True)


@receiver(post_delete, sender=ChaletBooking)
def notify_chalet_deleted(sender, instance, **kwargs):
    """
    Notify when a ChaletBooking is deleted.
    """
    try:
        logger.info("notify_chalet_deleted signal function entered")

        message = f"Booking for chalet {instance.chalet.name} has been cancelled."
        message_arabic = f"تم إلغاء الحجز للشاليه {instance.chalet.name}."
        notification_type = 'booking_cancelled'

        notify_super_admin_and_vendor_for_chalet(instance.chalet, message,message_arabic, notification_type)
        notify_super_admin_and_vendor(instance.user, instance.chalet, message,message_arabic, notification_type)

        logger.info(f"Chalet booking **deleted** - ID: {instance.id}, Name: {instance.chalet.name}")

        # WebSocket notification for cancellation
        chalet_cancel_update = {
            'type': 'send_chalet_update',
            'booking_id': instance.id,
            'chalet_name': instance.chalet.name if instance.chalet else "Unknown",
            'status': 'cancelled',
            'timestamp': datetime.now().isoformat(),
        }

        if instance.user:
            async_to_sync(channel_layer.group_send)(
                f"chalet_booking_updates_{instance.user.id}",
                chalet_cancel_update
            )
            logger.info(f"WebSocket chalet **cancellation notification sent**!")

    except Exception as e:
        logger.error(f"Error in notify_chalet_deleted: {e}", exc_info=True)

    
# Signal for Chalet model changes
@receiver(post_save, sender=Chalet)
def notify_chalet_changes(sender, instance, created, **kwargs):
    if created:
        message = f"New chalet '{instance.name}' has been created."
        message_arabic = f"تم إنشاء شاليه جديد '{instance.name}'."
        notification_type = 'chalet_created'
    else:
        message = f"Chalet '{instance.name}' has been updated."
        message_arabic = f"تم تحديث الشاليه '{instance.name}'."
        notification_type = 'chalet_updated'
    
    notify_super_admin_and_vendor_for_chalet(instance, message,message_arabic, notification_type)

@receiver(post_delete, sender=Chalet)
def notify_chalet_deleted(sender, instance, **kwargs):
    message = f"Chalet '{instance.name}' has been deleted."
    message_arabic = f"تم حذف الشاليه '{instance.name}'."
    notification_type = 'chalet_deleted'
    notify_super_admin_and_vendor_for_chalet(instance, message,message_arabic, notification_type)

# Signal for ChaletImage model changes
@receiver(post_save, sender=ChaletImage)
def notify_chalet_image_changes(sender, instance, created, **kwargs):
    message = f"Image for chalet '{instance.chalet.name}' has been {'added' if created else 'updated'}."
    message_arabic = f"تم {'إضافة' if created else 'تحديث'} صورة الشاليه '{instance.chalet.name}'."
    notification_type = 'chalet_image_updated'
    notify_super_admin_and_vendor_for_chalet(instance.chalet, message,message_arabic, notification_type)

@receiver(post_delete, sender=ChaletImage)
def notify_chalet_image_deleted(sender, instance, **kwargs):
    message = f"An image for chalet '{instance.chalet.name}' has been deleted."
    message_arabic = f"تم حذف صورة الشاليه '{instance.chalet.name}'."
    notification_type = 'chalet_image_deleted'
    notify_super_admin_and_vendor_for_chalet(instance.chalet, message,message_arabic, notification_type)

# Signal for chaletDocument model changes
@receiver(post_save, sender=chaletDocument)
def notify_chalet_document_changes(sender, instance, created, **kwargs):
    message = f"Document for chalet '{instance.chalet.name}' has been {'added' if created else 'updated'}."
    message_arabic = f"تم {'إضافة' if created else 'تحديث'} مستند الشاليه '{instance.chalet.name}'."
    notification_type = 'chalet_document_updated'
    notify_super_admin_and_vendor_for_chalet(instance.chalet, message,message_arabic, notification_type)

@receiver(post_delete, sender=chaletDocument)
def notify_chalet_document_deleted(sender, instance, **kwargs):
    message = f"A document for chalet '{instance.chalet.name}' has been deleted."
    message_arabic = f"تم حذف مستند الشاليه '{instance.chalet.name}'."
    notification_type = 'chalet_document_deleted'
    notify_super_admin_and_vendor_for_chalet(instance.chalet, message,message_arabic, notification_type)

# Signal for PropertyManagement model changes
@receiver(post_save, sender=PropertyManagement)
def notify_property_management_changes(sender, instance, created, **kwargs):
    message = f"Room '{instance.room_number}' for chalet '{instance.chalet.name}' has been {'added' if created else 'updated'}."
    message_arabic = f"تم {'إضافة' if created else 'تحديث'} الغرفة '{instance.room_number}' في الشاليه '{instance.chalet.name}'."
    notification_type = 'property_management_updated'
    notify_super_admin_and_vendor_for_chalet(instance.chalet, message,message_arabic, notification_type)

@receiver(post_delete, sender=PropertyManagement)
def notify_property_management_deleted(sender, instance, **kwargs):
    message = f"Room '{instance.room_number}' for chalet '{instance.chalet.name}' has been deleted."
    message_arabic = f"تم حذف الغرفة '{instance.room_number}' في الشاليه '{instance.chalet.name}'."
    notification_type = 'property_management_deleted'
    notify_super_admin_and_vendor_for_chalet(instance.chalet, message,message_arabic, notification_type)

@receiver(post_save, sender=Notification, dispatch_uid="send_notification_to_user")
def send_notification_to_user(sender, instance, created, **kwargs):
    if created:
        instance.refresh_from_db()
        notification_data = {
            "id": instance.id,
            "message": instance.message,
            "timestamp": instance.created_at.isoformat(),
            "notification_type": instance.notification_type,
        }
        group_name = f'notifications_{instance.recipient.id}'
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "send_notification",
                "message": instance.message,
                "id": instance.id,
                "timestamp": instance.created_at.isoformat(),
                "notification_type": instance.notification_type,
            }
        )
@receiver(pre_save, sender=City)
def update_coordinates(sender, instance, **kwargs):
    """
    Update latitude and longitude when the city name changes or is newly created.
    """
    if instance.pk:  # If the city already exists, fetch the current name from the database
        old_city_name = City.objects.get(pk=instance.pk).name
        if old_city_name == instance.name:
            # City name hasn't changed; skip API call
            return

    # Fetch coordinates from the Google Maps API
    google_maps_api_key = settings.GOOGLE_MAPS_API_KEY
    city_name = instance.name or ""
    state_name = instance.state.name if instance.state else ""
    country_name = instance.state.country.name if instance.state and instance.state.country else ""
    latitude, longitude = fetch_coordinates_from_api( city_name,state_name,country_name,google_maps_api_key)

    # Update instance with new coordinates if valid values are returned
    if latitude is not None and longitude is not None:
        instance.latitude = latitude
        instance.longitude = longitude
        logger.info(f"City '{instance.name}' updated with coordinates: ({latitude}, {longitude})")
    else:
        logger.warning(f"Coordinates for city '{instance.name}' could not be fetched.")


@receiver(post_save, sender=Transaction)
def update_booking_status(sender, instance, **kwargs):
    if instance.transaction_status == "completed" :
            if instance.payment_type:
                    if instance.payment_type.name!='Cash':
                    # Update ChaletBooking status
                        chalet_bookings = ChaletBooking.objects.filter(transaction=instance)
                        for chalet_booking in chalet_bookings:
                            if chalet_booking.status != "confirmed":  # Only update if not already confirmed
                                chalet_booking.status = "confirmed"
                                chalet_booking.save()

                        # Update Booking status
                        hotel_bookings = Booking.objects.filter(transaction=instance)
                        for hotel_booking in hotel_bookings:
                            if hotel_booking.status != "confirmed":  # Only update if not already confirmed
                                hotel_booking.status = "confirmed"
                                hotel_booking.save()
    elif instance.transaction_status == "pending": 
            if instance.payment_type:
                    if instance.payment_type.name =='Cash':
                        # Update ChaletBooking status
                        chalet_bookings = ChaletBooking.objects.filter(transaction=instance)
                        for chalet_booking in chalet_bookings:
                            if chalet_booking.status != "confirmed":  # Only update if not already confirmed
                                chalet_booking.status = "confirmed"
                                chalet_booking.save()

                        # Update Booking status
                        hotel_bookings = Booking.objects.filter(transaction=instance)
                        for hotel_booking in hotel_bookings:
                            if hotel_booking.status != "confirmed":  # Only update if not already confirmed
                                hotel_booking.status = "confirmed"
                                hotel_booking.save()

@receiver(post_save, sender=RefundTransaction)
def notify_refund_processed(sender, instance, created, **kwargs):
    """
    Notify super admins and vendors when a refund is processed.
    """
    try:
        if instance.refund_status == 'Processed':
            message = f"Refund for transaction {instance.transaction.transaction_id} has been processed successfully."
            message_arabic = f"تمت معالجة استرداد المعاملة {instance.transaction.transaction_id} بنجاح."
            notification_type = 'refund_processed'

            # Notify all super admins
            super_admins = User.objects.filter(is_superuser=True)
            for admin in super_admins:
                create_notification(user=admin, notification_type=notification_type, message=message,message_arabic=message_arabic)
                logger.info(f"Refund notification sent to super admin {admin.email} for transaction {instance.transaction.transaction_id}")


            # Check if the refund is related to a hotel or chalet booking
            booking = Booking.objects.filter(transaction=instance.transaction).first()
            chalet_booking = ChaletBooking.objects.filter(transaction=instance.transaction).first()

            if booking and booking.hotel:
                vendor = booking.hotel.vendor  # Assuming `vendor` is a field in `Hotel`
                vendor_message = f"A refund has been processed for a booking at {booking.hotel.name}."
                message_arabic = f"تمت معالجة استرداد لحجز في {booking.hotel.name}."
            elif chalet_booking and chalet_booking.chalet:
                vendor = chalet_booking.chalet.vendor  # Assuming `vendor` is a field in `Chalet`
                vendor_message = f"A refund has been processed for a booking at {chalet_booking.chalet.name}."
                message_arabic = f"تمت معالجة استرداد لحجز في {chalet_booking.chalet.name}."
            else:
                vendor = None

            # Notify vendor if found
            if vendor:
                create_notification(user=vendor.user, notification_type=notification_type, message=vendor_message,message_arabic=message_arabic)
                logger.info(f"Refund notification sent to vendor {vendor.email} for transaction {instance.transaction.transaction_id}")

    
    except Exception as e:
        logger.error(f"Error in notify_refund_processed: {e}")


# @receiver(post_save, sender=ChaletBooking)
# def notify_booking_status_change(sender, instance, created, **kwargs):
#     """
#     Notify on Booking status update and send WebSocket notification.
#     """
#     try:
#         logger.info(f"Signal received for ChaletBooking ID {instance.id}, Created: {created}")

#         if created:
#             logger.info(f"New booking created: ID {instance.id}, User: {instance.user}, Chalet: {instance.chalet.name if instance.chalet else 'Unknown'}")
#         else:
#             logger.info(f"Booking status update detected: ID {instance.id}, New Status: {instance.status}")

#             # Handling rejected or cancelled bookings
#             if instance.status in ['rejected', 'cancelled']:
#                 message = f"Booking for '{instance.chalet.name if instance.chalet else 'Unknown'}' has been {instance.status}."
#                 message_arabic = f"تم {instance.status} الحجز لـ '{instance.chalet.name if instance.chalet else 'غير معروف'}'."
#                 notification_type = f'booking_{instance.status}'

#                 logger.debug(f"Preparing to send notification: {message} (Type: {notification_type})")
                
#                 notify_super_admin_and_vendor(instance.user, instance.chalet, message,message_arabic, notification_type)
#                 logger.info(f"Notification sent successfully for Booking ID {instance.id}, Status: {instance.status}")

#             # WebSocket notification logic
#             booking_update = {
#                 'type': 'send_booking_update',
#                 'booking_id': instance.booking_id,
#                 'chalet_name': instance.chalet.name if instance.chalet else "Unknown",
#                 'status': instance.status,
#                 'timestamp': datetime.now().isoformat(),
#             }

#             user = getattr(instance.user, 'user', None)  # Ensure user exists before accessing ID
#             if user:
#                 user_id = user.id
#                 group_name = f"booking_updates_{user_id}"

#                 logger.debug(f"Preparing WebSocket message: {booking_update} for group {group_name}")

#                 async_to_sync(channel_layer.group_send)(group_name, booking_update)
#                 logger.info(f"WebSocket update sent to {group_name} for Booking ID {instance.id}")
#             else:
#                 logger.warning(f"Booking ID {instance.id} has no associated user, skipping WebSocket notification.")

#     except Exception as e:
#         logger.error(f"Error in notify_booking_status_change: {e}", exc_info=True)


@receiver(post_save, sender=Booking)
def simple_test_signal(sender, instance, created, **kwargs):
    logger.info("Simple test signal triggered for Booking model")


from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

@receiver(post_save, sender=Booking)
def send_confirmation_email_signal(sender, instance, created, **kwargs):
    """
    Signal to send confirmation email when Booking status changes to 'confirmed'.
    """
    # import pdb;pdb.set_trace()
    if not created:  # Trigger only on update, not on creation
        try:
            # Fetch the previous instance to compare status
            previous_instance = Booking.objects.get(pk=instance.pk)

            # Check if status changed to 'confirmed'
            if instance.status == 'confirmed':
                logger.info(f"Booking {instance.booking_id} confirmed. Sending confirmation email.")

                # Prepare email context
                context = {
                    'id': instance.id,
                    'property_name': instance.hotel.name.upper(),
                    'Booking_Number': instance.booking_id,
                    'recipient_name': f"{instance.booking_fname} {instance.booking_lname}",
                    'checkin_date': instance.checkin_date,
                    'checkout_date': instance.checkout_date,
                    'Guests': instance.number_of_guests,
                    'transaction_id': instance.transaction.transaction_id if instance.transaction else "N/A",
                    'total_amount': instance.booked_price,  
                    'address': instance.hotel.address,
                    'contact_number': instance.booking_mobilenumber,
                    'qrcode': instance.qr_code_url,
                    'first_name': instance.booking_fname,
                    'second_name': instance.booking_lname,
                    'email': instance.booking_email,
                    'adults': instance.adults,
                    'children': instance.children
                }

                # Render email content
                html_content = render_to_string('chalet_booking_email.html', context)
                text_content = strip_tags(html_content)

                # Send email
                subject = f'Your Booking in {instance.hotel.name.upper()} Confirmed'
                email = EmailMultiAlternatives(
                    subject,
                    text_content,
                    settings.EMAIL_HOST_USER,
                    [instance.booking_email]
                )
                email.attach_alternative(html_content, "text/html")
                email.send()

                logger.info(f"Confirmation email sent to: {instance.booking_email}")

        except Booking.DoesNotExist:
            logger.error(f"Previous booking instance not found for ID: {instance.pk}")
        except Exception as e:
            logger.error(f"Error sending confirmation email: {e}")

@receiver(post_save, sender=ChaletBooking)
def send_confirmation_email_signal(sender, instance, created, **kwargs):
    """
    Signal to send confirmation email when Booking status changes to 'confirmed'.
    """
    # import pdb;pdb.set_trace()
    if not created:  # Trigger only on update, not on creation
        try:
            # Check if status changed to 'confirmed'
            if instance.status == 'confirmed':
                logger.info(f"Booking {instance.booking_id} confirmed. Sending confirmation email.")

                # Prepare email context
                context = {
                    'id': instance.id,
                    'property_name': instance.chalet.name.upper(),
                    'Booking_Number': instance.booking_id,
                    'recipient_name': f"{instance.booking_fname} {instance.booking_lname}",
                    'checkin_date': instance.checkin_date,
                    'checkout_date': instance.checkout_date,
                    'Guests': instance.number_of_guests,
                    'transaction_id': instance.transaction.transaction_id if instance.transaction else "N/A",
                    'total_amount': instance.booked_price,  
                    'address': instance.chalet.address,
                    'contact_number': instance.booking_mobilenumber,
                    'qrcode': instance.qr_code_url,
                    'first_name': instance.booking_fname,
                    'second_name': instance.booking_lname,
                    'email': instance.booking_email,
                    'adults': instance.adults,
                    'children': instance.children
                }

                # Render email content
                html_content = render_to_string('chalet_booking_email.html', context)
                text_content = strip_tags(html_content)

                # Send email
                subject = f'Your Booking in {instance.chalet.name.upper()} Confirmed'
                email = EmailMultiAlternatives(
                    subject,
                    text_content,
                    settings.EMAIL_HOST_USER,
                    [instance.booking_email]
                )
                email.attach_alternative(html_content, "text/html")
                email.send()

                logger.info(f"Confirmation email sent to: {instance.booking_email}")

        except Booking.DoesNotExist:
            logger.error(f"Previous booking instance not found for ID: {instance.pk}")
        except Exception as e:
            logger.error(f"Error sending confirmation email: {e}")



from django.db import transaction

@receiver(post_save, sender=Notification)
def remove_duplicate_notifications(sender, instance, **kwargs):
    """
    Signal to remove duplicate notifications with the same message
    for the same recipient only.
    """
    # Use transaction to ensure atomicity
    with transaction.atomic():
        # Remove duplicates only for the same recipient
        duplicates = Notification.objects.filter(
            recipient=instance.recipient,   # Ensure same user
            message=instance.message,
            notification_type=instance.notification_type,  # Ensure same type
            source=instance.source          # Ensure same source
        ).exclude(id=instance.id)

        # Delete older duplicates
        duplicates.delete()
