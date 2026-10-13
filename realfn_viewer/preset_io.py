"""
Generic, data-driven preset snapshot/apply engine.

Background
----------
Each of the six RealFn object kinds (scalar, vector, surface, parametric
surface, 3D scalar field, 3D vector field) used to carry its own
``snapshot_*`` / ``apply_*`` pair — twelve near-identical ~80-line
functions that walked the modifier's input sockets and bucketed each one
into a nested JSON dict (and back). Adding a single socket (e.g. the
Taylor-surface controls) meant editing four of them in lockstep.

This module factors out the *engine* (socket iteration, JSON-safe
coercion, material-by-name handling, the param-leftover rule, the
applied/skipped report) and keeps only the *mapping* as data: a per-kind
:class:`Spec` says, for every socket, **where its value lives in the
preset dict** (a path of dict keys) and **whether it is a material**.

The public ``snapshot_*`` / ``apply_*`` functions in :mod:`presets` are
now thin wrappers around :func:`snapshot` / :func:`apply` with the right
spec, so their names, signatures and on-disk JSON shape are unchanged —
existing user presets keep loading byte-for-byte the same.

A socket route is ``(path_tuple, is_material)``:
  * ``path_tuple`` — keys to walk/create in the nested dict, e.g.
    ``("range", "x_min")`` or ``("pieces", "f", "thickness")``;
  * ``is_material`` — True stores/reads the datablock *name* and does the
    ``bpy.data.materials`` lookup on apply.
A socket with no fixed/prefix route that matches a declared free
parameter routes to ``("params", <name>)``; anything else is dropped on
snapshot and counts as skipped on apply (matching the old behaviour).
"""

from __future__ import annotations

import copy
import datetime

import bpy

from . import modifier_inputs


# --------------------------------------------------------------------------- #
# Value <-> socket helpers (shared, previously duplicated per kind)
# --------------------------------------------------------------------------- #
def _coerce(value):
    """JSON-safe coercion: bool stays bool, numerics become float,
    everything else best-effort list/str. Identical to the inline
    coercion the old snapshot functions used."""
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return list(value)
    except TypeError:
        return str(value)


def _mat_name(value):
    """Datablock name of a Material socket value, '' when unset."""
    return getattr(value, "name", "") or "" if value is not None else ""


def _set_path(d: dict, path, value):
    """Assign ``value`` at the nested ``path``, creating intermediate
    dicts (matches the old ``setdefault(piece, {})`` pattern)."""
    for k in path[:-1]:
        d = d.setdefault(k, {})
    d[path[-1]] = value


def _get_path(d: dict, path):
    """Read the value at ``path`` or None if any segment is missing."""
    for k in path[:-1]:
        d = d.get(k, {})
        if not isinstance(d, dict):
            return None
    return d.get(path[-1])


def set_modifier_socket(modifier, item, value) -> bool:
    """Write ``value`` to the modifier socket, coercing to the socket's
    type. Returns True on success. (Moved verbatim from presets.py — JSON
    loses the int/float/bool distinction, so we coerce by socket type.)"""
    try:
        sock_type = getattr(item, "socket_type", "")
        if "Bool" in sock_type:
            value = bool(value)
        elif "Int" in sock_type:
            value = int(value)
        elif "Float" in sock_type:
            value = float(value)
        elif "Vector" in sock_type:
            value = tuple(float(v) for v in value)
    except (TypeError, ValueError):
        return False
    return modifier_inputs.set_value(modifier, item.identifier, value)


