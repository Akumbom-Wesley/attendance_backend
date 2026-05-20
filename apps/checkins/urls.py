from django.urls import path
from apps.checkins.views import CheckinView, SyncOfflineBatchView

app_name = "checkins"

urlpatterns = [
    path("", CheckinView.as_view(), name="checkin"),
    path("sync/", SyncOfflineBatchView.as_view(), name="sync"),
]