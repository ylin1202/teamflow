import uuid
import json
from unittest.mock import patch
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from core.models import Organization, OrganizationMember, OrganizationRole, StripeEventLog, Subscription, Project
from core.services.stripe_service import StripeWebhookService

User = get_user_model()


class SaasBackendTests(APITestCase):

    def setUp(self):
        """
        測試環境初始化 (Fixture)
        建立 2 個獨立組織 (Company A 與 Company B) 用於多租戶隔離驗證。
        """
        # 1. 建立獨立使用者 User A 與 User B
        self.user_a = User.objects.create_user(username="user_a", email="usera@example.com", password="password123")
        self.user_b = User.objects.create_user(username="user_b", email="userb@example.com", password="password123")

        # 2. 建立 Company A (屬於 User A)
        self.org_a = Organization.objects.create(
            name="Company A", slug="company-a", owner=self.user_a, stripe_customer_id="cus_test_A123", plan="FREE"
        )
        OrganizationMember.objects.create(organization=self.org_a, user=self.user_a, role=OrganizationRole.OWNER)

        # 3. 建立 Company B (屬於 User B)
        self.org_b = Organization.objects.create(
            name="Company B", slug="company-b", owner=self.user_b, stripe_customer_id="cus_test_B456", plan="ENTERPRISE"
        )
        OrganizationMember.objects.create(organization=self.org_b, user=self.user_b, role=OrganizationRole.OWNER)

        # 預先為 API 測試準備路由 URL
        self.usage_url = reverse("project_quota_usage")

    # =========================================================================
    # 測試 1：ProjectQuotaUsageView 配額 API 與多租戶隔離測試
    # =========================================================================
    def test_project_quota_usage_api_success(self):
        """
        測試目標：驗證 GET /api/billing/project-usage/
        情境：User A 帶入 Company A 的 Header 查詢用量配額。
        預期結果：回傳 200 OK，且回傳當前 Plan (FREE) 與正確上限 (5)。
        """
        self.client.force_authenticate(user=self.user_a)

        # 建立 2 個專案，測試 current_projects 計算
        Project.objects.create(organization=self.org_a, name="Project 1")
        Project.objects.create(organization=self.org_a, name="Project 2")

        # 發起 GET 請求，帶上 Org A 的 Header
        response = self.client.get(self.usage_url, HTTP_X_ORGANIZATION_ID=str(self.org_a.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["plan"], "FREE")
        self.assertEqual(response.data["current_projects"], 2)
        self.assertEqual(response.data["max_projects"], 5)

    def test_project_quota_usage_after_upgrade(self):
        """
        測試目標：驗證當 Subscription 升級為 ENTERPRISE 時，API 會優先反映 Subscription 方案
        預期結果：max_projects 應為 50。
        """
        self.client.force_authenticate(user=self.user_a)

        # 建立/更新 Subscription 為 ENTERPRISE
        Subscription.objects.create(
            organization=self.org_a,
            plan="ENTERPRISE",
            status="active",
            stripe_price_id="price_1TydLXCNxWb8kewbppCnxt9M"
        )

        response = self.client.get(self.usage_url, HTTP_X_ORGANIZATION_ID=str(self.org_a.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["plan"], "ENTERPRISE")
        self.assertEqual(response.data["max_projects"], 50)

    def test_project_quota_usage_missing_header(self):
        """
        測試目標：缺少 Header 攔截
        預期結果：回傳 400 Bad Request。
        """
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(self.usage_url) # 故意不安插 HTTP_X_ORGANIZATION_ID
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # =========================================================================
    # 測試 2：Stripe Webhook 冪等性與方案同步測試 (Checkout Session)
    # =========================================================================
    @patch("stripe.checkout.Session.list_line_items")
    def test_stripe_webhook_checkout_completed_idempotency(self, mock_list_line_items):
        """
        【測試目標：驗證 checkout.session.completed 的處理與冪等性】
        情境：Stripe 送出 Enterprise 結帳成功的事件，且連送 2 次。
        預期結果：
        - 第一次：Org.plan 與 Subscription.plan 都被改成 ENTERPRISE。
        - 第二次：觸發 StripeEventLog 冪等攔截，不重複重複更新。
        """
        # Mock Stripe line_items API 回傳的 Price ID
        mock_list_line_items.return_value = {
            "data": [{"price": {"id": "price_1TydLXCNxWb8kewbppCnxt9M"}}]
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
                    "metadata": {"organization_id": str(self.org_a.id)}
                }
            }
        }

        # 1. 第一次呼叫 Webhook Service
        success_first = StripeWebhookService.handle_event(mock_payload)
        self.assertTrue(success_first)

        # 驗證第一次處理後：Org plan 正確變更為 ENTERPRISE
        self.org_a.refresh_from_db()
        self.assertEqual(self.org_a.plan, "ENTERPRISE")
        
        sub = Subscription.objects.get(organization=self.org_a)
        self.assertEqual(sub.plan, "ENTERPRISE")
        self.assertEqual(sub.status, "active")

        # 2. 第二次呼叫『完全相同』的 Webhook
        success_second = StripeWebhookService.handle_event(mock_payload)
        self.assertTrue(success_second)

        # 核心斷言：StripeEventLog 總筆數『依然只有 1 筆』！
        self.assertEqual(StripeEventLog.objects.filter(event_id=event_id).count(), 1)

    # =========================================================================
    # 測試 3：Celery 背景歡迎信任務派發測試
    # =========================================================================
    @patch("core.tasks.send_subscription_welcome_email.delay")
    def test_celery_task_dispatch(self, mock_celery_task):
        """
        測試目標：驗證『Celery 背景任務派發』
        情境：付款完成後，發送歡迎信的 Task 是否有被正確推進 Celery 佇列。
        """
        from core.tasks import send_subscription_welcome_email

        # 模擬呼叫 Celery Task 派發
        send_subscription_welcome_email.delay(str(self.org_a.id))

        # 核心驗證：確認此 Task 確實有被呼叫過 1 次，且參數為 Org A 的 UUID
        mock_celery_task.assert_called_once_with(str(self.org_a.id))