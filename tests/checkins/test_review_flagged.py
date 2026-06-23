# tests/checkins/test_review_flagged.py
"""
TDD — Review Flagged Checkin Records
Sprint 6

Endpoints:
  GET  /api/v1/checkins/flagged/               — list flagged records (HR_ADMIN, SUPER_ADMIN)
  POST /api/v1/checkins/flagged/{id}/approve/  — approve a flagged record
  POST /api/v1/checkins/flagged/{id}/reject/   — reject a flagged record

Rules:
  - is_flagged is NEVER cleared after being set (full audit trail)
  - Approve: sets is_approved=True, saves review_note + reviewed_by + reviewed_at
             dispatches push_checkin_to_erpnext if not yet synced
  - Reject:  sets is_rejected=True, saves review_note + reviewed_by + reviewed_at
             never dispatched to ERPNext
  - review_note is REQUIRED on both approve and reject
  - List default: all is_flagged=True records
  - List ?status=pending:  is_approved=False, is_rejected=False
  - List ?status=approved: is_approved=True
  - List ?status=rejected: is_rejected=True
  - HR_ADMIN scoped to their company; SUPER_ADMIN sees all
"""

import pytest
from unittest.mock import patch
from django.urls import reverse
from django.utils import timezone

from apps.checkins.models import CheckinRecord
from tests.factories.company_factory import CompanyFactory
from tests.factories.user_factory import UserFactory
from tests.factories.employee_factory import EmployeeFactory
from tests.factories.device_factory import DeviceBindingFactory


# ------------------------------------------------------------------ #
#  Factories / Fixtures                                                #
# ------------------------------------------------------------------ #

@pytest.fixture
def company(db):
    return CompanyFactory()


@pytest.fixture
def other_company(db):
    return CompanyFactory()


@pytest.fixture
def hr_user(db, company):
    return UserFactory(role="HR_ADMIN", company=company)


@pytest.fixture
def super_user(db):
    return UserFactory(role="SUPER_ADMIN")


@pytest.fixture
def employee_user(db, company):
    user = UserFactory(role="EMPLOYEE", company=company)
    EmployeeFactory(user=user, company=company)
    return user


@pytest.fixture
def device(db, company):
    user = UserFactory(role="EMPLOYEE", company=company)
    employee = EmployeeFactory(user=user, company=company)
    return DeviceBindingFactory(employee=employee, is_active=True)


@pytest.fixture
def other_device(db, other_company):
    user = UserFactory(role="EMPLOYEE", company=other_company)
    employee = EmployeeFactory(user=user, company=other_company)
    return DeviceBindingFactory(employee=employee, is_active=True)


@pytest.fixture
def flagged_record(db, device):
    return CheckinRecord.objects.create(
        device_binding=device,
        log_type="IN",
        timestamp_gps=timezone.now(),
        timestamp_device=timezone.now(),
        gps_lat_smoothed="3.848000",
        gps_lng_smoothed="11.502000",
        gps_accuracy_metres=10,
        wifi_band="UNAVAILABLE",
        biometric_passed=True,
        is_flagged=True,
        flag_reason="OFFLINE_RECORD",
    )


@pytest.fixture
def other_company_flagged_record(db, other_device):
    return CheckinRecord.objects.create(
        device_binding=other_device,
        log_type="IN",
        timestamp_gps=timezone.now(),
        timestamp_device=timezone.now(),
        gps_lat_smoothed="3.848000",
        gps_lng_smoothed="11.502000",
        gps_accuracy_metres=10,
        wifi_band="UNAVAILABLE",
        biometric_passed=True,
        is_flagged=True,
        flag_reason="OFFLINE_RECORD",
    )


@pytest.fixture
def non_flagged_record(db, device):
    return CheckinRecord.objects.create(
        device_binding=device,
        log_type="IN",
        timestamp_gps=timezone.now(),
        timestamp_device=timezone.now(),
        gps_lat_smoothed="3.848000",
        gps_lng_smoothed="11.502000",
        gps_accuracy_metres=10,
        wifi_band="UNAVAILABLE",
        biometric_passed=True,
        is_flagged=False,
    )


def list_flagged(authenticated_client, user, params=None):
    client = authenticated_client(user)
    url = reverse("checkins:flagged-list")
    return client.get(url, params or {})


def approve(authenticated_client, user, record_id, note="Verified via CCTV"):
    client = authenticated_client(user)
    url = reverse("checkins:flagged-approve", kwargs={"pk": record_id})
    return client.post(url, {"review_note": note}, format="json")


def reject(authenticated_client, user, record_id, note="Timestamp mismatch confirmed"):
    client = authenticated_client(user)
    url = reverse("checkins:flagged-reject", kwargs={"pk": record_id})
    return client.post(url, {"review_note": note}, format="json")


# ------------------------------------------------------------------ #
#  List — basic                                                        #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_list_flagged_returns_all_flagged_records(
    authenticated_client, hr_user, flagged_record
):
    """Default list returns all is_flagged=True records for HR Admin's company."""
    response = list_flagged(authenticated_client, hr_user)
    assert response.status_code == 200
    assert len(response.data) == 1


