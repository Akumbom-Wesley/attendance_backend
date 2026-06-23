from django.contrib import admin
from django.contrib import messages
from django.urls import path
from django.shortcuts import redirect
from .models import Employee, EmployeeStatus


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'erpnext_employee_id', 'company', 'is_active')
    search_fields = ('full_name', 'email', 'erpnext_employee_id')
    list_filter = ('is_active', 'company')
    change_list_template = 'admin/employees/employee/change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'sync-erpnext/',
                self.admin_site.admin_view(self.sync_erpnext_view),
                name='employees_employee_sync_erpnext',
            ),
        ]
        return custom_urls + urls

    def sync_erpnext_view(self, request):
        from apps.sync.services import ERPNextSyncService
        from apps.sync.erpnext_client import ERPNextAPIError
        from apps.companies.models import Company

        service = ERPNextSyncService()
        total_synced = 0
        total_skipped = 0
        errors = []

        for company in Company.objects.filter(is_active=True):
            try:
                result = service.sync_employees_for_company(company.erpnext_doc_name)
                total_synced += result["employees_synced"]
                total_skipped += result["employees_skipped"]
            except ERPNextAPIError as e:
                errors.append(f"{company.name}: {e}")

        if errors:
            for error in errors:
                self.message_user(request, f"ERPNext API error — {error}", messages.ERROR)

        self.message_user(
            request,
            f"Sync complete. Employees synced: {total_synced}, skipped: {total_skipped}.",
            messages.SUCCESS,
        )
        return redirect('admin:employees_employee_changelist')


@admin.register(EmployeeStatus)
class EmployeeStatusAdmin(admin.ModelAdmin):
    list_display = ('employee', 'status', 'changed_at', 'auto_return_at')
    list_filter = ('status',)
