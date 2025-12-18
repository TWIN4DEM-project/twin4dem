from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from api import views
from api.viewsets import simulation_router


urlpatterns = format_suffix_patterns(
    [
        path("settings/", views.list_settings, name="list-settings"),
        path("settings/<int:settings_id>/", views.get_settings, name="get-settings"),
        *simulation_router.urls,
    ]
)
