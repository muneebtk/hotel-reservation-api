import json
import logging
from datetime import datetime

import jwt
from Bookingapp_1969 import settings
from django.contrib.auth import get_user_model
from channels.generic.websocket import AsyncWebsocketConsumer

# Create a logger instance
logger = logging.getLogger(__name__)

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_authenticated:
            self.group_name = f"notifications_{self.user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            print(f"WebSocket connection accepted for user {self.user.id}")  # Print connection acceptance
            logger.info(f"WebSocket connection accepted for user {self.user.id}")  # Log connection acceptance
        else:
            await self.close()
            print("WebSocket connection rejected for unauthenticated user")  # Print rejection
            logger.warning("WebSocket connection rejected for unauthenticated user")  # Log rejection

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            print(f"WebSocket connection closed for user {self.user.id}")  # Print disconnect
            logger.info(f"WebSocket connection closed for user {self.user.id}")  # Log disconnect

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message')
        notification_id = data.get('id', "no_id_provided")  # Default to "no_id_provided" if not present

        print(f"Received message: {message} with ID: {notification_id}")
        logger.info(f"Received message: {message} with ID: {notification_id}")

        # Ensure notification ID is included when sending to the group
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'send_notification',
                'message': message,
                'id': notification_id,  # Use provided ID or "no_id_provided" if None
                'timestamp': datetime.now().isoformat(),
                'notification_type': 'general'  # Example type
            }
        )

    async def send_notification(self, event):
        notification_data = {
            'notification': {
                'id': event.get('id', "no_id_provided"),  # Default to "no_id_provided" if not present
                'message': event.get('message', 'No notification data available'),
                'timestamp': event.get('timestamp', datetime.now().isoformat()),
                'notification_type': event.get('notification_type', 'general'),
            }
        }

        print(f"Sending notification: {notification_data}")
        logger.info(f"Sending notification: {notification_data}")

        await self.send(text_data=json.dumps(notification_data))

from urllib.parse import parse_qs



import json
import logging
from datetime import datetime
from urllib.parse import parse_qs


class BookingUpdateConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.info("WebSocket connection attempt started")

        query_string = parse_qs(self.scope["query_string"].decode())
        token_key = query_string.get("token", [None])[0]
        
        logger.debug(f"Received token: {token_key}")

        self.user = None
        if token_key:
            try:
                payload = jwt.decode(token_key, settings.SECRET_KEY, algorithms=["HS256"])
                self.user = await self.get_user(payload["user_id"])
                logger.info(f"Token decoded successfully, User ID: {payload['user_id']}")
            except jwt.ExpiredSignatureError:
                logger.warning("JWT token has expired")
            except jwt.DecodeError:
                logger.warning("Invalid JWT token")
            except get_user_model().DoesNotExist:
                logger.warning("User does not exist")

        if self.user and self.user.is_authenticated:
            self.scope["user"] = self.user
            self.group_name = f"booking_updates_{self.user.id}"

            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

            logger.info(f"WebSocket connected for user {self.user.id} (Group: {self.group_name})")

            # Send authentication success message
            message = {
                "message": "Authenticated user connected",
                "user_id": self.user.id,
                "timestamp": datetime.now().isoformat()
            }
            await self.send(text_data=json.dumps(message))

            logger.debug(f"Sent message: {json.dumps(message)}")
        else:
            logger.warning("WebSocket rejected: Unauthenticated user")
            await self.close()

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnecting (User: {self.user.id if self.user else 'Unknown'}, Close Code: {close_code})")
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info("WebSocket closed")

    async def send_booking_update(self, event):
        """Handles sending booking updates via WebSocket"""
        try:
            booking_data = {
                'update': {
                    'booking_id': event.get('booking_id', "unknown"),
                    'status': event.get('status', 'unknown'),
                    'timestamp': event.get('timestamp', datetime.now().isoformat()),
                }
            }
            logger.info(f"Sending booking update: {json.dumps(booking_data)}")
            await self.send(text_data=json.dumps(booking_data))
        except Exception as e:
            logger.error(f"Error sending booking update: {e}", exc_info=True)

    @staticmethod
    async def get_user(user_id):
        User = get_user_model()
        try:
            user = await User.objects.aget(id=user_id)
            logger.debug(f"User found: {user.id}")
            return user
        except User.DoesNotExist:
            logger.warning(f"User with ID {user_id} not found")
            return None
