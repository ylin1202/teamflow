"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import (
    GoogleLoginView, 
    stripe_webhook_view, 
    MyOrganizationsView,
    ProjectViewSet
)

# 建立 DefaultRouter 並註冊 ProjectViewSet
router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/google/', GoogleLoginView.as_view(), name='google_login'),
    path('api/organizations/me/', MyOrganizationsView.as_view(), name='my_organizations'),
    path('webhooks/stripe/', stripe_webhook_view, name='stripe_webhook'),
    
    # 自動生成 /api/projects/ 與 /api/projects/{id}/ 的 CRUD 路由
    path('api/', include(router.urls)),
]