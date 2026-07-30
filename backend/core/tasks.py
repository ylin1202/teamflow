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
    """【背景任務】發送團隊邀請信"""
    try:
        logger.info(f"[Celery Worker] Sending invitation email to {email} for org: {organization_name}")
        
        subject = f"【{organization_name}】團隊邀請函"
        message = (
            f"您好，\n\n"
            f"{sender_email} 邀請您加入團隊「{organization_name}」（權限: {role}）。\n\n"
            f"請點擊下方連結接受邀請：\n"
            f"{accept_url}\n\n"
            f"此連結將在 7 天後失效。"
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,  # 設為 False 讓失敗時拋出 Exception 觸發 Celery 重試
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
    """【背景任務】付款成功發送歡迎信"""
    try:
        org = Organization.objects.get(id=organization_id)
        owner_email = org.owner.email
        logger.info(f"[Celery Worker] Sending welcome email to {owner_email}")

        subject = f"【{org.name}】感謝升級至 {org.plan} 方案！"
        message = (
            f"親愛的 {org.owner.username} 您好，\n\n"
            f"您的團隊「{org.name}」已成功升級至 {org.plan} 方案！\n"
            f"您現在享有最新的專案配額與完整權限功能。\n\n"
            f"祝使用愉快！"
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