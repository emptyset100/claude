"""
Auto-snapshot of RealFn modifiers into the .blend file.

The mechanism is straightforward but has a couple of subtle aspects
that justify a dedicated module:

1. Hook the ``save_pre`` Blender handler so the snapshot is captured
   *just before* the user saves their .blend — no manual action
   needed. The snapshot is stored as a JSON-encoded IDProperty
   on the node_group of each RealFn modifier (scalar or vector).
   Because IDProperties on node groups are saved with the .blend,
   the snapshot travels with the file automatically.

2. Provide a restore operation that, given a modifier with a stored
   snapshot, rebuilds its tree from the snapshot's formula and
   restores all socket values. This is exactly the same pipeline
   used by the "apply preset" operator — we just hand it the
   snapshot dict instead of a preset loaded from disk.

Why store on the node_group rather than the object or the modifier?

* The modifier itself doesn't accept arbitrary IDProperties in a
  way that persists across .blend roundtrips reliably in Blender 4.x.
* The object does, but the link "object ↔ which modifier" becomes
  ambiguous if a user adds several RealFn modifiers to one object
  (admittedly uncommon, but the node-group choice avoids the
  ambiguity entirely).
* The node_group is the natural locus of identity for a RealFn
  curve — that's where ``realfn_kind``, ``realfn_expr`` and the
  other metadata already live.

The JSON encoding is the same schema used by user-saved presets,
so a future feature like "export the stored snapshot as a preset"
would be a one-liner.
"""

from __future__ import annotations

import json

import bpy

from . import (bench_tree, parametric_surface_tree, scalar_field_3d_tree,
               surface_tree, tree, vector_field_3d_tree, vector_tree)


def _tree_prefixes():
    """All seven RealFn node-tree name prefixes, one per kind.

    Centralised so :func:`_iter_realfn_modifiers` snapshots *every*
    RealFn kind (curve, vector, surface, parametric surface, 3D scalar
    field, 3D vector field, vector bench) rather than just curves and
    vectors.
    """
    return (
        tree.TREE_PREFIX,
        vector_tree.VECTOR_TREE_PREFIX,
        surface_tree.SURFACE_TREE_PREFIX,
        parametric_surface_tree.PARAMETRIC_SURFACE_TREE_PREFIX,
        scalar_field_3d_tree.SCALAR_FIELD_3D_TREE_PREFIX,
        vector_field_3d_tree.VECTOR_FIELD_3D_TREE_PREFIX,
        bench_tree.BENCH_TREE_PREFIX,
    )


SNAPSHOT_PROP = "realfn_snapshot"
SNAPSHOT_SAVED_AT_PROP = "realfn_snapshot_saved_at"


# --------------------------------------------------------------------------- #
# Snapshotting
# --------------------------------------------------------------------------- #
def _iter_realfn_modifiers(scene):
    """Yield every (object, modifier) pair in the scene whose modifier
    is one of ours (scalar or vector).

    Iterates ``scene.objects`` rather than ``bpy.data.objects`` so a
    multi-scene .blend snapshots only the active scene's RealFn
    objects — which matches the natural "save the current scene's
    state" expectation.
    """
    for obj in scene.objects:
        for mod in getattr(obj, "modifiers", []):
            if mod.type != "NODES" or mod.node_group is None:
                continue
            name = mod.node_group.name
            if any(name.startswith(p) for p in _tree_prefixes()):
                yield obj, mod


