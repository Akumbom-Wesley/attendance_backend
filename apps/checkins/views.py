from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.checkins.serializers import CheckinSerializer
from apps.checkins.services import CheckinValidationService


class CheckinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = CheckinValidationService(payload=serializer.validated_data)
        status_code, data = service.run()

        return Response(data, status=status_code)