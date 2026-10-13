"""
Geometry Nodes tree construction for a real function y = f(x) viewer.

The tree exposes the following inputs to the modifier:

* ``x min`` / ``x max`` — sampling domain on the x-axis;
* ``Resolution`` — number of points along the curve and the tangent
  segment;
* ``x_0`` — basepoint where the tangent is computed (scrubbing this
  slider slides the tangent live);
* ``Curve thickness`` / ``Tangent thickness`` — tube radii for the
  visual rendering of each.

The output geometry joins three pieces:

1. The function curve y = f(x), sampled as N points (x_i, f(x_i), 0)
   linked by a Curve Line and swept by a small Curve Circle to make a
   readable tube.
2. The tangent line at x₀, which is itself an affine function of x —
   so it goes through the exact same compilation pipeline as f, with
   the expression T(x) = f(x₀) + f'(x₀)·(x - x₀). Both x₀ and the
   tangent are recomputed on the GPU side every frame; nothing is
   precomputed in Python.
3. A small sphere at (x₀, f(x₀), 0) marking the point of tangency.

Because the tangent expression contains x₀ as a *free symbol*, the
compiler exposes it as a modifier socket. Dragging the slider moves
both the tangent and the marker simultaneously and continuously.

Design choice: each curve gets its own Mesh Line + index→position
sub-graph, instead of trying to share one. The shared version would
save ~10 nodes but force both curves to use the same domain split,
which prevents future per-curve resolution differences (e.g. denser
sampling near a steep part of f). The duplicated scaffolding is also
trivial to read in the node editor.
"""

from __future__ import annotations

import bpy
import sympy as sp

from .compiler import NodeBuilder, SymPyCompiler, compile_outlined
from . import sympy_parser


# Identifiable prefix for tree names — useful for the operator that
# wants to detect "is this object one of ours?" by ``startswith``.
TREE_PREFIX = "REALFN_"


def _build_curve_path(nb: NodeBuilder, *,
                       n_samples_sock, x_min_sock, x_max_sock,
                       expr, free_param_sockets, x_var_name="x",
                       label="path", y_offset=0):
    """Build one parametric path realising x ↦ (x, expr(x), 0).

    Returns the Geometry socket carrying a Curve (not yet converted
    to mesh).

    ``free_param_sockets`` maps the name of each free symbol other
    than the integration variable to its source socket — usually
    GroupInput outputs.
    """
    # 1) Mesh Line of N points along the world X axis (will be
    #    repositioned in step 3). Using a Mesh Line rather than a
    #    Curve Line gives us free per-vertex computation via
    #    Set Position; we convert to curve at the end for sweeping.
    mesh_line = nb.add(
        "GeometryNodeMeshLine",
        label=f"{label}: line", x=-1400, y=y_offset,
        mode="OFFSET", count_mode="TOTAL",
    )
    nb.link(n_samples_sock, mesh_line.inputs["Count"])

    # 2) Compute t ∈ [x_min, x_max] from per-vertex index.
    idx = nb.add("GeometryNodeInputIndex", x=-1400, y=y_offset - 200)
    n_minus_1 = nb.math("SUBTRACT", n_samples_sock, 1.0,
                         label="N-1", x=-1200, y=y_offset - 100)
    t_norm = nb.math("DIVIDE", idx.outputs[0], n_minus_1,
                      label="i/(N-1)", x=-1000, y=y_offset - 100)
    span = nb.math("SUBTRACT", x_max_sock, x_min_sock,
                    label="x_max - x_min", x=-1000, y=y_offset - 250)
    scaled = nb.math("MULTIPLY", t_norm, span,
                      label="i/(N-1)·Δx", x=-800, y=y_offset - 100)
    x_sock = nb.math("ADD", x_min_sock, scaled,
                      label=f"{x_var_name} = x_min + i·Δx/(N-1)",
                      x=-600, y=y_offset - 100)

    # 3) Compile the user expression into a sub-graph fed by x_sock.
    var_sockets = {x_var_name: x_sock, **free_param_sockets}
    compiler = SymPyCompiler(nb, var_sockets)
    y_sock = compile_outlined(nb, compiler, expr,
                              name=f"{nb.tree.name} {label}",
                              x=-400, y=y_offset - 100, label=label)

    # 4) Build the world-space position (x, y, 0) and write it to
    #    each vertex.
    position = nb.combine_xyz(x_sock, y_sock, 0.0,
                               label=f"{label}: (x, f(x), 0)",
                               x=200, y=y_offset)
    set_pos = nb.add("GeometryNodeSetPosition",
                      label=f"{label}: place",
                      x=400, y=y_offset)
    nb.link(mesh_line.outputs["Mesh"], set_pos.inputs["Geometry"])
    nb.link(position, set_pos.inputs["Position"])

    # 5) Convert mesh to curve so we can sweep a profile later.
    to_curve = nb.add("GeometryNodeMeshToCurve",
                       label=f"{label}: as curve",
                       x=600, y=y_offset)
    nb.link(set_pos.outputs["Geometry"], to_curve.inputs["Mesh"])
    return to_curve.outputs["Curve"]


