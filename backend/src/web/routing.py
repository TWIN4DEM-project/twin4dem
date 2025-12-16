from django.urls import re_path

from .channels import SimulationAsyncConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/simulation/(?P<simulation_id>\d+)/$", SimulationAsyncConsumer.as_asgi()
    ),
]
