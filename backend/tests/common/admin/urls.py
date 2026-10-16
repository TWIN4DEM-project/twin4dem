from django.contrib import admin
from django.urls import path

# only the admin, so that the admin tests do not depend on the rest of the site
urlpatterns = [path("admin/", admin.site.urls)]
