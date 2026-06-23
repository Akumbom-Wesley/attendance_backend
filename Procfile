web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2
worker: celery -A config worker -l INFO -Q default,checkins,webhooks
beat: celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
