from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """
        當 Django 應用程式完成初始化並準備就緒時：
        必須在此處顯式 import core.signals，讓 Django 的 Signal 接收器 (Receiver) 註冊進系統記憶體中。
        如果沒有在 ready() 裡面 import，user_signed_up 訊號觸發時將不會執行建立組織的邏輯！
        """
        import core.signals  # 載入並啟用 Signals 監聽器