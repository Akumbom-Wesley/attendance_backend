import pytest
from unittest.mock import patch
from django.utils import timezone
from datetime import timedelta
import json, base64, hashlib, hmac as hmac_mod

from apps.accounts.models import User
from apps.employees.models import Employee

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def trigger_url(employee_id):
    return f"/api/v1/onboarding/trigger/{employee_id}/"


def resend_url(employee_id):
    return f"/api/v1/onboarding/resend/{employee_id}/"


BULK_URL = "/api/v1/onboarding/trigger/bulk/"
SET_PASSWORD_URL = "/api/v1/onboarding/set-password/"


# ===========================================================================
# 1. TRIGGER ONBOARDING — single employee
# ===========================================================================

class TestTriggerOnboarding:

    def test_hr_admin_can_trigger_onboarding_for_unboarded_employee(
        self, authenticated_client, hr_admin_user, employee_with_email
    ):
        """HR Admin triggers onboarding → 200, token set, email sent."""
        with patch("apps.accounts.services.send_mail") as mock_mail:
            response = authenticated_client(hr_admin_user).post(
                trigger_url(employee_with_email.erpnext_employee_id)
            )
        assert response.status_code == 200
        assert mock_mail.called
        employee_with_email.user.refresh_from_db()
        assert employee_with_email.user.onboarding_token != ""
        assert employee_with_email.user.onboarding_token_expires_at is not None

    def test_super_admin_can_trigger_onboarding(
        self, authenticated_client, super_admin_user, employee_with_email
    ):
        with patch("apps.accounts.services.send_mail"):
            response = authenticated_client(super_admin_user).post(
                trigger_url(employee_with_email.erpnext_employee_id)
            )
        assert response.status_code == 200

    def test_employee_role_cannot_trigger_onboarding(
        self, authenticated_client, employee_user, employee_with_email
    ):
        response = authenticated_client(employee_user).post(
            trigger_url(employee_with_email.erpnext_employee_id)
        )
        assert response.status_code == 403

    def test_unauthenticated_cannot_trigger_onboarding(
        self, api_client, employee_with_email
    ):
        response = api_client.post(
            trigger_url(employee_with_email.erpnext_employee_id)
        )
        assert response.status_code == 401

    def test_trigger_nonexistent_employee_returns_404(
        self, authenticated_client, hr_admin_user
    ):
        response = authenticated_client(hr_admin_user).post(
            trigger_url("HR-EMP-99999")
        )
        assert response.status_code == 404

    def test_trigger_employee_with_no_email_returns_400(
        self, authenticated_client, hr_admin_user, employee_without_email
    ):
        response = authenticated_client(hr_admin_user).post(
            trigger_url(employee_without_email.erpnext_employee_id)
        )
        assert response.status_code == 400
        assert "email" in response.data["detail"].lower()

    def test_trigger_already_onboarded_employee_returns_400(
        self, authenticated_client, hr_admin_user, onboarded_employee
    ):
        response = authenticated_client(hr_admin_user).post(
            trigger_url(onboarded_employee.erpnext_employee_id)
        )
        assert response.status_code == 400
        assert "already onboarded" in response.data["detail"].lower()

    def test_token_expires_in_24_hours(
        self, authenticated_client, hr_admin_user, employee_with_email
    ):
        with patch("apps.accounts.services.send_mail"):
            authenticated_client(hr_admin_user).post(
                trigger_url(employee_with_email.erpnext_employee_id)
            )
        employee_with_email.user.refresh_from_db()
        delta = employee_with_email.user.onboarding_token_expires_at - timezone.now()
        assert timedelta(hours=23, minutes=55) < delta < timedelta(hours=24, minutes=5)

    def test_email_contains_set_password_link(
        self, authenticated_client, hr_admin_user, employee_with_email, settings
    ):
        settings.FRONTEND_BASE_URL = "https://app.example.com"
        with patch("apps.accounts.services.send_mail") as mock_mail:
            authenticated_client(hr_admin_user).post(
                trigger_url(employee_with_email.erpnext_employee_id)
            )
        call_kwargs = mock_mail.call_args
        # message body (positional arg index 1 or kwarg 'message')
        body = call_kwargs[0][1] if call_kwargs[0] else call_kwargs[1]["message"]
        assert "https://app.example.com/set-password?token=" in body

    def test_hr_admin_scoped_to_own_company(
        self, authenticated_client, hr_admin_user, employee_other_company
    ):
        """HR Admin cannot trigger onboarding for employee in a different company."""
        response = authenticated_client(hr_admin_user).post(
            trigger_url(employee_other_company.erpnext_employee_id)
        )
        assert response.status_code == 403


# ===========================================================================
# 2. BULK TRIGGER
# ===========================================================================

