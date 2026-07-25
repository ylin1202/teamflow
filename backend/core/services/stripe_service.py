import time, os
import logging
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from redis import Redis
from core.models import StripeEventLog, Subscription, Organization, SubscriptionStatus

logger = logging.getLogger(__name__)

REDIS_URL = getattr(settings, "REDIS_URL", "redis://redis:6379/0")
redis_client = Redis.from_url(REDIS_URL)

class StripeWebhookService:
    """
    處理 Stripe Webhook 邏輯：
    1. 結合 Redis 分散式鎖，防範極短時間內的重複併發請求 (Race Condition)
    2. 結合 StripeEventLog 資料庫記錄，實現嚴格的「冪等性 (Idempotency)」
    3. 使用 transaction.atomic() 確保金流狀態更新之原子性
    """

    LOCK_EXPIRE_SECONDS = 60  # 分散式鎖過期時間

    @classmethod
    def handle_event(cls, event_data: dict) -> bool:
        event_id = event_data.get("id")
        event_type = event_data.get("type")
        
        if not event_id:
            return False

        # -------------------------------------------------------------
        # Step 1: Redis 分散式鎖 (Distributed Lock)
        # 防止同一筆 Event 在極短時間內因網絡 Retry 被多個 Thread/Worker 同時處理
        # -------------------------------------------------------------
        lock_key = f"lock:stripe_event:{event_id}"
        # SET key value NX PX -> 只有 key 不存在時才設定 (Acquire Lock)
        acquired_lock = redis_client.set(lock_key, "locked", ex=cls.LOCK_EXPIRE_SECONDS, nx=True)

        if not acquired_lock:
            logger.warning(f"[Redis Lock] Event {event_id} is currently being processed by another thread. Skipping.")
            return True  # 回傳 True 讓 Stripe 知道收到請求，避免持續重試塞爆系統

        try:
            # -------------------------------------------------------------
            # Step 2: DB 冪等性檢查 (Idempotency Check)
            # -------------------------------------------------------------
            event_log, created = StripeEventLog.objects.get_or_create(
                event_id=event_id,
                defaults={
                    "type": event_type,
                    "payload": event_data,
                    "status": StripeEventLog.EventStatus.PENDING
                }
            )

            # 如果這個事件之前已經成功處理過，直接返回 (Idempotent Return)
            if not created and event_log.status == StripeEventLog.EventStatus.PROCESSED:
                logger.info(f"[Idempotency] Event {event_id} has already been processed previously. Skipping.")
                return True

            # -------------------------------------------------------------
            # Step 3: 執行金流業務邏輯 (Wrapped in DB Transaction)
            # -------------------------------------------------------------
            with transaction.atomic():
                cls._process_event_payload(event_type, event_data.get("data", {}).get("object", {}))
                
                # 更新 Webhook 日誌狀態為成功
                event_log.status = StripeEventLog.EventStatus.PROCESSED
                event_log.processed_at = timezone.now()
                event_log.save()

            return True

        except Exception as e:
            logger.error(f"[Webhook Error] Failed to process event {event_id}: {str(e)}", exc_info=True)
            # 紀錄失敗狀態
            StripeEventLog.objects.filter(event_id=event_id).update(
                status=StripeEventLog.EventStatus.FAILED,
                error_message=str(e)
            )
            raise e

        finally:
            # 處理完成後釋放 Redis 分散式鎖
            redis_client.delete(lock_key)

    @classmethod
    def _process_event_payload(cls, event_type: str, payload_obj: dict):
        """
        根據不同的 Stripe 事件類型更新 DB 訂閱狀態
        """
        if event_type in ["checkout.session.completed", "customer.subscription.updated"]:
            customer_id = payload_obj.get("customer")
            subscription_id = payload_obj.get("subscription") or payload_obj.get("id")
            price_id = payload_obj.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
            status_str = payload_obj.get("status", "active")

            # 找到對應的 Organization
            org = Organization.objects.filter(stripe_customer_id=customer_id).first()
            if not org:
                logger.warning(f"Organization with stripe_customer_id {customer_id} not found.")
                return

            # 更新或建立 Subscription 狀態
            subscription, _ = Subscription.objects.get_or_create(organization=org)
            subscription.stripe_subscription_id = subscription_id
            subscription.stripe_price_id = price_id or subscription.stripe_price_id
            subscription.status = status_str
            
            # 設定權限與 API 配額 (例如 Pro 方案給 100,000 次)
            if status_str == SubscriptionStatus.ACTIVE:
                subscription.monthly_api_quota = 100000
            
            subscription.save()
            logger.info(f"Successfully updated subscription for Organization {org.name} to {status_str}")