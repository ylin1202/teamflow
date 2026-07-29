import redis
import logging
import uuid
from functools import wraps
from datetime import datetime
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status
from core.models import Subscription

logger = logging.getLogger(__name__)

REDIS_URL = getattr(settings, "REDIS_URL", "redis://redis:6379/0")
redis_client = redis.Redis.from_url(REDIS_URL)

def enforce_quota(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # 1. 取得 Organization ID (從 Header 讀取)
        org_id = request.headers.get("X-Organization-ID")

        if org_id:
            org_id = org_id.strip()

        if not org_id:
            return Response(
                {"detail": "Missing X-Organization-ID header."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 防護：驗證傳進來的 org_id 是否為合法 UUID
        try:
            uuid.UUID(str(org_id))
        except ValueError:
            return Response(
                {"detail": f"Invalid Organization ID format: '{org_id}'. Must be a valid UUID."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. 取得 Subscription 配額上限
        sub = Subscription.objects.filter(organization_id=org_id).first()
        limit = sub.monthly_api_quota if sub else 1000

        # 3. 組出 Redis Key (格式: quota:org:{org_id}:{YYYY-MM}:used)
        current_month = datetime.now().strftime("%Y-%m")
        redis_key = f"quota:org:{org_id}:{current_month}:used"

        try:
            # 4. 取得當前已使用次數
            current_used = redis_client.get(redis_key)
            used_count = int(current_used) if current_used else 0

            # 5. 判斷是否爆表 (Quota Exceeded)
            if used_count >= limit:
                return Response(
                    {
                        "error": "Quota Exceeded",
                        "detail": f"You have reached your monthly quota limit of {limit:,} API calls.",
                        "used": used_count,
                        "limit": limit
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )

            # 6. 未爆表 $\rightarrow$ Redis 計數 +1
            redis_client.incr(redis_key)

        except redis.RedisError as e:
            logger.error(f"Redis connection error in enforce_quota: {str(e)}")

        return view_func(request, *args, **kwargs)

    return _wrapped_view