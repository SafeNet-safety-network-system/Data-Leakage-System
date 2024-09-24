import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from taskflow import routing  # Import your routing file

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SafeNet.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            routing.websocket_urlpatterns  # Include your WebSocket URL patterns
        )
    ),
})
