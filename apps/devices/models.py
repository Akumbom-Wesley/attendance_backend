from django.db import models
from apps.common.models import BaseModel
from apps.employees.models import Employee


class DeviceBinding(BaseModel):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='device_bindings'
    )
    device_unique_id = models.CharField(max_length=255, unique=True)
    attendance_device_id = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    bound_at = models.DateTimeField(auto_now_add=True)
    unbound_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'device_bindings'

    def __str__(self):
        return f"{self.employee.full_name} — {self.device_unique_id}"

    def is_registered(self, device_id):
        return self.device_unique_id == device_id and self.is_active