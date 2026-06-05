"""
TDD — Push CheckinRecord to ERPNext as Employee Checkin
Task: apps/checkins/tasks.push_checkin_to_erpnext

Strategy:
- Every passing CheckinRecord (IN or OUT) is pushed to ERPNext
  as an Employee Checkin doc via POST /api/resource/Employee Checkin
- On success: CheckinRecord.is_synced = True
- On failure: retry 3x with 60s backoff
- Duplicate push guard: skip if already is_synced=True
- Timezone: timestamp_gps converted to Africa/Douala before sending
"""

import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone
from datetime import datetime
import pytz

from apps.checkins.tasks import push_checkin_to_erpnext
from apps.checkins.models import CheckinRecord
from tests.factories.company_factory import CompanyFactory
from tests.factories.user_factory import UserFactory
from tests.factories.employee_factory import EmployeeFactory
from tests.factories.device_factory import DeviceBindingFactory
from tests.factories.checkin_factory import CheckinRecordFactory


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def company(db):
    return CompanyFactory()


@pytest.fixture
def employee(db, company):
    user = UserFactory(role="EMPLOYEE", company=company)
    return EmployeeFactory(user=user, company=company)


@pytest.fixture
def device(db, employee):
    return DeviceBindingFactory(employee=employee, is_active=True)


@pytest.fixture
def checkin_in(db, device):
    return CheckinRecordFactory(
        device_binding=device,
        log_type="IN",
        is_synced=False,
    )


@pytest.fixture
def checkin_out(db, device):
    return CheckinRecordFactory(
        device_binding=device,
        log_type="OUT",
        is_synced=False,
    )


@pytest.fixture
def checkin_already_synced(db, device):
    return CheckinRecordFactory(
        device_binding=device,
        log_type="IN",
        is_synced=True,
    )


# ------------------------------------------------------------------ #
#  Success cases                                                       #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_push_in_checkin_calls_erpnext(checkin_in):
    """IN checkin → POST to ERPNext Employee Checkin with correct fields."""
    with patch("apps.checkins.tasks.ERPNextClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.create_employee_checkin.return_value = {"name": "EMP-CKIN-001"}

        push_checkin_to_erpnext(checkin_in.id)

        mock_instance.create_employee_checkin.assert_called_once()
        call_args = mock_instance.create_employee_checkin.call_args[0][0]
        assert call_args["employee"] == checkin_in.device_binding.employee.erpnext_employee_id
        assert call_args["log_type"] == "IN"
        assert call_args["skip_auto_attendance"] == 0


@pytest.mark.django_db
def test_push_out_checkin_calls_erpnext(checkin_out):
    """OUT checkin → POST to ERPNext with log_type=OUT."""
    with patch("apps.checkins.tasks.ERPNextClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.create_employee_checkin.return_value = {"name": "EMP-CKIN-002"}

        push_checkin_to_erpnext(checkin_out.id)

        call_args = mock_instance.create_employee_checkin.call_args[0][0]
        assert call_args["log_type"] == "OUT"


@pytest.mark.django_db
def test_push_sets_is_synced_true_on_success(checkin_in):
    """Successful push → CheckinRecord.is_synced set to True."""
    with patch("apps.checkins.tasks.ERPNextClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.create_employee_checkin.return_value = {"name": "EMP-CKIN-001"}

        push_checkin_to_erpnext(checkin_in.id)

        checkin_in.refresh_from_db()
        assert checkin_in.is_synced is True


@pytest.mark.django_db
def test_push_sends_time_in_douala_timezone(checkin_in):
    """timestamp_gps is converted to Africa/Douala before sending."""
    with patch("apps.checkins.tasks.ERPNextClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.create_employee_checkin.return_value = {"name": "EMP-CKIN-001"}

        push_checkin_to_erpnext(checkin_in.id)

        call_args = mock_instance.create_employee_checkin.call_args[0][0]
        douala_tz = pytz.timezone("Africa/Douala")
        expected_time = checkin_in.timestamp_gps.astimezone(douala_tz).strftime("%Y-%m-%d %H:%M:%S")
        assert call_args["time"] == expected_time


@pytest.mark.django_db
def test_push_sends_device_id(checkin_in):
    """device_unique_id is sent as device_id field."""
    with patch("apps.checkins.tasks.ERPNextClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.create_employee_checkin.return_value = {"name": "EMP-CKIN-001"}

        push_checkin_to_erpnext(checkin_in.id)

        call_args = mock_instance.create_employee_checkin.call_args[0][0]
        assert call_args["device_id"] == checkin_in.device_binding.device_unique_id


# ------------------------------------------------------------------ #
#  Duplicate guard                                                     #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_already_synced_checkin_is_skipped(checkin_already_synced):
    """is_synced=True → ERPNext not called, task exits silently."""
    with patch("apps.checkins.tasks.ERPNextClient") as MockClient:
        mock_instance = MockClient.return_value

        push_checkin_to_erpnext(checkin_already_synced.id)

        mock_instance.create_employee_checkin.assert_not_called()


# ------------------------------------------------------------------ #
#  Failure and retry                                                   #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_erpnext_failure_does_not_set_is_synced(checkin_in):
    """ERPNext error → is_synced stays False."""
    with patch("apps.checkins.tasks.ERPNextClient") as MockClient:
        from apps.sync.erpnext_client import ERPNextAPIError
        mock_instance = MockClient.return_value
        mock_instance.create_employee_checkin.side_effect = ERPNextAPIError("500 error")

        with pytest.raises(ERPNextAPIError):
            push_checkin_to_erpnext(checkin_in.id)

        checkin_in.refresh_from_db()
        assert checkin_in.is_synced is False


@pytest.mark.django_db
def test_nonexistent_checkin_record_raises(db):
    """Non-existent checkin_record_id → CheckinRecord.DoesNotExist raised."""
    with pytest.raises(CheckinRecord.DoesNotExist):
        push_checkin_to_erpnext(99999)