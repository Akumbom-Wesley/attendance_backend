# apps/devices/urls.py
from django.urls import path
from apps.devices.views import (
    RegisterDeviceView,
    MyDeviceView,
    DeviceBindingListView,
    UnbindDeviceView,
)

app_name = "devices"

urlpatterns = [
    path("register/", RegisterDeviceView.as_view(), name="register"),
    path("me/", MyDeviceView.as_view(), name="me"),
    path("", DeviceBindingListView.as_view(), name="list"),
    path("<int:pk>/unbind/", UnbindDeviceView.as_view(), name="unbind"),
]