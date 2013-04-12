"""Base settings shared by all environments"""
# Import global settings to make it easier to extend settings.
from django.conf.global_settings import *   # pylint: disable=W0614,W0401

# Common settings
import os

gettext = lambda s: s

PROJECT_DIR = os.path.dirname(__file__)

#==============================================================================
# Generic Django project settings
#==============================================================================

SITE_ID = 1

INSTALLED_APPS = (
    "compressor",
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.admindocs',
)

#==============================================================================
# Project URLS and media and compressor settings
#==============================================================================

ROOT_URLCONF = 'urls'

LOGIN_URL = '/login/'
LOGOUT_URL = '/logout/'
LOGIN_REDIRECT_URL = '/'

STATIC_URL = '/static/'
MEDIA_URL = '/uploads/'
ADMIN_MEDIA_PREFIX = STATIC_URL + 'admin/'

STATIC_ROOT = os.path.join(PROJECT_DIR, 'static')
MEDIA_ROOT = os.path.join(PROJECT_DIR, 'uploads')

STATICFILES_FINDERS += (
    'compressor.finders.CompressorFinder',
)

COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True

COMPRESS_PRECOMPILERS = (
    ('text/less', 'lesscpy {infile}'),
)

#==============================================================================
# Templates
#==============================================================================


TEMPLATE_DIRS = (
    os.path.join(PROJECT_DIR, 'templates')
)

TEMPLATE_CONTEXT_PROCESSORS += (
    "django.core.context_processors.request",
)
