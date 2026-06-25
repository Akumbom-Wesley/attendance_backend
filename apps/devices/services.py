from django.utils import timezone
from apps.devices.models import DeviceBinding


class DeviceBindingService:

    @staticmethod
    def register(employee, device_unique_id, attendance_device_id):
        # Employee already has an active binding
        if DeviceBinding.objects.filter(employee=employee, is_active=True).exists():
            raise ValueError("ALREADY_BOUND")

        # This device is already actively bound to another employee
        if DeviceBinding.objects.filter(
            device_unique_id=device_unique_id, is_active=True
        ).exists():
            raise ValueError("DEVICE_ALREADY_BOUND_TO_OTHER")

        # Device was previously bound to this same employee and then unbound
        # — reactivate the existing record instead of creating a duplicate
        existing = DeviceBinding.objects.filter(
            employee=employee,
            device_unique_id=device_unique_id,
            is_active=False,
        ).order_by('-unbound_at').first()

        if existing:
            existing.is_active = True
            existing.unbound_at = None
            existing.attendance_device_id = attendance_device_id
            existing.save(update_fields=['is_active', 'unbound_at', 'attendance_device_id'])
            return existing

        # Fresh registration
        return DeviceBinding.objects.create(
            employee=employee,
            device_unique_id=device_unique_id,
            attendance_device_id=attendance_device_id,
            is_active=True,
        )

    @staticmethod
    def unbind(binding):
        # Soft-delete device_unique_id so the physical device can be
        # rebound to another employee without hitting the unique constraint.
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        binding.device_unique_id = f"{binding.device_unique_id}_unbound_{timestamp}"
        binding.is_active = False
        binding.unbound_at = timezone.now()
        binding.save(update_fields=['device_unique_id', 'is_active', 'unbound_at'])
        return binding

    @staticmethod
    def rebind(employee, target_binding):
        """
        Admin rebind: deactivate employee's current active binding (if any)
        and activate the target binding. Target must belong to the same employee.
        """
        if target_binding.employee != employee:
            raise ValueError("BINDING_BELONGS_TO_DIFFERENT_EMPLOYEE")

        # Deactivate current active binding if different from target
        DeviceBinding.objects.filter(
            employee=employee,
            is_active=True,
        ).exclude(pk=target_binding.pk).update(
            is_active=False,
            unbound_at=timezone.now(),
        )

        # Activate target
        target_binding.is_active = True
        target_binding.unbound_at = None
        target_binding.save(update_fields=['is_active', 'unbound_at'])
        return target_binding
