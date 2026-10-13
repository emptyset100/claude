"""
Geometry-Nodes tree builder for parametric surfaces
(x(u, v), y(u, v), z(u, v)).

The visualisation
-----------------
Each vertex of a (u, v) grid in parameter space gets mapped to its 3D
position F(u, v) = (x(u,v), y(u,v), z(u,v)). On top of this surface we
draw:

* a sphere marker at F(u₀, v₀) — the basepoint;
* a small affine plane spanned by the two partial derivatives
  ∂F/∂u(u₀,v₀) and ∂F/∂v(u₀,v₀), anchored at the basepoint — the
  *tangent plane* at the contact point.

Tangent plane for a parametric surface
--------------------------------------
At F(u₀, v₀), the surface is best linearly approximated by the affine
plane

    P(s, t) = F(u₀, v₀)  +  s · ∂F/∂u(u₀, v₀)  +  t · ∂F/∂v(u₀, v₀)

with (s, t) ranging over a small square centred at (0, 0). Unlike the
explicit case z=f(x,y), the two tangent vectors here are *not*
constrained to point along the world XY axes — they live in the surface
and tilt freely in 3D. The tangent plane we render is therefore a
genuine 3D quad, not a flat grid in XY.

Implementation note
-------------------
Building a 2D grid in (u, v) parameter space is the same MeshGrid trick
as in :mod:`surface_tree`, but the Position override is different:
instead of lifting z by f(x, y), we *fully replace* x, y, z by the
three component expressions. The compiler.SymPyCompiler memo-share
between the three components is what makes this affordable (any
shared subterm — say ``sin(u)`` showing up in two components — only
compiles once).
"""

from __future__ import annotations

import bpy
import sympy as sp

from .compiler import NodeBuilder, SymPyCompiler, compile_vector_components
from . import sympy_parser


PARAMETRIC_SURFACE_TREE_PREFIX = "REALFNPSURF_"

# Highest Taylor-surface order pre-built into the tree (matches the
# explicit-surface builder). The runtime "Taylor order" socket masks the
# unused high-degree terms to zero, so the order scrubs live: 0 → the
# point F(u₀,v₀), 1 → tangent plane, 2 → osculating (paraboloid-like)
# patch, … For a parametric surface the expansion is done component-wise
# on each of x(u,v), y(u,v), z(u,v).
TAYLOR_SURFACE_MAX_ORDER = 8


def parametric_taylor_terms(components, *, u_name, v_name):
    """Component-wise homogeneous Taylor terms of F=(x,y,z) about (u₀,v₀).

    Returns a list ``[T_0, T_1, …, T_N]`` (N = :data:`TAYLOR_SURFACE_MAX_ORDER`)
    where each ``T_k`` is a 3-tuple ``(Dx_k, Dy_k, Dz_k)`` and

        Dc_k(u, v) = Σ_{i+j=k} ∂^k c/∂uⁱ∂vʲ (u₀,v₀) / (i! j!)
                              · (u − u₀)ⁱ (v − v₀)ʲ

    for component ``c``. The order-n Taylor surface is then
    ``Σ_{k=0}^{n} T_k`` summed component-wise — order 1 reproduces the
    affine tangent plane F(u₀,v₀)+ (u−u₀)F_u + (v−v₀)F_v, order 2 adds the
    second fundamental form, etc. Basepoint symbols ``u_0``/``v_0`` stay
    free (driven by the modifier sliders); ``u``/``v`` stay free for the
    per-vertex grid coordinates.
    """
    sp_ = sympy_parser._sympy()
    u_sym = sp_.Symbol(u_name, real=True)
    v_sym = sp_.Symbol(v_name, real=True)
    u0_sym = sp_.Symbol("u_0", real=True)
    v0_sym = sp_.Symbol("v_0", real=True)
    at_basepoint = {u_sym: u0_sym, v_sym: v0_sym}

    terms = []
    for k in range(TAYLOR_SURFACE_MAX_ORDER + 1):
        triple = []
        for c in components:
            dk = sp_.S.Zero
            for i in range(k + 1):
                j = k - i
                coeff = sp_.diff(c, (u_sym, i), (v_sym, j)).subs(at_basepoint)
                dk += (coeff
                       * (u_sym - u0_sym) ** i
                       * (v_sym - v0_sym) ** j
                       / (sp_.factorial(i) * sp_.factorial(j)))
            # Factored form (no expand) — the compiler memo-shares the
            # (u-u₀)ⁱ powers and basepoint coefficients across the three
            # components and across degrees, keeping the node count (and
            # both build and eval time) tractable even at order 8.
            triple.append(dk)
        terms.append(tuple(triple))
    return terms


