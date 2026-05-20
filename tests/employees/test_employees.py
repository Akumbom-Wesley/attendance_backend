"""
TDD — Employee Read Endpoints
GET /api/v1/employees/        — list
GET /api/v1/employees/{id}/   — retrieve

Rules:
- SUPER_ADMIN sees all employees across all companies
- HR_ADMIN sees only employees in their own company
- EMPLOYEE cannot access these endpoints
- Unauthenticated → 401
"""

import pytest
from django.urls import reverse

from tests.factories.user_factory import UserFactory
from tests.factories.company_factory import CompanyFactory
from tests.factories.employee_factory import EmployeeFactory


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def company_a(db):
    return CompanyFactory(erpnext_doc_name="CompanyA", name="Company A")


@pytest.fixture
def company_b(db):
    return CompanyFactory(erpnext_doc_name="CompanyB", name="Company B")


@pytest.fixture
def super_admin(db):
    return UserFactory(role="SUPER_ADMIN")


@pytest.fixture
def hr_admin_a(db, company_a):
    return UserFactory(role="HR_ADMIN", company=company_a)


@pytest.fixture
def hr_admin_b(db, company_b):
    return UserFactory(role="HR_ADMIN", company=company_b)


@pytest.fixture
def employee_user(db, company_a):
    return UserFactory(role="EMPLOYEE", company=company_a)


@pytest.fixture
def employees_company_a(db, company_a):
    return EmployeeFactory.create_batch(3, company=company_a)


@pytest.fixture
def employees_company_b(db, company_b):
    return EmployeeFactory.create_batch(2, company=company_b)


# ------------------------------------------------------------------ #
#  List employees                                                      #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_super_admin_can_list_all_employees(
    authenticated_client, super_admin, employees_company_a, employees_company_b
):
    """SUPER_ADMIN sees employees from all companies."""
    client = authenticated_client(super_admin)
    url = reverse("employees:employee-list")
    response = client.get(url)
    assert response.status_code == 200
    assert len(response.data) == 5


@pytest.mark.django_db
def test_hr_admin_sees_only_own_company_employees(
    authenticated_client, hr_admin_a, employees_company_a, employees_company_b
):
    """HR_ADMIN sees only employees in their company."""
    client = authenticated_client(hr_admin_a)
    url = reverse("employees:employee-list")
    response = client.get(url)
    assert response.status_code == 200
    assert len(response.data) == 3


@pytest.mark.django_db
def test_hr_admin_cannot_see_other_company_employees(
    authenticated_client, hr_admin_b, employees_company_a
):
    """HR_ADMIN from company B cannot see company A employees."""
    client = authenticated_client(hr_admin_b)
    url = reverse("employees:employee-list")
    response = client.get(url)
    assert response.status_code == 200
    assert len(response.data) == 0


@pytest.mark.django_db
def test_employee_cannot_list_employees(
    authenticated_client, employee_user
):
    """EMPLOYEE role cannot access employee list → 403."""
    client = authenticated_client(employee_user)
    url = reverse("employees:employee-list")
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_unauthenticated_cannot_list_employees(api_client):
    """Unauthenticated request → 401."""
    url = reverse("employees:employee-list")
    response = api_client.get(url)
    assert response.status_code == 401


# ------------------------------------------------------------------ #
#  Retrieve employee                                                   #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_super_admin_can_retrieve_any_employee(
    authenticated_client, super_admin, employees_company_a
):
    """SUPER_ADMIN can retrieve any employee."""
    client = authenticated_client(super_admin)
    emp = employees_company_a[0]
    url = reverse("employees:employee-detail", kwargs={"pk": emp.pk})
    response = client.get(url)
    assert response.status_code == 200
    assert response.data["erpnext_employee_id"] == emp.erpnext_employee_id


@pytest.mark.django_db
def test_hr_admin_can_retrieve_own_company_employee(
    authenticated_client, hr_admin_a, employees_company_a
):
    """HR_ADMIN can retrieve an employee from their company."""
    client = authenticated_client(hr_admin_a)
    emp = employees_company_a[0]
    url = reverse("employees:employee-detail", kwargs={"pk": emp.pk})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_hr_admin_cannot_retrieve_other_company_employee(
    authenticated_client, hr_admin_b, employees_company_a
):
    """HR_ADMIN cannot retrieve employee from another company → 404."""
    client = authenticated_client(hr_admin_b)
    emp = employees_company_a[0]
    url = reverse("employees:employee-detail", kwargs={"pk": emp.pk})
    response = client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_employee_cannot_retrieve_employee(
    authenticated_client, employee_user, employees_company_a
):
    """EMPLOYEE role cannot retrieve employee records → 403."""
    client = authenticated_client(employee_user)
    emp = employees_company_a[0]
    url = reverse("employees:employee-detail", kwargs={"pk": emp.pk})
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_retrieve_nonexistent_employee_returns_404(
    authenticated_client, super_admin
):
    """Retrieving a non-existent employee → 404."""
    client = authenticated_client(super_admin)
    url = reverse("employees:employee-detail", kwargs={"pk": 99999})
    response = client.get(url)
    assert response.status_code == 404


# ------------------------------------------------------------------ #
#  Response shape                                                      #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_employee_response_contains_expected_fields(
    authenticated_client, super_admin, employees_company_a
):
    """Employee response contains all expected fields."""
    client = authenticated_client(super_admin)
    emp = employees_company_a[0]
    url = reverse("employees:employee-detail", kwargs={"pk": emp.pk})
    response = client.get(url)
    assert response.status_code == 200
    for field in ["id", "erpnext_employee_id", "full_name", "email", "department", "is_active", "company"]:
        assert field in response.data