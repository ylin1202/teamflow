import json
import stripe
import logging
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from rest_framework import viewsets, exceptions, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView

from core.models import OrganizationMember, OrganizationInvitation, Project, Subscription
from core.serializers import ProjectSerializer, OrganizationMemberSerializer, OrganizationInvitationSerializer
from core.permissions import IsOrganizationMember, IsOrganizationAdmin, IsOrganizationOwner
from core.services.stripe_service import StripeWebhookService



stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    """
    Stripe Webhook API Endpoint
    注意：金流 Webhook 來自第三方伺服器，必須繞過 Django 的 CSRF 檢查，
    並透過 Stripe Signature Signing Secret 進行安全性驗簽。
    """
    print("[Webhook] Received a webhook request!")

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    # 加這兩行除錯印出
    print(f"DEBUG [Secret in Django]: '{endpoint_secret}'")
    print(f"DEBUG [Header received ]: {sig_header}")

    event = None

    # 1. 簽章驗證 (Signature Verification)
    try:
        # 如果有設定 Secret，先嘗試標準驗簽
        if endpoint_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        else:
            # 沒設定 Secret 時（僅限 local 測試）直接解析 JSON
            import json
            event = json.loads(payload)
            print("[Webhook Warning] No STRIPE_WEBHOOK_SECRET found, parsed raw JSON.")

    except ValueError as e:
        print(f"[Webhook Error] Invalid Payload: {e}")
        logger.error(f"[Webhook Error] Invalid Payload: {e}")
        return HttpResponse(status=400)

    except stripe.error.SignatureVerificationError as e:
        if settings.DEBUG:
            import json
            event = json.loads(payload)
            print("[DEBUG Mode] Signature verification failed, fallbacked to raw JSON for local dev.")
        else:
            print(f"[Webhook Error] Signature Verification Failed: {e}")
            logger.error(f"[Webhook Error] Signature Verification Failed: {e}")
            return HttpResponse(status=400)

    # 2. 呼叫 Service 執行 Redis 鎖 + 冪等性處理
    try:
        StripeWebhookService.handle_event(event)
        print("[Webhook Success] Event processed successfully!")
        return JsonResponse({"status": "success"}, status=200)
    except Exception as e:
        print(f"[Webhook Error] Service Exception: {e}")
        logger.error(f"[Webhook Error] Service Exception: {e}", exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)
    

import traceback

class CreateCheckoutSessionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # 1. 檢查 API Key 是否有正確載入
        if not stripe.api_key:
            print("[Stripe Error]: STRIPE_SECRET_KEY is not configured in settings!")
            return Response({"detail": "Stripe secret key missing"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        price_id = request.data.get("price_id")
        org_id = request.headers.get("X-Organization-ID")

        print(f"DEBUG: Received price_id={price_id}, org_id={org_id}")

        if not price_id or not org_id:
            return Response({"detail": "Missing price_id or X-Organization-ID header"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                client_reference_id=org_id,
                metadata={"organization_id": org_id},
                success_url=f"{frontend_url}/dashboard/billing?success=true",
                cancel_url=f"{frontend_url}/dashboard/billing?canceled=true",
                customer_email=request.user.email,
            )
            return Response({"url": checkout_session.url})
        except Exception as e:
            # 2. 將詳細的錯誤資訊與 Traceback 印到 Terminal Console
            print("[Stripe Checkout Exception]:", str(e))
            traceback.print_exc()
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class SubscriptionStatusView(APIView):
    """
    取得當前 Organization 的訂閱狀態與額度資訊
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return Response({"detail": "Missing X-Organization-ID"}, status=status.HTTP_400_BAD_REQUEST)

        sub = Subscription.objects.filter(organization_id=org_id).first()
        if not sub:
            return Response({
                "plan": "FREE",
                "status": "active",
                "monthly_api_quota": 1000,
            })

        return Response({
            "plan": sub.plan if hasattr(sub, 'plan') else "PRO",
            "status": sub.status,
            "monthly_api_quota": sub.monthly_api_quota,
            "current_period_end": sub.current_period_end,
        })
    

class GoogleLoginView(SocialLoginView):
    """
    接收前端 NextAuth 傳來的 Google Access Token
    1. 驗證 token 是否合規
    2. 首次登入自動創建 User 與預設 Organization (觸發 signal)
    3. 核發 JWT Token 回傳給前端
    """
    adapter_class = GoogleOAuth2Adapter
    

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
    

class MyOrganizationsView(APIView):
    """
    取得當前登入使用者所屬的所有 Organization 清單與角色
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = OrganizationMember.objects.filter(
            user=request.user
        ).select_related("organization")

        data = [
            {
                "id": str(m.organization.id),
                "name": m.organization.name,
                "slug": m.organization.slug,
                "role": m.role,
                "is_owner": m.organization.owner_id == request.user.id
            }
            for m in memberships
        ]
        return Response(data)


class ProjectViewSet(TenantBaseViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer


class OrganizationMemberViewSet(viewsets.ModelViewSet):
    """
    成員管理 ViewSet
    """
    serializer_class = OrganizationMemberSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        org_id = self.request.headers.get('X-Organization-ID')
        if not org_id:
            return OrganizationMember.objects.none()
        return OrganizationMember.objects.filter(organization_id=org_id).select_related('user')

    def destroy(self, request, *args, **kwargs):
        member = self.get_object()
        current_user_member = OrganizationMember.objects.filter(
            organization=member.organization, 
            user=request.user
        ).first()

        if not current_user_member or current_user_member.role not in ['OWNER', 'ADMIN']:
            return Response({'detail': '只有 Owner 或 Admin 可以移除成員。'}, status=status.HTTP_403_FORBIDDEN)

        if member.role == 'OWNER':
            return Response({'detail': '無法移除 Owner 角色。'}, status=status.HTTP_400_BAD_REQUEST)

        return super().destroy(request, *args, **kwargs)


class OrganizationInvitationViewSet(viewsets.ModelViewSet):
    """
    邀請碼發送與管理 ViewSet
    """
    serializer_class = OrganizationInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        org_id = self.request.headers.get('X-Organization-ID')
        if not org_id:
            return OrganizationInvitation.objects.none()
        return OrganizationInvitation.objects.filter(organization_id=org_id)

    def create(self, request, *args, **kwargs):
        org_id = self.request.headers.get('X-Organization-ID')
        if not org_id:
            return Response({'detail': '缺少 X-Organization-ID Header'}, status=status.HTTP_400_BAD_REQUEST)

        current_member = OrganizationMember.objects.filter(
            organization_id=org_id, 
            user=request.user
        ).first()

        if not current_member or current_member.role not in ['OWNER', 'ADMIN']:
            return Response({'detail': '只有 Owner 或 Admin 能發送邀請。'}, status=status.HTTP_403_FORBIDDEN)

        email = request.data.get('email')
        role = request.data.get('role', 'MEMBER')

        invitation, created = OrganizationInvitation.objects.get_or_create(
            organization_id=org_id,
            email=email,
            defaults={'role': role, 'invited_by': request.user}
        )

        serializer = self.get_serializer(invitation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)