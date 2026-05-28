# apps/devices/serializers.py
from rest_framework import serializers
from apps.devices.models import DeviceBinding


class DeviceBindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceBinding
        fields = [
            "id",
            "device_unique_id",
            "attendance_device_id",
            "is_active",
            "bound_at",
            "unbound_at",
        ]
        read_only_fields = [
            "id",
            "is_active",
            "bound_at",
            "unbound_at",
        ]


class RegisterDeviceSerializer(serializers.Serializer):
    device_unique_id = serializers.CharField(max_length=255)
    attendance_device_id = serializers.CharField(max_length=255)