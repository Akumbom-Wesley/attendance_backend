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