import os
import json
import stripe
import logging
import redis
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator

from rest_framework import viewsets, exceptions, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView


from core.decorators import enforce_quota
from core.models import (
    OrganizationMember,
    OrganizationInvitation,
    Project,
    Subscription,
    Organization,
    Task,
    Document,
)
from core.serializers import (
    ProjectSerializer,
    OrganizationMemberSerializer,
    OrganizationInvitationSerializer,
    TaskSerializer,
    DocumentSerializer,
)
from core.permissions import IsOrganizationMember, IsOrganizationAdmin, IsOrganizationOwner
from core.services.stripe_service import StripeWebhookService
from core.tasks import send_invitation_email_task

# 定義各方案的專案數量上限
PLAN_PROJECT_LIMITS = {
    "FREE": 5,
    "PRO": 25,
    "ENTERPRISE": 150,
}

PLAN_MEMBER_LIMITS = {
    "FREE": 3,
    "PRO": None,        # 無限制
    "ENTERPRISE": None, # 無限制
}


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
r = redis.Redis.from_url(REDIS_URL)

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

    print(f"DEBUG [Secret in Django]: '{endpoint_secret}'")
    print(f"DEBUG [Header received ]: {sig_header}")

    event = None

    # 1. 簽章驗證 (Signature Verification)
    try:
        if endpoint_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        else:
            event = json.loads(payload)
            print("[Webhook Warning] No STRIPE_WEBHOOK_SECRET found, parsed raw JSON.")

    except ValueError as e:
        print(f"[Webhook Error] Invalid Payload: {e}")
        logger.error(f"[Webhook Error] Invalid Payload: {e}")
        return HttpResponse(status=400)

    except stripe.error.SignatureVerificationError as e:
        if settings.DEBUG:
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
                "cancel_at_period_end": False,
            })

        # 判斷是否處於預約取消狀態
        is_canceling = bool(sub.cancel_at_period_end or sub.status == "canceling")

        return Response({
            "plan": getattr(sub, 'plan', 'PRO'),
            "status": "canceling" if is_canceling else sub.status, # 若預約取消，狀態統一回傳 canceling
            "monthly_api_quota": sub.monthly_api_quota,
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": is_canceling,
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
    

class QuotaUsageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # 1. 雙重保險抓取 Organization
        org = getattr(request, 'organization', None)
        
        # 2. 若 Middleware 未注入，從 Header 拿 X-Organization-ID
        if not org:
            org_id = request.headers.get("X-Organization-ID")
            if org_id:
                # 💡 修復處：先找該使用者是否有這間 Org 的 Member 紀錄
                member = OrganizationMember.objects.filter(
                    user=request.user, 
                    organization_id=org_id
                ).select_related('organization').first()
                
                if member:
                    org = member.organization

        # 3. 若 Header 也沒帶，預設抓該使用者所屬的第一個 Organization
        if not org:
            member = OrganizationMember.objects.filter(
                user=request.user
            ).select_related('organization').first()
            
            if member:
                org = member.organization

        # 4. 如果完全找不到任何 Org
        if not org:
            return Response(
                {"error": "No organization found for this user."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 5. 取得 Subscription 限額上限
        sub = Subscription.objects.filter(organization=org).first()
        limit = sub.monthly_api_quota if sub else 1000

        # 6. 讀取 Redis 當月 API 用量
        current_month = timezone.now().strftime("%Y-%m")
        redis_key = f"quota:org:{org.id}:{current_month}:used"

        used_val = r.get(redis_key)
        used = int(used_val.decode('utf-8')) if used_val else 0

        return Response({
            "used": used,
            "limit": limit,
            "remaining": max(0, limit - used),
            "percentage": round((used / limit) * 100, 2) if limit > 0 else 0.0,
            "month": current_month,
        })
    

class CustomerPortalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 1. 取得當前請求的 Organization
        org = getattr(request, "organization", None) or getattr(request.user, "organization", None)
        if not org:
            return Response({"error": "No organization associated with current user."}, status=400)

        # 2. 直接從 Organization 取得 stripe_customer_id
        customer_id = getattr(org, "stripe_customer_id", None)

        if not customer_id:
            return Response(
                {"error": "No Stripe Customer ID found. Please complete a payment first."}, 
                status=400
            )

        try:
            # 3. 建立 Stripe Customer Portal Session
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=f"{frontend_url}/billing",
            )
            return Response({"url": portal_session.url})
        except Exception as e:
            logger.error(f"Failed to create Stripe portal session: {str(e)}")
            return Response({"error": str(e)}, status=500)
        


class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return Response({"error": "Missing X-Organization-ID header."}, status=400)

        sub = Subscription.objects.filter(organization_id=org_id).first()
        if not sub:
            return Response({"error": "No subscription found for this organization."}, status=404)

        if sub.stripe_subscription_id and sub.stripe_subscription_id.startswith("sub_"):
            try:
                stripe.Subscription.modify(
                    sub.stripe_subscription_id,
                    cancel_at_period_end=True
                )
            except stripe.error.StripeError as e:
                logger.warning(f"Stripe API Cancel Notice: {str(e)}")

        # 同時更新 status 與 cancel_at_period_end 欄位
        sub.status = "canceling"
        sub.cancel_at_period_end = True
        sub.save()

        return Response({
            "message": "Subscription will be canceled at the end of current billing period.",
            "status": "canceling",
            "cancel_at_period_end": True
        })
    

class ExecuteCoreTaskView(APIView):
    """
    模擬耗用 API 配額的核心業務 API
    """
    permission_classes = [IsAuthenticated]

    @method_decorator(enforce_quota)
    def post(self, request):
        return Response({
            "status": "success",
            "message": "Task executed successfully! 1 API quota consumed."
        })
    
class ReactivateSubscriptionView(APIView):
    """
    將即將到期的訂閱恢復為自動續訂 (cancel_at_period_end = False)
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return Response({"error": "Missing X-Organization-ID header."}, status=status.HTTP_400_BAD_REQUEST)

        sub = Subscription.objects.filter(organization_id=org_id).first()
        if not sub or not sub.stripe_subscription_id:
            return Response({"error": "No subscription found to reactivate."}, status=status.HTTP_404_NOT_FOUND)

        try:
            # 呼叫 Stripe API 關閉取消預定
            stripe.Subscription.modify(
                sub.stripe_subscription_id,
                cancel_at_period_end=False
            )
            sub.cancel_at_period_end = False
            sub.status = "active"
            sub.save()

            return Response({
                "message": "Subscription reactivated successfully!",
                "status": "active"
            })
        except Exception as e:
            logger.error(f"Failed to reactivate subscription: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TaskViewSet(TenantBaseViewSet):
    """
    看板任務 ViewSet
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    
    # 允許所有團隊成員（MEMBER / ADMIN / OWNER）檢視、新增與更新狀態 (包含拖曳移動)
    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]

    def get_permissions(self):
        # 僅刪除動作需要 ADMIN 以上權限
        if self.action == 'destroy':
            return [permissions.IsAuthenticated(), IsOrganizationAdmin()]
        return [permissions.IsAuthenticated(), IsOrganizationMember()]

    def get_queryset(self):
        queryset = super().get_queryset().order_by('-updated_at')
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset


class DocumentViewSet(TenantBaseViewSet):
    """
    專案 Markdown 文件 ViewSet
    """
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer 
    
    # 允許所有團隊成員（MEMBER / ADMIN / OWNER）閱讀與編輯文件內文
    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]

    def get_permissions(self):
        # 僅刪除動作需要 ADMIN 以上權限
        if self.action == 'destroy':
            return [permissions.IsAuthenticated(), IsOrganizationAdmin()]
        return [permissions.IsAuthenticated(), IsOrganizationMember()]

    def get_queryset(self):
        queryset = super().get_queryset().order_by('-updated_at')
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def perform_create(self, serializer):
        super().perform_create(serializer)
        if self.request.user.is_authenticated:
            serializer.instance.created_by = self.request.user
            serializer.instance.save()


class ProjectQuotaUsageView(APIView):
    """
    取得當前 Organization 的 Project 建立數量與方案上限配額
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return Response(
                {"detail": "Missing X-Organization-ID header"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        org = Organization.objects.filter(id=org_id).first()
        if not org:
            return Response(
                {"detail": "Organization not found"}, 
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