from config.celery import app as celery_app


@celery_app.task(bind=True, name='checkins.push_checkin_to_erpnext')
def push_checkin_to_erpnext(self, checkin_record_id: int):
    """
    Push a confirmed CheckinRecord to ERPNext HRMS.
    Triggered after CheckinRecord is created successfully.
    Retry policy: 3 retries, 60s backoff.
    UC20 — implementation in Sprint 3.
    """
    raise NotImplementedError("Implement in Sprint 3")

@celery_app.task(bind=True, name='checkins.sync_offline_batch')
def sync_offline_batch(self, records: list):
    """
    Process a batch of offline checkin records through the validation pipeline.
    Retry policy: 3 retries, 30s backoff.
    UC21 — implementation in Sprint 3.
    """
    raise NotImplementedError("Implement in Sprint 3")