import uuid6
import secrets

from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.serializers.json import DjangoJSONEncoder


# UUIDv7 generator callable for Django ORM field defaults
def generate_uuidv7():
    return uuid6.uuid7()

def get_default_invitation_expiration():
    return timezone.now() + timedelta(days=7)

# Abstract Base Model
class BaseModel(models.Model):
    """
    Abstract base class for models:
    1. Uses UUIDv7 as Primary Key (time-ordered + non-enumerable)
    2. Automatically tracks creation and update timestamps
    """
    id = models.UUIDField(
        primary_key=True, 
        default=generate_uuidv7, 
        editable=False,
        help_text="UUIDv7 (Time-ordered Universally Unique Identifier)"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# Custom User Model
class User(AbstractUser):
    """
    Custom User model utilizing UUIDv7 primary keys.
    """
    id = models.UUIDField(
        primary_key=True, 
        default=generate_uuidv7, 
        editable=False
    )
    email = models.EmailField(_("email address"), unique=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "saas_user"

    def __str__(self):
        return self.email


# Organization / Workspace Model
class Organization(BaseModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, help_text="Workspace URL slug")
    
    # Stripe Customer ID scoped to the Organization level
    stripe_customer_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True, db_index=True
    )

    # Cached plan identifier for quick API retrieval (default: FREE)
    plan = models.CharField(
        max_length=20,
        default="FREE",
        help_text="Current plan: FREE (5), PRO (25), ENTERPRISE (150)"
    )
    
    owner = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="owned_organizations"
    )
    members = models.ManyToManyField(
        User, through="OrganizationMember", related_name="organizations"
    )

    class Meta:
        db_table = "saas_organization"

    def __str__(self):
        return f"{self.name} [{self.plan}]"


# Organization RBAC Roles and Membership
class OrganizationRole(models.TextChoices):
    OWNER = "OWNER", _("Owner")
    ADMIN = "ADMIN", _("Admin")
    MEMBER = "MEMBER", _("Member")


class OrganizationMember(BaseModel):
    """
    Many-to-many intermediate model between User and Organization for RBAC.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=20, 
        choices=OrganizationRole.choices, 
        default=OrganizationRole.MEMBER
    )

    class Meta:
        db_table = "saas_organization_member"
        unique_together = ("organization", "user")

    def __str__(self):
        return f"{self.user.email} - {self.organization.name} ({self.role})"


# Subscription Status Choices
class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    PAST_DUE = "past_due", _("Past Due")
    CANCELED = "canceled", _("Canceled")
    CANCELING = "canceling", _("Canceling at Period End")
    INCOMPLETE = "incomplete", _("Incomplete")


# Subscription Plan Tier Choices
class SubscriptionPlan(models.TextChoices):
    FREE = "FREE", _("Free Tier")
    PRO = "PRO", _("Pro Plan")
    ENTERPRISE = "ENTERPRISE", _("Enterprise")


# Organization Subscription & Quotas
class Subscription(BaseModel):
    """
    Tracks Stripe subscription metadata and project quota limits per organization.
    """
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="subscription"
    )
    
    # Stripe billing identifiers
    stripe_subscription_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True, db_index=True
    )
    stripe_customer_id = models.CharField(
        max_length=255, null=True, blank=True, db_index=True
    )
    stripe_price_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Tier and Lifecycle Status
    plan = models.CharField(
        max_length=20,
        choices=SubscriptionPlan.choices,
        default=SubscriptionPlan.FREE
    )
    status = models.CharField(
        max_length=20, 
        choices=SubscriptionStatus.choices, 
        default=SubscriptionStatus.ACTIVE
    )
    
    # Quota Limits (Free: 5, Pro: 25, Enterprise: 150)
    max_projects = models.IntegerField(default=5, help_text="Maximum allowed projects for this plan")
    
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "saas_subscription"

    def __str__(self):
        return f"{self.organization.name} - {self.plan} ({self.status})"
    

# Stripe Webhook Audit & Idempotency Log
class StripeEventLog(BaseModel):
    """
    Ensures webhook idempotency and maintains an audit log for billing events.
    """
    class EventStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        PROCESSED = "processed", _("Processed")
        FAILED = "failed", _("Failed")

    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    type = models.CharField(max_length=255, help_text="Stripe event type, e.g., checkout.session.completed")
    
    status = models.CharField(
        max_length=20, 
        choices=EventStatus.choices, 
        default=EventStatus.PENDING
    )
    
    payload = models.JSONField(encoder=DjangoJSONEncoder, default=dict)
    error_message = models.TextField(null=True, blank=True)
    
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "saas_stripe_event_log"

    def __str__(self):
        return f"{self.event_id} - {self.type} ({self.status})"
    

# Workspace Project Model
class Project(BaseModel):
    """
    Project model scoped to an Organization.
    """
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.CASCADE, 
        related_name="projects"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    
    class Meta:
        db_table = "saas_project"

    def __str__(self):
        return f"{self.name} ({self.organization.name})"
    
    
# Organization Member Invitation Model
class OrganizationInvitation(BaseModel):
    """
    Tracks pending email invitations to join a workspace.
    """
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.CASCADE, 
        related_name="invitations"
    )
    email = models.EmailField(_("invited email"))
    role = models.CharField(
        max_length=20, 
        choices=OrganizationRole.choices, 
        default=OrganizationRole.MEMBER
    )
    invited_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name="sent_invitations"
    )
    is_accepted = models.BooleanField(default=False)
    
    token = models.CharField(
        max_length=64, 
        unique=True, 
        null=True, 
        blank=True,
        help_text="Unique invitation token"
    )
    
    expires_at = models.DateTimeField(
        default=get_default_invitation_expiration,
        help_text="Expiration timestamp for the invitation link (defaults to 7 days)"
    )

    class Meta:
        db_table = "saas_organization_invitation"
        unique_together = ("organization", "email")

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invite {self.email} to {self.organization.name} as {self.role}"
    
    
# Kanban Task Model
class TaskStatus(models.TextChoices):
    TODO = "todo", _("To Do")
    IN_PROGRESS = "in_progress", _("In Progress")
    DONE = "done", _("Done")


class Task(BaseModel):
    """
    Kanban task model scoped to both Project and Organization.
    """
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="tasks"
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="tasks"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.TODO
    )
    assignee = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tasks"
    )

    class Meta:
        db_table = "saas_task"

    def __str__(self):
        return f"{self.title} [{self.status}]"


# Markdown Specification & Documentation Model
class Document(BaseModel):
    """
    Project-level Markdown documentation and specification sheets.
    """
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="documents"
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="documents"
    )
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, default="", help_text="Raw Markdown content")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_documents"
    )

    class Meta:
        db_table = "saas_document"

    def __str__(self):
        return f"{self.title} ({self.project.name})"