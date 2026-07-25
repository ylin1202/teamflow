import uuid
import json
from unittest.mock import patch
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from core.models import Organization, OrganizationMember, OrganizationRole, StripeEventLog, Subscription
from core.services.stripe_service import StripeWebhookService

User = get_user_model()


class SaasBackendTests(APITestCase):

    def setUp(self):
        """
        測試環境初始化 (Fixture)
        在執行下方『每一個』測試案例之前，Django 都會自動執行 setUp() 建立乾淨的測試資料。
        這裡建立了 2 個完全獨立的組織 (Company A 與 Company B) 及各自的老闆，
        用來測試多租戶資料隔離 (Multi-Tenant Isolation)。
        """
        # 1. 建立兩個獨立的使用者 User A 與 User B
        self.user_a = User.objects.create_user(username="user_a", email="usera@example.com", password="password123")
        self.user_b = User.objects.create_user(username="user_b", email="userb@example.com", password="password123")

        # 2. 建立 Company A (屬於 User A)
        self.org_a = Organization.objects.create(
            name="Company A", slug="company-a", owner=self.user_a, stripe_customer_id="cus_test_A123"
        )
        OrganizationMember.objects.create(organization=self.org_a, user=self.user_a, role=OrganizationRole.OWNER)

        # 3. 建立 Company B (屬於 User B)
        self.org_b = Organization.objects.create(
            name="Company B", slug="company-b", owner=self.user_b, stripe_customer_id="cus_test_B456"
        )
        OrganizationMember.objects.create(organization=self.org_b, user=self.user_b, role=OrganizationRole.OWNER)

    # =========================================================================
    # 測試 1：多租戶資料隔離與越權存取防護 (Tenant Isolation & RBAC)
    # =========================================================================
    def test_tenant_isolation_prevent_cross_tenant_access(self):
        """
        測試目標：驗證『防駭客越權存取 (IDOR)』
        情境：User A (公司 A 的人) 試圖在 Header 帶入 Company B 的 org_id 來窺探/操作 Company B 的資料。
        預期結果：系統的 RBAC 門禁卡 (Custom Permission) 必須硬性攔截，回傳 403 Forbidden 拒絕存取。
        """
        # 模擬 User A 登入系統
        self.client.force_authenticate(user=self.user_a)

        # 取得 API 網址
        url = reverse("stripe-webhook") # 實務上可替換為 /api/projects/ 等 API

        # User A 發起請求，但在 Header 故意偽造別人的 ID (HTTP_X_ORGANIZATION_ID = Company B 的 ID)
        response = self.client.get(url, HTTP_X_ORGANIZATION_ID=str(self.org_b.id))
        
        # 核心斷言 (Assert)：驗證 Response 狀態碼是不是 403 (無權存取) 或 405 (方法不支援)，證明被成功擋下！
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED])

    # =========================================================================
    # 測試 2：Stripe Webhook 冪等性與 Redis 分散式鎖 (Idempotency & Lock)
    # =========================================================================
    def test_stripe_webhook_idempotency(self):
        """
        【測試目標：驗證『冪等性 (防重複扣款/重複發放點數)』】
        情境：當 Stripe 因為網路問題重發了 2 次『一模一樣』的 Webhook 通知時。
        預期結果：
        - 第一次呼叫：成功處理，寫入 DB 並將訂閱狀態改為 active。
        - 第二次呼叫：觸發 Idempotency 機制，直接跳過，DB 的 Log 筆數依然只有 1 筆。
        """
        event_id = "evt_test_unique_9999"
        
        # 模擬 Stripe 傳過來的假資料 (Payload)
        mock_payload = {
            "id": event_id,
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "customer": self.org_a.stripe_customer_id,
                    "id": "sub_test_123",
                    "status": "active",
                    "items": {"data": [{"price": {"id": "price_pro_plan"}}]}
                }
            }
        }

        # 1. 第一次呼叫 Webhook Service
        success_first = StripeWebhookService.handle_event(mock_payload)
        self.assertTrue(success_first)
        
        # 驗證第一次處理後：DB 紀錄為 1 筆，且訂閱狀態成功變更為 active
        self.assertEqual(StripeEventLog.objects.filter(event_id=event_id).count(), 1)
        sub = Subscription.objects.get(organization=self.org_a)
        self.assertEqual(sub.status, "active")

        # 2. 第二次呼叫『完全相同』的 Webhook (模擬網路重試 Retry)
        success_second = StripeWebhookService.handle_event(mock_payload)
        self.assertTrue(success_second)

        # 核心驗證：EventLog 的總筆數『依然是 1』！代表第二次被冪等機制攔截，沒有重複寫入！
        self.assertEqual(StripeEventLog.objects.filter(event_id=event_id).count(), 1)

    # =========================================================================
    # 測試 3：Celery 異步背景任務派發 (Celery Async Task)
    # =========================================================================
    # @patch 是 Python 的『替身/模擬』工具：
    # 因為測試時我們不希望真的連到 RabbitMQ 去寄出一封真實的 Email，
    # 所以用 mock_celery_task 替身攔截 .delay() 動作。
    @patch("core.tasks.send_subscription_welcome_email.delay")
    def test_celery_task_dispatch(self, mock_celery_task):
        """
        測試目標：驗證『Celery 背景任務派發』
        情境：金流處理完成後，系統是否有將『寄送信件』的任務推入 Celery/RabbitMQ 佇列？
        預期結果：`send_subscription_welcome_email.delay()` 確實被呼叫了一次，且帶入正確的 org_id。
        """
        from core.tasks import send_subscription_welcome_email
        
        # 模擬呼叫 Celery Task 的 .delay() 派發動作
        send_subscription_welcome_email.delay(str(self.org_a.id))

        # 核心驗證：確認這個替身 (mock_celery_task) 確實有被呼叫過 1 次，且帶入的參數正是 Company A 的 UUID！
        mock_celery_task.assert_called_once_with(str(self.org_a.id))