# --------------------------------------------------------------------------- #
# Spec
# --------------------------------------------------------------------------- #
class Spec:
    """Declarative socket→preset-dict mapping for one object kind.

    Parameters
    ----------
    meta : callable(node_group, name) -> dict
        Builds the kind-specific top of the preset (schema, kind, name,
        created, formula). The section buckets are added from ``template``.
    template : dict
        Empty section skeleton (so e.g. the three arrow buckets always
        appear even when a socket is missing), deep-copied per snapshot.
    fixed : dict[str, (path, is_material)]
        Exact socket-name → route.
    prefix : list[(str, callable(suffix) -> (path, is_material) | None)]
        Dynamic sockets (only the scalar curve needs this: ``Thickness · f``
        …). The callable receives the part after the prefix.
    """

    __slots__ = ("meta", "template", "fixed", "prefix")

    def __init__(self, *, meta, template, fixed, prefix=()):
        self.meta = meta
        self.template = template
        self.fixed = fixed
        self.prefix = tuple(prefix)

    def route(self, name, params):
        """Return ``(path, is_material)`` for a socket, or None to drop."""
        r = self.fixed.get(name)
        if r is not None:
            return r
        for prefix, fn in self.prefix:
            if name.startswith(prefix):
                return fn(name[len(prefix):])
        if name in params:
            return (("params", name), False)
        return None


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
def snapshot(modifier, name: str, spec: Spec) -> dict:
    """Build a preset dict from a live modifier using ``spec``."""
    nt = modifier.node_group
    params = list(nt.get("realfn_params", []))
    out = spec.meta(nt, name)
    for key, skeleton in spec.template.items():
        out.setdefault(key, copy.deepcopy(skeleton))

    for item in nt.interface.items_tree:
        if getattr(item, "in_out", None) != "INPUT":
            continue
        value = modifier_inputs.get_value(
            modifier, item.identifier,
            getattr(item, "default_value", None))
        route = spec.route(item.name, params)
        if route is None:
            continue
        path, is_material = route
        _set_path(out, path, _mat_name(value) if is_material
                  else _coerce(value))
    return out


def apply(preset: dict, modifier, spec: Spec) -> dict:
    """Restore ``preset`` values into ``modifier`` using ``spec``.

    Returns ``{"applied": N, "skipped": M}``. The node group is assumed to
    already match the preset's formula structure (the operator rebuilds
    it first when the formula differs)."""
    nt = modifier.node_group
    params = list(nt.get("realfn_params", []))
    n_applied = 0
    n_skipped = 0

    for item in nt.interface.items_tree:
        if getattr(item, "in_out", None) != "INPUT":
            continue
        route = spec.route(item.name, params)
        if route is None:
            n_skipped += 1
            continue
        path, is_material = route

        if is_material:
            mat_name = _get_path(preset, path)
            if not mat_name:
                n_skipped += 1
                continue
            try:
                mat = bpy.data.materials.get(mat_name)
            except Exception:
                mat = None
            if mat is None:
                n_skipped += 1
                continue
            if modifier_inputs.set_value(modifier, item.identifier, mat):
                n_applied += 1
            else:
                n_skipped += 1
            continue

        value = _get_path(preset, path)
        if value is None:
            n_skipped += 1
            continue
        if set_modifier_socket(modifier, item, value):
            n_applied += 1
        else:
            n_skipped += 1

    return {"applied": n_applied, "skipped": n_skipped}


# --------------------------------------------------------------------------- #
# Per-kind metadata builders (the kind-specific top of the preset dict)
# --------------------------------------------------------------------------- #
def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _meta_scalar(nt, name):
    # NB: the scalar schema (the original) carries no "kind" key.
    return {
        "schema": 1,
        "name": name,
        "created": _now(),
        "formula": {
            "expr": str(nt.get("realfn_expr", "0")),
            "allowed_params": list(nt.get("realfn_params", [])),
            "derivative_order": int(nt.get("realfn_derivative_order", 0)),
            "taylor_order": int(nt.get("realfn_taylor_order", 0)),
        },
    }


def _meta_vector(nt, name):
    return {
        "schema": 1,
        "kind": "vector",
        "name": name,
        "created": _now(),
        "formula": {
            "expr": str(nt.get("realfn_expr", "0*N.x + 0*N.y + 0*N.z")),
            "var_name": str(nt.get("realfn_var", "t")),
            "allowed_params": list(nt.get("realfn_params", [])),
        },
    }


