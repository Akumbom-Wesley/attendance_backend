import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.companies.permissions import IsSuperAdminOrHRAdmin
from apps.sync.services import ERPNextSyncService
from apps.sync.erpnext_client import ERPNextAPIError

logger = logging.getLogger(__name__)


class ResyncCompanyView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdminOrHRAdmin]

    def post(self, request, erpnext_doc_name):
        service = ERPNextSyncService()
        try:
            data = service.client.get_company(erpnext_doc_name)
            if not data:
                return Response({"detail": "Company not found in ERPNext."}, status=404)
            company = service.sync_company(data)
            return Response({
                "detail": "Company resynced.",
                "erpnext_doc_name": company.erpnext_doc_name,
                "name": company.name,
            }, status=200)
        except ERPNextAPIError as e:
            return Response({"detail": str(e)}, status=502)


class ResyncEmployeeView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdminOrHRAdmin]

    def post(self, request, erpnext_employee_id):
        service = ERPNextSyncService()
        try:
            data = service.client.get_employee(erpnext_employee_id)
            if not data:
                return Response({"detail": "Employee not found in ERPNext."}, status=404)
            employee = service.sync_employee(data)
            return Response({
                "detail": "Employee resynced.",
                "erpnext_employee_id": employee.erpnext_employee_id,
                "full_name": employee.full_name,
            }, status=200)
        except ERPNextAPIError as e:
            logger.error("ERPNext API error during employee resync: %s", e)
            if "404" in str(e):
                return Response({"detail": "Employee not found in ERPNext."}, status=404)
            return Response({"detail": str(e)}, status=502)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

class SyncCompanyEmployeesView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdminOrHRAdmin]

    def post(self, request, erpnext_doc_name):
        service = ERPNextSyncService()
        try:
            result = service.sync_employees_for_company(erpnext_doc_name)
            return Response({
                "detail": "Employees synced.",
                "erpnext_doc_name": erpnext_doc_name,
                "employees_synced": result["employees_synced"],
                "employees_skipped": result["employees_skipped"],
            }, status=200)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        except ERPNextAPIError as e:
            logger.error("ERPNext API error during company employees sync: %s", e)
            return Response({"detail": str(e)}, status=502)
