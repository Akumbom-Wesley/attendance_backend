"""
TDD — Employee Status Endpoints
GET  /api/v1/employees/{id}/status/   — get current status
POST /api/v1/employees/{id}/status/   — change status
"""

import pytest
from django.urls import reverse

from apps.employees.models import EmployeeStatus
from tests.factories.company_factory import CompanyFactory
from tests.factories.user_factory import UserFactory
from tests.factories.employee_factory import EmployeeFactory


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
def hr_admin(db, company):
    return UserFactory(role="HR_ADMIN", company=company)


@pytest.fixture
def super_admin(db):
    return UserFactory(role="SUPER_ADMIN")


@pytest.fixture
def employee_user(employee):
    return employee.user


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def get_status_url(employee_id):
    return reverse("employees:employee-status", kwargs={"pk": employee_id})


def get_status(authenticated_client, user, employee_id):
    client = authenticated_client(user)
    return client.get(get_status_url(employee_id))


def post_status(authenticated_client, user, employee_id, payload):
    client = authenticated_client(user)
    return client.post(get_status_url(employee_id), payload, format="json")


# ------------------------------------------------------------------ #
#  GET — current status                                                #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_get_status_no_history_returns_null(
    authenticated_client, employee_user, employee
):
    """Employee with no status history → status is null."""
    response = get_status(authenticated_client, employee_user, employee.id)
    assert response.status_code == 200
    assert response.data["status"] is None


@pytest.mark.django_db
def test_get_status_returns_latest(
    authenticated_client, employee_user, employee
):
    """Returns the most recent status."""
    EmployeeStatus.objects.create(employee=employee, status="present")
    EmployeeStatus.objects.create(employee=employee, status="break")
    response = get_status(authenticated_client, employee_user, employee.id)
    assert response.status_code == 200
    assert response.data["status"] == "break"


@pytest.mark.django_db
def test_hr_admin_can_get_employee_status(
    authenticated_client, hr_admin, employee
):
    """HR_ADMIN can view status of employee in same company."""
    EmployeeStatus.objects.create(employee=employee, status="present")
    response = get_status(authenticated_client, hr_admin, employee.id)
    assert response.status_code == 200
    assert response.data["status"] == "present"


@pytest.mark.django_db
def test_super_admin_can_get_employee_status(
    authenticated_client, super_admin, employee
):
    """SUPER_ADMIN can view any employee status."""
    EmployeeStatus.objects.create(employee=employee, status="present")
    response = get_status(authenticated_client, super_admin, employee.id)
    assert response.status_code == 200


@pytest.mark.django_db
def test_get_status_unauthenticated_returns_401(api_client, employee):
    """Unauthenticated request → 401."""
    response = api_client.get(get_status_url(employee.id))
    assert response.status_code == 401


@pytest.mark.django_db
def test_get_status_wrong_employee_returns_404(
    authenticated_client, employee_user
):
    """Non-existent employee id → 404."""
    response = get_status(authenticated_client, employee_user, 99999)
    assert response.status_code == 404


# ------------------------------------------------------------------ #
#  POST — change status                                                #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_employee_can_change_own_status(
    authenticated_client, employee_user, employee
):
    """Employee can update their own status."""
    response = post_status(
        authenticated_client, employee_user, employee.id, {"status": "break"}
    )
    assert response.status_code == 201
    assert EmployeeStatus.objects.filter(employee=employee, status="break").exists()


@pytest.mark.django_db
def test_hr_admin_can_change_employee_status(
    authenticated_client, hr_admin, employee
):
    """HR_ADMIN can change status of employee in same company."""
    response = post_status(
        authenticated_client, hr_admin, employee.id, {"status": "errand"}
    )
    assert response.status_code == 201
    assert EmployeeStatus.objects.filter(employee=employee, status="errand").exists()


@pytest.mark.django_db
def test_invalid_status_returns_400(
    authenticated_client, employee_user, employee
):
    """Invalid status value → 400."""
    response = post_status(
        authenticated_client, employee_user, employee.id, {"status": "flying"}
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_missing_status_returns_400(
    authenticated_client, employee_user, employee
):
    """Missing status field → 400."""
    response = post_status(
        authenticated_client, employee_user, employee.id, {}
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_post_status_unauthenticated_returns_401(api_client, employee):
    """Unauthenticated request → 401."""
    response = api_client.post(
        get_status_url(employee.id), {"status": "present"}, format="json"
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_post_status_wrong_employee_returns_404(
    authenticated_client, employee_user
):
    """Non-existent employee id → 404."""
    response = post_status(
        authenticated_client, employee_user, 99999, {"status": "present"}
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_status_change_creates_new_record_not_update(
    authenticated_client, employee_user, employee
):
    """Each status change creates a new EmployeeStatus row — never updates."""
    post_status(authenticated_client, employee_user, employee.id, {"status": "present"})
    post_status(authenticated_client, employee_user, employee.id, {"status": "break"})
    assert EmployeeStatus.objects.filter(employee=employee).count() == 2


@pytest.mark.django_db
def test_get_status_response_includes_changed_at(
    authenticated_client, employee_user, employee
):
    """Response includes changed_at timestamp."""
    EmployeeStatus.objects.create(employee=employee, status="present")
    response = get_status(authenticated_client, employee_user, employee.id)
    assert response.status_code == 200
    assert "changed_at" in response.data