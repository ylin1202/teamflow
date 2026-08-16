from rest_framework import status, permissions
from rest_framework.response import Response

from core.models import Project, Task, Document, Organization, Subscription
from core.serializers import ProjectSerializer, TaskSerializer, DocumentSerializer
from core.permissions import IsOrganizationMember, IsOrganizationAdmin
from core.views.base import TenantBaseViewSet
from core.views.billing import PLAN_PROJECT_LIMITS


class ProjectViewSet(TenantBaseViewSet):
    """
    Workspace Project ViewSet:
    - MEMBER+: List, retrieve, create, and update projects.
    - ADMIN/OWNER: Delete projects.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    def get_permissions(self):
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), IsOrganizationAdmin()]
        return [permissions.IsAuthenticated(), IsOrganizationMember()]

    def get_queryset(self):
        return super().get_queryset().order_by("-updated_at")

    def create(self, request, *args, **kwargs):
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return Response({"detail": "Missing X-Organization-ID header."}, status=status.HTTP_400_BAD_REQUEST)

        org = Organization.objects.filter(id=org_id).first()
        if not org:
            return Response({"detail": "Organization not found."}, status=status.HTTP_404_NOT_FOUND)

        sub = Subscription.objects.filter(organization=org).first()
        plan = (sub.plan if sub and sub.plan else getattr(org, "plan", "FREE") or "FREE").upper()
        max_projects = PLAN_PROJECT_LIMITS.get(plan, 5)

        current_projects = Project.objects.filter(organization=org).count()
        if current_projects >= max_projects:
            return Response(
                {
                    "detail": f"Your current plan ({plan}) allows up to {max_projects} projects. "
                              f"You currently have {current_projects} project(s). "
                              f"Please upgrade your plan in Billing to create more projects."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().create(request, *args, **kwargs)


class TaskViewSet(TenantBaseViewSet):
    """
    Kanban Task ViewSet scoped to Organization and Project.
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]

    def get_permissions(self):
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), IsOrganizationAdmin()]
        return [permissions.IsAuthenticated(), IsOrganizationMember()]

    def get_queryset(self):
        queryset = super().get_queryset().order_by("-updated_at")
        project_id = self.request.query_params.get("project_id")
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
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), IsOrganizationAdmin()]
        return [permissions.IsAuthenticated(), IsOrganizationMember()]

    def get_queryset(self):
        queryset = super().get_queryset().order_by("-updated_at")
        project_id = self.request.query_params.get("project_id")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def perform_create(self, serializer):
        super().perform_create(serializer)
        if self.request.user.is_authenticated:
            serializer.instance.created_by = self.request.user
            serializer.instance.save()