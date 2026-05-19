from django.contrib import admin
from .models import DeviceBinding

@admin.register(DeviceBinding)
class DeviceBindingAdmin(admin.ModelAdmin):
    list_display = ('employee', 'device_unique_id', 'is_active', 'bound_at')
    search_fields = ('device_unique_id',)
    list_filter = ('is_active',)