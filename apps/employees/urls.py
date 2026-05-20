from django.urls import path
from apps.employees.views import EmployeeListView, EmployeeDetailView, EmployeeStatusView

app_name = "employees"

urlpatterns = [
    path("", EmployeeListView.as_view(), name="employee-list"),
    path("<int:pk>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path("<int:pk>/status/", EmployeeStatusView.as_view(), name="employee-status"),
]