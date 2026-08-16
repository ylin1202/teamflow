import os
import json
import stripe
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from rest_framework import viewsets, exceptions, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView

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

# Project creation limits per subscription plan
PLAN_PROJECT_LIMITS = {
    "FREE": 5,
    "PRO": 25,
    "ENTERPRISE": 150,
}

# Member invitation limits per subscription plan
PLAN_MEMBER_LIMITS = {
    "FREE": 3,
    "PRO": None,        # Unlimited
    "ENTERPRISE": None, # Unlimited
}

stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    """
    Stripe Webhook API Endpoint:
    Exempt from CSRF protection and validates payload authenticity via Stripe signature verification.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    event = None

    # 1. Signature Verification
    try:
        if endpoint_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        else:
            event = json.loads(payload)
            logger.warning("[Webhook Warning] No STRIPE_WEBHOOK_SECRET found, parsed raw JSON.")

    except ValueError as e:
        logger.error(f"[Webhook Error] Invalid Payload: {e}")
        return HttpResponse(status=400)

    except stripe.error.SignatureVerificationError as e:
        if settings.DEBUG:
            event = json.loads(payload)
            logger.warning("[DEBUG Mode] Signature verification failed, falling back to raw JSON for local testing.")
        else:
            logger.error(f"[Webhook Error] Signature Verification Failed: {e}")
            return HttpResponse(status=400)

    # 2. Delegate to Service Layer (Handles Redis distributed locks and DB idempotency)
    try:
        StripeWebhookService.handle_event(event)
        return JsonResponse({"status": "success"}, status=200)
    except Exception as e:
        logger.error(f"[Webhook Error] Service Exception: {e}", exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)


class CreateCheckoutSessionView(APIView):
    """
    Creates a Stripe Checkout Session for upgrading workspace subscription tiers.
    """
    permission_classes = [permissions.IsAuthenticated, IsOrganizationOwner]

    def post(self, request):
        if not stripe.api_key:
            return Response(
                {"detail": "Stripe secret key is not configured."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        price_id = request.data.get("price_id")
        org_id = request.headers.get("X-Organization-ID") or request.data.get("organization_id")

        if not price_id or not org_id:
            return Response(
                {"detail": "Missing price_id or X-Organization-ID header."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
            
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode="payment",
                client_reference_id=org_id,
                metadata={"organization_id": org_id},
                success_url=f"{frontend_url}/dashboard/billing?success=true",
                cancel_url=f"{frontend_url}/dashboard/billing?canceled=true",
                customer_email=request.user.email,
            )
            return Response({"url": checkout_session.url})
        except Exception as e:
            logger.error(f"[Stripe Checkout Exception]: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SubscriptionStatusView(APIView):
    """
    Retrieves current workspace subscription status and quota tier metadata.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return Response({"detail": "Missing X-Organization-ID header."}, status=status.HTTP_400_BAD_REQUEST)

        org = Organization.objects.filter(id=org_id).first()
        if not org:
            return Response({"detail": "Organization not found."}, status=status.HTTP_404_NOT_FOUND)

        sub = Subscription.objects.filter(organization=org).first()
        plan = (sub.plan if sub and sub.plan else getattr(org, "plan", "FREE") or "FREE").upper()
        status_val = sub.status if sub else "active"

        return Response({
            "plan": plan,
            "status": status_val,
            "max_projects": PLAN_PROJECT_LIMITS.get(plan, 5),
            "current_period_end": sub.current_period_end if sub else None,
        })


class GoogleLoginView(SocialLoginView):
    """
    Receives Google Access Token from NextAuth client:
    1. Validates token authenticity against Google OAuth provider.
    2. Provisions User and default Organization on initial registration (via signals).
    3. Issues DRF Auth Token / JWT back to the client.
    """
    adapter_class = GoogleOAuth2Adapter
    

