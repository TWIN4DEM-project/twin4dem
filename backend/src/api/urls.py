from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from api import views


urlpatterns = format_suffix_patterns(
    [
        path("settings/", views.list_settings, name="list-settings"),
        path("settings/<int:settings_id>/", views.get_settings, name="get-settings"),
        path(
            "simulation/",
            views.create_or_list_simulations,
            name="create-or-list-simulations",
        ),
        path(
            "simulation/<int:simulation_id>/",
            views.patch_simulation,
            name="patch-simulation",
        ),
    ]
)
