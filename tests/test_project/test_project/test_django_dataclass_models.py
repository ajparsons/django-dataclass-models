import os
from typing import Any

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_project.settings")
django.setup()

from testapp.models import (
    ExampleTypedModel,
    OriginalAbstractModel,
    OriginalModel,
    TypedAbstractModel,
)


def check_field_equiv(fielda: Any, fieldb: Any):
    # test max length, null and default options on a django field are the same between two fields
    assert fielda.max_length == fieldb.max_length
    assert fielda.null == fieldb.null
    assert fielda.default == fieldb.default


def check_if_django_model_is_abstract(cls: Any):
    # test if a django model is abstract
    return cls._meta.abstract is True  # type: ignore


def test_equiv():
    # test that the fields in the original model are the same as the fields in the typed model
    for field_a in OriginalModel._meta.get_fields():  # type: ignore
        field_b = ExampleTypedModel._meta.get_field(field_a.name)  # type: ignore
        check_field_equiv(field_a, field_b)  # type: ignore


def test_abstract():
    # test that the abstract model is abstract
    assert check_if_django_model_is_abstract(TypedAbstractModel)  # type: ignore
    assert check_if_django_model_is_abstract(OriginalAbstractModel)  # type: ignore
    assert check_if_django_model_is_abstract(ExampleTypedModel) is False
