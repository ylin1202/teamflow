from rest_framework import serializers
from core.models import OrganizationMember, OrganizationInvitation, Project, Task, Document, User


class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'username']


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
    

class OrganizationMemberSerializer(serializers.ModelSerializer):
    # 💡 同時補上 user_email 欄位，確保前端抓 member.user_email 抓得到！
    user_email = serializers.EmailField(source='user.email', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = OrganizationMember
        fields = ['id', 'organization', 'user', 'user_email', 'email', 'role', 'created_at']


class OrganizationInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationInvitation
        fields = ['id', 'organization', 'email', 'role', 'invited_by', 'is_accepted', 'token', 'expires_at', 'created_at']
        read_only_fields = ['organization', 'invited_by', 'is_accepted', 'token', 'expires_at']
        

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'project', 'organization', 'title', 'description', 'status', 'assignee', 'created_at', 'updated_at']
        read_only_fields = ['organization']

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'project', 'organization', 'title', 'content', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['organization']


