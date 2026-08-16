import json
import stripe
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from core.models import Organization, Subscription, Project
from core.permissions import IsOrganizationOwner
from core.services.stripe_service import StripeWebhookService

# Project creation limits per subscription plan
PLAN_PROJECT_LIMITS = {
    "FREE": 5,
    "PRO": 25,
    "ENTERPRISE": 150,
}

stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    """
    Stripe Webhook API Endpoint:
    Exempt from CSRF protection and validates payload authenticity via Stripe signature verification.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    event = None

    # 1. Signature Verification
    try:
        if endpoint_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        else:
            event = json.loads(payload)
            logger.warning("[Webhook Warning] No STRIPE_WEBHOOK_SECRET found, parsed raw JSON.")

    except ValueError as e:
        logger.error(f"[Webhook Error] Invalid Payload: {e}")
        return HttpResponse(status=400)

    except stripe.error.SignatureVerificationError as e:
        if settings.DEBUG:
            event = json.loads(payload)
            logger.warning("[DEBUG Mode] Signature verification failed, falling back to raw JSON for local testing.")
        else:
            logger.error(f"[Webhook Error] Signature Verification Failed: {e}")
            return HttpResponse(status=400)

    # 2. Delegate to Service Layer (Handles Redis distributed locks and DB idempotency)
    try:
        StripeWebhookService.handle_event(event)
        return JsonResponse({"status": "success"}, status=200)
    except Exception as e:
        logger.error(f"[Webhook Error] Service Exception: {e}", exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)


class CreateCheckoutSessionView(APIView):
    """
    Creates a Stripe Checkout Session for upgrading workspace subscription tiers.
    """
    permission_classes = [permissions.IsAuthenticated, IsOrganizationOwner]

    def post(self, request):
        if not stripe.api_key:
            return Response(
                {"detail": "Stripe secret key is not configured."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        price_id = request.data.get("price_id")
        org_id = request.headers.get("X-Organization-ID") or request.data.get("organization_id")

        if not price_id or not org_id:
            return Response(
                {"detail": "Missing price_id or X-Organization-ID header."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
            
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode="payment",
                client_reference_id=org_id,
                metadata={"organization_id": org_id},
                success_url=f"{frontend_url}/dashboard/billing?success=true",
                cancel_url=f"{frontend_url}/dashboard/billing?canceled=true",
                customer_email=request.user.email,
            )
            return Response({"url": checkout_session.url})
        except Exception as e:
            logger.error(f"[Stripe Checkout Exception]: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SubscriptionStatusView(APIView):
    """
    Retrieves current workspace subscription status and quota tier metadata.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return Response({"detail": "Missing X-Organization-ID header."}, status=status.HTTP_400_BAD_REQUEST)

        org = Organization.objects.filter(id=org_id).first()
        if not org:
            return Response({"detail": "Organization not found."}, status=status.HTTP_404_NOT_FOUND)

        sub = Subscription.objects.filter(organization=org).first()
        plan = (sub.plan if sub and sub.plan else getattr(org, "plan", "FREE") or "FREE").upper()
        status_val = sub.status if sub else "active"

        return Response({
            "plan": plan,
            "status": status_val,
            "max_projects": PLAN_PROJECT_LIMITS.get(plan, 5),
            "current_period_end": sub.current_period_end if sub else None,
        })


class ProjectQuotaUsageView(APIView):
    """
    Returns current project creation count and maximum allowed quota for the workspace.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return Response(
                {"detail": "Missing X-Organization-ID header."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        org = Organization.objects.filter(id=org_id).first()
        if not org:
            return Response(
                {"detail": "Organization not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        sub = Subscription.objects.filter(organization=org).first()
        plan = (sub.plan if sub and sub.plan else getattr(org, "plan", "FREE") or "FREE").upper()

        current_projects = Project.objects.filter(organization=org).count()
        max_projects = PLAN_PROJECT_LIMITS.get(plan, 5)

        return Response({
            "plan": plan,
            "current_projects": current_projects,
            "max_projects": max_projects,
        })


class CustomerPortalView(APIView):
    """
    Creates a Stripe Customer Portal session for billing and invoice management.
    """
    permission_classes = [permissions.IsAuthenticated, IsOrganizationOwner]

    def post(self, request):
        org = getattr(request, "organization", None) or getattr(request.user, "organization", None)
        if not org:
            return Response({"error": "No organization associated with current user."}, status=status.HTTP_400_BAD_REQUEST)

        customer_id = getattr(org, "stripe_customer_id", None)
        if not customer_id:
            return Response(
                {"error": "No Stripe Customer ID found. Please complete a payment first."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=f"{frontend_url}/billing",
            )
            return Response({"url": portal_session.url})
        except Exception as e:
            logger.error(f"Failed to create Stripe portal session: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)