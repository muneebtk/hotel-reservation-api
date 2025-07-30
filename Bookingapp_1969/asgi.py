import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from common import routing  

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Bookingapp_1969.settings')
django.setup()
print("Setting up ASGI application...")  

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            routing.websocket_urlpatterns  
        )
    ),
})

print("ASGI application setup complete.")  
print(f"WebSocket URL Patterns Loaded: {routing.websocket_urlpatterns}")

