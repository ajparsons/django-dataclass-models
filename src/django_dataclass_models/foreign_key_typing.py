"""
Helpers for managing using type hints to specify different kinds of 
foreign key relationships.
"""


from __future__ import annotations

from typing import Any, Generic, Literal, Type, TypeVar, get_origin

from django.db import models
from django.db.models import Manager

_T = TypeVar("_T")
_Model = TypeVar("_Model", bound=models.Model)


class HolderBase(type):
    """
    Base that emulates the form of Generic typing while lying slightly.
    It returns a wrapper around the given object that allows access to the object
    at runtime, while the typehinter sees just the object itself.

    So we can go:

    item: Holder[ExampleModel]

    and 'item' will be given a type of ExampleModel. But in the annotations,
    there's actually Holder(example_model)

    """

    def __getitem__(
        cls,
        item: _T,
    ) -> _T:
        return cls(item)


class RelatedBase(metaclass=HolderBase):
    """
    Base class to manager different foreign key relationship hints
    """

    def __init__(
        self,
        item: Any,
    ):
        self.item = item


class OneToOne(RelatedBase):
    """
    Indicated a OneToOne relationship with a different model.
    foo: OneToOne[OtherModel] = related("bar")
    """


class ManyToOne(RelatedBase):
    """
    Indicated a ManyToOne relationship with a different model.
    This is the normal ForeignKey.
    foo: ManyToOne[OtherModel] = related("bar")
    """


class GenericManager(Generic[_Model], Manager[_Model]):
    """
    Manager stand-in where the specified model can be acccessed
    through the generic handler.
    """


class OneToMany(GenericManager[_Model]):
    """
    Stand in for a RelatedManager that suggests the right methods
    while allowing validation against the 'active' end of the connection.
    This is the reverse Foreign Key.
    """


class ManyToMany(GenericManager[_Model]):
    """
    Stand in for a RelatedManager that suggests the right methods.
    When a pair is defined (the same relationship inverted), the latter one is passive.
    """


_Model = TypeVar("_Model", bound=models.Model)

valid_mode = (
    Literal["OneToOne"]
    | Literal["OneToMany"]
    | Literal["ManyToOne"]
    | Literal["ManyToMany"]
)


class RelatedStandIn:
    """
    Stand in for the related field that allows us to access the model
    """

    def __init__(self, model: Type[_Model], related_name: str | None):
        self.model = model
        self.related_name = related_name


class OneToManyFieldStandIn:
    """
    Stand in for the equiv of models.OneToManyField, which doesn't exist.
    This will get nullified so just the annotation remains, but it needs to store
    some values in the meantime so reverse relations can be registered.
    """

    one_to_one = False
    one_to_many = True
    many_to_many = False
    many_to_one = True

    def __init__(
        self,
        to: Type[_Model],
        related_name: str | None = None,
        null: bool = False,
        blank: bool = False,
    ):
        self.to = to
        self.null = null
        self.blank = blank
        self.related_name = related_name
        self.remote_field = RelatedStandIn(model=to, related_name=related_name)


