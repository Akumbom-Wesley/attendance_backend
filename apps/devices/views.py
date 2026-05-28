# apps/devices/views.py
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound

from apps.devices.models import DeviceBinding
from apps.devices.serializers import DeviceBindingSerializer, RegisterDeviceSerializer
from apps.devices.services import DeviceBindingService


class RegisterDeviceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != "EMPLOYEE":
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = RegisterDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            employee = request.user.employee_profile
        except Exception:
            return Response(
                {"detail": "Employee profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            binding = DeviceBindingService.register(
                employee=employee,
                device_unique_id=serializer.validated_data["device_unique_id"],
                attendance_device_id=serializer.validated_data["attendance_device_id"],
            )
        except ValueError:
            return Response(
                {"detail": "A device is already bound to this account. Ask HR to unbind first."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            DeviceBindingSerializer(binding).data,
            status=status.HTTP_201_CREATED,
        )


class MyDeviceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            binding = DeviceBinding.objects.get(
                employee=request.user.employee_profile,
                is_active=True,
            )
        except DeviceBinding.DoesNotExist:
            raise NotFound()

        return Response(DeviceBindingSerializer(binding).data)


class DeviceBindingListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ("HR_ADMIN", "SUPER_ADMIN"):
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = DeviceBinding.objects.select_related("employee")
        if request.user.role == "HR_ADMIN":
            qs = qs.filter(employee__company=request.user.company)

        return Response(DeviceBindingSerializer(qs, many=True).data)


class UnbindDeviceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ("HR_ADMIN", "SUPER_ADMIN"):
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = DeviceBinding.objects.all()
        if request.user.role == "HR_ADMIN":
            qs = qs.filter(employee__company=request.user.company)

        try:
            binding = qs.get(pk=pk)
        except DeviceBinding.DoesNotExist:
            raise NotFound()

        binding = DeviceBindingService.unbind(binding)
        return Response(DeviceBindingSerializer(binding).data)