def _build_param_taylor_surface(nb: NodeBuilder, *,
                                  u0_sock, v0_sock, order_sock,
                                  size_sock, resolution_sock,
                                  taylor_terms, free_param_sockets,
                                  u_name="u", v_name="v",
                                  label="taylor surface", y_offset=-2600):
    """Build the order-n osculating Taylor surface of F at (u₀, v₀).

    Same grid-in-parameter-space skeleton as the surface mesh, but every
    vertex is placed at the component-wise Taylor sum

        F_n(u,v) = ( Σ_k [order≥k]·Dx_k ,
                     Σ_k [order≥k]·Dy_k ,
                     Σ_k [order≥k]·Dz_k )

    with the ``[order≥k]`` mask shared across the three components, so the
    order slider scrubs the polynomial degree live. Returns a Geometry
    socket carrying the meshed surface.
    """
    grid = nb.add("GeometryNodeMeshGrid",
                   label=f"{label}: (u,v) grid", x=-1600, y=y_offset)
    nb.link(size_sock, grid.inputs["Size X"])
    nb.link(size_sock, grid.inputs["Size Y"])
    nb.link(resolution_sock, grid.inputs["Vertices X"])
    nb.link(resolution_sock, grid.inputs["Vertices Y"])

    # Centre the (u,v) patch on (u₀, v₀).
    center = nb.combine_xyz(u0_sock, v0_sock, 0.0,
                             label="basepoint UV", x=-1400, y=y_offset - 100)
    translate = nb.add("GeometryNodeTransform",
                        label=f"{label}: center", x=-1200, y=y_offset)
    nb.link(grid.outputs["Mesh"], translate.inputs["Geometry"])
    nb.link(center, translate.inputs["Translation"])

    pos = nb.add("GeometryNodeInputPosition",
                  label=f"{label}: (u,v)", x=-1000, y=y_offset - 200)
    sep = nb.add("ShaderNodeSeparateXYZ",
                  label="separate", x=-800, y=y_offset - 200)
    nb.link(pos.outputs["Position"], sep.inputs["Vector"])
    u_sock = sep.outputs["X"]
    v_sock = sep.outputs["Y"]

    var_sockets = {u_name: u_sock, v_name: v_sock,
                   "u_0": u0_sock, "v_0": v0_sock, **free_param_sockets}
    comp = SymPyCompiler(nb, var_sockets)

    acc = [None, None, None]  # x, y, z accumulators
    for k, triple in enumerate(taylor_terms):
        row_y = y_offset - 300 - 70 * k
        # One mask per degree, reused across the three components.
        mask = nb.math("GREATER_THAN", order_sock, k - 0.5,
                        label=f"order ≥ {k}", x=-560, y=row_y)
        for ci in range(3):
            zk = comp.compile(triple[ci])
            masked = nb.math("MULTIPLY", zk, mask,
                              label=f"D_{k}[{'xyz'[ci]}]",
                              x=-360, y=row_y - 20 * ci)
            if acc[ci] is None:
                acc[ci] = masked
            else:
                acc[ci] = nb.math("ADD", acc[ci], masked,
                                   label=f"Σ{'xyz'[ci]} ≤ {k}",
                                   x=-160, y=row_y - 20 * ci)

    new_pos = nb.combine_xyz(acc[0], acc[1], acc[2],
                              label="taylor F_n(u,v)", x=240, y=y_offset)
    set_pos = nb.add("GeometryNodeSetPosition",
                      label=f"{label}: place", x=440, y=y_offset)
    nb.link(translate.outputs["Geometry"], set_pos.inputs["Geometry"])
    nb.link(new_pos, set_pos.inputs["Position"])
    return set_pos.outputs["Geometry"]


