from django.urls import path
from apps.checkins.views import (
    CheckinView,
    SyncOfflineBatchView,
    FlaggedRecordListView,
    FlaggedRecordApproveView,
    FlaggedRecordRejectView,
)

app_name = "checkins"

urlpatterns = [
    path("", CheckinView.as_view(), name="checkin"),
    path("sync/", SyncOfflineBatchView.as_view(), name="sync"),
    path("flagged/", FlaggedRecordListView.as_view(), name="flagged-list"),
    path("flagged/<int:pk>/approve/", FlaggedRecordApproveView.as_view(), name="flagged-approve"),
    path("flagged/<int:pk>/reject/", FlaggedRecordRejectView.as_view(), name="flagged-reject"),
]