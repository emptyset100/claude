"""
Editable bench definition + live auto-update.

Each vector-bench object carries a :class:`RealFnBenchProps` (via
``Object.realfn_bench``) holding the editable name/expression of every
row plus the parameter list. The panel draws these as text fields; when
a field is committed and *auto-update* is on, the bench's Geometry-Nodes
tree is rebuilt — preserving the live socket values (parameter sliders,
visibility, materials) wherever the socket names still match.

The actual rebuild is deferred to a zero-delay ``bpy.app.timers`` tick so
it runs *outside* the property-write/UI context, where creating and
removing node-group datablocks is unrestricted.
"""

from __future__ import annotations

import bpy

from . import bench_tree, default_materials, preset_io


_BENCH_PALETTE = ("Bleu", "Vert", "Rouge", "Jaune",
                  "Magenta", "Cyan", "Orange", "Gris")

# Suppresses the update callback while we populate the props
# programmatically (create / preset apply / sync-from-tree).
_SYNC = [False]

N_ROWS = 6


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _bench_mod(obj):
    if obj is None:
        return None
    for m in obj.modifiers:
        ng = getattr(m, "node_group", None)
        if (m.type == "NODES" and ng is not None
                and ng.get("realfn_kind") == "vector_bench"):
            return m
    return None


def _rows_of(bp):
    """Ordered (name, expr) of the non-empty rows, names defaulting to vN."""
    out = []
    for i in range(1, N_ROWS + 1):
        expr = getattr(bp, f"expr{i}").strip()
        if not expr:
            continue
        name = getattr(bp, f"name{i}").strip() or f"v{i}"
        out.append((name, expr))
    return out


def rebuild_bench(obj) -> str:
    """Rebuild ``obj``'s bench tree from its editable props, preserving
    socket values by name. Returns '' on success or an error message."""
    bp = getattr(obj, "realfn_bench", None)
    if bp is None:
        return "Pas de banc"
    rows = _rows_of(bp)
    if not rows:
        return "Aucun vecteur"
    names = [n for n, _ in rows]
    if len(set(names)) != len(names):
        return "Noms de vecteurs en double"
    params = tuple(s.strip() for s in bp.params.split(",") if s.strip())

    mod = _bench_mod(obj)
    if mod is None:
        return "Banc introuvable sur l'objet"
    old = mod.node_group

    # Capture current input-socket values by socket name.
    saved = {}
    if old is not None:
        for it in old.interface.items_tree:
            if getattr(it, "in_out", None) != "INPUT":
                continue
            try:
                saved[it.name] = mod[it.identifier]
            except KeyError:
                saved[it.name] = getattr(it, "default_value", None)

    try:
        nt = bench_tree.make_vector_bench_tree(rows, allowed_params=params)
    except ValueError as exc:
        return str(exc)

    mod.node_group = nt
    default_materials.ensure_default_materials()
    by = {it.name: it for it in nt.interface.items_tree
          if getattr(it, "in_out", None) == "INPUT"}

    # Restore matching socket values (params kept, show/material kept).
    for name, it in by.items():
        if name in saved and saved[name] is not None:
            preset_io.set_modifier_socket(mod, it, saved[name])

    # Colour any row whose material socket is still empty (new rows).
    for idx, (rname, _) in enumerate(rows):
        it = by.get(f"Matériau · {rname}")
        if it is not None and not mod.get(it.identifier):
            mat = default_materials.get_palette_material(
                _BENCH_PALETTE[idx % len(_BENCH_PALETTE)])
            if mat is not None:
                try:
                    mod[it.identifier] = mat
                except (TypeError, KeyError):
                    pass

    # Drop the now-orphaned old tree (safe at timer time).
    if old is not None and old is not nt and old.users == 0:
        try:
            bpy.data.node_groups.remove(old)
        except Exception:
            pass

    try:
        obj.data.update()
    except Exception:
        pass
    return ""


# --------------------------------------------------------------------------- #
# Programmatic population (no rebuild)
# --------------------------------------------------------------------------- #
def set_bench_props(obj, rows, params):
    """Fill the editable props from ``rows`` (list of (name, expr)) and
    ``params`` (iterable) without firing the update callback."""
    bp = getattr(obj, "realfn_bench", None)
    if bp is None:
        return
    _SYNC[0] = True
    try:
        for i in range(1, N_ROWS + 1):
            setattr(bp, f"name{i}", "")
            setattr(bp, f"expr{i}", "")
        for i, (name, expr) in enumerate(list(rows)[:N_ROWS], start=1):
            setattr(bp, f"name{i}", str(name))
            setattr(bp, f"expr{i}", str(expr))
        bp.params = ", ".join(str(p) for p in params)
        bp.error = ""
    finally:
        _SYNC[0] = False


def sync_from_tree(obj):
    """Refill the editable props from the object's bench node-group
    metadata (used after a preset apply rebuilt the tree)."""
    mod = _bench_mod(obj)
    if mod is None:
        return
    ng = mod.node_group
    names = list(ng.get("realfn_bench_names") or [])
    exprs = list(ng.get("realfn_bench_exprs") or [])
    params = list(ng.get("realfn_params") or [])
    set_bench_props(obj, list(zip(names, exprs)), params)


# --------------------------------------------------------------------------- #
# Update callback (deferred rebuild)
# --------------------------------------------------------------------------- #
def _on_edit(self, context):
    if _SYNC[0] or not self.auto_update:
        return
    obj = getattr(context, "object", None) or bpy.context.object
    if obj is None or getattr(obj, "realfn_bench", None) is None:
        return
    if _bench_mod(obj) is None:
        return
    name = obj.name

    def _deferred():
        o = bpy.data.objects.get(name)
        if o is not None and getattr(o, "realfn_bench", None) is not None:
            err = rebuild_bench(o)
            try:
                o.realfn_bench.error = err   # no update cb on `error`
            except Exception:
                pass
        return None  # one-shot

    # Defer to the next idle tick — outside the property-write context.
    bpy.app.timers.register(_deferred, first_interval=0.0)


# --------------------------------------------------------------------------- #
# Property group
# --------------------------------------------------------------------------- #
def _str(default=""):
    return bpy.props.StringProperty(default=default, update=_on_edit)


class RealFnBenchProps(bpy.types.PropertyGroup):
    name1: _str("v1")
    expr1: _str()
    name2: _str("v2")
    expr2: _str()
    name3: _str("v3")
    expr3: _str()
    name4: _str("v4")
    expr4: _str()
    name5: _str("v5")
    expr5: _str()
    name6: _str("v6")
    expr6: _str()
    params: bpy.props.StringProperty(
        name="Paramètres",
        description="Symboles scalaires (séparés par des virgules) → sliders",
        update=_on_edit,
    )
    auto_update: bpy.props.BoolProperty(
        name="Mise à jour auto",
        description="Reconstruit le banc automatiquement à chaque modification "
                    "d'une formule ou des paramètres",
        default=True,
    )
    error: bpy.props.StringProperty(default="")


def register():
    bpy.utils.register_class(RealFnBenchProps)
    bpy.types.Object.realfn_bench = bpy.props.PointerProperty(
        type=RealFnBenchProps)


def unregister():
    if hasattr(bpy.types.Object, "realfn_bench"):
        del bpy.types.Object.realfn_bench
    bpy.utils.unregister_class(RealFnBenchProps)
