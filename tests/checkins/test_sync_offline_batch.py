"""
TDD — Offline Batch Sync
POST /api/v1/checkins/sync/

Strategy:
- Flutter posts a list of offline payloads when connectivity restores
- Endpoint returns 202 Accepted + batch_id immediately
- Celery processes each record through modified pipeline:
  - Step 3 skips gps vs server timestamp check
  - All other steps identical to online pipeline
- Every passing record gets is_flagged=True
- Every record (pass or fail) gets an AuditLog
"""

import pytest
from unittest.mock import patch
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from apps.checkins.models import CheckinRecord
from apps.audit.models import AuditLog
from tests.factories.company_factory import CompanyFactory
from tests.factories.user_factory import UserFactory
from tests.factories.employee_factory import EmployeeFactory
from tests.factories.device_factory import DeviceBindingFactory


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def company(db):
    return CompanyFactory()


@pytest.fixture
def geofence_site(db, company):
    from apps.companies.models import GeofenceSite
    return GeofenceSite.objects.create(
        company=company,
        name="HQ",
        latitude=Decimal("3.848000"),
        longitude=Decimal("11.502000"),
        radius_metres=100,
        wifi_ssid="Office-WiFi",
        wifi_bssid="AA:BB:CC:DD:EE:FF",
        rssi_threshold=-70,
        enforce_5ghz=False,
        is_active=True,
    )


@pytest.fixture
def employee(db, company):
    user = UserFactory(role="EMPLOYEE", company=company)
    return EmployeeFactory(user=user, company=company)


@pytest.fixture
def device(db, employee):
    return DeviceBindingFactory(employee=employee, is_active=True)


@pytest.fixture
def employee_user(employee):
    return employee.user


@pytest.fixture
def old_now():
    """Simulates a timestamp from 2 hours ago — old enough to fail server check."""
    return timezone.now() - timedelta(hours=2)


@pytest.fixture
def valid_offline_payload(device, geofence_site, old_now):
    """A payload that is old (would fail server timestamp check) but otherwise valid."""
    return {
        "device_unique_id": device.device_unique_id,
        "log_type": "IN",
        "timestamp_gps": old_now.isoformat(),
        "timestamp_device": old_now.isoformat(),
        "gps_lat_smoothed": "3.848000",
        "gps_lng_smoothed": "11.502000",
        "gps_accuracy_metres": 10,
        "rssi_avg": -60,
        "wifi_ssid": "Office-WiFi",
        "wifi_bssid": "AA:BB:CC:DD:EE:FF",
        "wifi_band": "5GHz",
        "biometric_passed": True,
        "antispoofing_flags": {
            "mock_location": False,
            "is_rooted": False,
        },
    }


def post_sync(authenticated_client, user, payload):
    client = authenticated_client(user)
    url = reverse("checkins:sync")
    return client.post(url, payload, format="json")


# ------------------------------------------------------------------ #
#  Endpoint                                                            #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_sync_returns_202(
    authenticated_client, employee_user, valid_offline_payload
):
    """Valid batch → 202 Accepted immediately."""
    with patch("apps.checkins.tasks.sync_offline_batch.delay"):
        response = post_sync(
            authenticated_client,
            employee_user,
            {"records": [valid_offline_payload]},
        )
    assert response.status_code == 202


@pytest.mark.django_db
def test_sync_returns_batch_id(
    authenticated_client, employee_user, valid_offline_payload
):
    """Response includes a batch_id."""
    with patch("apps.checkins.tasks.sync_offline_batch.delay"):
        response = post_sync(
            authenticated_client,
            employee_user,
            {"records": [valid_offline_payload]},
        )
    assert "batch_id" in response.data


@pytest.mark.django_db
def test_sync_dispatches_celery_task(
    authenticated_client, employee_user, valid_offline_payload
):
    """Celery task is dispatched with the records."""
    with patch("apps.checkins.tasks.sync_offline_batch.delay") as mock_task:
        post_sync(
            authenticated_client,
            employee_user,
            {"records": [valid_offline_payload]},
        )
    mock_task.assert_called_once()


@pytest.mark.django_db
def test_sync_empty_records_returns_400(
    authenticated_client, employee_user
):
    """Empty records list → 400."""
    with patch("apps.checkins.tasks.sync_offline_batch.delay"):
        response = post_sync(
            authenticated_client,
            employee_user,
            {"records": []},
        )
    assert response.status_code == 400


