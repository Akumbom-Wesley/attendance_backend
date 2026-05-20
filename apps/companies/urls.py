from django.urls import path
from .views import (
    CompanyListView,
    CompanyRetrieveUpdateView,
    CompanyDeactivateView,
)

app_name = 'companies'

urlpatterns = [
    path('', CompanyListView.as_view(), name='company-list'),
    path('<int:pk>/', CompanyRetrieveUpdateView.as_view(), name='company-detail'),
    path('<int:pk>/deactivate/', CompanyDeactivateView.as_view(), name='company-deactivate'),
]