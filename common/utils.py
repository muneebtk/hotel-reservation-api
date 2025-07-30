from decimal import Decimal
from django.conf import settings
from django.shortcuts import redirect
import requests
from asgiref.sync import async_to_sync
# from channels.layers import get_channel_layer
from Crypto.Cipher import AES

from channels.layers import get_channel_layer
from firebase_admin import messaging
from api.function import create_wallet_transaction
from chalets.models import Notification
from Crypto.Util.Padding import pad, unpad
import logging
import base64
import json


# from .models import Notification


logger = logging.getLogger('lessons')

def create_notification(user, notification_type, message, message_arabic, **kwargs):
    logger.info(f"\n\n\n\n USER: {user}, NOTIFICATION: {notification_type}, MESSAGE: {message}, **KWARGS: {kwargs}\n\n\n\n")
    notification = Notification.objects.create(
        recipient=user,
        notification_type=notification_type,
        message=message,
        message_arabic=message_arabic,
        **kwargs
    )

    # Trigger real-time notification
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"notifications_{user.id}",
        {
            "type": "send_notification",
            "message": message,
        }
    )



def send_firebase_notification(device_token, title, body, data=None):
    """
    Sends a push notification using Firebase Cloud Messaging (FCM) via Firebase Admin SDK.
    """
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        token=device_token,
        data=data or {}  # 
    )

    try:
        # Send the message and get the response
        response = messaging.send(message)
        return {"success": True, "response": response}
    except Exception as e:
        return {"success": False, "error": str(e)}

def fetch_coordinates_from_api(city_name,state_name,country_name,api_key):
    """
    Fetch latitude and longitude for a city using Google Maps Geocoding API.
    """
    try:
        if city_name is None:
            return None, None

        # Build the address by joining non-None parts
        address_parts = [city_name, state_name, country_name]
        address = ", ".join([part for part in address_parts if part])

        # If address is empty (unlikely here, but safe), return None
        if not address:
            return None, None
        
        geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
        response = requests.get(geocode_url)
        response_data = response.json()

        if response.status_code == 200 and response_data['results']:
            location = response_data['results'][0]['geometry']['location']
            return location['lat'], location['lng']
        else:
            logger.warning(f"Could not fetch coordinates for city '{city_name}'. Response: {response_data}")
            return None, None
    except Exception as e:
        logger.error(f"Error fetching coordinates for city '{city_name}': {e}")
        return None, None

def hex2ByteArray(hex_string):
    """
    Converts a hex string into a byte array.
    Args:
        hex_string (str): The hex string to be converted.
    Returns:
        bytes: The corresponding byte array.
    """
    # Convert hex string to bytes
    return bytearray.fromhex(hex_string)

def byteArray2String(byte_array):
    """
    Converts a byte array into a string.
    Args:
        byte_array (bytes): The byte array to be converted.
    Returns:
        str: The corresponding string.
    """
    return bytes(byte_array).decode('utf-8')  # Convert bytes to string assuming UTF-8 encoding



def hex_to_byte_array(hex_string):
    """
    Converts a hex string to a byte array.
    """
    return bytes.fromhex(hex_string)


def byte_array_to_hex(byte_array):
    """
    Converts a byte array to a hex string.
    Args:
        byte_array (bytes): Byte array to convert.
    Returns:
        str: Hex string representation of the byte array.
    """
    return ''.join(format(byte, '02x') for byte in byte_array)



def encrypt_aes(to_encrypt, key, iv):
    """
    Encrypts the given string using AES-256-CBC.
    Args:
        to_encrypt (str or bytes): Data to be encrypted (string or already byte-encoded).
        key (str): The encryption key (must be 32 bytes for AES-256).
        iv (str): The initialization vector (must be 16 bytes).
    Returns:
        str: Encrypted data as a hex string.
    """
    # Ensure the key length is 32 bytes (AES-256)
    if len(key) != 32:
        raise ValueError("Key must be exactly 32 bytes for AES-256 encryption.")
    
    # Ensure the IV length is 16 bytes
    if len(iv) != 16:
        raise ValueError("IV must be exactly 16 bytes for AES encryption.")

    # If to_encrypt is a string, encode it to bytes
    if isinstance(to_encrypt, str):
        to_encrypt = to_encrypt.encode('utf-8')  # Convert string to bytes

    # Encrypt using AES in CBC mode
    cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))

    # Pad the data and encrypt
    encrypted = cipher.encrypt(pad(to_encrypt, AES.block_size))

    # Convert encrypted data to hex
    encrypted_hex = encrypted.hex()
    return encrypted_hex.upper() 


