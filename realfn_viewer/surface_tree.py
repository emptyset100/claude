"""
Geometry-Nodes tree builder for explicit surfaces z = f(x, y).

The visualization
-----------------
An explicit surface is rendered as a quadrilateral mesh over a
rectangular domain in the (x, y) plane, with each vertex elevated to
z = f(x, y). On top of this surface we draw:

* a sphere marker at (x₀, y₀, f(x₀, y₀)) — the basepoint;
* a small quad mesh representing the *tangent plane* at the basepoint —
  the affine plane z = f(x₀, y₀) + ∂f/∂x(x₀,y₀)·(x-x₀) + ∂f/∂y(x₀,y₀)·(y-y₀).

The tangent plane is the explicit-surface analog of the tangent line in
1D. It "kisses" the surface at the basepoint and tilts according to the
local gradient — pedagogically the same shape of insight as f'(x₀) on a
1D curve.

Implementation
--------------
The surface mesh comes from ``GeometryNodeMeshGrid`` (Blender 4.x has
this primitive built in) producing an NxN flat grid in XY. We then
override the position of every vertex via ``GeometryNodeSetPosition``
to lift it to f(x, y).

The tangent-plane mesh is a *separate* small grid produced the same
way and elevated to the tangent-plane equation — a degenerate
"surface" that happens to be a flat affine plane.

The two meshes are then joined and emitted through the group output.
"""

from __future__ import annotations

import bpy
import sympy as sp

from .compiler import NodeBuilder, SymPyCompiler, compile_outlined
from . import sympy_parser


# Distinct prefix so the active-modifier helper can tell surface trees
# apart from scalar / vector ones.
SURFACE_TREE_PREFIX = "REALFNSURF_"

# Highest Taylor-surface order we pre-build into the tree. The runtime
# "Taylor order" socket selects how many of these homogeneous terms are
# summed (0 → flat plane at f(x₀,y₀); 1 → tangent plane; 2 → osculating
# paraboloid; …). All terms are always present in the graph; the order
# socket just masks the unused high-degree ones to zero — so the order
# is scrubbable live with no rebuild.
TAYLOR_SURFACE_MAX_ORDER = 8


