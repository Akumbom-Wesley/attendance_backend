#!/usr/bin/env bash
set -e

python manage.py migrate --no-input
python manage.py collectstatic --no-input
python manage.py create_superuser_from_env

celery -A config worker -l INFO -Q default,checkins,webhooks &
celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler &

gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2