@pytest.mark.django_db
def test_list_flagged_excludes_non_flagged_records(
    authenticated_client, hr_user, flagged_record, non_flagged_record
):
    """Non-flagged records never appear in the list."""
    response = list_flagged(authenticated_client, hr_user)
    assert response.status_code == 200
    assert all(r["is_flagged"] for r in response.data)


@pytest.mark.django_db
def test_list_flagged_unauthenticated_returns_401(api_client):
    url = reverse("checkins:flagged-list")
    response = api_client.get(url)
    assert response.status_code == 401


@pytest.mark.django_db
def test_list_flagged_employee_returns_403(
    authenticated_client, employee_user, flagged_record
):
    response = list_flagged(authenticated_client, employee_user)
    assert response.status_code == 403


# ------------------------------------------------------------------ #
#  List — company scoping                                              #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_list_flagged_scoped_to_hr_admin_company(
    authenticated_client, hr_user, flagged_record, other_company_flagged_record
):
    """HR Admin only sees records from their own company."""
    response = list_flagged(authenticated_client, hr_user)
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == flagged_record.id


@pytest.mark.django_db
def test_list_flagged_super_admin_sees_all(
    authenticated_client, super_user, flagged_record, other_company_flagged_record
):
    """Super Admin sees flagged records across all companies."""
    response = list_flagged(authenticated_client, super_user)
    assert response.status_code == 200
    assert len(response.data) == 2


# ------------------------------------------------------------------ #
#  List — status filter                                                #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_list_flagged_status_pending_filter(
    authenticated_client, hr_user, device
):
    """?status=pending returns only unreviewed records."""
    pending = CheckinRecord.objects.create(
        device_binding=device, log_type="IN",
        timestamp_gps=timezone.now(), timestamp_device=timezone.now(),
        gps_lat_smoothed="3.848000", gps_lng_smoothed="11.502000",
        gps_accuracy_metres=10, wifi_band="UNAVAILABLE",
        biometric_passed=True, is_flagged=True, flag_reason="OFFLINE_RECORD",
    )
    CheckinRecord.objects.create(
        device_binding=device, log_type="OUT",
        timestamp_gps=timezone.now(), timestamp_device=timezone.now(),
        gps_lat_smoothed="3.848000", gps_lng_smoothed="11.502000",
        gps_accuracy_metres=10, wifi_band="UNAVAILABLE",
        biometric_passed=True, is_flagged=True, is_approved=True,
        flag_reason="OFFLINE_RECORD",
    )
    response = list_flagged(authenticated_client, hr_user, {"status": "pending"})
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == pending.id


@pytest.mark.django_db
def test_list_flagged_status_approved_filter(
    authenticated_client, hr_user, device
):
    """?status=approved returns only approved records."""
    CheckinRecord.objects.create(
        device_binding=device, log_type="IN",
        timestamp_gps=timezone.now(), timestamp_device=timezone.now(),
        gps_lat_smoothed="3.848000", gps_lng_smoothed="11.502000",
        gps_accuracy_metres=10, wifi_band="UNAVAILABLE",
        biometric_passed=True, is_flagged=True, flag_reason="OFFLINE_RECORD",
    )
    approved = CheckinRecord.objects.create(
        device_binding=device, log_type="OUT",
        timestamp_gps=timezone.now(), timestamp_device=timezone.now(),
        gps_lat_smoothed="3.848000", gps_lng_smoothed="11.502000",
        gps_accuracy_metres=10, wifi_band="UNAVAILABLE",
        biometric_passed=True, is_flagged=True, is_approved=True,
        flag_reason="OFFLINE_RECORD",
    )
    response = list_flagged(authenticated_client, hr_user, {"status": "approved"})
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == approved.id


@pytest.mark.django_db
def test_list_flagged_status_rejected_filter(
    authenticated_client, hr_user, device
):
    """?status=rejected returns only rejected records."""
    CheckinRecord.objects.create(
        device_binding=device, log_type="IN",
        timestamp_gps=timezone.now(), timestamp_device=timezone.now(),
        gps_lat_smoothed="3.848000", gps_lng_smoothed="11.502000",
        gps_accuracy_metres=10, wifi_band="UNAVAILABLE",
        biometric_passed=True, is_flagged=True, flag_reason="OFFLINE_RECORD",
    )
    rejected = CheckinRecord.objects.create(
        device_binding=device, log_type="OUT",
        timestamp_gps=timezone.now(), timestamp_device=timezone.now(),
        gps_lat_smoothed="3.848000", gps_lng_smoothed="11.502000",
        gps_accuracy_metres=10, wifi_band="UNAVAILABLE",
        biometric_passed=True, is_flagged=True, is_rejected=True,
        flag_reason="OFFLINE_RECORD",
    )
    response = list_flagged(authenticated_client, hr_user, {"status": "rejected"})
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == rejected.id


