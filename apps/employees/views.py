import logging

from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from apps.companies.permissions import IsSuperAdminOrHRAdmin
from apps.employees.models import Employee, EmployeeStatus
from apps.employees.serializers import (
    EmployeeSerializer,
    EmployeeStatusSerializer,
    EmployeeStatusWriteSerializer,
)
from apps.accounts.models import User

logger = logging.getLogger(__name__)


class EmployeeListView(ListAPIView):
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated, IsSuperAdminOrHRAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.SUPER_ADMIN:
            return Employee.objects.all()
        return Employee.objects.filter(company=user.company)


class EmployeeDetailView(RetrieveAPIView):
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated, IsSuperAdminOrHRAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.SUPER_ADMIN:
            return Employee.objects.all()
        return Employee.objects.filter(company=user.company)


class EmployeeStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_employee(self, pk):
        return get_object_or_404(Employee, pk=pk)

    def get(self, request, pk):
        employee = self._get_employee(pk)
        latest = EmployeeStatus.objects.filter(employee=employee).order_by("-changed_at").first()
        if latest is None:
            return Response({"status": None, "changed_at": None, "auto_return_at": None})
        serializer = EmployeeStatusSerializer(latest)
        return Response(serializer.data)

    def post(self, request, pk):
        employee = self._get_employee(pk)
        serializer = EmployeeStatusWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = EmployeeStatus.objects.create(
            employee=employee,
            status=serializer.validated_data["status"],
        )
        return Response(
            EmployeeStatusSerializer(record).data,
            status=status.HTTP_201_CREATED,
        )

class EmployeeLastCheckinAuditView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if request.user.role not in ("HR_ADMIN", "SUPER_ADMIN"):
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from apps.audit.models import AuditLog

        qs = Employee.objects.all()
        if request.user.role == "HR_ADMIN":
            qs = qs.filter(company=request.user.company)

        employee = get_object_or_404(qs, pk=pk)

        audit = (
            AuditLog.objects
            .filter(employee=employee)
            .order_by("-created_at")
            .first()
        )
        if audit is None:
            return Response(
                {"detail": "No audit log found for this employee."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = {
            "id": audit.id,
            "biometric_result": audit.biometric_result,
            "geofence_result": audit.geofence_result,
            "rssi_result": audit.rssi_result,
            "antispoofing_result": audit.antispoofing_result,
            "wifi_available": audit.wifi_available,
            "two_factor_only": audit.two_factor_only,
            "error_code": audit.error_code,
            "final_decision": audit.final_decision,
            "gps_timestamp_used": audit.gps_timestamp_used,
            "created_at": audit.created_at,
        }
        return Response(data, status=status.HTTP_200_OK)
