"""
TDD — Check-in Validation Pipeline
POST /api/v1/checkins/

Pipeline order (strict, first failure short-circuits):
0. Rate limit
1. Device binding check
2. Anti-spoofing
3. Timestamp plausibility (gps vs device AND gps vs server)
4. GPS geofence
5. Biometric
6. Wi-Fi RSSI
7. Duplicate check
8. Log type validation
9. Pass decision → CheckinRecord + AuditLog + Celery
"""

import pytest
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from apps.checkins.models import CheckinRecord
from apps.audit.models import AuditLog
from apps.employees.models import EmployeeStatus
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
def now():
    return timezone.now()


@pytest.fixture
def valid_payload(device, geofence_site, now):
    """A payload that passes every validation step."""
    return {
        "device_unique_id": device.device_unique_id,
        "log_type": "IN",
        "timestamp_gps": now.isoformat(),
        "timestamp_device": now.isoformat(),
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


@pytest.fixture
def employee_user(db, employee):
    return employee.user


# ------------------------------------------------------------------ #
#  Helper                                                              #
# ------------------------------------------------------------------ #

def post_checkin(authenticated_client, user, payload):
    client = authenticated_client(user)
    url = reverse("checkins:checkin")
    return client.post(url, payload, format="json")


# ------------------------------------------------------------------ #
#  Step 1 — Device binding                                             #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_unregistered_device_returns_403(
    authenticated_client, employee_user, valid_payload
):
    """Unknown device_unique_id → 403, AuditLog with DEVICE_NOT_REGISTERED."""
    valid_payload["device_unique_id"] = "UNKNOWN-DEVICE-999"
    response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 403
    assert AuditLog.objects.filter(error_code="DEVICE_NOT_REGISTERED").count() == 1


@pytest.mark.django_db
def test_inactive_device_returns_403(
    authenticated_client, employee_user, valid_payload, device
):
    """Inactive device → 403."""
    device.is_active = False
    device.save()
    response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 403
    assert AuditLog.objects.filter(error_code="DEVICE_NOT_REGISTERED").count() == 1


# ------------------------------------------------------------------ #
#  Step 2 — Anti-spoofing                                              #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_mock_location_returns_403(
    authenticated_client, employee_user, valid_payload, device, geofence_site
):
    """Mock location flag → 403, AuditLog MOCK_LOCATION_DETECTED."""
    valid_payload["antispoofing_flags"]["mock_location"] = True
    response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 403
    assert AuditLog.objects.filter(error_code="MOCK_LOCATION_DETECTED").count() == 1


@pytest.mark.django_db
def test_rooted_device_returns_403(
    authenticated_client, employee_user, valid_payload, device, geofence_site
):
    """Rooted device flag → 403, AuditLog ROOTED_DEVICE_DETECTED."""
    valid_payload["antispoofing_flags"]["is_rooted"] = True
    response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 403
    assert AuditLog.objects.filter(error_code="ROOTED_DEVICE_DETECTED").count() == 1


# ------------------------------------------------------------------ #
#  Step 3 — Timestamp plausibility                                     #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_gps_device_timestamp_gap_too_large_returns_422(
    authenticated_client, employee_user, valid_payload, device, geofence_site, now
):
    """GPS and device timestamps differ by > 300s → 422."""
    valid_payload["timestamp_device"] = (now - timedelta(seconds=400)).isoformat()
    response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 422
    assert AuditLog.objects.filter(error_code="TIMESTAMP_IMPLAUSIBLE").count() == 1


@pytest.mark.django_db
def test_gps_server_timestamp_gap_too_large_returns_422(
    authenticated_client, employee_user, valid_payload, device, geofence_site, now
):
    """GPS timestamp differs from server time by > 600s → 422."""
    valid_payload["timestamp_gps"] = (now - timedelta(seconds=700)).isoformat()
    valid_payload["timestamp_device"] = (now - timedelta(seconds=700)).isoformat()
    response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 422
    assert AuditLog.objects.filter(error_code="TIMESTAMP_IMPLAUSIBLE").count() == 1


# ------------------------------------------------------------------ #
#  Step 4 — GPS geofence                                               #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_outside_geofence_returns_422(
    authenticated_client, employee_user, valid_payload, device, geofence_site
):
    """GPS coordinates outside all geofence sites → 422."""
    valid_payload["gps_lat_smoothed"] = "0.000000"
    valid_payload["gps_lng_smoothed"] = "0.000000"
    response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 422
    assert AuditLog.objects.filter(error_code="GEOFENCE_FAILED").count() == 1


@pytest.mark.django_db
def test_no_active_geofence_site_returns_422(
    authenticated_client, employee_user, valid_payload, device, geofence_site
):
    """No active geofence sites for company → 422."""
    geofence_site.is_active = False
    geofence_site.save()
    response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 422
    assert AuditLog.objects.filter(error_code="GEOFENCE_FAILED").count() == 1


# ------------------------------------------------------------------ #
#  Step 5 — Biometric                                                  #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_biometric_failed_returns_422(
    authenticated_client, employee_user, valid_payload, device, geofence_site
):
    """biometric_passed=False → 422."""
    valid_payload["biometric_passed"] = False
    response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 422
    assert AuditLog.objects.filter(error_code="BIOMETRIC_FAILED").count() == 1


