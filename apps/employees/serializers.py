from rest_framework import serializers
from apps.employees.models import Employee


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            "id",
            "erpnext_employee_id",
            "full_name",
            "email",
            "department",
            "is_active",
            "company",
        ]
        read_only_fields = fields