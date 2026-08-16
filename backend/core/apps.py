from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        """
        Executed when the Django application completes initialization and is ready:
        Explicitly import core.signals here to register Django signal receivers into memory.
        Without importing inside ready(), the user_signed_up signal will not trigger the organization provisioning logic!
        """
        import core.signals  # Load and register signal handlers