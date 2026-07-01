# apps/reports/views.py
from datetime import date
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound

from apps.employees.models import Employee
from apps.reports.services import build_employee_report, build_company_report
from apps.reports.renderers import (
    render_employee_csv, render_employee_pdf,
    render_company_csv, render_company_pdf,
)


def _parse_dates(request):
    """Parse and validate date_from / date_to query params."""
    date_from_str = request.query_params.get("date_from")
    date_to_str = request.query_params.get("date_to")
    date_from = None
    date_to = None
    try:
        if date_from_str:
            date_from = date.fromisoformat(date_from_str)
        if date_to_str:
            date_to = date.fromisoformat(date_to_str)
    except ValueError:
        return None, None, Response(
            {"detail": "Invalid date format. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if date_from and date_to and date_from > date_to:
        return None, None, Response(
            {"detail": "date_from must be before or equal to date_to."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return date_from, date_to, None


def _render(fmt, report, is_company=False):
    if is_company:
        if fmt == "csv":
            return render_company_csv(report)
        if fmt == "pdf":
            return render_company_pdf(report)
    else:
        if fmt == "csv":
            return render_employee_csv(report)
        if fmt == "pdf":
            return render_employee_pdf(report)
    return None


class EmployeeHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ("HR_ADMIN", "EMPLOYEE"):
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )

        date_from, date_to, err = _parse_dates(request)
        if err:
            return err

        employee = request.user.employee_profile
        report = build_employee_report(employee, date_from, date_to)

        fmt = request.query_params.get("output_format", "json")
        rendered = _render(fmt, report)
        if rendered:
            return rendered

        return Response(report, status=status.HTTP_200_OK)


class EmployeeReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if request.user.role not in ("HR_ADMIN", "SUPER_ADMIN"):
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )

        date_from, date_to, err = _parse_dates(request)
        if err:
            return err

        try:
            qs = Employee.objects.all()
            if request.user.role == "HR_ADMIN":
                qs = qs.filter(company=request.user.company)
            employee = qs.get(pk=pk)
        except Employee.DoesNotExist:
            raise NotFound()

        report = build_employee_report(employee, date_from, date_to)

        fmt = request.query_params.get("output_format", "json")
        rendered = _render(fmt, report)
        if rendered:
            return rendered

        return Response(report, status=status.HTTP_200_OK)


class CompanyReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ("HR_ADMIN", "SUPER_ADMIN"):
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )

        date_from, date_to, err = _parse_dates(request)
        if err:
            return err

        if request.user.role == "SUPER_ADMIN":
            company_id = request.query_params.get("company_id")
            if not company_id:
                return Response(
                    {"detail": "company_id is required for SUPER_ADMIN."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            from apps.companies.models import Company
            try:
                company = Company.objects.get(pk=company_id)
            except Company.DoesNotExist:
                raise NotFound()
        else:
            company = request.user.company

        report = build_company_report(company, date_from, date_to)

        fmt = request.query_params.get("output_format", "json")
        rendered = _render(fmt, report, is_company=True)
        if rendered:
            return rendered

        return Response(report, status=status.HTTP_200_OK)