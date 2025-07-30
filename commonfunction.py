from itertools import chain
import logging

from chalets.models import ChaletBooking,Chalet
from vendor.models import Booking,Hotel
from user.models import Wallet,Userdetails
import requests
from Bookingapp_1969 import settings
from datetime import date

logger = logging.getLogger('lessons')
from django.utils.timezone import is_aware
from datetime import timezone
from django.utils.timezone import make_naive
def make_naive_date(dt):
    if not dt:
        return 'N/A'
    if is_aware(dt):
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime('%d-%m-%Y')  

def booking_filters(request,logger,bookings):
    fromDate = request.GET.get('fromDate')
    toDate = request.GET.get('toDate')
    data = request.GET.get('statusType', '')  # Get the 'data' parameter from the URL
    print(data)
    statusType = data.split(',') if data else []
    room_type = request.GET.get("room_type")
    activeButtonId = request.GET.get('activeButtonId')
    print(f"POST parameters received - From Date: {fromDate}, To Date: {toDate}, Status Type: {statusType}")
    logger.info(f"POST parameters received - From Date: {fromDate}, To Date: {toDate}, Status Type: {statusType}")
    if fromDate and toDate:
        bookings = bookings.filter(checkin_date__gte=fromDate, checkout_date__lte=toDate)
        print(bookings,"====================================+++++++++++++++++++")
        logger.info(f"Filtered bookings by date range ({fromDate} to {toDate}): {bookings.count()}")
    elif fromDate:
        bookings = bookings.filter(checkin_date__gte=fromDate)
        print(bookings,"====================================+++++++++++++++++++")
        logger.info(f"Filtered bookings by 'from_date' ({fromDate}): {bookings.count()}")
    elif toDate:
        bookings = bookings.filter(checkout_date__lte=toDate)
        print(bookings,"====================================+++++++++++++++++++")
        logger.info(f"Filtered bookings by 'to_date' ({toDate}): {bookings.count()}")

    
    if room_type and room_type != "Room Type":
        bookings = bookings.filter(
            booked_rooms__room__room_types__room_types=room_type
        )
        logger.info(f"Filtered bookings by status type ({room_type}): {bookings.count()}")
    # Filter by status type
    print(f"\n\n\n\n\n\n\n\n statusType---------------------------------{statusType}\n\n\n\n\n\n\n\n\n\n")
    if statusType and "Status Type" not in statusType:
        
        if statusType in ["expired","cancelled"]:
            print("\n\n\n\n++++++++++++++++++++++++++++\n\n\n\n")
            bookings = bookings.filter(status__in=["expired","cancelled"])
        else:
            print("\n\n\n\n=========================\n\n\n\n")
            bookings = bookings.filter(status__in=statusType)
        print(bookings,"====================================+++++++++++++++++++")
        logger.info(f"Filtered bookings by status type ({statusType}): {bookings.count()}")
    print(bookings)
    return bookings


def combine_bookings(hotel, chalet,sort):
    combined = list(chain(hotel, chalet))
    if sort:
        sorted_result = sorted(combined, key=lambda x: x.created_date, reverse=True) 
        return sorted_result
    return combined

from itertools import chain
from collections import defaultdict

def merge_and_sum_bookings(hotel, chalet, sort):
    combined_dict = defaultdict(int)
    
    for booking in chain(hotel, chalet):
        combined_dict[booking["day"]] += booking["total_bookings"]

    merged_list = [{"day": day, "total_bookings": total} for day, total in combined_dict.items()]

    if sort:
        merged_list.sort(key=lambda x: x["day"])  # Sort by date

    return merged_list

   
def transaction_list_filter(transactions = None, from_date = None,  to_date = None, payment_method = None, transaction_status = None, booking_status = None, name_search = None, transaction_id = None, user = None):
    from common.models import PaymentType
    from django.db.models import Q
    try:
        
        if user == "admin":
            print("=====================================")
            # transactions = [t for t in transactions if t.transaction is not None]
            if from_date:
                transactions = [t for t in transactions if t.transaction is not None and t.transaction.modified_date.date() >= from_date]
            if to_date:
                transactions = transactions = [t for t in transactions if t.transaction is not None and t.transaction.modified_date.date() <= from_date]
            if from_date and to_date:
                transactions = [
                                    t for t in transactions 
                                    if from_date <= t.transaction.modified_date.date() <= to_date
                                ]
            if transaction_status:
                transactions = [t for t in transactions if t.transaction is not None and t.transaction.transaction_status == transaction_status]
            if booking_status:
                transactions = [t for t in transactions if t.status == booking_status]
            if payment_method:
                payment_type = PaymentType.objects.get(name=payment_method)
                transactions = [t for t in transactions if t.transaction is not None and t.transaction.payment_type == payment_type]
            if name_search:
                transactions = [
                                t for t in transactions if (
                                    (t.booking_fname and name_search.lower() in t.booking_fname.lower()) or
                                    (hasattr(t, "hotel") and t.hotel and name_search.lower() in t.hotel.name.lower()) or
                                    (hasattr(t, "hotel") and t.hotel and t.hotel.name_arabic and name_search.lower() in t.hotel.name_arabic.lower()) or
                                    (hasattr(t, "chalet") and t.chalet and name_search.lower() in t.chalet.name.lower()) or
                                    (hasattr(t, "chalet") and t.chalet and t.chalet.name_arabic and name_search.lower() in t.chalet.name_arabic.lower())
                                )
                            ]
            if transaction_id:
                transactions = [t for t in transactions if t.transaction is not None and t.transaction.transaction_id == transaction_id]
            
        else:
            if from_date:
                transactions = transactions.filter(modified_date__date__gte = from_date)
            if to_date:
                transactions = transactions.filter(modified_date__date__lte=to_date)
            if from_date and to_date:
                transactions = transactions.filter(modified_date__date__gte = from_date, modified_date__date__lte=to_date)
            if transaction_status:
                transactions = transactions.filter(transaction__transaction_status=transaction_status)
            if booking_status:
                transactions = transactions.filter(status=booking_status)
            if payment_method:
                payment_type = PaymentType.objects.get(name=payment_method)
                transactions = transactions.filter(transaction__payment_type=payment_type)
            if name_search:
                transactions = transactions.filter(
                    Q(booking_fname__icontains=name_search) | 
                    Q(hotel__name__icontains=name_search) |
                    Q(hotel__name_arabic__icontains=name_search) |
                    Q(chalet__name__icontains=name_search) |
                    Q(chalet__name_arabic__icontains=name_search)
                    )
            if transaction_id:
                transactions = transactions.filter(transaction__transaction_id__icontains=transaction_id)
        return transactions
    except Exception as e:
        print(f"\n\n\n\n\n\n\n\n\n{e}\n\n\n\n\n\n\n")
    
    

