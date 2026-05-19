from .base import *
from decouple import config

DEBUG = True

ALLOWED_HOSTS = str(
    config('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1')
).split(',')

# Allow Flutter dev app
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

# Emails just print to console in dev
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'