def _build_parametric_surface_mesh(nb: NodeBuilder, *,
                                     u_min_sock, u_max_sock,
                                     v_min_sock, v_max_sock,
                                     res_u_sock, res_v_sock,
                                     components, free_param_sockets,
                                     u_name="u", v_name="v",
                                     label="psurface", y_offset=0):
    """Build a parametric surface mesh F(u, v) over [u_min, u_max] ×
    [v_min, v_max].

    Returns a Geometry socket carrying the mesh. ``components`` is the
    triplet (x(u,v), y(u,v), z(u,v)) of SymPy expressions, typically
    returned by :func:`sympy_parser.parse_parametric_surface_components`.
    """
    grid = nb.add("GeometryNodeMeshGrid",
                   label=f"{label}: (u,v) grid", x=-1600, y=y_offset)
    span_u = nb.math("SUBTRACT", u_max_sock, u_min_sock,
                      label="u_max - u_min", x=-1400, y=y_offset + 200)
    span_v = nb.math("SUBTRACT", v_max_sock, v_min_sock,
                      label="v_max - v_min", x=-1400, y=y_offset + 100)
    nb.link(span_u, grid.inputs["Size X"])
    nb.link(span_v, grid.inputs["Size Y"])
    nb.link(res_u_sock, grid.inputs["Vertices X"])
    nb.link(res_v_sock, grid.inputs["Vertices Y"])

    # Translate to centre at ((u_min+u_max)/2, (v_min+v_max)/2, 0).
    cu = nb.math("ADD", u_min_sock, u_max_sock,
                  label="u_min + u_max", x=-1400, y=y_offset - 50)
    cu_half = nb.math("DIVIDE", cu, 2.0,
                       label="(u_min+u_max)/2", x=-1200, y=y_offset - 50)
    cv = nb.math("ADD", v_min_sock, v_max_sock,
                  label="v_min + v_max", x=-1400, y=y_offset - 150)
    cv_half = nb.math("DIVIDE", cv, 2.0,
                       label="(v_min+v_max)/2", x=-1200, y=y_offset - 150)
    center = nb.combine_xyz(cu_half, cv_half, 0.0,
                             label="grid center", x=-1000, y=y_offset - 100)
    translate = nb.add("GeometryNodeTransform",
                        label=f"{label}: center", x=-800, y=y_offset)
    nb.link(grid.outputs["Mesh"], translate.inputs["Geometry"])
    nb.link(center, translate.inputs["Translation"])

    # Read (u, v) from the vertex position (after translation).
    pos = nb.add("GeometryNodeInputPosition",
                  label=f"{label}: (u,v)", x=-600, y=y_offset - 250)
    sep = nb.add("ShaderNodeSeparateXYZ",
                  label="separate", x=-400, y=y_offset - 250)
    nb.link(pos.outputs["Position"], sep.inputs["Vector"])
    u_sock = sep.outputs["X"]
    v_sock = sep.outputs["Y"]

    # Compile F(u, v) → Vector socket.
    var_sockets = {u_name: u_sock, v_name: v_sock, **free_param_sockets}
    F_sock = compile_vector_components(
        nb, components, var_sockets,
        x=400, y=y_offset, label=f"{label}: F(u,v)",
    )

    set_pos = nb.add("GeometryNodeSetPosition",
                      label=f"{label}: place F(u,v)",
                      x=600, y=y_offset)
    nb.link(translate.outputs["Geometry"], set_pos.inputs["Geometry"])
    nb.link(F_sock, set_pos.inputs["Position"])
    return set_pos.outputs["Geometry"]


