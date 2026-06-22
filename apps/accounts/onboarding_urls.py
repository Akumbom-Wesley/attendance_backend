from django.urls import path
from .views import (
    TriggerOnboardingView, BulkTriggerOnboardingView,
    SetPasswordView, ResendOnboardingView,
)

urlpatterns = [
    path('trigger/bulk/', BulkTriggerOnboardingView.as_view(), name='onboarding_bulk'),
    path('trigger/<str:erpnext_employee_id>/', TriggerOnboardingView.as_view(), name='onboarding_trigger'),
    path('set-password/', SetPasswordView.as_view(), name='onboarding_set_password'),
    path('resend/<str:erpnext_employee_id>/', ResendOnboardingView.as_view(), name='onboarding_resend'),
]