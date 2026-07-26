from rest_framework import serializers
from core.models import OrganizationMember, OrganizationInvitation, Project

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
    

class OrganizationMemberSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = OrganizationMember
        fields = ["id", "user", "user_email", "user_name", "role", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class OrganizationInvitationSerializer(serializers.ModelSerializer):
    invited_by_email = serializers.EmailField(source="invited_by.email", read_only=True)

    class Meta:
        model = OrganizationInvitation
        fields = ["id", "email", "role", "is_accepted", "invited_by_email", "created_at"]
        read_only_fields = ["id", "is_accepted", "invited_by_email", "created_at"]