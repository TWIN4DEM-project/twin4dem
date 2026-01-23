from django.urls import path, include

from twin4dem.urls import urlpatterns


urlpatterns.insert(0, path("__reload__/", include("django_browser_reload.urls")))
