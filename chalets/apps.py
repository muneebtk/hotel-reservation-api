from django.apps import AppConfig


class ChaletsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chalets'
    def ready(self):
        from . import signals
