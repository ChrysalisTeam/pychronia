from django.apps import AppConfig


class PychroniaGameConfig(AppConfig):
    name = "pychronia_game"
    verbose_name = "Pychronia game"

    def ready(self):
        # registers all game views, abilities and permissions (no SQL models: game data lives in ZODB)
        from . import views  # noqa: F401
