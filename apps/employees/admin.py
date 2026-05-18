from django.contrib import admin
from .models import Employee, EmployeeStatus

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'erpnext_employee_id', 'company', 'is_active')
    search_fields = ('full_name', 'email', 'erpnext_employee_id')
    list_filter = ('is_active', 'company')

@admin.register(EmployeeStatus)
class EmployeeStatusAdmin(admin.ModelAdmin):
    list_display = ('employee', 'status', 'changed_at', 'auto_return_at')
    list_filter = ('status',)