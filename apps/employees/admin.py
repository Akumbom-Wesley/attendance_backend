from django.contrib import admin
from django.contrib import messages
from django.urls import path
from django.shortcuts import redirect
from django.utils import timezone
from .models import Employee, EmployeeStatus


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'erpnext_employee_id', 'company', 'is_active', 'is_onboarded_display')
    search_fields = ('full_name', 'email', 'erpnext_employee_id')
    list_filter = ('is_active', 'company')
    change_list_template = 'admin/employees/employee/change_list.html'
    actions = ['send_onboarding_email']

    def is_onboarded_display(self, obj):
        return obj.user.is_onboarded if hasattr(obj, 'user') else False
    is_onboarded_display.boolean = True
    is_onboarded_display.short_description = 'Onboarded'

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

        # Auto-trigger onboarding emails for newly synced employees
        try:
            from apps.accounts.services import OnboardingService
            from apps.accounts.models import User
            onboarding = OnboardingService()
            super_admin = User.objects.filter(role=User.Role.SUPER_ADMIN).first()
            if super_admin:
                onboarding_result = onboarding.trigger_bulk(super_admin)
                self.message_user(
                    request,
                    f"Onboarding emails sent: {onboarding_result['triggered']}, "
                    f"skipped (already onboarded): {onboarding_result['skipped']}, "
                    f"skipped (no email): {onboarding_result['skipped_no_email']}.",
                    messages.SUCCESS,
                )
        except Exception as e:
            self.message_user(request, f"Onboarding email error: {e}", messages.WARNING)

        return redirect('admin:employees_employee_changelist')

    @admin.action(description='Send onboarding email to selected employees')
    def send_onboarding_email(self, request, queryset):
        from apps.accounts.services import OnboardingService

        service = OnboardingService()
        sent = 0
        skipped_onboarded = 0
        skipped_no_email = 0
        errors = []

        for employee in queryset.select_related('user'):
            try:
                if employee.user.is_onboarded:
                    skipped_onboarded += 1
                    continue
                if not employee.user.email:
                    skipped_no_email += 1
                    continue
                token = service._generate_and_save_token(employee.user)
                from apps.accounts.tasks import send_onboarding_email_task
                send_onboarding_email_task.delay(employee.user.pk, token)
                sent += 1
            except Exception as e:
                errors.append(f"{employee.full_name}: {e}")

        if sent:
            self.message_user(
                request,
                f"Onboarding email sent to {sent} employee(s).",
                messages.SUCCESS,
            )
        if skipped_onboarded:
            self.message_user(
                request,
                f"{skipped_onboarded} employee(s) skipped — already onboarded.",
                messages.WARNING,
            )
        if skipped_no_email:
            self.message_user(
                request,
                f"{skipped_no_email} employee(s) skipped — no email address.",
                messages.WARNING,
            )
        for error in errors:
            self.message_user(request, f"Error: {error}", messages.ERROR)


@admin.register(EmployeeStatus)
class EmployeeStatusAdmin(admin.ModelAdmin):
    list_display = ('employee', 'status', 'changed_at', 'auto_return_at')
    list_filter = ('status',)
