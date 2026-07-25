# 確保 Django 伺服器啟動時，自動匯入並載入 Celery app，
# 讓 @shared_task 裝飾器能夠正常工作。
from .celery import app as celery_app

__all__ = ("celery_app",)