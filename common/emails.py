import threading
import logging
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from Bookingapp_1969 import settings
from vendor.models import Bookedrooms
            

logger = logging.getLogger('lessons')

         
class EmailThread(threading.Thread):
    def __init__(self, subject, html_content, recipient_list, sender):
        self.subject = subject
        self.recipient_list = recipient_list
        self.html_content = html_content
        self.sender = sender
        threading.Thread.__init__(self)

    def run(self):
        msg = EmailMessage(self.subject, self.html_content, self.sender, self.recipient_list)
        msg.content_subtype = 'html'
        msg.send()

def send_html_mail(subject, html_content, recipient_list, sender):
    EmailThread(subject, html_content, recipient_list, sender).start()

def send_email(subject=None,html=None,recipients=[]):
    allowed=True
    if allowed:
        sender=f'App Support <{settings.EMAIL_HOST_USER}>'
        send_html_mail(subject=subject,html_content=html,recipient_list=recipients,sender=sender)

# def notify_booking_aggregator(booking,property_type):
#     try:
#         if not booking or property_type:
#             logger.info("Passed None value argument to notify_booking_aggregator. Function not executed.")
#             return None
#         template="booking-aggregator-email.html"
#         aggregator_emails=['vishnu.pk@codesvera.com','developer@codesvera.com'] # Can be stored in .env and can be accessef from settings in future
#         if isinstance(booking, object):
#             logger.info("Verified booking object")
#             data={
#                 'check_in':None,
#                 'check_out':None,
#                 'customer_name':None,
#                 'booking_id':None,
#                 'customer_contact':None,
#                 'rooms':[],
#                 'rooms_count':None,
#                 'guests':None,
#                 'vendor_name':None,
#                 'vendor_contact':None,
#                 'vendor_email':None,
#                 'property_name':None,
#                 'property_address':None,
#                 'action_url':None
#             }
#             if property_type == 'hotel' and booking.hotel:
#                 logger.info("Verified hotel object is present within the booking")
#                 data['check_in']=booking.checkin_date
#                 data['check_out']=booking.checkout_date
#                 data['customer_name']=booking.get_guest_full_name()
#                 data['booking_id']=booking.booking_id
#                 data['customer_contact']=booking.booking_mobilenumber
#                 # data['rooms']=None
#                 data['rooms_count']=booking.number_of_booking_rooms
#                 # data['guests']=booking
#                 data['vendor_name']=booking.hotel.get_vendor_full_name()
#                 data['vendor_contact']=booking.hotel.office_number
#                 data['vendor_email']=booking.hotel.get_vendor_email()
#                 data['property_name']=booking.hotel.name
#                 data['property_address']=booking.hotel.address
#             elif property_type == 'chalet':
#                 pass
#             else:
#                 logger.info(f"Received unexpected property type in notify_booking_aggregator. Property type : {property_type}")
#                 return None
#             try:
#                 html=render_to_string(template,data)
#                 subject=f"Immediate action required! New Booking received for {data.property_name} #{data.booking_id}"
#                 send_email(subject=subject,html=html,recipients=aggregator_emails)
#                 return True
#             except Exception as e:
#                 logger.info(f"Exception occured in sending email from notify_booking_aggregator. Exception : {e}") 
#         else:
#             logger.info(f"Data type mismatch found in notify_booking_aggregator with booking variable. Booking : {booking} ({type(booking)})")
#     except Exception as e: 
#         logger.info(f"Exception occured in notify_booking_aggregator. Exception : {e}")
#     return None

