import os
from celery import Celery

# Set the default Django settings module for Celery to locate the configuration
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Instantiate the Celery application and name the background task runner "saas_platform"
app = Celery("saas_platform")

# Load configuration from Django's settings.py for all keys prefixed with "CELERY_"
# Example: CELERY_BROKER_URL will be automatically loaded
app.config_from_object("django.conf:settings", namespace="CELERY")

# Automatically discover and load tasks.py modules from all registered INSTALLED_APPS
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """
    Debug task for testing Celery execution.
    bind=True: Passes the current task instance as 'self' to access request metadata.
    ignore_result=True: Skips storing task execution results to conserve backend storage.
    """
    print(f"Request: {self.request!r}")