from __future__ import annotations

import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from types import GenericAlias, UnionType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Generic,
    Literal,
    Type,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
)

from django.core.files import File
from django.db import models

from .annotation_funcs import (
    get_specialisation_name_or_type,
    get_type_hints_from_class_dict,
)
from .fields import field as field_helper
from .foreign_key_typing import (
    ForeignRegistry,
    GenericManager,
    ManyToMany,
    ManyToOne,
    OneToMany,
    OneToManyFieldStandIn,
    OneToOne,
    RelatedBase,
)

if sys.version_info >= (3, 11):
    from typing import Self, dataclass_transform
else:
    from typing_extensions import Self, dataclass_transform

_T = TypeVar("_T")


def fix_self(obj: _T) -> _T | Literal["self"]:
    """
    Convert an object to the str "self" if it is the Self class.
    """
    if obj in (Self, "Self"):  # type: ignore
        return "self"
    return obj


class BothSidedForeignKeyWarning(Warning):
    ...


if TYPE_CHECKING:
    BaseField = models.Field[Any, Any]
else:
    BaseField = models.Field


def is_snake_case(name: str) -> bool:
    """
    Check if a string is in snake case. Only lower case letters and underscores are allowed..
    """
    return all(c.islower() or c == "_" for c in name)


def related(related_name: str) -> Any:
    """
    Helper method to define related_names for foreign key fields.
    This is effectively the same as `cast(Any, "related_name")`
    """
    return related_name


_Field = TypeVar("_Field", bound=Type[BaseField])


class FieldLookup(Generic[_Field]):
    """
    Helper function for holding default settings for field types.
    """

    def __init__(
        self,
        field: _Field | OneToManyFieldStandIn,
        default_key: str = "default",
        **kwargs: Any,
    ):
        self.field = field
        self.default_key = default_key
        self.default_kwargs = kwargs

    def item(
        self, default: None | str = None, null: bool = False, blank: bool = False
    ) -> _Field | OneToManyFieldStandIn:
        """
        Return the field with the configured options.
        """

        kwargs = {**self.default_kwargs}
        if null:
            kwargs["null"] = null
        if blank:
            kwargs["blank"] = blank

        if default:
            kwargs[self.default_key] = default

        return self.field(**kwargs)  # type: ignore


_Nullify = object()
text = Annotated[str, FieldLookup(models.TextField)]
slug = Annotated[str, FieldLookup(models.SlugField, max_length=255)]
email = Annotated[str, FieldLookup(models.EmailField, max_length=255)]
file = Annotated[  # type: ignore
    File,  # type: ignore
    FieldLookup(models.FileField, upload_to="uploads"),
]
image = Annotated[  # type: ignore
    File, FieldLookup(models.ImageField, upload_to="uploads")  # type: ignore
]

# Lookup table for field types.
types_to_fields: dict[type | str, FieldLookup[Any]] = {
    str: FieldLookup(models.CharField, max_length=255),
    int: FieldLookup(models.IntegerField),
    float: FieldLookup(models.FloatField),
    bool: FieldLookup(models.BooleanField),
    datetime: FieldLookup(models.DateTimeField),
    date: FieldLookup(models.DateField),
    time: FieldLookup(models.TimeField),
    timedelta: FieldLookup(models.DurationField),
    Decimal: FieldLookup(models.DecimalField, max_digits=10, decimal_places=2),
    list: FieldLookup(models.JSONField),
    dict: FieldLookup(models.JSONField),
    bytes: FieldLookup(models.BinaryField),
}


