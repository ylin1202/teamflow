import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from core.models import Organization

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def send_invitation_email_task(
    self, email: str, organization_name: str, accept_url: str, sender_email: str, role: str
):
    """[Background Task] Send team workspace invitation email."""
    try:
        logger.info(f"[Celery Worker] Sending invitation email to {email} for org: {organization_name}")
        
        subject = f"[{organization_name}] Team Workspace Invitation"
        message = (
            f"Hello,\n\n"
            f"{sender_email} has invited you to join the team '{organization_name}' with role '{role}'.\n\n"
            f"Please click the link below to accept the invitation:\n"
            f"{accept_url}\n\n"
            f"This link will expire in 7 days."
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,  # Set to False to raise exceptions and trigger Celery retry
        )
        logger.info(f"[Celery Worker] Invitation email successfully sent to {email}")
        return {"status": "success", "email": email}

    except Exception as exc:
        logger.warning(f"[Celery Worker] Failed to send invitation email to {email}. Error: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def send_subscription_welcome_email(self, organization_id: str):
    """[Background Task] Send welcome confirmation email upon successful subscription."""
    try:
        org = Organization.objects.get(id=organization_id)
        owner_email = org.owner.email
        logger.info(f"[Celery Worker] Sending welcome email to {owner_email}")

        subject = f"[{org.name}] Thank you for upgrading to the {org.plan} plan!"
        message = (
            f"Dear {org.owner.username},\n\n"
            f"Your team '{org.name}' has been successfully upgraded to the {org.plan} plan!\n"
            f"You now have access to increased project quotas and all premium features.\n\n"
            f"Best regards,\n"
            f"The TeamFlow Team"
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner_email],
            fail_silently=False,
        )

        logger.info(f"[Celery Worker] Welcome email successfully sent for Org: {org.name}")
        return {"status": "success", "org_id": organization_id, "sent_at": str(timezone.now())}

    except Organization.DoesNotExist as e:
        logger.error(f"[Celery Worker] Organization {organization_id} not found. Skipping retry.")
        raise e

    except Exception as exc:
        logger.warning(f"[Celery Worker] Failed to send welcome email for {organization_id}. Retrying... Error: {exc}")
        raise self.retry(exc=exc)