# ------------------------------------------------------------------ #
#  Approve                                                             #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_approve_returns_200(
    authenticated_client, hr_user, flagged_record
):
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        response = approve(authenticated_client, hr_user, flagged_record.id)
    assert response.status_code == 200


@pytest.mark.django_db
def test_approve_sets_is_approved(
    authenticated_client, hr_user, flagged_record
):
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        approve(authenticated_client, hr_user, flagged_record.id)
    flagged_record.refresh_from_db()
    assert flagged_record.is_approved is True


@pytest.mark.django_db
def test_approve_keeps_is_flagged_true(
    authenticated_client, hr_user, flagged_record
):
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        approve(authenticated_client, hr_user, flagged_record.id)
    flagged_record.refresh_from_db()
    assert flagged_record.is_flagged is True


@pytest.mark.django_db
def test_approve_saves_review_note_and_reviewer(
    authenticated_client, hr_user, flagged_record
):
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        approve(authenticated_client, hr_user, flagged_record.id, note="All good")
    flagged_record.refresh_from_db()
    assert flagged_record.review_note == "All good"
    assert flagged_record.reviewed_by == hr_user
    assert flagged_record.reviewed_at is not None


@pytest.mark.django_db
def test_approve_dispatches_push_task_if_not_synced(
    authenticated_client, hr_user, flagged_record
):
    flagged_record.is_synced = False
    flagged_record.save()
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay") as mock_task:
        approve(authenticated_client, hr_user, flagged_record.id)
    mock_task.assert_called_once_with(flagged_record.id)


@pytest.mark.django_db
def test_approve_skips_push_task_if_already_synced(
    authenticated_client, hr_user, flagged_record
):
    flagged_record.is_synced = True
    flagged_record.save()
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay") as mock_task:
        approve(authenticated_client, hr_user, flagged_record.id)
    mock_task.assert_not_called()


@pytest.mark.django_db
def test_approve_requires_review_note(
    authenticated_client, hr_user, flagged_record
):
    client = authenticated_client(hr_user)
    url = reverse("checkins:flagged-approve", kwargs={"pk": flagged_record.id})
    response = client.post(url, {"review_note": ""}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_approve_non_flagged_record_returns_404(
    authenticated_client, hr_user, non_flagged_record
):
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        response = approve(authenticated_client, hr_user, non_flagged_record.id)
    assert response.status_code == 404


# ------------------------------------------------------------------ #
#  Reject                                                              #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_reject_returns_200(
    authenticated_client, hr_user, flagged_record
):
    response = reject(authenticated_client, hr_user, flagged_record.id)
    assert response.status_code == 200


@pytest.mark.django_db
def test_reject_sets_is_rejected(
    authenticated_client, hr_user, flagged_record
):
    reject(authenticated_client, hr_user, flagged_record.id)
    flagged_record.refresh_from_db()
    assert flagged_record.is_rejected is True


@pytest.mark.django_db
def test_reject_keeps_is_flagged_true(
    authenticated_client, hr_user, flagged_record
):
    reject(authenticated_client, hr_user, flagged_record.id)
    flagged_record.refresh_from_db()
    assert flagged_record.is_flagged is True


@pytest.mark.django_db
def test_reject_saves_review_note_and_reviewer(
    authenticated_client, hr_user, flagged_record
):
    reject(authenticated_client, hr_user, flagged_record.id, note="GPS spoofed")
    flagged_record.refresh_from_db()
    assert flagged_record.review_note == "GPS spoofed"
    assert flagged_record.reviewed_by == hr_user
    assert flagged_record.reviewed_at is not None


@pytest.mark.django_db
def test_reject_does_not_dispatch_push_task(
    authenticated_client, hr_user, flagged_record
):
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay") as mock_task:
        reject(authenticated_client, hr_user, flagged_record.id)
    mock_task.assert_not_called()


@pytest.mark.django_db
def test_reject_requires_review_note(
    authenticated_client, hr_user, flagged_record
):
    client = authenticated_client(hr_user)
    url = reverse("checkins:flagged-reject", kwargs={"pk": flagged_record.id})
    response = client.post(url, {"review_note": ""}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_reject_non_flagged_record_returns_404(
    authenticated_client, hr_user, non_flagged_record
):
    response = reject(authenticated_client, hr_user, non_flagged_record.id)
    assert response.status_code == 404


# ------------------------------------------------------------------ #
#  Company isolation                                                   #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_hr_admin_cannot_approve_other_company_record(
    authenticated_client, hr_user, other_company_flagged_record
):
    with patch("apps.checkins.tasks.push_checkin_to_erpnext.delay"):
        response = approve(
            authenticated_client, hr_user, other_company_flagged_record.id
        )
    assert response.status_code == 404


@pytest.mark.django_db
def test_hr_admin_cannot_reject_other_company_record(
    authenticated_client, hr_user, other_company_flagged_record
):
    response = reject(
        authenticated_client, hr_user, other_company_flagged_record.id
    )
    assert response.status_code == 404