def _build_surface_mesh(nb: NodeBuilder, *,
                         x_min_sock, x_max_sock,
                         y_min_sock, y_max_sock,
                         res_x_sock, res_y_sock,
                         f_expr, free_param_sockets,
                         x_name="x", y_name="y",
                         label="surface", y_offset=0):
    """Build a meshed graph of ``z = f(x, y)`` over the given domain.

    Returns a Geometry socket carrying the meshed surface, ready to be
    wired downstream (set material, join, …). The mesh has ``res_x ×
    res_y`` vertices arranged in a regular grid spanning the rectangle
    [x_min, x_max] × [y_min, y_max] in the XY plane.

    Why ``MeshGrid`` rather than two nested ``MeshLine`` ?
    ``MeshGrid`` produces a *quad* topology straight away, which is the
    natural representation for an explicit-surface graph — every vertex
    has exactly four neighbours, edge loops run along the iso-x and
    iso-y lines, and downstream geometry-nodes operations (subdivide,
    smooth, etc.) all behave intuitively on it.
    """
    # 1) Flat grid in XY with the requested resolution.
    grid = nb.add(
        "GeometryNodeMeshGrid",
        label=f"{label}: grid", x=-1600, y=y_offset,
    )
    # MeshGrid's Size inputs control side length; we want to control the
    # *domain* (x_min, x_max). So we set Size to (x_max - x_min) and
    # then translate the grid by ((x_min+x_max)/2, (y_min+y_max)/2, 0).
    span_x = nb.math("SUBTRACT", x_max_sock, x_min_sock,
                      label="x_max - x_min", x=-1400, y=y_offset + 200)
    span_y = nb.math("SUBTRACT", y_max_sock, y_min_sock,
                      label="y_max - y_min", x=-1400, y=y_offset + 100)
    nb.link(span_x, grid.inputs["Size X"])
    nb.link(span_y, grid.inputs["Size Y"])
    nb.link(res_x_sock, grid.inputs["Vertices X"])
    nb.link(res_y_sock, grid.inputs["Vertices Y"])

    # Translate the grid so its bbox is [x_min, x_max] × [y_min, y_max].
    cx = nb.math("ADD", x_min_sock, x_max_sock,
                  label="x_min + x_max", x=-1400, y=y_offset - 50)
    cx_half = nb.math("DIVIDE", cx, 2.0,
                       label="(x_min + x_max)/2", x=-1200, y=y_offset - 50)
    cy = nb.math("ADD", y_min_sock, y_max_sock,
                  label="y_min + y_max", x=-1400, y=y_offset - 150)
    cy_half = nb.math("DIVIDE", cy, 2.0,
                       label="(y_min + y_max)/2", x=-1200, y=y_offset - 150)
    center = nb.combine_xyz(cx_half, cy_half, 0.0,
                             label="grid center", x=-1000, y=y_offset - 100)
    translate = nb.add("GeometryNodeTransform",
                        label=f"{label}: center grid",
                        x=-800, y=y_offset)
    nb.link(grid.outputs["Mesh"], translate.inputs["Geometry"])
    nb.link(center, translate.inputs["Translation"])

    # 2) Compile f(x, y) into a scalar socket, with x and y coming from
    # the *current* vertex position.
    # The Position attribute is a Vector socket exposed by
    # ``GeometryNodeInputPosition``. We split it via SeparateXYZ to
    # feed the x and y components into the SymPy compiler.
    pos_in = nb.add("GeometryNodeInputPosition",
                     label=f"{label}: vertex (x,y)", x=-600, y=y_offset - 250)
    sep = nb.add("ShaderNodeSeparateXYZ",
                  label="separate", x=-400, y=y_offset - 250)
    nb.link(pos_in.outputs["Position"], sep.inputs["Vector"])
    x_sock = sep.outputs["X"]
    y_sock = sep.outputs["Y"]

    var_sockets = {x_name: x_sock, y_name: y_sock, **free_param_sockets}
    compiler = SymPyCompiler(nb, var_sockets)
    z_sock = compiler.compile(f_expr)

    # 3) Override Position: take (x, y) from the grid, replace z with f(x, y).
    new_pos = nb.combine_xyz(x_sock, y_sock, z_sock,
                              label=f"{label}: (x, y, f)",
                              x=400, y=y_offset)
    set_pos = nb.add("GeometryNodeSetPosition",
                      label=f"{label}: lift to f(x,y)",
                      x=600, y=y_offset)
    nb.link(translate.outputs["Geometry"], set_pos.inputs["Geometry"])
    nb.link(new_pos, set_pos.inputs["Position"])
    return set_pos.outputs["Geometry"]


