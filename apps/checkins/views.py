import uuid
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.checkins.serializers import (
    CheckinSerializer,
    OfflineBatchSerializer,
    serialize_records_for_celery,
)
from apps.checkins.services import CheckinValidationService


class CheckinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = CheckinValidationService(payload=serializer.validated_data)
        status_code, data = service.run()

        return Response(data, status=status_code)


class SyncOfflineBatchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OfflineBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        records = serializer.validated_data["records"]
        batch_id = str(uuid.uuid4())

        from apps.checkins.tasks import sync_offline_batch
        sync_offline_batch.delay(serialize_records_for_celery(records))

        return Response({"batch_id": batch_id}, status=status.HTTP_202_ACCEPTED)


class FlaggedRecordListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ("HR_ADMIN", "SUPER_ADMIN"):
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )
        from apps.checkins.services import FlaggedRecordService
        from apps.checkins.serializers import FlaggedRecordSerializer

        qs = FlaggedRecordService.get_queryset(request.user)
        qs = FlaggedRecordService.apply_status_filter(
            qs, request.query_params.get("status")
        )
        serializer = FlaggedRecordSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FlaggedRecordApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ("HR_ADMIN", "SUPER_ADMIN"):
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )
        from apps.checkins.services import FlaggedRecordService
        from apps.checkins.serializers import ReviewNoteSerializer

        serializer = ReviewNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        record = FlaggedRecordService.get_flagged_record_for_user(pk, request.user)
        FlaggedRecordService.approve(
            record, request.user, serializer.validated_data["review_note"]
        )
        return Response({"detail": "Record approved."}, status=status.HTTP_200_OK)


class FlaggedRecordRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ("HR_ADMIN", "SUPER_ADMIN"):
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )
        from apps.checkins.services import FlaggedRecordService
        from apps.checkins.serializers import ReviewNoteSerializer

        serializer = ReviewNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        record = FlaggedRecordService.get_flagged_record_for_user(pk, request.user)
        FlaggedRecordService.reject(
            record, request.user, serializer.validated_data["review_note"]
        )
        return Response({"detail": "Record rejected."}, status=status.HTTP_200_OK)