class FieldTypeRegistry:
    """
    Lookup table for types to django field objects
    """

    lookup_registry = types_to_fields

    @classmethod
    def register(cls, field_type: type, field: FieldLookup[Any]):
        """
        Method to make a connect from new field type to django field.
        """
        cls.lookup_registry[field_type] = field

    @classmethod
    def get_django_lookup(
        cls,
        field_type: str | type | RelatedBase | Type[GenericManager[Any]] | GenericAlias,
    ) -> FieldLookup[Any] | None:
        """
        Convert type hint to a lookup object
        """

        # convert typng.Self to "self"
        field_type = fix_self(field_type)

        # Makes 'var: Model' a foreign relation the same as 'var: ManyToOne[Model]'.
        if (
            isinstance(field_type, type) and issubclass(field_type, models.Model)
        ) or isinstance(field_type, str):
            field_type = ManyToOne(field_type)

        is_generic_alias = hasattr(field_type, "__origin__")
        is_annotated_type = hasattr(field_type, "__metadata__")

        # get FieldLookup for various foreign key relationships
        if isinstance(field_type, ManyToOne):
            # Standard ManyToOne relationship
            return FieldLookup(
                models.ForeignKey,
                default_key="related_name",
                on_delete=models.CASCADE,
                to=fix_self(field_type.item),
            )
        elif isinstance(field_type, OneToOne):
            # Standard OneToOne relationship
            return FieldLookup(
                models.OneToOneField,
                default_key="related_name",
                to=fix_self(field_type.item),
                on_delete=models.CASCADE,
            )
        elif is_generic_alias and get_origin(field_type) == ManyToMany:
            # Given ManyToMany[Model], use "Model" (or "self") in a Foreign Key relationship.
            related_model = fix_self(get_specialisation_name_or_type(field_type))  # type: ignore
            return FieldLookup(
                models.ManyToManyField, to=related_model, default_key="related_name"
            )
        elif is_generic_alias and get_origin(field_type) == OneToMany:
            # this is a psuedo field that will get removed later - but is
            # used to validate both sides of a related relationship.
            related_model = fix_self(get_specialisation_name_or_type(field_type))  # type: ignore
            return FieldLookup(
                OneToManyFieldStandIn, to=related_model, default_key="related_name"
            )
        elif field_type == GenericManager[Any]:
            # check we're just using a subclass of GenericManager
            raise NotImplementedError("GenericManager is not implemented")
        if is_generic_alias and not is_annotated_type:
            # this is dealing with stuff like `'list[int]'
            origin = get_origin(field_type)
            if not origin:
                raise ValueError(f"Could not determine origin of {field_type}")
            field_type = origin
        if is_annotated_type:
            # This deals with fields where the FieldLookup has been hidden
            # within an annotation.
            metadata = getattr(field_type, "__metadata__")
            if len(metadata) == 1 and isinstance(metadata[0], FieldLookup):
                return metadata[0]
            # Or when the annotation is a Field class and a dictionary of default options.
            elif (
                len(metadata) == 2
                and isinstance(metadata[0], type)
                and issubclass(metadata[0], models.Field)
                and isinstance(metadata[1], dict)
            ):
                return FieldLookup(metadata[0], **metadata[1])
            else:
                raise ValueError(
                    f"Metadata for {field_type} is not valid, does not fit either 'FieldLookup' instance, or 'Field, dict' patterns."
                )
        field_type = cast(type, field_type)
        return cls.lookup_registry.get(field_type, None)


@dataclass_transform(kw_only_default=True, field_specifiers=(field_helper,))
class TypedModelBase(models.base.ModelBase):
    """
    A model base class that automatically adds fields for all the typehints in the class.
    """

    def __new__(cls, name: str, bases: tuple[type], dct: dict[str, Any], **kwargs: Any):
        """
        Convert typed style fields declarations to django style fields.
        Also convert any keyword arguments to a django meta class.
        """
        annotations = get_type_hints_from_class_dict(dct)

        for variable, field_type in annotations.items():
            # non snake case are assumed to be constants that shouldn't be transformed
            if not is_snake_case(variable):
                continue

            # get any object already assigned to this value
            default = None
            default_or_value = dct.get(variable, None)
            if isinstance(default_or_value, str):
                default = default_or_value
            elif isinstance(default_or_value, models.ForeignObject):
                # Register a manually created relation and move on
                if TYPE_CHECKING:
                    # when type checking Foreign Office has generic, but not at run time
                    default_or_value = cast(models.ForeignObject[Any, Any], default_or_value)  # type: ignore
                ForeignRegistry.register_field_object(
                    model_name=name, field_name=variable, field=default_or_value
                )
                continue
            elif default_or_value:
                continue

            null = False
            if (
                isinstance(field_type, UnionType)
                or getattr(field_type, "__origin__", None) == Union
            ):
                field_args = get_args(field_type)
                null = any([x == type(None) for x in field_args])
                non_null = [x for x in field_args if x is not type(None)]
                if len(non_null) == 1:
                    field_type = non_null[0]
                else:
                    raise ValueError(
                        f"Cannot determine field type for {field_type}, nothing other than None in Union"
                    )

            field_instance = FieldTypeRegistry.get_django_lookup(field_type)
            if field_instance is None:
                raise ValueError(
                    f"Field '{variable}' has typehint '{field_type}', but there is no default django field for that type."
                )
            field_object = field_instance.item(default=default, null=null)

            # if field_object is a foreign key relationship, we need to register it
            if isinstance(
                field_object,
                OneToManyFieldStandIn
                | models.ForeignKey
                | models.ManyToManyField
                | models.OneToOneField,
            ):
                registered = ForeignRegistry.register_field_object(
                    model_name=name, field_name=variable, field=field_object  # type: ignore
                )
                # In this case, if the reverse is acknowledged, we dump the value because we
                # don't want to register both ends.
                if isinstance(
                    field_object, (models.ManyToManyField, models.OneToOneField)
                ):
                    if registered.reverse_created:
                        field_object = _Nullify

                # can't actually have a value here or it'll get confused, and need
                # to clear out any str default value.

                if field_object is OneToManyFieldStandIn:
                    field_object = _Nullify
            if field_object:
                dct[variable] = field_object
                if field_object == _Nullify:
                    del dct[variable]

        if kwargs:
            dct["Meta"] = type("Meta", (type,), kwargs)

        return super().__new__(cls, name, bases, dct)


_ForeignRelationship = TypeVar("_ForeignRelationship")


class TypedModel(models.Model, metaclass=TypedModelBase, abstract=True):
    """
    A simplified version of the default django model that automatically adds fields for all the typehints in the class.
    """

    id: int = field_helper(models.BigAutoField, primary_key=True)
