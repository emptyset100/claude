"""
Cross-object synchronisation of the ``x_0`` basepoint.

When ``scene.realfn_sync_x0`` is enabled, scrubbing the x₀ slider of
any RealFn object should propagate that value to every other RealFn
object in the scene. Without this, comparing the tangent / Taylor
behaviour of two functions at the same point of interest means
manually moving multiple sliders in sync.

Implementation
--------------
We rely on ``bpy.app.handlers.depsgraph_update_post``, the handler
that fires after every dependency-graph evaluation (i.e. after almost
any user-visible change). When the handler runs we:

1. Bail out fast if the sync toggle is off.
2. Identify the *active object's* x₀ value (only the active object
   is considered the "source of truth" — otherwise a feedback loop
   would form between the objects writing to each other).
3. Write that value into every *other* RealFn object's x₀ socket,
   skipping objects whose current x₀ already matches (to avoid
   triggering yet another depsgraph update on a no-op write).

A guard flag ``_in_sync_handler`` prevents the handler from
re-entering itself if Blender fires update events for the writes
we ourselves performed.

Performance
-----------
For typical scenes with a handful of RealFn objects the cost is a few
dict lookups per depsgraph update — negligible. The handler is a
no-op when the toggle is off, so users who don't use the feature pay
nothing.
"""

from __future__ import annotations

import bpy


# Reentrancy guard. ``bpy.app.handlers`` callbacks can fire recursively
# if the work they perform triggers further depsgraph updates — which
# is exactly what writing to a modifier socket does. The flag is a
# 1-element list (rather than a module-level bool) so it can be
# mutated by inner closures without ``nonlocal`` ceremony.
_IN_SYNC = [False]

# Floating-point comparison epsilon for "this socket already has the
# value we'd write" — anything smaller than this we treat as equal.
# 1e-6 is two orders of magnitude smaller than the smallest useful
# x₀ increment a user would scrub by hand.
_EPSILON = 1e-6


def _find_x0_socket_id(node_group) -> str | None:
    """Look up the modifier-side identifier of the ``x_0`` socket.

    Returns ``None`` if this node group isn't one of ours, or doesn't
    have an x_0 input (legacy tree from before the basepoint feature).
    Cached on the node group itself so the per-frame cost is one
    attribute access in steady state.
    """
    cached = node_group.get("_realfn_x0_identifier")
    if cached:
        return str(cached)
    for item in node_group.interface.items_tree:
        if (getattr(item, "in_out", None) == "INPUT"
                and item.name == "x_0"):
            ident = item.identifier
            node_group["_realfn_x0_identifier"] = ident
            return ident
    return None


_REALFN_KINDS = frozenset({
    "scalar", "vector", "surface", "parametric_surface",
    "scalar_field_3d", "vector_field_3d", "vector_bench",
})


def _is_realfn_modifier(mod) -> bool:
    """True if ``mod`` is one of our Geometry Nodes modifiers."""
    if mod.type != "NODES" or mod.node_group is None:
        return False
    ng = mod.node_group
    # Primary: ``realfn_kind`` metadata stash present on every tree
    # built since v2. Robust against Blender auto-suffixing tree names
    # with ".001" when duplicating objects.
    if ng.get("realfn_kind") in _REALFN_KINDS:
        return True
    # Legacy fallback for trees built before ``realfn_kind`` was added.
    return "realfn_expr" in ng or "realfn_components_text" in ng


def _iter_realfn_modifiers(scene):
    """Yield every RealFn modifier in the scene, alongside its object."""
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        for mod in obj.modifiers:
            if _is_realfn_modifier(mod):
                yield obj, mod


@bpy.app.handlers.persistent
def _depsgraph_handler(scene, _depsgraph):
    """Propagate the active object's ``x_0`` to all others.

    ``persistent`` decoration keeps the handler registered across
    .blend file loads, which is the behaviour the user expects.
    """
    if _IN_SYNC[0]:
        return
    if not getattr(scene, "realfn_sync_x0", False):
        return

    # The active object is the source of truth. If none is active or
    # the active one isn't a RealFn, there's no canonical x₀ to
    # propagate — wait for the next event.
    active = bpy.context.view_layer.objects.active if bpy.context.view_layer else None
    if active is None or active.type != "MESH":
        return
    source_mod = None
    for mod in active.modifiers:
        if _is_realfn_modifier(mod):
            source_mod = mod
            break
    if source_mod is None:
        return

    src_id = _find_x0_socket_id(source_mod.node_group)
    if src_id is None:
        return
    try:
        src_value = float(source_mod[src_id])
    except (KeyError, TypeError, ValueError):
        return

    # Propagate. Re-entrant updates from our own writes are blocked
    # by ``_IN_SYNC[0]``.
    _IN_SYNC[0] = True
    try:
        for obj, mod in _iter_realfn_modifiers(scene):
            if mod is source_mod:
                continue
            dst_id = _find_x0_socket_id(mod.node_group)
            if dst_id is None:
                continue
            try:
                current = float(mod[dst_id])
            except (KeyError, TypeError, ValueError):
                current = None
            if current is not None and abs(current - src_value) < _EPSILON:
                continue
            try:
                mod[dst_id] = src_value
            except (KeyError, TypeError, ValueError):
                continue
            # Force the receiving object's modifier to re-evaluate.
            # Same trick as in the visibility operators — the rebind
            # plus update_tag ensures the geometry actually refreshes.
            mod.node_group = mod.node_group
            try:
                obj.update_tag(refresh={'OBJECT'})
            except TypeError:
                obj.update_tag()
    finally:
        _IN_SYNC[0] = False


def register():
    """Register the sync handler + the scene toggle.

    Idempotent — re-registration just deduplicates."""
    if not hasattr(bpy.types.Scene, "realfn_sync_x0"):
        bpy.types.Scene.realfn_sync_x0 = bpy.props.BoolProperty(
            name="Synchroniser x₀",
            description=(
                "Si coché, scrubber x₀ sur n'importe quel objet "
                "RealFn propage la valeur à tous les autres objets "
                "RealFn de la scène. Permet de comparer plusieurs "
                "fonctions au même point de tangence"
            ),
            default=False,
        )
    if _depsgraph_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_depsgraph_handler)


def unregister():
    """Unregister the sync handler + remove the scene toggle.
    Idempotent."""
    try:
        bpy.app.handlers.depsgraph_update_post.remove(_depsgraph_handler)
    except ValueError:
        pass
    if hasattr(bpy.types.Scene, "realfn_sync_x0"):
        del bpy.types.Scene.realfn_sync_x0
