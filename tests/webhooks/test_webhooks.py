import base64
import hashlib
import hmac
import json
import pytest

from unittest.mock import patch
from django.urls import reverse
from apps.webhooks.models import WebhookEvent
from tests.factories.company_factory import CompanyFactory


def make_signature(secret: str, body: bytes) -> str:
    return base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")


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


@pytest.mark.django_db
def test_webhook_rejects_missing_signature(api_client, employee_created_payload):
    url = reverse("webhooks:erpnext")
    response = api_client.post(url, data=employee_created_payload, format="json")
    assert response.status_code == 403


@pytest.mark.django_db
def test_webhook_rejects_invalid_signature(api_client, company, employee_created_payload):
    url = reverse("webhooks:erpnext")
    response = api_client.post(
        url,
        data=employee_created_payload,
        format="json",
        HTTP_X_FRAPPE_WEBHOOK_SIGNATURE="invalidsignature",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_webhook_accepts_valid_signature(api_client, company, employee_created_payload):
    url = reverse("webhooks:erpnext")
    raw = json.dumps(employee_created_payload, separators=(",", ":")).encode("utf-8")
    sig = make_signature("testsecret123", raw)
    with patch("apps.webhooks.tasks.process_webhook_event.delay"):
        response = api_client.post(
            url,
            data=raw,
            content_type="application/json",
            HTTP_X_FRAPPE_WEBHOOK_SIGNATURE=sig,
        )
    assert response.status_code == 200


@pytest.mark.django_db
def test_webhook_creates_webhook_event(api_client, company, employee_created_payload):
    url = reverse("webhooks:erpnext")
    raw = json.dumps(employee_created_payload, separators=(",", ":")).encode("utf-8")
    sig = make_signature("testsecret123", raw)
    with patch("apps.webhooks.tasks.process_webhook_event.delay"):
        api_client.post(
            url,
            data=raw,
            content_type="application/json",
            HTTP_X_FRAPPE_WEBHOOK_SIGNATURE=sig,
        )
    assert WebhookEvent.objects.count() == 1


@pytest.mark.django_db
def test_webhook_event_has_correct_fields(api_client, company, employee_created_payload):
    url = reverse("webhooks:erpnext")
    raw = json.dumps(employee_created_payload, separators=(",", ":")).encode("utf-8")
    sig = make_signature("testsecret123", raw)
    with patch("apps.webhooks.tasks.process_webhook_event.delay"):
        api_client.post(
            url,
            data=raw,
            content_type="application/json",
            HTTP_X_FRAPPE_WEBHOOK_SIGNATURE=sig,
        )
    event = WebhookEvent.objects.first()
    assert event.erpnext_doctype == "Employee"
    assert event.erpnext_doc_name == "HR-EMP-00010"
    assert event.company == company
    assert event.processed is False


@pytest.mark.django_db
def test_webhook_company_updated_event(api_client, company, company_updated_payload):
    url = reverse("webhooks:erpnext")
    raw = json.dumps(company_updated_payload, separators=(",", ":")).encode("utf-8")
    sig = make_signature("testsecret123", raw)
    with patch("apps.webhooks.tasks.process_webhook_event.delay"):
        api_client.post(
            url,
            data=raw,
            content_type="application/json",
            HTTP_X_FRAPPE_WEBHOOK_SIGNATURE=sig,
        )
    event = WebhookEvent.objects.first()
    assert event.erpnext_doctype == "Company"
    assert event.erpnext_doc_name == company.erpnext_doc_name


@pytest.mark.django_db
def test_webhook_rejects_unsupported_doctype(api_client, company):
    payload = {
        "doctype": "SalesOrder",
        "name": "SO-00001",
        "company": company.erpnext_doc_name,
    }
    url = reverse("webhooks:erpnext")
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = make_signature("testsecret123", raw)
    response = api_client.post(
        url,
        data=raw,
        content_type="application/json",
        HTTP_X_FRAPPE_WEBHOOK_SIGNATURE=sig,
    )
    assert response.status_code == 400
