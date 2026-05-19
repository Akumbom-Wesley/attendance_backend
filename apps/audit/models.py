from django.db import models
from apps.common.models import BaseModel
from apps.checkins.models import CheckinRecord
from apps.employees.models import Employee


class AuditLog(BaseModel):
    ERROR_CODE_CHOICES = [
        ('SUCCESS', 'Success'),
        ('DEVICE_NOT_REGISTERED', 'Device Not Registered'),
        ('MOCK_LOCATION_DETECTED', 'Mock Location Detected'),
        ('ROOTED_DEVICE_DETECTED', 'Rooted Device Detected'),
        ('TIMESTAMP_IMPLAUSIBLE', 'Timestamp Implausible'),
        ('GEOFENCE_FAILED', 'Geofence Failed'),
        ('BIOMETRIC_FAILED', 'Biometric Failed'),
        ('WIFI_RSSI_BELOW_THRESHOLD', 'Wi-Fi RSSI Below Threshold'),
        ('ALREADY_CHECKED_IN', 'Already Checked In'),
        ('ALREADY_SYNCED', 'Already Synced'),
    ]

    FINAL_DECISION_CHOICES = [
        ('PASS', 'Pass'),
        ('FAIL', 'Fail'),
        ('TWO_FACTOR_ONLY', 'Two Factor Only'),
    ]

    checkin_record = models.ForeignKey(
        CheckinRecord,
        on_delete=models.PROTECT,
        related_name='audit_logs',
        null=True,
        blank=True
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='audit_logs'
    )
    biometric_result = models.BooleanField(default=False)
    geofence_result = models.BooleanField(default=False)
    rssi_result = models.BooleanField(default=False)
    antispoofing_result = models.BooleanField(default=False)
    wifi_available = models.BooleanField(default=True)
    two_factor_only = models.BooleanField(default=False)
    error_code = models.CharField(
        max_length=40,
        choices=ERROR_CODE_CHOICES,
        default='SUCCESS'
    )
    final_decision = models.CharField(
        max_length=16,
        choices=FINAL_DECISION_CHOICES
    )
    gps_timestamp_used = models.DateTimeField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict)

    class Meta:
        db_table = 'audit_logs'
        # Immutable — no update methods ever

    def __str__(self):
        return f"AuditLog #{self.pk} — {self.final_decision}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("AuditLog is immutable. Records cannot be updated.")
        super().save(*args, **kwargs)