def _build_tangent_plane_mesh(nb: NodeBuilder, *,
                                x0_sock, y0_sock,
                                f0_sock, dfdx0_sock, dfdy0_sock,
                                tan_size_sock, tan_resolution_sock,
                                label="tangent plane", y_offset=-1200):
    """Build the affine tangent plane at (x₀, y₀, f(x₀,y₀)).

    The tangent plane equation is
        z = f(x₀, y₀) + ∂f/∂x(x₀,y₀) · (x - x₀)
                       + ∂f/∂y(x₀,y₀) · (y - y₀)
    and we sample it over a square of side ``tan_size`` centred on
    (x₀, y₀). The resulting mesh "rests" against the surface at the
    contact point and tilts according to the gradient.

    Returns a Geometry socket carrying the meshed tangent plane.
    """
    grid = nb.add("GeometryNodeMeshGrid",
                   label=f"{label}: grid", x=-1600, y=y_offset)
    nb.link(tan_size_sock, grid.inputs["Size X"])
    nb.link(tan_size_sock, grid.inputs["Size Y"])
    nb.link(tan_resolution_sock, grid.inputs["Vertices X"])
    nb.link(tan_resolution_sock, grid.inputs["Vertices Y"])

    # Translate the grid to (x₀, y₀, 0).
    center = nb.combine_xyz(x0_sock, y0_sock, 0.0,
                             label="basepoint XY", x=-1400, y=y_offset - 100)
    translate = nb.add("GeometryNodeTransform",
                        label=f"{label}: center", x=-1200, y=y_offset)
    nb.link(grid.outputs["Mesh"], translate.inputs["Geometry"])
    nb.link(center, translate.inputs["Translation"])

    # Compute the tangent-plane z at every vertex:
    #   z_plane = f0 + dfdx0 · (x - x0) + dfdy0 · (y - y0)
    pos = nb.add("GeometryNodeInputPosition",
                  label=f"{label}: vertex", x=-1000, y=y_offset - 200)
    sep = nb.add("ShaderNodeSeparateXYZ",
                  label="separate", x=-800, y=y_offset - 200)
    nb.link(pos.outputs["Position"], sep.inputs["Vector"])
    dx = nb.math("SUBTRACT", sep.outputs["X"], x0_sock,
                  label="x - x_0", x=-600, y=y_offset - 100)
    dy = nb.math("SUBTRACT", sep.outputs["Y"], y0_sock,
                  label="y - y_0", x=-600, y=y_offset - 200)
    term_x = nb.math("MULTIPLY", dfdx0_sock, dx,
                      label="∂f/∂x · (x-x_0)", x=-400, y=y_offset - 100)
    term_y = nb.math("MULTIPLY", dfdy0_sock, dy,
                      label="∂f/∂y · (y-y_0)", x=-400, y=y_offset - 200)
    z_lin = nb.math("ADD", term_x, term_y,
                     label="grad·(p-p_0)", x=-200, y=y_offset - 150)
    z_plane = nb.math("ADD", f0_sock, z_lin,
                       label="f_0 + grad·(p-p_0)", x=0, y=y_offset)

    new_pos = nb.combine_xyz(sep.outputs["X"], sep.outputs["Y"], z_plane,
                              label="tangent (x,y,z)",
                              x=200, y=y_offset)
    set_pos = nb.add("GeometryNodeSetPosition",
                      label=f"{label}: lift", x=400, y=y_offset)
    nb.link(translate.outputs["Geometry"], set_pos.inputs["Geometry"])
    nb.link(new_pos, set_pos.inputs["Position"])
    return set_pos.outputs["Geometry"]


def taylor_surface_terms(f_expr, *, x_name, y_name):
    """Homogeneous Taylor terms of ``f`` about (x₀, y₀), degrees 0..N.

    Returns a list ``[D_0, D_1, …, D_N]`` (N = :data:`TAYLOR_SURFACE_MAX_ORDER`)
    where each ``D_k`` is the *degree-k* slice of the multivariate Taylor
    expansion:

        D_k(x, y) = Σ_{i+j=k}  ∂^k f/∂xⁱ∂yʲ (x₀,y₀) / (i! j!)
                              · (x − x₀)ⁱ (y − y₀)ʲ

    so that the order-n Taylor surface is ``Σ_{k=0}^{n} D_k`` — D_0 is the
    constant f(x₀,y₀), D_0+D_1 is the tangent plane, D_0+D_1+D_2 the
    osculating paraboloid, and so on. The coefficients are evaluated at
    the basepoint symbols ``x_0``/``y_0`` (kept free so the modifier's
    x₀/y₀ sliders drive them live); the powers keep ``x``/``y`` free so
    they resolve to the per-vertex grid coordinates at compile time.
    """
    sp_ = sympy_parser._sympy()
    x_sym = sp_.Symbol(x_name, real=True)
    y_sym = sp_.Symbol(y_name, real=True)
    x0_sym = sp_.Symbol("x_0", real=True)
    y0_sym = sp_.Symbol("y_0", real=True)
    return homogeneous_taylor_terms(f_expr, x_sym, y_sym, x0_sym, y0_sym,
                                    TAYLOR_SURFACE_MAX_ORDER)


