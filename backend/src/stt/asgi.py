"""
ASGI config for stt project.
"""

import os
import sys

# Must be set before any Django or app imports so that settings.py
# (and its load_dotenv call) runs before any model/service code is imported.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stt.settings')

import django
django.setup()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
import app_stt.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(app_stt.routing.websocket_urlpatterns)
    ),
})
