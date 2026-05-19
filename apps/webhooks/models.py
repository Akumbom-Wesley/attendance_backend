from django.db import models
from apps.common.models import BaseModel
from apps.companies.models import Company


class WebhookEvent(BaseModel):
    EVENT_TYPE_CHOICES = [
        ('employee_created', 'Employee Created'),
        ('employee_updated', 'Employee Updated'),
        ('company_created', 'Company Created'),
        ('company_updated', 'Company Updated'),
        ('checkin_received', 'Checkin Received'),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='webhook_events',
        null=True,
        blank=True
    )
    event_type = models.CharField(max_length=32, choices=EVENT_TYPE_CHOICES)
    erpnext_doctype = models.CharField(max_length=64)
    erpnext_doc_name = models.CharField(max_length=140)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = 'webhook_events'

    def __str__(self):
        return f"{self.event_type} — {self.erpnext_doc_name}"

    def process(self):
        raise NotImplementedError("Use WebhookService.process()")