def _build_param_tangent_plane(nb: NodeBuilder, *,
                                 F0_sock, dFdu0_sock, dFdv0_sock,
                                 tan_size_sock, tan_resolution_sock,
                                 label="tangent plane", y_offset=-1300):
    """Build the affine tangent plane at F(u₀, v₀) of a parametric surface.

    The plane is parametrised as
        P(s, t) = F(u₀,v₀) + s·∂F/∂u(u₀,v₀) + t·∂F/∂v(u₀,v₀)
    with (s, t) ∈ [-tan_size/2, +tan_size/2]². We build it as a small
    grid in (s, t) parameter space and replace each vertex by the
    affine combination above.
    """
    grid = nb.add("GeometryNodeMeshGrid",
                   label=f"{label}: (s,t) grid", x=-1600, y=y_offset)
    nb.link(tan_size_sock, grid.inputs["Size X"])
    nb.link(tan_size_sock, grid.inputs["Size Y"])
    nb.link(tan_resolution_sock, grid.inputs["Vertices X"])
    nb.link(tan_resolution_sock, grid.inputs["Vertices Y"])

    # Read (s, t) from the vertex position (grid is centred at origin
    # already, no need to translate before reading).
    pos = nb.add("GeometryNodeInputPosition",
                  label=f"{label}: (s,t)", x=-1400, y=y_offset - 200)
    sep = nb.add("ShaderNodeSeparateXYZ",
                  label="separate (s,t)", x=-1200, y=y_offset - 200)
    nb.link(pos.outputs["Position"], sep.inputs["Vector"])
    s_sock = sep.outputs["X"]
    t_sock = sep.outputs["Y"]

    # Compute P = F0 + s · dFdu0 + t · dFdv0 (vector arithmetic).
    s_du = nb.add("ShaderNodeVectorMath",
                   label="s · ∂F/∂u", x=-900, y=y_offset)
    s_du.operation = "SCALE"
    nb.link(dFdu0_sock, s_du.inputs[0])
    nb.link(s_sock, s_du.inputs["Scale"])
    t_dv = nb.add("ShaderNodeVectorMath",
                   label="t · ∂F/∂v", x=-900, y=y_offset - 200)
    t_dv.operation = "SCALE"
    nb.link(dFdv0_sock, t_dv.inputs[0])
    nb.link(t_sock, t_dv.inputs["Scale"])
    sum1 = nb.add("ShaderNodeVectorMath",
                   label="s·∂F/∂u + t·∂F/∂v",
                   x=-600, y=y_offset - 100)
    sum1.operation = "ADD"
    nb.link(s_du.outputs[0], sum1.inputs[0])
    nb.link(t_dv.outputs[0], sum1.inputs[1])
    plane_pos = nb.add("ShaderNodeVectorMath",
                        label="F_0 + s·∂F/∂u + t·∂F/∂v",
                        x=-400, y=y_offset)
    plane_pos.operation = "ADD"
    nb.link(F0_sock, plane_pos.inputs[0])
    nb.link(sum1.outputs[0], plane_pos.inputs[1])

    set_pos = nb.add("GeometryNodeSetPosition",
                      label=f"{label}: lift", x=-100, y=y_offset)
    nb.link(grid.outputs["Mesh"], set_pos.inputs["Geometry"])
    nb.link(plane_pos.outputs[0], set_pos.inputs["Position"])
    return set_pos.outputs["Geometry"]


