"""
Methods to help fields using normal django components in the typed advantage.
"""

import sys

if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec

from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast

from django.db.models import Field as DjangoField


class TypeSafeMeta(type):
    """
    Metaclass to use Field directly rather than requiring an instance.
    """

    def __or__(cls, other: Any):
        """
        Cast 'other' in x | other to Any.
        """
        return cast(Any, other)


class Field(metaclass=TypeSafeMeta):
    """
    Helper for typing django fields.

    item: str = models.CharField(...)

    Will have an incompatibility.

    item: str = Field | models.CharField(...)

    Casts the CharField to Any.

    """


_P = ParamSpec("_P")
_T = TypeVar("_T")

if TYPE_CHECKING:
    _Field = DjangoField[Any, Any]
else:
    _Field = DjangoField


def field(field_type: Callable[_P, _Field], *args: _P.args, **kwargs: _P.kwargs) -> Any:
    """
    Create a field with the given type.
    """

    return cast(Any, field_type(*args, **kwargs))
