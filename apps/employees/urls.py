from django.urls import path
from apps.employees.views import EmployeeListView, EmployeeDetailView, EmployeeStatusView, EmployeeLastCheckinAuditView
from apps.reports.views import EmployeeHistoryView, EmployeeReportView

app_name = "employees"

urlpatterns = [
    path("", EmployeeListView.as_view(), name="employee-list"),
    path("<int:pk>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path("<int:pk>/status/", EmployeeStatusView.as_view(), name="employee-status"),
    path("me/history/", EmployeeHistoryView.as_view(), name="me-history"),
    path("<int:pk>/history/", EmployeeReportView.as_view(), name="employee-history-hr"),
    path("<int:pk>/last-checkin-audit/", EmployeeLastCheckinAuditView.as_view(), name="employee-last-audit"),
]