class ForeignRegistry:
    """
    Holds details of the connections between models so that
    reverse connections (and a lack of reverse connections)
    can be identified.
    """

    _key_type = tuple[valid_mode, str, str, str, str]
    _registry: dict[_key_type, ForeignRegistry] = {}

    ONE_TO_ONE = "OneToOne"
    ONE_TO_MANY = "OneToMany"
    MANY_TO_ONE = "ManyToOne"
    MANY_TO_MANY = "ManyToMany"

    @classmethod
    def field_type_to_mode(cls, field_type: type) -> valid_mode:
        """
        Convert a field type to a mode
        """
        if issubclass(field_type, models.ForeignKey):
            return cls.MANY_TO_ONE
        elif issubclass(field_type, models.ManyToManyField):
            return cls.MANY_TO_MANY
        elif issubclass(field_type, models.OneToOneField):
            return cls.ONE_TO_ONE
        elif issubclass(field_type, OneToManyFieldStandIn):
            return cls.ONE_TO_MANY
        raise ValueError(f"Unknown field type {field_type}")

    @classmethod
    def all_relationships_resolved(cls):
        """
        Check if all relationships are resolved and return
        A list of all unresolved relationships.
        """
        return [
            relationship
            for relationship in cls._registry.values()
            if relationship.reverse_created is False
        ]

    @classmethod
    def check_model_valid(cls, model: str):
        """
        Check if all relationships that expect a model to be modelB have been resolved.
        Return a list of relationships this isn't true for.
        """

        return [
            relationship
            for relationship in cls._registry.values()
            if relationship.modelB == model and relationship.reverse_created is False
        ]

    @classmethod
    def flip_mode(cls, mode: valid_mode) -> valid_mode:
        """
        Reverse the direction of the relationship to help find
        the reverse relationship.
        """
        match mode:
            case cls.ONE_TO_ONE:
                return cls.ONE_TO_ONE
            case cls.ONE_TO_MANY:
                return cls.MANY_TO_ONE
            case cls.MANY_TO_ONE:
                return cls.ONE_TO_MANY
            case cls.MANY_TO_MANY:
                return cls.MANY_TO_MANY
            case _:
                raise ValueError(f"reverse not found for {mode}")

    def str_to_mode(self, mode: str) -> valid_mode:
        """
        Convert a string to a mode - makes type checker happy
        """
        match mode:
            case self.ONE_TO_ONE:
                return self.ONE_TO_ONE
            case self.ONE_TO_MANY:
                return self.ONE_TO_MANY
            case self.MANY_TO_ONE:
                return self.MANY_TO_ONE
            case self.MANY_TO_MANY:
                return self.MANY_TO_MANY
            case _:
                ...
        raise ValueError(f"Unknown mode {mode}")

    @classmethod
    def register_field_object(
        cls, model_name: str, field_name: str, field: models.ForeignObject[Any, Any]  # type: ignore
    ):
        """
        Register a field object in the registry.
        """
        if field.__class__.many_to_many is True:
            mode = cls.MANY_TO_MANY
        elif field.__class__.one_to_one is True:
            mode = cls.ONE_TO_ONE
        elif field.__class__.one_to_many is True:
            mode = cls.ONE_TO_MANY
        elif field.__class__.many_to_one is True:
            mode = cls.MANY_TO_ONE
        else:
            raise ValueError(f"Unknown field mode {field}")
        modelA = model_name
        modelB: str | Type[models.Model] = field.remote_field.model  # type: ignore
        if isinstance(modelB, type):
            modelB = modelB.__name__
        fieldA = field_name
        fieldB: str = field.remote_field.related_name  # type: ignore
        return cls(mode, modelA, modelB, fieldA, fieldB)

    def __init__(
        self,
        mode: valid_mode | type | str | RelatedBase,
        modelA: str,
        modelB: str,
        fieldA: str,
        fieldB: str | None,
    ) -> None:
        if isinstance(mode, type):
            mode = self.field_type_to_mode(mode)

        if isinstance(mode, RelatedBase):
            mode = self.str_to_mode(mode.__class__.__name__)

        if hasattr(mode, "__origin__"):
            mode = self.str_to_mode(get_origin(mode).__name__)  # type: ignore
        if fieldB is None:
            if mode == self.ONE_TO_ONE:
                fieldB = modelA.lower()
            elif mode == self.ONE_TO_MANY:
                fieldB = modelA.lower() + "_set"
            elif mode == self.MANY_TO_ONE:
                fieldB = modelA.lower() + "_set"
            elif mode == self.MANY_TO_MANY:
                fieldB = modelA.lower() + "_set"

        self.mode: valid_mode = mode  # type: ignore
        self.modelA = modelA
        self.modelB = modelB
        self.fieldA = fieldA
        self.fieldB = fieldB
        self.reverse_created: bool = False
        self._registry[self.get_key()] = self
        self.check_for_reverse()

    def reverse_mode(self):
        """
        Get the expected reverse relationship
        """
        return self.__class__.flip_mode(self.mode)

    def check_for_reverse(self):
        """
        Check if the reverse of this object already exists in the registry

        """
        if (rkey := self.get_reverse_key()) in self._registry:
            self.reverse_created = True
            reverse = self._registry[rkey]
            if reverse.reverse_created is True:
                # A reverse of this has already been registered, uh oh
                raise ValueError(
                    f"Multiple possible reverse relationships registered for relationship {reverse.get_key()}."
                )
            reverse.reverse_created = True

    def get_key(self) -> _key_type:
        """
        return a tuple that compounds all input values in a way that can be checked
        """
        self.mode: valid_mode = self.mode
        if self.fieldB is None:
            raise ValueError(f"fieldB is None for {self.get_key()}")
        return (self.mode, self.modelA, self.modelB, self.fieldA, self.fieldB)

    def get_reverse_key(self):
        """
        Tuple that mirrors the key the reverse relationship should have
        """
        return (
            self.__class__.flip_mode(self.mode),
            self.modelB,
            self.modelA,
            self.fieldB,
            self.fieldA,
        )
