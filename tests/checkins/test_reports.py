# tests/checkins/test_reports.py
"""
TDD — View History + Generate Reports
Sprint 7

Endpoints:
  GET /api/v1/employees/me/history/        — EMPLOYEE own history
  GET /api/v1/reports/employee/{id}/       — HR_ADMIN, SUPER_ADMIN per-employee
  GET /api/v1/reports/company/             — HR_ADMIN, SUPER_ADMIN company-wide

Query params:
  date_from, date_to  — ISO date filter
  format              — json (default) | csv | pdf
  company_id          — required for SUPER_ADMIN on /reports/company/

Pairing logic:
  IN + OUT = COMPLETE entry with duration
  IN only  = INCOMPLETE
  OUT only = OUT_ONLY
"""

import pytest
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal

from apps.checkins.models import CheckinRecord
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
def other_company(db):
    return CompanyFactory()


@pytest.fixture
def employee_user(db, company):
    user = UserFactory(role="EMPLOYEE", company=company)
    EmployeeFactory(user=user, company=company)
    return user


@pytest.fixture
def employee(db, employee_user):
    return employee_user.employee_profile


@pytest.fixture
def device(db, employee):
    return DeviceBindingFactory(employee=employee, is_active=True)


@pytest.fixture
def hr_user(db, company):
    return UserFactory(role="HR_ADMIN", company=company)


@pytest.fixture
def super_user(db):
    return UserFactory(role="SUPER_ADMIN")


@pytest.fixture
def other_employee_user(db, other_company):
    user = UserFactory(role="EMPLOYEE", company=other_company)
    EmployeeFactory(user=user, company=other_company)
    return user


@pytest.fixture
def other_employee(db, other_employee_user):
    return other_employee_user.employee_profile


@pytest.fixture
def other_device(db, other_employee):
    return DeviceBindingFactory(employee=other_employee, is_active=True)


@pytest.fixture
def base_dt():
    """A fixed datetime within the test date range."""
    return timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)


@pytest.fixture
def paired_records(db, device, base_dt):
    """One complete IN+OUT pair for today."""
    clock_in = CheckinRecord.objects.create(
        device_binding=device,
        log_type="IN",
        timestamp_gps=base_dt,
        timestamp_device=base_dt,
        gps_lat_smoothed=Decimal("3.848000"),
        gps_lng_smoothed=Decimal("11.502000"),
        gps_accuracy_metres=10,
        wifi_band="UNAVAILABLE",
        biometric_passed=True,
    )
    clock_out = CheckinRecord.objects.create(
        device_binding=device,
        log_type="OUT",
        timestamp_gps=base_dt + timedelta(hours=8),
        timestamp_device=base_dt + timedelta(hours=8),
        gps_lat_smoothed=Decimal("3.848000"),
        gps_lng_smoothed=Decimal("11.502000"),
        gps_accuracy_metres=10,
        wifi_band="UNAVAILABLE",
        biometric_passed=True,
    )
    return clock_in, clock_out


@pytest.fixture
def incomplete_record(db, device, base_dt):
    """A clock-in with no matching clock-out."""
    return CheckinRecord.objects.create(
        device_binding=device,
        log_type="IN",
        timestamp_gps=base_dt + timedelta(days=1),
        timestamp_device=base_dt + timedelta(days=1),
        gps_lat_smoothed=Decimal("3.848000"),
        gps_lng_smoothed=Decimal("11.502000"),
        gps_accuracy_metres=10,
        wifi_band="UNAVAILABLE",
        biometric_passed=True,
    )


def get_history(authenticated_client, user, params=None):
    client = authenticated_client(user)
    url = reverse("employees:me-history")
    return client.get(url, params or {})


def get_employee_report(authenticated_client, user, employee_id, params=None):
    client = authenticated_client(user)
    url = reverse("reports:employee-report", kwargs={"pk": employee_id})
    return client.get(url, params or {})


def get_company_report(authenticated_client, user, params=None):
    client = authenticated_client(user)
    url = reverse("reports:company-report")
    return client.get(url, params or {})


# ------------------------------------------------------------------ #
#  View History                                                        #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_history_returns_200(
    authenticated_client, employee_user, paired_records
):
    response = get_history(authenticated_client, employee_user)
    assert response.status_code == 200


@pytest.mark.django_db
def test_history_returns_paired_attendance_entries(
    authenticated_client, employee_user, paired_records
):
    """IN+OUT pair → one COMPLETE attendance entry with hours_worked."""
    response = get_history(authenticated_client, employee_user)
    assert response.status_code == 200
    attendance = response.data["attendance"]
    assert len(attendance) == 1
    assert attendance[0]["status"] == "COMPLETE"
    assert attendance[0]["hours_worked"] is not None
    assert attendance[0]["clock_out"] is not None


