"""
User preset management for RealFnViewer.

A *preset* is the full state of a RealFn modifier — formula, free
parameters, derivative / Taylor orders, sampling range, basepoint x₀,
per-piece tube thicknesses and visibility flags — serialised to JSON.

Storage layout
--------------
Each preset is one JSON file under
``<extension_path_user>/presets/<slug>.json``. ``extension_path_user``
is Blender's per-user data directory for the extension; files there
follow the user across .blend documents and Blender versions
(provided the extension stays installed).

Filenames are slugified from the preset's display ``name`` so users
can drop, copy, version-control them outside Blender without going
through the UI. The display name lives inside the JSON, so renaming
a file doesn't lose anything.

Schema (v1)
-----------
::

    {
        "schema": 1,
        "name": "Cubic with extrema",
        "created": "2024-05-19T18:00:00",   # ISO 8601, informational
        "formula": {
            "expr": "x**3 - 3*x",
            "allowed_params": ["a", "b"],
            "derivative_order": 2,
            "taylor_order": 1
        },
        "range": {"x_min": -3.0, "x_max": 3.0, "x_0": 1.0,
                  "resolution": 256, "marker_size": 0.1},
        "params": {"a": 1.0, "b": 0.5},
        "pieces": {
            "f":   {"thickness": 0.030, "visible": true},
            "f'":  {"thickness": 0.010, "visible": true},
            "f''": {"thickness": 0.010, "visible": false},
            "T_1": {"thickness": 0.015, "visible": true}
        }
    }

A future revision would bump ``schema``; load code checks the version
and refuses incompatible files cleanly.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

import bpy

from . import preset_io


def _display_name(data, fallback):
    """Pick the preset name to *show*, honouring the UI language.

    Built-in presets carry an optional ``name_en`` field; in English
    mode it's preferred over the French ``name``. User presets have no
    ``name_en`` and so always show under the name the user gave them —
    which is the right behaviour (their own names aren't translated).

    Returns ``(display_name, stable_name)``: the first is for the
    button label, the second is the canonical French ``name`` used as
    the identity key by apply / export / delete (so the toggle never
    changes which file an action targets)."""
    stable = str(data.get("name", fallback))
    try:
        from . import i18n
        if i18n.get_lang() == "EN":
            return str(data.get("name_en", stable)), stable
    except Exception:
        pass
    return stable, stable


SCHEMA_VERSION = 1
PRESETS_SUBDIR = "presets"


# --------------------------------------------------------------------------- #
# Filesystem
# --------------------------------------------------------------------------- #
def _presets_dir() -> Path:
    """Return the per-user presets directory, creating it on first call.

    ``bpy.utils.extension_path_user`` resolves to
    ``~/.config/blender/<version>/extensions/<repo>/<addon>/`` on Linux
    and the platform-equivalent elsewhere — managed by Blender so we
    don't have to deal with platform paths ourselves.
    """
    base = Path(bpy.utils.extension_path_user(
        __package__, create=True,
    ))
    pdir = base / PRESETS_SUBDIR
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


_SLUG_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def _slugify(name: str) -> str:
    """Turn a display name into a filesystem-safe slug.

    Empty-after-slug, all-punctuation names fall back to ``"preset"``
    so the loader never has to guess at exotic inputs.
    """
    slug = _SLUG_RE.sub("_", name.strip()).strip("_").lower()
    return slug or "preset"


def _preset_path(name: str) -> Path:
    return _presets_dir() / (_slugify(name) + ".json")


def find_preset_file(name: str) -> Path | None:
    """Resolve a preset display ``name`` to an existing file path.

    Returns None if neither the standard nor the builtin-prefixed
    filename exists. This helper is used by export / delete operations
    that need to load a preset by name regardless of whether it's
    user-saved or a bundled built-in.
    """
    fp = _preset_path(name)
    if fp.exists():
        return fp
    from . import builtin_presets
    fp_builtin = _presets_dir() / (
        builtin_presets.BUILTIN_FILE_PREFIX + _slugify(name) + ".json"
    )
    if fp_builtin.exists():
        return fp_builtin
    return None


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #
def list_presets() -> list:
    """Return ``[(display_name, path), ...]`` sorted by display name.

    Reads only the ``name`` field of each JSON file, not the full body
    — keeps the UI list snappy even with hundreds of presets.
    """
    results = []
    for fp in _presets_dir().glob("*.json"):
        try:
            with fp.open("r", encoding="utf-8") as f:
                data = json.load(f)
            disp, stable = _display_name(data, fp.stem)
            results.append((disp, stable, fp))
        except (json.JSONDecodeError, OSError):
            # Skip files we can't read — better than failing the
            # whole panel draw because a single preset is corrupt.
            continue
    results.sort(key=lambda x: x[0].lower())
    return results


# --------------------------------------------------------------------------- #
# Snapshot the active modifier into a preset dict
# --------------------------------------------------------------------------- #
def snapshot_modifier(modifier, name: str) -> dict:
    """Build a scalar-curve preset dict from a live modifier.

    Thin wrapper over the generic engine (see preset_io.SCALAR).
    """
    return preset_io.snapshot(modifier, name, preset_io.SCALAR)


# --------------------------------------------------------------------------- #
# Save / load / delete
# --------------------------------------------------------------------------- #
def save_preset(preset: dict, *, overwrite: bool = True) -> Path:
    """Write a preset dict to JSON. Returns the resulting path."""
    fp = _preset_path(preset["name"])
    if fp.exists() and not overwrite:
        raise FileExistsError(f"Preset already exists: {fp.name}")
    with fp.open("w", encoding="utf-8") as f:
        json.dump(preset, f, indent=2, ensure_ascii=False)
    return fp


def load_preset(path) -> dict:
    """Read a JSON file from disk and validate its schema version."""
    fp = Path(path)
    with fp.open("r", encoding="utf-8") as f:
        data = json.load(f)
    schema = data.get("schema")
    if schema != SCHEMA_VERSION:
        raise ValueError(
            f"Preset {fp.name!r} : version de schéma incompatible "
            f"({schema!r}, attendu {SCHEMA_VERSION})"
        )
    # Light validation — full validation would just slow us down
    # without catching anything that the apply step doesn't already
    # report cleanly.
    for required in ("name", "formula"):
        if required not in data:
            raise ValueError(
                f"Preset {fp.name!r} : champ {required!r} manquant"
            )
    return data


def delete_preset(name: str) -> bool:
    """Remove a preset by display name. Returns True on success.

    Searches for the file under both the standard slug
    (``<slug>.json``) and the builtin-prefixed slug
    (``_builtin_<slug>.json``) so the user can delete a builtin from
    the panel without having to know which kind of file it is.
    Deleting a builtin merely removes the file; the user can always
    re-install it via the "Réinstaller les builtin" operator.
    """
    fp = _preset_path(name)
    if fp.exists():
        fp.unlink()
        return True
    # Try the builtin-prefixed filename. We import lazily to avoid a
    # circular import (builtin_presets uses presets, not the other
    # way around, but importing at module top would create an awkward
    # coupling for what's essentially a fallback path).
    from . import builtin_presets
    fp_builtin = _presets_dir() / (
        builtin_presets.BUILTIN_FILE_PREFIX + _slugify(name) + ".json"
    )
    if fp_builtin.exists():
        fp_builtin.unlink()
        return True
    return False


# --------------------------------------------------------------------------- #
# Apply a preset to a modifier
# --------------------------------------------------------------------------- #
def apply_preset_to_modifier(preset: dict, modifier) -> dict:
    """Restore a scalar-curve preset into ``modifier``.

    Thin wrapper over the generic engine (see preset_io.SCALAR).
    """
    return preset_io.apply(preset, modifier, preset_io.SCALAR)


# =========================================================================== #
# Vector function presets
# =========================================================================== #
# Vector presets live in a sibling subdirectory and follow a schema that's
# distinct from the scalar one — different sockets to capture, different
# semantics (no derivative_order or taylor_order, but a t-range and per-arrow
# visibility / material). Keeping the two systems separated in code and on
# disk avoids the trap of overloaded "if kind == ..." branches scattered
# through the snapshot / apply pipeline.

VECTOR_PRESETS_SUBDIR = "presets/vector"
VECTOR_SCHEMA_VERSION = 1


def _vector_presets_dir() -> Path:
    """Return the per-user vector-presets directory, creating it on first call.

    Located under ``…/realfn_viewer/presets/vector/`` so it's a natural
    sibling to the scalar ``…/realfn_viewer/presets/`` — easy to browse
    side-by-side in a file manager, easy to back up as a unit.
    """
    base = Path(bpy.utils.extension_path_user(__package__, create=True))
    pdir = base / VECTOR_PRESETS_SUBDIR
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


def _vector_preset_path(name: str) -> Path:
    return _vector_presets_dir() / (_slugify(name) + ".json")


def find_vector_preset_file(name: str) -> Path | None:
    """Resolve a vector preset display ``name`` to an existing file path,
    handling both user-saved and bundled built-in filenames."""
    fp = _vector_preset_path(name)
    if fp.exists():
        return fp
    from . import builtin_presets
    fp_builtin = _vector_presets_dir() / (
        builtin_presets.BUILTIN_VECTOR_FILE_PREFIX
        + _slugify(name) + ".json"
    )
    if fp_builtin.exists():
        return fp_builtin
    return None


def list_vector_presets() -> list:
    """Return ``[(display_name, path), ...]`` for vector presets only,
    sorted by display name."""
    results = []
    for fp in _vector_presets_dir().glob("*.json"):
        try:
            with fp.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # Defensive: skip files that somehow ended up here but aren't
            # vector presets. A scalar preset placed manually into the
            # vector directory would have kind != "vector".
            if data.get("kind") != "vector":
                continue
            disp, stable = _display_name(data, fp.stem)
            results.append((disp, stable, fp))
        except (json.JSONDecodeError, OSError):
            continue
    results.sort(key=lambda x: x[0].lower())
    return results


def snapshot_vector_modifier(modifier, name: str) -> dict:
    """Build a vector-curve preset dict from a live modifier.

    Thin wrapper over the generic engine (see preset_io.VECTOR).
    """
    return preset_io.snapshot(modifier, name, preset_io.VECTOR)


def save_vector_preset(preset: dict, *, overwrite: bool = True) -> Path:
    """Write a vector preset dict to JSON. Returns the resulting path."""
    fp = _vector_preset_path(preset["name"])
    if fp.exists() and not overwrite:
        raise FileExistsError(f"Preset vectoriel existe déjà : {fp.name}")
    with fp.open("w", encoding="utf-8") as f:
        json.dump(preset, f, indent=2, ensure_ascii=False)
    return fp


def load_vector_preset(path) -> dict:
    """Read a vector preset from disk and validate its schema + kind."""
    fp = Path(path)
    with fp.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("kind") != "vector":
        raise ValueError(
            f"Preset {fp.name!r} : kind {data.get('kind')!r}, vectoriel attendu"
        )
    schema = data.get("schema")
    if schema != VECTOR_SCHEMA_VERSION:
        raise ValueError(
            f"Preset vectoriel {fp.name!r} : version de schéma "
            f"incompatible ({schema!r}, attendu {VECTOR_SCHEMA_VERSION})"
        )
    for required in ("name", "formula"):
        if required not in data:
            raise ValueError(
                f"Preset vectoriel {fp.name!r} : champ {required!r} manquant"
            )
    return data


def delete_vector_preset(name: str) -> bool:
    """Remove a vector preset by display name. Returns True on success.

    Like :func:`delete_preset`, searches both the standard slug and the
    builtin-prefixed slug so deletion from the UI works uniformly
    regardless of whether the preset is user-saved or one of the
    bundled built-ins.
    """
    fp = _vector_preset_path(name)
    if fp.exists():
        fp.unlink()
        return True
    from . import builtin_presets
    fp_builtin = _vector_presets_dir() / (
        builtin_presets.BUILTIN_VECTOR_FILE_PREFIX
        + _slugify(name) + ".json"
    )
    if fp_builtin.exists():
        fp_builtin.unlink()
        return True
    return False


def apply_vector_preset_to_modifier(preset: dict, modifier) -> dict:
    """Restore a vector-curve preset into ``modifier``.

    Thin wrapper over the generic engine (see preset_io.VECTOR).
    """
    return preset_io.apply(preset, modifier, preset_io.VECTOR)


# =========================================================================== #
# Surface (explicit z = f(x,y)) preset system
# =========================================================================== #
# Lives in its own subdirectory and uses its own schema. Per-piece data
# from the scalar / vector systems doesn't apply here — instead we have:
#
#   * a 2D domain (x_min, x_max, y_min, y_max) and (x_0, y_0) basepoint;
#   * Resolution X / Y for the surface mesh;
#   * tangent-plane controls (size, resolution, visibility);
#   * material slots for surface / marker / tangent plane.

SURFACE_PRESETS_SUBDIR = "presets/surface"
SURFACE_SCHEMA_VERSION = 1


def _surface_presets_dir() -> Path:
    base = Path(bpy.utils.extension_path_user(__package__, create=True))
    pdir = base / SURFACE_PRESETS_SUBDIR
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


def _surface_preset_path(name: str) -> Path:
    return _surface_presets_dir() / (_slugify(name) + ".json")


def find_surface_preset_file(name: str) -> Path | None:
    """Resolve a surface preset name to an existing file path, trying
    both the standard slug and the builtin-prefixed slug.
    """
    fp = _surface_preset_path(name)
    if fp.exists():
        return fp
    from . import builtin_presets
    fp_builtin = _surface_presets_dir() / (
        builtin_presets.BUILTIN_SURFACE_FILE_PREFIX
        + _slugify(name) + ".json"
    )
    if fp_builtin.exists():
        return fp_builtin
    return None


def list_surface_presets() -> list:
    """Return ``[(display_name, path), ...]`` of all explicit-surface
    presets in the user directory."""
    results = []
    for fp in _surface_presets_dir().glob("*.json"):
        try:
            with fp.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("kind") != "surface":
                continue
            disp, stable = _display_name(data, fp.stem)
            results.append((disp, stable, fp))
        except (json.JSONDecodeError, OSError):
            continue
    results.sort(key=lambda x: x[0].lower())
    return results


def snapshot_surface_modifier(modifier, name: str) -> dict:
    """Build an explicit-surface preset dict from a live modifier.

    Thin wrapper over the generic engine (see preset_io.SURFACE).
    """
    return preset_io.snapshot(modifier, name, preset_io.SURFACE)


def save_surface_preset(preset: dict, *, overwrite: bool = True) -> Path:
    fp = _surface_preset_path(preset["name"])
    if fp.exists() and not overwrite:
        raise FileExistsError(f"Preset surface existe déjà : {fp.name}")
    with fp.open("w", encoding="utf-8") as f:
        json.dump(preset, f, indent=2, ensure_ascii=False)
    return fp


def load_surface_preset(path) -> dict:
    fp = Path(path)
    with fp.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("kind") != "surface":
        raise ValueError(
            f"Preset {fp.name!r} : kind {data.get('kind')!r}, "
            f"surface (explicite) attendu"
        )
    schema = data.get("schema")
    if schema != SURFACE_SCHEMA_VERSION:
        raise ValueError(
            f"Preset surface {fp.name!r} : version de schéma "
            f"incompatible ({schema!r}, attendu {SURFACE_SCHEMA_VERSION})"
        )
    for required in ("name", "formula"):
        if required not in data:
            raise ValueError(
                f"Preset surface {fp.name!r} : champ {required!r} manquant"
            )
    return data


def delete_surface_preset(name: str) -> bool:
    fp = _surface_preset_path(name)
    if fp.exists():
        fp.unlink()
        return True
    from . import builtin_presets
    fp_builtin = _surface_presets_dir() / (
        builtin_presets.BUILTIN_SURFACE_FILE_PREFIX
        + _slugify(name) + ".json"
    )
    if fp_builtin.exists():
        fp_builtin.unlink()
        return True
    return False


def apply_surface_preset_to_modifier(preset: dict, modifier) -> dict:
    """Restore an explicit-surface preset into ``modifier``.

    Thin wrapper over the generic engine (see preset_io.SURFACE).
    """
    return preset_io.apply(preset, modifier, preset_io.SURFACE)


# =========================================================================== #
# Parametric surface (x(u,v), y(u,v), z(u,v)) preset system
# =========================================================================== #
# Conceptually similar to the explicit-surface system but stores three
# expressions instead of one, plus (u_0, v_0) instead of (x_0, y_0).

PARAMETRIC_SURFACE_PRESETS_SUBDIR = "presets/surface_param"
PARAMETRIC_SURFACE_SCHEMA_VERSION = 1


def _parametric_surface_presets_dir() -> Path:
    base = Path(bpy.utils.extension_path_user(__package__, create=True))
    pdir = base / PARAMETRIC_SURFACE_PRESETS_SUBDIR
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


def _parametric_surface_preset_path(name: str) -> Path:
    return _parametric_surface_presets_dir() / (_slugify(name) + ".json")


def find_parametric_surface_preset_file(name: str) -> Path | None:
    fp = _parametric_surface_preset_path(name)
    if fp.exists():
        return fp
    from . import builtin_presets
    fp_builtin = _parametric_surface_presets_dir() / (
        builtin_presets.BUILTIN_PARAMETRIC_SURFACE_FILE_PREFIX
        + _slugify(name) + ".json"
    )
    if fp_builtin.exists():
        return fp_builtin
    return None


def list_parametric_surface_presets() -> list:
    results = []
    for fp in _parametric_surface_presets_dir().glob("*.json"):
        try:
            with fp.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("kind") != "parametric_surface":
                continue
            disp, stable = _display_name(data, fp.stem)
            results.append((disp, stable, fp))
        except (json.JSONDecodeError, OSError):
            continue
    results.sort(key=lambda x: x[0].lower())
    return results


def snapshot_parametric_surface_modifier(modifier, name: str) -> dict:
    """Build a parametric-surface preset dict from a live modifier.

    Thin wrapper over the generic engine (see preset_io.PARAMETRIC_SURFACE).
    """
    return preset_io.snapshot(modifier, name, preset_io.PARAMETRIC_SURFACE)


def save_parametric_surface_preset(preset: dict, *,
                                     overwrite: bool = True) -> Path:
    fp = _parametric_surface_preset_path(preset["name"])
    if fp.exists() and not overwrite:
        raise FileExistsError(
            f"Preset surface paramétrée existe déjà : {fp.name}"
        )
    with fp.open("w", encoding="utf-8") as f:
        json.dump(preset, f, indent=2, ensure_ascii=False)
    return fp


def load_parametric_surface_preset(path) -> dict:
    fp = Path(path)
    with fp.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("kind") != "parametric_surface":
        raise ValueError(
            f"Preset {fp.name!r} : kind {data.get('kind')!r}, "
            f"parametric_surface attendu"
        )
    schema = data.get("schema")
    if schema != PARAMETRIC_SURFACE_SCHEMA_VERSION:
        raise ValueError(
            f"Preset paramétrique {fp.name!r} : schéma incompatible "
            f"({schema!r}, attendu {PARAMETRIC_SURFACE_SCHEMA_VERSION})"
        )
    for required in ("name", "formula"):
        if required not in data:
            raise ValueError(
                f"Preset {fp.name!r} : champ {required!r} manquant"
            )
    return data


def delete_parametric_surface_preset(name: str) -> bool:
    fp = _parametric_surface_preset_path(name)
    if fp.exists():
        fp.unlink()
        return True
    from . import builtin_presets
    fp_builtin = _parametric_surface_presets_dir() / (
        builtin_presets.BUILTIN_PARAMETRIC_SURFACE_FILE_PREFIX
        + _slugify(name) + ".json"
    )
    if fp_builtin.exists():
        fp_builtin.unlink()
        return True
    return False


def apply_parametric_surface_preset_to_modifier(preset: dict, modifier) -> dict:
    """Restore a parametric-surface preset into ``modifier``.

    Thin wrapper over the generic engine (see preset_io.PARAMETRIC_SURFACE).
    """
    return preset_io.apply(preset, modifier, preset_io.PARAMETRIC_SURFACE)


# =========================================================================== #
# 3D scalar field preset system
# =========================================================================== #
# Lives in ``presets/scalar_field_3d/``. Schema captures: the expression
# f(x, y, z), 3D box (x/y/z min/max + 3D resolution), basepoint (x_0,
# y_0, z_0), all marker/label sizes and materials, and free parameters.

SCALAR_FIELD_3D_PRESETS_SUBDIR = "presets/scalar_field_3d"
SCALAR_FIELD_3D_SCHEMA_VERSION = 1


def _scalar_field_3d_presets_dir() -> Path:
    base = Path(bpy.utils.extension_path_user(__package__, create=True))
    pdir = base / SCALAR_FIELD_3D_PRESETS_SUBDIR
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


def _scalar_field_3d_preset_path(name: str) -> Path:
    return _scalar_field_3d_presets_dir() / (_slugify(name) + ".json")


def find_scalar_field_3d_preset_file(name: str) -> Path | None:
    """Resolve a 3D scalar field preset name to an existing path."""
    fp = _scalar_field_3d_preset_path(name)
    if fp.exists():
        return fp
    from . import builtin_presets
    fp_builtin = _scalar_field_3d_presets_dir() / (
        builtin_presets.BUILTIN_SCALAR_FIELD_3D_FILE_PREFIX
        + _slugify(name) + ".json"
    )
    if fp_builtin.exists():
        return fp_builtin
    return None


def list_scalar_field_3d_presets() -> list:
    results = []
    for fp in _scalar_field_3d_presets_dir().glob("*.json"):
        try:
            with fp.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("kind") != "scalar_field_3d":
                continue
            disp, stable = _display_name(data, fp.stem)
            results.append((disp, stable, fp))
        except (json.JSONDecodeError, OSError):
            continue
    results.sort(key=lambda x: x[0].lower())
    return results


def snapshot_scalar_field_3d_modifier(modifier, name: str) -> dict:
    """Build a 3D scalar-field preset dict from a live modifier.

    Thin wrapper over the generic engine (see preset_io.SCALAR_FIELD_3D).
    """
    return preset_io.snapshot(modifier, name, preset_io.SCALAR_FIELD_3D)


def save_scalar_field_3d_preset(preset: dict, *,
                                  overwrite: bool = True) -> Path:
    fp = _scalar_field_3d_preset_path(preset["name"])
    if fp.exists() and not overwrite:
        raise FileExistsError(
            f"Preset champ scalaire 3D existe déjà : {fp.name}"
        )
    with fp.open("w", encoding="utf-8") as f:
        json.dump(preset, f, indent=2, ensure_ascii=False)
    return fp


def load_scalar_field_3d_preset(path) -> dict:
    fp = Path(path)
    with fp.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("kind") != "scalar_field_3d":
        raise ValueError(
            f"Preset {fp.name!r} : kind {data.get('kind')!r}, "
            f"scalar_field_3d attendu"
        )
    schema = data.get("schema")
    if schema != SCALAR_FIELD_3D_SCHEMA_VERSION:
        raise ValueError(
            f"Preset {fp.name!r} : schéma incompatible "
            f"({schema!r}, attendu {SCALAR_FIELD_3D_SCHEMA_VERSION})"
        )
    for required in ("name", "formula"):
        if required not in data:
            raise ValueError(f"Preset {fp.name!r} : champ {required!r} manquant")
    return data


def delete_scalar_field_3d_preset(name: str) -> bool:
    fp = _scalar_field_3d_preset_path(name)
    if fp.exists():
        fp.unlink()
        return True
    from . import builtin_presets
    fp_builtin = _scalar_field_3d_presets_dir() / (
        builtin_presets.BUILTIN_SCALAR_FIELD_3D_FILE_PREFIX
        + _slugify(name) + ".json"
    )
    if fp_builtin.exists():
        fp_builtin.unlink()
        return True
    return False


def apply_scalar_field_3d_preset_to_modifier(preset: dict, modifier) -> dict:
    """Restore a 3D scalar-field preset into ``modifier``.

    Thin wrapper over the generic engine (see preset_io.SCALAR_FIELD_3D).
    """
    return preset_io.apply(preset, modifier, preset_io.SCALAR_FIELD_3D)


# =========================================================================== #
# Vector field 3D (V: R³ → R³) preset system
# =========================================================================== #
# Two-mode preset: stores either the three components V_x, V_y, V_z
# explicitly, or a single scalar potential ϕ along with the mode flag.
# At load time we re-derive the field accordingly (computing the
# gradient again in the "from_potential" case so the panel can
# faithfully show "this field came from a potential" rather than
# pretending it was explicit).

VECTOR_FIELD_3D_PRESETS_SUBDIR = "presets/vector_field_3d"
VECTOR_FIELD_3D_SCHEMA_VERSION = 1


def _vector_field_3d_presets_dir() -> Path:
    base = Path(bpy.utils.extension_path_user(__package__, create=True))
    pdir = base / VECTOR_FIELD_3D_PRESETS_SUBDIR
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


def _vector_field_3d_preset_path(name: str) -> Path:
    return _vector_field_3d_presets_dir() / (_slugify(name) + ".json")


def find_vector_field_3d_preset_file(name: str) -> Path | None:
    fp = _vector_field_3d_preset_path(name)
    if fp.exists():
        return fp
    from . import builtin_presets
    fp_builtin = _vector_field_3d_presets_dir() / (
        builtin_presets.BUILTIN_VECTOR_FIELD_3D_FILE_PREFIX
        + _slugify(name) + ".json"
    )
    if fp_builtin.exists():
        return fp_builtin
    return None


def list_vector_field_3d_presets() -> list:
    results = []
    for fp in _vector_field_3d_presets_dir().glob("*.json"):
        try:
            with fp.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("kind") != "vector_field_3d":
                continue
            disp, stable = _display_name(data, fp.stem)
            results.append((disp, stable, fp))
        except (json.JSONDecodeError, OSError):
            continue
    results.sort(key=lambda x: x[0].lower())
    return results


def snapshot_vector_field_3d_modifier(modifier, name: str) -> dict:
    """Build a 3D vector-field preset dict from a live modifier.

    Thin wrapper over the generic engine (see preset_io.VECTOR_FIELD_3D).
    """
    return preset_io.snapshot(modifier, name, preset_io.VECTOR_FIELD_3D)


def save_vector_field_3d_preset(preset: dict, *, overwrite: bool = True) -> Path:
    fp = _vector_field_3d_preset_path(preset["name"])
    if fp.exists() and not overwrite:
        raise FileExistsError(
            f"Preset champ de vecteurs existe déjà : {fp.name}"
        )
    with fp.open("w", encoding="utf-8") as f:
        json.dump(preset, f, indent=2, ensure_ascii=False)
    return fp


def load_vector_field_3d_preset(path) -> dict:
    fp = Path(path)
    with fp.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("kind") != "vector_field_3d":
        raise ValueError(
            f"Preset {fp.name!r} : kind {data.get('kind')!r}, "
            f"vector_field_3d attendu"
        )
    schema = data.get("schema")
    if schema != VECTOR_FIELD_3D_SCHEMA_VERSION:
        raise ValueError(
            f"Preset champ de vecteurs {fp.name!r} : schéma incompatible "
            f"({schema!r}, attendu {VECTOR_FIELD_3D_SCHEMA_VERSION})"
        )
    for required in ("name", "formula"):
        if required not in data:
            raise ValueError(
                f"Preset {fp.name!r} : champ {required!r} manquant"
            )
    return data


def delete_vector_field_3d_preset(name: str) -> bool:
    fp = _vector_field_3d_preset_path(name)
    if fp.exists():
        fp.unlink()
        return True
    from . import builtin_presets
    fp_builtin = _vector_field_3d_presets_dir() / (
        builtin_presets.BUILTIN_VECTOR_FIELD_3D_FILE_PREFIX
        + _slugify(name) + ".json"
    )
    if fp_builtin.exists():
        fp_builtin.unlink()
        return True
    return False


def apply_vector_field_3d_preset_to_modifier(preset: dict, modifier) -> dict:
    """Restore a 3D vector-field preset into ``modifier``.

    Thin wrapper over the generic engine (see preset_io.VECTOR_FIELD_3D).
    """
    return preset_io.apply(preset, modifier, preset_io.VECTOR_FIELD_3D)


# =========================================================================== #
# Vector bench preset system
# =========================================================================== #
# The bench stores a variable number of named vector rows (its core data is
# the expressions, in ``formula.rows``) plus per-row socket values (show +
# material) under ``slots`` and the shared scalar parameters under ``params``.
# Lives in ``presets/vector_bench/``.

VECTOR_BENCH_PRESETS_SUBDIR = "presets/vector_bench"
VECTOR_BENCH_SCHEMA_VERSION = 1


def _vector_bench_presets_dir() -> Path:
    base = Path(bpy.utils.extension_path_user(__package__, create=True))
    pdir = base / VECTOR_BENCH_PRESETS_SUBDIR
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


def _vector_bench_preset_path(name: str) -> Path:
    return _vector_bench_presets_dir() / (_slugify(name) + ".json")


def find_vector_bench_preset_file(name: str) -> Path | None:
    fp = _vector_bench_preset_path(name)
    if fp.exists():
        return fp
    from . import builtin_presets
    fp_builtin = _vector_bench_presets_dir() / (
        builtin_presets.BUILTIN_VECTOR_BENCH_FILE_PREFIX
        + _slugify(name) + ".json"
    )
    if fp_builtin.exists():
        return fp_builtin
    return None


def list_vector_bench_presets() -> list:
    results = []
    for fp in _vector_bench_presets_dir().glob("*.json"):
        try:
            with fp.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("kind") != "vector_bench":
                continue
            disp, stable = _display_name(data, fp.stem)
            results.append((disp, stable, fp))
        except (json.JSONDecodeError, OSError):
            continue
    results.sort(key=lambda x: x[0].lower())
    return results


def snapshot_vector_bench_modifier(modifier, name: str) -> dict:
    """Build a vector-bench preset dict from a live modifier."""
    return preset_io.snapshot(modifier, name, preset_io.VECTOR_BENCH)


def save_vector_bench_preset(preset: dict, *, overwrite: bool = True) -> Path:
    fp = _vector_bench_preset_path(preset["name"])
    if fp.exists() and not overwrite:
        raise FileExistsError(f"Preset banc existe déjà : {fp.name}")
    with fp.open("w", encoding="utf-8") as f:
        json.dump(preset, f, indent=2, ensure_ascii=False)
    return fp


def load_vector_bench_preset(path) -> dict:
    fp = Path(path)
    with fp.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("kind") != "vector_bench":
        raise ValueError(
            f"Preset {fp.name!r} : kind {data.get('kind')!r}, "
            f"vector_bench attendu"
        )
    schema = data.get("schema")
    if schema != VECTOR_BENCH_SCHEMA_VERSION:
        raise ValueError(
            f"Preset banc {fp.name!r} : version de schéma incompatible "
            f"({schema!r}, attendu {VECTOR_BENCH_SCHEMA_VERSION})"
        )
    for required in ("name", "formula"):
        if required not in data:
            raise ValueError(
                f"Preset banc {fp.name!r} : champ {required!r} manquant"
            )
    return data


def delete_vector_bench_preset(name: str) -> bool:
    fp = _vector_bench_preset_path(name)
    if fp.exists():
        fp.unlink()
        return True
    from . import builtin_presets
    fp_builtin = _vector_bench_presets_dir() / (
        builtin_presets.BUILTIN_VECTOR_BENCH_FILE_PREFIX
        + _slugify(name) + ".json"
    )
    if fp_builtin.exists():
        fp_builtin.unlink()
        return True
    return False


def apply_vector_bench_preset_to_modifier(preset: dict, modifier) -> dict:
    """Restore a vector-bench preset into ``modifier``.

    Ensures the palette materials exist first, so applying a built-in
    bench (which references RealFn palette materials by name) colours the
    arrows even if the user never installed the defaults explicitly.
    """
    try:
        from . import default_materials
        default_materials.ensure_default_materials()
    except Exception:
        pass
    return preset_io.apply(preset, modifier, preset_io.VECTOR_BENCH)

