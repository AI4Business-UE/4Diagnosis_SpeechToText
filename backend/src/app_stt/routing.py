from django.urls import re_path
from .services.audio_consumers import AudioConsumer

websocket_urlpatterns = [
    re_path(r'^ws/audio/?$', AudioConsumer.as_asgi()),
]