# def decrypt_aes(to_decrypt, key, iv):
#     """
#     Decrypts the given hex-encoded AES-256-CBC encrypted data.
#     Args:
#         to_decrypt (str): The encrypted hex string to decrypt.
#         key (str): The decryption key (must be 32 bytes).
#         iv (str): The initialization vector (must be 16 bytes).
#     Returns:
#         str: Decrypted data as a string.
#     """
#     # Convert the hex string to bytes
#     to_decrypt = hex2ByteArray(to_decrypt)  # Convert from hex to byte array
#     to_decrypt = byteArray2String(to_decrypt)  # Convert byte array to string
    
#     cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
#     decrypted = cipher.decrypt(to_decrypt)
#     decrypted = unpad(decrypted, AES.block_size)
#     return decrypted.decode('utf-8')  # Assuming decrypted data is UTF-8 encoded

# def decrypt_aes(to_decrypt, key, iv):
#     """
#     Decrypts AES-256-CBC encrypted hex data.
#     """
#     try:
#         import binascii
#         # Convert hex string to bytes
#         to_decrypt = binascii.unhexlify(to_decrypt)

#         # Create AES cipher
#         cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))

#         # Decrypt the data
#         decrypted = cipher.decrypt(to_decrypt)

#         # Remove padding
#         decrypted = unpad(decrypted, AES.block_size)

#         # Decode to string
#         decrypted = decrypted.decode('utf-8')

#         # Debug: Inspect decrypted output
#         print(f"Decrypted raw content: {repr(decrypted)}")

#         # Parse JSON (if applicable)
#         return json.loads(decrypted)  # Only if you expect JSON output

#     except json.JSONDecodeError as json_err:
#         print(f"JSON Parsing Error: {json_err}")
#         return f"Decryption succeeded but data is not valid JSON: {repr(decrypted)}"

#     except Exception as e:
#         print(f"Decryption failed. Error: {e}")
#         return None
import binascii
from urllib.parse import unquote

def decrypt_aes(to_decrypt, key, iv):
    """
    Decrypts AES-256-CBC encrypted hex data and ensures the output is properly parsed.
    """
    try:
        # Convert hex string to bytes
        to_decrypt = binascii.unhexlify(to_decrypt)

        # Create AES cipher
        cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))

        # Decrypt the data
        decrypted = cipher.decrypt(to_decrypt)

        # Remove padding
        decrypted = unpad(decrypted, AES.block_size)

        # Decode to string
        decrypted = decrypted.decode('utf-8')

        # Debug: Log raw decrypted content
        print(f"Decrypted raw content: {repr(decrypted)}")

        # URL decode the decrypted content
        url_decoded = unquote(decrypted)

        # Check if already a list or dict
        if isinstance(url_decoded, (list, dict)):
            return url_decoded

        # Parse JSON if it's a string
        parsed_json = json.loads(url_decoded)
        return parsed_json

    except json.JSONDecodeError as json_err:
        print(f"JSON Parsing Error: {json_err}")
        return f"Decryption succeeded but data is not valid JSON: {repr(decrypted)}"

    except Exception as e:
        print(f"Decryption failed. Error: {e}")
        return None


