import hashlib
import hmac
import base64
import json
import secrets
import pytest
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APIClient

from pytest_factoryboy import register
from tests.factories.user_factory import UserFactory
from tests.factories.company_factory import CompanyFactory
from tests.factories.employee_factory import EmployeeFactory
from tests.factories.device_factory import DeviceBindingFactory
from tests.factories.checkin_factory import CheckinRecordFactory

from apps.accounts.models import User

register(UserFactory)
register(CompanyFactory)
register(EmployeeFactory)
register(DeviceBindingFactory)
register(CheckinRecordFactory)


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_client():
    def _authenticated_client(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client
    return _authenticated_client


@pytest.fixture(autouse=True)
def flush_cache():
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# Role-based user fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def company(db):
    return CompanyFactory(
        erpnext_doc_name="Sure-Engineering-001",
        name="Sure Engineering and Technologies ltd",
        webhook_secret=secrets.token_hex(32),
        is_active=True,
    )


@pytest.fixture
def super_admin_user(db):
    return UserFactory(
        role=User.Role.SUPER_ADMIN,
        is_onboarded=True,
        company=None,
    )


@pytest.fixture
def hr_admin_user(company):
    return UserFactory(
        role=User.Role.HR_ADMIN,
        is_onboarded=True,
        company=company,
    )


@pytest.fixture
def employee_user(company):
    return UserFactory(
        role=User.Role.EMPLOYEE,
        is_onboarded=True,
        company=company,
    )


# ---------------------------------------------------------------------------
# Onboarding-specific employee fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def employee_with_email(company):
    """Unboarded employee with a valid email address."""
    user = UserFactory(
        role=User.Role.EMPLOYEE,
        is_onboarded=False,
        company=company,
        onboarding_token="",
        onboarding_token_expires_at=None,
    )
    return EmployeeFactory(
        user=user,
        company=company,
        email=f"emp_{user.username}@example.com",
        is_active=True,
    )


@pytest.fixture
def employee_without_email(company):
    """Employee whose email field is blank (cannot receive onboarding email)."""
    user = UserFactory(
        role=User.Role.EMPLOYEE,
        is_onboarded=False,
        company=company,
        onboarding_token="",
        onboarding_token_expires_at=None,
    )
    emp = EmployeeFactory(
        user=user,
        company=company,
        is_active=True,
    )
    # blank out the email after creation to avoid unique constraint issues
    emp.email = ""
    emp.save()
    user.email = ""
    user.save()
    return emp


@pytest.fixture
def onboarded_employee(company):
    """Employee who has already completed onboarding."""
    user = UserFactory(
        role=User.Role.EMPLOYEE,
        is_onboarded=True,
        company=company,
        onboarding_token="",
        onboarding_token_expires_at=None,
    )
    return EmployeeFactory(
        user=user,
        company=company,
        is_active=True,
    )


@pytest.fixture
def employee_with_pending_token(company):
    """Employee with a valid (non-expired) onboarding token, not yet onboarded."""
    token = secrets.token_urlsafe(32)
    user = UserFactory(
        role=User.Role.EMPLOYEE,
        is_onboarded=False,
        company=company,
        onboarding_token=token,
        onboarding_token_expires_at=timezone.now() + timedelta(hours=24),
    )
    return EmployeeFactory(
        user=user,
        company=company,
        email=f"pending_{user.username}@example.com",
        is_active=True,
    )


@pytest.fixture
def employee_with_expired_token(company):
    """Employee whose onboarding token has expired."""
    token = secrets.token_urlsafe(32)
    user = UserFactory(
        role=User.Role.EMPLOYEE,
        is_onboarded=False,
        company=company,
        onboarding_token=token,
        onboarding_token_expires_at=timezone.now() - timedelta(hours=1),
    )
    return EmployeeFactory(
        user=user,
        company=company,
        email=f"expired_{user.username}@example.com",
        is_active=True,
    )


@pytest.fixture
def multiple_unboarded_employees(company):
    """3 unboarded employees with valid emails, same company."""
    employees = []
    for i in range(3):
        user = UserFactory(
            role=User.Role.EMPLOYEE,
            is_onboarded=False,
            company=company,
            onboarding_token="",
            onboarding_token_expires_at=None,
        )
        emp = EmployeeFactory(
            user=user,
            company=company,
            email=f"bulk_{i}_{user.username}@example.com",
            is_active=True,
        )
        employees.append(emp)
    return employees


@pytest.fixture
def employee_other_company():
    """Employee belonging to a different company (for scoping tests)."""
    other_company = CompanyFactory(
        erpnext_doc_name="Other-Company-001",
        name="Other Company Ltd",
        webhook_secret=secrets.token_hex(32),
        is_active=True,
    )
    user = UserFactory(
        role=User.Role.EMPLOYEE,
        is_onboarded=False,
        company=other_company,
        onboarding_token="",
        onboarding_token_expires_at=None,
    )
    return EmployeeFactory(
        user=user,
        company=other_company,
        email=f"other_{user.username}@example.com",
        is_active=True,
    )


# ---------------------------------------------------------------------------
# Webhook fixtures (Sprint 10 — auto-onboarding via webhook)
# ---------------------------------------------------------------------------

@pytest.fixture
def company_with_secret(company):
    """Returns the company fixture (already has webhook_secret set)."""
    return company


@pytest.fixture
def new_employee_payload(company):
    """Simulates an ERPNext after_insert webhook payload for a brand-new employee."""
    return {
        "doctype": "Employee",
        "name": "HR-EMP-99001",
        "employee_name": "Test New Employee",
        "company_email": "new.employee@example.com",
        "department": "Engineering",
        "status": "Active",
        "company": company.name,
    }


@pytest.fixture
def existing_employee_payload(company, onboarded_employee):
    """Simulates an ERPNext on_update webhook payload for an existing employee."""
    return {
        "doctype": "Employee",
        "name": onboarded_employee.erpnext_employee_id,
        "employee_name": onboarded_employee.full_name,
        "company_email": onboarded_employee.email,
        "department": onboarded_employee.department,
        "status": "Active",
        "company": company.name,
    }


@pytest.fixture
def hmac_headers():
    def _make_headers(raw_bytes, company):
        sig = base64.b64encode(
            hmac.new(
                company.webhook_secret.encode("utf-8"),
                raw_bytes,
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        return {"X-Frappe-Webhook-Signature": sig}
    return _make_headers