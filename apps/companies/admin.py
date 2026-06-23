from django.contrib import admin
from django.contrib import messages
from django.urls import path
from django.shortcuts import redirect
from .models import Company, GeofenceSite


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'erpnext_doc_name', 'is_active', 'created_at')
    search_fields = ('name', 'erpnext_doc_name')
    list_filter = ('is_active',)
    actions = ['import_from_erpnext']
    change_list_template = 'admin/companies/company/change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'import-erpnext/',
                self.admin_site.admin_view(self.import_erpnext_view),
                name='companies_company_import_erpnext',
            ),
        ]
        return custom_urls + urls

    def import_erpnext_view(self, request):
        from apps.sync.services import ERPNextSyncService
        from apps.sync.erpnext_client import ERPNextAPIError
        try:
            service = ERPNextSyncService()
            result = service.bulk_import()
            self.message_user(
                request,
                f"Import complete. Companies synced: {result['companies_synced']}, "
                f"Employees synced: {result['employees_synced']}.",
                messages.SUCCESS,
            )
        except ERPNextAPIError as e:
            self.message_user(request, f"ERPNext API error: {e}", messages.ERROR)
        return redirect('admin:companies_company_changelist')

    @admin.action(description='Import all Companies and Employees from ERPNext')
    def import_from_erpnext(self, request, queryset):
        from apps.sync.services import ERPNextSyncService
        from apps.sync.erpnext_client import ERPNextAPIError
        try:
            service = ERPNextSyncService()
            result = service.bulk_import()
            self.message_user(
                request,
                f"Import complete. Companies synced: {result['companies_synced']}, "
                f"Employees synced: {result['employees_synced']}.",
                messages.SUCCESS,
            )
        except ERPNextAPIError as e:
            self.message_user(request, f"ERPNext API error: {e}", messages.ERROR)


@admin.register(GeofenceSite)
class GeofenceSiteAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'radius_metres', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active', 'company')