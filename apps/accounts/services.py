import secrets
from datetime import timedelta

from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.accounts.models import User
from apps.employees.models import Employee


class OnboardingService:

    TOKEN_EXPIRY_HOURS = 24

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_employee(erpnext_employee_id, requesting_user):
        """
        Fetch employee by erpnext_employee_id.
        SUPER_ADMIN sees all. HR_ADMIN scoped to own company.
        Raises Employee.DoesNotExist or PermissionError.
        """
        try:
            employee = Employee.objects.select_related('user', 'company').get(
                erpnext_employee_id=erpnext_employee_id
            )
        except Employee.DoesNotExist:
            raise Employee.DoesNotExist

        if requesting_user.role == User.Role.HR_ADMIN:
            if employee.company != requesting_user.company:
                raise PermissionError("Employee belongs to a different company.")

        return employee

    @staticmethod
    def _generate_and_save_token(user):
        token = secrets.token_urlsafe(32)
        user.onboarding_token = token
        user.onboarding_token_expires_at = (
            timezone.now() + timedelta(hours=OnboardingService.TOKEN_EXPIRY_HOURS)
        )
        user.save(update_fields=['onboarding_token', 'onboarding_token_expires_at'])
        return token

    @staticmethod
    def _send_onboarding_email(user, token):
        import requests as http_requests

        link = f"{settings.FRONTEND_BASE_URL}/set-password?token={token}"
        full_name = user.get_full_name()

        subject = "Welcome to WorkTrackr — Activate Your Account"

        text_body = (
            f"Hello {full_name},\n\n"
            f"You have been added to WorkTrackr, the attendance management system "
            f"for Sure Engineering and Technologies Ltd.\n\n"
            f"Click the link below to set your password and activate your account:\n"
            f"{link}\n\n"
            f"This link expires in 24 hours. If it expires, contact your HR Admin.\n\n"
            f"WorkTrackr Team"
        )

        html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Activate Your WorkTrackr Account</title>
