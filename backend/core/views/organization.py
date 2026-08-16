import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.models import Organization, OrganizationMember, OrganizationInvitation, Subscription
from core.serializers import OrganizationMemberSerializer, OrganizationInvitationSerializer
from core.permissions import IsOrganizationMember, IsOrganizationAdmin
from core.tasks import send_invitation_email_task

# Member invitation limits per subscription plan
PLAN_MEMBER_LIMITS = {
    "FREE": 3,
    "PRO": None,        # Unlimited
    "ENTERPRISE": None, # Unlimited
}


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


class OrganizationMemberViewSet(viewsets.ModelViewSet):
    """
    Workspace Member Management ViewSet.
    """
    serializer_class = OrganizationMemberSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        org_id = self.request.headers.get("X-Organization-ID")
        if not org_id:
            return OrganizationMember.objects.none()
        return OrganizationMember.objects.filter(organization_id=org_id).select_related("user")

    def destroy(self, request, *args, **kwargs):
        member = self.get_object()
        current_user_member = OrganizationMember.objects.filter(
            organization=member.organization, 
            user=request.user
        ).first()

        if not current_user_member or current_user_member.role not in ["OWNER", "ADMIN"]:
            return Response({"detail": "Only Workspace Owners or Admins can remove members."}, status=status.HTTP_403_FORBIDDEN)

        if member.role == "OWNER":
            return Response({"detail": "Cannot remove the Workspace Owner."}, status=status.HTTP_400_BAD_REQUEST)

        return super().destroy(request, *args, **kwargs)


class OrganizationInvitationViewSet(viewsets.ModelViewSet):
    """
    Workspace Email Invitation Management ViewSet.
    """
    serializer_class = OrganizationInvitationSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]

    def get_permissions(self):
        if self.action in ["create", "destroy", "update", "partial_update"]:
            return [permissions.IsAuthenticated(), IsOrganizationAdmin()]
        return [permissions.IsAuthenticated(), IsOrganizationMember()]

    def get_queryset(self):
        org_id = self.request.headers.get("X-Organization-ID")
        if not org_id:
            return OrganizationInvitation.objects.none()
        return OrganizationInvitation.objects.filter(organization_id=org_id, is_accepted=False)

    def create(self, request, *args, **kwargs):
        org_id = self.request.headers.get("X-Organization-ID")
        if not org_id:
            return Response({"detail": "Missing X-Organization-ID header."}, status=status.HTTP_400_BAD_REQUEST)

        org = Organization.objects.filter(id=org_id).first()
        if not org:
            return Response({"detail": "Organization not found."}, status=status.HTTP_404_NOT_FOUND)

        email = request.data.get("email", "").strip().lower()
        if not email:
            return Response({"detail": "Please provide a valid email address."}, status=status.HTTP_400_BAD_REQUEST)

        role = request.data.get("role", "MEMBER")

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
                            "detail": f"Your current plan ({plan}) allows up to {member_limit} team members. "
                                      f"You already have {current_members_count} active member(s) and {pending_invites_count} pending invitation(s). "
                                      f"Please upgrade your plan to invite more members."
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

        invitation, created = OrganizationInvitation.objects.get_or_create(
            organization_id=org_id,
            email=email,
            defaults={"role": role, "invited_by": request.user}
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
            defaults={"role": invitation.role}
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