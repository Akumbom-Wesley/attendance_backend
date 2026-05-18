from django.contrib import admin
from .models import CheckinRecord

@admin.register(CheckinRecord)
class CheckinRecordAdmin(admin.ModelAdmin):
    list_display = ('device_binding', 'log_type', 'timestamp_gps', 'is_flagged', 'is_synced')
    list_filter = ('log_type', 'is_flagged', 'is_synced', 'wifi_band')
    search_fields = ('device_binding__device_unique_id',)