def homogeneous_taylor_terms(expr, a_sym, b_sym, a0_sym, b0_sym, order):
    """``[D_0 … D_order]`` of a two-variable function about (a₀, b₀).

    Each mixed partial ∂^(i+j)/∂aⁱ∂bʲ is obtained from the previous one
    by a single differentiation (instead of differentiating ``expr``
    i+j times from scratch) and evaluated at the basepoint with
    ``xreplace`` — a purely structural substitution, much cheaper than
    ``subs`` and exact here since we only swap symbols for symbols.
    """
    sp_ = sympy_parser._sympy()
    at_basepoint = {a_sym: a0_sym, b_sym: b0_sym}
    partials = {(0, 0): expr}
    terms = []
    for k in range(order + 1):
        parts = []
        for i in range(k + 1):
            j = k - i
            if (i, j) not in partials:
                if j > 0:
                    partials[(i, j)] = sp_.diff(partials[(i, j - 1)], b_sym)
                else:
                    partials[(i, j)] = sp_.diff(partials[(i - 1, 0)], a_sym)
            coeff = partials[(i, j)].xreplace(at_basepoint)
            if coeff == 0:
                continue
            parts.append(coeff
                         * (a_sym - a0_sym) ** i
                         * (b_sym - b0_sym) ** j
                         / (sp_.factorial(i) * sp_.factorial(j)))
        # Keep the *factored* form (no expand): the SymPy→nodes compiler
        # memo-shares identical subexpressions, so the (x-x₀)ⁱ powers and
        # the basepoint coefficients are built once and reused. Expanding
        # would blow each term into a flat sum of monomials and create
        # thousands of un-shared nodes — slow to build and to evaluate.
        terms.append(sp_.Add(*parts))
        # Partials of degree k-1 are no longer needed.
        for i in range(k):
            partials.pop((i, k - 1 - i), None)
    return terms


def _build_taylor_surface_mesh(nb: NodeBuilder, *,
                                x0_sock, y0_sock, order_sock,
                                size_sock, resolution_sock,
                                taylor_terms, free_param_sockets,
                                x_name="x", y_name="y",
                                label="taylor surface", y_offset=-2600):
    """Build the order-n osculating Taylor surface at (x₀, y₀).

    Same skeleton as :func:`_build_tangent_plane_mesh` — a small grid
    centred on the basepoint, every vertex lifted to the Taylor z-value —
    but instead of the affine plane it sums the pre-built homogeneous
    terms ``D_0 … D_N`` gated by the runtime ``Taylor order`` socket:

        z = Σ_k  [order ≥ k] · D_k(x, y)

    The ``[order ≥ k]`` mask is a ``GREATER_THAN`` node, so dialling the
    order slider grows/shrinks the polynomial degree live, with no
    rebuild. Returns a Geometry socket carrying the meshed surface.
    """
    grid = nb.add("GeometryNodeMeshGrid",
                   label=f"{label}: grid", x=-1600, y=y_offset)
    nb.link(size_sock, grid.inputs["Size X"])
    nb.link(size_sock, grid.inputs["Size Y"])
    nb.link(resolution_sock, grid.inputs["Vertices X"])
    nb.link(resolution_sock, grid.inputs["Vertices Y"])

    # Centre the grid on (x₀, y₀, 0).
    center = nb.combine_xyz(x0_sock, y0_sock, 0.0,
                             label="basepoint XY", x=-1400, y=y_offset - 100)
    translate = nb.add("GeometryNodeTransform",
                        label=f"{label}: center", x=-1200, y=y_offset)
    nb.link(grid.outputs["Mesh"], translate.inputs["Geometry"])
    nb.link(center, translate.inputs["Translation"])

    # Per-vertex (x, y) feed the compiled Taylor terms.
    pos = nb.add("GeometryNodeInputPosition",
                  label=f"{label}: vertex", x=-1000, y=y_offset - 200)
    sep = nb.add("ShaderNodeSeparateXYZ",
                  label="separate", x=-800, y=y_offset - 200)
    nb.link(pos.outputs["Position"], sep.inputs["Vector"])
    x_sock = sep.outputs["X"]
    y_sock = sep.outputs["Y"]

    var_sockets = {x_name: x_sock, y_name: y_sock,
                   "x_0": x0_sock, "y_0": y0_sock, **free_param_sockets}
    comp = SymPyCompiler(nb, var_sockets)

    z_acc = None
    for k, dk in enumerate(taylor_terms):
        row_y = y_offset - 300 - 45 * k
        zk = compile_outlined(nb, comp, dk,
                              name=f"{nb.tree.name} D{k}",
                              x=-600, y=row_y, label=f"D_{k}")
        # mask_k = 1.0 if order ≥ k else 0.0  (k-0.5 keeps the Int compare
        # robust against float rounding).
        mask = nb.math("GREATER_THAN", order_sock, k - 0.5,
                        label=f"order ≥ {k}", x=-380, y=row_y)
        masked = nb.math("MULTIPLY", zk, mask,
                          label=f"D_{k} (gated)", x=-180, y=row_y)
        if z_acc is None:
            z_acc = masked
        else:
            z_acc = nb.math("ADD", z_acc, masked,
                             label=f"Σ ≤ {k}", x=20, y=row_y)

    new_pos = nb.combine_xyz(x_sock, y_sock, z_acc,
                              label="taylor (x,y,z)", x=240, y=y_offset)
    set_pos = nb.add("GeometryNodeSetPosition",
                      label=f"{label}: lift", x=440, y=y_offset)
    nb.link(translate.outputs["Geometry"], set_pos.inputs["Geometry"])
    nb.link(new_pos, set_pos.inputs["Position"])
    return set_pos.outputs["Geometry"]