def encrypt_trandata(trandata, resource_key, iv):
    """
    Encrypts the given `trandata` dictionary using AES encryption with CBC mode and PKCS5Padding.

    :param trandata: Dictionary containing the transaction data to be encrypted
    :param resource_key: The Resource Key for encryption (must be 16, 24, or 32 bytes long)
    :param iv: Initialization Vector (16 bytes long)
    :return: Encrypted Base64 string of the trandata
    """

    if len(resource_key) not in [16, 24, 32]:
        raise ValueError(f"Invalid AES key length ({len(resource_key)} bytes). Must be 16, 24, or 32 bytes.")
    
    # Convert the trandata dictionary to a JSON string
    trandata_str = json.dumps(trandata)
    
    # Initialize the AES cipher
    cipher = AES.new(resource_key.encode('utf-8'), AES.MODE_CBC, iv)
    
    # Encrypt the data with padding
    ciphertext = cipher.encrypt(pad(trandata_str.encode('utf-8'), AES.block_size))
    
    # Encode the encrypted data in Base64
    return base64.b64encode(ciphertext).decode('utf-8')



def payment_gateway(request,trandata_to_encrypt,wallet=None):
    language = request.GET.get('lang', 'en')
    encrypted_trandata=None
    decrypted_trandata=None
    endpoint_url=settings.NBO_ENDPOINT
    print("Testing payment gateway connection ...")
    # trandata = [{"id": "ipay434316883980","trandata": [{"amt": "10000","action": "1","password": "TEST123456@","id": "ipay434316883980","currencycode": "512","trackId": "882366456567890","expYear": "2027","expMonth": "08","member": "cardholdername","cvv2": "512","cardNo": "4393570006084551","cardType": "D","responseURL": "https://merchantpage/PaymentResult.jsp","errorURL": "https://merchantpage/PaymentResult.jsp"}],"responseURL": "https://merchantpage/PaymentResult.jsp","errorURL": "https://merchantpage/PaymentResult.jsp"}]

    print(f"Collected trandata to be encrypted. Trandata: {trandata_to_encrypt}")
    logger.info(f"Collected trandata to be encrypted. Trandata: {trandata_to_encrypt}")
    # Encrypt the transaction data
    try:
        encrypted_trandata = encrypt_aes(json.dumps(trandata_to_encrypt), settings.NBO_ENCRYPTION_KEY, settings.NBO_IV)

        # encrypted_trandata = encrypt_aes(plain_trandata, resource_key, iv)
        # encrypted_trandata=trandata_to_encrypt 
        print(f"Encrypted trandata. Encrypted Data : {encrypted_trandata}")
        logger.info(f"Encrypted trandata. Encrypted Data : {encrypted_trandata}")
        domain = request.build_absolute_uri("/")
        print(f"\n\n\n\n{domain}\n\n\n\n")
        logger.info(f"\n\n\n\n{domain}\n\n\n\n")
        user_id=request.user.id
        if wallet:
            request_payload = [
            { 
                "id": settings.NBO_TRANSPORTAL_ID,
                "trandata": encrypted_trandata,
                "responseURL": f"{domain}common/wallet-payment-status?status=&user_id={user_id}&lang={language}",
                "errorURL": settings.NBO_ERROR_URL
            }
        ]
        else:
            request_payload = [
                {
                    "id": settings.NBO_TRANSPORTAL_ID,
                    "trandata": encrypted_trandata,
                    "responseURL": f"{domain}common/payment-status?status=&lang={language}",
                    "errorURL": settings.NBO_ERROR_URL
                }
            ]

        # Frame the request payload
        print(f"Payload about to send. Payload : {request_payload}")
        logger.info(f"Payload about to send. Payload : {request_payload}")
        headers = {
            'Content-Type': 'application/json',
            # 'User-Agent': 'Thunder Client (https://www.thunderclient.com)'  # Replace with your actual User-Agent
            'User-Agent': '1929HotelsApp/1.0 (https://hotels.1929way.app)'
        }

        try:
            # Send the request to the endpoint
            response_data=None
            response = requests.post(endpoint_url, json=request_payload, headers=headers)
            print(f"Response Status Code: {response.status_code}")
            print(f"Response Content: {response.text}")
            print(f"Response Content-Type: {response.headers.get('Content-Type')}")
            logger.info(f"Response Status Code: {response.status_code}")
            logger.info(f"Response Content: {response.text}")
            logger.info(f"Response Content-Type: {response.headers.get('Content-Type')}")

            if response.status_code != 200:
                raise Exception(f"Request failed with status code {response.status_code}: {response.text}")
            if 'application/json' in response.headers.get('Content-Type', ''):
                response_data = response.json()
                # Process the JSON data
            else:
                print(f"Non-JSON response received: {response.text}")
                logger.info(f"Non-JSON response received: {response.text}")
                response_data = json.loads(response.text)
            print(f"Response received from NBO. Response : {response_data}")
            logger.info(f"Response received from NBO. Response : {response_data}")
            if response_data and "trandata" not in response_data:
                raise Exception("Response does not contain 'trandata'")
        except Exception as e:
            print(f"Exception occured in NBO request. Exception : {e}")
    except Exception as e:
        print(f"Exception occured in encrypt_trandata. Exception {e}")
    
    return response_data



