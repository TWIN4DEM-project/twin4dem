from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from api import views
from api.viewsets import (
    country_router,
    institution_kind_router,
    party_position_router,
    simulation_router,
)


urlpatterns = format_suffix_patterns(
    [
        path("settings/", views.list_settings, name="list-settings"),
        path("settings/<int:settings_id>/", views.get_settings, name="get-settings"),
        path(
            "simulation/<int:simulation_id>/log/",
            views.get_simulation_log,
            name="get-simulation-log",
        ),
        *country_router.urls,
        *institution_kind_router.urls,
        *party_position_router.urls,
        *simulation_router.urls,
    ]
)