def make_surfacefn_tree(expr_str: str, *,
                         x_name: str = "x", y_name: str = "y",
                         allowed_params: tuple[str, ...] = (),
                         x_default_range: tuple[float, float] = (-3.0, 3.0),
                         y_default_range: tuple[float, float] = (-3.0, 3.0),
                         x0_default: float = 0.0,
                         y0_default: float = 0.0,
                         key_suffix: str = ""):
    """Build a Geometry-Nodes tree visualising an explicit surface z=f(x,y).

    Sockets exposed on the modifier
    -------------------------------
    * ``Resolution X`` / ``Resolution Y`` — grid resolution
    * ``x min``/``x max``, ``y min``/``y max`` — domain rectangle
    * ``x_0`` / ``y_0`` — basepoint (drives marker + tangent plane)
    * ``Surface material`` — material slot for the main surface mesh
    * ``Marker size`` / ``Marker material``
    * ``Show tangent plane`` (bool) — toggle the tangent-plane mesh
    * ``Tangent plane size`` / ``Tangent plane resolution`` /
      ``Tangent plane material``
    * one float socket per free parameter declared in ``allowed_params``

    Geometry output
    ---------------
    Join of: the surface mesh, the marker sphere at the basepoint, and
    (if visible) the tangent plane mesh at the basepoint.

    Metadata
    --------
    Stashes ``realfn_kind = "surface"``, the source expression, and the
    text + LaTeX rendering of f(x, y), ∂f/∂x, ∂f/∂y for the panel.

    Returns
    -------
    bpy.types.NodeTree
    """
    sp_ = sympy_parser._sympy()

    # ----- Parse & differentiate -----------------------------------------
    f_expr = sympy_parser.parse_surface_expression(
        expr_str, x_name=x_name, y_name=y_name,
    )
    dfdx, dfdy = sympy_parser.surface_gradient(
        f_expr, x_name=x_name, y_name=y_name,
    )
    # Substitute x₀, y₀ for the basepoint evaluation. The result is
    # parameterised over the modifier's x_0 and y_0 sockets — same trick
    # as for the scalar tangent line.
    x_sym = sp_.Symbol(x_name, real=True)
    y_sym = sp_.Symbol(y_name, real=True)
    x0_sym = sp_.Symbol("x_0", real=True)
    y0_sym = sp_.Symbol("y_0", real=True)
    subs = {x_sym: x0_sym, y_sym: y0_sym}
    f0_expr = f_expr.subs(subs)
    dfdx0_expr = dfdx.subs(subs)
    dfdy0_expr = dfdy.subs(subs)

    # Homogeneous Taylor terms D_0 … D_N about (x₀, y₀) for the
    # scrubbable osculating-surface feature. D_0+D_1 reproduces the
    # tangent plane above; higher orders add curvature and beyond.
    taylor_terms = taylor_surface_terms(f_expr, x_name=x_name, y_name=y_name)

    # ----- Validate free symbols -----------------------------------------
    all_free = (f_expr.free_symbols | dfdx.free_symbols | dfdy.free_symbols
                | f0_expr.free_symbols | dfdx0_expr.free_symbols
                | dfdy0_expr.free_symbols)
    for _dk in taylor_terms:
        all_free |= _dk.free_symbols
    known = {x_name, y_name, "x_0", "y_0"} | set(allowed_params)
    unknown = sorted(s.name for s in all_free if s.name not in known)
    if unknown:
        raise ValueError(
            f"Symboles non autorisés : {', '.join(unknown)}. "
            f"Autorisés : {sorted(known)}"
        )

    # ----- Create tree + interface ---------------------------------------
    nt = bpy.data.node_groups.new(
        f"{SURFACE_TREE_PREFIX}{key_suffix or 'fn'}",
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

    add_int("Resolution X", 64,
             desc="Nombre de subdivisions en x du maillage de la surface")
    add_int("Resolution Y", 64,
             desc="Nombre de subdivisions en y du maillage de la surface")
    add_float("x min", float(x_default_range[0]))
    add_float("x max", float(x_default_range[1]))
    add_float("y min", float(y_default_range[0]))
    add_float("y max", float(y_default_range[1]))
    add_float("x_0", float(x0_default),
               desc="Coordonnée x du point d'ancrage où sont calculés "
                    "le marqueur et le plan tangent")
    add_float("y_0", float(y0_default),
               desc="Coordonnée y du point d'ancrage")
    add_mat("Surface material",
             desc="Matériau appliqué à la surface principale")
    add_float("Marker size", 0.15, mn=0.0,
               desc="Rayon de la sphère marqueur au point d'ancrage")
    add_mat("Marker material",
             desc="Matériau de la sphère marqueur")
    add_bool("Show tangent plane", True,
              desc="Affiche le plan tangent affine au point d'ancrage. "
                   "Décocher pour ne montrer que la surface et le marqueur")
    add_float("Tangent plane size", 1.5, mn=0.0,
               desc="Côté du petit carré qui visualise le plan tangent")
    add_int("Tangent plane resolution", 8, mn=2, mx=64,
             desc="Subdivisions du carré du plan tangent. 8 suffit "
                  "puisque c'est un plan affine — pas de courbure à capter")
    add_mat("Tangent plane material",
             desc="Matériau du plan tangent")
    add_bool("Show Taylor surface", False,
              desc="Affiche la surface de Taylor osculatrice au point "
                   "d'ancrage. Montez « Ordre de Taylor » pour passer du "
                   "plan tangent au paraboloïde, etc.")
    add_int("Taylor order", 2, mn=0, mx=TAYLOR_SURFACE_MAX_ORDER,
             desc="Ordre du développement de Taylor en (x₀, y₀). "
                  "0 = plan horizontal ; 1 = plan tangent ; "
                  "2 = paraboloïde osculateur ; plus = approximation plus "
                  "serrée. Scrubbez pour voir la surface épouser f en direct")
    add_float("Taylor surface size", 1.5, mn=0.0,
               desc="Côté du carré sur lequel la surface de Taylor est "
                    "échantillonnée, centré sur (x₀, y₀)")
    add_int("Taylor surface resolution", 24, mn=2, mx=200,
             desc="Subdivisions du carré de la surface de Taylor. Plus "
                  "élevé qu'un plan car la courbure des ordres ≥ 2 doit "
                  "être finement maillée")
    add_mat("Taylor surface material",
             desc="Matériau de la surface de Taylor")
    for p in allowed_params:
        ps = nt.interface.new_socket(p, in_out="INPUT",
                                       socket_type="NodeSocketFloat")
        ps.default_value = 1.0

    # ----- Build graph ---------------------------------------------------
    nb = NodeBuilder(nt)
    group_in = nb.add("NodeGroupInput", x=-2000, y=0)
    group_out = nb.add("NodeGroupOutput", x=2400, y=0)

    free_param_sockets = {p: group_in.outputs[p] for p in allowed_params}
    # Basepoint sockets used in subs expressions ("x_0", "y_0").
    basepoint_extra = dict(free_param_sockets)
    basepoint_extra["x_0"] = group_in.outputs["x_0"]
    basepoint_extra["y_0"] = group_in.outputs["y_0"]

    # 1) Surface mesh.
    surf_geom = _build_surface_mesh(
        nb,
        x_min_sock=group_in.outputs["x min"],
        x_max_sock=group_in.outputs["x max"],
        y_min_sock=group_in.outputs["y min"],
        y_max_sock=group_in.outputs["y max"],
        res_x_sock=group_in.outputs["Resolution X"],
        res_y_sock=group_in.outputs["Resolution Y"],
        f_expr=f_expr,
        free_param_sockets=free_param_sockets,
        x_name=x_name, y_name=y_name, y_offset=0,
    )
    surf_mat_node = nb.add("GeometryNodeSetMaterial",
                            label="surface: material",
                            x=900, y=0)
    nb.link(surf_geom, surf_mat_node.inputs["Geometry"])
    nb.link(group_in.outputs["Surface material"],
             surf_mat_node.inputs["Material"])
    surf_geom = surf_mat_node.outputs["Geometry"]

    # 2) Marker sphere at (x₀, y₀, f(x₀, y₀)).
    # Compile f(x₀, y₀) as a scalar that depends on the modifier's
    # x_0, y_0 sockets (and any free parameters).
    nbm_compiler = SymPyCompiler(nb, basepoint_extra)
    f0_sock = nbm_compiler.compile(f0_expr)
    dfdx0_sock = nbm_compiler.compile(dfdx0_expr)
    dfdy0_sock = nbm_compiler.compile(dfdy0_expr)
    marker_pos = nb.combine_xyz(
        group_in.outputs["x_0"], group_in.outputs["y_0"], f0_sock,
        label="basepoint", x=200, y=-700,
    )
    sphere = nb.add("GeometryNodeMeshUVSphere",
                     label="marker", x=400, y=-700)
    sphere.inputs["Segments"].default_value = 16
    sphere.inputs["Rings"].default_value = 8
    nb.link(group_in.outputs["Marker size"], sphere.inputs["Radius"])
    place_marker = nb.add("GeometryNodeSetPosition",
                           label="place marker", x=600, y=-700)
    nb.link(sphere.outputs["Mesh"], place_marker.inputs["Geometry"])
    nb.link(marker_pos, place_marker.inputs["Offset"])
    marker_mat_node = nb.add("GeometryNodeSetMaterial",
                              label="marker: material", x=800, y=-700)
    nb.link(place_marker.outputs["Geometry"], marker_mat_node.inputs["Geometry"])
    nb.link(group_in.outputs["Marker material"],
             marker_mat_node.inputs["Material"])

    # 3) Tangent plane mesh.
    tangent_geom = _build_tangent_plane_mesh(
        nb,
        x0_sock=group_in.outputs["x_0"],
        y0_sock=group_in.outputs["y_0"],
        f0_sock=f0_sock,
        dfdx0_sock=dfdx0_sock,
        dfdy0_sock=dfdy0_sock,
        tan_size_sock=group_in.outputs["Tangent plane size"],
        tan_resolution_sock=group_in.outputs["Tangent plane resolution"],
        y_offset=-1300,
    )
    tangent_mat_node = nb.add("GeometryNodeSetMaterial",
                               label="tangent: material",
                               x=900, y=-1300)
    nb.link(tangent_geom, tangent_mat_node.inputs["Geometry"])
    nb.link(group_in.outputs["Tangent plane material"],
             tangent_mat_node.inputs["Material"])
    # Visibility switch.
    tan_switch = nb.add("GeometryNodeSwitch",
                         label="show tangent?",
                         x=1200, y=-1300)
    tan_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show tangent plane"],
                 tan_switch.inputs["Switch"])
        nb.link(tangent_mat_node.outputs["Geometry"],
                 tan_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show tangent plane"],
                 tan_switch.inputs[0])
        nb.link(tangent_mat_node.outputs["Geometry"],
                 tan_switch.inputs[2])
    tan_out = (tan_switch.outputs["Output"]
               if "Output" in tan_switch.outputs
               else tan_switch.outputs[0])

    # 3bis) Taylor surface mesh — scrubbable osculating surface.
    taylor_geom = _build_taylor_surface_mesh(
        nb,
        x0_sock=group_in.outputs["x_0"],
        y0_sock=group_in.outputs["y_0"],
        order_sock=group_in.outputs["Taylor order"],
        size_sock=group_in.outputs["Taylor surface size"],
        resolution_sock=group_in.outputs["Taylor surface resolution"],
        taylor_terms=taylor_terms,
        free_param_sockets=free_param_sockets,
        x_name=x_name, y_name=y_name,
        y_offset=-2600,
    )
    taylor_mat_node = nb.add("GeometryNodeSetMaterial",
                              label="taylor: material", x=900, y=-2600)
    nb.link(taylor_geom, taylor_mat_node.inputs["Geometry"])
    nb.link(group_in.outputs["Taylor surface material"],
             taylor_mat_node.inputs["Material"])
    taylor_switch = nb.add("GeometryNodeSwitch",
                            label="show taylor?", x=1200, y=-2600)
    taylor_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show Taylor surface"],
                 taylor_switch.inputs["Switch"])
        nb.link(taylor_mat_node.outputs["Geometry"],
                 taylor_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show Taylor surface"],
                 taylor_switch.inputs[0])
        nb.link(taylor_mat_node.outputs["Geometry"],
                 taylor_switch.inputs[2])
    taylor_out = (taylor_switch.outputs["Output"]
                  if "Output" in taylor_switch.outputs
                  else taylor_switch.outputs[0])

    # 4) Join everything.
    join = nb.add("GeometryNodeJoinGeometry",
                   label="final", x=1900, y=-400)
    nb.link(surf_geom, join.inputs["Geometry"])
    nb.link(marker_mat_node.outputs["Geometry"], join.inputs["Geometry"])
    nb.link(tan_out, join.inputs["Geometry"])
    nb.link(taylor_out, join.inputs["Geometry"])
    nb.link(join.outputs["Geometry"], group_out.inputs[0])

    # ----- Metadata stash ------------------------------------------------
    nt["realfn_kind"] = "surface"
    nt["realfn_expr"] = expr_str
    nt["realfn_var_x"] = x_name
    nt["realfn_var_y"] = y_name
    nt["realfn_params"] = list(allowed_params)
    nt["realfn_f_text"] = str(sp_.sstr(f_expr))
    nt["realfn_f_latex"] = str(sp_.latex(f_expr))
    nt["realfn_dfdx_text"] = str(sp_.sstr(dfdx))
    nt["realfn_dfdx_latex"] = str(sp_.latex(dfdx))
    nt["realfn_dfdy_text"] = str(sp_.sstr(dfdy))
    nt["realfn_dfdy_latex"] = str(sp_.latex(dfdy))
    nt["realfn_taylor_surface_max"] = int(TAYLOR_SURFACE_MAX_ORDER)
    # Cumulative Taylor polynomials T_0 … T_N (T_n = Σ_{k≤n} D_k), text +
    # LaTeX, so the panel can display the order-n polynomial by a cheap
    # list index (no SymPy in draw). Index == order.
    _cum = sp_.S.Zero
    _taylor_polys = []
    for _dk in taylor_terms:
        _cum = _cum + _dk
        _taylor_polys.append(_cum)
    nt["realfn_taylor_poly_text"] = [str(sp_.sstr(t)) for t in _taylor_polys]
    nt["realfn_taylor_poly_latex"] = [str(sp_.latex(t)) for t in _taylor_polys]
    return nt