# ------------------------------------------------------------------ #
#  Step 6 — Wi-Fi RSSI                                                 #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_rssi_below_threshold_returns_422(
    authenticated_client, employee_user, valid_payload, device, geofence_site
):
    """RSSI below site threshold → 422."""
    valid_payload["rssi_avg"] = -90
    response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 422
    assert AuditLog.objects.filter(error_code="WIFI_RSSI_BELOW_THRESHOLD").count() == 1


@pytest.mark.django_db
def test_wrong_bssid_returns_422(
    authenticated_client, employee_user, valid_payload, device, geofence_site
):
    """BSSID doesn't match site → 422."""
    valid_payload["wifi_bssid"] = "00:00:00:00:00:00"
    response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 422
    assert AuditLog.objects.filter(error_code="WIFI_RSSI_BELOW_THRESHOLD").count() == 1


@pytest.mark.django_db
def test_wifi_unavailable_sets_two_factor_only(
    authenticated_client, employee_user, valid_payload, device, geofence_site
):
    """wifi_band=UNAVAILABLE skips RSSI, sets two_factor_only=True on AuditLog."""
    valid_payload["wifi_band"] = "UNAVAILABLE"
    valid_payload["rssi_avg"] = None
    valid_payload["wifi_bssid"] = ""
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 201
    log = AuditLog.objects.first()
    assert log.two_factor_only is True
    assert log.final_decision == "TWO_FACTOR_ONLY"


@pytest.mark.django_db
def test_enforce_5ghz_rejects_2_4ghz(
    authenticated_client, employee_user, valid_payload, device, geofence_site
):
    """Site enforces 5GHz but device on 2.4GHz → 422."""
    geofence_site.enforce_5ghz = True
    geofence_site.save()
    valid_payload["wifi_band"] = "2.4GHz"
    response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 422
    assert AuditLog.objects.filter(error_code="WIFI_RSSI_BELOW_THRESHOLD").count() == 1


# ------------------------------------------------------------------ #
#  Step 7 — Duplicate check                                            #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_duplicate_checkin_returns_409(
    authenticated_client, employee_user, valid_payload, device, geofence_site
):
    """Same device + timestamp_gps submitted twice → 409."""
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        post_checkin(authenticated_client, employee_user, valid_payload)
    response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 409
    assert AuditLog.objects.filter(error_code="ALREADY_CHECKED_IN").count() == 1


# ------------------------------------------------------------------ #
#  Step 8 — Log type validation                                        #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_clock_out_without_prior_clock_in_returns_422(
    authenticated_client, employee_user, valid_payload, device, geofence_site, employee
):
    """OUT submitted with no prior IN status → 422."""
    valid_payload["log_type"] = "OUT"
    response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 422
    assert AuditLog.objects.filter(error_code="INVALID_LOG_TYPE").count() == 1


@pytest.mark.django_db
def test_clock_out_with_prior_clock_in_passes(
    authenticated_client, employee_user, valid_payload, device, geofence_site, employee, now
):
    """OUT submitted after employee is present → passes."""
    EmployeeStatus.objects.create(
        employee=employee,
        status="present",
    )
    valid_payload["log_type"] = "OUT"
    valid_payload["timestamp_gps"] = (now + timedelta(seconds=1)).isoformat()
    valid_payload["timestamp_device"] = (now + timedelta(seconds=1)).isoformat()
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 201


# ------------------------------------------------------------------ #
#  Step 9 — Pass decision                                              #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_valid_checkin_creates_checkin_record(
    authenticated_client, employee_user, valid_payload, device, geofence_site
):
    """Valid payload → CheckinRecord created."""
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 201
    assert CheckinRecord.objects.count() == 1


@pytest.mark.django_db
def test_valid_checkin_creates_audit_log(
    authenticated_client, employee_user, valid_payload, device, geofence_site
):
    """Valid payload → AuditLog with PASS decision."""
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        response = post_checkin(authenticated_client, employee_user, valid_payload)
    assert response.status_code == 201
    log = AuditLog.objects.first()
    assert log.final_decision == "PASS"
    assert log.error_code == "SUCCESS"
    assert log.employee is not None


@pytest.mark.django_db
def test_valid_checkin_dispatches_celery_task(
    authenticated_client, employee_user, valid_payload, device, geofence_site
):
    """Valid payload → Celery push task dispatched."""
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay") as mock_task:
        post_checkin(authenticated_client, employee_user, valid_payload)
    mock_task.assert_called_once()


@pytest.mark.django_db
def test_valid_checkin_audit_log_is_immutable(
    authenticated_client, employee_user, valid_payload, device, geofence_site
):
    """AuditLog cannot be updated after creation."""
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        post_checkin(authenticated_client, employee_user, valid_payload)
    log = AuditLog.objects.first()
    with pytest.raises(ValueError, match="immutable"):
        log.save()


@pytest.mark.django_db
def test_unauthenticated_checkin_returns_401(api_client, valid_payload):
    """Unauthenticated request → 401."""
    url = reverse("checkins:checkin")
    response = api_client.post(url, valid_payload, format="json")
    assert response.status_code == 401