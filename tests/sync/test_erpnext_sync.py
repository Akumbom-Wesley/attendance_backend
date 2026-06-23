"""
TDD — ERPNext Bulk Import Service
Red → Green → Refactor

Uses `responses` library to mock all HTTP calls to ERPNext.
No real network calls in tests.
"""

import pytest
import responses as responses_lib
from responses import GET

from apps.sync.services import ERPNextSyncService
from apps.companies.models import Company
from apps.employees.models import Employee
from apps.accounts.models import User


ERPNEXT_BASE = "https://tarh.work"


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def service():
    return ERPNextSyncService()


@pytest.fixture
def company_payload():
    """Simulates one Company record returned by ERPNext list endpoint."""
    return {"name": "Nchemty", "company_name": "Nchemty"}


@pytest.fixture
def employee_payload():
    """Simulates one Employee record returned by ERPNext list endpoint."""
    return {
        "name": "HR-EMP-00004",
        "employee_name": "Akumbom Wesley",
        "company": "Nchemty",
        "department": "IT - NCH",
        "company_email": "wesley.akumbom@se-tl.com",
        "status": "Active",
    }


@pytest.fixture
def employee_payload_no_email():
    """Employee with no company_email — tests nullable email handling."""
    return {
        "name": "HR-EMP-00003",
        "employee_name": "Ayuk Blaisius",
        "company": "Nchemty",
        "department": "IT - NCH",
        "company_email": None,
        "status": "Active",
    }


@pytest.fixture
def employee_payload_inactive():
    """Employee with status Left — maps to is_active=False."""
    return {
        "name": "HR-EMP-00010",
        "employee_name": "John Doe",
        "company": "Nchemty",
        "department": None,
        "company_email": None,
        "status": "Left",
    }


# ------------------------------------------------------------------ #
#  sync_company tests                                                  #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_sync_company_creates_new_company(service, company_payload):
    """sync_company() creates a Company record that doesn't exist yet."""
    assert Company.objects.count() == 0

    company = service.sync_company(company_payload)

    assert Company.objects.count() == 1
    assert company.erpnext_doc_name == "Nchemty"
    assert company.name == "Nchemty"
    assert company.is_active is True


@pytest.mark.django_db
def test_sync_company_updates_existing_company(service, company_payload):
    """sync_company() updates a Company that already exists (idempotent)."""
    Company.objects.create(
        erpnext_doc_name="Nchemty",
        name="Old Name",
        is_active=False,
    )

    company = service.sync_company(company_payload)

    assert Company.objects.count() == 1
    assert company.name == "Nchemty"
    assert company.is_active is True


@pytest.mark.django_db
def test_sync_company_is_idempotent(service, company_payload):
    """Calling sync_company() twice does not create duplicate records."""
    service.sync_company(company_payload)
    service.sync_company(company_payload)

    assert Company.objects.count() == 1


# ------------------------------------------------------------------ #
#  sync_employee tests                                                 #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_sync_employee_creates_user_and_employee(service, company_payload, employee_payload):
    """sync_employee() creates both a User and an Employee profile."""
    service.sync_company(company_payload)

    assert User.objects.count() == 0
    assert Employee.objects.count() == 0

    service.sync_employee(employee_payload)

    assert User.objects.count() == 1
    assert Employee.objects.count() == 1


@pytest.mark.django_db
def test_sync_employee_correct_fields(service, company_payload, employee_payload):
    """Employee record has correct field values after sync."""
    service.sync_company(company_payload)
    service.sync_employee(employee_payload)

    emp = Employee.objects.get(erpnext_employee_id="HR-EMP-00004")
    assert emp.full_name == "Akumbom Wesley"
    assert emp.department == "IT - NCH"
    assert emp.email == "wesley.akumbom@se-tl.com"
    assert emp.is_active is True
    assert emp.company.erpnext_doc_name == "Nchemty"


