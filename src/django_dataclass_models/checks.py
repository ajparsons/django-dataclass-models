from typing import Any

from django.apps import AppConfig, apps
from django.core.checks import CheckMessage, Warning, register
from .models import TypedModel
from .foreign_key_typing import ForeignRegistry


@register()
def reverse_foreign_key_warning(
    app_configs: list[AppConfig] | None,
    **kwargs: Any,  # pytype: disable=unused-argument
) -> list[CheckMessage]:
    """
    Generate warning for when foreign key relationships are not explicit for freeform models.
    """
    errors: list[CheckMessage] = []
    for model_dict in apps.all_models.values():
        for model in model_dict.values():
            if issubclass(model, TypedModel):
                for ir in ForeignRegistry.check_model_valid(model.__name__):
                    errors.append(
                        Warning(
                            "Missing explicit reverse relationship for this foreign key. Django doesn't require this, but it helps with typing.",
                            hint=f"Expecting equivalent in {ir.modelB} model of '{ir.fieldB}: {ir.reverse_mode()}[{ir.modelA}] = related('{ir.fieldA}')'",
                            obj=".".join(
                                [
                                    str(model._meta.app_label),  # type: ignore
                                    ir.modelA,
                                    ir.fieldA,
                                ]
                            ),
                            id="freeform.W001",
                        )
                    )
    return errors
