from django.urls import re_path

from .consumers import SimulationProgressConsumer

websocket_urlpatterns = [
    re_path(r"ws/simulation/(?P<sim_id>\d+)/$", SimulationProgressConsumer.as_asgi()),
]