def report_data_frame(bookings,user,lang):
    data_frame = []
    for booking in bookings:
        vendor_transaction = booking.transaction.vendor_transaction.all() if booking.transaction else None
        admin_transaction = booking.transaction.admin_transaction.all() if booking.transaction else None
        print(booking)
        if isinstance(booking, Booking) and booking.hotel:
            print(f"\n\n\n\n\n  ==========================HOTEL========================== \n\n\n\n\n\n\n")
            print(booking.created_date)
        elif isinstance(booking, ChaletBooking) and booking.chalet:
            print(f"\n\n\n\n  ==========================CHALET==========================  \n\n\n\n\n\n")
       
        if user == "admin":
            if booking.transaction:
                if vendor_transaction:
                    for vendor in vendor_transaction:
                        if admin_transaction:
                            for admin in admin_transaction:
                                try:
                                    # logger.info(f"Requested user is admin")
                                    if lang == 'en':
                                        if isinstance(booking, Booking) and booking.hotel:
                                            print("bookings-----")
                                            print(booking.created_date)
                                            data_frame.append({
                                                'Property name': booking.hotel.name,
                                                'Transaction ID': booking.transaction.transaction_id,
                                                'Booking ID': booking.booking_id,
                                                'Guest Name' : booking.booking_fname,
                                                'User Name':booking.user.user.get_full_name().strip(),
                                                'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                                'Transaction Date' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                                'Booking Time': make_naive(booking.created_date).strftime("%I:%M %p"),
                                                # 'Booking Date':htbooking.booking_date.strftime('%d/%m/%Y'),
                                                'Payment Method' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                                'Transaction Status' : booking.transaction.transaction_status,
                                                'Booking Status' : booking.status,
                                                'Transaction Amount' : f" OMR {booking.transaction.amount}",
                                                'Vendor Earnings' : f" OMR {vendor.vendor_earnings}",
                                                'Property Amount' : f" OMR {vendor.base_price}",
                                                'Discount Amount' : f"OMR{booking.discount_price}",
                                                'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                                'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                                'Tax' : f" OMR {booking.tax_and_services}",
                                                'Meal Price': f" OMR {booking.meal_price}",
                                                'Meal Tax' : f" OMR {booking.meal_tax}",
                                                'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                                                'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                                                'Total Members':booking.number_of_guests,
                                                'Booked Rooms':booking.number_of_booking_rooms,
                                                'Room Types': ', '.join(
                                                    booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                                                ) if booking.booked_rooms.exists() else 'N/A',
                                                'Payment Gateway Charges' : f" OMR {admin.actual_gateway_fee}",
                                                'Payment gateway Commission for Admin' : f" OMR {admin.admin_gateway_fee}",
                                                'Commission Amount' : f" OMR {admin.admin_commission}"
                                            })
                                        elif isinstance(booking, ChaletBooking) and booking.chalet:
                                            data_frame.append({
                                                'Property name': booking.chalet.name,
                                                'Transaction ID': booking.transaction.transaction_id,
                                                'Booking ID': booking.booking_id,
                                                'Guest Name' : booking.booking_fname,
                                                'User Name':booking.user.user.get_full_name().strip(),
                                                'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                                'Transaction Date' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                                'Booking Time': make_naive(booking.created_date).strftime("%I:%M %p"),

                                                # 'Booking Date':htbooking.booking_date.strftime('%d/%m/%Y'),
                                                'Payment Method' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                                'Transaction Status' : booking.transaction.transaction_status,
                                                'Booking Status' : booking.status,
                                                'Transaction Amount' : f" OMR {booking.transaction.amount}",
                                                'Vendor Earnings' : f" OMR {vendor.vendor_earnings}",
                                                'Property Amount' : f" OMR {vendor.base_price}",
                                                'Discount Amount' : f"OMR{booking.discount_price}",
                                                'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                                'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                                'Tax' : f" OMR {booking.tax_and_services}",
                                                'Meal Price': "N/A",
                                                'Meal Tax' : "N/A",
                                                'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                                                'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                                                'Total Members':booking.number_of_guests,
                                                'Booked Rooms':booking.number_of_booking_rooms,
                                                'Room Types': f"N/A",
                                                'Payment Gateway Charges' : f" OMR {admin.actual_gateway_fee}",
                                                'Payment gateway Commission for Admin' : f" OMR {admin.admin_gateway_fee}",
                                                'Commission Amount' : f" OMR {admin.admin_commission}"
                                            })
                                    else:
                                        if isinstance(booking, Booking) and booking.hotel:
                                            data_frame.append({
                                                'اسم العقار': booking.hotel.name_arabic,
                                                'معرف المعاملة': booking.transaction.transaction_id,
                                                'معرف الحجز': booking.booking_id,
                                                'اسم الضيف' : booking.booking_fname,
                                                'اسم المستخدم':booking.user.user.get_full_name().strip(),
                                                'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                                'تاريخ المعاملة' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                                'وقت الحجز': make_naive(booking.created_date).strftime("%I:%M %p"),

                                                # 'تاريخ الحجز':htbooking.booking_date.strftime('%d/%m/%Y'),
                                                'طريقة الدفع' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                                'حالة المعاملة' : booking.transaction.transaction_status,
                                                'حالة الحجز' : booking.status,
                                                'مبلغ المعاملة' : f" OMR {booking.transaction.amount}",
                                                'أرباح البائعين' : f" OMR {vendor.vendor_earnings}",
                                                'مبلغ العقار' : f" OMR {vendor.base_price}",
                                                'مبلغ الخصم' : f"OMR {booking.discount_price}",
                                                'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                                'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                                'ضريبة' : f" OMR {booking.tax_and_services}",
                                                'سعر الوجبة': f" OMR {booking.meal_price}",
                                                'ضريبة الوجبات' : f" OMR {booking.meal_tax}",
                                                'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                                                'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                                                'إجمالي الأعضاء':booking.number_of_guests,
                                                'الغرف المحجوزة':booking.number_of_booking_rooms,
                                                'أنواع الغرف': ', '.join(
                                                    booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                                                ) if booking.booked_rooms.exists() else 'N/A',
                                                'رسوم بوابة الدفع' : f" OMR {admin.actual_gateway_fee}",
                                                'بوابة الدفع عمولة للمسؤول' : f" OMR {admin.admin_gateway_fee}",
                                                'مبلغ العمولة' : f" OMR {admin.admin_commission}"
                                            })
                                        elif isinstance(booking, ChaletBooking) and booking.chalet:
                                            data_frame.append({
                                                'اسم العقار': booking.chalet.name_arabic,
                                                'معرف المعاملة': booking.transaction.transaction_id,
                                                'معرف الحجز': booking.booking_id,
                                                'اسم الضيف' : booking.booking_fname,
                                                'اسم المستخدم':booking.user.user.get_full_name().strip(),
                                                'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                                'تاريخ المعاملة' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                               'وقت الحجز': make_naive(booking.created_date).strftime("%I:%M %p"),

                                                # 'تاريخ الحجز':htbooking.booking_date.strftime('%d/%m/%Y'),
                                                'طريقة الدفع' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                                'حالة المعاملة' : booking.transaction.transaction_status,
                                                'حالة الحجز' : booking.status,
                                                'مبلغ المعاملة' : f" OMR {booking.transaction.amount}",
                                                'أرباح البائعين' : f" OMR {vendor.vendor_earnings}",
                                                'مبلغ العقار' : f" OMR {vendor.base_price}",
                                                'مبلغ الخصم' : f"OMR {booking.discount_price}",
                                                'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                                'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                                'ضريبة' : f" OMR {booking.tax_and_services}",
                                                'سعر الوجبة': "N/A",
                                                'ضريبة الوجبات' : "N/A",
                                                'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                                                'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                                                'إجمالي الأعضاء':booking.number_of_guests,
                                                'الغرف المحجوزة':booking.number_of_booking_rooms,
                                                'أنواع الغرف': f"N/A",
                                                'رسوم بوابة الدفع' : f" OMR {admin.actual_gateway_fee}",
                                                'بوابة الدفع عمولة للمسؤول' : f" OMR {admin.admin_gateway_fee}",
                                                'مبلغ العمولة' : f" OMR {admin.admin_commission}"
                                            })
                                    
                                except Exception as e:
                                    print(f"Exception for hotel_bookings inside report_data_frame function for admin. Exception: {e}")
                                    # logger.error(f"Exception for hotel_bookings inside report_data_frame function for admin. Exception: {e}")
                        else:
                            try:
                                if lang == 'en':
                                    if isinstance(booking, Booking) and booking.hotel:
                                        data_frame.append({
                                            'Property name': booking.hotel.name,
                                            'Transaction ID': booking.transaction.transaction_id,
                                            'Booking ID': booking.booking_id,
                                            'Guest Name' : booking.booking_fname,
                                            'User Name':booking.user.user.get_full_name().strip(),
                                            'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                            'Transaction Date' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                            'Booking Time': make_naive(booking.created_date).strftime("%I:%M %p"),

                                            # 'Booking Date':htbooking.booking_date.strftime('%d/%m/%Y'),
                                            'Payment Method' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                            'Transaction Status' : booking.transaction.transaction_status,
                                            'Booking Status' : booking.status,
                                            'Transaction Amount' : f" OMR {booking.transaction.amount}",
                                            'Vendor Earnings' : f" OMR {vendor.vendor_earnings}",
                                            'Property Amount' : f" OMR {vendor.base_price}",
                                            'Discount Amount' : f"OMR{booking.discount_price}",
                                            'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                            'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                            'Tax' : f" OMR {booking.tax_and_services}",
                                            'Meal Price': f" OMR {booking.meal_price}",
                                            'Meal Tax' : f" OMR {booking.meal_tax}",
                                            'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                                            'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                                            'Total Members':booking.number_of_guests,
                                            'Booked Rooms':booking.number_of_booking_rooms,
                                            'Room Types': ', '.join(
                                                booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                                            ) if booking.booked_rooms.exists() else 'N/A',
                                            'Payment Gateway Charges' :f"N/A",
                                            'Payment gateway Commission for Admin' : f"N/A",
                                            'Commission Amount' : f"N/A"
                                        })
                                    elif isinstance(booking, ChaletBooking) and booking.chalet:
                                        data_frame.append({
                                            'Property name': booking.chalet.name,
                                            'Transaction ID': booking.transaction.transaction_id,
                                            'Booking ID': booking.booking_id,
                                            'Guest Name' : booking.booking_fname,
                                            'User Name':booking.user.user.get_full_name().strip(),
                                            'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                            'Transaction Date' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                            'Booking Time': make_naive(booking.created_date).strftime("%I:%M %p"),

                                            # 'Booking Date':htbooking.booking_date.strftime('%d/%m/%Y'),
                                            'Payment Method' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                            'Transaction Status' : booking.transaction.transaction_status,
                                            'Booking Status' : booking.status,
                                            'Transaction Amount' : f" OMR {booking.transaction.amount}",
                                            'Vendor Earnings' : f" OMR {vendor.vendor_earnings}",
                                            'Property Amount' : f" OMR {vendor.base_price}",
                                            'Discount Amount' : f"OMR{booking.discount_price}",
                                            'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                            'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                            'Tax' : f" OMR {booking.tax_and_services}",
                                            'Meal Price': "N/A",
                                            'Meal Tax' : "N/A",
                                            'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                                            'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                                            'Total Members':booking.number_of_guests,
                                            'Booked Rooms':booking.number_of_booking_rooms,
                                            'Room Types': f"N/A",
                                            'Payment Gateway Charges' :f"N/A",
                                            'Payment gateway Commission for Admin' : f"N/A",
                                            'Commission Amount' : f"N/A"
                                        })
                                else:
                                    if isinstance(booking, Booking) and booking.hotel:
                                        data_frame.append({
                                            'اسم العقار': booking.hotel.name_arabic,
                                            'معرف المعاملة': booking.transaction.transaction_id,
                                            'معرف الحجز': booking.booking_id,
                                            'اسم الضيف' : booking.booking_fname,
                                            'اسم المستخدم':booking.user.user.get_full_name().strip(),
                                            'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",

                                            'تاريخ المعاملة' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                            'وقت الحجز': make_naive(booking.created_date).strftime("%I:%M %p"),
                                            # 'تاريخ الحجز':htbooking.booking_date.strftime('%d/%m/%Y'),
                                            'طريقة الدفع' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                            'حالة المعاملة' : booking.transaction.transaction_status,
                                            'حالة الحجز' : booking.status,
                                            'مبلغ المعاملة' : f" OMR {booking.transaction.amount}",
                                            'أرباح البائعين' : f" OMR {vendor.vendor_earnings}",
                                            'مبلغ العقار' : f" OMR {vendor.base_price}",
                                            'مبلغ الخصم' : f"OMR {booking.discount_price}",
                                            'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                            'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                            'ضريبة' : f" OMR {booking.tax_and_services}",
                                            'سعر الوجبة': f" OMR {booking.meal_price}",
                                            'ضريبة الوجبات' : f" OMR {booking.meal_tax}",
                                            'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                                            'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                                            'إجمالي الأعضاء':booking.number_of_guests,
                                            'الغرف المحجوزة':booking.number_of_booking_rooms,
                                            'أنواع الغرف': ', '.join(
                                                booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                                            ) if booking.booked_rooms.exists() else 'N/A',
                                            'رسوم بوابة الدفع' :f"N/A",
                                            'بوابة الدفع عمولة للمسؤول' : f"N/A",
                                            'مبلغ العمولة' : f"N/A"
                                        })
                                    elif isinstance(booking, ChaletBooking) and booking.chalet:
                                        data_frame.append({
                                            'اسم العقار': booking.chalet.name_arabic,
                                            'معرف المعاملة': booking.transaction.transaction_id,
                                            'معرف الحجز': booking.booking_id,
                                            'اسم الضيف' : booking.booking_fname,
                                            'اسم المستخدم':booking.user.user.get_full_name().strip(),
                                            'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                            'تاريخ المعاملة' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                           'وقت الحجز': make_naive(booking.created_date).strftime("%I:%M %p"),
                                            # 'تاريخ الحجز':htbooking.booking_date.strftime('%d/%m/%Y'),
                                            'طريقة الدفع' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                            'حالة المعاملة' : booking.transaction.transaction_status,
                                            'حالة الحجز' : booking.status,
                                            'مبلغ المعاملة' : f" OMR {booking.transaction.amount}",
                                            'أرباح البائعين' : f" OMR {vendor.vendor_earnings}",
                                            'مبلغ العقار' : f" OMR {vendor.base_price}",
                                            'مبلغ الخصم' : f"OMR {booking.discount_price}",
                                            'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                            'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                            'ضريبة' : f" OMR {booking.tax_and_services}",
                                            'سعر الوجبة': "N/A",
                                            'ضريبة الوجبات' : "N/A",
                                            'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                                            'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                                            'إجمالي الأعضاء':booking.number_of_guests,
                                            'الغرف المحجوزة':booking.number_of_booking_rooms,
                                            'أنواع الغرف': f"N/A",
                                            'رسوم بوابة الدفع' :f"N/A",
                                            'بوابة الدفع عمولة للمسؤول' : f"N/A",
                                            'مبلغ العمولة' : f"N/A"
                                        })
                            except Exception as e:
                                print(f"Exception for hotel_bookings inside vendor_transaction loop report_data_frame function for admin. Exception: {e}")
                                # logger.error(f"Exception for hotel_bookings inside vendor_transaction loop report_data_frame function for admin. Exception: {e}")
                else:
                    print(f"\n\n\n\n\n\n else vendor: {vendor} \n\n\n\n\n\n\n\n")
                    print(f"\n\n\n\n\n\n booking: {booking} \n\n\n\n\n\n\n\n")
                    try:
                        if lang == 'en':
                            if isinstance(booking, Booking) and booking.hotel:
                                data_frame.append({
                                    'Property name': booking.hotel.name,
                                    'Transaction ID': booking.transaction.transaction_id,
                                    'Booking ID': booking.booking_id,
                                    'Guest Name' : booking.booking_fname,
                                    'User Name':booking.user.user.get_full_name().strip(),
                                    'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                    'Transaction Date' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                    'Booking Time': make_naive(booking.created_date).strftime("%I:%M %p"),

                                    # 'Booking Date':booking.booking_date.strftime('%d/%m/%Y'),
                                    'Payment Method' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                    'Transaction Status' : booking.transaction.transaction_status,
                                    'Booking Status' : booking.status,
                                    'Transaction Amount' : f" OMR {booking.transaction.amount}",
                                    'Vendor Earnings' : f"N/A",
                                    'Property Amount' : f"N/A",
                                    'Discount Amount' : f"OMR{booking.discount_price}",
                                    'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                    'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                    'Tax' : f" OMR {booking.tax_and_services}",
                                    'Meal Price': f" OMR {booking.meal_price}",
                                    'Meal Tax' : f" OMR {booking.meal_tax}",
                                    'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                                    'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                                    'Total Members':booking.number_of_guests,
                                    'Booked Rooms':booking.number_of_booking_rooms,
                                    'Room Types': ', '.join(
                                        booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                                    ) if booking.booked_rooms.exists() else 'N/A',
                                    'Payment Gateway Charges' :f"N/A",
                                    'Payment gateway Commission for Admin' : f"N/A",
                                    'Commission Amount' : f"N/A"
                                })
                            elif isinstance(booking, ChaletBooking) and booking.chalet:
                                data_frame.append({
                                    'Property name': booking.chalet.name,
                                    'Transaction ID': booking.transaction.transaction_id,
                                    'Booking ID': booking.booking_id,
                                    'Guest Name' : booking.booking_fname,
                                    'User Name':booking.user.user.get_full_name().strip(),
                                    'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                    'Transaction Date' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                    'Booking Time': make_naive(booking.created_date).strftime("%I:%M %p"),

                                    # 'Booking Date':booking.booking_date.strftime('%d/%m/%Y'),
                                    'Payment Method' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                    'Transaction Status' : booking.transaction.transaction_status,
                                    'Booking Status' : booking.status,
                                    'Transaction Amount' : f" OMR {booking.transaction.amount}",
                                    'Vendor Earnings' : f"N/A",
                                    'Property Amount' : f"N/A",
                                    'Discount Amount' : f"OMR{booking.discount_price}",
                                    'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                    'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                    'Tax' : f" OMR {booking.tax_and_services}",
                                    'Meal Price': "N/A",
                                    'Meal Tax' : "N/A",
                                    'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                                    'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                                    'Total Members':booking.number_of_guests,
                                    'Booked Rooms':booking.number_of_booking_rooms,
                                    'Room Types': f"N/A",
                                    'Payment Gateway Charges' :f"N/A",
                                    'Payment gateway Commission for Admin' : f"N/A",
                                    'Commission Amount' : f"N/A"
                                })
                                
                        else:
                            if isinstance(booking, Booking) and booking.hotel:
                                data_frame.append({
                                    'اسم العقار': booking.hotel.name_arabic,
                                    'معرف المعاملة': booking.transaction.transaction_id,
                                    'معرف الحجز': booking.booking_id,
                                    'اسم الضيف' : booking.booking_fname,
                                    'اسم المستخدم':booking.user.user.get_full_name().strip(),
                                    'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                    'تاريخ المعاملة' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                  'وقت الحجز': make_naive(booking.created_date).strftime("%I:%M %p"),

                                    # 'تاريخ الحجز':htbooking.booking_date.strftime('%d/%m/%Y'),
                                    'طريقة الدفع' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                    'حالة المعاملة' : booking.transaction.transaction_status,
                                    'حالة الحجز' : booking.status,
                                    'مبلغ المعاملة' : f" OMR {booking.transaction.amount}",
                                    'أرباح البائعين' : f"N/A",
                                    'مبلغ العقار' : f"N/A",
                                    'مبلغ الخصم' : f"OMR {booking.discount_price}",
                                    'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                    'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                    'ضريبة' : f" OMR {booking.tax_and_services}",
                                    'سعر الوجبة': f" OMR {booking.meal_price}",
                                    'ضريبة الوجبات' : f" OMR {booking.meal_tax}",
                                    'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                                    'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                                    'إجمالي الأعضاء':booking.number_of_guests,
                                    'الغرف المحجوزة':booking.number_of_booking_rooms,
                                    'أنواع الغرف': ', '.join(
                                        booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                                    ) if booking.booked_rooms.exists() else 'N/A',
                                    'رسوم بوابة الدفع' :f"N/A",
                                    'بوابة الدفع عمولة للمسؤول' : f"N/A",
                                    'مبلغ العمولة' : f"N/A"
                                })
                            elif isinstance(booking, ChaletBooking) and booking.chalet:
                                data_frame.append({
                                    'اسم العقار': booking.chalet.name_arabic,
                                    'معرف المعاملة': booking.transaction.transaction_id,
                                    'معرف الحجز': booking.booking_id,
                                    'اسم الضيف' : booking.booking_fname,
                                    'اسم المستخدم':booking.user.user.get_full_name().strip(),
                                    'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                    'تاريخ المعاملة' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                   'وقت الحجز': make_naive(booking.created_date).strftime("%I:%M %p"),

                                    # 'تاريخ الحجز':htbooking.booking_date.strftime('%d/%m/%Y'),
                                    'طريقة الدفع' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                    'حالة المعاملة' : booking.transaction.transaction_status,
                                    'حالة الحجز' : booking.status,
                                    'مبلغ المعاملة' : f" OMR {booking.transaction.amount}",
                                    'أرباح البائعين' : f"N/A",
                                    'مبلغ العقار' : f"N/A",
                                    'مبلغ الخصم' : f"OMR {booking.discount_price}",
                                    'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                    'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                    'ضريبة' : f" OMR {booking.tax_and_services}",
                                    'سعر الوجبة': "N/A",
                                    'ضريبة الوجبات' : "N/A",
                                    'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                                    'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                                    'إجمالي الأعضاء':booking.number_of_guests,
                                    'الغرف المحجوزة':booking.number_of_booking_rooms,
                                    'أنواع الغرف': f"N/A",
                                    'رسوم بوابة الدفع' :f"N/A",
                                    'بوابة الدفع عمولة للمسؤول' : f"N/A",
                                    'مبلغ العمولة' : f"N/A"
                                })

                    except Exception as e:
                        print(f"Exception for hotel_bookings inside vendor_transaction else loop report_data_frame function for admin. Exception: {e}")
                        # logger.error(f"Exception for hotel_bookings inside vendor_transaction else loop report_data_frame function for admin. Exception: {e}")     
            else:  
                print(f"\n\n\n\n\n\n\n\n\n    elseeeeeeeeeeeeee   \n\n\n\n\n\n\n\n\n\n\n")       
                try:
                    if lang == 'en':
                        if isinstance(booking, Booking) and booking.hotel:
                            data_frame.append({
                                'Property name': booking.hotel.name,
                                'Transaction ID': "N/A",
                                'Booking ID': booking.booking_id,
                                'Guest Name' : booking.booking_fname,
                                'User Name':booking.user.user.get_full_name().strip(),
                                'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                'Transaction Date' : "N/A",
                                'Booking Time':  "N/A",

                                # 'Booking Date':booking.booking_date.strftime('%d/%m/%Y'),
                                'Payment Method' : "N/A",
                                'Transaction Status' : "N/A",
                                'Booking Status' : booking.status,
                                'Transaction Amount' : "N/A",
                                'Vendor Earnings' : f"N/A",
                                'Property Amount' : f"N/A",
                                'Discount Amount' : f"OMR{booking.discount_price}",
                                'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                'Tax' : f" OMR {booking.tax_and_services}",
                                'Meal Price': f" OMR {booking.meal_price}",
                                'Meal Tax' : f" OMR {booking.meal_tax}",
                                'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                                'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                                'Total Members':booking.number_of_guests,
                                'Booked Rooms':booking.number_of_booking_rooms,
                                'Room Types': ', '.join(
                                    booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                                ) if booking.booked_rooms.exists() else 'N/A',
                                'Payment Gateway Charges' :f"N/A",
                                'Payment gateway Commission for Admin' : f"N/A",
                                'Commission Amount' : f"N/A"
                            })
                        elif isinstance(booking, ChaletBooking) and booking.chalet:
                            data_frame.append({
                                'Property name': booking.chalet.name,
                                'Transaction ID': "N/A",
                                'Booking ID': booking.booking_id,
                                'Guest Name' : booking.booking_fname,
                                'User Name':booking.user.user.get_full_name().strip(),
                                'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                'Transaction Date' : "N/A",
                                'Booking Time':"N/A",

                                # 'Booking Date':booking.booking_date.strftime('%d/%m/%Y'),
                                'Payment Method' : "N/A",
                                'Transaction Status' : "N/A",
                                'Booking Status' : booking.status,
                                'Transaction Amount' : "N/A",
                                'Vendor Earnings' : f"N/A",
                                'Property Amount' : f"N/A",
                                'Discount Amount' : f"OMR{booking.discount_price}",
                                'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                'Tax' : f" OMR {booking.tax_and_services}",
                                'Meal Price': "N/A",
                                'Meal Tax' : "N/A",
                                'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                                'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                                'Total Members':booking.number_of_guests,
                                'Booked Rooms':booking.number_of_booking_rooms,
                                'Room Types': f"N/A",
                                'Payment Gateway Charges' :f"N/A",
                                'Payment gateway Commission for Admin' : f"N/A",
                                'Commission Amount' : f"N/A"
                            })
                    else:
                        if isinstance(booking, Booking) and booking.hotel:
                            data_frame.append({
                                'اسم العقار': booking.hotel.name_arabic,
                                'معرف المعاملة': "N/A",
                                'معرف الحجز': booking.booking_id,
                                'اسم الضيف' : booking.booking_fname,
                                'اسم المستخدم':booking.user.user.get_full_name().strip(),
                                'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                'تاريخ المعاملة' : "N/A",
                                'وقت الحجز':"N/A",
                                # 'تاريخ الحجز':htbooking.booking_date.strftime('%d/%m/%Y'),
                                'طريقة الدفع' : "N/A",
                                'حالة المعاملة' : "N/A",
                                'حالة الحجز' : booking.status,
                                'مبلغ المعاملة' : "N/A",
                                'أرباح البائعين' : f"N/A",
                                'مبلغ العقار' : f"N/A",
                                'مبلغ الخصم' : f"OMR {booking.discount_price}",
                                'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                'ضريبة' : f" OMR {booking.tax_and_services}",
                                'سعر الوجبة': f" OMR {booking.meal_price}",
                                'ضريبة الوجبات' : f" OMR {booking.meal_tax}",
                                'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                                'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                                'إجمالي الأعضاء':booking.number_of_guests,
                                'الغرف المحجوزة':booking.number_of_booking_rooms,
                                'أنواع الغرف': ', '.join(
                                    booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                                ) if booking.booked_rooms.exists() else 'N/A',
                                'رسوم بوابة الدفع' :f"N/A",
                                'بوابة الدفع عمولة للمسؤول' : f"N/A",
                                'مبلغ العمولة' : f"N/A"
                            })
                        elif isinstance(booking, ChaletBooking) and booking.chalet:
                            data_frame.append({
                                'اسم العقار': booking.chalet.name_arabic,
                                'معرف المعاملة': "N/A",
                                'معرف الحجز': booking.booking_id,
                                'اسم الضيف' : booking.booking_fname,
                                'اسم المستخدم':booking.user.user.get_full_name().strip(),
                                'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                'تاريخ المعاملة' : "N/A",
                                'وقت الحجز': "N/A",
                                # 'تاريخ الحجز':htbooking.booking_date.strftime('%d/%m/%Y'),
                                'طريقة الدفع' : "N/A",
                                'حالة المعاملة' : "N/A",
                                'حالة الحجز' : booking.status,
                                'مبلغ المعاملة' : "N/A",
                                'أرباح البائعين' : f"N/A",
                                'مبلغ العقار' : f"N/A",
                                'مبلغ الخصم' : f"OMR {booking.discount_price}",
                                'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                             'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                'ضريبة' : f" OMR {booking.tax_and_services}",
                                'سعر الوجبة': "N/A",
                                'ضريبة الوجبات' : "N/A",
                                'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                                'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                                'إجمالي الأعضاء':booking.number_of_guests,
                                'الغرف المحجوزة':booking.number_of_booking_rooms,
                                'أنواع الغرف': f"N/A",
                                'رسوم بوابة الدفع' :f"N/A",
                                'بوابة الدفع عمولة للمسؤول' : f"N/A",
                                'مبلغ العمولة' : f"N/A"
                            })

                except Exception as e:
                    print(f"Exception for hotel_bookings inside vendor_transaction else loop report_data_frame function for admin. Exception: {e}")
                    # logger.error(f"Exception for hotel_bookings inside vendor_transaction else loop report_data_frame function for admin. Exception: {e}")         
                # if chalet_booking:
                #     for chbooking in chalet_booking:
                #         print(chbooking,"chbooking")
                #         for vendor in vendor_transaction:
                #             if admin_transaction:
                #                 for admin in admin_transaction:
                #                     try:
                #                         if lang == 'en':
                #                             data_frame.append({
                #                                 'Property name': chbooking.chalet.name,
                #                                 'Transaction ID': trans.transaction_id,
                #                                 'Booking ID': chbooking.booking_id,
                #                                 'Guest Name' : chbooking.booking_fname,
                #                                 'Transaction Date' : trans.modified_at.strftime('%d/%m/%Y'),
                #                                 # 'Booking Date':chbooking.booking_date.strftime('%d/%m/%Y'),
                #                                 'Payment Method' : trans.payment_type.name if trans.payment_type else "N/A",
                #                                 'Transaction Status' : trans.transaction_status,
                #                                 'Booking Status' : chbooking.status,
                #                                 'Transaction Amount' : f" OMR {trans.amount}",
                #                                 'Vendor Earnings' : f" OMR {vendor.vendor_earnings}",
                #                                 'Property Amount' : f" OMR {vendor.base_price}",
                #                                 'Tax' : f" OMR {chbooking.tax_and_services}",
                #                                 'Meal Price': f"N/A",
                #                                 'Meal Tax' : f"N/A",
                #                                 'Check-In':chbooking.checkin_date.strftime('%d/%m/%Y'),
                #                                 'Check-Out':chbooking.checkout_date.strftime('%d/%m/%Y'),
                #                                 'Total Members':chbooking.number_of_guests,
                #                                 'Booked Rooms':chbooking.number_of_booking_rooms,
                #                                 'Room Types': f"N/A",
                #                                 'Payment Gateway Charges' : f" OMR {admin.actual_gateway_fee}",
                #                                 'Payment gateway Commission for Admin' : f" OMR {admin.admin_gateway_fee}",
                #                                 'Commission Amount' : f" OMR {admin.admin_commission}"
                #                             })
                #                         else:
                #                             data_frame.append({
                #                             'اسم العقار': chbooking.chalet.name,
                #                             'معرف المعاملة': trans.transaction_id,
                #                             'معرف الحجز': chbooking.booking_id,
                #                             'اسم الضيف' : chbooking.booking_fname,
                #                             'تاريخ المعاملة' : trans.modified_at.strftime('%d/%m/%Y'),
                #                             # 'تاريخ الحجز':chbooking.booking_date.strftime('%d/%m/%Y'),
                #                             'طريقة الدفع' : trans.payment_type.name if trans.payment_type else "N/A",
                #                             'حالة المعاملة' : trans.transaction_status,
                #                             'حالة الحجز' : chbooking.status,
                #                             'مبلغ المعاملة' : f" OMR {trans.amount}",
                #                             'أرباح البائعين' : f" OMR {vendor.vendor_earnings}",
                #                             'مبلغ العقار' : f" OMR {vendor.base_price}",
                #                             'ضريبة' : f" OMR {chbooking.tax_and_services}",
                #                             'سعر الوجبة': f"N/A",
                #                             'ضريبة الوجبات' :  f"N/A",
                #                             'تحقق في':chbooking.checkin_date.strftime('%d/%m/%Y'),
                #                             'الدفع':chbooking.checkout_date.strftime('%d/%m/%Y'),
                #                             'إجمالي الأعضاء':chbooking.number_of_guests,
                #                             'الغرف المحجوزة':chbooking.number_of_booking_rooms,
                #                             'أنواع الغرف': f"N/A",
                #                             'رسوم بوابة الدفع' : f" OMR {admin.actual_gateway_fee}",
                #                             'بوابة الدفع عمولة للمسؤول' : f" OMR {admin.admin_gateway_fee}",
                #                             'مبلغ العمولة' : f" OMR {admin.admin_commission}"
                #                         })

                #                     except Exception as e:
                #                         print(f"Exception for chalet_booking inside report_data_frame function. Exception: {e}")
                #                         logger.error(f"Exception for chalet_booking inside report_data_frame function. Exception: {e}")
                #             else:
                #                 try:
                #                     if lang == 'en':
                #                         data_frame.append({
                #                             'Property name': chbooking.chalet.name,
                #                             'Transaction ID': trans.transaction_id,
                #                             'Booking ID': chbooking.booking_id,
                #                             'Guest Name' : chbooking.booking_fname,
                #                             'Transaction Date' : trans.modified_at.strftime('%d/%m/%Y'),
                #                             # 'Booking Date':chbooking.booking_date.strftime('%d/%m/%Y'),
                #                             'Payment Method' : trans.payment_type.name if trans.payment_type else "N/A",
                #                             'Transaction Status' : trans.transaction_status,
                #                             'Booking Status' : chbooking.status,
                #                             'Transaction Amount' : f" OMR {trans.amount}",
                #                             'Vendor Earnings' : f" OMR {vendor.vendor_earnings}",
                #                             'Property Amount' : f" OMR {vendor.base_price}",
                #                             'Tax' : f" OMR {chbooking.tax_and_services}",
                #                             'Meal Price': f"N/A",
                #                             'Meal Tax' : f"N/A",
                #                             'Check-In':chbooking.checkin_date.strftime('%d/%m/%Y'),
                #                             'Check-Out':chbooking.checkout_date.strftime('%d/%m/%Y'),
                #                             'Total Members':chbooking.number_of_guests,
                #                             'Booked Rooms':chbooking.number_of_booking_rooms,
                #                             'Room Types': f"N/A",
                #                             'Payment gateway Commission for Admin' : f"N/A",
                #                             'Commission Amount' : f"N/A",
                #                             'Payment Gateway Charges' :f"N/A"
                #                         })
                #                     else:
                #                         data_frame.append({
                #                         'اسم العقار': chbooking.chalet.name,
                #                         'معرف المعاملة': trans.transaction_id,
                #                         'معرف الحجز': chbooking.booking_id,
                #                         'اسم الضيف' : chbooking.booking_fname,
                #                         'تاريخ المعاملة' : trans.modified_at.strftime('%d/%m/%Y'),
                #                         # 'تاريخ الحجز':chbooking.booking_date.strftime('%d/%m/%Y'),
                #                         'طريقة الدفع' : trans.payment_type.name if trans.payment_type else "N/A",
                #                         'حالة المعاملة' : trans.transaction_status,
                #                         'حالة الحجز' : chbooking.status,
                #                         'مبلغ المعاملة' : f" OMR {trans.amount}",
                #                         'أرباح البائعين' : f" OMR {vendor.vendor_earnings}",
                #                         'مبلغ العقار' : f" OMR {vendor.base_price}",
                #                         'ضريبة' : f" OMR {chbooking.tax_and_services}",
                #                         'سعر الوجبة': f"N/A",
                #                         'ضريبة الوجبات' :  f"N/A",
                #                         'تحقق في':chbooking.checkin_date.strftime('%d/%m/%Y'),
                #                         'الدفع':chbooking.checkout_date.strftime('%d/%m/%Y'),
                #                         'إجمالي الأعضاء':chbooking.number_of_guests,
                #                         'الغرف المحجوزة':chbooking.number_of_booking_rooms,
                #                         'أنواع الغرف': f"N/A",
                #                         'رسوم بوابة الدفع' : f"N/A",
                #                         'بوابة الدفع عمولة للمسؤول' :f"N/A",
                #                         'مبلغ العمولة' : f"N/A"
                #                     })
                #                 except Exception as e:
                #                     print(f"Exception for chalet_booking inside report_data_frame function. Exception: {e}")
                #                     logger.error(f"Exception for chalet_booking inside report_data_frame function. Exception: {e}")
        elif user == "hotel":
            logger.info(f"Requested user is Hotel")
            if booking.transaction:
                if vendor_transaction:
                    for vendor in vendor_transaction:
                        if admin_transaction:
                            for admin in admin_transaction:
                                try:
                                    if lang =='en':
                                        data_frame.append({
                                            'Transaction ID': booking.transaction.transaction_id,
                                            'Booking ID': booking.booking_id,
                                            'Guest Name' : booking.booking_fname,
                                            'User Name':booking.user.user.get_full_name().strip(),
                                            'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                            'Transaction Date' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                            'Booking Time': make_naive(booking.created_date).strftime("%I:%M %p"),
                                            # 'Booking Date':booking.booking_date.strftime('%d/%m/%Y'),
                                            'Payment Method' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                            'Transaction Status' : booking.transaction.transaction_status,
                                            'Booking Status' : booking.status,
                                            'Transaction Amount' : f" OMR {booking.transaction.amount}",
                                            # 'Vendor Earnings' : vendor.vendor_earnings,
                                            'Property Amount' : f" OMR {vendor.base_price}",
                                            'Discount Amount' : f" OMR {booking.discount_price}",
                                            'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                            'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                            'Tax' : f" OMR {booking.tax_and_services}",
                                            'Meal Price': f" OMR {booking.meal_price}",
                                            'Meal Tax' : f" OMR {booking.meal_tax}",
                                            'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                                            'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                                            'Total Members':booking.number_of_guests,
                                            'Booked Rooms':booking.number_of_booking_rooms,
                                            'Room Types': ', '.join(
                                                booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                                            ) if booking.booked_rooms.exists() else 'N/A',
                                            'Payment Gateway Charges' : f" OMR {admin.gateway_fee}"
                                        })
                                    else:
                                        data_frame.append({
                                        'معرف المعاملة': booking.transaction.transaction_id,
                                        'معرف الحجز': booking.booking_id,
                                        'اسم الضيف' : booking.booking_fname,
                                        'اسم المستخدم':booking.user.user.get_full_name().strip(),
                                        'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                        'تاريخ المعاملة' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                        'وقت الحجز': make_naive(booking.created_date).strftime("%I:%M %p"),
                                        # 'تاريخ الحجز':booking.booking_date.strftime('%d/%m/%Y'),
                                        'طريقة الدفع' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                        'حالة المعاملة' : booking.transaction.transaction_status,
                                        'حالة الحجز' : booking.status,
                                        'مبلغ المعاملة' : f" OMR {booking.transaction.amount}",
                                        'مبلغ العقار' : f" OMR {vendor.base_price}",
                                        'مبلغ الخصم' : f" OMR {booking.discount_price}",
                                        'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                        'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                        'ضريبة' : f" OMR {booking.tax_and_services}",
                                        'سعر الوجبة': f" OMR {booking.meal_price}",
                                        'ضريبة الوجبات' : f" OMR {booking.meal_tax}",
                                        'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                                        'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                                        'إجمالي الأعضاء':booking.number_of_guests,
                                        'الغرف المحجوزة':booking.number_of_booking_rooms,
                                        'أنواع الغرف': ', '.join(
                                            booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                                        ) if booking.booked_rooms.exists() else f"N/A",
                                        'رسوم بوابة الدفع' : f" OMR {admin.gateway_fee}"
                                    })     
                                except Exception as e:
                                    print(f"Exception for hotel_bookings inside report_data_frame function. Exception: {e}")
                                    # logger.error(f"Exception for hotel_bookings inside report_data_frame function. Exception: {e}")
                        else:
                            try:
                                if lang =='en':
                                    data_frame.append({
                                        'Transaction ID': booking.transaction.transaction_id,
                                        'Booking ID': booking.booking_id,
                                        'Guest Name' : booking.booking_fname,
                                        'User Name':booking.user.user.get_full_name().strip(),
                                        'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                        'Transaction Date' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                        'Booking Time':make_naive(booking.created_date).strftime("%I:%M %p"),
                                        # 'Booking Date':booking.booking_date.strftime('%d/%m/%Y'),
                                        'Payment Method' : booking.transaction.payment_type.name if booking.transaction.payment_type else f"N/A",
                                        'Transaction Status' : booking.transaction.transaction_status,
                                        'Booking Status' : booking.status,
                                        'Transaction Amount' : f" OMR {booking.transaction.amount}",
                                        # 'Vendor Earnings' : vendor.vendor_earnings,
                                        'Property Amount' : f" OMR {vendor.base_price}",
                                        'Discount Amount' : f" OMR {booking.discount_price}",
                                        'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                        'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                        'Tax' : f" OMR {booking.tax_and_services}",
                                        'Meal Price': f" OMR {booking.meal_price}",
                                        'Meal Tax' : f" OMR {booking.meal_tax}",
                                        'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                                        'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                                        'Total Members':booking.number_of_guests,
                                        'Booked Rooms':booking.number_of_booking_rooms,
                                        'Room Types': ', '.join(
                                            booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                                        ) if booking.booked_rooms.exists() else f"N/A",
                                        'Payment Gateway Charges' : f"N/A",
                                    })
                                else:
                                    data_frame.append({
                                        'معرف المعاملة': booking.transaction.transaction_id,
                                        'معرف الحجز': booking.booking_id,
                                        'اسم الضيف' : booking.booking_fname,
                                        'اسم المستخدم':booking.user.user.get_full_name().strip(),
                                        'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                        'تاريخ المعاملة' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                        'وقت الحجز': make_naive(booking.created_date).strftime("%I:%M %p"),
                                        # 'تاريخ الحجز':booking.booking_date.strftime('%d/%m/%Y'),
                                        'طريقة الدفع' : booking.transaction.payment_type.name if booking.transaction.payment_type else f"N/A",
                                        'حالة المعاملة' : booking.transaction.transaction_status,
                                        'حالة الحجز' : booking.status,
                                        'مبلغ المعاملة' : f" OMR {booking.transaction.amount}",
                                        'مبلغ العقار' : f" OMR {vendor.base_price}",
                                        'مبلغ الخصم' : f" OMR {booking.discount_price}",
                                        'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                        'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                        'ضريبة' : f" OMR {booking.tax_and_services}",
                                        'سعر الوجبة': f" OMR {booking.meal_price}",
                                        'ضريبة الوجبات' : f" OMR {booking.meal_tax}",
                                        'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                                        'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                                        'إجمالي الأعضاء':booking.number_of_guests,
                                        'الغرف المحجوزة':booking.number_of_booking_rooms,
                                        'أنواع الغرف': ', '.join(
                                            booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                                        ) if booking.booked_rooms.exists() else 'N/A',
                                        'رسوم بوابة الدفع' :  f"N/A"
                                    })      
                            except Exception as e:
                                print(f"Exception for hotel_bookings inside report_data_frame function. Exception: {e}")
                                # logger.error(f"Exception for hotel_bookings inside report_data_frame function. Exception: {e}")
                else:
                    try:
                        if lang =='en':
                            data_frame.append({
                                'Transaction ID': booking.transaction.transaction_id,
                                'Booking ID': booking.booking_id,
                                'Guest Name' : booking.booking_fname,
                                'User Name':booking.user.user.get_full_name().strip(),
                                'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                'Transaction Date' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                'Booking Time': make_naive(booking.created_date).strftime("%I:%M %p"),
                                # 'Booking Date':booking.booking_date.strftime('%d/%m/%Y'),
                                'Payment Method' : booking.transaction.payment_type.name if booking.transaction.payment_type else f"N/A",
                                'Transaction Status' : booking.transaction.transaction_status,
                                'Booking Status' : booking.status,
                                'Transaction Amount' : f" OMR {booking.transaction.amount}",
                                # 'Vendor Earnings' : vendor.vendor_earnings,
                                'Property Amount' : f" N/A",
                                'Discount Amount' : f" OMR {booking.discount_price}",
                                'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                'Tax' : f" OMR {booking.tax_and_services}",
                                'Meal Price': f" OMR {booking.meal_price}",
                                'Meal Tax' : f" OMR {booking.meal_tax}",
                                'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                                'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                                'Total Members':booking.number_of_guests,
                                'Booked Rooms':booking.number_of_booking_rooms,
                                'Room Types': ', '.join(
                                    booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                                ) if booking.booked_rooms.exists() else f"N/A",
                                'Payment Gateway Charges' : f"N/A",
                            })
                        else:
                            data_frame.append({
                                'معرف المعاملة': booking.transaction.transaction_id,
                                'معرف الحجز': booking.booking_id,
                                'اسم الضيف' : booking.booking_fname,
                                'اسم المستخدم':booking.user.user.get_full_name().strip(),
                                'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                'تاريخ المعاملة' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                'وقت الحجز': make_naive(booking.created_date).strftime("%I:%M %p"),
                                # 'تاريخ الحجز':booking.booking_date.strftime('%d/%m/%Y'),
                                'طريقة الدفع' : booking.transaction.payment_type.name if booking.transaction.payment_type else f"N/A",
                                'حالة المعاملة' : booking.transaction.transaction_status,
                                'حالة الحجز' : booking.status,
                                'مبلغ المعاملة' : f" OMR {booking.transaction.amount}",
                                'مبلغ العقار' : f" N/A",
                                'مبلغ الخصم' : f" OMR {booking.discount_price}",
                                'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                'ضريبة' : f" OMR {booking.tax_and_services}",
                                'سعر الوجبة': f" OMR {booking.meal_price}",
                                'ضريبة الوجبات' : f" OMR {booking.meal_tax}",
                                'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                                'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                                'إجمالي الأعضاء':booking.number_of_guests,
                                'الغرف المحجوزة':booking.number_of_booking_rooms,
                                'أنواع الغرف': ', '.join(
                                    booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                                ) if booking.booked_rooms.exists() else 'N/A',
                                'رسوم بوابة الدفع' :  f"N/A"
                            })      
                    except Exception as e:
                        print(f"Exception for hotel_bookings inside report_data_frame function. Exception: {e}")
                        # logger.error(f"Exception for hotel_bookings inside report_data_frame function. Exception: {e}")
            else:
                try:
                    if lang =='en':
                        data_frame.append({
                            'Transaction ID': "N/A",
                            'Booking ID': booking.booking_id,
                            'Guest Name' : booking.booking_fname,
                            'User Name':booking.user.user.get_full_name().strip(),
                            'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                            'Transaction Date' : "N/A",
                            'Booking Time': "N/A",
                            # 'Booking Date':booking.booking_date.strftime('%d/%m/%Y'),
                            'Payment Method' : "N/A",
                            'Transaction Status' : "N/A",
                            'Booking Status' : booking.status,
                            'Transaction Amount' : "N/A",
                            # 'Vendor Earnings' : vendor.vendor_earnings,
                            'Property Amount' : "N/A",
                            'Discount Amount' : f" OMR {booking.discount_price}",
                            'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                            'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                            'Tax' : f" OMR {booking.tax_and_services}",
                            'Meal Price': f" OMR {booking.meal_price}",
                            'Meal Tax' : f" OMR {booking.meal_tax}",
                            'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                            'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                            'Total Members':booking.number_of_guests,
                            'Booked Rooms':booking.number_of_booking_rooms,
                            'Room Types': ', '.join(
                                booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                            ) if booking.booked_rooms.exists() else f"N/A",
                            'Payment Gateway Charges' : f"N/A",
                        })
                    else:
                        data_frame.append({
                            'معرف المعاملة': "N/A",
                            'معرف الحجز': booking.booking_id,
                            'اسم الضيف' : booking.booking_fname,
                            'اسم المستخدم':booking.user.user.get_full_name().strip(),
                            'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                            'تاريخ المعاملة' : "N/A",
                             'وقت الحجز': "N/A",
                            # 'تاريخ الحجز':booking.booking_date.strftime('%d/%m/%Y'),
                            'طريقة الدفع' : "N/A",
                            'حالة المعاملة' : "N/A",
                            'حالة الحجز' : booking.status,
                            'مبلغ المعاملة' : "N/A",
                            'مبلغ العقار' : "N/A",
                            'مبلغ الخصم' : f" OMR {booking.discount_price}",
                            'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                            'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                            'ضريبة' : f" OMR {booking.tax_and_services}",
                            'سعر الوجبة': f" OMR {booking.meal_price}",
                            'ضريبة الوجبات' : f" OMR {booking.meal_tax}",
                            'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                            'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                            'إجمالي الأعضاء':booking.number_of_guests,
                            'الغرف المحجوزة':booking.number_of_booking_rooms,
                            'أنواع الغرف': ', '.join(
                                booked_room.room.room_types.room_types for booked_room in booking.booked_rooms.all()
                            ) if booking.booked_rooms.exists() else 'N/A',
                            'رسوم بوابة الدفع' :  f"N/A"
                        })      
                except Exception as e:
                    print(f"Exception for hotel_bookings inside report_data_frame function. Exception: {e}")
                    # logger.error(f"Exception for hotel_bookings inside report_data_frame function. Exception: {e}")
        else:
            # logger.info(f"requested user is chalet")
            if booking.transaction:
                if vendor_transaction:
                    for vendor in vendor_transaction:
                        if admin_transaction:
                            for admin in admin_transaction:
                                try:
                                    if lang =='en':
                                        data_frame.append({
                                            'Transaction ID': booking.transaction.transaction_id,
                                            'Booking ID': booking.booking_id,
                                            'Guest Name' : booking.booking_fname,
                                            'User Name':booking.user.user.get_full_name().strip(),
                                            'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                            'Transaction Date' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                            'Booking Time': make_naive(booking.created_date).strftime("%I:%M %p"),
                                            # 'Booking Date':chbooking.booking_date.strftime('%d/%m/%Y'),
                                            'Payment Method' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                            'Transaction Status' : booking.transaction.transaction_status,
                                            'Booking Status' : booking.status,
                                            'Transaction Amount' :f" OMR {booking.transaction.amount}",
                                            # 'Vendor Earnings' : vendor.vendor_earnings,
                                            'Property Amount' :f" OMR {vendor.base_price}",
                                            'Discount Amount' :f" OMR {booking.discount_price}",
                                            'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                            'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                            'Tax' : f" OMR {booking.tax_and_services}",
                                            'Meal Price': f"N/A",
                                            'Meal Tax' : f"N/A",
                                            'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                                            'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                                            'Total Members':booking.number_of_guests,
                                            'Booked Rooms':booking.number_of_booking_rooms,
                                            'Payment Gateway Charges' : f" OMR {admin.gateway_fee}",
                                        })
                                    else:
                                        data_frame.append({
                                            'معرف المعاملة': booking.transaction.transaction_id,
                                            'معرف الحجز': booking.booking_id,
                                            'اسم الضيف' : booking.booking_fname,
                                            'اسم المستخدم':booking.user.user.get_full_name().strip(),
                                            'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                            'تاريخ المعاملة' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                           'وقت الحجز': make_naive(booking.created_date).strftime("%I:%M %p"),
                                            # 'تاريخ الحجز':booking.booking_date.strftime('%d/%m/%Y'),
                                            'طريقة الدفع' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                            'حالة المعاملة' : booking.transaction.transaction_status,
                                            'حالة الحجز' : booking.status,
                                            'مبلغ المعاملة' : f" OMR {booking.transaction.amount}",
                                            'أرباح البائعين' : f" OMR {vendor.base_price}",
                                            'مبلغ الخصم' : f" OMR {booking.discount_price}",
                                            'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                            'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                            'ضريبة' : f" OMR {booking.tax_and_services}",
                                            'سعر الوجبة': f"N/A",
                                            'ضريبة الوجبات' :  f"N/A",
                                            'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                                            'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                                            'إجمالي الأعضاء':booking.number_of_guests,
                                            'الغرف المحجوزة':booking.number_of_booking_rooms,
                                            'رسوم بوابة الدفع' : f" OMR {admin.gateway_fee}",
                                        })


                                except Exception as e:
                                    print(f"Exception for chalet_booking inside report_data_frame function. Exception: {e}")
                                    # logger.error(f"Exception for chalet_booking inside report_data_frame function. Exception: {e}")
                        else:
                            try:
                                if lang =='en':
                                    data_frame.append({
                                        'Transaction ID': booking.transaction.transaction_id,
                                        'Booking ID': booking.booking_id,
                                        'Guest Name' : booking.booking_fname,
                                        'User Name':booking.user.user.get_full_name().strip(),
                                        'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                        'Transaction Date' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                        'Booking Time': make_naive(booking.created_date).strftime("%I:%M %p"),
                                        # 'Booking Date':booking.booking_date.strftime('%d/%m/%Y'),
                                        'Payment Method' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                        'Transaction Status' : booking.transaction.transaction_status,
                                        'Booking Status' : booking.status,
                                        'Transaction Amount' :f" OMR {booking.transaction.amount}",
                                        # 'Vendor Earnings' : vendor.vendor_earnings,
                                        'Property Amount' :f" OMR {vendor.base_price}",
                                        'Discount Amount' :f" OMR {booking.discount_price}",
                                        'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                        'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                        'Tax' : f" OMR {booking.tax_and_services}",
                                        'Meal Price': f"N/A",
                                        'Meal Tax' : f"N/A",
                                        'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                                        'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                                        'Total Members':booking.number_of_guests,
                                        'Booked Rooms':booking.number_of_booking_rooms,
                                        'Payment Gateway Charges' :f'N/A'
                                    })
                                else:
                                    data_frame.append({
                                        'معرف المعاملة': booking.transaction.transaction_id,
                                        'معرف الحجز': booking.booking_id,
                                        'اسم الضيف' : booking.booking_fname,
                                        'اسم المستخدم':booking.user.user.get_full_name().strip(),
                                        'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                        'تاريخ المعاملة' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                        'وقت الحجز': make_naive(booking.created_date).strftime("%I:%M %p"),
                                        # 'تاريخ الحجز':booking.booking_date.strftime('%d/%m/%Y'),
                                        'طريقة الدفع' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                        'حالة المعاملة' : booking.transaction.transaction_status,
                                        'حالة الحجز' : booking.status,
                                        'مبلغ المعاملة' : f" OMR {booking.transaction.amount}",
                                        'أرباح البائعين' : f" OMR {vendor.base_price}",
                                        'مبلغ الخصم' : f" OMR {booking.discount_price}",
                                        'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                        'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                        'ضريبة' : f" OMR {booking.tax_and_services}",
                                        'سعر الوجبة': f"N/A",
                                        'ضريبة الوجبات' :  f"N/A",
                                        'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                                        'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                                        'إجمالي الأعضاء':booking.number_of_guests,
                                        'الغرف المحجوزة':booking.number_of_booking_rooms,
                                        'رسوم بوابة الدفع' : f'N/A'
                                    })
                            except Exception as e:
                                    print(f"Exception for chalet_booking inside report_data_frame function. Exception: {e}")
                                    # logger.error(f"Exception for chalet_booking inside report_data_frame function. Exception: {e}")
                else:
                    try:
                        if lang =='en':
                            data_frame.append({
                                'Transaction ID': booking.transaction.transaction_id,
                                'Booking ID': booking.booking_id,
                                'Guest Name' : booking.booking_fname,
                                'User Name':booking.user.user.get_full_name().strip(),
                                'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                'Transaction Date' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                'Booking Time': make_naive(booking.created_date).strftime("%I:%M %p"),
                                # 'Booking Date':booking.booking_date.strftime('%d/%m/%Y'),
                                'Payment Method' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                'Transaction Status' : booking.transaction.transaction_status,
                                'Booking Status' : booking.status,
                                'Transaction Amount' :f" OMR {booking.transaction.amount}",
                                # 'Vendor Earnings' : vendor.vendor_earnings,
                                'Property Amount' :f"N/A",
                                'Discount Amount' :f" OMR {booking.discount_price}",
                                'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                'Tax' : f" OMR {booking.tax_and_services}",
                                'Meal Price': f"N/A",
                                'Meal Tax' : f"N/A",
                                'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                                'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                                'Total Members':booking.number_of_guests,
                                'Booked Rooms':booking.number_of_booking_rooms,
                                'Payment Gateway Charges' :f'N/A'
                            })
                        else:
                            data_frame.append({
                                'معرف المعاملة': booking.transaction.transaction_id,
                                'معرف الحجز': booking.booking_id,
                                'اسم الضيف' : booking.booking_fname,
                                'اسم المستخدم':booking.user.user.get_full_name().strip(),
                                'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                                'تاريخ المعاملة' : booking.transaction.modified_at.strftime('%d/%m/%Y'),
                                'وقت الحجز': make_naive(booking.created_date).strftime("%I:%M %p"),
                                # 'تاريخ الحجز':booking.booking_date.strftime('%d/%m/%Y'),
                                'طريقة الدفع' : booking.transaction.payment_type.name if booking.transaction.payment_type else "N/A",
                                'حالة المعاملة' : booking.transaction.transaction_status,
                                'حالة الحجز' : booking.status,
                                'مبلغ المعاملة' : f" OMR {booking.transaction.amount}",
                                'أرباح البائعين' : f"N/A",
                                'مبلغ الخصم' : f" OMR {booking.discount_price}",
                                'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                                'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                                'ضريبة' : f" OMR {booking.tax_and_services}",
                                'سعر الوجبة': f"N/A",
                                'ضريبة الوجبات' :  f"N/A",
                                'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                                'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                                'إجمالي الأعضاء':booking.number_of_guests,
                                'الغرف المحجوزة':booking.number_of_booking_rooms,
                                'رسوم بوابة الدفع' : f'N/A'
                            })
                    except Exception as e:
                            print(f"Exception for chalet_booking inside report_data_frame function. Exception: {e}")
                            # logger.error(f"Exception for chalet_booking inside report_data_frame function. Exception: {e}")
            else:
                try:
                    if lang =='en':
                        data_frame.append({
                            'Transaction ID': "N/A",
                            'Booking ID': booking.booking_id,
                            'Guest Name' : booking.booking_fname,
                            'User Name':booking.user.user.get_full_name().strip(),
                            'Booking Mobile Number':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                            'Transaction Date' : "N/A",
                            'Booking Time': "N/A",
                            # 'Booking Date':booking.booking_date.strftime('%d/%m/%Y'),
                            'Payment Method' : "N/A",
                            'Transaction Status' : "N/A",
                            'Booking Status' : booking.status,
                            'Transaction Amount' :"N/A",
                            # 'Vendor Earnings' : vendor.vendor_earnings,
                            'Property Amount' :f"N/A",
                            'Discount Amount' :f" OMR {booking.discount_price}",
                            'Promo Code Applied' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                            'Discount Percentage Applied' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                            'Tax' : f" OMR {booking.tax_and_services}",
                            'Meal Price': f"N/A",
                            'Meal Tax' : f"N/A",
                            'Check-In':booking.checkin_date.strftime('%d/%m/%Y'),
                            'Check-Out':booking.checkout_date.strftime('%d/%m/%Y'),
                            'Total Members':booking.number_of_guests,
                            'Booked Rooms':booking.number_of_booking_rooms,
                            'Payment Gateway Charges' :f'N/A'
                        })
                    else:
                        data_frame.append({
                            'معرف المعاملة': "N/A",
                            'معرف الحجز': booking.booking_id,
                            'اسم الضيف' : booking.booking_fname,
                            'اسم المستخدم':booking.user.user.get_full_name().strip(),
                            'حجز رقم الجوال':booking.booking_mobilenumber if booking.booking_mobilenumber else "N/A",
                            'تاريخ المعاملة' : "N/A",
                            'وقت الحجز': "N/A",
                            # 'تاريخ الحجز':booking.booking_date.strftime('%d/%m/%Y'),
                            'طريقة الدفع' : "N/A",
                            'حالة المعاملة' : "N/A",
                            'حالة الحجز' : booking.status,
                            'مبلغ المعاملة' : "N/A",
                            'أرباح البائعين' : f"N/A",
                            'مبلغ الخصم' : f" OMR {booking.discount_price}",
                            'تم تطبيق رمز العرض الترويجي' : booking.promocode_applied if booking.promocode_applied else "N/A", 
                            'تم تطبيق نسبة الخصم' : booking.discount_percentage_applied if booking.discount_percentage_applied else "N/A" ,
                            'ضريبة' : f" OMR {booking.tax_and_services}",
                            'سعر الوجبة': f"N/A",
                            'ضريبة الوجبات' :  f"N/A",
                            'تحقق في':booking.checkin_date.strftime('%d/%m/%Y'),
                            'الدفع':booking.checkout_date.strftime('%d/%m/%Y'),
                            'إجمالي الأعضاء':booking.number_of_guests,
                            'الغرف المحجوزة':booking.number_of_booking_rooms,
                            'رسوم بوابة الدفع' : f'N/A'
                        })
                except Exception as e:
                        print(f"Exception for chalet_booking inside report_data_frame function. Exception: {e}")
                        # logger.error(f"Exception for chalet_booking inside report_data_frame function. Exception: {e}")
    # print(data_frame)         
    return data_frame

