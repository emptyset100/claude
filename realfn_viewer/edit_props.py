"""
Live in-panel formula editing + auto-update for the six classic RealFn
kinds (scalar curve, vector function F(t), explicit & parametric surfaces,
3D scalar & vector fields). The vector *bench* has its own editor
(:mod:`bench_props`); this module covers everything else.

Strategy: reuse the preset machinery. To rebuild after an edit we take a
full :func:`presets.snapshot_*` of the live modifier (which already knows
each kind's complete schema — ranges, orders, var names, materials,
parameter values…), override only the *formula* with the edited text,
rebuild the tree with the per-kind ``preset_ops._rebuild_*`` and re-apply
the snapshot. Everything except the formula is therefore preserved.

The rebuild is deferred to a zero-delay ``bpy.app.timers`` tick so it runs
outside the property-write/UI context (same rationale as bench_props).
"""

from __future__ import annotations

import bpy

from . import presets


_SYNC = [False]

# Debounce state: object-name → pending generation counter.
# Each keystroke bumps the counter and schedules a 300 ms timer.
# When the timer fires it compares its captured generation against the
# current one; if a newer edit arrived in the meantime, it's a no-op.
# Only the *last* timer per object actually triggers a rebuild.
_PENDING: dict[str, int] = {}

EDITABLE_KINDS = ("scalar", "vector", "surface", "parametric_surface",
                  "scalar_field_3d", "vector_field_3d")


# --------------------------------------------------------------------------- #
# Maps (built lazily to avoid import-time cycles)
# --------------------------------------------------------------------------- #
def _snap_apply(kind):
    m = {
        "scalar": (presets.snapshot_modifier,
                   presets.apply_preset_to_modifier),
        "vector": (presets.snapshot_vector_modifier,
                   presets.apply_vector_preset_to_modifier),
        "surface": (presets.snapshot_surface_modifier,
                    presets.apply_surface_preset_to_modifier),
        "parametric_surface": (presets.snapshot_parametric_surface_modifier,
                               presets.apply_parametric_surface_preset_to_modifier),
        "scalar_field_3d": (presets.snapshot_scalar_field_3d_modifier,
                            presets.apply_scalar_field_3d_preset_to_modifier),
        "vector_field_3d": (presets.snapshot_vector_field_3d_modifier,
                           presets.apply_vector_field_3d_preset_to_modifier),
    }
    return m.get(kind, (None, None))


def _rebuild_fn(kind):
    from . import preset_ops
    return {
        "scalar": preset_ops._rebuild_scalar,
        "vector": preset_ops._rebuild_vector,
        "surface": preset_ops._rebuild_surface,
        "parametric_surface": preset_ops._rebuild_parametric,
        "scalar_field_3d": preset_ops._rebuild_scalar_field_3d,
        "vector_field_3d": preset_ops._rebuild_vector_field_3d,
    }.get(kind)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _realfn_mod(obj):
    if obj is None:
        return None
    for m in obj.modifiers:
        ng = getattr(m, "node_group", None)
        if (m.type == "NODES" and ng is not None
                and (ng.get("realfn_kind") is not None
                     or ng.name.startswith("REALFN"))):
            return m
    return None


def _params_list(ep):
    return [s.strip() for s in ep.params.split(",") if s.strip()]


def _override_formula(kind, data, ep):
    f = data.setdefault("formula", {})
    f["allowed_params"] = _params_list(ep)
    if kind in ("scalar", "vector", "surface", "scalar_field_3d"):
        f["expr"] = ep.expr
    elif kind == "parametric_surface":
        f["components"] = [ep.comp_x, ep.comp_y, ep.comp_z]
    elif kind == "vector_field_3d":
        if f.get("mode") == "from_potential":
            f["potential"] = ep.potential
        else:
            f["components"] = [ep.comp_x, ep.comp_y, ep.comp_z]


