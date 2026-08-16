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
    Automatically creates a default Organization and assigns the user as Owner upon registration.
    """
    if created:
        base_name = instance.first_name or instance.email.split("@")[0]
        base_slug = slugify(base_name) or "team"
        unique_slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        # Create the default Organization (escaped double quote to fix syntax)
        org = Organization.objects.create(
            name=f"{base_name}'s Team",
            slug=unique_slug,
            owner=instance
        )

        # Add the user to the OrganizationMember junction table as OWNER
        OrganizationMember.objects.create(
            organization=org,
            user=instance,
            role=OrganizationRole.OWNER
        )