def _meta_surface(nt, name):
    return {
        "schema": 1,
        "kind": "surface",
        "name": name,
        "created": _now(),
        "formula": {
            "expr": str(nt.get("realfn_expr", "0")),
            "x_name": str(nt.get("realfn_var_x", "x")),
            "y_name": str(nt.get("realfn_var_y", "y")),
            "allowed_params": list(nt.get("realfn_params", [])),
        },
    }


def _meta_parametric(nt, name):
    comps = list(nt.get("realfn_components_text") or ["0", "0", "0"])
    return {
        "schema": 1,
        "kind": "parametric_surface",
        "name": name,
        "created": _now(),
        "formula": {
            "components": [str(c) for c in comps],
            "u_name": str(nt.get("realfn_var_u", "u")),
            "v_name": str(nt.get("realfn_var_v", "v")),
            "allowed_params": list(nt.get("realfn_params", [])),
        },
    }


def _meta_scalar_field_3d(nt, name):
    return {
        "schema": 1,
        "kind": "scalar_field_3d",
        "name": name,
        "created": _now(),
        "formula": {
            "expr": str(nt.get("realfn_expr", "0")),
            "x_name": str(nt.get("realfn_var_x", "x")),
            "y_name": str(nt.get("realfn_var_y", "y")),
            "z_name": str(nt.get("realfn_var_z", "z")),
            "allowed_params": list(nt.get("realfn_params", [])),
        },
    }


def _meta_vector_field_3d(nt, name):
    comps = list(nt.get("realfn_components_source") or ["0", "0", "0"])
    return {
        "schema": 1,
        "kind": "vector_field_3d",
        "name": name,
        "created": _now(),
        "formula": {
            "mode": str(nt.get("realfn_mode", "explicit")),
            "components": comps,
            "potential": nt.get("realfn_potential") or "",
            "x_name": str(nt.get("realfn_var_x", "x")),
            "y_name": str(nt.get("realfn_var_y", "y")),
            "z_name": str(nt.get("realfn_var_z", "z")),
            "allowed_params": list(nt.get("realfn_params", [])),
        },
    }


def _meta_vector_bench(nt, name):
    names = list(nt.get("realfn_bench_names") or [])
    exprs = list(nt.get("realfn_bench_exprs") or [])
    return {
        "schema": 1,
        "kind": "vector_bench",
        "name": name,
        "created": _now(),
        "formula": {
            "rows": [[str(n), str(e)] for n, e in zip(names, exprs)],
            "allowed_params": list(nt.get("realfn_params", [])),
        },
    }


# --------------------------------------------------------------------------- #
# Per-kind specs
# --------------------------------------------------------------------------- #
_F = False
_M = True


def _scalar_piece(field, is_mat=False):
    return lambda piece: (("pieces", piece, field), is_mat)


SCALAR = Spec(
    meta=_meta_scalar,
    template={"range": {}, "params": {}, "pieces": {}, "materials": {}},
    fixed={
        "Resolution": (("range", "resolution"), _F),
        "Marker size": (("range", "marker_size"), _F),
        "x min": (("range", "x_min"), _F),
        "x max": (("range", "x_max"), _F),
        "x_0": (("range", "x_0"), _F),
        "Marker material": (("materials", "__marker__"), _M),
    },
    prefix=[
        ("Thickness · ", _scalar_piece("thickness")),
        ("Visible · ", _scalar_piece("visible")),
        ("Material · ", _scalar_piece("material_name", is_mat=True)),
    ],
)


