import pytz
from config.celery import app as celery_app
from apps.sync.erpnext_client import ERPNextClient, ERPNextAPIError


@celery_app.task(
    bind=True,
    name="checkins.push_checkin_to_erpnext",
    max_retries=3,
    default_retry_delay=60,
)
def push_checkin_to_erpnext(self, checkin_record_id: int):
    """
    Push a confirmed CheckinRecord to ERPNext as an Employee Checkin doc.
    - Skips if already synced (is_synced=True)
    - Converts timestamp_gps to Africa/Douala before sending
    - Sets is_synced=True on success
    - Retries 3x with 60s backoff on ERPNext failure
    """
    from apps.checkins.models import CheckinRecord

    record = CheckinRecord.objects.select_related(
        "device_binding__employee"
    ).get(id=checkin_record_id)

    if record.is_synced:
        return

    douala_tz = pytz.timezone("Africa/Douala")
    time_str = record.timestamp_gps.astimezone(douala_tz).strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "employee": record.device_binding.employee.erpnext_employee_id,
        "time": time_str,
        "log_type": record.log_type,
        "device_id": record.device_binding.device_unique_id,
        "skip_auto_attendance": 0,
    }

    try:
        client = ERPNextClient()
        client.create_employee_checkin(payload)
        record.is_synced = True
        record.save()
    except ERPNextAPIError as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="checkins.sync_offline_batch")
def sync_offline_batch(self, records: list):
    """
    Process a batch of offline checkin records through the validation pipeline.
    Retry policy: 3 retries, 30s backoff.
    UC21 — implementation in Sprint 5.
    """
    raise NotImplementedError("Implement in Sprint 5")