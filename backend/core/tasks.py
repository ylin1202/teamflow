import logging
from celery import shared_task
from django.utils import timezone
from core.models import Organization

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,                  # 綁定 self 實體，讓內部可以呼叫 self.retry() 執行自動重試
    max_retries=3,              # 任務失敗時的「最大重試次數」 (最多重試 3 次)
    default_retry_delay=60,     # 每次失敗後「等待 60 秒」再進行下一次重試 (防止連續暴擊第三方 API)
    acks_late=True,             # 確保該任務遵循延遲 Ack 機制，成功才確認
)
def send_subscription_welcome_email(self, organization_id: str):
    """
    【非同步背景任務】金流成功後在背景發送歡迎信件與發票資訊
    注意：在 View 或 Service 中請使用 `send_subscription_welcome_email.delay(org_id)` 來呼叫
    """
    try:
        # 1. 根據 ID 抓取組織與 Owner 資料
        org = Organization.objects.get(id=organization_id)
        logger.info(f"[Celery Worker] Sending welcome & invoice email to Organization: {org.name} ({org.owner.email})")
        
        # 2. 模擬發送 Email 或呼叫第三方 API (如 SendGrid, Resend, Mailgun 等)
        # ... Mail Sending Logic ...

        logger.info(f"[Celery Worker] Email successfully sent for Organization: {org.name}")
        return {
            "status": "success", 
            "org_id": organization_id, 
            "sent_at": str(timezone.now())
        }

    except Organization.DoesNotExist as e:
        # 特殊處理：如果資料庫根本找不到這個 Organization ID，屬於資料異常，重試也沒用
        # 紀錄 Error Log 後直接拋出異常，不觸發 self.retry()
        logger.error(f"[Celery Worker] Organization {organization_id} not found. Skipping retry.")
        raise e

    except Exception as exc:
        # 通用異常處理：若是網路波動、Email 服務暫時連不上等問題
        logger.warning(f"[Celery Worker] Failed to send email for {organization_id}. Retrying... Error: {exc}")
        
        # 自動重試核心點：拋出 self.retry()，Celery 會自動將這個任務重新塞回佇列，60 秒後再試
        raise self.retry(exc=exc)