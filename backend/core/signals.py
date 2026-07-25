import uuid
from django.dispatch import receiver
from allauth.account.signals import user_signed_up
from django.utils.text import slugify
from core.models import Organization, OrganizationMember, OrganizationRole


# @receiver 裝飾器：監聽 allauth 的 user_signed_up 訊號
# 觸發時機：當「新使用者」第一次透過 Google 授權登入並在資料庫建立 User 記錄時
@receiver(user_signed_up)
def create_default_organization_on_google_signup(request, user, **kwargs):
    """
    【自動化初始化邏輯】
    當使用者透過 Google 首次註冊成功時，自動為他建立預設 Organization 並將其設為 Owner。
    """
    # 1. 取得組織預設名稱：優先拿 Google 的 first_name，拿不到就拿 Email 前綴 (例如 john@gmail.com -> john)
    base_name = user.first_name or user.email.split('@')[0]
    
    # 2. 轉換成 URL 安全字串 (Slug)，並附加 6 碼隨機 HEX 防止重複 (例如: johns-team-a1b2c3)
    base_slug = slugify(base_name) or "team"
    unique_slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    # 3. 建立該使用者的預設 Organization (例如: "John's Team")
    org = Organization.objects.create(
        name=f"{base_name}'s Team",
        slug=unique_slug,
        owner=user
    )

    # 4. 寫入 OrganizationMember 中間表，給予最高權限 OWNER 角色
    OrganizationMember.objects.create(
        organization=org,
        user=user,
        role=OrganizationRole.OWNER
    )