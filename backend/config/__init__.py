# This ensures that the Celery app is always imported when
# Django starts, allowing @shared_task decorators to work properly.
from .celery import app as celery_app

__all__ = ("celery_app",)