@pytest.mark.django_db
def test_history_incomplete_entry_for_unmatched_clock_in(
    authenticated_client, employee_user, incomplete_record
):
    """Unmatched IN → INCOMPLETE entry."""
    response = get_history(authenticated_client, employee_user)
    assert response.status_code == 200
    attendance = response.data["attendance"]
    assert len(attendance) == 1
    assert attendance[0]["status"] == "INCOMPLETE"
    assert attendance[0]["clock_out"] is None
    assert attendance[0]["hours_worked"] is None


@pytest.mark.django_db
def test_history_filters_by_date_range(
    authenticated_client, employee_user, device, base_dt
):
    """Records outside date_from/date_to are excluded."""
    # inside range
    CheckinRecord.objects.create(
        device_binding=device, log_type="IN",
        timestamp_gps=base_dt,
        timestamp_device=base_dt,
        gps_lat_smoothed=Decimal("3.848000"),
        gps_lng_smoothed=Decimal("11.502000"),
        gps_accuracy_metres=10, wifi_band="UNAVAILABLE", biometric_passed=True,
    )
    # outside range — 10 days ago
    CheckinRecord.objects.create(
        device_binding=device, log_type="IN",
        timestamp_gps=base_dt - timedelta(days=10),
        timestamp_device=base_dt - timedelta(days=10),
        gps_lat_smoothed=Decimal("3.848000"),
        gps_lng_smoothed=Decimal("11.502000"),
        gps_accuracy_metres=10, wifi_band="UNAVAILABLE", biometric_passed=True,
    )
    today = date.today().isoformat()
    response = get_history(
        authenticated_client, employee_user,
        {"date_from": today, "date_to": today},
    )
    assert response.status_code == 200
    assert len(response.data["attendance"]) == 1


@pytest.mark.django_db
def test_history_returns_csv(
    authenticated_client, employee_user, paired_records
):
    response = get_history(
        authenticated_client, employee_user, {"output_format": "csv"}
    )
    assert response.status_code == 200
    assert "text/csv" in response["Content-Type"]


