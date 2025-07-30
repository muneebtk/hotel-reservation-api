# import logging

# from django.db.models.signals import post_save, post_delete, pre_save
# from django.dispatch import receiver

# from chalets.models import ChaletBooking

# logger = logging.getLogger('lessons')
# # channel_layer = get_channel_layer()

# @receiver(post_save, sender=ChaletBooking)
# def notify_chalet_changes(sender, instance, created, **kwargs):
#     logger.info("notify_chalet_changes started")
#     try:
#         logger.info("Initialising chalet for chalet booking Id")
#         if not instance.booking_id:
#             instance.booking_id = f"CHBK{instance.id}"
#             instance.save()
#             logger.info(f" chalet Initialisation completed. Booking id : {instance.booking_id}")
#     except Exception as e:
#         logger.error(f"Exception occured in instance creating . Exception : {e}")
        
#     try:
#         logger.info(f"\n\n\n\n\n\nEntered before notify_chalet_changes_booking \n\n\n\n\n")
#         notify_chalet_changes_booking(sender, instance, created, **kwargs)
#     except Exception as e:
#         logger.info(f"\n\n\n\n\n\n Excepyion in notify_chalet_changes_booking. Exception: {e}\n\n\n\n\n")
