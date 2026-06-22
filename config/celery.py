import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('attendance_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.task_routes = {
    "checkins.push_checkin_to_erpnext": {"queue": "checkins"},
    "checkins.sync_offline_batch": {"queue": "checkins"},
    "webhooks.process_webhook_event": {"queue": "webhooks"},
    "employees.schedule_auto_return": {"queue": "default"},
    "employees.cancel_auto_return": {"queue": "default"},
}
app.conf.task_default_queue = "default"