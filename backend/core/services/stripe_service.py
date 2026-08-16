import logging
import stripe
from redis import Redis
from django.db import transaction
from django.conf import settings
from django.utils import timezone

from core.models import StripeEventLog, Subscription, Organization
from core.tasks import send_subscription_welcome_email

logger = logging.getLogger(__name__)

REDIS_URL = getattr(settings, "REDIS_URL", "redis://redis:6379/0")
redis_client = Redis.from_url(REDIS_URL)
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


class StripeWebhookService:
    """
    Handles Stripe Webhook business logic:
    1. Leverages Redis distributed locks to guard against rapid concurrent race conditions.
    2. Enforces strict idempotency via StripeEventLog database records.
    3. Guarantees transactional atomicity using transaction.atomic().
    4. Dynamically maps Stripe Price IDs and updates organization subscription limits.
    5. Manages boundary payment events (e.g., payment failures).
    """
    LOCK_EXPIRE_SECONDS = 60

    PRICE_MAP = {
        settings.STRIPE_PRICE_PRO: {
            "plan": "PRO",
            "project_limit": 25,
        },
        settings.STRIPE_PRICE_ENTERPRISE: {
            "plan": "ENTERPRISE",
            "project_limit": 150,
        },
    }

    @classmethod
    def handle_event(cls, event_data) -> bool:
        # Normalize Stripe event payloads/dicts into a standard Python dict to prevent AttributeErrors
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

        # Redis Distributed Lock
        lock_key = f"lock:stripe_event:{event_id}"
        acquired_lock = redis_client.set(lock_key, "locked", ex=cls.LOCK_EXPIRE_SECONDS, nx=True)

        if not acquired_lock:
            logger.warning(f"[Redis Lock] Event {event_id} is currently being processed by another thread. Skipping.")
            return True  # Return True to acknowledge receipt and prevent Stripe infinite retries

        try:
            # Database Idempotency Check
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

            # Execute Billing Business Logic
            with transaction.atomic():
                payload_obj = event_data.get("data", {}).get("object", {})
                cls._process_event_payload(event_type, payload_obj)

                # Update webhook log status to PROCESSED
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
            # Release Redis distributed lock after processing
            redis_client.delete(lock_key)

    @classmethod
    def _process_event_payload(cls, event_type: str, payload_obj: dict):
        # One-time payment/Checkout completed (checkout.session.completed)
        if event_type == "checkout.session.completed":
            payment_status = payload_obj.get("payment_status")
            if payment_status != "paid":
                logger.info(f"[Webhook] Checkout Session {payload_obj.get('id')} payment_status is '{payment_status}', skipping.")
                return

            customer_id = payload_obj.get("customer")
            session_id = payload_obj.get("id")

            metadata = payload_obj.get("metadata", {})
            org_id = payload_obj.get("client_reference_id") or metadata.get("organization_id")
            
            logger.info(f"DEBUG [Webhook] Processing Session: {session_id}, Extracted org_id: {org_id}")

            org = None
            if org_id:
                org = Organization.objects.filter(id=org_id).first()

            if not org and customer_id:
                org = Organization.objects.filter(stripe_customer_id=customer_id).first()

            if not org:
                logger.error(f"[Webhook Error] Organization not found for session_id: {session_id}, org_id: {org_id}")
                return

            if customer_id and org.stripe_customer_id != customer_id:
                org.stripe_customer_id = customer_id
                org.save()

            # Parse Price ID compatibly across Stripe SDK objects and pure dict responses
            price_id = None
            try:
                line_items = stripe.checkout.Session.list_line_items(session_id, limit=1)
                items_data = line_items.get("data", []) if isinstance(line_items, dict) else getattr(line_items, "data", [])
                
                if items_data:
                    first_item = items_data[0]
                    price_obj = first_item.get("price", {}) if isinstance(first_item, dict) else getattr(first_item, "price", {})
                    price_id = price_obj.get("id") if isinstance(price_obj, dict) else getattr(price_obj, "id", None)
            except Exception as e:
                logger.warning(f"[Webhook Exception] Failed to list_line_items for session {session_id}: {e}")

            logger.info(f"DEBUG [Webhook] Extracted Price ID: '{price_id}'")

            plan_config = cls.PRICE_MAP.get(price_id) if price_id else None

            if plan_config:
                target_plan = str(plan_config["plan"]).upper()
            else:
                logger.warning(f"[Webhook Warning] Unmapped or missing price_id '{price_id}'. Defaulting to 'PRO'.")
                target_plan = "PRO"

            # Synchronize Organization plan and Subscription records
            org.plan = target_plan
            org.save()

            subscription, _ = Subscription.objects.get_or_create(organization=org)
            if price_id:
                subscription.stripe_price_id = price_id
            
            subscription.plan = target_plan
            subscription.status = "active"
            subscription.save()

            transaction.on_commit(
                lambda: send_subscription_welcome_email.delay(str(org.id))
            )

            logger.info(
                f"[Webhook Success] Successfully upgraded Org '{org.name}' ({org.id}) to Plan '{target_plan}'!"
            )
        
        # Payment failed (payment_intent.payment_failed)
        elif event_type == "payment_intent.payment_failed":
            customer_id = payload_obj.get("customer")
            last_payment_error = payload_obj.get("last_payment_error", {}).get("message", "Unknown payment error")
            
            logger.warning(
                f"[Webhook Border Event] Payment failed for Customer {customer_id}. Reason: {last_payment_error}"
            )
            
            if customer_id:
                org = Organization.objects.filter(stripe_customer_id=customer_id).first()
                if org:
                    # Update subscription state to unpaid without modifying tier limits
                    subscription, _ = Subscription.objects.get_or_create(organization=org)
                    subscription.status = "unpaid"
                    subscription.save()
                    logger.info(f"[Webhook Border Event] Marked subscription as 'unpaid' for Org {org.name}")

        # Session expired / abandoned (checkout.session.expired)
        elif event_type == "checkout.session.expired":
            session_id = payload_obj.get("id")
            logger.info(f"[Webhook Border Event] Checkout session {session_id} expired without payment.")