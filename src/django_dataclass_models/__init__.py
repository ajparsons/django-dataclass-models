"""
Simplified Django dataclass models - use typing rather than explicit field objects.
"""

__version__ = "0.1.0"


from .fields import Field, field
from .models import image  # type: ignore
from .models import (
    FieldTypeRegistry,
    ManyToMany,
    ManyToOne,
    OneToMany,
    OneToOne,
    Self,
    TypedModel,
    email,
    file,
    related,
    slug,
    text,
)

Foreign = ManyToOne
ReverseForeign = OneToMany
Reverse = OneToMany

__all__ = [
    "Self",
    "Foreign",
    "ReverseForeign",
    "Reverse",
    "Field",
    "field",
    "related",
    "TypedModel",
    "text",
    "slug",
    "email",
    "file",
    "image",
    "FieldTypeRegistry",
    "OneToMany",
    "OneToOne",
    "ManyToOne",
    "ManyToMany",
]