@pytest.mark.django_db
def test_history_returns_pdf(
    authenticated_client, employee_user, paired_records
):
    response = get_history(
        authenticated_client, employee_user, {"output_format": "pdf"}
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"


@pytest.mark.django_db
def test_history_unauthenticated_returns_401(api_client):
    url = reverse("employees:me-history")
    response = api_client.get(url)
    assert response.status_code == 401


@pytest.mark.django_db
def test_history_hr_admin_returns_403(
    authenticated_client, hr_user, paired_records
):
    response = get_history(authenticated_client, hr_user)
    assert response.status_code == 403


# ------------------------------------------------------------------ #
#  Per-employee report                                                 #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_employee_report_returns_200(
    authenticated_client, hr_user, employee, paired_records
):
    response = get_employee_report(
        authenticated_client, hr_user, employee.id
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_employee_report_returns_paired_entries(
    authenticated_client, hr_user, employee, paired_records
):
    response = get_employee_report(
        authenticated_client, hr_user, employee.id
    )
    assert response.status_code == 200
    attendance = response.data["attendance"]
    assert len(attendance) == 1
    assert attendance[0]["status"] == "COMPLETE"


@pytest.mark.django_db
def test_employee_report_filters_by_date_range(
    authenticated_client, hr_user, employee, device, base_dt
):
    CheckinRecord.objects.create(
        device_binding=device, log_type="IN",
        timestamp_gps=base_dt,
        timestamp_device=base_dt,
        gps_lat_smoothed=Decimal("3.848000"),
        gps_lng_smoothed=Decimal("11.502000"),
        gps_accuracy_metres=10, wifi_band="UNAVAILABLE", biometric_passed=True,
    )
    CheckinRecord.objects.create(
        device_binding=device, log_type="IN",
        timestamp_gps=base_dt - timedelta(days=10),
        timestamp_device=base_dt - timedelta(days=10),
        gps_lat_smoothed=Decimal("3.848000"),
        gps_lng_smoothed=Decimal("11.502000"),
        gps_accuracy_metres=10, wifi_band="UNAVAILABLE", biometric_passed=True,
    )
    today = date.today().isoformat()
    response = get_employee_report(
        authenticated_client, hr_user, employee.id,
        {"date_from": today, "date_to": today},
    )
    assert response.status_code == 200
    assert len(response.data["attendance"]) == 1


@pytest.mark.django_db
def test_employee_report_returns_csv(
    authenticated_client, hr_user, employee, paired_records
):
    response = get_employee_report(
        authenticated_client, hr_user, employee.id, {"output_format": "csv"}
    )
    assert response.status_code == 200
    assert "text/csv" in response["Content-Type"]


@pytest.mark.django_db
def test_employee_report_returns_pdf(
    authenticated_client, hr_user, employee, paired_records
):
    response = get_employee_report(
        authenticated_client, hr_user, employee.id, {"output_format": "pdf"}
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"


@pytest.mark.django_db
def test_employee_report_employee_role_returns_403(
    authenticated_client, employee_user, employee
):
    response = get_employee_report(
        authenticated_client, employee_user, employee.id
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_employee_report_hr_admin_scoped_to_company(
    authenticated_client, hr_user, employee, paired_records
):
    """HR Admin can access employee in their own company."""
    response = get_employee_report(
        authenticated_client, hr_user, employee.id
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_employee_report_hr_admin_cannot_access_other_company(
    authenticated_client, hr_user, other_employee
):
    """HR Admin cannot access employee from another company."""
    response = get_employee_report(
        authenticated_client, hr_user, other_employee.id
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_employee_report_unauthenticated_returns_401(api_client, employee):
    url = reverse("reports:employee-report", kwargs={"pk": employee.id})
    response = api_client.get(url)
    assert response.status_code == 401


@pytest.mark.django_db
def test_employee_report_invalid_date_range_returns_400(
    authenticated_client, hr_user, employee
):
    """date_from after date_to → 400."""
    response = get_employee_report(
        authenticated_client, hr_user, employee.id,
        {"date_from": "2026-05-31", "date_to": "2026-05-01"},
    )
    assert response.status_code == 400


# ------------------------------------------------------------------ #
#  Company-wide report                                                 #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_company_report_returns_200(
    authenticated_client, hr_user, paired_records
):
    response = get_company_report(authenticated_client, hr_user)
    assert response.status_code == 200


@pytest.mark.django_db
def test_company_report_contains_all_employees(
    authenticated_client, hr_user, company, paired_records
):
    """Company report lists all employees in the company."""
    response = get_company_report(authenticated_client, hr_user)
    assert response.status_code == 200
    assert "employees" in response.data
    assert len(response.data["employees"]) >= 1


@pytest.mark.django_db
def test_company_report_filters_by_date_range(
    authenticated_client, hr_user, device, base_dt
):
    CheckinRecord.objects.create(
        device_binding=device, log_type="IN",
        timestamp_gps=base_dt,
        timestamp_device=base_dt,
        gps_lat_smoothed=Decimal("3.848000"),
        gps_lng_smoothed=Decimal("11.502000"),
        gps_accuracy_metres=10, wifi_band="UNAVAILABLE", biometric_passed=True,
    )
    today = date.today().isoformat()
    response = get_company_report(
        authenticated_client, hr_user,
        {"date_from": today, "date_to": today},
    )
    assert response.status_code == 200
    assert "employees" in response.data


@pytest.mark.django_db
def test_company_report_returns_csv(
    authenticated_client, hr_user, paired_records
):
    response = get_company_report(
        authenticated_client, hr_user, {"output_format": "csv"}
    )
    assert response.status_code == 200
    assert "text/csv" in response["Content-Type"]


@pytest.mark.django_db
def test_company_report_returns_pdf(
    authenticated_client, hr_user, paired_records
):
    response = get_company_report(
        authenticated_client, hr_user, {"output_format": "pdf"}
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"


@pytest.mark.django_db
def test_company_report_employee_role_returns_403(
    authenticated_client, employee_user
):
    response = get_company_report(authenticated_client, employee_user)
    assert response.status_code == 403


@pytest.mark.django_db
def test_company_report_hr_admin_scoped_to_own_company(
    authenticated_client, hr_user, other_employee, other_device, base_dt
):
    """HR Admin company report does not include other company employees."""
    CheckinRecord.objects.create(
        device_binding=other_device, log_type="IN",
        timestamp_gps=base_dt,
        timestamp_device=base_dt,
        gps_lat_smoothed=Decimal("3.848000"),
        gps_lng_smoothed=Decimal("11.502000"),
        gps_accuracy_metres=10, wifi_band="UNAVAILABLE", biometric_passed=True,
    )
    response = get_company_report(authenticated_client, hr_user)
    assert response.status_code == 200
    employee_ids = [e["erpnext_employee_id"] for e in response.data["employees"]]
    assert other_employee.erpnext_employee_id not in employee_ids


@pytest.mark.django_db
def test_company_report_super_admin_requires_company_param(
    authenticated_client, super_user
):
    """SUPER_ADMIN without company_id → 400."""
    response = get_company_report(authenticated_client, super_user)
    assert response.status_code == 400


@pytest.mark.django_db
def test_company_report_unauthenticated_returns_401(api_client):
    url = reverse("reports:company-report")
    response = api_client.get(url)
    assert response.status_code == 401


@pytest.mark.django_db
def test_company_report_invalid_date_range_returns_400(
    authenticated_client, hr_user
):
    """date_from after date_to → 400."""
    response = get_company_report(
        authenticated_client, hr_user,
        {"date_from": "2026-05-31", "date_to": "2026-05-01"},
    )
    assert response.status_code == 400