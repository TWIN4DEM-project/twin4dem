from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path
import web.views
from . import settings

urlpatterns = [
    path("", web.views.index),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/v1/", include("api.urls")),
    # catch-all route for the routes defined using react-router
    re_path(r"^(?!api/|admin/|static/|media/).*$", web.views.index),
]

if not settings.VITE_DEV_MODE:
    urlpatterns.extend(static(settings.STATIC_URL, document_root=settings.STATIC_ROOT))