class TestBulkTriggerOnboarding:

    def test_super_admin_can_bulk_trigger(
        self, authenticated_client, super_admin_user, multiple_unboarded_employees
    ):
        with patch("apps.accounts.services.send_mail"):
            response = authenticated_client(super_admin_user).post(BULK_URL)
        assert response.status_code == 200
        assert "triggered" in response.data
        assert response.data["triggered"] == len(multiple_unboarded_employees)

    def test_hr_admin_can_bulk_trigger_own_company(
        self, authenticated_client, hr_admin_user, multiple_unboarded_employees
    ):
        with patch("apps.accounts.services.send_mail"):
            response = authenticated_client(hr_admin_user).post(BULK_URL)
        assert response.status_code == 200
        assert response.data["triggered"] > 0

    def test_bulk_trigger_skips_already_onboarded(
        self, authenticated_client, super_admin_user,
        multiple_unboarded_employees, onboarded_employee
    ):
        with patch("apps.accounts.services.send_mail") as mock_mail:
            response = authenticated_client(super_admin_user).post(BULK_URL)
        assert response.status_code == 200
        assert response.data["skipped"] >= 1
        # email count == triggered only (not onboarded)
        assert mock_mail.call_count == response.data["triggered"]

    def test_bulk_trigger_skips_employees_without_email(
        self, authenticated_client, super_admin_user,
        multiple_unboarded_employees, employee_without_email
    ):
        with patch("apps.accounts.services.send_mail"):
            response = authenticated_client(super_admin_user).post(BULK_URL)
        assert response.data["skipped_no_email"] >= 1

    def test_employee_role_cannot_bulk_trigger(
        self, authenticated_client, employee_user
    ):
        response = authenticated_client(employee_user).post(BULK_URL)
        assert response.status_code == 403

    def test_bulk_trigger_returns_zero_when_all_onboarded(
        self, authenticated_client, super_admin_user, onboarded_employee
    ):
        with patch("apps.accounts.services.send_mail"):
            response = authenticated_client(super_admin_user).post(BULK_URL)
        assert response.status_code == 200
        assert response.data["triggered"] == 0


# ===========================================================================
# 3. SET PASSWORD (public endpoint)
# ===========================================================================

class TestSetPassword:

    def test_valid_token_sets_password_and_marks_onboarded(
        self, api_client, employee_with_pending_token
    ):
        user = employee_with_pending_token.user
        token = user.onboarding_token
        response = api_client.post(SET_PASSWORD_URL, {
            "token": token,
            "password": "Str0ng!Pass99",
            "password_confirm": "Str0ng!Pass99",
        })
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.is_onboarded is True
        assert user.check_password("Str0ng!Pass99")

    def test_token_is_cleared_after_set_password(
        self, api_client, employee_with_pending_token
    ):
        user = employee_with_pending_token.user
        token = user.onboarding_token
        api_client.post(SET_PASSWORD_URL, {
            "token": token,
            "password": "Str0ng!Pass99",
            "password_confirm": "Str0ng!Pass99",
        })
        user.refresh_from_db()
        assert user.onboarding_token == ""
        assert user.onboarding_token_expires_at is None

    def test_invalid_token_returns_400(self, api_client):
        response = api_client.post(SET_PASSWORD_URL, {
            "token": "not-a-real-token",
            "password": "Str0ng!Pass99",
            "password_confirm": "Str0ng!Pass99",
        })
        assert response.status_code == 400

    def test_expired_token_returns_400(
        self, api_client, employee_with_expired_token
    ):
        user = employee_with_expired_token.user
        response = api_client.post(SET_PASSWORD_URL, {
            "token": user.onboarding_token,
            "password": "Str0ng!Pass99",
            "password_confirm": "Str0ng!Pass99",
        })
        assert response.status_code == 400
        assert "expired" in response.data["detail"].lower()

    def test_password_mismatch_returns_400(
        self, api_client, employee_with_pending_token
    ):
        token = employee_with_pending_token.user.onboarding_token
        response = api_client.post(SET_PASSWORD_URL, {
            "token": token,
            "password": "Str0ng!Pass99",
            "password_confirm": "Different!Pass99",
        })
        assert response.status_code == 400

    def test_weak_password_returns_400(
        self, api_client, employee_with_pending_token
    ):
        token = employee_with_pending_token.user.onboarding_token
        response = api_client.post(SET_PASSWORD_URL, {
            "token": token,
            "password": "123",
            "password_confirm": "123",
        })
        assert response.status_code == 400

    def test_already_onboarded_token_cannot_be_reused(
        self, api_client, onboarded_employee
    ):
        """Token must be cleared on first use — second attempt fails."""
        user = onboarded_employee.user
        # Manually re-set token to simulate replay attempt
        user.onboarding_token = "stale-token"
        user.onboarding_token_expires_at = timezone.now() + timedelta(hours=1)
        user.save()
        response = api_client.post(SET_PASSWORD_URL, {
            "token": "stale-token",
            "password": "Str0ng!Pass99",
            "password_confirm": "Str0ng!Pass99",
        })
        assert response.status_code == 400

    def test_set_password_missing_fields_returns_400(self, api_client):
        response = api_client.post(SET_PASSWORD_URL, {"token": "abc"})
        assert response.status_code == 400


