from django.db import models
from apps.common.models import BaseModel


class Company(BaseModel):
    erpnext_doc_name = models.CharField(max_length=140, unique=True)
    name = models.CharField(max_length=255)
    webhook_secret = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'companies'
        verbose_name_plural = 'companies'

    def __str__(self):
        return self.name

    def get_active_sites(self):
        return self.geofence_sites.filter(is_active=True)
    

class GeofenceSite(BaseModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='geofence_sites'
    )
    name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    radius_metres = models.IntegerField()
    wifi_ssid = models.CharField(max_length=255, blank=True)
    wifi_bssid = models.CharField(max_length=17, blank=True)
    rssi_threshold = models.IntegerField(default=-70)
    enforce_5ghz = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'geofence_sites'

    def __str__(self):
        return f"{self.company.name} — {self.name}"

    def is_within_fence(self, lat, lng):
        """Haversine check — full implementation goes in services.py"""
        raise NotImplementedError("Use GeofenceService.is_within_fence()")