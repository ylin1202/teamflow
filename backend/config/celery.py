import os
from celery import Celery

# 設定 Django 的預設 settings 模組路徑，讓 Celery 知道去哪裡讀取設定檔
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# 建立 Celery 應用程式實體，並將這個專案的背景任務命名為 "saas_platform"
app = Celery("saas_platform")

# 從 Django 的 settings.py 讀取所有以 "CELERY_" 為字首的設定項目
# 例如：CELERY_BROKER_URL 會被自動載入
app.config_from_object("django.conf:settings", namespace="CELERY")

# 自動搜尋並載入所有已在 INSTALLED_APPS 註冊的 Django app 底下的 tasks.py 檔案
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """
    測試用的 Celery Task
    bind=True: 讓第一個參數 self 代表當前 Task 實體，可存取 request 等狀態
    ignore_result=True: 不儲存此測試任務的執行結果以節省 Redis 空間
    """
    print(f"Request: {self.request!r}")