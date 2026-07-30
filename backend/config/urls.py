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
    CancelSubscriptionView,
    ExecuteCoreTaskView,
    ReactivateSubscriptionView,
    CustomerPortalView
)


# 建立 DefaultRouter 並註冊 ViewSets
router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'org-members', OrganizationMemberViewSet, basename='org-member')
router.register(r'invitations', OrganizationInvitationViewSet, basename='invitation')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/google/', GoogleLoginView.as_view(), name='google_login'),
    path('api/organizations/me/', MyOrganizationsView.as_view(), name='my_organizations'),
    path('api/billing/checkout/', CreateCheckoutSessionView.as_view(), name='billing_checkout'),
    path('api/billing/subscription/', SubscriptionStatusView.as_view(), name='billing_subscription'),
    
    path('api/billing/usage/', QuotaUsageView.as_view(), name='quota_usage'),
    path('api/billing/portal/', CustomerPortalView.as_view(), name='billing_portal'),
    path('api/billing/subscription/cancel/', CancelSubscriptionView.as_view(), name='cancel_subscription'),
    path('api/billing/subscription/reactivate/', ReactivateSubscriptionView.as_view(), name='reactivate_subscription'),
    path("api/tasks/execute/", ExecuteCoreTaskView.as_view(), name="task-execute"),
    
    path('webhooks/stripe/', stripe_webhook_view, name='stripe_webhook'),
    
    # 自動生成 /api/projects/、/api/org-members/ 與 /api/invitations/ 的路由
    path('api/', include(router.urls)),

    # -------------------------------------------------------------------------
    # 2. OpenAPI 3 Schema & Swagger / Redoc 文件路由
    # -------------------------------------------------------------------------
    # 下載/產生 OpenAPI Schema JSON
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    
    # Swagger UI 網頁介面
    path('api/docs/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # ReDoc 網頁介面
    path('api/docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]