@pytest.mark.django_db
def test_sync_unauthenticated_returns_401(api_client, valid_offline_payload):
    """Unauthenticated request → 401."""
    url = reverse("checkins:sync")
    response = api_client.post(
        url, {"records": [valid_offline_payload]}, format="json"
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_sync_missing_records_key_returns_400(
    authenticated_client, employee_user
):
    """Payload without records key → 400."""
    with patch("apps.checkins.tasks.sync_offline_batch.delay"):
        response = post_sync(
            authenticated_client,
            employee_user,
            {},
        )
    assert response.status_code == 400


# ------------------------------------------------------------------ #
#  Pipeline — modified timestamp check                                 #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_old_timestamp_passes_offline_pipeline(
    valid_offline_payload, device, geofence_site
):
    """Old timestamp (>600s from server) passes offline pipeline."""
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        from apps.checkins.services import OfflineCheckinValidationService
        service = OfflineCheckinValidationService(
            payload=_deserialize(valid_offline_payload)
        )
        status_code, data = service.run()
    assert status_code == 201


@pytest.mark.django_db
def test_old_timestamp_would_fail_online_pipeline(
    valid_offline_payload, device, geofence_site
):
    """Same old payload fails the standard online pipeline at Step 3."""
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        from apps.checkins.services import CheckinValidationService
        service = CheckinValidationService(
            payload=_deserialize(valid_offline_payload)
        )
        status_code, data = service.run()
    assert status_code == 422
    assert AuditLog.objects.filter(error_code="TIMESTAMP_IMPLAUSIBLE").count() == 1


# ------------------------------------------------------------------ #
#  Pipeline — pass creates flagged record                              #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_offline_pass_creates_flagged_checkin_record(
    valid_offline_payload, device, geofence_site
):
    """Passing offline record → CheckinRecord with is_flagged=True."""
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        from apps.checkins.services import OfflineCheckinValidationService
        service = OfflineCheckinValidationService(
            payload=_deserialize(valid_offline_payload)
        )
        service.run()
    record = CheckinRecord.objects.first()
    assert record is not None
    assert record.is_flagged is True


@pytest.mark.django_db
def test_offline_pass_creates_audit_log(
    valid_offline_payload, device, geofence_site
):
    """Passing offline record → AuditLog with PASS decision."""
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        from apps.checkins.services import OfflineCheckinValidationService
        service = OfflineCheckinValidationService(
            payload=_deserialize(valid_offline_payload)
        )
        service.run()
    log = AuditLog.objects.first()
    assert log.final_decision in ("PASS", "TWO_FACTOR_ONLY")
    assert log.error_code == "SUCCESS"


@pytest.mark.django_db
def test_offline_pass_dispatches_push_task(
    valid_offline_payload, device, geofence_site
):
    """Passing offline record → push_checkin_to_erpnext dispatched."""
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay") as mock_task:
        from apps.checkins.services import OfflineCheckinValidationService
        service = OfflineCheckinValidationService(
            payload=_deserialize(valid_offline_payload)
        )
        service.run()
    mock_task.assert_called_once()


# ------------------------------------------------------------------ #
#  Pipeline — fail cases still write AuditLog                          #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_offline_unregistered_device_writes_audit_log(
    valid_offline_payload, device, geofence_site
):
    """Unknown device in offline batch → AuditLog DEVICE_NOT_REGISTERED."""
    payload = dict(valid_offline_payload)
    payload["device_unique_id"] = "UNKNOWN-999"
    from apps.checkins.services import OfflineCheckinValidationService
    service = OfflineCheckinValidationService(payload=_deserialize(payload))
    status_code, _ = service.run()
    assert status_code == 403
    assert AuditLog.objects.filter(error_code="DEVICE_NOT_REGISTERED").count() == 1


@pytest.mark.django_db
def test_offline_mock_location_writes_audit_log(
    valid_offline_payload, device, geofence_site
):
    """Mock location in offline batch → AuditLog MOCK_LOCATION_DETECTED."""
    payload = dict(valid_offline_payload)
    payload["antispoofing_flags"] = {"mock_location": True, "is_rooted": False}
    from apps.checkins.services import OfflineCheckinValidationService
    service = OfflineCheckinValidationService(payload=_deserialize(payload))
    status_code, _ = service.run()
    assert status_code == 403
    assert AuditLog.objects.filter(error_code="MOCK_LOCATION_DETECTED").count() == 1


@pytest.mark.django_db
def test_offline_gps_device_gap_still_fails(
    valid_offline_payload, device, geofence_site, old_now
):
    """GPS vs device gap > 300s still fails even in offline mode."""
    payload = dict(valid_offline_payload)
    payload["timestamp_device"] = (old_now - timedelta(seconds=400)).isoformat()
    from apps.checkins.services import OfflineCheckinValidationService
    service = OfflineCheckinValidationService(payload=_deserialize(payload))
    status_code, _ = service.run()
    assert status_code == 422
    assert AuditLog.objects.filter(error_code="TIMESTAMP_IMPLAUSIBLE").count() == 1


# ------------------------------------------------------------------ #
#  Helper                                                              #
# ------------------------------------------------------------------ #

def _deserialize(payload: dict) -> dict:
    """Convert raw dict with ISO strings into DRF-validated types."""
    from apps.checkins.serializers import CheckinSerializer
    s = CheckinSerializer(data=payload)
    s.is_valid(raise_exception=True)
    return s.validated_data 