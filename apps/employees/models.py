from django.db import models
from django.conf import settings
from apps.common.models import BaseModel
from apps.companies.models import Company


class Employee(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee_profile'
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='employees'
    )
    erpnext_employee_id = models.CharField(max_length=255, unique=True)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, unique=True)
    department = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'employees'

    def __str__(self):
        return f"{self.full_name} ({self.erpnext_employee_id})"

    def get_active_device(self):
        return self.device_bindings.filter(is_active=True).first()

    def get_current_status(self):
        return self.statuses.order_by('-changed_at').first()
class EmployeeStatus(BaseModel):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('break', 'Break'),
        ('errand', 'Errand'),
        ('assignment', 'Assignment'),
        ('checked_out', 'Checked Out'),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='statuses'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    changed_at = models.DateTimeField(auto_now_add=True)
    auto_return_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'employee_statuses'
        get_latest_by = 'changed_at'

    def __str__(self):
        return f"{self.employee.full_name} — {self.status}"

    def schedule_auto_return(self, duration):
        raise NotImplementedError("Use EmployeeStatusService.schedule_auto_return()")

    def cancel_auto_return(self):
        raise NotImplementedError("Use EmployeeStatusService.cancel_auto_return()")