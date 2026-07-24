from rest_framework import permissions
from core.models import OrganizationMember, OrganizationRole

class HasOrganizationRole(permissions.BasePermission):
    """
    檢查 User 在特定 Organization 中是否具備指定角色的權限基類
    """
    allowed_roles = []

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # 從 URL kwargs 或是 Request Header/Query 中取得 org_id
        org_id = view.kwargs.get("org_id") or request.headers.get("X-Organization-ID")
        if not org_id:
            return False

        # 查詢目前使用者在該組織的中間表紀錄與角色
        membership = OrganizationMember.objects.filter(
            organization_id=org_id,
            user=request.user
        ).first()

        if not membership:
            return False

        # 將當前 membership 暫存於 request 物件，方便 View 內部後續調用，避免二次 Query
        request.org_membership = membership
        return membership.role in self.allowed_roles


class IsOrganizationMember(HasOrganizationRole):
    """一般成員層級：OWNER, ADMIN, MEMBER 皆可讀取"""
    allowed_roles = [
        OrganizationRole.OWNER, 
        OrganizationRole.ADMIN, 
        OrganizationRole.MEMBER
    ]


class IsOrganizationAdmin(HasOrganizationRole):
    """管理員層級：僅 OWNER, ADMIN 可執行編輯/刪除"""
    allowed_roles = [
        OrganizationRole.OWNER, 
        OrganizationRole.ADMIN
    ]


class IsOrganizationOwner(HasOrganizationRole):
    """最高權限層級：僅 OWNER 可執行敏感情節（如解散團隊、轉讓權限、解約）"""
    allowed_roles = [
        OrganizationRole.OWNER
    ]