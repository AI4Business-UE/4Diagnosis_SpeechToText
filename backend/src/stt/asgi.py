"""
ASGI config for stt project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
import sys
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app_stt.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stt.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(app_stt.routing.websocket_urlpatterns)
    ),
})