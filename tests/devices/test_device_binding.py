# tests/devices/test_device_binding.py
"""
TDD — Device Binding
Sprint 8

Endpoints:
  POST /api/v1/devices/register/     — EMPLOYEE self-register device
  GET  /api/v1/devices/me/           — EMPLOYEE view own binding
  GET  /api/v1/devices/              — HR_ADMIN, SUPER_ADMIN list bindings
  POST /api/v1/devices/{id}/unbind/  — HR_ADMIN, SUPER_ADMIN unbind device

Rules:
  - One active binding per employee (1:1)
  - Employee can only register if no active binding exists
  - Only HR_ADMIN / SUPER_ADMIN can unbind
  - HR_ADMIN scoped to own company
  - After unbind, employee can re-register
"""

import pytest
from django.urls import reverse

from apps.devices.models import DeviceBinding
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
def register_payload():
    return {
        "device_unique_id": "DEVICE-ABC-001",
        "attendance_device_id": "Samsung Galaxy S24 - John",
    }


@pytest.fixture
def active_binding(db, employee):
    return DeviceBindingFactory(employee=employee, is_active=True)


@pytest.fixture
def other_active_binding(db, other_employee):
    return DeviceBindingFactory(employee=other_employee, is_active=True)


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def register_device(authenticated_client, user, payload):
    client = authenticated_client(user)
    url = reverse("devices:register")
    return client.post(url, payload, format="json")


def get_my_binding(authenticated_client, user):
    client = authenticated_client(user)
    url = reverse("devices:me")
    return client.get(url)


def list_bindings(authenticated_client, user):
    client = authenticated_client(user)
    url = reverse("devices:list")
    return client.get(url)


def unbind_device(authenticated_client, user, binding_id):
    client = authenticated_client(user)
    url = reverse("devices:unbind", kwargs={"pk": binding_id})
    return client.post(url)


# ------------------------------------------------------------------ #
#  Register Device                                                     #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_register_device_returns_201(
    authenticated_client, employee_user, register_payload
):
    response = register_device(authenticated_client, employee_user, register_payload)
    assert response.status_code == 201


@pytest.mark.django_db
def test_register_device_creates_binding(
    authenticated_client, employee_user, employee, register_payload
):
    register_device(authenticated_client, employee_user, register_payload)
    assert DeviceBinding.objects.filter(
        employee=employee,
        device_unique_id=register_payload["device_unique_id"],
        is_active=True,
    ).exists()


@pytest.mark.django_db
def test_register_device_already_bound_returns_409(
    authenticated_client, employee_user, active_binding, register_payload
):
    response = register_device(authenticated_client, employee_user, register_payload)
    assert response.status_code == 409


@pytest.mark.django_db
def test_register_device_unauthenticated_returns_401(api_client, register_payload):
    url = reverse("devices:register")
    response = api_client.post(url, register_payload, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_register_device_hr_admin_returns_403(
    authenticated_client, hr_user, register_payload
):
    response = register_device(authenticated_client, hr_user, register_payload)
    assert response.status_code == 403


# ------------------------------------------------------------------ #
#  Me — own binding                                                    #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_me_returns_own_binding(
    authenticated_client, employee_user, active_binding
):
    response = get_my_binding(authenticated_client, employee_user)
    assert response.status_code == 200
    assert response.data["device_unique_id"] == active_binding.device_unique_id


@pytest.mark.django_db
def test_me_no_binding_returns_404(
    authenticated_client, employee_user
):
    response = get_my_binding(authenticated_client, employee_user)
    assert response.status_code == 404


@pytest.mark.django_db
def test_me_unauthenticated_returns_401(api_client):
    url = reverse("devices:me")
    response = api_client.get(url)
    assert response.status_code == 401


# ------------------------------------------------------------------ #
#  List Bindings                                                       #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_list_bindings_hr_admin_scoped_to_company(
    authenticated_client, hr_user, active_binding, other_active_binding
):
    response = list_bindings(authenticated_client, hr_user)
    assert response.status_code == 200
    device_ids = [b["device_unique_id"] for b in response.data]
    assert active_binding.device_unique_id in device_ids
    assert other_active_binding.device_unique_id not in device_ids


@pytest.mark.django_db
def test_list_bindings_super_admin_sees_all(
    authenticated_client, super_user, active_binding, other_active_binding
):
    response = list_bindings(authenticated_client, super_user)
    assert response.status_code == 200
    device_ids = [b["device_unique_id"] for b in response.data]
    assert active_binding.device_unique_id in device_ids
    assert other_active_binding.device_unique_id in device_ids


@pytest.mark.django_db
def test_list_bindings_employee_returns_403(
    authenticated_client, employee_user
):
    response = list_bindings(authenticated_client, employee_user)
    assert response.status_code == 403


# ------------------------------------------------------------------ #
#  Unbind                                                              #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_unbind_returns_200(
    authenticated_client, hr_user, active_binding
):
    response = unbind_device(authenticated_client, hr_user, active_binding.id)
    assert response.status_code == 200


@pytest.mark.django_db
def test_unbind_sets_is_active_false(
    authenticated_client, hr_user, active_binding
):
    unbind_device(authenticated_client, hr_user, active_binding.id)
    active_binding.refresh_from_db()
    assert active_binding.is_active is False


@pytest.mark.django_db
def test_unbind_sets_unbound_at(
    authenticated_client, hr_user, active_binding
):
    unbind_device(authenticated_client, hr_user, active_binding.id)
    active_binding.refresh_from_db()
    assert active_binding.unbound_at is not None


@pytest.mark.django_db
def test_unbind_employee_returns_403(
    authenticated_client, employee_user, active_binding
):
    response = unbind_device(authenticated_client, employee_user, active_binding.id)
    assert response.status_code == 403


@pytest.mark.django_db
def test_unbind_other_company_returns_404(
    authenticated_client, hr_user, other_active_binding
):
    response = unbind_device(authenticated_client, hr_user, other_active_binding.id)
    assert response.status_code == 404


@pytest.mark.django_db
def test_register_after_unbind_creates_new_binding(
    authenticated_client, employee_user, employee, hr_user, active_binding, register_payload
):
    # HR Admin unbinds first
    unbind_device(authenticated_client, hr_user, active_binding.id)

    # Employee re-registers
    response = register_device(authenticated_client, employee_user, register_payload)
    assert response.status_code == 201
    assert DeviceBinding.objects.filter(
        employee=employee,
        is_active=True,
    ).count() == 1