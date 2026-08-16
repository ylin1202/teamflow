from rest_framework import permissions
from core.models import OrganizationMember, OrganizationRole

class HasOrganizationRole(permissions.BasePermission):
    """
    Base permission class to check if a user holds the required role within a specific organization.
    """
    allowed_roles = []

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Extract org_id from URL kwargs or request headers
        org_id = view.kwargs.get("org_id") or request.headers.get("X-Organization-ID")
        if not org_id:
            return False

        # Query the user's membership and role in the specified organization
        membership = OrganizationMember.objects.filter(
            organization_id=org_id,
            user=request.user
        ).first()

        if not membership:
            return False

        # Cache the membership record on the request object for downstream views to prevent redundant queries
        request.org_membership = membership
        return membership.role in self.allowed_roles


class IsOrganizationMember(HasOrganizationRole):
    """General member tier: Accessible by OWNER, ADMIN, and MEMBER roles."""
    allowed_roles = [
        OrganizationRole.OWNER, 
        OrganizationRole.ADMIN, 
        OrganizationRole.MEMBER
    ]


class IsOrganizationAdmin(HasOrganizationRole):
    """Admin tier: Restricted to OWNER and ADMIN roles for modifying resources."""
    allowed_roles = [
        OrganizationRole.OWNER, 
        OrganizationRole.ADMIN
    ]


class IsOrganizationOwner(HasOrganizationRole):
    """Owner tier: Restricted exclusively to OWNER for sensitive operations (e.g., deleting workspace, transferring ownership, billing)."""
    allowed_roles = [
        OrganizationRole.OWNER
    ]