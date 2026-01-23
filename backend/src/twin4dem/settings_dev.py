"""
Django settings for twin4dem project.
"""

# ruff ignore F403,F405
from twin4dem.settings import *


DEBUG = True
INSTALLED_APPS += ["django_browser_reload"]
MIDDLEWARE += ["django_browser_reload.middleware.BrowserReloadMiddleware"]
ROOT_URLCONF = "twin4dem.urls_dev"
del STATICFILES_DIRS[0]  # remove FRONTEND_ROOT
