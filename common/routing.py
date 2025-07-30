from django.urls import path
from .consumers import NotificationConsumer, BookingUpdateConsumer
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from Bookingapp_1969.middleware import WebSocketAuthMiddleware

websocket_urlpatterns = [
    path("ws/notifications/", NotificationConsumer.as_asgi()),  
    path("ws/booking_updates/", BookingUpdateConsumer.as_asgi()),
]

print(f"WebSocket URL Patterns: {websocket_urlpatterns}")

application = ProtocolTypeRouter({
    "websocket": WebSocketAuthMiddleware(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})