VECTOR = Spec(
    meta=_meta_vector,
    template={"range": {}, "params": {}, "trace": {},
              "arrows": {"position": {}, "vitesse": {}, "accélération": {}},
              "marker": {}},
    fixed={
        "Resolution": (("range", "resolution"), _F),
        "Marker size": (("marker", "size"), _F),
        "t min": (("range", "t_min"), _F),
        "t max": (("range", "t_max"), _F),
        "t_0": (("range", "t_0"), _F),
        "Trace thickness": (("trace", "thickness"), _F),
        "Show position vector": (("arrows", "position", "visible"), _F),
        "Show derivative vector": (("arrows", "vitesse", "visible"), _F),
        "Show acceleration vector": (("arrows", "accélération", "visible"), _F),
        "Marker material": (("marker", "material_name"), _M),
        "Material · trace": (("trace", "material_name"), _M),
        "Material · position": (("arrows", "position", "material_name"), _M),
        "Material · vitesse": (("arrows", "vitesse", "material_name"), _M),
        "Material · accélération":
            (("arrows", "accélération", "material_name"), _M),
    },
)


# Tangent-plane + Taylor-surface socket routes are shared by the two
# surface kinds; only the domain sockets (x/y vs u/v) differ.
_SURFACE_COMMON = {
    "Marker size": (("marker", "size"), _F),
    "Show tangent plane": (("tangent", "visible"), _F),
    "Tangent plane size": (("tangent", "size"), _F),
    "Tangent plane resolution": (("tangent", "resolution"), _F),
    "Show Taylor surface": (("taylor", "visible"), _F),
    "Taylor order": (("taylor", "order"), _F),
    "Taylor surface size": (("taylor", "size"), _F),
    "Taylor surface resolution": (("taylor", "resolution"), _F),
    "Surface material": (("surface", "material_name"), _M),
    "Marker material": (("marker", "material_name"), _M),
    "Tangent plane material": (("tangent", "material_name"), _M),
    "Taylor surface material": (("taylor", "material_name"), _M),
}

SURFACE = Spec(
    meta=_meta_surface,
    template={"range": {}, "params": {}, "surface": {}, "marker": {},
              "tangent": {}, "taylor": {}},
    fixed={
        "Resolution X": (("range", "resolution_x"), _F),
        "Resolution Y": (("range", "resolution_y"), _F),
        "x min": (("range", "x_min"), _F),
        "x max": (("range", "x_max"), _F),
        "y min": (("range", "y_min"), _F),
        "y max": (("range", "y_max"), _F),
        "x_0": (("range", "x_0"), _F),
        "y_0": (("range", "y_0"), _F),
        **_SURFACE_COMMON,
    },
)

PARAMETRIC_SURFACE = Spec(
    meta=_meta_parametric,
    template={"range": {}, "params": {}, "surface": {}, "marker": {},
              "tangent": {}, "taylor": {}},
    fixed={
        "Resolution U": (("range", "resolution_u"), _F),
        "Resolution V": (("range", "resolution_v"), _F),
        "u min": (("range", "u_min"), _F),
        "u max": (("range", "u_max"), _F),
        "v min": (("range", "v_min"), _F),
        "v max": (("range", "v_max"), _F),
        "u_0": (("range", "u_0"), _F),
        "v_0": (("range", "v_0"), _F),
        **_SURFACE_COMMON,
    },
)


# 3D box sockets shared by both field kinds.
_BOX_3D = {
    "Resolution X": (("range", "resolution_x"), _F),
    "Resolution Y": (("range", "resolution_y"), _F),
    "Resolution Z": (("range", "resolution_z"), _F),
    "x min": (("range", "x_min"), _F),
    "x max": (("range", "x_max"), _F),
    "y min": (("range", "y_min"), _F),
    "y max": (("range", "y_max"), _F),
    "z min": (("range", "z_min"), _F),
    "z max": (("range", "z_max"), _F),
    "x_0": (("range", "x_0"), _F),
    "y_0": (("range", "y_0"), _F),
    "z_0": (("range", "z_0"), _F),
}

