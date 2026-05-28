# apps/reports/urls.py
from django.urls import path
from apps.reports.views import (
    EmployeeReportView,
    CompanyReportView,
)

app_name = "reports"

urlpatterns = [
    path("employee/<int:pk>/", EmployeeReportView.as_view(), name="employee-report"),
    path("company/", CompanyReportView.as_view(), name="company-report"),
]