@pytest.mark.django_db
def test_sync_employee_handles_null_email(service, company_payload, employee_payload_no_email):
    """sync_employee() handles null company_email without error."""
    service.sync_company(company_payload)
    service.sync_employee(employee_payload_no_email)

    emp = Employee.objects.get(erpnext_employee_id="HR-EMP-00003")
    assert emp.email == ""


@pytest.mark.django_db
def test_sync_employee_inactive_when_status_left(service, company_payload, employee_payload_inactive):
    """Employee with ERPNext status 'Left' maps to is_active=False."""
    service.sync_company(company_payload)
    service.sync_employee(employee_payload_inactive)

    emp = Employee.objects.get(erpnext_employee_id="HR-EMP-00010")
    assert emp.is_active is False


@pytest.mark.django_db
def test_sync_employee_is_idempotent(service, company_payload, employee_payload):
    """Calling sync_employee() twice does not create duplicate records."""
    service.sync_company(company_payload)
    service.sync_employee(employee_payload)
    service.sync_employee(employee_payload)

    assert Employee.objects.count() == 1
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_sync_employee_updates_existing(service, company_payload, employee_payload):
    """sync_employee() updates an existing Employee record."""
    service.sync_company(company_payload)
    service.sync_employee(employee_payload)

    updated_payload = {**employee_payload, "employee_name": "Akumbom Wesley Updated"}
    service.sync_employee(updated_payload)

    emp = Employee.objects.get(erpnext_employee_id="HR-EMP-00004")
    assert emp.full_name == "Akumbom Wesley Updated"
    assert Employee.objects.count() == 1


@pytest.mark.django_db
def test_sync_employee_skips_unknown_company(service, employee_payload):
    """sync_employee() raises ValueError if company doesn't exist locally."""
    with pytest.raises(ValueError, match="Company 'Nchemty' not found"):
        service.sync_employee(employee_payload)


# ------------------------------------------------------------------ #
#  bulk_import tests (mocked HTTP)                                     #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
@responses_lib.activate
def test_bulk_import_creates_companies_and_employees(service):
    """bulk_import() fetches all pages and creates Company + Employee records."""

    # Mock company list — one page, then empty
    responses_lib.add(
        GET,
        f"{ERPNEXT_BASE}/api/resource/Company",
        json={"data": [{"name": "Nchemty", "company_name": "Nchemty"}]},
        status=200,
    )
    responses_lib.add(
        GET,
        f"{ERPNEXT_BASE}/api/resource/Company",
        json={"data": []},
        status=200,
    )

    # Mock employee list — one page, then empty
    responses_lib.add(
        GET,
        f"{ERPNEXT_BASE}/api/resource/Employee",
        json={"data": [
            {
                "name": "HR-EMP-00004",
                "employee_name": "Akumbom Wesley",
                "company": "Nchemty",
                "department": "IT - NCH",
                "company_email": "wesley.akumbom@se-tl.com",
                "status": "Active",
            }
        ]},
        status=200,
    )
    responses_lib.add(
        GET,
        f"{ERPNEXT_BASE}/api/resource/Employee",
        json={"data": []},
        status=200,
    )

    result = service.bulk_import()

    assert Company.objects.count() == 1
    assert Employee.objects.count() == 1
    assert result["companies_synced"] == 1
    assert result["employees_synced"] == 1


@pytest.mark.django_db
@responses_lib.activate
def test_bulk_import_returns_summary(service):
    """bulk_import() returns a dict with counts of synced records."""

    responses_lib.add(GET, f"{ERPNEXT_BASE}/api/resource/Company",
        json={"data": [{"name": "Nchemty", "company_name": "Nchemty"}]}, status=200)
    responses_lib.add(GET, f"{ERPNEXT_BASE}/api/resource/Company",
        json={"data": []}, status=200)
    responses_lib.add(GET, f"{ERPNEXT_BASE}/api/resource/Employee",
        json={"data": []}, status=200)

    result = service.bulk_import()

    assert "companies_synced" in result
    assert "employees_synced" in result
    assert result["companies_synced"] == 1
    assert result["employees_synced"] == 0