def _snapshot_modifier(modifier) -> dict | None:
    """Snapshot a single modifier into a preset-shaped dict.

    Returns None if the modifier's kind is unknown — that shouldn't
    happen in practice since the dispatch in :func:`_iter_realfn_modifiers`
    already filters to known prefixes, but the defensive check makes
    the intent explicit and survives future code where the iteration
    is replaced by something less strict.
    """
    # Imported lazily to avoid pulling presets.py at module import time
    # — it's not needed unless we're actually saving.
    from . import presets

    nt = modifier.node_group
    kind = nt.get("realfn_kind", "scalar")
    # Build a short human-readable label for the snapshot. Vector bench
    # trees don't stash ``realfn_expr``; fall back to the first row name.
    if kind == "vector_bench":
        names = list(nt.get("realfn_bench_names") or [])
        name = names[0] if names else "bench"
    else:
        name = nt.get("realfn_expr", "snapshot")
    label = f"snapshot:{name}"

    # One snapshot builder per kind. Every builder shares the signature
    # ``(modifier, name) -> dict``, so the dispatch is a plain lookup.
    builders = {
        "scalar": presets.snapshot_modifier,
        "vector": presets.snapshot_vector_modifier,
        "surface": presets.snapshot_surface_modifier,
        "parametric_surface": presets.snapshot_parametric_surface_modifier,
        "scalar_field_3d": presets.snapshot_scalar_field_3d_modifier,
        "vector_field_3d": presets.snapshot_vector_field_3d_modifier,
        "vector_bench": presets.snapshot_vector_bench_modifier,
    }
    builder = builders.get(kind)
    if builder is None:
        return None
    return builder(modifier, label)


@bpy.app.handlers.persistent
def _snapshot_on_save(_self):
    """``save_pre`` handler: stash a JSON snapshot on every RealFn
    modifier's node_group.

    Why ``save_pre`` rather than ``save_post``?
    --------------------------------------------
    We need the IDProperty assignment to happen *before* Blender
    writes the file to disk, so the snapshot ends up baked into the
    saved .blend. ``save_post`` fires after writing and would only
    update the in-memory state — the user would have to save again
    for the snapshot to actually persist.
    """
    # Errors here should never block a save. Wrap broadly and log;
    # the user sees nothing intrusive but a console message exists
    # if anything goes wrong.
    try:
        scene = bpy.context.scene
        if scene is None:
            return
        n = 0
        for _obj, mod in _iter_realfn_modifiers(scene):
            data = _snapshot_modifier(mod)
            if data is None:
                continue
            # ``ensure_ascii=False`` keeps French accents readable
            # when inspecting the file with a hex editor or a JSON
            # tool that displays string properties.
            try:
                mod.node_group[SNAPSHOT_PROP] = json.dumps(
                    data, ensure_ascii=False,
                )
                # Lightweight metadata for the panel to display.
                import datetime
                mod.node_group[SNAPSHOT_SAVED_AT_PROP] = (
                    datetime.datetime.now().isoformat(timespec="seconds")
                )
                n += 1
            except (TypeError, ValueError):
                # Should be impossible — snapshot dicts are plain
                # JSON-serialisable structures by construction —
                # but guard against future schema changes that might
                # introduce non-serialisable types.
                pass
        if n:
            print(f"[RealFn] save_pre: snapshotted {n} RealFn "
                   f"modifier(s) into the .blend")
    except Exception as exc:
        print(f"[RealFn] save_pre snapshot skipped: {exc}")


# --------------------------------------------------------------------------- #
# Restoration helpers
# --------------------------------------------------------------------------- #
def get_stored_snapshot(modifier) -> dict | None:
    """Return the JSON-decoded snapshot stored on this modifier's
    node_group, or None if no snapshot is present.

    Used by the panel to decide whether to show the "Restaurer"
    button, and by the restore operator to fetch the data.
    """
    if modifier is None or modifier.node_group is None:
        return None
    raw = modifier.node_group.get(SNAPSHOT_PROP)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def get_snapshot_timestamp(modifier) -> str | None:
    """Return the ISO timestamp of the last snapshot, or None.

    Stored as a separate IDProperty so reading it doesn't require
    decoding the full JSON snapshot.
    """
    if modifier is None or modifier.node_group is None:
        return None
    return modifier.node_group.get(SNAPSHOT_SAVED_AT_PROP) or None


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def register():
    # Idempotent registration: if Blender reloads scripts mid-session
    # the same handler can land in the list twice, so we check first.
    if _snapshot_on_save not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(_snapshot_on_save)


def unregister():
    if _snapshot_on_save in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(_snapshot_on_save)
