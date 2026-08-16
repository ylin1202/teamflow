from django.contrib import admin
from core.models import User, Organization, OrganizationMember, Subscription, StripeEventLog, Project, OrganizationInvitation

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "username", "is_staff", "is_active", "created_at")
    search_fields = ("email", "username")

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "created_at")
    search_fields = ("name", "slug")

@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ("organization", "user", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__email", "organization__name")

@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = ("organization", "email", "role", "invited_by", "is_accepted", "created_at")
    list_filter = ("role", "is_accepted")
    search_fields = ("email", "organization__name")

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "created_at")
    search_fields = ("name", "organization__name")

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("organization", "plan", "max_projects", "status", "current_period_start", "current_period_end")
    list_filter = ("plan", "status")
    search_fields = ("organization__name", "stripe_subscription_id", "stripe_customer_id")

@admin.register(StripeEventLog)
class StripeEventLogAdmin(admin.ModelAdmin):
    list_display = ("event_id", "type", "status", "created_at")
    list_filter = ("status", "type")