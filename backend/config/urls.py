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
    CustomerPortalView,
    TaskViewSet,
    DocumentViewSet,
    AcceptInvitationView,
    ProjectQuotaUsageView, 
)

# Register ViewSet Routers
router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"org-members", OrganizationMemberViewSet, basename="org-member")
router.register(r"invitations", OrganizationInvitationViewSet, basename="invitation")
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"documents", DocumentViewSet, basename="document")


# Group all API-related routes under a unified namespace
api_patterns = [
    # Auth & Organization
    path("auth/google/", GoogleLoginView.as_view(), name="google_login"),
    path("organizations/me/", MyOrganizationsView.as_view(), name="my_organizations"),
    path("accept-invitation/", AcceptInvitationView.as_view(), name="accept-invitation"),
    
    # Billing & Quotas
    path("billing/checkout/", CreateCheckoutSessionView.as_view(), name="billing_checkout"),
    path("billing/subscription/", SubscriptionStatusView.as_view(), name="billing_subscription"),
    path("billing/project-usage/", ProjectQuotaUsageView.as_view(), name="project_quota_usage"),
    path("billing/portal/", CustomerPortalView.as_view(), name="billing_portal"),
    
    # ViewSet Router endpoints (projects, tasks, documents, etc.)
    path("", include(router.urls)),

    # API Documentation (Swagger / ReDoc)
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]


# Root URL Configuration
urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Mount all API endpoints under the /api/ prefix
    path("api/", include(api_patterns)),
    
    # Third-party service callbacks and webhooks (exempt from /api/ prefix)
    path("webhooks/stripe/", stripe_webhook_view, name="stripe_webhook"),
]