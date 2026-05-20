from django.urls import path
from apps.sync.views import ResyncCompanyView, ResyncEmployeeView

app_name = "sync"

urlpatterns = [
    path(
        "erpnext/company/<str:erpnext_doc_name>/",
        ResyncCompanyView.as_view(),
        name="resync_company",
    ),
    path(
        "erpnext/employee/<str:erpnext_employee_id>/",
        ResyncEmployeeView.as_view(),
        name="resync_employee",
    ),
]