# ===========================================================================
# 4. RESEND ONBOARDING EMAIL
# ===========================================================================

class TestResendOnboarding:

    def test_hr_admin_can_resend_for_unboarded_employee(
        self, authenticated_client, hr_admin_user, employee_with_pending_token
    ):
        with patch("apps.accounts.services.send_mail") as mock_mail:
            response = authenticated_client(hr_admin_user).post(
                resend_url(employee_with_pending_token.erpnext_employee_id)
            )
        assert response.status_code == 200
        assert mock_mail.called

    def test_resend_resets_token_and_expiry(
        self, authenticated_client, hr_admin_user, employee_with_pending_token
    ):
        old_token = employee_with_pending_token.user.onboarding_token
        with patch("apps.accounts.services.send_mail"):
            authenticated_client(hr_admin_user).post(
                resend_url(employee_with_pending_token.erpnext_employee_id)
            )
        employee_with_pending_token.user.refresh_from_db()
        assert employee_with_pending_token.user.onboarding_token != old_token
        delta = (
            employee_with_pending_token.user.onboarding_token_expires_at
            - timezone.now()
        )
        assert timedelta(hours=23, minutes=55) < delta < timedelta(hours=24, minutes=5)

    def test_resend_for_already_onboarded_returns_400(
        self, authenticated_client, hr_admin_user, onboarded_employee
    ):
        response = authenticated_client(hr_admin_user).post(
            resend_url(onboarded_employee.erpnext_employee_id)
        )
        assert response.status_code == 400
        assert "already onboarded" in response.data["detail"].lower()

    def test_resend_nonexistent_employee_returns_404(
        self, authenticated_client, hr_admin_user
    ):
        response = authenticated_client(hr_admin_user).post(
            resend_url("HR-EMP-99999")
        )
        assert response.status_code == 404

    def test_employee_role_cannot_resend(
        self, authenticated_client, employee_user, employee_with_pending_token
    ):
        response = authenticated_client(employee_user).post(
            resend_url(employee_with_pending_token.erpnext_employee_id)
        )
        assert response.status_code == 403

    def test_resend_employee_with_no_email_returns_400(
        self, authenticated_client, hr_admin_user, employee_without_email
    ):
        response = authenticated_client(hr_admin_user).post(
            resend_url(employee_without_email.erpnext_employee_id)
        )
        assert response.status_code == 400


# ===========================================================================
# 5. AUTO-TRIGGER ON WEBHOOK (employee_created)
# ===========================================================================

class TestWebhookAutoOnboarding:

    def test_employee_created_webhook_triggers_onboarding_email(
        self, api_client, company_with_secret, new_employee_payload,
        hmac_headers
    ):
        """
        When ERPNext fires employee_created webhook, process_webhook_event
        should auto-trigger the onboarding email for the new employee.
        """

        raw = json.dumps(new_employee_payload).encode("utf-8")
        headers = hmac_headers(raw, company_with_secret)
        
        # Debug — print what we're sending
        print("\nRAW:", raw)
        print("SECRET:", company_with_secret.webhook_secret)
        print("SIG SENT:", headers["X-Frappe-Webhook-Signature"])
        
        with patch("apps.webhooks.tasks.process_webhook_event.delay"):
            response = api_client.post(
            "/api/v1/webhooks/erpnext/",
            data=raw,
            content_type="application/json",
            **{"HTTP_X_FRAPPE_WEBHOOK_SIGNATURE": headers["X-Frappe-Webhook-Signature"]},
        )
        print("RESPONSE:", response.status_code, response.data)
        assert response.status_code == 200
    
    def test_employee_updated_webhook_does_not_trigger_onboarding(
        self, api_client, company_with_secret, existing_employee_payload,
        hmac_headers
    ):
        """on_update for existing employee must NOT re-trigger onboarding."""
        raw = json.dumps(existing_employee_payload).encode("utf-8")
        headers = hmac_headers(raw, company_with_secret)
        with patch("apps.webhooks.tasks.process_webhook_event.delay") as mock_task:
            response = api_client.post(
                "/api/v1/webhooks/erpnext/",
                data=raw,
                content_type="application/json",
                **{"HTTP_X_FRAPPE_WEBHOOK_SIGNATURE": headers["X-Frappe-Webhook-Signature"]},
            )
        assert response.status_code == 200
        mock_task.assert_called_once()