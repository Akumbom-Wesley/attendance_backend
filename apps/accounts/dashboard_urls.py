from django.urls import path
from .views import HRDashboardView

urlpatterns = [
    path('hr/', HRDashboardView.as_view(), name='dashboard-hr'),
]
