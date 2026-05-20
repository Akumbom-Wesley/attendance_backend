"""
TDD — Manual Resync Endpoints
POST /api/v1/sync/erpnext/employee/{erpnext_employee_id}/
POST /api/v1/sync/erpnext/company/{erpnext_doc_name}/

Only HR_ADMIN and SUPER_ADMIN can trigger resyncs.
Uses `responses` library to mock ERPNext HTTP calls.
"""

import pytest
import responses as responses_lib
from responses import GET
from django.urls import reverse

from apps.companies.models import Company
from apps.employees.models import Employee
from tests.factories.company_factory import CompanyFactory
from tests.factories.user_factory import UserFactory


ERPNEXT_BASE = "https://erp.nchemty.com"


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def super_admin(db):
    return UserFactory(role="SUPER_ADMIN")


@pytest.fixture
def hr_admin(db):
    return UserFactory(role="HR_ADMIN")


@pytest.fixture
def employee_user(db):
    return UserFactory(role="EMPLOYEE")


@pytest.fixture
def company(db):
    return CompanyFactory(erpnext_doc_name="Nchemty", name="Nchemty")


@pytest.fixture
def mock_company_response(company):
    """Mock ERPNext single Company fetch."""
    responses_lib.add(
        GET,
        f"{ERPNEXT_BASE}/api/resource/Company/{company.erpnext_doc_name}",
        json={"data": {
            "name": company.erpnext_doc_name,
            "company_name": "Nchemty Updated",
        }},
        status=200,
    )


@pytest.fixture
def mock_employee_response(company):
    """Mock ERPNext single Employee fetch."""
    responses_lib.add(
        GET,
        f"{ERPNEXT_BASE}/api/resource/Employee/HR-EMP-00004",
        json={"data": {
            "name": "HR-EMP-00004",
            "employee_name": "Akumbom Wesley",
            "company": company.erpnext_doc_name,
            "department": "IT - NCH",
            "company_email": "wesley.akumbom@se-tl.com",
            "status": "Active",
        }},
        status=200,
    )


# ------------------------------------------------------------------ #
#  Company resync tests                                                #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
@responses_lib.activate
def test_company_resync_returns_200(authenticated_client, super_admin, company, mock_company_response):
    """SUPER_ADMIN can trigger a company resync → 200."""
    client = authenticated_client(super_admin)
    url = reverse("sync:resync_company", kwargs={"erpnext_doc_name": company.erpnext_doc_name})
    response = client.post(url)
    assert response.status_code == 200


@pytest.mark.django_db
@responses_lib.activate
def test_company_resync_updates_local_record(authenticated_client, super_admin, company, mock_company_response):
    """Company resync updates the local Company record from ERPNext."""
    client = authenticated_client(super_admin)
    url = reverse("sync:resync_company", kwargs={"erpnext_doc_name": company.erpnext_doc_name})
    client.post(url)

    company.refresh_from_db()
    assert company.name == "Nchemty Updated"


@pytest.mark.django_db
@responses_lib.activate
def test_company_resync_allowed_for_hr_admin(authenticated_client, hr_admin, company, mock_company_response):
    """HR_ADMIN can also trigger a company resync → 200."""
    client = authenticated_client(hr_admin)
    url = reverse("sync:resync_company", kwargs={"erpnext_doc_name": company.erpnext_doc_name})
    response = client.post(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_company_resync_forbidden_for_employee(authenticated_client, employee_user, company):
    """EMPLOYEE cannot trigger a company resync → 403."""
    client = authenticated_client(employee_user)
    url = reverse("sync:resync_company", kwargs={"erpnext_doc_name": company.erpnext_doc_name})
    response = client.post(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_company_resync_forbidden_for_unauthenticated(api_client, company):
    """Unauthenticated request → 401."""
    url = reverse("sync:resync_company", kwargs={"erpnext_doc_name": company.erpnext_doc_name})
    response = api_client.post(url)
    assert response.status_code == 401


# ------------------------------------------------------------------ #
#  Employee resync tests                                               #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
@responses_lib.activate
def test_employee_resync_returns_200(authenticated_client, super_admin, company, mock_employee_response):
    """SUPER_ADMIN can trigger an employee resync → 200."""
    client = authenticated_client(super_admin)
    url = reverse("sync:resync_employee", kwargs={"erpnext_employee_id": "HR-EMP-00004"})
    response = client.post(url)
    assert response.status_code == 200


@pytest.mark.django_db
@responses_lib.activate
def test_employee_resync_creates_employee(authenticated_client, super_admin, company, mock_employee_response):
    """Employee resync creates local Employee if it doesn't exist."""
    assert Employee.objects.count() == 0
    client = authenticated_client(super_admin)
    url = reverse("sync:resync_employee", kwargs={"erpnext_employee_id": "HR-EMP-00004"})
    client.post(url)
    assert Employee.objects.count() == 1


@pytest.mark.django_db
@responses_lib.activate
def test_employee_resync_allowed_for_hr_admin(authenticated_client, hr_admin, company, mock_employee_response):
    """HR_ADMIN can trigger an employee resync → 200."""
    client = authenticated_client(hr_admin)
    url = reverse("sync:resync_employee", kwargs={"erpnext_employee_id": "HR-EMP-00004"})
    response = client.post(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_employee_resync_forbidden_for_employee(authenticated_client, employee_user, company):
    """EMPLOYEE cannot trigger an employee resync → 403."""
    client = authenticated_client(employee_user)
    url = reverse("sync:resync_employee", kwargs={"erpnext_employee_id": "HR-EMP-00004"})
    response = client.post(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_employee_resync_forbidden_for_unauthenticated(api_client):
    """Unauthenticated request → 401."""
    url = reverse("sync:resync_employee", kwargs={"erpnext_employee_id": "HR-EMP-00004"})
    response = api_client.post(url)
    assert response.status_code == 401


@pytest.mark.django_db
@responses_lib.activate
def test_employee_resync_returns_404_if_not_in_erpnext(authenticated_client, super_admin, company):
    """If ERPNext returns 404 for the employee → our endpoint returns 404."""
    responses_lib.add(
        GET,
        f"{ERPNEXT_BASE}/api/resource/Employee/HR-EMP-99999",
        json={"exc_type": "DoesNotExist"},
        status=404,
    )
    client = authenticated_client(super_admin)
    url = reverse("sync:resync_employee", kwargs={"erpnext_employee_id": "HR-EMP-99999"})
    response = client.post(url)
    assert response.status_code == 404