def xlsxwriter_styles(workbook):
    toper_formate = workbook.add_format({
                        'bold': True,
                        'align': 'center',
                        'valign': 'vcenter',
                        'border': 1,
                        'font_size': 18
                    })
                
    header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'center',
            'fg_color': '#D7E4BC',
            'border': 1
        })
    cell_format = workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter'
    })
    
    return toper_formate, header_format, cell_format



def user_data_frame(users,lang):
    data_frame = []
    if users:
        try:
            if lang=='en':
                for user in users:
                    full_name = user.get_full_name().strip()
                    # Determine User Type
                    if hasattr(user, 'vendor_profile') and user.vendor_profile:
                        category = user.vendor_profile.category
                        if category == 'superadmin':
                            user_type = 'Superadmin'
                        elif category == 'admin':
                            user_type = 'Admin'
                        else:
                            user_type = 'User'
                    else:
                        user_type = 'User'  # default if vendor_profile not present
                    booking_count = 'N/A'
                    wallet_balance = 'N/A'

                    userdetails = getattr(user, 'user_details', None)
                    if userdetails:
                        hotel_booking_count = Booking.objects.filter(user=userdetails).count()
                        chalet_booking_count = ChaletBooking.objects.filter(user=userdetails).count()
                        total_booking_count = hotel_booking_count + chalet_booking_count
                        booking_count = total_booking_count if total_booking_count > 0 else 'N/A'
                    # Wallet Balance
                    try:
                        wallet = Wallet.objects.get(user=userdetails)
                        wallet_balance = wallet.balance
                    except Wallet.DoesNotExist:
                        wallet_balance = 'N/A'
                    try:
                        user_detail = Userdetails.objects.get(user=user)
                        phone_number = user_detail.contact_number
                        dial_code=user_detail.dial_code
                        registration_date=make_naive_date(user_detail.created_date) 
                        if not phone_number:
                            phone_number = 'N/A'
                        elif phone_number.startswith('+'):
                            phone_number =  phone_number
                        else:
                            if phone_number and dial_code:
                                phone_number = f"{dial_code}{ phone_number}"
                    except Userdetails.DoesNotExist:
                        phone_number = 'N/A'
                        registration_date='N/A'


                    data_frame.append({
                        'Name': full_name if full_name else "N/A",
                        'Email': user.email if user.email else "N/A",
                        'Status': "Active" if user.is_active else "Inactive",
                        'Mobile Number': phone_number,
                        'Registration Date': registration_date if registration_date else 'N/A',
                        'Total Bookings': booking_count if booking_count != 'N/A' else 'N/A',
                        'Wallet Balance': f"OMR {wallet_balance}" if wallet_balance != 'N/A' and wallet_balance > 0 else wallet_balance,
                        'Operating System': user.user_details.operating_system if hasattr(user, 'user_details') and user.user_details.operating_system else "Unknown",
                        'User Type': user_type  
                    })
            else:
                for user in users:
                    full_name = user.get_full_name().strip()
                    # Determine User Type
                    if hasattr(user, 'vendor_profile') and user.vendor_profile:
                        category = user.vendor_profile.category
                        if category == 'superadmin':
                            user_type = 'المشرف الفائق'
                        elif category == 'admin':
                            user_type = 'مسؤل'
                        else:
                            user_type = 'مستخدم'
                    else:
                        user_type = 'مستخدم'  # default if vendor_profile not present
                    booking_count = 'N/A'
                    wallet_balance = 'N/A'

                    userdetails = getattr(user, 'user_details', None)
                    if userdetails:
                        hotel_booking_count = Booking.objects.filter(user=userdetails).count()
                        chalet_booking_count = ChaletBooking.objects.filter(user=userdetails).count()
                        total_booking_count = hotel_booking_count + chalet_booking_count
                        booking_count = total_booking_count if total_booking_count > 0 else 'N/A'
                    # Wallet Balance
                    try:
                        wallet = Wallet.objects.get(user=userdetails)
                        wallet_balance = wallet.balance
                    except Wallet.DoesNotExist:
                        wallet_balance = 'N/A'

                    try:
                        user_detail = Userdetails.objects.get(user=user)
                        phone_number = user_detail.contact_number
                        dial_code=user_detail.dial_code
                        registration_date=make_naive_date(user_detail.created_date)
                        if not phone_number:
                            phone_number = 'N/A'
                        elif phone_number.startswith('+'):
                            phone_number =  phone_number
                        else:
                            if phone_number and dial_code:
                                phone_number = f"{dial_code}{ phone_number}"
                       
                    except Userdetails.DoesNotExist:
                        phone_number = 'N/A'
                        registration_date='N/A'

                    data_frame.append({
                        'اسم': full_name if full_name else "N/A",
                        'بريد إلكتروني': user.email if user.email else "N/A",
                        'الحالةة': "نشيط" if user.is_active else "غير نشط",
                         'رقم الهاتف المحمول':phone_number if phone_number else 'N/A',
                         'تاريخ التسجيل': registration_date if registration_date else 'N/A',
                        'إجمالي الحجوزات': booking_count if booking_count != 'N/A' else 'N/A',
                        'رصيد المحفظة': f"OMR {wallet_balance}" if wallet_balance != 'N/A' and wallet_balance > 0 else wallet_balance,
                        'نظام التشغيل': user.user_details.operating_system if hasattr(user, 'user_details') and user.user_details.operating_system else "Unknown",
                        'نوع المستخدم': user_type  
                    })

                
            return data_frame
        except Exception as e:
            logger.info(f"An exception Occured at the report creation of user management: {e}")


