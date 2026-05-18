from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('employee', 'final_decision', 'error_code', 'created_at')
    list_filter = ('final_decision', 'error_code')
    search_fields = ('employee__full_name',)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False