</head>
<body style="margin:0;padding:0;background:#F8F9FF;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F8F9FF;padding:40px 16px;">
  <tr>
    <td align="center">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="max-width:520px;background:#ffffff;border-radius:16px;overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,26,66,0.1);">

        <!-- Header -->
        <tr>
          <td style="background:#001A42;padding:32px 40px;text-align:center;">
            <table cellpadding="0" cellspacing="0" style="display:inline-table;">
              <tr>
                <td style="vertical-align:middle;padding-right:10px;">
                  <div style="width:36px;height:36px;background:#001A42;border:2px solid #6CF8BB;
                              border-radius:8px;display:inline-flex;align-items:center;
                              justify-content:center;text-align:center;line-height:36px;">
                    <span style="color:#6CF8BB;font-size:18px;font-weight:700;">W</span>
                  </div>
                </td>
                <td style="vertical-align:middle;">
                  <span style="font-size:22px;font-weight:700;color:#ffffff;
                               letter-spacing:-0.3px;">Work<span style="color:#6CF8BB;">Trackr</span></span>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:40px 40px 32px;">
            <h1 style="font-size:22px;font-weight:700;color:#0B1C30;margin:0 0 8px;">
              Activate Your Account
            </h1>
            <p style="font-size:14px;color:#45464D;margin:0 0 24px;line-height:1.6;">
              Hello <strong style="color:#0B1C30;">{full_name}</strong>,
            </p>
            <p style="font-size:14px;color:#45464D;margin:0 0 24px;line-height:1.6;">
              You have been added to <strong style="color:#0B1C30;">WorkTrackr</strong>,
              the attendance management system for
              <strong style="color:#0B1C30;">Sure Engineering and Technologies Ltd</strong>.
              Click the button below to set your password and activate your account.
            </p>

            <!-- CTA Button -->
            <table cellpadding="0" cellspacing="0" width="100%" style="margin:32px 0;">
              <tr>
                <td align="center">
                  <a href="{link}"
                     style="display:inline-block;background:#001A42;color:#ffffff;
                            text-decoration:none;font-size:15px;font-weight:600;
                            padding:14px 40px;border-radius:10px;letter-spacing:0.2px;">
                    Activate Account
                  </a>
                </td>
              </tr>
            </table>

            <!-- Divider -->
            <hr style="border:none;border-top:1px solid #EEF0F2;margin:28px 0;"/>

            <!-- Link fallback -->
            <p style="font-size:12px;color:#76777D;margin:0 0 8px;line-height:1.5;">
              If the button doesn&#39;t work, copy and paste this link into your browser:
            </p>
            <p style="font-size:12px;margin:0 0 24px;">
              <a href="{link}" style="color:#006C49;word-break:break-all;">{link}</a>
            </p>

            <!-- Expiry warning -->
            <table cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td style="background:#EFF4FF;border-radius:8px;padding:12px 16px;">
                  <p style="font-size:12px;color:#131B2E;margin:0;line-height:1.5;">
                    <strong>&#9432; This link expires in 24 hours.</strong>
                    If it expires, contact your HR Admin to resend the activation email.
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#F8F9FF;padding:20px 40px;border-top:1px solid #EEF0F2;">
            <p style="font-size:11px;color:#76777D;margin:0;text-align:center;line-height:1.5;">
              This email was sent by WorkTrackr on behalf of
              Sure Engineering and Technologies Ltd.<br/>
              If you did not expect this email, please ignore it.
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

        from django.conf import settings as django_settings
        api_key = django_settings.EMAIL_HOST_PASSWORD
        response = http_requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": django_settings.DEFAULT_FROM_EMAIL,
                "to": [user.email],
                "subject": subject,
                "text": text_body,
                "html": html_body,
            },
            timeout=30,
        )
        if not response.ok:
            raise Exception(f"Resend API error {response.status_code}: {response.text}")
        logger.info("Resend API response: %s", response.json())

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def trigger(self, erpnext_employee_id, requesting_user):
        """
        Trigger onboarding for a single employee.
        Returns the employee on success.
        Raises: Employee.DoesNotExist, PermissionError, ValueError
        """
        employee = self._get_employee(erpnext_employee_id, requesting_user)

        if employee.user.is_onboarded:
            raise ValueError("Employee is already onboarded.")

        if not employee.user.email:
            raise ValueError("Employee has no email address.")

        token = self._generate_and_save_token(employee.user)
        from apps.accounts.tasks import send_onboarding_email_task
        send_onboarding_email_task.delay(employee.user.pk, token)
        return employee

    def trigger_bulk(self, requesting_user):
        """
        Trigger onboarding for all eligible employees.
        Returns dict: {triggered, skipped, skipped_no_email}
        """
        qs = Employee.objects.select_related('user', 'company').filter(is_active=True)

        if requesting_user.role == User.Role.HR_ADMIN:
            qs = qs.filter(company=requesting_user.company)

        triggered = 0
        skipped = 0
        skipped_no_email = 0

        for employee in qs:
            if employee.user.is_onboarded:
                skipped += 1
                continue
            if not employee.user.email:
                skipped_no_email += 1
                continue
            token = self._generate_and_save_token(employee.user)
            from apps.accounts.tasks import send_onboarding_email_task
            send_onboarding_email_task.delay(employee.user.pk, token)
            triggered += 1

        return {
            "triggered": triggered,
            "skipped": skipped,
            "skipped_no_email": skipped_no_email,
        }

    def resend(self, erpnext_employee_id, requesting_user):
        """
        Resend onboarding email (resets token).
        Raises: Employee.DoesNotExist, PermissionError, ValueError
        """
        employee = self._get_employee(erpnext_employee_id, requesting_user)

        if employee.user.is_onboarded:
            raise ValueError("Employee is already onboarded.")

        if not employee.user.email:
            raise ValueError("Employee has no email address.")

        token = self._generate_and_save_token(employee.user)
        from apps.accounts.tasks import send_onboarding_email_task
        send_onboarding_email_task.delay(employee.user.pk, token)
        return employee

    @staticmethod
    def set_password(token, password, password_confirm):
        """
        Validate token, set password, mark user as onboarded.
        Raises ValueError on any validation failure.
        """
        if password != password_confirm:
            raise ValueError("Passwords do not match.")

        try:
            user = User.objects.get(onboarding_token=token)
        except User.DoesNotExist:
            raise ValueError("Invalid or unknown token.")

        if user.is_onboarded:
            raise ValueError("Token has already been used.")

        if not user.onboarding_token_expires_at:
            raise ValueError("Invalid or unknown token.")

        if timezone.now() > user.onboarding_token_expires_at:
            raise ValueError("Token has expired.")

        try:
            validate_password(password, user=user)
        except DjangoValidationError as e:
            raise ValueError(" ".join(e.messages))

        user.set_password(password)
        user.is_onboarded = True
        user.onboarding_token = ""
        user.onboarding_token_expires_at = None
        user.save(update_fields=[
            'password', 'is_onboarded',
            'onboarding_token', 'onboarding_token_expires_at'
        ])
        return user