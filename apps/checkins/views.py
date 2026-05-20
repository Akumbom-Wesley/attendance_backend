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