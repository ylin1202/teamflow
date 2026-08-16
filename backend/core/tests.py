import uuid
import json
from unittest.mock import patch
from django.urls import reverse
from django.conf import settings
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

from core.models import (
    Organization,
    OrganizationMember,
    OrganizationRole,
    StripeEventLog,
    Subscription,
    Project,
)
from core.services.stripe_service import StripeWebhookService

User = get_user_model()


class SaasBackendTests(APITestCase):

    def setUp(self):
        """
        Test fixture initialization:
        Provisions two isolated organizations (Company A & Company B) to verify multi-tenant isolation.
        """
        # Create distinct users
        self.user_a = User.objects.create_user(
            username="user_a", email="usera@example.com", password="password123"
        )
        self.user_b = User.objects.create_user(
            username="user_b", email="userb@example.com", password="password123"
        )

        # Provision Company A (Owned by User A, Free tier)
        self.org_a = Organization.objects.create(
            name="Company A",
            slug="company-a",
            owner=self.user_a,
            stripe_customer_id="cus_test_A123",
            plan="FREE",
        )
        OrganizationMember.objects.create(
            organization=self.org_a, user=self.user_a, role=OrganizationRole.OWNER
        )

        # Provision Company B (Owned by User B, Enterprise tier)
        self.org_b = Organization.objects.create(
            name="Company B",
            slug="company-b",
            owner=self.user_b,
            stripe_customer_id="cus_test_B456",
            plan="ENTERPRISE",
        )
        OrganizationMember.objects.create(
            organization=self.org_b, user=self.user_b, role=OrganizationRole.OWNER
        )

        # Reverse endpoint URL for billing project quota usage
        self.usage_url = reverse("project_quota_usage")

    # ProjectQuotaUsageView & Multi-Tenancy Isolation
    def test_project_quota_usage_api_success(self):
        """
        Target: Verify GET /api/billing/project-usage/
        Scenario: User A queries project quota usage supplying Company A's header.
        Expected: HTTP 200 OK with FREE plan metadata and maximum limit of 5 projects.
        """
        self.client.force_authenticate(user=self.user_a)

        # Create two projects to test project count aggregation
        Project.objects.create(organization=self.org_a, name="Project 1")
        Project.objects.create(organization=self.org_a, name="Project 2")

        response = self.client.get(
            self.usage_url, HTTP_X_ORGANIZATION_ID=str(self.org_a.id)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["plan"], "FREE")
        self.assertEqual(response.data["current_projects"], 2)
        self.assertEqual(response.data["max_projects"], 5)

    def test_project_quota_usage_after_upgrade(self):
        """
        Target: Verify quota reflection after organization tier upgrade.
        Scenario: Subscription updated to ENTERPRISE.
        Expected: max_projects returns 150.
        """
        self.client.force_authenticate(user=self.user_a)

        # Create / update Subscription record to ENTERPRISE
        Subscription.objects.create(
            organization=self.org_a,
            plan="ENTERPRISE",
            status="active",
            max_projects=150,
            stripe_price_id=settings.STRIPE_PRICE_ENTERPRISE or "price_enterprise_mock",
        )

        response = self.client.get(
            self.usage_url, HTTP_X_ORGANIZATION_ID=str(self.org_a.id)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["plan"], "ENTERPRISE")
        self.assertEqual(response.data["max_projects"], 150)

    def test_project_quota_usage_missing_header(self):
        """
        Target: Guard against requests missing tenant context headers.
        Expected: HTTP 400 Bad Request.
        """
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(self.usage_url)  # Omit HTTP_X_ORGANIZATION_ID
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # Stripe Webhook Idempotency & Tier Synchronization
    @patch("stripe.checkout.Session.list_line_items")
    def test_stripe_webhook_checkout_completed_idempotency(self, mock_list_line_items):
        """
        Target: Verify checkout.session.completed processing and webhook idempotency.
        Scenario: Webhook receives identical checkout completion events twice.
        Expected:
        - First execution: Upgrades Organization and Subscription to ENTERPRISE.
        - Second execution: Intercepted by StripeEventLog idempotency guard without duplicate mutation.
        """
        enterprise_price_id = settings.STRIPE_PRICE_ENTERPRISE or "price_enterprise_mock"
        mock_list_line_items.return_value = {
            "data": [{"price": {"id": enterprise_price_id}}]
        }

        event_id = "evt_test_checkout_8888"
        session_id = "cs_test_session_123"

        mock_payload = {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "payment_status": "paid",
                    "customer": self.org_a.stripe_customer_id,
                    "client_reference_id": str(self.org_a.id),
                    "metadata": {"organization_id": str(self.org_a.id)},
                }
            },
        }

        # 1. First execution
        success_first = StripeWebhookService.handle_event(mock_payload)
        self.assertTrue(success_first)

        self.org_a.refresh_from_db()
        self.assertEqual(self.org_a.plan, "ENTERPRISE")

        sub = Subscription.objects.get(organization=self.org_a)
        self.assertEqual(sub.plan, "ENTERPRISE")
        self.assertEqual(sub.status, "active")

        # 2. Second execution (identical payload)
        success_second = StripeWebhookService.handle_event(mock_payload)
        self.assertTrue(success_second)

        # Ensure exactly one event log entry was created (Idempotency check)
        self.assertEqual(StripeEventLog.objects.filter(event_id=event_id).count(), 1)

    # Celery Background Task Dispatch
    @patch("core.tasks.send_subscription_welcome_email.delay")
    def test_celery_task_dispatch(self, mock_celery_task):
        """
        Target: Verify Celery background task queuing.
        Scenario: Dispatches welcome email upon subscription upgrade.
        Expected: Task called once with target organization UUID.
        """
        from core.tasks import send_subscription_welcome_email

        send_subscription_welcome_email.delay(str(self.org_a.id))
        mock_celery_task.assert_called_once_with(str(self.org_a.id))