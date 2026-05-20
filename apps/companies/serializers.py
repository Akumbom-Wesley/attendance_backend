from rest_framework import serializers
from .models import Company, GeofenceSite


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = (
            'id',
            'erpnext_doc_name',
            'name',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'erpnext_doc_name', 'created_at', 'updated_at')


class GeofenceSiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeofenceSite
        fields = (
            'id',
            'company',
            'name',
            'latitude',
            'longitude',
            'radius_metres',
            'wifi_ssid',
            'wifi_bssid',
            'rssi_threshold',
            'enforce_5ghz',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')