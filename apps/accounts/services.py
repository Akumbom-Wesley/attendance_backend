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
        link = (
            f"{settings.FRONTEND_BASE_URL}/set-password?token={token}"
        )
        send_mail(
            subject="Set your attendance system password",
            message=(
                f"Hello {user.get_full_name()},\n\n"
                f"You have been added to the attendance system. "
                f"Click the link below to set your password:\n\n"
                f"{link}\n\n"
                f"This link expires in 24 hours.\n"
            ),
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[user.email],
        )

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
        self._send_onboarding_email(employee.user, token)
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
            self._send_onboarding_email(employee.user, token)
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
        self._send_onboarding_email(employee.user, token)
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