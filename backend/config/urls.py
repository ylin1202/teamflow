"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from core.views import (
    GoogleLoginView, 
    stripe_webhook_view, 
    MyOrganizationsView,
    ProjectViewSet,
    OrganizationMemberViewSet,
    OrganizationInvitationViewSet,
    CreateCheckoutSessionView,
    SubscriptionStatusView,
    QuotaUsageView,
    CustomerPortalView,
    TaskViewSet,
    DocumentViewSet,
    AcceptInvitationView,
    ProjectQuotaUsageView, 
)

# 1. 註冊 ViewSets Router
router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'org-members', OrganizationMemberViewSet, basename='org-member')
router.register(r'invitations', OrganizationInvitationViewSet, basename='invitation')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'documents', DocumentViewSet, basename='document')


# 2. 將所有 API 相關的路由打包在一起 (前面不用再重複寫 api/ 了)
api_patterns = [
    # Auth & Organization
    path('auth/google/', GoogleLoginView.as_view(), name='google_login'),
    path('organizations/me/', MyOrganizationsView.as_view(), name='my_organizations'),
    path('accept-invitation/', AcceptInvitationView.as_view(), name='accept-invitation'),
    
    # Billing & Quota
    path('billing/checkout/', CreateCheckoutSessionView.as_view(), name='billing_checkout'),
    path('billing/subscription/', SubscriptionStatusView.as_view(), name='billing_subscription'),
    path('billing/usage/', QuotaUsageView.as_view(), name='quota_usage'),
    path('billing/project-usage/', ProjectQuotaUsageView.as_view(), name='project_quota_usage'),
    path('billing/portal/', CustomerPortalView.as_view(), name='billing_portal'),
    
    # Router 產生的 ViewSets (projects, tasks, documents...)
    path('', include(router.urls)),

    # API 文件 (Swagger / ReDoc)
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]


# 3. 主路由入口
urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 統一掛載所有 /api/ 開頭的 Endpoint
    path('api/', include(api_patterns)),
    
    # 第三方服務的回呼 (不經過 /api/ 前綴)
    path('webhooks/stripe/', stripe_webhook_view, name='stripe_webhook'),
]