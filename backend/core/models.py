import uuid6
import secrets

from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.serializers.json import DjangoJSONEncoder


# 定義 UUIDv7 產生器函數，供 Django ORM default 呼叫
def generate_uuidv7():
    return uuid6.uuid7()

def get_default_invitation_expiration():
    return timezone.now() + timedelta(days=7)

# ==========================================
# 1. 核心抽象模型 (Base Model)
# ==========================================
class BaseModel(models.Model):
    """
    所有模型的抽象基類：
    1. 使用 UUIDv7 作為 Primary Key（時間排序 + 不可枚舉）
    2. 自動紀錄建立與更新時間
    """
    id = models.UUIDField(
        primary_key=True, 
        default=generate_uuidv7, 
        editable=False,
        help_text="UUIDv7 (Time-ordered Universally Unique Identifier)"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)  # 統一由 BaseModel 提供更新時間

    class Meta:
        abstract = True


# ==========================================
# 2. 客製化 User 模型
# ==========================================
class User(AbstractUser):
    """
    客製化 User 模型，主鍵繼承使用 UUIDv7
    """
    id = models.UUIDField(
        primary_key=True, 
        default=generate_uuidv7, 
        editable=False
    )
    email = models.EmailField(_("email address"), unique=True)
    
    # 補上建立與更新時間戳記
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "saas_user"

    def __str__(self):
        return self.email


# ==========================================
# 3. 組織/團隊模型 (Organization - Multi-Tenancy 核心)
# ==========================================
class Organization(BaseModel):
    """
    多租戶 (Tenant) 核心。商業資料完全以此作為隔離邊界。
    """
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, help_text="團隊專屬 URL 縮寫")
    
    # Stripe Customer ID 綁定在組織（租戶）層級
    stripe_customer_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True, db_index=True
    )

    # 增加 plan 欄位方便 API 直接讀取，預設為 FREE
    plan = models.CharField(
        max_length=20,
        default="FREE",
        help_text="當前方案: FREE (5), PRO (30), ENTERPRISE (100)"
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


# ==========================================
# 4. 組織成員與 RBAC 權限模型
# ==========================================
class OrganizationRole(models.TextChoices):
    OWNER = "OWNER", _("Owner")
    ADMIN = "ADMIN", _("Admin")
    MEMBER = "MEMBER", _("Member")


class OrganizationMember(BaseModel):
    """
    User 與 Organization 的多對多中間表，實作 RBAC 權限控管
    (繼承 BaseModel 即可擁有 created_at 作為加入時間)
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


# ==========================================
# 5. 訂閱與專案額度模型 (Subscription)
# ==========================================
class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    PAST_DUE = "past_due", _("Past Due")
    CANCELED = "canceled", _("Canceled")
    CANCELING = "canceling", _("Canceling at Period End")
    INCOMPLETE = "incomplete", _("Incomplete")


class SubscriptionPlan(models.TextChoices):
    FREE = "FREE", _("Free Tier")
    PRO = "PRO", _("Pro Plan")
    ENTERPRISE = "ENTERPRISE", _("Enterprise")


class Subscription(BaseModel):
    """
    紀錄組織的 Stripe 購買紀錄與 Project 配額 (Quota)
    """
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="subscription"
    )
    
    # Stripe 相關識別碼 (初始化或未付費前允許 null)
    stripe_subscription_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True, db_index=True
    )
    stripe_customer_id = models.CharField(
        max_length=255, null=True, blank=True, db_index=True
    )
    stripe_price_id = models.CharField(max_length=255, null=True, blank=True)
    
    # 方案與狀態
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
    
    # 專案配額上限 (Free: 5, Pro: 30, Enterprise: 100)
    max_projects = models.IntegerField(default=5, help_text="該方案允許的最大專案建立數量")
    monthly_api_quota = models.IntegerField(default=1000, help_text="當月可用 API 配額")
    
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    class Meta:
        db_table = "saas_subscription"

    def __str__(self):
        return f"{self.organization.name} - {self.plan} ({self.status})"
    

# ==========================================
# 6. Stripe Webhook 審計與冪等日誌 (Stripe Event Log)
# ==========================================
class StripeEventLog(BaseModel):
    """
    用於防範 Webhook 重複打入 (Idempotency) 與金流事件審計 (Audit Log)
    """
    class EventStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        PROCESSED = "processed", _("Processed")
        FAILED = "failed", _("Failed")

    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    type = models.CharField(max_length=255, help_text="事件類型，如 checkout.session.completed")
    
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
    

# ==========================================
# 7. 專案/業務模型
# ==========================================
class Project(BaseModel):
    """
    專案模型：綁定 Organization，自動繼承 BaseModel 的 created_at 與 updated_at
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
    
    
# ==========================================
# 8. 組織邀請模型 (Organization Invitation)
# ==========================================
class OrganizationInvitation(BaseModel):
    """
    紀錄受邀加入 Working Space 的 Email 邀請紀錄
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
        help_text="專屬邀請 Token"
    )
    
    expires_at = models.DateTimeField(
        default=get_default_invitation_expiration,
        help_text="邀請連結過期時間 (預設 7 天)"
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
    
    
# ==========================================
# 9. 看板任務模型 (Task)
# ==========================================
class TaskStatus(models.TextChoices):
    TODO = "todo", _("To Do")
    IN_PROGRESS = "in_progress", _("In Progress")
    DONE = "done", _("Done")


class Task(BaseModel):
    """
    專案內部的看板 Task：綁定 Project 與 Organization (Row-Level 雙重隔離)
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


# ==========================================
# 10. 專案 Markdown 文件與規格書模型 (Document)
# ==========================================
class Document(BaseModel):
    """
    專案層級的 Markdown 文件與規格書 (支援雙欄編輯與 SSE 即時 AI 產生)
    """
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="documents"
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="documents"
    )
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, default="", help_text="Markdown 原始內文")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_documents"
    )

    class Meta:
        db_table = "saas_document"

    def __str__(self):
        return f"{self.title} ({self.project.name})"
    

