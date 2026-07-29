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
    4. 動態對應 Stripe Price ID 並自動更新 API 配額 (Quota)
    """

    LOCK_EXPIRE_SECONDS = 60  # 分散式鎖過期時間

    # Price ID 與 Plan / Quota 的映射設定表
    PRICE_MAP = {
        "price_1TxXgaCNxWb8kewbGkYFsc40": {"plan": "PRO", "quota": 50000},
        "price_1TxXi5CNxWb8kewbtKDELVkY": {"plan": "ENTERPRISE", "quota": 500000},
    }

    @classmethod
    def handle_event(cls, event_data) -> bool:
        # 1. 統一將 Stripe 物件或 dict 轉為標準 Python dict，避免 AttributeError
        if hasattr(event_data, "to_dict_recursive"):
            event_data = event_data.to_dict_recursive()
        elif hasattr(event_data, "to_dict"):
            event_data = event_data.to_dict()
        elif not isinstance(event_data, dict):
            event_data = dict(event_data)

        event_id = event_data.get("id")
        event_type = event_data.get("type")

        if not event_id:
            logger.error("[Webhook Error] Event data missing 'id'")
            return False

        # -------------------------------------------------------------
        # Step 1: Redis 分散式鎖 (Distributed Lock)
        # -------------------------------------------------------------
        lock_key = f"lock:stripe_event:{event_id}"
        acquired_lock = redis_client.set(lock_key, "locked", ex=cls.LOCK_EXPIRE_SECONDS, nx=True)

        if not acquired_lock:
            logger.warning(f"[Redis Lock] Event {event_id} is currently being processed by another thread. Skipping.")
            return True  # 回傳 True 避免 Stripe 無限重試

        try:
            # -------------------------------------------------------------
            # Step 2: DB 冪等性檢查 (Idempotency Check)
            # -------------------------------------------------------------
            event_log, created = StripeEventLog.objects.get_or_create(
                event_id=event_id,
                defaults={
                    "type": event_type,
                    "payload": event_data,
                    "status": StripeEventLog.EventStatus.PENDING,
                },
            )

            if not created and event_log.status == StripeEventLog.EventStatus.PROCESSED:
                logger.info(f"[Idempotency] Event {event_id} has already been processed previously. Skipping.")
                return True

            # -------------------------------------------------------------
            # Step 3: 執行金流業務邏輯
            # -------------------------------------------------------------
            with transaction.atomic():
                payload_obj = event_data.get("data", {}).get("object", {})
                cls._process_event_payload(event_type, payload_obj)

                # 更新 Webhook 日誌狀態為成功
                event_log.status = StripeEventLog.EventStatus.PROCESSED
                event_log.processed_at = timezone.now()
                event_log.save()

            return True

        except Exception as e:
            logger.error(f"[Webhook Error] Failed to process event {event_id}: {str(e)}", exc_info=True)
            StripeEventLog.objects.filter(event_id=event_id).update(
                status=StripeEventLog.EventStatus.FAILED, error_message=str(e)
            )
            raise e

        finally:
            # 處理完成後釋放 Redis 鎖
            redis_client.delete(lock_key)

    @classmethod
    def _process_event_payload(cls, event_type: str, payload_obj: dict):
        """
        根據不同的 Stripe 事件類型更新 DB 訂閱狀態與 API 配額
        """
        if event_type in ["checkout.session.completed", "customer.subscription.updated"]:
            customer_id = payload_obj.get("customer")
            subscription_id = payload_obj.get("subscription") or payload_obj.get("id")
            status_str = payload_obj.get("status", "active")

            # 安全解析 Price ID (兼顧 Subscription 與 Checkout Session 物件結構)
            price_id = None
            if "items" in payload_obj:
                items = payload_obj.get("items", {}).get("data", [])
                if items:
                    price_id = items[0].get("price", {}).get("id")
            elif "line_items" in payload_obj:
                lines = payload_obj.get("line_items", {}).get("data", [])
                if lines:
                    price_id = lines[0].get("price", {}).get("id")

            # 雙重搜尋策略 (1. stripe_customer_id -> 2. metadata.organization_id)
            org = None
            if customer_id:
                org = Organization.objects.filter(stripe_customer_id=customer_id).first()

            metadata = payload_obj.get("metadata", {})
            if not org and metadata.get("organization_id"):
                org_id = metadata.get("organization_id")
                org = Organization.objects.filter(id=org_id).first()
                if org and customer_id:
                    # 順手補齊 Organization 的 stripe_customer_id
                    org.stripe_customer_id = customer_id
                    org.save(update_fields=["stripe_customer_id"])

            if not org:
                logger.warning(f"Organization not found for customer_id: {customer_id}, metadata: {metadata}")
                return

            # 更新或建立 Subscription 狀態
            subscription, _ = Subscription.objects.get_or_create(organization=org)
            subscription.stripe_subscription_id = subscription_id or subscription.stripe_subscription_id

            if price_id:
                subscription.stripe_price_id = price_id

            subscription.status = status_str

            # 動態更新 Plan 與 API 配額 logic
            target_price_id = price_id or subscription.stripe_price_id
            plan_config = cls.PRICE_MAP.get(target_price_id)

            if status_str in ["active", SubscriptionStatus.ACTIVE]:
                if plan_config:
                    subscription.plan = plan_config["plan"]
                    subscription.monthly_api_quota = plan_config["quota"]
                else:
                    # 預設 active 回退方案
                    subscription.plan = getattr(subscription, "plan", "PRO") or "PRO"
                    subscription.monthly_api_quota = 50000
            else:
                # 訂閱取消、過期或失敗，降級為 Free Tier
                subscription.plan = "FREE"
                subscription.monthly_api_quota = 1000

            subscription.save()
            logger.info(
                f"Successfully updated subscription for Org '{org.name}' | "
                f"Status: '{status_str}' | Plan: '{subscription.plan}' | Quota: {subscription.monthly_api_quota}"
            )