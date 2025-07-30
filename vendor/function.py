from django.template.defaultfilters import slugify
from django.db.models import Sum
from Bookingapp_1969 import settings
import logging
import requests
from datetime import date
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


def format_validity(validity):
    """Convert the validity duration into total hours."""
    if validity:
        total_seconds = validity.total_seconds()
        total_hours = total_seconds // 3600  # Divide by 3600 seconds (1 hour)
        return f"{int(total_hours)}"
    return "Not provided"  # If validity is None
def get_roomtype_availability(hotel_id,selected_date):
    from vendor.models import Bookedrooms,Booking
    logger.info("entered the get_roomtype_availability function")
    logger.info(selected_date)
    active_bookings = Booking.objects.filter(
        hotel_id=hotel_id,
        checkin_date__lte=selected_date,
        checkout_date__gt=selected_date,
        status__in=["booked", "confirmed", "check-in","pending"]
    )
    booked_rooms = Bookedrooms.objects.filter(
        booking__in=active_bookings,
        status='confirmed'
    ).values('room').annotate(total_booked=Sum('no_of_rooms_booked'))
    return  booked_rooms
def detect_lang(city_name):
    if not city_name:
        return 'unknown'  # or return None

    if any('\u0600' <= c <= '\u06FF' for c in city_name):
        return 'ar'
    elif any('a' <= c.lower() <= 'z' for c in city_name):
        return 'en'
    else:
        return 'unknown'



def get_city_name(name, state_name, country_name, language):
    from common.utils import fetch_coordinates_from_api
    from deep_translator import GoogleTranslator
    from langdetect import detect as detect_lang
    from django.conf import settings
    import requests
    import logging

    logger = logging.getLogger(__name__)
    api_key = settings.GOOGLE_MAPS_API_KEY

    logger.info(f"Requested language: {language}")
    
    lat, lng = fetch_coordinates_from_api(name, state_name, country_name, api_key)
    logger.info("Latitude and Longitude found: %s, %s", lat, lng)

    # Fallback: No coordinates found, try translation
    if lat is None or lng is None:
        logger.warning("No coordinates found. Falling back to translation.")
        lang_detect = detect_lang(name)
        return GoogleTranslator(source=lang_detect, target=language).translate(name)

    # Build URL for Google Maps reverse geocoding
    url = (
        f"https://maps.googleapis.com/maps/api/geocode/json"
        f"?latlng={lat},{lng}&language={language}&key={api_key}"
    )

    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        print("Google Maps response received successfully.")
    except requests.RequestException as e:
        print("Request to Google Maps API failed: %s", str(e))
        return None
    except ValueError:
        logger.error("Failed to parse JSON from Google Maps API.")
        return None

    # Handle API errors
    if data.get("status") != "OK":
        logger.warning("Google Maps API returned a non-OK status: %s", data.get("status"))
        return None

    def ensure_correct_language(text):
        detected_lang = detect_lang(text)
        if detected_lang == language:
            return text
        logger.info("Translating city name from %s to %s", detected_lang, language)
        return GoogleTranslator(source=detected_lang, target=language).translate(text)

    # Try to extract the city name
    for result in data.get("results", []):
        for component in result.get("address_components", []):
            types = component.get("types", [])
            if "locality" in types or "administrative_area_level_2" in types:
                city_name = component.get("long_name")
                return ensure_correct_language(city_name)

    # If no suitable match, fallback translation
    logger.warning("No matching locality or admin area found. Translating input name.")
    return GoogleTranslator(source=detect_lang(name), target=language).translate(name)


# def set_city():
#     from vendor.models import City
#     city_all=City.objects.all()
#     for i in city_all:
#         if not i.name and not i.arabic_name:
#             continue
#         eng_name=detect_lang(i.name)
#         arabic_name=detect_lang(i.arabic_name)
#         if eng_name == 'en' and arabic_name == 'ar':
#             continue
#         elif eng_name == 'en' and arabic_name !='ar':
#             arab_name=get_city_name(i.name,i.state.name,i.state.country.name,'ar')
#             i.arabic_name=arab_name
#             i.save()
#         elif eng_name != 'en' and arabic_name =='ar':
#             engl_name=get_city_name(i.arabic_name,i.state.name,i.state.country.name,'en')
#             i.name=engl_name
#             i.save()
#         elif eng_name != 'en' and arabic_name != 'ar':
#             arab_name=get_city_name(i.name,i.state.name,i.state.country.name,'ar')
#             engl_name=get_city_name(i.name,i.state.name,i.state.country.name,'en')
#             i.arabic_name=arab_name
#             i.name=engl_name
#             i.save()
#     return True
def save_image(image_file, room_manage_obj):
    from vendor.models import RoomImage
    new_image = RoomImage.objects.create(image=image_file)
    room_manage_obj.image.add(new_image)

def populate_missing_coordinates():
    from commonfunction import get_lat_long
    from vendor.models import Hotel
    from chalets.models import Chalet
    # === Update Hotels ===
    hotels = Hotel.objects.filter(latitude__isnull=True, longitude__isnull=True)
    logger.info(f"[Hotels] Found {hotels.count()} entries with missing coordinates.")

    for hotel in hotels:
        lat, lng = get_lat_long(
            hotel.address or '',
            hotel.city.name if hotel.city else '',
            hotel.state.name if hotel.state else '',
            hotel.country.name if hotel.country else ''
        )
        if lat and lng:
            hotel.latitude = lat
            hotel.longitude = lng
            hotel.save(update_fields=['latitude', 'longitude'])
            logger.info(f"[Hotel] Updated ID {hotel.id} → lat: {lat}, lng: {lng}")
        else:
            logger.warning(f"[Hotel] Failed to fetch coordinates for ID {hotel.id}")

    # === Update Chalets ===
    chalets = Chalet.objects.filter(latitude__isnull=True, longitude__isnull=True)
    logger.info(f"[Chalets] Found {chalets.count()} entries with missing coordinates.")

    for chalet in chalets:
        lat, lng = get_lat_long(
            chalet.address or '',
            chalet.city.name if chalet.city else '',
            chalet.state.name if chalet.state else '',
            chalet.country.name if chalet.country else ''
        )
        if lat and lng:
            chalet.latitude = lat
            chalet.longitude = lng
            chalet.save(update_fields=['latitude', 'longitude'])
            logger.info(f"[Chalet] Updated ID {chalet.id} → lat: {lat}, lng: {lng}")
        else:
            logger.warning(f"[Chalet] Failed to fetch coordinates for ID {chalet.id}")
    return True

        





