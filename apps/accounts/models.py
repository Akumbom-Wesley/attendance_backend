from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
        HR_ADMIN = 'HR_ADMIN', 'HR Admin'
        EMPLOYEE = 'EMPLOYEE', 'Employee'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    erpnext_employee_id = models.CharField(
        max_length=255,
        blank=True,
        unique=True,
        null=True
    )
    onboarding_token = models.CharField(max_length=255, blank=True)
    onboarding_token_expires_at = models.DateTimeField(null=True, blank=True)
    is_onboarded = models.BooleanField(default=False)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

    @property
    def is_super_admin(self):
        return self.role == self.Role.SUPER_ADMIN

    @property
    def is_hr_admin(self):
        return self.role == self.Role.HR_ADMIN

    @property
    def is_employee(self):
        return self.role == self.Role.EMPLOYEE