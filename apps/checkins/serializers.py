import json
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework import serializers
from apps.checkins.models import CheckinRecord


class AntispoofingFlagsSerializer(serializers.Serializer):
    mock_location = serializers.BooleanField()
    is_rooted = serializers.BooleanField()


class CheckinSerializer(serializers.Serializer):
    device_unique_id = serializers.CharField()
    log_type = serializers.ChoiceField(choices=["IN", "OUT"])
    timestamp_gps = serializers.DateTimeField()
    timestamp_device = serializers.DateTimeField()
    gps_lat_smoothed = serializers.DecimalField(max_digits=9, decimal_places=6)
    gps_lng_smoothed = serializers.DecimalField(max_digits=9, decimal_places=6)
    gps_accuracy_metres = serializers.IntegerField()
    rssi_avg = serializers.IntegerField(allow_null=True, required=False)
    wifi_ssid = serializers.CharField(allow_blank=True, required=False, default="")
    wifi_bssid = serializers.CharField(allow_blank=True, required=False, default="")
    wifi_band = serializers.ChoiceField(choices=["2.4GHz", "5GHz", "UNAVAILABLE"])
    biometric_passed = serializers.BooleanField()
    antispoofing_flags = AntispoofingFlagsSerializer()


class CheckinRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckinRecord
        fields = [
            "id",
            "log_type",
            "timestamp_gps",
            "timestamp_device",
            "sync_received_at",
            "gps_lat_smoothed",
            "gps_lng_smoothed",
            "gps_accuracy_metres",
            "rssi_avg",
            "wifi_ssid",
            "wifi_bssid",
            "wifi_band",
            "biometric_passed",
            "is_flagged",
            "is_synced",
            "created_at",
        ]


class OfflineBatchSerializer(serializers.Serializer):
    records = serializers.ListField(
        child=CheckinSerializer(),
        min_length=1,
        error_messages={"min_length": "records list must not be empty."},
    )


def serialize_records_for_celery(records: list) -> list:
    """Convert validated_data records (with datetime/Decimal) to JSON-safe dicts for Celery."""
    return json.loads(json.dumps(records, cls=DjangoJSONEncoder))

class FlaggedRecordSerializer(serializers.ModelSerializer):
    reviewed_by = serializers.StringRelatedField()

    class Meta:
        model = CheckinRecord
        fields = [
            "id",
            "log_type",
            "timestamp_gps",
            "timestamp_device",
            "flag_reason",
            "is_flagged",
            "is_approved",
            "is_rejected",
            "is_synced",
            "review_note",
            "reviewed_by",
            "reviewed_at",
            "created_at",
        ]


class ReviewNoteSerializer(serializers.Serializer):
    review_note = serializers.CharField(min_length=1, error_messages={
        "blank": "review_note is required.",
        "min_length": "review_note is required.",
    })