SCALAR_FIELD_3D = Spec(
    meta=_meta_scalar_field_3d,
    template={"range": {}, "params": {}, "markers": {}, "labels": {},
              "basepoint": {}, "frame": {}, "axes": {}},
    fixed={
        **_BOX_3D,
        "f min": (("range", "f_min"), _F),
        "f max": (("range", "f_max"), _F),
        "Marker size": (("markers", "size"), _F),
        "Show value labels": (("labels", "visible"), _F),
        "Label stride": (("labels", "stride"), _F),
        "Label size": (("labels", "size"), _F),
        "Label offset": (("labels", "offset"), _F),
        "Label decimals": (("labels", "decimals"), _F),
        "Label vertical": (("labels", "vertical"), _F),
        "Label max points": (("labels", "max_points"), _F),
        "Show domain frame": (("frame", "visible"), _F),
        "Frame thickness": (("frame", "thickness"), _F),
        "Show graduated axes": (("axes", "visible"), _F),
        "Axis label size": (("axes", "size"), _F),
        "Axis label decimals": (("axes", "decimals"), _F),
        "Show basepoint": (("basepoint", "visible"), _F),
        "Basepoint marker size": (("basepoint", "marker_size"), _F),
        "Basepoint label size": (("basepoint", "label_size"), _F),
        "Basepoint label offset": (("basepoint", "label_offset"), _F),
        "Marker material": (("markers", "material_name"), _M),
        "Label material": (("labels", "material_name"), _M),
        "Basepoint marker material":
            (("basepoint", "marker_material_name"), _M),
        "Basepoint label material":
            (("basepoint", "label_material_name"), _M),
        "Frame material": (("frame", "material_name"), _M),
        "Axis label material": (("axes", "material_name"), _M),
    },
)

VECTOR_FIELD_3D = Spec(
    meta=_meta_vector_field_3d,
    template={"range": {}, "params": {}, "arrow": {}, "marker": {},
              "base_arrow": {}, "component_arrow": {}, "label": {},
              "norm_labels": {}, "frame": {}, "axes": {}},
    fixed={
        **_BOX_3D,
        "Arrow scale": (("arrow", "scale"), _F),
        "Show arrows": (("arrow", "visible"), _F),
        "Marker size": (("marker", "size"), _F),
        "Show component arrows": (("component_arrow", "visible"), _F),
        "Show basepoint norm label": (("label", "visible"), _F),
        "Label size": (("label", "size"), _F),
        "Label vertical offset": (("label", "offset"), _F),
        "Show norm labels": (("norm_labels", "visible"), _F),
        "Norm label stride": (("norm_labels", "stride"), _F),
        "Norm label size": (("norm_labels", "size"), _F),
        "Norm label offset": (("norm_labels", "offset"), _F),
        "Norm label decimals": (("norm_labels", "decimals"), _F),
        "Norm label vertical": (("norm_labels", "vertical"), _F),
        "Norm label max points": (("norm_labels", "max_points"), _F),
        "Show domain frame": (("frame", "visible"), _F),
        "Frame thickness": (("frame", "thickness"), _F),
        "Show graduated axes": (("axes", "visible"), _F),
        "Axis label size": (("axes", "size"), _F),
        "Axis label decimals": (("axes", "decimals"), _F),
        "Arrow material": (("arrow", "material_name"), _M),
        "Marker material": (("marker", "material_name"), _M),
        "Basepoint arrow material": (("base_arrow", "material_name"), _M),
        "Component arrow material":
            (("component_arrow", "material_name"), _M),
        "Label material": (("label", "material_name"), _M),
        "Norm label material": (("norm_labels", "material_name"), _M),
        "Frame material": (("frame", "material_name"), _M),
        "Axis label material": (("axes", "material_name"), _M),
    },
)


# Vector bench: a variable number of named arrow rows. The structural
# definition (row names + expressions) lives in the meta's ``formula.rows``;
# here we only route the per-row *socket* values — a show toggle and a
# material per row, plus the shared scalar parameters (handled by the
# default ``name in params`` rule).
def _bench_slot(field, is_mat=False):
    return lambda suffix: (("slots", suffix, field), is_mat)


VECTOR_BENCH = Spec(
    meta=_meta_vector_bench,
    template={"slots": {}, "params": {}},
    fixed={},
    prefix=[
        ("Afficher ", _bench_slot("visible")),
        ("Matériau · ", _bench_slot("material_name", is_mat=True)),
    ],
)
