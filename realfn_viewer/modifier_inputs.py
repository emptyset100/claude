"""
Version-independent access to Geometry Nodes modifier input values.

Blender ≤ 5.1 stored every modifier input as an IDProperty on the
modifier itself::

    mod["Socket_2"] = 1.5
    layout.prop(mod, '["Socket_2"]')
    data_path = 'modifiers["GeometryNodes"]["Socket_2"]'

Blender 5.2 replaced that with a typed RNA interface — ``mod["…"]`` now
raises ``TypeError: this type doesn't support IDProperties``::

    mod.properties.inputs.Socket_2.value = 1.5
    layout.prop(mod.properties.inputs.Socket_2, "value")
    data_path = 'modifiers["GeometryNodes"].properties.inputs.Socket_2.value'

Every read, write, UI draw and animation path for a modifier input in
the extension goes through this module, so the rest of the code never
has to care which API the running Blender exposes.
"""

from __future__ import annotations

import re


def uses_rna_inputs(mod) -> bool:
    """True on Blender 5.2+ (typed ``mod.properties.inputs`` API)."""
    props = getattr(mod, "properties", None)
    return props is not None and hasattr(props, "inputs")


def _slot(mod, identifier):
    """The per-input RNA struct (5.2+) or None if absent."""
    try:
        return getattr(mod.properties.inputs, identifier, None)
    except (AttributeError, ReferenceError):
        return None


def has_input(mod, identifier) -> bool:
    """Whether the modifier currently exposes a value for ``identifier``."""
    if uses_rna_inputs(mod):
        slot = _slot(mod, identifier)
        return slot is not None and "value" in slot.bl_rna.properties
    try:
        return identifier in mod
    except TypeError:
        return False


def _plain(value):
    """Detach array values (vectors, colours) from Blender memory so they
    stay valid after the modifier's node group is swapped."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "bl_rna"):  # datablock (Material, Object…)
        return value
    try:
        return tuple(value)
    except TypeError:
        return value


def get_value(mod, identifier, default=None):
    """Value of a modifier input, or ``default`` if it doesn't exist.

    Vectors / colours come back as plain tuples."""
    if uses_rna_inputs(mod):
        slot = _slot(mod, identifier)
        if slot is None:
            return default
        return _plain(getattr(slot, "value", default))
    try:
        return _plain(mod[identifier])
    except (KeyError, TypeError):
        return default


def set_value(mod, identifier, value) -> bool:
    """Write a modifier input. Returns False if it can't be written
    (unknown identifier, incompatible value)."""
    if uses_rna_inputs(mod):
        slot = _slot(mod, identifier)
        if slot is None or "value" not in slot.bl_rna.properties:
            return False
        try:
            slot.value = value
            return True
        except (TypeError, ValueError, AttributeError):
            return False
    try:
        mod[identifier] = value
        return True
    except (KeyError, TypeError, ValueError):
        return False


def input_data_path(mod, identifier) -> str:
    """Object-relative RNA path of an input's value — usable for
    ``keyframe_insert``, F-curve lookups and drivers."""
    name = mod.name.replace("\\", "\\\\").replace('"', '\\"')
    if uses_rna_inputs(mod):
        return f'modifiers["{name}"].properties.inputs.{identifier}.value'
    return f'modifiers["{name}"]["{identifier}"]'


# Pre-5.2 form of a modifier-input path: modifiers["Name"]["Socket_2"]
_OLD_PATH_RE = re.compile(
    r'^modifiers\["((?:[^"\\]|\\.)*)"\]\["([A-Za-z_]+_\d+)"\]$')


def upgrade_data_path(owner, path):
    """Rewrite a pre-5.2 modifier-input path stored in a driver or
    F-curve into the running Blender's form. Returns the new path, or
    None when nothing needs to change."""
    match = _OLD_PATH_RE.match(path or "")
    mods = getattr(owner, "modifiers", None)
    if match is None or mods is None:
        return None
    mod = mods.get(match.group(1).replace('\\"', '"'))
    if mod is None or not uses_rna_inputs(mod):
        return None
    if _slot(mod, match.group(2)) is None:
        return None
    return input_data_path(mod, match.group(2))


def draw_input(layout, mod, identifier, **kwargs) -> bool:
    """``layout.prop`` for a modifier input; returns False (and draws
    nothing) when the input doesn't exist on this modifier."""
    if uses_rna_inputs(mod):
        slot = _slot(mod, identifier)
        if slot is None or "value" not in slot.bl_rna.properties:
            return False
        layout.prop(slot, "value", **kwargs)
        return True
    try:
        if identifier not in mod:
            return False
    except TypeError:
        return False
    layout.prop(mod, f'["{identifier}"]', **kwargs)
    return True
