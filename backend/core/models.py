import uuid6
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

# 定義 UUIDv7 產生器函數，供 Django ORM default 呼叫
def generate_uuidv7():
    return uuid6.uuid7()


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
    updated_at = models.DateTimeField(auto_now=True)

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
    
    owner = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="owned_organizations"
    )
    members = models.ManyToManyField(
        User, through="OrganizationMember", related_name="organizations"
    )

    class Meta:
        db_table = "saas_organization"

    def __str__(self):
        return self.name


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
# 5. 訂閱狀態與配額模型 (Subscription)
# ==========================================
class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    PAST_DUE = "past_due", _("Past Due")
    CANCELED = "canceled", _("Canceled")
    INCOMPLETE = "incomplete", _("Incomplete")


class Subscription(BaseModel):
    """
    紀錄組織的 Stripe 訂閱狀態與 API 配額 (Quota)
    """
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="subscription"
    )
    
    # Stripe 相關識別碼 (初始化或未付費前允許 null)
    stripe_subscription_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True, db_index=True
    )
    stripe_price_id = models.CharField(max_length=255, null=True, blank=True)
    
    status = models.CharField(
        max_length=20, 
        choices=SubscriptionStatus.choices, 
        default=SubscriptionStatus.INCOMPLETE
    )
    
    # 商業 API 配額（提供給 Redis Rate Limiter 讀取與驗證）
    monthly_api_quota = models.IntegerField(default=1000, help_text="當月可用 API 配額")
    
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    class Meta:
        db_table = "saas_subscription"

    def __str__(self):
        return f"{self.organization.name} - {self.status}"


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

    # Stripe 事件的唯一 ID (例如 evt_1Nxxx)，設置 db_index 加速查詢
    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    type = models.CharField(max_length=255, help_text="事件類型，如 checkout.session.completed")
    
    status = models.CharField(
        max_length=20, 
        choices=EventStatus.choices, 
        default=EventStatus.PENDING
    )
    
    # MySQL JSON 欄位（儲存 Webhook 原始 Payload）
    payload = models.JSONField()
    error_message = models.TextField(null=True, blank=True)
    
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "saas_stripe_event_log"

    def __str__(self):
        return f"{self.event_id} - {self.type} ({self.status})"
    

# ==========================================
# 7. 專案/業務模型 (用於測試多租戶資料隔離)
# ==========================================
class Project(BaseModel):
    """
    專案模型：綁定 Organization，用於驗證 TenantBaseViewSet 的資料隔離機制
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