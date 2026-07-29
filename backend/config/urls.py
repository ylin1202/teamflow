"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
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
    ExecuteCoreTaskView
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
    path("api/tasks/execute/", ExecuteCoreTaskView.as_view(), name="task-execute"),
    
    path('webhooks/stripe/', stripe_webhook_view, name='stripe_webhook'),
    
    # 自動生成 /api/projects/、/api/org-members/ 與 /api/invitations/ 的路由
    path('api/', include(router.urls)),
]