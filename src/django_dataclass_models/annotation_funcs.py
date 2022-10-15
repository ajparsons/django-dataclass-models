"""
Functions to help runtime interpretation of typehints.
"""


import sys
from types import GenericAlias
from typing import Any, ForwardRef, get_args


def typehint_eval(
    code: str, __globals: dict[str, Any], __locals: dict[str, Any]
) -> Any:
    """
    Evaluate a string of code for a typehint.
    If something hasn't appeared yet, store as a string.
    """
    try:
        return eval(code, __globals, __locals)  # pylint: disable=eval-used
    except NameError as e:
        new_code = code.replace(e.name, f'"{e.name}"')
        return typehint_eval(new_code, __globals, __locals)


def get_type_hints_from_class_dict(attrs: dict[str, Any]) -> dict[str, Any]:
    """
    Evaluate annotations in the context of the metatype.
    """
    allowed = vars(sys.modules[attrs["__module__"]])
    return {
        k: typehint_eval(v, allowed, allowed) if isinstance(v, str) else v
        for k, v in attrs.get("__annotations__", {}).items()
    }


def get_specialisation_name_or_type(alias: GenericAlias) -> type | str:
    """
    Given something that's a generic alias, get its specialisation
    and extract the name from a forward ref if that's being used.
    """
    first_arg = get_args(alias)[0]
    if isinstance(first_arg, ForwardRef):
        first_arg = first_arg.__forward_arg__
    return first_arg
