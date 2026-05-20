import logging

from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from apps.companies.permissions import IsSuperAdminOrHRAdmin
from apps.employees.models import Employee
from apps.employees.serializers import EmployeeSerializer
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