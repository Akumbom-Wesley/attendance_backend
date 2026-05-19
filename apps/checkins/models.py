from django.db import models
from apps.common.models import BaseModel
from apps.devices.models import DeviceBinding


class CheckinRecord(BaseModel):
    LOG_TYPE_CHOICES = [
        ('IN', 'Clock In'),
        ('OUT', 'Clock Out'),
    ]

    WIFI_BAND_CHOICES = [
        ('2.4GHz', '2.4GHz'),
        ('5GHz', '5GHz'),
        ('UNAVAILABLE', 'Unavailable'),
    ]

    device_binding = models.ForeignKey(
        DeviceBinding,
        on_delete=models.PROTECT,
        related_name='checkin_records'
    )
    log_type = models.CharField(max_length=3, choices=LOG_TYPE_CHOICES)
    timestamp_gps = models.DateTimeField()
    timestamp_device = models.DateTimeField()
    sync_received_at = models.DateTimeField(null=True, blank=True)
    gps_lat_smoothed = models.DecimalField(max_digits=9, decimal_places=6)
    gps_lng_smoothed = models.DecimalField(max_digits=9, decimal_places=6)
    gps_accuracy_metres = models.IntegerField()
    rssi_avg = models.IntegerField(null=True, blank=True)
    wifi_ssid = models.CharField(max_length=255, blank=True)
    wifi_bssid = models.CharField(max_length=17, blank=True)
    wifi_band = models.CharField(
        max_length=15,
        choices=WIFI_BAND_CHOICES,
        default='UNAVAILABLE'
    )
    biometric_passed = models.BooleanField(default=False)
    is_flagged = models.BooleanField(default=False)
    is_synced = models.BooleanField(default=False)

    class Meta:
        db_table = 'checkin_records'
        constraints = [
            models.UniqueConstraint(
                fields=['device_binding', 'timestamp_gps'],
                name='unique_checkin_per_device_per_timestamp'
            )
        ]

    def __str__(self):
        return f"{self.device_binding} — {self.log_type} at {self.timestamp_gps}"

    def is_timestamp_plausible(self):
        raise NotImplementedError("Use CheckinValidationService.is_timestamp_plausible()")

    def is_duplicate(self):
        raise NotImplementedError("Use CheckinValidationService.is_duplicate()")