def payment_status(request, wallet=None):
    payment_id = request.POST.get('paymentId')
    trandata = request.POST.get('trandata')
    error = request.POST.get('error')
    error_text = request.POST.get('errorText')
    print("====================POST REQUEST======================")
    print(payment_id)
    print(trandata)
    print(error)
    print(error_text)
    print("====================POST REQUEST======================")
    if not payment_id:
        if request.body:
            try:
                data = request.POST  # Automatically parses URL-encoded data into a QueryDict
                logger.info(f"Parsed POST data: {data}")
                print(data)
            
                # Extract values from the data
                payment_id = data.get('paymentid')
                trackid = data.get('trackid')
                error = data.get('Error')
                error_text = data.get('ErrorText')

                logger.info(f"Payment ID: {payment_id}, Track ID: {trackid}, Error: {error}, Error Text: {error_text}")
                print(f"\n\n\n\n\n\n\n\n\n\n{data.get('trandata')}\n\n\n\n\n\n\n\n\n\n\n")
                if data.get("trandata"):
                    print(f"Trandata found. Trandata : {data.get('trandata')}")
                    try:
                        from common.utils import decrypt_aes
                        from urllib.parse import unquote

                        print("Started decrypting")
                        decrypted_trandata = decrypt_aes(data.get("trandata"), settings.NBO_ENCRYPTION_KEY, settings.NBO_IV)
                        print(f"TYPE: ------> {type(decrypted_trandata)}")
                        parsed_data=None
                        url_decoded_data=None
                        if decrypted_trandata:
                            if isinstance(decrypted_trandata, list):
                                parsed_data=decrypted_trandata
                            elif isinstance(decrypted_trandata, str):
                                url_decoded_data = unquote(decrypted_trandata)
                            else:
                                raise ValueError(f"Unexpected type after decryption: {type(decrypted_trandata)}")

                        

                            # If it’s still a JSON string, parse it into a Python object
                            if parsed_data and url_decoded_data:
                                try:
                                    parsed_data = json.loads(url_decoded_data)
                                    print(f"Parsed data. Data : {parsed_data}")
                                except json.JSONDecodeError as e:
                                    print(f"JSON Parsing Error: {e}")
                            else:
                                print(f"Parsed data. Data : {parsed_data} ------ Type : {type(parsed_data)}")
                        print(f"Decrypted data. Data : {decrypted_trandata} ------ Type : {type(decrypted_trandata)}")
                        logger.info(f"Decrypted data. Data : {decrypted_trandata} ------ Type : {type(decrypted_trandata)}")
                            # Check the payment result
                        return decrypted_trandata
                    except Exception as e:
                        print(f"Exception occured in decrypting payload. Exception : {e}")
                else:
                    decrypted_trandata = "Expired"
                    print("\n\n\n\n\n\n\n\n\n\n\n\n\n")
                    print(decrypted_trandata,"=========decrypted_trandatadecrypted_trandata")
                    print("\n\n\n\n\n\n\n\n\n\n\n\n\n")
                    return decrypted_trandata
                    # return redirect(f'/common/payment-status?status=expired')
            except Exception as e:
                logger.info(f"Exception occured in test_template post method while loading json. Exception : {e}")
        else:
            print(f"Request body is empty. Body: {request.body}, request.POST : {request.POST}")