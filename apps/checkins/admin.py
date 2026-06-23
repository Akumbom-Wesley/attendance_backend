from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import CheckinRecord
from .tasks import push_checkin_to_erpnext



@admin.register(CheckinRecord)
class CheckinRecordAdmin(admin.ModelAdmin):
    list_display = (
        'device_binding', 'log_type', 'timestamp_gps',
        'is_flagged', 'is_synced', 'sync_button'
    )
    list_filter = ('log_type', 'is_flagged', 'is_synced', 'wifi_band')
    search_fields = ('device_binding__device_unique_id',)
    actions = ['bulk_sync_to_erpnext']

    # --- Bulk action ---
    @admin.action(description='Sync selected records to ERPNext')
    def bulk_sync_to_erpnext(self, request, queryset):
        unsynced = queryset.filter(is_synced=False)
        count = unsynced.count()
        if count == 0:
            self.message_user(request, "All selected records are already synced.", messages.WARNING)
            return
        for record in unsynced:
            push_checkin_to_erpnext.delay(record.id)
        self.message_user(
            request,
            f"{count} record(s) queued for sync to ERPNext.",
            messages.SUCCESS
        )

    # --- Per-row sync button in list view ---
    @admin.display(description='Sync')
    def sync_button(self, obj):
        if obj.is_synced:
            return mark_safe('<span style="color:green;">✓ Synced</span>')
        return mark_safe(f'<a class="button" href="sync/{obj.pk}/">Sync</a>')

    # --- Handle the per-row sync URL ---
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path(
                'sync/<int:record_id>/',
                self.admin_site.admin_view(self.sync_single_view),
                name='checkins_checkinrecord_sync',
            ),
        ]
        return custom + urls

    def sync_single_view(self, request, record_id):
        from django.shortcuts import redirect
        try:
            record = CheckinRecord.objects.get(pk=record_id)
            if record.is_synced:
                self.message_user(request, f"Record {record_id} is already synced.", messages.WARNING)
            else:
                push_checkin_to_erpnext.delay(record.id)
                self.message_user(request, f"Record {record_id} queued for sync to ERPNext.", messages.SUCCESS)
        except CheckinRecord.DoesNotExist:
            self.message_user(request, f"Record {record_id} not found.", messages.ERROR)
        return redirect('../../')