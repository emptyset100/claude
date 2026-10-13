"""
Geometry Nodes tree construction for a 3D vector function F: R → R³.

The user provides a SymPy ``Vector`` expression in a fixed
``ReferenceFrame`` ``N`` (see :mod:`sympy_parser`). We build a tree
that displays two things in the viewport:

1. **Trace curve** — the locus of F(t) for t ∈ [t_min, t_max],
   sampled as a poly-line and tubed for visibility. This is the
   3D analogue of the curve produced by :mod:`tree` for scalar
   functions.

2. **Current derivative arrow** — an instance of the bundled
   ``Vecteur`` node group (see :mod:`vecteur`), with its ``orig``
   input set to F(t₀) and its ``ext`` input set to F(t₀) + F'(t₀).
   Scrubbing the ``t_0`` modifier socket slides both endpoints in
   real time, so the user sees the velocity vector ride along the
   trace as t₀ moves.

Vector pipeline
---------------
The compilation pipeline mirrors the scalar one: a single
:class:`SymPyCompiler` instance is shared across all three
components of every vector quantity, so common sub-expressions
between Fx, Fy, Fz (and between F(t) and F'(t)) emit only once.

The mesh sampling differs from the scalar case in that the
per-vertex position is genuinely 3D — there's no implicit "z = 0".
We use the same Mesh Line + Index + Set Position scaffold, but
the Position vector comes from a CombineXYZ fed by three Math
sub-graphs (one per component), packaged inside
:func:`compiler.compile_vector_components`.
"""

from __future__ import annotations

import bpy

from . import compiler, sympy_parser, vecteur


# Identifiable prefix for vector trees — separate from the scalar
# TREE_PREFIX of :mod:`tree` so panel code can tell the two
# families apart at a glance.
VECTOR_TREE_PREFIX = "REALFNVEC_"


def _build_vector_curve(nb: compiler.NodeBuilder, *,
                          n_samples_sock, t_min_sock, t_max_sock,
                          components, var_sockets,
                          var_name="t", label="trace",
                          y_offset=0):
    """Build the 3D trace curve from a SymPy component triplet.

    Returns the Geometry socket carrying a Curve (not yet a tube — the
    caller is in charge of sweeping a profile).

    The structure is the same as :func:`tree._build_curve_path` but
    the per-vertex position is built from three component sub-graphs
    rather than a single ``(x, f(x), 0)`` packed expression.
    """
    # Mesh Line of N points along the world X axis (positions get
    # overwritten in the Set Position step).
    mesh_line = nb.add(
        "GeometryNodeMeshLine",
        label=f"{label}: line", x=-1400, y=y_offset,
        mode="OFFSET", count_mode="TOTAL",
    )
    nb.link(n_samples_sock, mesh_line.inputs["Count"])

    # Compute t ∈ [t_min, t_max] from per-vertex index.
    idx = nb.add("GeometryNodeInputIndex", x=-1400, y=y_offset - 200)
    n_minus_1 = nb.math("SUBTRACT", n_samples_sock, 1.0,
                          label="N-1", x=-1200, y=y_offset - 100)
    t_norm = nb.math("DIVIDE", idx.outputs[0], n_minus_1,
                       label="i/(N-1)", x=-1000, y=y_offset - 100)
    span = nb.math("SUBTRACT", t_max_sock, t_min_sock,
                     label="t_max - t_min", x=-1000, y=y_offset - 250)
    scaled = nb.math("MULTIPLY", t_norm, span,
                       label="i·Δt/(N-1)", x=-800, y=y_offset - 100)
    t_sock = nb.math("ADD", t_min_sock, scaled,
                       label=f"{var_name} = t_min + i·Δt/(N-1)",
                       x=-600, y=y_offset - 100)

    # Wire the integration variable into the symbol-to-socket mapping
    # used by the vector compiler.
    var_sockets_with_t = dict(var_sockets)
    var_sockets_with_t[var_name] = t_sock

    # Compile (Fx, Fy, Fz) into a single CombineXYZ vector output.
    position_sock = compiler.compile_vector_components(
        nb, components, var_sockets_with_t,
        x=200, y=y_offset, label=f"{label}: F(t)",
    )

    # Move each mesh vertex onto F(t_i).
    set_pos = nb.add("GeometryNodeSetPosition",
                      label=f"{label}: place",
                      x=400, y=y_offset)
    nb.link(mesh_line.outputs["Mesh"], set_pos.inputs["Geometry"])
    nb.link(position_sock, set_pos.inputs["Position"])

    # Mesh → Curve so we can sweep a tube profile downstream.
    to_curve = nb.add("GeometryNodeMeshToCurve",
                       label=f"{label}: as curve",
                       x=600, y=y_offset)
    nb.link(set_pos.outputs["Geometry"], to_curve.inputs["Mesh"])
    return to_curve.outputs["Curve"]


