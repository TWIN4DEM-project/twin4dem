from django.urls import re_path

from .consumers import SimulationProgressConsumer, ExecutiveModelConsumer

websocket_urlpatterns = [
    re_path(r"ws/simulation/(?P<sim_id>\d+)/$", SimulationProgressConsumer.as_asgi()),
    re_path(r"ws/executive/(?P<sim_id>\d+)/$", ExecutiveModelConsumer.as_asgi()),
]
