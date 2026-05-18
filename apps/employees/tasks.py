from config.celery import app as celery_app


@celery_app.task(bind=True, name='employees.schedule_auto_return')
def schedule_auto_return(self, employee_status_id: int, duration_seconds: int):
    """
    Schedule an automatic status return after break/errand/assignment.
    UC22 — implementation in Sprint 4.
    """
    raise NotImplementedError("Implement in Sprint 4")


@celery_app.task(bind=True, name='employees.cancel_auto_return')
def cancel_auto_return(self, celery_task_id: str):
    """
    Cancel a scheduled auto-return if status changes before timer fires.
    UC22 — implementation in Sprint 4.
    """
    raise NotImplementedError("Implement in Sprint 4")