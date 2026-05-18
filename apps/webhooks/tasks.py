from config.celery import app as celery_app


@celery_app.task(bind=True, name='webhooks.process_webhook_event')
def process_webhook_event(self, webhook_event_id: int):
    """
    Retry processing a failed WebhookEvent.
    Retry policy: 5 retries, 300s backoff.
    UC28 — implementation in Sprint 5.
    """
    raise NotImplementedError("Implement in Sprint 5")