def get_lat_long(address, city, state, country):
    if not all([address, city, state, country]):
        # Any of the required address components are missing
        return None, None

    full_address = f"{address}, {city}, {state}, {country}"
    api_key = settings.GOOGLE_MAPS_API_KEY

    if not api_key:
        # API key is missing in settings
        return None, None

    endpoint = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": full_address,
        "key": api_key
    }

    try:
        response = requests.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get('status') == 'OK' and data.get('results'):
            location = data['results'][0]['geometry']['location']
            return location.get('lat'), location.get('lng')
    except Exception as e:
        # Optional: log the error using logging module
        pass  # Or: logging.warning(f"Geocoding failed: {e}")

    return None, None


from math import radians, sin, cos, sqrt, asin

def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a))

    return 6371 * c  # Radius of Earth in km

def get_nearby_hotels(user_lat, user_lon, radius_km=50):
    lat_range = radius_km / 111
    lon_range = radius_km / 111

    lat_min = user_lat - lat_range
    lat_max = user_lat + lat_range
    lon_min = user_lon - lon_range
    lon_max = user_lon + lon_range

    hotels = Hotel.objects.filter(
        latitude__gte=lat_min,
        latitude__lte=lat_max,
        longitude__gte=lon_min,
        longitude__lte=lon_max,
        approval_status__iexact="approved",
        post_approval=True,
        date_of_expiry__gt=date.today()
    )

    nearby = []
    for hotel in hotels:
        distance = haversine(user_lat, user_lon, hotel.latitude, hotel.longitude)
        logger.info(f"Hotel: {hotel.name}, {hotel.id} Distance: {distance:.2f} km")  # <-- Log hotel name & distance

        if distance <= radius_km:
            nearby.append((hotel, distance))

    nearby.sort(key=lambda x: x[1])
    logger.info(f"Available hotel after decreasing according to the distance are ,{nearby}")
    return nearby

def get_nearby_chalets(user_lat, user_lon, members, radius_km=50):
    lat_range = radius_km / 111
    lon_range = radius_km / 111

    lat_min = user_lat - lat_range
    lat_max = user_lat + lat_range
    lon_min = user_lon - lon_range
    lon_max = user_lon + lon_range

    chalets = Chalet.objects.filter(
        latitude__gte=lat_min,
        latitude__lte=lat_max,
        longitude__gte=lon_min,
        longitude__lte=lon_max,
        approval_status__iexact="approved",
        post_approval=True,
        number_of_guests__gte=members
    )
    logger.info(f"Chalet founded --- {chalets}")


    nearby = []
    for chalet in chalets:
        distance = haversine(user_lat, user_lon, chalet.latitude, chalet.longitude)
        logger.info(f"Chalet: {chalet.name}, {chalet.id} Distance: {distance:.2f} km")  # <-- Log hotel name & distance
        if distance <= radius_km:
            nearby.append((chalet, distance))

    nearby.sort(key=lambda x: x[1])
    logger.info(f"Available chalets after decreasing according to the distance are ,{nearby}")
    return nearby



