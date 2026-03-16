from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from api import views
from api.viewsets import simulation_router


urlpatterns = format_suffix_patterns(
    [
        path("settings/", views.list_settings, name="list-settings"),
        path("settings/<int:settings_id>/", views.get_settings, name="get-settings"),
        path(
            "simulation/<int:simulation_id>/log/",
            views.get_simulation_log,
            name="get-simulation-log",
        ),
        *simulation_router.urls,
    ]
)
