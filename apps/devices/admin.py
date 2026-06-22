from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from .models import DeviceBinding
from .services import DeviceBindingService


@admin.register(DeviceBinding)
class DeviceBindingAdmin(admin.ModelAdmin):
    list_display = (
        'employee', 'attendance_device_id', 'device_unique_id',
        'is_active', 'bound_at', 'unbound_at'
    )
    search_fields = (
        'device_unique_id', 'attendance_device_id',
        'employee__full_name', 'employee__erpnext_employee_id'
    )
    list_filter = ('is_active',)
    readonly_fields = ('device_unique_id', 'bound_at', 'unbound_at', 'employee')
    actions = ['unbind_devices', 'rebind_to_selected_device']

    def unbind_devices(self, request, queryset):
        active = queryset.filter(is_active=True)
        count = active.count()
        if count == 0:
            self.message_user(request, "No active bindings selected.", messages.WARNING)
            return
        active.update(is_active=False, unbound_at=timezone.now())
        self.message_user(
            request, f"{count} device(s) unbound successfully.", messages.SUCCESS
        )

    unbind_devices.short_description = "Unbind selected devices"

    def rebind_to_selected_device(self, request, queryset):
        """
        Select exactly one inactive binding to reactivate for its employee.
        The employee's current active binding (if any) will be deactivated first.
        Only works when exactly one binding is selected.
        """
        if queryset.count() != 1:
            self.message_user(
                request,
                "Select exactly one binding to rebind.",
                messages.WARNING,
            )
            return

        target = queryset.first()

        if target.is_active:
            self.message_user(
                request,
                f"Device '{target.attendance_device_id}' is already active. "
                "Select an inactive binding to rebind.",
                messages.WARNING,
            )
            return

        try:
            DeviceBindingService.rebind(
                employee=target.employee,
                target_binding=target,
            )
            self.message_user(
                request,
                f"Device '{target.attendance_device_id}' rebound to "
                f"{target.employee.full_name} successfully.",
                messages.SUCCESS,
            )
        except ValueError as e:
            self.message_user(request, str(e), messages.ERROR)

    rebind_to_selected_device.short_description = "Rebind selected device to its employee"