class TenantBaseViewSet(viewsets.ModelViewSet):
    """
    Abstract multi-tenant ViewSet base class:
    1. Enforces row-level tenant isolation by scoping QuerySets to X-Organization-ID.
    2. Automatically associates newly created instances with the target organization.
    3. Dynamically maps HTTP methods to RBAC permission classes.
    """
    permission_classes = [IsOrganizationMember]

    def get_organization_id(self):
        org_id = self.kwargs.get("org_id") or self.request.headers.get("X-Organization-ID")
        if not org_id:
            raise exceptions.ValidationError({"detail": "X-Organization-ID header or org_id URL parameter is required."})
        return org_id

    def get_queryset(self):
        queryset = super().get_queryset()
        org_id = self.get_organization_id()
        return queryset.filter(organization_id=org_id)

    def perform_create(self, serializer):
        org_id = self.get_organization_id()
        serializer.save(organization_id=org_id)

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update"]:
            return [IsOrganizationAdmin()]
        elif self.action == "destroy":
            return [IsOrganizationOwner()]
        return [IsOrganizationMember()]
    

class MyOrganizationsView(APIView):
    """
    Returns list of workspaces associated with the authenticated user.
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
    """
    Workspace Project ViewSet:
    - MEMBER+: List, retrieve, create, and update projects.
    - ADMIN/OWNER: Delete projects.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    def get_permissions(self):
        if self.action == 'destroy':
            return [permissions.IsAuthenticated(), IsOrganizationAdmin()]
        return [permissions.IsAuthenticated(), IsOrganizationMember()]

    def get_queryset(self):
        return super().get_queryset().order_by('-updated_at')

    def create(self, request, *args, **kwargs):
        org_id = request.headers.get('X-Organization-ID')
        if not org_id:
            return Response({'detail': 'Missing X-Organization-ID header.'}, status=status.HTTP_400_BAD_REQUEST)

        org = Organization.objects.filter(id=org_id).first()
        if not org:
            return Response({'detail': 'Organization not found.'}, status=status.HTTP_404_NOT_FOUND)

        sub = Subscription.objects.filter(organization=org).first()
        plan = (sub.plan if sub and sub.plan else getattr(org, "plan", "FREE") or "FREE").upper()
        max_projects = PLAN_PROJECT_LIMITS.get(plan, 5)

        current_projects = Project.objects.filter(organization=org).count()
        if current_projects >= max_projects:
            return Response(
                {
                    'detail': f"Your current plan ({plan}) allows up to {max_projects} projects. "
                              f"You currently have {current_projects} project(s). "
                              f"Please upgrade your plan in Billing to create more projects."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().create(request, *args, **kwargs)
    

class OrganizationMemberViewSet(viewsets.ModelViewSet):
    """
    Workspace Member Management ViewSet.
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
            return Response({'detail': 'Only Workspace Owners or Admins can remove members.'}, status=status.HTTP_403_FORBIDDEN)

        if member.role == 'OWNER':
            return Response({'detail': 'Cannot remove the Workspace Owner.'}, status=status.HTTP_400_BAD_REQUEST)

        return super().destroy(request, *args, **kwargs)


class OrganizationInvitationViewSet(viewsets.ModelViewSet):
    """
    Workspace Email Invitation Management ViewSet.
    """
    serializer_class = OrganizationInvitationSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update']:
            return [permissions.IsAuthenticated(), IsOrganizationAdmin()]
        return [permissions.IsAuthenticated(), IsOrganizationMember()]

    def get_queryset(self):
        org_id = self.request.headers.get('X-Organization-ID')
        if not org_id:
            return OrganizationInvitation.objects.none()
        return OrganizationInvitation.objects.filter(organization_id=org_id, is_accepted=False)

    def create(self, request, *args, **kwargs):
        org_id = self.request.headers.get('X-Organization-ID')
        if not org_id:
            return Response({'detail': 'Missing X-Organization-ID header.'}, status=status.HTTP_400_BAD_REQUEST)

        org = Organization.objects.filter(id=org_id).first()
        if not org:
            return Response({'detail': 'Organization not found.'}, status=status.HTTP_404_NOT_FOUND)

        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response({'detail': 'Please provide a valid email address.'}, status=status.HTTP_400_BAD_REQUEST)

        role = request.data.get('role', 'MEMBER')

        sub = Subscription.objects.filter(organization=org).first()
        plan = (sub.plan if sub and sub.plan else getattr(org, "plan", "FREE") or "FREE").upper()
        member_limit = PLAN_MEMBER_LIMITS.get(plan)
        
        if member_limit is not None:
            is_already_invited = OrganizationInvitation.objects.filter(
                organization_id=org_id, 
                email=email, 
                is_accepted=False
            ).exists()

            if not is_already_invited:
                current_members_count = OrganizationMember.objects.filter(organization_id=org_id).count()
                pending_invites_count = OrganizationInvitation.objects.filter(organization_id=org_id, is_accepted=False).count()
                total_occupied = current_members_count + pending_invites_count

                if total_occupied >= member_limit:
                    return Response(
                        {
                            'detail': f"Your current plan ({plan}) allows up to {member_limit} team members. "
                                      f"You already have {current_members_count} active member(s) and {pending_invites_count} pending invitation(s). "
                                      f"Please upgrade your plan to invite more members."
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

        invitation, created = OrganizationInvitation.objects.get_or_create(
            organization_id=org_id,
            email=email,
            defaults={'role': role, 'invited_by': request.user}
        )

        if not created:
            invitation.role = role
            invitation.token = secrets.token_urlsafe(32)
            invitation.expires_at = timezone.now() + timedelta(days=7)
            invitation.save()

        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        accept_url = f"{frontend_url}/invite/accept?token={invitation.token}"

        send_invitation_email_task.delay(
            email=email,
            organization_name=invitation.organization.name,
            accept_url=accept_url,
            sender_email=request.user.email,
            role=role
        )

        serializer = self.get_serializer(invitation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    

class AcceptInvitationView(APIView):
    """
    Accepts workspace invitation token sent via email.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response({"error": "Missing token."}, status=status.HTTP_400_BAD_REQUEST)

        invitation = OrganizationInvitation.objects.filter(token=token, is_accepted=False).first()
        if not invitation:
            return Response({"error": "Invalid or expired invitation token."}, status=status.HTTP_404_NOT_FOUND)

        if invitation.expires_at < timezone.now():
            return Response({"error": "This invitation link has expired. Please ask the administrator to re-send it."}, status=status.HTTP_400_BAD_REQUEST)

        user_email = request.user.email.strip().lower()
        invite_email = invitation.email.strip().lower()

        if user_email != invite_email:
            return Response(
                {"error": f"This invitation was sent to {invitation.email}, but you are logged in as {request.user.email}."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        member, created = OrganizationMember.objects.get_or_create(
            organization=invitation.organization,
            user=request.user,
            defaults={'role': invitation.role}
        )
        if not created:
            member.role = invitation.role
            member.save()

        invitation.is_accepted = True
        invitation.save()

        return Response({
            "message": f"Successfully joined {invitation.organization.name}!",
            "organization_id": str(member.organization.id),
            "organization_name": member.organization.name
        })


class CustomerPortalView(APIView):
    """
    Creates a Stripe Customer Portal session for billing and invoice management.
    """
    permission_classes = [permissions.IsAuthenticated, IsOrganizationOwner]

    def post(self, request):
        org = getattr(request, "organization", None) or getattr(request.user, "organization", None)
        if not org:
            return Response({"error": "No organization associated with current user."}, status=status.HTTP_400_BAD_REQUEST)

        customer_id = getattr(org, "stripe_customer_id", None)
        if not customer_id:
            return Response(
                {"error": "No Stripe Customer ID found. Please complete a payment first."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=f"{frontend_url}/billing",
            )
            return Response({"url": portal_session.url})
        except Exception as e:
            logger.error(f"Failed to create Stripe portal session: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TaskViewSet(TenantBaseViewSet):
    """
    Kanban Task ViewSet scoped to Organization and Project.
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]

    def get_permissions(self):
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
    Project Documentation ViewSet for Markdown specs.
    """
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer 
    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]

    def get_permissions(self):
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
    Returns current project creation count and maximum allowed quota for the workspace.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return Response(
                {"detail": "Missing X-Organization-ID header."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        org = Organization.objects.filter(id=org_id).first()
        if not org:
            return Response(
                {"detail": "Organization not found."}, 
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