def make_parametric_surface_tree(components_source,
                                   *,
                                   u_name: str = "u", v_name: str = "v",
                                   allowed_params: tuple[str, ...] = (),
                                   u_default_range: tuple[float, float] = (0.0, 6.283),
                                   v_default_range: tuple[float, float] = (0.0, 3.142),
                                   u0_default: float = 1.0,
                                   v0_default: float = 1.0,
                                   key_suffix: str = ""):
    """Build a Geometry-Nodes tree for a parametric surface.

    ``components_source`` is the triplet of strings
    ``(x_expr, y_expr, z_expr)`` — three independent scalar expressions
    in (u, v).

    See module docstring for the full feature list.

    Returns
    -------
    bpy.types.NodeTree
    """
    sp_ = sympy_parser._sympy()

    # ----- Parse + differentiate ----------------------------------------
    components = sympy_parser.parse_parametric_surface_components(
        components_source, u_name=u_name, v_name=v_name,
    )
    d_u, d_v = sympy_parser.parametric_surface_partial_derivatives(
        components, u_name=u_name, v_name=v_name,
    )
    u_sym = sp_.Symbol(u_name, real=True)
    v_sym = sp_.Symbol(v_name, real=True)
    u0_sym = sp_.Symbol("u_0", real=True)
    v0_sym = sp_.Symbol("v_0", real=True)
    subs = {u_sym: u0_sym, v_sym: v0_sym}
    F0_components = tuple(c.subs(subs) for c in components)
    dFdu0_components = tuple(c.subs(subs) for c in d_u)
    dFdv0_components = tuple(c.subs(subs) for c in d_v)

    # Component-wise Taylor terms about (u₀, v₀) for the scrubbable
    # osculating-surface feature (order 1 == the tangent plane above).
    taylor_terms = parametric_taylor_terms(
        components, u_name=u_name, v_name=v_name,
    )

    # Validate free symbols.
    all_free = set()
    for e in (components + d_u + d_v + F0_components
              + dFdu0_components + dFdv0_components):
        all_free |= e.free_symbols
    for _triple in taylor_terms:
        for _dk in _triple:
            all_free |= _dk.free_symbols
    known = {u_name, v_name, "u_0", "v_0"} | set(allowed_params)
    unknown = sorted(s.name for s in all_free if s.name not in known)
    if unknown:
        raise ValueError(
            f"Symboles non autorisés : {', '.join(unknown)}. "
            f"Autorisés : {sorted(known)}"
        )

    # ----- Tree + interface ---------------------------------------------
    nt = bpy.data.node_groups.new(
        f"{PARAMETRIC_SURFACE_TREE_PREFIX}{key_suffix or 'fn'}",
        "GeometryNodeTree",
    )
    nt.interface.new_socket(
        "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry",
    )

    def add_int(name, default, mn=2, mx=10000, desc=""):
        s = nt.interface.new_socket(name, in_out="INPUT",
                                     socket_type="NodeSocketInt")
        s.default_value = default
        s.min_value = mn; s.max_value = mx
        if desc: s.description = desc
        return s

    def add_float(name, default, mn=None, mx=None, desc=""):
        s = nt.interface.new_socket(name, in_out="INPUT",
                                     socket_type="NodeSocketFloat")
        s.default_value = default
        if mn is not None: s.min_value = mn
        if mx is not None: s.max_value = mx
        if desc: s.description = desc
        return s

    def add_bool(name, default, desc=""):
        s = nt.interface.new_socket(name, in_out="INPUT",
                                     socket_type="NodeSocketBool")
        s.default_value = default
        if desc: s.description = desc
        return s

    def add_mat(name, desc=""):
        s = nt.interface.new_socket(name, in_out="INPUT",
                                     socket_type="NodeSocketMaterial")
        if desc: s.description = desc
        return s

    add_int("Resolution U", 64,
             desc="Subdivisions en u de la surface paramétrée")
    add_int("Resolution V", 64,
             desc="Subdivisions en v de la surface paramétrée")
    add_float("u min", float(u_default_range[0]))
    add_float("u max", float(u_default_range[1]))
    add_float("v min", float(v_default_range[0]))
    add_float("v max", float(v_default_range[1]))
    add_float("u_0", float(u0_default),
               desc="Coordonnée u du point d'ancrage F(u₀, v₀)")
    add_float("v_0", float(v0_default),
               desc="Coordonnée v du point d'ancrage F(u₀, v₀)")
    add_mat("Surface material",
             desc="Matériau de la surface paramétrée")
    add_float("Marker size", 0.10, mn=0.0,
               desc="Rayon de la sphère marqueur en F(u₀, v₀)")
    add_mat("Marker material")
    add_bool("Show tangent plane", True,
              desc="Affiche le plan tangent affine engendré par "
                   "∂F/∂u et ∂F/∂v en F(u₀, v₀)")
    add_float("Tangent plane size", 1.0, mn=0.0,
               desc="Côté du carré (s, t) qui paramétrise le plan tangent")
    add_int("Tangent plane resolution", 8, mn=2, mx=64)
    add_mat("Tangent plane material")
    add_bool("Show Taylor surface", False,
              desc="Affiche la surface de Taylor osculatrice en F(u₀,v₀). "
                   "Montez « Ordre de Taylor » pour passer du plan tangent "
                   "au paraboloïde osculateur, etc.")
    add_int("Taylor order", 2, mn=0, mx=TAYLOR_SURFACE_MAX_ORDER,
             desc="Ordre du développement de Taylor (par composante) en "
                  "(u₀, v₀). 1 = plan tangent ; 2 = approximation du second "
                  "ordre. Scrubbez pour voir la nappe épouser F en direct")
    add_float("Taylor surface size", 1.0, mn=0.0,
               desc="Côté du carré (u, v) sur lequel la surface de Taylor "
                    "est échantillonnée, centré sur (u₀, v₀)")
    add_int("Taylor surface resolution", 24, mn=2, mx=200,
             desc="Subdivisions du carré de la surface de Taylor")
    add_mat("Taylor surface material",
             desc="Matériau de la surface de Taylor")
    for p in allowed_params:
        ps = nt.interface.new_socket(p, in_out="INPUT",
                                       socket_type="NodeSocketFloat")
        ps.default_value = 1.0

    # ----- Graph build --------------------------------------------------
    nb = NodeBuilder(nt)
    group_in = nb.add("NodeGroupInput", x=-2000, y=0)
    group_out = nb.add("NodeGroupOutput", x=2400, y=0)

    free_param_sockets = {p: group_in.outputs[p] for p in allowed_params}
    basepoint_extra = dict(free_param_sockets)
    basepoint_extra["u_0"] = group_in.outputs["u_0"]
    basepoint_extra["v_0"] = group_in.outputs["v_0"]

    # 1) Surface mesh.
    surf_geom = _build_parametric_surface_mesh(
        nb,
        u_min_sock=group_in.outputs["u min"],
        u_max_sock=group_in.outputs["u max"],
        v_min_sock=group_in.outputs["v min"],
        v_max_sock=group_in.outputs["v max"],
        res_u_sock=group_in.outputs["Resolution U"],
        res_v_sock=group_in.outputs["Resolution V"],
        components=components,
        free_param_sockets=free_param_sockets,
        u_name=u_name, v_name=v_name, y_offset=0,
    )
    surf_mat = nb.add("GeometryNodeSetMaterial",
                       label="surface: material", x=900, y=0)
    nb.link(surf_geom, surf_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Surface material"],
             surf_mat.inputs["Material"])

    # 2) Marker sphere at F(u₀, v₀). We compile the three component
    # expressions evaluated at (u₀, v₀) — they yield three scalar
    # sockets that we combine via CombineXYZ.
    F0_sock = compile_vector_components(
        nb, F0_components, basepoint_extra,
        x=400, y=-700, label="F(u_0, v_0)",
    )
    sphere = nb.add("GeometryNodeMeshUVSphere",
                     label="marker", x=600, y=-700)
    sphere.inputs["Segments"].default_value = 16
    sphere.inputs["Rings"].default_value = 8
    nb.link(group_in.outputs["Marker size"], sphere.inputs["Radius"])
    place = nb.add("GeometryNodeSetPosition",
                    label="place marker", x=900, y=-700)
    nb.link(sphere.outputs["Mesh"], place.inputs["Geometry"])
    nb.link(F0_sock, place.inputs["Offset"])
    marker_mat = nb.add("GeometryNodeSetMaterial",
                         label="marker: material", x=1200, y=-700)
    nb.link(place.outputs["Geometry"], marker_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Marker material"],
             marker_mat.inputs["Material"])

    # 3) Tangent plane.
    dFdu0_sock = compile_vector_components(
        nb, dFdu0_components, basepoint_extra,
        x=400, y=-1100, label="∂F/∂u(u_0,v_0)",
    )
    dFdv0_sock = compile_vector_components(
        nb, dFdv0_components, basepoint_extra,
        x=400, y=-1400, label="∂F/∂v(u_0,v_0)",
    )
    tan_geom = _build_param_tangent_plane(
        nb,
        F0_sock=F0_sock,
        dFdu0_sock=dFdu0_sock,
        dFdv0_sock=dFdv0_sock,
        tan_size_sock=group_in.outputs["Tangent plane size"],
        tan_resolution_sock=group_in.outputs["Tangent plane resolution"],
        y_offset=-1300,
    )
    tan_mat = nb.add("GeometryNodeSetMaterial",
                      label="tangent: material", x=300, y=-1300)
    nb.link(tan_geom, tan_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Tangent plane material"],
             tan_mat.inputs["Material"])
    tan_switch = nb.add("GeometryNodeSwitch",
                         label="show tangent?",
                         x=1200, y=-1300)
    tan_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show tangent plane"],
                 tan_switch.inputs["Switch"])
        nb.link(tan_mat.outputs["Geometry"],
                 tan_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show tangent plane"],
                 tan_switch.inputs[0])
        nb.link(tan_mat.outputs["Geometry"],
                 tan_switch.inputs[2])
    tan_out = (tan_switch.outputs["Output"]
               if "Output" in tan_switch.outputs
               else tan_switch.outputs[0])

    # 3bis) Taylor surface — scrubbable osculating surface (component-wise).
    taylor_geom = _build_param_taylor_surface(
        nb,
        u0_sock=group_in.outputs["u_0"],
        v0_sock=group_in.outputs["v_0"],
        order_sock=group_in.outputs["Taylor order"],
        size_sock=group_in.outputs["Taylor surface size"],
        resolution_sock=group_in.outputs["Taylor surface resolution"],
        taylor_terms=taylor_terms,
        free_param_sockets=free_param_sockets,
        u_name=u_name, v_name=v_name,
        y_offset=-2600,
    )
    taylor_mat = nb.add("GeometryNodeSetMaterial",
                         label="taylor: material", x=300, y=-2600)
    nb.link(taylor_geom, taylor_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Taylor surface material"],
             taylor_mat.inputs["Material"])
    taylor_switch = nb.add("GeometryNodeSwitch",
                            label="show taylor?", x=1200, y=-2600)
    taylor_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show Taylor surface"],
                 taylor_switch.inputs["Switch"])
        nb.link(taylor_mat.outputs["Geometry"],
                 taylor_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show Taylor surface"],
                 taylor_switch.inputs[0])
        nb.link(taylor_mat.outputs["Geometry"],
                 taylor_switch.inputs[2])
    taylor_out = (taylor_switch.outputs["Output"]
                  if "Output" in taylor_switch.outputs
                  else taylor_switch.outputs[0])

    # 4) Join.
    join = nb.add("GeometryNodeJoinGeometry",
                   label="final", x=1900, y=-400)
    nb.link(surf_mat.outputs["Geometry"], join.inputs["Geometry"])
    nb.link(marker_mat.outputs["Geometry"], join.inputs["Geometry"])
    nb.link(tan_out, join.inputs["Geometry"])
    nb.link(taylor_out, join.inputs["Geometry"])
    nb.link(join.outputs["Geometry"], group_out.inputs[0])

    # ----- Metadata stash -----------------------------------------------
    nt["realfn_kind"] = "parametric_surface"
    # Store each component separately (a list of three) for the panel.
    nt["realfn_components_text"] = [str(sp_.sstr(c)) for c in components]
    nt["realfn_components_latex"] = [str(sp_.latex(c)) for c in components]
    nt["realfn_dFdu_text"] = [str(sp_.sstr(c)) for c in d_u]
    nt["realfn_dFdv_text"] = [str(sp_.sstr(c)) for c in d_v]
    nt["realfn_var_u"] = u_name
    nt["realfn_var_v"] = v_name
    nt["realfn_params"] = list(allowed_params)
    nt["realfn_taylor_surface_max"] = int(TAYLOR_SURFACE_MAX_ORDER)
    # Cumulative component-wise Taylor polynomials T_0 … T_N for the panel
    # (index == order). Stored as three flat per-component string lists —
    # ID properties don't nest cleanly — text + LaTeX each.
    _acc = [sp_.S.Zero, sp_.S.Zero, sp_.S.Zero]
    _cum = ([], [], [])  # x, y, z cumulative-per-order
    for _triple in taylor_terms:
        for _ci in range(3):
            _acc[_ci] = _acc[_ci] + _triple[_ci]
            _cum[_ci].append(_acc[_ci])
    for _ci, _axis in enumerate("xyz"):
        nt[f"realfn_taylor_poly_{_axis}_text"] = [
            str(sp_.sstr(e)) for e in _cum[_ci]]
        nt[f"realfn_taylor_poly_{_axis}_latex"] = [
            str(sp_.latex(e)) for e in _cum[_ci]]
    return nt
