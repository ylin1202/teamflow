from rest_framework import viewsets, exceptions
from core.permissions import IsOrganizationMember, IsOrganizationAdmin, IsOrganizationOwner


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