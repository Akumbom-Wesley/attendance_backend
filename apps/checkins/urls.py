from django.urls import path
from apps.checkins.views import CheckinView

app_name = "checkins"

urlpatterns = [
    path("", CheckinView.as_view(), name="checkin"),
]