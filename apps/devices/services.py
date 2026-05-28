# apps/devices/services.py
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from apps.devices.models import DeviceBinding


class DeviceBindingService:

    @staticmethod
    def register(employee, device_unique_id, attendance_device_id):
        """
        Bind a device to an employee.
        Raises ValueError if an active binding already exists.
        """
        if DeviceBinding.objects.filter(employee=employee, is_active=True).exists():
            raise ValueError("ALREADY_BOUND")

        binding = DeviceBinding.objects.create(
            employee=employee,
            device_unique_id=device_unique_id,
            attendance_device_id=attendance_device_id,
            is_active=True,
        )
        return binding

    @staticmethod
    def unbind(binding):
        """
        Deactivate a binding. Sets is_active=False and unbound_at timestamp.
        """
        binding.is_active = False
        binding.unbound_at = timezone.now()
        binding.save()
        return binding