def _build_tube(nb, *, curve_sock, radius_sock, x=900, y=0,
                 label="tube", resolution=8):
    """Sweep a small circle profile along a curve to make it visible.

    Lifted from :mod:`tree` and tweaked: the profile resolution is
    parametrised because the trace curve, being 3D and seen from
    arbitrary angles, benefits from a slightly higher tube
    resolution than a flat-plane curve."""
    profile = nb.add("GeometryNodeCurvePrimitiveCircle",
                      label=f"{label}: profile",
                      x=x, y=y - 200)
    profile.mode = "RADIUS"
    profile.inputs["Resolution"].default_value = resolution
    nb.link(radius_sock, profile.inputs["Radius"])
    to_mesh = nb.add("GeometryNodeCurveToMesh",
                      label=f"{label}: sweep",
                      x=x + 200, y=y)
    nb.link(curve_sock, to_mesh.inputs["Curve"])
    nb.link(profile.outputs["Curve"], to_mesh.inputs["Profile Curve"])
    return to_mesh.outputs["Mesh"]


def make_vectorfn_tree(expr_str: str, *,
                        var_name: str = "t",
                        allowed_params: tuple = (),
                        t_default_range: tuple = (-3.14, 3.14),
                        t0_default: float = 0.0,
                        key_suffix: str = ""):
    """Build a Geometry Nodes tree for a 3D vector function F(t).

    Visualises the trace curve plus a derivative-vector arrow at t₀,
    using the bundled "Vecteur" node group (see :mod:`vecteur`) for
    the arrow geometry. The arrow's origin sits on the trace
    (``orig = F(t₀)``) and its tip is F(t₀) + F'(t₀), so it
    visualises the velocity vector glued to the curve — the classic
    tangent vector of differential geometry.

    Parameters
    ----------
    expr_str : str
        Vector expression in the ``N`` reference frame, e.g.
        ``"cos(t)*N.x + sin(t)*N.y + t*N.z"`` for a helix.
    var_name : str
        Integration variable name (default ``"t"``).
    allowed_params : tuple of str
        Free parameter names that may appear in ``expr_str``; each
        becomes a float modifier socket.
    t_default_range : (float, float)
        Initial values for ``t min`` and ``t max``.
    t0_default : float
        Initial basepoint where the derivative vector is computed.

    Returns
    -------
    bpy.types.NodeTree
        Fresh tree, ready to attach to a modifier. Stashes the
        original expression and a few labels as ID properties for
        a future Edit operator (not yet wired in this version).

    Notes
    -----
    Unlike the scalar :func:`tree.make_realfn_tree`, we don't (yet)
    surface derivative-order or Taylor-order knobs. The reason is
    pedagogical scope: in 3D the immediate value is the *tangent
    vector* on a *trace curve*, and adding multi-order
    visualisation here would clutter the viewport with arrows
    pointing in arbitrary 3D directions. Higher-order derivatives
    can be added later as toggleable second/third arrows when the
    plain version proves out.
    """
    # Parse and decompose F(t) into (Fx, Fy, Fz).
    components = sympy_parser.parse_vector_expression(
        expr_str, var_name=var_name,
    )
    sp_ = sympy_parser._sympy()

    # Symbolic derivative F'(t) — component-wise.
    derivatives = sympy_parser.vector_diff(components, var_name=var_name)
    # Second derivative F''(t) — applied once more to F'(t). The
    # acceleration vector is conceptually distinct from the velocity
    # vector even when they share components (e.g. for a uniform
    # circular motion, F'' is centripetal — orthogonal to F').
    second_derivatives = sympy_parser.vector_diff(
        derivatives, var_name=var_name,
    )

    # Validate free parameters against components and BOTH derivative
    # orders — a user-declared parameter may legitimately appear in
    # F''(t) only (e.g. an acceleration constant that vanishes from
    # F and F').
    all_free = set()
    for c in components + derivatives + second_derivatives:
        all_free |= c.free_symbols
    known = {var_name} | set(allowed_params)
    unknown = sorted(s.name for s in all_free if s.name not in known)
    if unknown:
        raise ValueError(
            f"Symboles non autorisés : {', '.join(unknown)}. "
            f"Autorisés : {sorted(known)}"
        )

    nt = bpy.data.node_groups.new(
        f"{VECTOR_TREE_PREFIX}{key_suffix or 'fn'}", "GeometryNodeTree",
    )

    # --- declare the node-group interface -------------------------------
    nt.interface.new_socket(
        "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry",
    )
    res = nt.interface.new_socket(
        "Resolution", in_out="INPUT", socket_type="NodeSocketInt",
    )
    res.default_value = 256
    res.min_value = 2
    res.max_value = 10000
    res.description = "Nombre d'échantillons le long de la trajectoire"
    tmin = nt.interface.new_socket(
        "t min", in_out="INPUT", socket_type="NodeSocketFloat",
    )
    tmin.default_value = float(t_default_range[0])
    tmax = nt.interface.new_socket(
        "t max", in_out="INPUT", socket_type="NodeSocketFloat",
    )
    tmax.default_value = float(t_default_range[1])
    t0 = nt.interface.new_socket(
        "t_0", in_out="INPUT", socket_type="NodeSocketFloat",
    )
    t0.default_value = float(t0_default)
    t0.description = (
        "Point d'ancrage de la flèche dérivée. Faire varier ce slider "
        "fait glisser la flèche le long de la trajectoire"
    )
    trace_r = nt.interface.new_socket(
        "Trace thickness", in_out="INPUT", socket_type="NodeSocketFloat",
    )
    trace_r.default_value = 0.02
    trace_r.min_value = 0.0
    trace_r.description = "Rayon du tube qui matérialise la trajectoire"

    # Visibility toggles. Each arrow can be shown or hidden
    # independently — useful to compare conceptually (the position
    # vector points *from the origin* to F(t₀), the velocity vector
    # is *anchored on the trace at F(t₀)*).
    #
    # These wire to ``GeometryNodeSwitch`` nodes downstream; unchecking
    # the box returns an empty geometry for that branch, leaving the
    # rest of the join untouched. Same pattern as the scalar pieces.
    show_pos = nt.interface.new_socket(
        "Show position vector", in_out="INPUT",
        socket_type="NodeSocketBool",
    )
    show_pos.default_value = True
    show_pos.description = (
        "Affiche le vecteur position depuis l'origine (0, 0, 0) "
        "jusqu'à F(t₀). Décocher pour ne montrer que la vitesse "
        "et / ou l'accélération"
    )
    show_deriv = nt.interface.new_socket(
        "Show derivative vector", in_out="INPUT",
        socket_type="NodeSocketBool",
    )
    show_deriv.default_value = True
    show_deriv.description = (
        "Affiche le vecteur vitesse F'(t₀) ancré au point F(t₀) "
        "de la trajectoire. C'est la tangente géométrique à la courbe"
    )
    show_accel = nt.interface.new_socket(
        "Show acceleration vector", in_out="INPUT",
        socket_type="NodeSocketBool",
    )
    show_accel.default_value = True
    show_accel.description = (
        "Affiche le vecteur accélération F''(t₀) ancré au même point "
        "F(t₀). Pour un mouvement circulaire uniforme il pointe vers "
        "le centre (accélération centripète)"
    )

    # Per-curve material slots — one for the trace tube and one for
    # each of the three arrow instances. Same pattern as the scalar
    # per-piece materials: empty by default, panel picker lets the
    # user assign any ``bpy.types.Material``.
    mat_trace = nt.interface.new_socket(
        "Material · trace", in_out="INPUT",
        socket_type="NodeSocketMaterial",
    )
    mat_trace.description = "Matériau du tube de la trajectoire"
    mat_pos = nt.interface.new_socket(
        "Material · position", in_out="INPUT",
        socket_type="NodeSocketMaterial",
    )
    mat_pos.description = "Matériau de la flèche position"
    mat_vel = nt.interface.new_socket(
        "Material · vitesse", in_out="INPUT",
        socket_type="NodeSocketMaterial",
    )
    mat_vel.description = "Matériau de la flèche vitesse F'(t₀)"
    mat_acc = nt.interface.new_socket(
        "Material · accélération", in_out="INPUT",
        socket_type="NodeSocketMaterial",
    )
    mat_acc.description = "Matériau de la flèche accélération F''(t₀)"

    # Per-parameter scalar sliders (a, b, omega, …).
    for p in allowed_params:
        ps = nt.interface.new_socket(
            p, in_out="INPUT", socket_type="NodeSocketFloat",
        )
        ps.default_value = 1.0

    # --- build the node tree -------------------------------------------
    nb = compiler.NodeBuilder(nt)
    group_in = nb.add("NodeGroupInput", x=-1700, y=0)
    group_out = nb.add("NodeGroupOutput", x=2400, y=0)

    param_sockets = {p: group_in.outputs[p] for p in allowed_params}

    # 1) Trace curve.
    trace_curve = _build_vector_curve(
        nb,
        n_samples_sock=group_in.outputs["Resolution"],
        t_min_sock=group_in.outputs["t min"],
        t_max_sock=group_in.outputs["t max"],
        components=components,
        var_sockets=param_sockets,
        var_name=var_name,
        label="trace", y_offset=0,
    )
    trace_mesh = _build_tube(
        nb, curve_sock=trace_curve,
        radius_sock=group_in.outputs["Trace thickness"],
        x=900, y=0, label="trace",
    )
    # Material assignment for the trace tube. Placed immediately
    # downstream so the rest of the pipeline (the Join below) sees
    # a single Geometry socket exactly as before — the SetMaterial
    # is a transparent passthrough when the Material socket is empty.
    trace_set_mat = nb.add(
        "GeometryNodeSetMaterial",
        label="trace: material", x=1100, y=0,
    )
    nb.link(trace_mesh, trace_set_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Material · trace"],
             trace_set_mat.inputs["Material"])
    trace_mesh = trace_set_mat.outputs["Geometry"]

    # 2) Vectors at t₀ — both anchored using the t_0 group-input socket.
    #
    # We build *two* arrow instances:
    #
    #   (a) Position vector: orig = (0, 0, 0), ext = F(t₀).
    #       Goes from the world origin to the point on the trace; this
    #       is the canonical "vecteur position" of vector kinematics.
    #
    #   (b) Derivative vector: orig = F(t₀), ext = F(t₀) + F'(t₀).
    #       Anchored on the trace itself — the velocity tangent.
    #
    # Each is wrapped in a Geometry Switch driven by its visibility
    # boolean, so the user can show/hide them independently from the
    # modifier panel without rebuilding the tree.
    t0_sym_sockets = dict(param_sockets)
    t0_sym_sockets[var_name] = group_in.outputs["t_0"]

    # F(t₀) — used as the endpoint of the position vector AND as the
    # anchor of the derivative vector. One compilation, shared via the
    # SymPyCompiler's memo.
    pos_sock = compiler.compile_vector_components(
        nb, components, t0_sym_sockets,
        x=400, y=-700, label="F(t_0)",
    )
    # F'(t₀)
    fprime_at_t0_sock = compiler.compile_vector_components(
        nb, derivatives, t0_sym_sockets,
        x=400, y=-1000, label="F'(t_0)",
    )
    # ext_derivative = F(t₀) + F'(t₀) for the velocity arrow.
    add_node = nb.add("ShaderNodeVectorMath",
                       label="F(t_0) + F'(t_0)",
                       x=700, y=-850)
    add_node.operation = "ADD"
    nb.link(pos_sock, add_node.inputs[0])
    nb.link(fprime_at_t0_sock, add_node.inputs[1])
    ext_deriv_sock = add_node.outputs[0]

    # Origin (0,0,0) for the position arrow's orig socket. A
    # ShaderNodeCombineXYZ with three default-zero inputs is the
    # cleanest way to produce a constant Vector socket — alternatives
    # (Value nodes wired into a Combine, or a Vector input on the
    # group) work but add visual clutter.
    origin_node = nb.add("ShaderNodeCombineXYZ",
                          label="Origin (0,0,0)",
                          x=400, y=-450)
    # All three inputs default to 0.0; no need to set them explicitly.

    # Get the shared Vecteur node group instance once.
    vec_ng = vecteur.get_vecteur_node_group()

    # --- (a) Position arrow: origin → F(t₀) -------------------------
    pos_arrow = nb.add("GeometryNodeGroup",
                        label="Position arrow",
                        x=1000, y=-500)
    pos_arrow.node_tree = vec_ng
    try:
        nb.link(origin_node.outputs["Vector"], pos_arrow.inputs["orig"])
        nb.link(pos_sock, pos_arrow.inputs["ext"])
    except (KeyError, AttributeError):
        nb.link(origin_node.outputs[0], pos_arrow.inputs[0])
        nb.link(pos_sock, pos_arrow.inputs[1])
    pos_arrow_out = (pos_arrow.outputs["Geometry"]
                     if "Geometry" in pos_arrow.outputs
                     else pos_arrow.outputs[0])

    # Material assignment for the position arrow — same passthrough
    # pattern as the trace. Sits between the Vecteur group instance
    # and the visibility Switch, so when the arrow is hidden the
    # SetMaterial is bypassed by the Switch anyway.
    pos_mat = nb.add("GeometryNodeSetMaterial",
                      label="position: material",
                      x=1200, y=-500)
    nb.link(pos_arrow_out, pos_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Material · position"],
             pos_mat.inputs["Material"])
    pos_arrow_out = pos_mat.outputs["Geometry"]

    # Wrap in a Switch driven by Show position vector.
    pos_switch = nb.add("GeometryNodeSwitch",
                         label="Show position?",
                         x=1400, y=-500)
    pos_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show position vector"],
                 pos_switch.inputs["Switch"])
        nb.link(pos_arrow_out, pos_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show position vector"],
                 pos_switch.inputs[0])
        nb.link(pos_arrow_out, pos_switch.inputs[2])
    pos_switch_out = (pos_switch.outputs["Output"]
                       if "Output" in pos_switch.outputs
                       else pos_switch.outputs[0])

    # --- (b) Derivative arrow: F(t₀) → F(t₀) + F'(t₀) ---------------
    deriv_arrow = nb.add("GeometryNodeGroup",
                          label="Derivative arrow",
                          x=1000, y=-900)
    deriv_arrow.node_tree = vec_ng
    try:
        nb.link(pos_sock, deriv_arrow.inputs["orig"])
        nb.link(ext_deriv_sock, deriv_arrow.inputs["ext"])
    except (KeyError, AttributeError):
        nb.link(pos_sock, deriv_arrow.inputs[0])
        nb.link(ext_deriv_sock, deriv_arrow.inputs[1])
    deriv_arrow_out = (deriv_arrow.outputs["Geometry"]
                       if "Geometry" in deriv_arrow.outputs
                       else deriv_arrow.outputs[0])

    deriv_mat = nb.add("GeometryNodeSetMaterial",
                        label="vitesse: material",
                        x=1200, y=-900)
    nb.link(deriv_arrow_out, deriv_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Material · vitesse"],
             deriv_mat.inputs["Material"])
    deriv_arrow_out = deriv_mat.outputs["Geometry"]

    deriv_switch = nb.add("GeometryNodeSwitch",
                           label="Show derivative?",
                           x=1400, y=-900)
    deriv_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show derivative vector"],
                 deriv_switch.inputs["Switch"])
        nb.link(deriv_arrow_out, deriv_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show derivative vector"],
                 deriv_switch.inputs[0])
        nb.link(deriv_arrow_out, deriv_switch.inputs[2])
    deriv_switch_out = (deriv_switch.outputs["Output"]
                         if "Output" in deriv_switch.outputs
                         else deriv_switch.outputs[0])

    # --- (c) Acceleration arrow: F(t₀) → F(t₀) + F''(t₀) ------------
    # Anchored at the same point F(t₀) as the velocity arrow — this
    # is the standard physics convention: kinematic vectors live on
    # the trajectory, not at the world origin. Visually you'll see
    # the velocity and acceleration arrows fan out from the same
    # point on the trace, making their relative orientation directly
    # readable (e.g. perpendicular for uniform circular motion).
    fsecond_at_t0_sock = compiler.compile_vector_components(
        nb, second_derivatives, t0_sym_sockets,
        x=400, y=-1300, label="F''(t_0)",
    )
    # ext_acceleration = F(t₀) + F''(t₀).
    add_accel_node = nb.add("ShaderNodeVectorMath",
                             label="F(t_0) + F''(t_0)",
                             x=700, y=-1200)
    add_accel_node.operation = "ADD"
    nb.link(pos_sock, add_accel_node.inputs[0])
    nb.link(fsecond_at_t0_sock, add_accel_node.inputs[1])
    ext_accel_sock = add_accel_node.outputs[0]

    accel_arrow = nb.add("GeometryNodeGroup",
                          label="Acceleration arrow",
                          x=1000, y=-1200)
    accel_arrow.node_tree = vec_ng
    try:
        nb.link(pos_sock, accel_arrow.inputs["orig"])
        nb.link(ext_accel_sock, accel_arrow.inputs["ext"])
    except (KeyError, AttributeError):
        nb.link(pos_sock, accel_arrow.inputs[0])
        nb.link(ext_accel_sock, accel_arrow.inputs[1])
    accel_arrow_out = (accel_arrow.outputs["Geometry"]
                        if "Geometry" in accel_arrow.outputs
                        else accel_arrow.outputs[0])

    accel_mat = nb.add("GeometryNodeSetMaterial",
                        label="accélération: material",
                        x=1200, y=-1200)
    nb.link(accel_arrow_out, accel_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Material · accélération"],
             accel_mat.inputs["Material"])
    accel_arrow_out = accel_mat.outputs["Geometry"]

    accel_switch = nb.add("GeometryNodeSwitch",
                           label="Show acceleration?",
                           x=1400, y=-1200)
    accel_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show acceleration vector"],
                 accel_switch.inputs["Switch"])
        nb.link(accel_arrow_out, accel_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show acceleration vector"],
                 accel_switch.inputs[0])
        nb.link(accel_arrow_out, accel_switch.inputs[2])
    accel_switch_out = (accel_switch.outputs["Output"]
                         if "Output" in accel_switch.outputs
                         else accel_switch.outputs[0])

    # 3) Join trace tube + all three arrow geometries.
    join = nb.add("GeometryNodeJoinGeometry",
                   label="Final geometry", x=1900, y=-400)
    nb.link(trace_mesh, join.inputs["Geometry"])
    nb.link(pos_switch_out, join.inputs["Geometry"])
    nb.link(deriv_switch_out, join.inputs["Geometry"])
    nb.link(accel_switch_out, join.inputs["Geometry"])
    nb.link(join.outputs["Geometry"], group_out.inputs[0])

    # Metadata stash — symmetric with tree.make_realfn_tree, so a
    # future Edit operator can introspect.
    nt["realfn_kind"] = "vector"
    nt["realfn_expr"] = expr_str
    nt["realfn_var"] = var_name
    nt["realfn_params"] = list(allowed_params)
    # Store stringified components so the panel can show them.
    nt["realfn_components_text"] = [str(sp_.sstr(c)) for c in components]
    nt["realfn_components_latex"] = [str(sp_.latex(c)) for c in components]
    nt["realfn_derivatives_text"] = [str(sp_.sstr(d)) for d in derivatives]
    nt["realfn_derivatives_latex"] = [str(sp_.latex(d)) for d in derivatives]
    # Second derivative (acceleration in the kinematic interpretation).
    # Parallel layout: stored as length-3 arrays for x/y/z components.
    nt["realfn_second_derivatives_text"] = [
        str(sp_.sstr(d)) for d in second_derivatives
    ]
    nt["realfn_second_derivatives_latex"] = [
        str(sp_.latex(d)) for d in second_derivatives
    ]
    return nt
