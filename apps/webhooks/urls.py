from django.urls import path
from apps.webhooks.views import ERPNextWebhookView

app_name = "webhooks"

urlpatterns = [
    path("erpnext/", ERPNextWebhookView.as_view(), name="erpnext"),
]