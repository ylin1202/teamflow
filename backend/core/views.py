import stripe
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import viewsets, exceptions
from core.permissions import IsOrganizationMember, IsOrganizationAdmin, IsOrganizationOwner
from core.services.stripe_service import StripeWebhookService


@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    """
    Stripe Webhook API Endpoint
    注意：金流 Webhook 來自第三方伺服器，必須繞過 Django 的 CSRF 檢查，
    並透過 Stripe Signature Signing Secret 進行安全性驗簽。
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    event = None

    # 1. 簽章驗證 (Signature Verification)
    try:
        if endpoint_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        else:
            # 開發測試環境未配置 Secret 時解析 JSON
            import json
            event = json.loads(payload)
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)

    # 2. 呼叫 Service 執行 Redis 鎖 + 冪等性處理
    try:
        StripeWebhookService.handle_event(event)
        return JsonResponse({"status": "success"}, status=200)
    except Exception as e:
        return JsonResponse({"error": "Internal server error"}, status=500)
    

class TenantBaseViewSet(viewsets.ModelViewSet):
    """
    多租戶模型 ViewSet 基類：
    1. 自動根據當前 Request 的 Organization ID 過濾 QuerySet (Row-Level 數據隔離)
    2. 自動在 Create 時將物件與當前 Organization 綁定
    3. 根據 HTTP Method 動態配對 RBAC 權限 (GET 需要 Member，POST/PUT 需要 Admin，DELETE 需要 Owner)
    """
    permission_classes = [IsOrganizationMember]

    def get_organization_id(self):
        org_id = self.kwargs.get("org_id") or self.request.headers.get("X-Organization-ID")
        if not org_id:
            raise exceptions.ValidationError({"detail": "X-Organization-ID header or org_id URL kwarg is required."})
        return org_id

    def get_queryset(self):
        """
        核心數據隔離點：覆寫 get_queryset()
        確保任何 DB 查詢語法背後都強制帶有 organization_id 條件
        """
        queryset = super().get_queryset()
        org_id = self.get_organization_id()
        return queryset.filter(organization_id=org_id)

    def perform_create(self, serializer):
        """
        寫入隔離點：建立新資料時，自動寫入對應的 organization_id
        """
        org_id = self.get_organization_id()
        serializer.save(organization_id=org_id)

    def get_permissions(self):
        """
        動態權限分配：
        - 讀取類 (GET, HEAD, OPTIONS) -> 一般 Member 即可
        - 寫入/更新類 (POST, PUT, PATCH) -> 需要 Admin 權限
        - 刪除類 (DELETE) -> 需要 Owner 權限
        """
        if self.action in ["create", "update", "partial_update"]:
            return [IsOrganizationAdmin()]
        elif self.action == "destroy":
            return [IsOrganizationOwner()]
        return [IsOrganizationMember()]