def _build_tube(nb: NodeBuilder, *, curve_sock, radius_sock,
                 x=900, y=0, label="tube"):
    """Sweep a small circle profile along a curve to make it visible."""
    profile = nb.add("GeometryNodeCurvePrimitiveCircle",
                      label=f"{label}: profile",
                      x=x, y=y - 200)
    profile.mode = "RADIUS"
    profile.inputs["Resolution"].default_value = 8
    nb.link(radius_sock, profile.inputs["Radius"])
    to_mesh = nb.add("GeometryNodeCurveToMesh",
                      label=f"{label}: sweep",
                      x=x + 200, y=y)
    nb.link(curve_sock, to_mesh.inputs["Curve"])
    nb.link(profile.outputs["Curve"], to_mesh.inputs["Profile Curve"])
    return to_mesh.outputs["Mesh"]


def make_realfn_tree(expr_str: str, *,
                      var_name: str = "x",
                      allowed_params: tuple[str, ...] = (),
                      derivative_order: int = 1,
                      taylor_order: int = 0,
                      x_default_range: tuple[float, float] = (-5.0, 5.0),
                      x0_default: float = 0.0,
                      key_suffix: str = ""):
    """Build a Geometry Nodes tree visualising f(x) together with
    several derivatives and/or Taylor polynomials.

    Parameters
    ----------
    expr_str : str
        User-typed formula for f(x).
    var_name : str
        Independent variable name (default ``"x"``).
    allowed_params : tuple of str
        Extra free symbols the formula may reference. Each becomes a
        float modifier socket.
    derivative_order : int
        Maximum derivative order to trace. ``0`` shows only f;
        ``1`` adds f'; ``k`` adds f, f', ..., f^(k) as separate
        curves, each with its own thickness slider. Default ``1`` for
        legacy behaviour (= the old "tangent" object, replaced by f'
        in this version — see below).
    taylor_order : int
        Maximum Taylor polynomial order to trace at x₀. ``0`` adds
        nothing; ``1`` adds the tangent line T₁(x) = f(x₀) + f'(x₀)·(x-x₀);
        ``n`` adds T₁, T₂, ..., Tₙ as separate curves.
    x_default_range : (float, float)
        Initial sampling domain.
    x0_default : float
        Initial basepoint for the Taylor polynomials and the marker.

    Returns
    -------
    bpy.types.NodeTree
        A fresh Geometry Nodes tree with one input socket per derivative
        thickness, per Taylor-polynomial thickness, plus the standard
        sampling/range/x₀ controls. ID properties stash the source
        expression and the orders so the Edit operator can recreate.
    """
    if derivative_order < 0:
        raise ValueError("derivative_order doit être ≥ 0")
    if taylor_order < 0:
        raise ValueError("taylor_order doit être ≥ 0")

    sp_ = sympy_parser._sympy()
    f_expr = sympy_parser.parse_expression(expr_str, var_name=var_name)
    x_sym = sp_.Symbol(var_name, real=True)
    x0_sym = sp_.Symbol("x_0", real=True)

    # --- Build the list of (label, sympy expression) pieces to trace ----
    # Each piece becomes one curve in the final geometry, with its own
    # thickness socket on the modifier so it can be individually shown
    # or hidden (thickness = 0).
    pieces: list[tuple[str, object]] = []

    # Derivatives: f, f', f'', ..., f^(k)
    deriv = f_expr
    for k in range(derivative_order + 1):
        if k == 0:
            label = "f"
        elif k == 1:
            label = "f'"
        elif k == 2:
            label = "f''"
        elif k == 3:
            label = "f'''"
        else:
            label = f"f^({k})"
        pieces.append((label, deriv))
        if k < derivative_order:
            deriv = sp_.diff(deriv, x_sym)

    # Taylor polynomials T₁, T₂, ..., T_n at x₀.
    # T_n(x) = sum_{j=0}^{n} f^(j)(x₀) · (x - x₀)^j / j!
    # We accumulate the running derivative *and* the running factorial
    # to avoid recomputing the diff chain for each n.
    if taylor_order >= 1:
        delta = x_sym - x0_sym
        taylor_running = sp_.S.Zero
        running_deriv = f_expr
        running_factorial = sp_.S.One
        for n in range(0, taylor_order + 1):
            # Add the n-th term: f^(n)(x₀) · (x-x₀)^n / n!
            taylor_running = (taylor_running
                              + running_deriv.subs(x_sym, x0_sym)
                              * delta**n / running_factorial)
            if n >= 1:
                # T_n is now complete — emit it as a piece.
                label = f"T_{n}"
                pieces.append((label, taylor_running))
            # Prepare next iteration: differentiate once more, multiply
            # the factorial accumulator by (n+1).
            running_deriv = sp_.diff(running_deriv, x_sym)
            running_factorial = running_factorial * (n + 1)

    # The marker sits at (x₀, f(x₀), 0). Computed as a SymPy expression
    # so it's compiled through the same pipeline as everything else.
    marker_y_expr = f_expr.subs(x_sym, x0_sym)

    # --- Validate user parameters -------------------------------------
    all_free = set()
    for _, e in pieces:
        all_free |= e.free_symbols
    all_free |= marker_y_expr.free_symbols
    known = {var_name, "x_0"} | set(allowed_params)
    unknown = sorted(s.name for s in all_free if s.name not in known)
    if unknown:
        raise ValueError(
            f"Symboles non autorisés : {', '.join(unknown)}. "
            f"Autorisés : {sorted(known)}"
        )

    # --- Create the node tree and declare its interface ---------------
    nt = bpy.data.node_groups.new(
        f"{TREE_PREFIX}{key_suffix or 'fn'}", "GeometryNodeTree",
    )
    nt.interface.new_socket(
        "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry",
    )
    res_sock = nt.interface.new_socket(
        "Resolution", in_out="INPUT", socket_type="NodeSocketInt",
    )
    res_sock.default_value = 256
    res_sock.min_value = 2
    res_sock.max_value = 10000
    res_sock.description = "Number of samples along each traced curve"
    xmin_sock = nt.interface.new_socket(
        "x min", in_out="INPUT", socket_type="NodeSocketFloat",
    )
    xmin_sock.default_value = float(x_default_range[0])
    xmax_sock = nt.interface.new_socket(
        "x max", in_out="INPUT", socket_type="NodeSocketFloat",
    )
    xmax_sock.default_value = float(x_default_range[1])
    x0_socket = nt.interface.new_socket(
        "x_0", in_out="INPUT", socket_type="NodeSocketFloat",
    )
    x0_socket.default_value = float(x0_default)
    x0_socket.description = (
        "Basepoint. Drives the marker sphere position and (if any "
        "Taylor polynomials are traced) the centre of expansion. "
        "Scrub to slide everything live"
    )
    marker_r = nt.interface.new_socket(
        "Marker size", in_out="INPUT", socket_type="NodeSocketFloat",
    )
    marker_r.default_value = 0.1
    marker_r.min_value = 0.0

    marker_mat = nt.interface.new_socket(
        "Marker material", in_out="INPUT",
        socket_type="NodeSocketMaterial",
    )
    marker_mat.description = (
        "Matériau de la sphère marqueur en x₀. Laisser vide pour le "
        "matériau par défaut"
    )

    # One thickness slider + one visibility checkbox per traced piece.
    #
    # Visibility uses a BoolProperty wired to a Geometry Switch in the
    # build phase below, so unchecking the box is *truly* "this curve
    # contributes nothing to the output". Setting thickness to 0 also
    # hides the curve visually, but the underlying tube geometry is
    # still computed; the boolean cut is cleaner — useful when an
    # advanced user adds downstream nodes that consume the modifier
    # output.
    thickness_socket_names: list[str] = []
    visible_socket_names: list[str] = []
    material_socket_names: list[str] = []
    for label, _ in pieces:
        sock_name = f"Thickness · {label}"
        thickness_socket_names.append(sock_name)
        s = nt.interface.new_socket(
            sock_name, in_out="INPUT", socket_type="NodeSocketFloat",
        )
        # All curves share the same default thickness so the initial
        # rendering is visually balanced; the user can then thicken f
        # or thin out high-order derivatives independently.
        s.default_value = 0.01
        s.min_value = 0.0
        s.description = (
            f"Tube radius for {label}. Set to 0 to make the tube "
            f"degenerate to nothing (cheap soft-hide). For a hard "
            f"hide that also removes the geometry, uncheck the "
            f"'Visible · {label}' box below"
        )

        vis_sock_name = f"Visible · {label}"
        visible_socket_names.append(vis_sock_name)
        v = nt.interface.new_socket(
            vis_sock_name, in_out="INPUT", socket_type="NodeSocketBool",
        )
        v.default_value = True
        v.description = (
            f"Show or hide the {label} curve. Unchecking it removes "
            f"the tube entirely from the output geometry"
        )

        # Per-piece material slot. Left unset by default (Blender
        # falls back to the default material), so a freshly created
        # tree still renders without forcing the user to assign one.
        # The material socket has no default_value mechanism beyond
        # "None" — assignment happens via the modifier UI.
        mat_sock_name = f"Material · {label}"
        material_socket_names.append(mat_sock_name)
        mat = nt.interface.new_socket(
            mat_sock_name, in_out="INPUT",
            socket_type="NodeSocketMaterial",
        )
        mat.description = (
            f"Matériau appliqué au tube de {label}. Laisser vide "
            f"pour utiliser le matériau par défaut de Blender"
        )

    # Sliders for user-declared free parameters.
    for p in allowed_params:
        p_sock = nt.interface.new_socket(
            p, in_out="INPUT", socket_type="NodeSocketFloat",
        )
        p_sock.default_value = 1.0

    # --- Build the node tree -----------------------------------------
    nb = NodeBuilder(nt)
    group_in = nb.add("NodeGroupInput", x=-1700, y=0)
    group_out = nb.add("NodeGroupOutput", x=2400, y=0)

    free_param_sockets = {p: group_in.outputs[p] for p in allowed_params}
    # x₀ is also a free symbol from the compiler's point of view —
    # it appears in the Taylor expressions and must resolve to the x_0
    # group-input socket.
    expr_param_sockets = dict(free_param_sockets)
    expr_param_sockets["x_0"] = group_in.outputs["x_0"]

    # Pre-allocate the final join — every piece's tube and the marker
    # plug into it. We position pieces vertically in the node editor
    # purely for readability of the resulting graph.
    join = nb.add("GeometryNodeJoinGeometry",
                   label="Final geometry", x=1900, y=0)

    for idx, (label, expr) in enumerate(pieces):
        y_offset = -700 * idx
        curve_sock = _build_curve_path(
            nb,
            n_samples_sock=group_in.outputs["Resolution"],
            x_min_sock=group_in.outputs["x min"],
            x_max_sock=group_in.outputs["x max"],
            expr=expr,
            free_param_sockets=expr_param_sockets,
            x_var_name=var_name,
            label=label, y_offset=y_offset,
        )
        sock_name = thickness_socket_names[idx]
        mesh_sock = _build_tube(
            nb, curve_sock=curve_sock,
            radius_sock=group_in.outputs[sock_name],
            x=900, y=y_offset, label=label,
        )

        # Per-piece material. Inserted between the tube and the
        # visibility Switch so the material assignment lives inside
        # the True branch only — when the piece is hidden the empty
        # geometry travels through the switch unchanged, no spurious
        # SetMaterial overhead. The SetMaterial node accepts the
        # Material socket directly from the group input; if the user
        # hasn't assigned a material the socket carries None and
        # Blender simply leaves the mesh with its default material.
        set_mat = nb.add(
            "GeometryNodeSetMaterial",
            label=f"{label}: material",
            x=1100, y=y_offset,
        )
        nb.link(mesh_sock, set_mat.inputs["Geometry"])
        nb.link(group_in.outputs[material_socket_names[idx]],
                 set_mat.inputs["Material"])
        mesh_sock = set_mat.outputs["Geometry"]

        # Geometry Switch driven by the "Visible · <label>" boolean.
        # ``input_type='GEOMETRY'`` makes the True / False inputs accept
        # geometry sockets; leaving the False input unconnected gives an
        # empty geometry, so unchecking the box removes this piece
        # entirely from the joined output.
        switch = nb.add(
            "GeometryNodeSwitch",
            label=f"{label}: visible?",
            x=1400, y=y_offset,
            input_type="GEOMETRY",
        )
        # The Switch node's input socket names depend on the Blender
        # build (some versions expose them as "Switch / False / True",
        # others use indexed identifiers). We look them up by name with
        # a robust fallback to indices.
        try:
            switch_in = switch.inputs["Switch"]
            false_in = switch.inputs["False"]
            true_in = switch.inputs["True"]
        except KeyError:
            switch_in = switch.inputs[0]
            false_in = switch.inputs[1]
            true_in = switch.inputs[2]
        nb.link(group_in.outputs[visible_socket_names[idx]], switch_in)
        nb.link(mesh_sock, true_in)
        # False input left unconnected → resolves to "empty geometry"
        # on Blender's side, which is exactly what we want.

        try:
            switch_out = switch.outputs["Output"]
        except KeyError:
            switch_out = switch.outputs[0]
        nb.link(switch_out, join.inputs["Geometry"])

    # Marker sphere at (x₀, f(x₀), 0) — sits below all the curves in
    # the node editor.
    marker_y_off = -700 * len(pieces)
    sphere = nb.add("GeometryNodeMeshUVSphere",
                     label="Marker", x=400, y=marker_y_off)
    sphere.inputs["Segments"].default_value = 16
    sphere.inputs["Rings"].default_value = 8
    nb.link(group_in.outputs["Marker size"], sphere.inputs["Radius"])
    marker_compiler = SymPyCompiler(nb, expr_param_sockets)
    marker_y_sock = marker_compiler.compile(marker_y_expr)
    marker_pos = nb.combine_xyz(
        group_in.outputs["x_0"], marker_y_sock, 0.0,
        label="Marker pos (x₀, f(x₀), 0)", x=600, y=marker_y_off,
    )
    set_marker = nb.add("GeometryNodeSetPosition",
                         label="Place marker", x=900, y=marker_y_off)
    nb.link(sphere.outputs["Mesh"], set_marker.inputs["Geometry"])
    nb.link(marker_pos, set_marker.inputs["Offset"])
    # Material for the marker sphere.
    set_marker_mat = nb.add(
        "GeometryNodeSetMaterial",
        label="Marker material", x=1100, y=marker_y_off,
    )
    nb.link(set_marker.outputs["Geometry"],
             set_marker_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Marker material"],
             set_marker_mat.inputs["Material"])
    nb.link(set_marker_mat.outputs["Geometry"], join.inputs["Geometry"])

    # Final connection to group output.
    nb.link(join.outputs["Geometry"], group_out.inputs[0])

    # Stash metadata for the Edit operator + per-piece formulas so the
    # panel can display the equation next to each visibility checkbox
    # without re-parsing or re-differentiating at draw time.
    #
    # The two formula lists are parallel to ``piece_labels``: the
    # i-th label, plain-text formula and LaTeX formula all describe the
    # same curve. Order matches the declaration order of the
    # ``Visible · …`` / ``Thickness · …`` sockets, so the panel can
    # map by index.
    #
    # Per-label simplification strategy
    # ---------------------------------
    # The aim is to display each formula in the form that is most
    # *pedagogically informative*, not the one closest to what SymPy
    # built internally.
    #
    # * **f, f', f''…** (derivatives) → ``sp.factor``. Factoring helps
    #   the user *see the zeros* of f' (extrema of f), f'' (inflexion
    #   points), etc. ``3*x**2 - 3`` becomes ``3*(x-1)*(x+1)``, which
    #   is exactly the form a calculus textbook would write.
    #
    # * **T_n** (Taylor polynomials) → kept in their *accumulated*
    #   form ``f(x_0) + f'(x_0)(x - x_0) + f''(x_0)(x - x_0)²/2 + …``
    #   because this is the canonical Taylor expansion, and it stays
    #   readable when x_0 is symbolic. We do NOT call ``sp.expand``
    #   here — that would distribute every ``(x - x_0)^n`` into a
    #   polynomial in two variables and produce illegible 200-char
    #   strings for T_5 at symbolic x_0. The user can switch to a
    #   numeric x_0 later if they want the expanded form; that's a
    #   separate display, not a simplification.
    #
    # Beyond factor / no-op, we also unwrap a stray leading
    # ``Mul(-1, ...)`` via ``sp.simplify`` if the formula starts
    # with one — that's the ``-1*sin(x)`` → ``-sin(x)`` case the
    # user explicitly cared about.
    def _simplified(label, expr):
        try:
            if label.startswith("T_"):
                # Taylor: keep the accumulated form (most readable).
                return expr
            # Derivatives (including f itself): factor when possible.
            # ``factor`` returns the input unchanged when nothing
            # factors — so non-factorable expressions like sin(x)
            # round-trip cleanly.
            return sp_.factor(expr)
        except Exception:
            # If SymPy hits a corner case (e.g. with Heaviside in the
            # expression), keep the original. Better to display an
            # unsimplified formula than to fail the build.
            return expr

    simplified_pieces = [(lab, _simplified(lab, e)) for lab, e in pieces]

    nt["realfn_kind"] = "scalar"
    nt["realfn_expr"] = expr_str
    nt["realfn_var"] = var_name
    nt["realfn_params"] = list(allowed_params)
    nt["realfn_derivative_order"] = int(derivative_order)
    nt["realfn_taylor_order"] = int(taylor_order)
    nt["realfn_piece_labels"] = [lab for lab, _ in simplified_pieces]
    # Plain SymPy text form: ``sin(x)``, ``-x**2/6 + x``, etc.
    nt["realfn_piece_formulas"] = [
        str(sp_.sstr(e)) for _, e in simplified_pieces
    ]
    # LaTeX form: ``\sin{\left(x \right)}``, ``-\frac{x^{3}}{6} + x``.
    # Stored alongside the text form so the user can switch display
    # mode in the panel or copy a ready-to-paste LaTeX fragment.
    nt["realfn_piece_formulas_latex"] = [
        str(sp_.latex(e)) for _, e in simplified_pieces
    ]
    return nt

