from django.urls import path
from .views import (
    CompanyMeView,
    CompanyListView,
    CompanyRetrieveUpdateView,
    CompanyDeactivateView,
    GeofenceSiteMobileView,
)

app_name = 'companies'

urlpatterns = [
    path('', CompanyListView.as_view(), name='company-list'),
    path('<int:pk>/', CompanyRetrieveUpdateView.as_view(), name='company-detail'),
    path('<int:pk>/deactivate/', CompanyDeactivateView.as_view(), name='company-deactivate'),
    path('me/', CompanyMeView.as_view(), name='company-me'),
    path('geofence-site/', GeofenceSiteMobileView.as_view(), name='geofence-site'),
]