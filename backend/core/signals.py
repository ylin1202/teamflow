from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
import uuid
from django.utils.text import slugify
from core.models import Organization, OrganizationMember, OrganizationRole

User = get_user_model()

@receiver(post_save, sender=User)
def create_default_organization_on_user_created(sender, instance, created, **kwargs):
    """
    當資料庫新增 User 記錄時，自動建立預設 Organization 並將其設為 Owner
    """
    if created:
        base_name = instance.first_name or instance.email.split('@')[0]
        base_slug = slugify(base_name) or "team"
        unique_slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        # 1. 建立預設 Organization
        org = Organization.objects.create(
            name=f"{base_name}'s Team",
            slug=unique_slug,
            owner=instance
        )

        # 2. 寫入 OrganizationMember 中間表
        OrganizationMember.objects.create(
            organization=org,
            user=instance,
            role=OrganizationRole.OWNER
        )