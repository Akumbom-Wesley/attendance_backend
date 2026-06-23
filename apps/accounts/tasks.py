import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    queue='default',
    max_retries=3,
    default_retry_delay=60,
    name='accounts.send_onboarding_email',
)
def send_onboarding_email_task(self, user_id: int, token: str):
    """Send onboarding email asynchronously via Celery."""
    from apps.accounts.models import User
    from apps.accounts.services import OnboardingService

    try:
        user = User.objects.get(pk=user_id)
        OnboardingService._send_onboarding_email(user, token)
        logger.info("Onboarding email sent to user %s", user_id)
    except User.DoesNotExist:
        logger.error("User %s not found for onboarding email", user_id)
    except Exception as exc:
        logger.error("Failed to send onboarding email to user %s: %s", user_id, exc)
        raise self.retry(exc=exc)
