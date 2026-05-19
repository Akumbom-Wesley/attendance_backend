from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # API Schema
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # App routes — wired in as we build each app
#     path('api/v1/companies/', include('apps.companies.urls')),
#     path('api/v1/employees/', include('apps.employees.urls')),
#     path('api/v1/devices/', include('apps.devices.urls')),
#     path('api/v1/checkins/', include('apps.checkins.urls')),
#     path('api/v1/webhooks/', include('apps.webhooks.urls')),
#     path('api/v1/audit/', include('apps.audit.urls')),
 ]