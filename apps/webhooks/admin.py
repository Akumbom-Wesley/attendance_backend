from django.contrib import admin
from .models import WebhookEvent

@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'erpnext_doc_name', 'processed', 'processed_at')
    list_filter = ('event_type', 'processed')
    search_fields = ('erpnext_doc_name',)