def notify_booking_aggregator(booking, property_type):
    try:
        if not booking:
            logger.info("Booking is None. Function not executed.")
            return None

        if not property_type:
            logger.info("Property type is None. Function not executed.")
            return None

        if property_type not in ['hotel', 'chalet']:
            logger.info(f"Unexpected property type: {property_type}. Function not executed.")
            return None

        logger.info("Verified booking object and property type.")

        template = "booking-aggregator-email.html"
        logo_name="email-logo.png"
        logo_path=f"{getattr(settings, 'STATIC_URL','https://storage.1929way.app:9000/1929way-testserver/static/')}images/{logo_name}"
        aggregator_emails = getattr(settings, 'AGGREGATOR_EMAILS', [
            settings.SECONDRY_ADMIN_MAIL,
            settings.ADMIN_EMAIL
        ])

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
            'adults':None,
            'children':None,
            'logo_url':logo_path
        }

        def populate_hotel_data(booking, data):
            
            """Populate data dictionary for hotel property type."""
            try:
                
                room_type = Bookedrooms.objects.filter(booking=booking)
                
                # action_url = reverse('booking_detail', kwargs={'pk': booking.id}) # Site domain should be correct. Else it will show localhost
                action_url = f"/vendor/booking/{booking.id}"
                domain_name = settings.DOMAIN_NAME.rstrip('/') 
                data.update({
                    'check_in': booking.checkin_date,
                    'check_out': booking.checkout_date,
                    'customer_name': booking.get_guest_full_name(),
                    'booking_id': booking.booking_id,
                    'customer_contact': booking.booking_mobilenumber,
                    'rooms_count': booking.number_of_booking_rooms,
                    'vendor_name': booking.hotel.get_vendor_full_name(),
                    'vendor_contact': booking.hotel.office_number,
                    'vendor_email': booking.hotel.get_vendor_email(),
                    'property_name': booking.hotel.name,
                    'property_address': booking.hotel.address,
                    'rooms':[room.room.room_types.room_types for room in room_type],
                    'action_url': f"{domain_name}{action_url}",
                    'total_members': booking.number_of_guests,
                    'adults':booking.adults,
                    'children':booking.children,
                    'category':"hotel"
                })
                
            except Exception as e:
                logger.info(f"Exception occured in populate_hotel_data. Exception : {e}")
            return data
        
        def populate_chalet_data(booking, data):
            print(booking,"=============++++++++++++++++++++++",booking.checkin_date)
            print(type(data),"+++++++++++++++++",data)
            """Populate data dictionary for chalet property type."""
            try:
                # action_url = reverse('booking_detail', kwargs={'pk': booking.id}) # Site domain should be correct. Else it will show localhost
                action_url = f"/chalets/chalet/view/{booking.id}/"
                domain_name = settings.DOMAIN_NAME.rstrip('/') 
                data.update({
                    'check_in': booking.checkin_date,
                    'check_out': booking.checkout_date,
                    'customer_name': booking.get_guest_full_name(),
                    'booking_id': booking.booking_id,
                    'customer_contact': booking.booking_mobilenumber,
                    'rooms_count': booking.number_of_booking_rooms,
                    'vendor_name': booking.chalet.get_vendor_full_name(),
                    'vendor_contact': booking.chalet.office_number,
                    'vendor_email': booking.chalet.get_vendor_email(),
                    'property_name': booking.chalet.name,
                    'property_address': booking.chalet.address,
                    'action_url': f"{domain_name}{action_url}",
                    'total_members': booking.number_of_guests,
                    'category':"chalet"
                })
            except Exception as e:
                print(e,"==========================++++++++++++++++++++++")
                logger.info(f"Exception occured in populate_chalet_data. Exception : {e}")
            return data
        
        if property_type == 'hotel' and hasattr(booking, 'hotel') and booking.hotel:
            logger.info("Hotel object is present within the booking.")
            data = populate_hotel_data(booking, data)
            
        elif property_type == 'chalet':
            logger.info("Handling chalet property type (future implementation).")
            data = populate_chalet_data(booking, data)  # Implement chalet logic here
            print(data,"++++++++++++++++++++++++++++++++++++")
        else:
            logger.info(f"Unsupported property type: {property_type}. Function not executed.")
            return None

        # Attempt to render the email and send it
        try:
            vendor_email = data.get('vendor_email')
            
            if vendor_email:
                logger.info(f"Appending vendor email : {aggregator_emails}")
                aggregator_emails.append(vendor_email)
                logger.info(f'Updated recipients : {aggregator_emails}')
            data['is_admin_email'] = 'settings.ADMIN_EMAIL' in aggregator_emails 
            html = render_to_string(template, data)
            property_name = data.get('property_name', 'N/A') or 'N/A'
            booking_id = data.get('booking_id', 'N/A') or 'N/A'
            subject = f"Immediate Action Required! New Booking Received For {property_name} #{booking_id}"
            send_email(subject=subject, html=html, recipients=aggregator_emails)
            logger.info("Email successfully sent to aggregator.")
            return True
        except Exception as e:
            logger.exception("Exception occurred while sending email.", exc_info=True)

    except Exception as e:
        logger.exception("Unexpected exception occurred in notify_booking_aggregator.", exc_info=True)

    return None