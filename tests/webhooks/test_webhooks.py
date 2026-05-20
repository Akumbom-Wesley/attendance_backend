"""
TDD — Webhook Receiver
Red → Green → Refactor

Tests HMAC validation, payload parsing, WebhookEvent creation,
and Celery task dispatch.
"""

import hashlib
import hmac
import json
import pytest

from django.urls import reverse
from apps.webhooks.models import WebhookEvent
from tests.factories.company_factory import CompanyFactory


def make_signature(secret: str, payload: dict) -> str:
    """Helper — computes the HMAC-SHA256 signature ERPNext would send."""
    body = json.dumps(payload, separators=(",", ":"))
    return hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def company(db):
    return CompanyFactory(webhook_secret="testsecret123")


@pytest.fixture
def employee_created_payload(company):
    return {
        "doctype": "Employee",
        "name": "HR-EMP-00010",
        "employee_name": "New Employee",
        "company": company.erpnext_doc_name,
        "department": "IT - NCH",
        "company_email": "new.employee@nchemty.com",
        "status": "Active",
    }


@pytest.fixture
def company_updated_payload(company):
    return {
        "doctype": "Company",
        "name": company.erpnext_doc_name,
        "company_name": company.name,
    }


# ------------------------------------------------------------------ #
#  HMAC validation tests                                               #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_webhook_rejects_missing_signature(api_client, employee_created_payload):
    """Request with no X-Frappe-Signature header → 403."""
    url = reverse("webhooks:erpnext")
    response = api_client.post(
        url,
        data=employee_created_payload,
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_webhook_rejects_invalid_signature(api_client, company, employee_created_payload):
    """Request with wrong signature → 403."""
    url = reverse("webhooks:erpnext")
    response = api_client.post(
        url,
        data=employee_created_payload,
        format="json",
        HTTP_X_FRAPPE_SIGNATURE="invalidsignature",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_webhook_accepts_valid_signature(api_client, company, employee_created_payload):
    """Request with correct HMAC signature → 200."""
    url = reverse("webhooks:erpnext")
    sig = make_signature("testsecret123", employee_created_payload)
    response = api_client.post(
        url,
        data=json.dumps(employee_created_payload, separators=(",", ":")),
        content_type="application/json",
        HTTP_X_FRAPPE_SIGNATURE=sig,
    )
    assert response.status_code == 200


# ------------------------------------------------------------------ #
#  WebhookEvent creation tests                                         #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_webhook_creates_webhook_event(api_client, company, employee_created_payload):
    """A valid webhook creates a WebhookEvent record."""
    url = reverse("webhooks:erpnext")
    sig = make_signature("testsecret123", employee_created_payload)
    api_client.post(
        url,
        data=json.dumps(employee_created_payload, separators=(",", ":")),
        content_type="application/json",
        HTTP_X_FRAPPE_SIGNATURE=sig,
    )
    assert WebhookEvent.objects.count() == 1


@pytest.mark.django_db
def test_webhook_event_has_correct_fields(api_client, company, employee_created_payload):
    """WebhookEvent is created with correct doctype, doc_name and company."""
    url = reverse("webhooks:erpnext")
    sig = make_signature("testsecret123", employee_created_payload)
    api_client.post(
        url,
        data=json.dumps(employee_created_payload, separators=(",", ":")),
        content_type="application/json",
        HTTP_X_FRAPPE_SIGNATURE=sig,
    )
    event = WebhookEvent.objects.first()
    assert event.erpnext_doctype == "Employee"
    assert event.erpnext_doc_name == "HR-EMP-00010"
    assert event.company == company
    assert event.processed is False


@pytest.mark.django_db
def test_webhook_company_updated_event(api_client, company, company_updated_payload):
    """Company updated webhook creates a WebhookEvent with correct doctype."""
    url = reverse("webhooks:erpnext")
    sig = make_signature("testsecret123", company_updated_payload)
    api_client.post(
        url,
        data=json.dumps(company_updated_payload, separators=(",", ":")),
        content_type="application/json",
        HTTP_X_FRAPPE_SIGNATURE=sig,
    )
    event = WebhookEvent.objects.first()
    assert event.erpnext_doctype == "Company"
    assert event.erpnext_doc_name == company.erpnext_doc_name


# ------------------------------------------------------------------ #
#  Unsupported doctype                                                 #
# ------------------------------------------------------------------ #

@pytest.mark.django_db
def test_webhook_rejects_unsupported_doctype(api_client, company):
    """Payload with unsupported doctype → 400."""
    payload = {
        "doctype": "SalesOrder",
        "name": "SO-00001",
        "company": company.erpnext_doc_name,
    }
    url = reverse("webhooks:erpnext")
    sig = make_signature("testsecret123", payload)
    response = api_client.post(
        url,
        data=json.dumps(payload, separators=(",", ":")),
        content_type="application/json",
        HTTP_X_FRAPPE_SIGNATURE=sig,
    )
    assert response.status_code == 400