def rebuild_edit(obj) -> str:
    """Rebuild ``obj``'s function from the edited formula, preserving the
    rest (ranges, orders, materials, parameters). Returns ''/error."""
    mod = _realfn_mod(obj)
    if mod is None:
        return "Pas de fonction RealFn active"
    kind = mod.node_group.get("realfn_kind") or "scalar"
    if kind not in EDITABLE_KINDS:
        return ""  # bench is handled by bench_props
    ep = getattr(obj, "realfn_edit", None)
    if ep is None:
        return "Pas d'edition"
    snap, apply_fn = _snap_apply(kind)
    rebuild = _rebuild_fn(kind)
    if snap is None or rebuild is None:
        return "Type non editable"

    # Full current state, then override only the formula.
    data = snap(mod, str(mod.node_group.get("name") or "edit"))
    _override_formula(kind, data, ep)

    old = mod.node_group
    try:
        new_nt = rebuild(data)
    except ValueError as exc:
        return str(exc)

    mod.node_group = new_nt
    try:
        apply_fn(data, mod)
    except Exception:
        pass
    from .compiler import release_tree
    release_tree(old, keep=new_nt)
    try:
        obj.data.update()
    except Exception:
        pass
    return ""


# --------------------------------------------------------------------------- #
# Sync props from the live tree (after create / preset apply)
# --------------------------------------------------------------------------- #
def sync_from_tree(obj):
    mod = _realfn_mod(obj)
    if mod is None:
        return
    nt = mod.node_group
    kind = nt.get("realfn_kind") or "scalar"
    if kind not in EDITABLE_KINDS:
        return  # bench / unknown
    ep = getattr(obj, "realfn_edit", None)
    if ep is None:
        return
    _SYNC[0] = True
    try:
        ep.params = ", ".join(str(p) for p in (nt.get("realfn_params") or []))
        ep.error = ""
        ep.expr = ep.comp_x = ep.comp_y = ep.comp_z = ep.potential = ""
        if kind in ("scalar", "vector", "surface", "scalar_field_3d"):
            ep.expr = str(nt.get("realfn_expr", "0"))
        elif kind == "parametric_surface":
            comps = list(nt.get("realfn_components_text") or ["0", "0", "0"])
            comps = (comps + ["", "", ""])[:3]
            ep.comp_x, ep.comp_y, ep.comp_z = (str(comps[0]), str(comps[1]),
                                               str(comps[2]))
        elif kind == "vector_field_3d":
            if str(nt.get("realfn_mode", "explicit")) == "from_potential":
                ep.potential = str(nt.get("realfn_potential", "0"))
            else:
                comps = list(nt.get("realfn_components_source")
                             or ["0", "0", "0"])
                comps = (comps + ["", "", ""])[:3]
                ep.comp_x, ep.comp_y, ep.comp_z = (str(comps[0]),
                                                   str(comps[1]),
                                                   str(comps[2]))
    finally:
        _SYNC[0] = False


# --------------------------------------------------------------------------- #
# Update callback (deferred)
# --------------------------------------------------------------------------- #
def _on_edit(self, context):
    if _SYNC[0] or not self.auto_update:
        return
    obj = getattr(context, "object", None) or bpy.context.object
    if obj is None or getattr(obj, "realfn_edit", None) is None:
        return
    if _realfn_mod(obj) is None:
        return
    name = obj.name
    gen = _PENDING.get(name, 0) + 1
    _PENDING[name] = gen

    def _deferred(_name=name, _gen=gen):
        # A newer edit arrived while we were waiting — skip this one.
        if _PENDING.get(_name) != _gen:
            return None
        _PENDING.pop(_name, None)
        o = bpy.data.objects.get(_name)
        if o is not None and getattr(o, "realfn_edit", None) is not None:
            err = rebuild_edit(o)
            try:
                o.realfn_edit.error = err
            except Exception:
                pass
        return None

    bpy.app.timers.register(_deferred, first_interval=0.3)


# --------------------------------------------------------------------------- #
# Property group
# --------------------------------------------------------------------------- #
def _str():
    return bpy.props.StringProperty(update=_on_edit)


class RealFnEditProps(bpy.types.PropertyGroup):
    expr: _str()
    comp_x: _str()
    comp_y: _str()
    comp_z: _str()
    potential: _str()
    params: bpy.props.StringProperty(
        name="Paramètres",
        description="Symboles libres (séparés par des virgules) → sliders",
        update=_on_edit)
    auto_update: bpy.props.BoolProperty(
        name="Mise à jour auto",
        description="Reconstruit la fonction automatiquement à chaque "
                    "modification de la formule ou des paramètres",
        default=True)
    error: bpy.props.StringProperty(default="")


def register():
    bpy.utils.register_class(RealFnEditProps)
    bpy.types.Object.realfn_edit = bpy.props.PointerProperty(
        type=RealFnEditProps)


def unregister():
    if hasattr(bpy.types.Object, "realfn_edit"):
        del bpy.types.Object.realfn_edit
    bpy.utils.unregister_class(RealFnEditProps)
