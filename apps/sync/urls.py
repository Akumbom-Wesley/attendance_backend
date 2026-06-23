from django.urls import path
from apps.sync.views import ResyncCompanyView, ResyncEmployeeView, SyncCompanyEmployeesView

app_name = "sync"

urlpatterns = [
    path(
        "erpnext/company/<str:erpnext_doc_name>/",
        ResyncCompanyView.as_view(),
        name="resync_company",
    ),
    path(
        "erpnext/company/<str:erpnext_doc_name>/employees/",
        SyncCompanyEmployeesView.as_view(),
        name="sync_company_employees",
    ),
    path(
        "erpnext/employee/<str:erpnext_employee_id>/",
        ResyncEmployeeView.as_view(),
        name="resync_employee",
    ),
]
