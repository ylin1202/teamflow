import logging
import stripe
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from redis import Redis
from core.models import StripeEventLog, Subscription, Organization, SubscriptionStatus

logger = logging.getLogger(__name__)

REDIS_URL = getattr(settings, "REDIS_URL", "redis://redis:6379/0")
redis_client = Redis.from_url(REDIS_URL)
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


class StripeWebhookService:
    """
    處理 Stripe Webhook 邏輯：
    1. 結合 Redis 分散式鎖，防範極短時間內的重複併發請求 (Race Condition)
    2. 結合 StripeEventLog 資料庫記錄，實現嚴格的「冪等性 (Idempotency)」
    3. 使用 transaction.atomic() 確保金流狀態更新之原子性
    4. 動態對應 Stripe Price ID 並自動更新 API 配額 (Quota)
    5. 完整的金流邊界事件處理 (扣款失敗 past_due、訂閱終止 canceled / 降級 Free)
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
        # 涵蓋所有訂閱週期與扣款狀態變更事件
        if event_type in [
            "checkout.session.completed",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "invoice.payment_failed",
        ]:
            customer_id = payload_obj.get("customer")
            subscription_id = payload_obj.get("subscription") or payload_obj.get("id")
            
            # 1. 抓取 Stripe 傳來的 cancel_at_period_end 標記
            cancel_at_period_end = payload_obj.get("cancel_at_period_end", False)

            # 依據事件類型與取消標記精確對應狀態
            if event_type == "customer.subscription.deleted":
                status_str = "canceled"
            elif event_type == "invoice.payment_failed":
                status_str = "past_due"
            elif cancel_at_period_end:
                # 2. 若預約取消，直接將狀態記為 canceling
                status_str = "canceling"
            else:
                status_str = payload_obj.get("status", "active")

            # 優先解析 Price ID
            price_id = None
            if "items" in payload_obj:
                items = payload_obj.get("items", {}).get("data", [])
                if items:
                    price_id = items[0].get("price", {}).get("id")
            
            # 若 payload 沒帶 items (常見於 checkout.session.completed)，向 Stripe API 撈取 Subscription 物件
            if not price_id and subscription_id and str(subscription_id).startswith("sub_") and stripe.api_key:
                try:
                    stripe_sub = stripe.Subscription.retrieve(subscription_id)
                    sub_items = stripe_sub.get("items", {}).get("data", [])
                    if sub_items:
                        price_id = sub_items[0].get("price", {}).get("id")
                        
                    # 若原本沒抓到，順便從 Stripe 物件更新 cancel_at_period_end
                    if cancel_at_period_end is False:
                        cancel_at_period_end = stripe_sub.get("cancel_at_period_end", False)
                        if cancel_at_period_end and status_str == "active":
                            status_str = "canceling"
                except Exception as e:
                    logger.warning(f"Could not retrieve Stripe subscription {subscription_id}: {e}")

            # 雙重搜尋策略 (1. stripe_customer_id -> 2. metadata.organization_id / client_reference_id)
            org = None
            if customer_id:
                org = Organization.objects.filter(stripe_customer_id=customer_id).first()

            metadata = payload_obj.get("metadata", {})
            org_id = metadata.get("organization_id") or payload_obj.get("client_reference_id")
            
            if not org and org_id:
                org = Organization.objects.filter(id=org_id).first()
                if org and customer_id:
                    # 順手補齊 Organization 的 stripe_customer_id
                    org.stripe_customer_id = customer_id
                    org.save(update_fields=["stripe_customer_id"])

            if not org:
                logger.warning(f"Organization not found for customer_id: {customer_id}, org_id: {org_id}")
                return

            # 更新或建立 Subscription 狀態
            subscription, _ = Subscription.objects.get_or_create(organization=org)
            if subscription_id:
                subscription.stripe_subscription_id = subscription_id

            if price_id:
                subscription.stripe_price_id = price_id

            subscription.status = status_str
            # 3. 確保將 cancel_at_period_end 保存至資料庫
            subscription.cancel_at_period_end = cancel_at_period_end

            # 動態更新 Plan 與 API 配額 logic
            target_price_id = price_id or subscription.stripe_price_id
            plan_config = cls.PRICE_MAP.get(target_price_id)

            # 4. active 或 canceling 都依然享有付費配額（直到期滿正式 deleted 才降級）
            if status_str in ["active", "canceling", SubscriptionStatus.ACTIVE]:
                if plan_config:
                    subscription.plan = plan_config["plan"]
                    subscription.monthly_api_quota = plan_config["quota"]
                else:
                    subscription.plan = "PRO"
                    subscription.monthly_api_quota = 50000
            else:
                # 訂閱正式終止 (canceled) 或扣款失敗 (past_due)，自動降級為 Free Tier
                subscription.plan = "FREE"
                subscription.monthly_api_quota = 1000

            subscription.save()
            logger.info(
                f"Successfully updated subscription for Org '{org.name}' | "
                f"Status: '{status_str}' | Plan: '{subscription.plan}' | Quota: {subscription.monthly_api_quota}"
            )