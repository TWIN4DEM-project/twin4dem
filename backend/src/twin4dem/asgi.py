"""
ASGI config for twin4dem project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application
from web.routing import websocket_urlpatterns


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twin4dem.settings")

application = get_asgi_application()
application = ProtocolTypeRouter(
    {
        "http": application,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
        # Just HTTP for now. (We can add other protocols later.)
    }
)
