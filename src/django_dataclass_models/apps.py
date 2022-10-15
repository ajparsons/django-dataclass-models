"""
App config that runs the reverse typing tests
"""

from django.apps import AppConfig


class TypedModelConfig(AppConfig):
    """
    Functions to run before the application is considered ready
    """

    name = "django_freeform.typed_model"

    def ready(self):
        """
        This just imports a model that registers and runs a check
        that ensures the reverse foreign key relationships are explicit.
        """
        from . import checks  # type:ignore
