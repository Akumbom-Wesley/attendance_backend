from rest_framework import serializers
from apps.employees.models import Employee, EmployeeStatus


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


class EmployeeStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeStatus
        fields = ["id", "status", "changed_at", "auto_return_at"]
        read_only_fields = ["id", "changed_at", "auto_return_at"]


class EmployeeStatusWriteSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=EmployeeStatus.STATUS_CHOICES)