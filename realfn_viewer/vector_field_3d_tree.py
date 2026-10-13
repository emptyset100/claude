"""
Geometry-Nodes tree builder for 3D vector fields V: R³ → R³.

The visualisation
-----------------
A regular NxNxN grid of sample points spans the box
[x_min, x_max] × [y_min, y_max] × [z_min, z_max]. At each point
(x, y, z) we draw a **3D arrow** going from (x, y, z) to
(x, y, z) + scale * V(x, y, z), using the bundled :mod:`vecteur`
node group (which renders shaft + cone given two endpoint Vectors).

The basepoint (x₀, y₀, z₀) gets:

* the **total arrow** V(x₀, y₀, z₀) emphasised by its own material,
* **three component arrows** along the coordinate axes — V_x·e_x,
  V_y·e_y, V_z·e_z — anchored at (x₀, y₀, z₀), the visual
  decomposition of V into its Cartesian components,
* a **numeric label** showing the norm ‖V(x₀, y₀, z₀)‖, formatted
  to two decimals via the bundled :mod:`ecrit` node group.

Two input modes
---------------
The caller chooses how the field is specified:

* ``"explicit"``: three scalar expressions V_x, V_y, V_z of (x, y, z);
* ``"from_potential"``: a single scalar expression ϕ(x, y, z); the
  field is then V = ∇ϕ, computed symbolically by SymPy at construction
  time.

Internally both modes converge to the same triplet of SymPy
expressions — once we have V_x, V_y, V_z it doesn't matter where they
came from. The mode is stashed in tree metadata so the panel can
display the right thing (a potential or three components) and so
presets round-trip faithfully.

Per-point arrows: attribute-baking + instancing
-----------------------------------------------
Originally implemented with a ``GeometryNodeForeachGeometryElement``
zone, but the Blender 5.1 Python API for adding ``input_items`` to
that zone is broken ("Cannot add socket to built-in node" — see
https://blenderartists.org/t/1561091). So we use the same pattern as
the scalar field 3D tree:

1. Bake ``V_x, V_y, V_z`` (combined as a ``rfn_V`` vector attribute)
   and the point position (``rfn_orig``) onto every grid point via
   ``StoreNamedAttribute``. Attribute-aware → forces field evaluation
   per point.

2. Instance a 2-vertex template (``Mesh Line``) on each point and
   realize. The realized vertices each inherit the host point's
   attributes (documented by Blender as "every vertex of the instance
   will hold the exact same copy of all the attributes that were in
   that instance before it was converted to a real mesh").

3. SetPosition per vertex based on Index parity: even = ``rfn_orig``,
   odd = ``rfn_orig + scale * rfn_V``. This realises the per-point
   arrow as a real edge whose endpoints carry the vector field's
   information.

4. Convert edges to a curve, run through Curve to Mesh with a thin
   circular profile (shaft cylinder) and instance cones at the head
   vertices aligned to ``rfn_V`` (arrow tip).

This pattern is fully supported by the Blender 4.3+/5.x API and
faster than For-Each zones for this kind of "per-point geometry
recipe" (documented in Blender's own foreach-zone manual).
"""

from __future__ import annotations

import bpy
import sympy as sp

from .compiler import NodeBuilder, SymPyCompiler
from . import ecrit, sympy_parser, vecteur, label_number
from . import domain_frame


# Distinct prefix so the active-modifier helper can identify this kind.
VECTOR_FIELD_3D_TREE_PREFIX = "REALFNVF3D_"


# --------------------------------------------------------------------------- #
# Grid helper (copied & lightly adapted from scalar_field_3d_tree)
# --------------------------------------------------------------------------- #
def _build_3d_grid(nb: NodeBuilder, *,
                    x_min_sock, x_max_sock,
                    y_min_sock, y_max_sock,
                    z_min_sock, z_max_sock,
                    res_x_sock, res_y_sock, res_z_sock,
                    x=-1400, y=0, label="3d grid"):
    """Build an NxNxN point cloud spanning the box.

    Same trick as in :mod:`scalar_field_3d_tree`: a 2D MeshGrid in XY,
    instanced with a Z-axis MeshLine, then Realize Instances to get a
    flat point cloud of N³ points. Cheaper than a For-Each loop just
    to lay out points (the For-Each comes in later, only when we
    actually need per-element processing).
    """
    grid_xy = nb.add("GeometryNodeMeshGrid",
                      label=f"{label}: XY grid", x=x, y=y)
    span_x = nb.math("SUBTRACT", x_max_sock, x_min_sock,
                      label="x_max - x_min", x=x + 100, y=y + 200)
    span_y = nb.math("SUBTRACT", y_max_sock, y_min_sock,
                      label="y_max - y_min", x=x + 100, y=y + 100)
    nb.link(span_x, grid_xy.inputs["Size X"])
    nb.link(span_y, grid_xy.inputs["Size Y"])
    nb.link(res_x_sock, grid_xy.inputs["Vertices X"])
    nb.link(res_y_sock, grid_xy.inputs["Vertices Y"])

    cx = nb.math("ADD", x_min_sock, x_max_sock, x=x + 100, y=y - 50)
    cx_half = nb.math("DIVIDE", cx, 2.0, x=x + 300, y=y - 50)
    cy = nb.math("ADD", y_min_sock, y_max_sock, x=x + 100, y=y - 150)
    cy_half = nb.math("DIVIDE", cy, 2.0, x=x + 300, y=y - 150)
    centre_xy = nb.combine_xyz(cx_half, cy_half, 0.0,
                                 label="XY centre",
                                 x=x + 500, y=y - 100)
    translate_xy = nb.add("GeometryNodeTransform",
                           label=f"{label}: centre XY",
                           x=x + 700, y=y)
    nb.link(grid_xy.outputs["Mesh"], translate_xy.inputs["Geometry"])
    nb.link(centre_xy, translate_xy.inputs["Translation"])

    xy_to_points = nb.add("GeometryNodeMeshToPoints",
                           label=f"{label}: XY points",
                           x=x + 900, y=y)
    nb.link(translate_xy.outputs["Geometry"],
             xy_to_points.inputs["Mesh"])

    z_line = nb.add("GeometryNodeMeshLine",
                     label=f"{label}: Z line", x=x + 700, y=y - 400)
    z_line.mode = "END_POINTS"
    nb.link(res_z_sock, z_line.inputs["Count"])
    z_start = nb.combine_xyz(0.0, 0.0, z_min_sock,
                              label="z_min point",
                              x=x + 500, y=y - 400)
    z_end = nb.combine_xyz(0.0, 0.0, z_max_sock,
                            label="z_max point",
                            x=x + 500, y=y - 500)
    try:
        nb.link(z_start, z_line.inputs["Start Location"])
        nb.link(z_end, z_line.inputs["End Location"])
    except KeyError:
        nb.link(z_start, z_line.inputs[2])
        nb.link(z_end, z_line.inputs[3])

    z_to_points = nb.add("GeometryNodeMeshToPoints",
                          label=f"{label}: Z points",
                          x=x + 900, y=y - 400)
    nb.link(z_line.outputs["Mesh"], z_to_points.inputs["Mesh"])

    inst = nb.add("GeometryNodeInstanceOnPoints",
                   label=f"{label}: 3D points",
                   x=x + 1100, y=y - 200)
    nb.link(xy_to_points.outputs["Points"], inst.inputs["Points"])
    nb.link(z_to_points.outputs["Points"], inst.inputs["Instance"])

    realize = nb.add("GeometryNodeRealizeInstances",
                      label=f"{label}: realize",
                      x=x + 1300, y=y - 200)
    nb.link(inst.outputs["Instances"], realize.inputs["Geometry"])

    return realize.outputs["Geometry"]


# --------------------------------------------------------------------------- #
# Per-point arrow generation — instancing + attributes pattern
# --------------------------------------------------------------------------- #
def _build_field_arrows(nb, *,
                         points_geom_sock,
                         components,
                         free_param_sockets,
                         scale_sock,
                         x_name="x", y_name="y", z_name="z",
                         x=0, y=-1400, label="arrows"):
    """Build a per-point arrow field without using a For-Each zone.

    Why no For-Each zone
    --------------------
    The Blender 5.1 Python API for adding input items to a
    ``GeometryNodeForeachGeometryElementInput`` is broken — the
    ``input_items`` collection doesn't exist on the input node, and
    workarounds via ``fe_out.input_items`` hit the "Cannot add socket
    to built-in node" error documented at
    https://blenderartists.org/t/1561091.

    So we use the same pattern as the scalar-field-3D tree: bake the
    per-point data we need as named attributes BEFORE any instancing
    or per-element operation, then exploit field/attribute semantics
    (which are well-supported by the API) to drive a single-instance
    template per point.

    Construction
    ------------
    1. Bake on each grid point:
         * ``rfn_orig``  (FLOAT_VECTOR) — the point's own position
         * ``rfn_V``     (FLOAT_VECTOR) — the field value V(x, y, z)
       Both bakes use ``StoreNamedAttribute`` (attribute-aware), so
       the position field and the SymPy-compiled V components are
       evaluated per-point of the grid.

    2. Instance a short ``Mesh Line`` (2 endpoints) on every point.

    3. Realize Instances. We now have 2N³ vertices and N³ edges; the
       ``rfn_orig`` / ``rfn_V`` attributes are propagated from each
       host point onto **both** vertices of its instance — the
       defining property of point-instance attribute propagation.

    4. ``Set Position`` per vertex:
         * even-indexed vertex (the "first" of the pair):
             position = ``rfn_orig``                       (arrow tail)
         * odd-indexed  vertex (the "second"):
             position = ``rfn_orig`` + ``scale * rfn_V``   (arrow head)
       Even/odd parity is computed from ``Index → Modulo 2``.

    5. Two geometries are produced:
         * **Shafts** — the edges, converted to a curve, then
           Curve to Mesh with a tiny circular profile → 3D cylinders.
         * **Tips**   — a cone instanced at the head vertex of each
           pair (selection: odd-index AND from the realized arrows),
           rotated to align its +Z axis with ``rfn_V`` via
           Align Euler to Vector. This gives the arrow its
           directional "point".

    Joined together, they form a recognisable 3D arrow field.

    Returns the Geometry socket carrying the full arrow mesh.
    """
    # --- Step 1a: bake position as 'rfn_orig' -----------------------------
    pos_field = nb.add("GeometryNodeInputPosition",
                        label="position field",
                        x=x + 100, y=y + 200)
    store_orig = nb.add("GeometryNodeStoreNamedAttribute",
                         label="bake rfn_orig",
                         x=x + 300, y=y + 100)
    store_orig.domain = "POINT"
    store_orig.data_type = "FLOAT_VECTOR"
    try:
        store_orig.inputs["Name"].default_value = "rfn_orig"
    except (KeyError, TypeError):
        store_orig.inputs[2].default_value = "rfn_orig"
    nb.link(points_geom_sock, store_orig.inputs["Geometry"])
    # StoreNamedAttribute's "Value" input has different indices
    # depending on data_type — defensive name-based linking with
    # positional fallback.
    try:
        nb.link(pos_field.outputs["Position"], store_orig.inputs["Value"])
    except KeyError:
        # The "Value" socket may appear under variants like "Value Vector"
        # depending on the data_type subselection.
        linked = False
        for cand in ("Value", "Value_Vector", "Vector"):
            try:
                nb.link(pos_field.outputs["Position"], store_orig.inputs[cand])
                linked = True
                break
            except KeyError:
                continue
        if not linked:
            # Positional fallback: inputs are typically
            # [Geometry, Selection, Name, Value_Vector, ...]
            nb.link(pos_field.outputs["Position"], store_orig.inputs[3])

    # --- Step 1b: bake V(x, y, z) as 'rfn_V' ------------------------------
    # SymPy → Math nodes for each of V_x, V_y, V_z, then CombineXYZ.
    sep = nb.add("ShaderNodeSeparateXYZ",
                  label="separate xyz (for V)",
                  x=x + 100, y=y - 100)
    nb.link(pos_field.outputs["Position"], sep.inputs["Vector"])
    var_sockets = {
        x_name: sep.outputs["X"],
        y_name: sep.outputs["Y"],
        z_name: sep.outputs["Z"],
        **free_param_sockets,
    }
    compiler = SymPyCompiler(nb, var_sockets)
    Vx_sock = compiler.compile(components[0])
    Vy_sock = compiler.compile(components[1])
    Vz_sock = compiler.compile(components[2])
    V_combined = nb.combine_xyz(Vx_sock, Vy_sock, Vz_sock,
                                  label="V(x,y,z) → vector",
                                  x=x + 500, y=y - 100)

    store_V = nb.add("GeometryNodeStoreNamedAttribute",
                      label="bake rfn_V",
                      x=x + 700, y=y)
    store_V.domain = "POINT"
    store_V.data_type = "FLOAT_VECTOR"
    try:
        store_V.inputs["Name"].default_value = "rfn_V"
    except (KeyError, TypeError):
        store_V.inputs[2].default_value = "rfn_V"
    nb.link(store_orig.outputs["Geometry"], store_V.inputs["Geometry"])
    try:
        nb.link(V_combined, store_V.inputs["Value"])
    except KeyError:
        linked = False
        for cand in ("Value", "Value_Vector", "Vector"):
            try:
                nb.link(V_combined, store_V.inputs[cand])
                linked = True
                break
            except KeyError:
                continue
        if not linked:
            nb.link(V_combined, store_V.inputs[3])

    baked_geom_sock = store_V.outputs["Geometry"]

    # --- Step 2: template = MeshLine of 2 points along +Z ----------------
    # Two endpoints: (0,0,0) → (0,0,1). The actual orientation is
    # rewritten in Step 4 via SetPosition; this template is just a
    # vehicle for "2 vertices joined by 1 edge".
    line_template = nb.add("GeometryNodeMeshLine",
                            label="arrow template (2 pts)",
                            x=x + 900, y=y - 400)
    line_template.mode = "END_POINTS"
    line_template.inputs["Count"].default_value = 2
    try:
        line_template.inputs["Start Location"].default_value = (0.0, 0.0, 0.0)
        line_template.inputs["End Location"].default_value = (0.0, 0.0, 1.0)
    except KeyError:
        # Positional fallback for older API
        line_template.inputs[2].default_value = (0.0, 0.0, 0.0)
        line_template.inputs[3].default_value = (0.0, 0.0, 1.0)

    # Instance the template on every grid point.
    iop = nb.add("GeometryNodeInstanceOnPoints",
                  label="arrows: instance template",
                  x=x + 1100, y=y)
    nb.link(baked_geom_sock, iop.inputs["Points"])
    nb.link(line_template.outputs["Mesh"], iop.inputs["Instance"])

    # Realize so we get a flat mesh with the propagated attributes.
    realize = nb.add("GeometryNodeRealizeInstances",
                      label="arrows: realize",
                      x=x + 1300, y=y)
    nb.link(iop.outputs["Instances"], realize.inputs["Geometry"])

    # --- Step 3: read back propagated attributes -------------------------
    read_orig = nb.add("GeometryNodeInputNamedAttribute",
                        label="read rfn_orig",
                        x=x + 1100, y=y + 300)
    read_orig.data_type = "FLOAT_VECTOR"
    try:
        read_orig.inputs["Name"].default_value = "rfn_orig"
    except (KeyError, TypeError):
        read_orig.inputs[0].default_value = "rfn_orig"

    read_V = nb.add("GeometryNodeInputNamedAttribute",
                     label="read rfn_V",
                     x=x + 1100, y=y + 150)
    read_V.data_type = "FLOAT_VECTOR"
    try:
        read_V.inputs["Name"].default_value = "rfn_V"
    except (KeyError, TypeError):
        read_V.inputs[0].default_value = "rfn_V"

    # --- Step 4: per-vertex position based on index parity ---------------
    # Even index → orig ; Odd index → orig + scale * V
    index_node = nb.add("GeometryNodeInputIndex",
                         label="vertex index",
                         x=x + 1300, y=y + 500)
    # Modulo 2 to get parity.
    mod2 = nb.math("MODULO", index_node.outputs["Index"], 2,
                    label="index % 2",
                    x=x + 1500, y=y + 500)
    # parity 1 → odd (head), parity 0 → even (tail). Use as a Bool
    # for the Switch selecting between "orig" and "orig + s·V".
    # We need a Vector socket for SetPosition.Offset, but it's
    # simpler to drive the final vertex position via SetPosition's
    # Position input (absolute position, not offset).
    # Build offset_V = scale * rfn_V (a vector).
    scale_vec_v = nb.add("ShaderNodeVectorMath",
                          label="scale * V", x=x + 1500, y=y + 200)
    scale_vec_v.operation = "SCALE"
    try:
        nb.link(read_V.outputs["Attribute"], scale_vec_v.inputs[0])
    except KeyError:
        nb.link(read_V.outputs[0], scale_vec_v.inputs[0])
    # SCALE mode's scale input is the third socket ("Scale").
    try:
        nb.link(scale_sock, scale_vec_v.inputs["Scale"])
    except KeyError:
        nb.link(scale_sock, scale_vec_v.inputs[3])

    # ext = orig + scale_V
    ext_vec = nb.add("ShaderNodeVectorMath",
                      label="orig + s·V", x=x + 1700, y=y + 300)
    ext_vec.operation = "ADD"
    try:
        nb.link(read_orig.outputs["Attribute"], ext_vec.inputs[0])
    except KeyError:
        nb.link(read_orig.outputs[0], ext_vec.inputs[0])
    nb.link(scale_vec_v.outputs["Vector"], ext_vec.inputs[1])

    # Select between orig and ext based on parity. Use a Switch node
    # in Vector mode: False (parity=0, even) → orig ; True (parity=1)
    # → ext.
    # First convert parity (float) to bool via a Compare > 0.5.
    cmp = nb.add("FunctionNodeCompare",
                  label="parity > 0.5",
                  x=x + 1700, y=y + 500)
    cmp.data_type = "FLOAT"
    cmp.operation = "GREATER_THAN"
    nb.link(mod2, cmp.inputs[0])
    try:
        cmp.inputs[1].default_value = 0.5
    except (TypeError, AttributeError):
        pass

    # Vector switch.
    pos_switch = nb.add("GeometryNodeSwitch",
                         label="position by parity",
                         x=x + 1900, y=y + 400)
    pos_switch.input_type = "VECTOR"
    try:
        nb.link(cmp.outputs["Result"], pos_switch.inputs["Switch"])
    except KeyError:
        nb.link(cmp.outputs[0], pos_switch.inputs[0])
    # False → orig, True → ext. Find the False/True vector slots by
    # type and parity (Switch sockets vary by version).
    # Strategy: link the second-to-last vector input to False (orig),
    # last vector input to True (ext). In practice the GeometryNodeSwitch
    # has named "False"/"True" inputs in Blender 4.x+.
    try:
        nb.link(read_orig.outputs["Attribute"], pos_switch.inputs["False"])
        nb.link(ext_vec.outputs["Vector"],       pos_switch.inputs["True"])
    except KeyError:
        # Defensive: find the two Vector inputs by iteration.
        vec_inputs = [s for s in pos_switch.inputs
                       if s.name in ("False", "True")]
        if len(vec_inputs) == 2:
            nb.link(read_orig.outputs[0], vec_inputs[0])
            nb.link(ext_vec.outputs[0],   vec_inputs[1])
        else:
            # Last resort: positional. Vector Switch typically has
            # Switch + False + True with vector sockets.
            nb.link(read_orig.outputs[0], pos_switch.inputs[2])
            nb.link(ext_vec.outputs[0],   pos_switch.inputs[3])

    # Apply the position.
    set_pos = nb.add("GeometryNodeSetPosition",
                      label="set vertex pos",
                      x=x + 2100, y=y)
    nb.link(realize.outputs["Geometry"], set_pos.inputs["Geometry"])
    try:
        nb.link(pos_switch.outputs["Output"], set_pos.inputs["Position"])
    except KeyError:
        nb.link(pos_switch.outputs[0], set_pos.inputs["Position"])

    # --- Step 5a: shaft mesh = curve from edges + tiny circular profile ---
    # Convert the edges to a curve.
    mesh_to_curve = nb.add("GeometryNodeMeshToCurve",
                             label="edges → curve",
                             x=x + 2300, y=y - 100)
    nb.link(set_pos.outputs["Geometry"], mesh_to_curve.inputs["Mesh"])

    # Tiny circular profile (radius proportional to scale, capped low).
    profile = nb.add("GeometryNodeCurvePrimitiveCircle",
                      label="shaft profile",
                      x=x + 2300, y=y - 300)
    profile.mode = "RADIUS"
    try:
        profile.inputs["Resolution"].default_value = 8
        profile.inputs["Radius"].default_value = 0.015
    except KeyError:
        # Older API: positional access.
        profile.inputs[0].default_value = 8

    # Curve to mesh — generates shaft cylinders.
    curve_to_mesh = nb.add("GeometryNodeCurveToMesh",
                            label="shaft mesh",
                            x=x + 2500, y=y - 100)
    nb.link(mesh_to_curve.outputs["Curve"], curve_to_mesh.inputs["Curve"])
    nb.link(profile.outputs["Curve"], curve_to_mesh.inputs["Profile Curve"])

    shafts_geom = curve_to_mesh.outputs["Mesh"]

    # --- Step 5b: tips = cones instanced on head vertices, aligned with V ---
    # Selection of head vertices: parity == 1 AND on the realized arrow
    # geometry. We re-use mod2 and Compare > 0.5 already built.
    #
    # To instance only on head vertices, use Points + Selection on
    # InstanceOnPoints with the head selection.
    cone = nb.add("GeometryNodeMeshCone",
                   label="cone (arrow tip)",
                   x=x + 2300, y=y - 600)
    try:
        cone.inputs["Vertices"].default_value = 8
        cone.inputs["Radius Bottom"].default_value = 0.04
        cone.inputs["Radius Top"].default_value = 0.0
        cone.inputs["Depth"].default_value = 0.08
    except (KeyError, TypeError):
        pass

    # Rotation: align +Z with rfn_V.
    align_rot = nb.add("FunctionNodeAlignEulerToVector",
                        label="align +Z with V",
                        x=x + 2300, y=y - 800)
    align_rot.axis = "Z"
    try:
        nb.link(read_V.outputs["Attribute"], align_rot.inputs["Vector"])
    except KeyError:
        nb.link(read_V.outputs[0], align_rot.inputs["Vector"])

    # Instance cone on points, selecting head vertices.
    tip_iop = nb.add("GeometryNodeInstanceOnPoints",
                      label="cones on heads",
                      x=x + 2500, y=y - 700)
    nb.link(set_pos.outputs["Geometry"], tip_iop.inputs["Points"])
    nb.link(cone.outputs["Mesh"],         tip_iop.inputs["Instance"])
    nb.link(cmp.outputs["Result"],        tip_iop.inputs["Selection"])
    try:
        nb.link(align_rot.outputs["Rotation"], tip_iop.inputs["Rotation"])
    except KeyError:
        nb.link(align_rot.outputs[0], tip_iop.inputs["Rotation"])

    tips_realize = nb.add("GeometryNodeRealizeInstances",
                           label="tips: realize",
                           x=x + 2700, y=y - 700)
    nb.link(tip_iop.outputs["Instances"], tips_realize.inputs["Geometry"])
    tips_geom = tips_realize.outputs["Geometry"]

    # --- Final join: shafts + tips --------------------------------------
    join = nb.add("GeometryNodeJoinGeometry",
                   label="arrows: shafts + tips",
                   x=x + 2900, y=y - 300)
    nb.link(shafts_geom, join.inputs["Geometry"])
    nb.link(tips_geom,   join.inputs["Geometry"])

    return join.outputs["Geometry"]


def make_vector_field_3d_tree(components_source=None,
                                *,
                                potential_source: str | None = None,
                                x_name: str = "x",
                                y_name: str = "y",
                                z_name: str = "z",
                                allowed_params: tuple[str, ...] = (),
                                x_default_range: tuple[float, float] = (-1.5, 1.5),
                                y_default_range: tuple[float, float] = (-1.5, 1.5),
                                z_default_range: tuple[float, float] = (-1.5, 1.5),
                                x0_default: float = 0.5,
                                y0_default: float = 0.5,
                                z0_default: float = 0.5,
                                key_suffix: str = ""):
    """Build a Geometry-Nodes tree visualising a 3D vector field.

    Caller specifies the field via *exactly one* of two paths:

    * ``components_source = (V_x, V_y, V_z)`` — three SymPy-compatible
      source strings. Mode is recorded as ``"explicit"``.
    * ``potential_source = "phi(x,y,z)"`` — a single scalar source
      string; the field is taken as ``V = ∇phi``. Mode is recorded
      as ``"from_potential"``.

    Passing neither or both raises ``ValueError``.

    Sockets exposed on the modifier
    -------------------------------
    * Grid: ``Resolution X/Y/Z`` (Int, default 4, max 10),
      ``x/y/z min/max`` (Float).
    * Basepoint: ``x_0 / y_0 / z_0`` (Float).
    * Scale: ``Arrow scale`` (Float) — global multiplier for vector
      lengths; raise it when V is "small", lower it when arrows
      overlap.
    * Materials: ``Arrow material``, ``Marker material``,
      ``Basepoint arrow material``, ``Component arrow material``,
      ``Label material``.
    * Visibility: ``Show component arrows`` (Bool), ``Show basepoint
      norm label`` (Bool).
    * Marker: ``Marker size``, ``Label size``, ``Label vertical offset``.
    * One float socket per free parameter.

    Geometry output: union of (i) the grid of arrows, (ii) the
    basepoint marker, (iii) the emphasised basepoint arrow, (iv) the
    three component arrows, (v) the norm label.
    """
    sp_ = sympy_parser._sympy()

    # ----- Choose mode, derive components --------------------------------
    if components_source is None and potential_source is None:
        raise ValueError(
            "Spécifier soit components_source (3 expressions), "
            "soit potential_source (1 expression scalaire ϕ)"
        )
    if components_source is not None and potential_source is not None:
        raise ValueError(
            "Choisir un seul mode : components_source ou potential_source, "
            "pas les deux"
        )

    if components_source is not None:
        mode = "explicit"
        components = sympy_parser.parse_vector_field_3d_components(
            components_source, x_name=x_name, y_name=y_name, z_name=z_name,
        )
        # Store the *source* strings so the preset / panel can show the
        # exact text the user typed (rather than SymPy's canonical form,
        # which may differ slightly).
        components_source_clean = tuple(s.strip() for s in components_source)
    else:
        mode = "from_potential"
        phi_expr = sympy_parser.parse_scalar_field_3d_expression(
            potential_source, x_name=x_name, y_name=y_name, z_name=z_name,
        )
        components = sympy_parser.scalar_field_3d_gradient(
            phi_expr, x_name=x_name, y_name=y_name, z_name=z_name,
        )
        components_source_clean = tuple(
            str(sp_.sstr(c)) for c in components
        )

    # Validate free symbols.
    all_free = set()
    for c in components:
        all_free |= c.free_symbols
    known = ({x_name, y_name, z_name, "x_0", "y_0", "z_0"}
             | set(allowed_params))
    unknown = sorted(s.name for s in all_free if s.name not in known)
    if unknown:
        raise ValueError(
            f"Symboles non autorisés : {', '.join(unknown)}. "
            f"Autorisés : {sorted(known)}"
        )

    # Compute basepoint-substituted components (function of x_0, y_0, z_0).
    x_sym = sp_.Symbol(x_name, real=True)
    y_sym = sp_.Symbol(y_name, real=True)
    z_sym = sp_.Symbol(z_name, real=True)
    x0_sym = sp_.Symbol("x_0", real=True)
    y0_sym = sp_.Symbol("y_0", real=True)
    z0_sym = sp_.Symbol("z_0", real=True)
    subs = {x_sym: x0_sym, y_sym: y0_sym, z_sym: z0_sym}
    V0_components = tuple(c.subs(subs) for c in components)

    # Divergence and curl for panel display only (computed symbolically
    # at construction time, no extra runtime cost).
    div_expr = sympy_parser.vector_field_3d_divergence(
        components, x_name=x_name, y_name=y_name, z_name=z_name,
    )
    curl_expr = sympy_parser.vector_field_3d_curl(
        components, x_name=x_name, y_name=y_name, z_name=z_name,
    )

    # ----- Create tree + interface --------------------------------------
    nt = bpy.data.node_groups.new(
        f"{VECTOR_FIELD_3D_TREE_PREFIX}{key_suffix or 'fn'}",
        "GeometryNodeTree",
    )
    nt.interface.new_socket(
        "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry",
    )

    def add_int(name, default, mn=2, mx=10, desc=""):
        s = nt.interface.new_socket(name, in_out="INPUT",
                                     socket_type="NodeSocketInt")
        s.default_value = default
        s.min_value = mn
        s.max_value = mx
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

    add_int("Resolution X", 4, mn=2, mx=10,
             desc="Subdivisions de la grille selon x (max 10 par axe ; "
                  "10³ = 1000 flèches ≈ limite d'interactivité)")
    add_int("Resolution Y", 4, mn=2, mx=10)
    add_int("Resolution Z", 4, mn=2, mx=10)
    add_float("x min", float(x_default_range[0]))
    add_float("x max", float(x_default_range[1]))
    add_float("y min", float(y_default_range[0]))
    add_float("y max", float(y_default_range[1]))
    add_float("z min", float(z_default_range[0]))
    add_float("z max", float(z_default_range[1]))
    add_float("x_0", float(x0_default))
    add_float("y_0", float(y0_default))
    add_float("z_0", float(z0_default))
    add_bool("Show arrows", True,
              desc="Affiche la grille de flèches V sur tous les "
                   "échantillons. Décocher pour ne garder que le "
                   "point d'ancrage et ses flèches (utile sur grilles "
                   "denses ou pour focaliser l'attention)")
    add_float("Arrow scale", 0.3, mn=0.0,
               desc="Facteur multiplicatif appliqué à V pour obtenir la "
                    "longueur des flèches. Augmenter si les flèches sont "
                    "trop courtes ; diminuer si elles se chevauchent")
    add_mat("Arrow material",
             desc="Matériau des flèches du champ (la grille entière)")
    add_float("Marker size", 0.08, mn=0.0,
               desc="Rayon de la sphère qui marque le point d'ancrage")
    add_mat("Marker material")
    add_mat("Basepoint arrow material",
             desc="Matériau de la flèche V(x₀,y₀,z₀) "
                  "(mise en évidence du vecteur au point d'ancrage)")
    add_bool("Show component arrows", True,
              desc="Affiche les trois flèches V_x·e_x, V_y·e_y, V_z·e_z "
                   "décomposant V(x₀,y₀,z₀) selon les axes")
    add_mat("Component arrow material",
             desc="Matériau des trois flèches décomposées au point d'ancrage")
    add_bool("Show basepoint norm label", True,
              desc="Affiche un label numérique ‖V(x₀,y₀,z₀)‖ "
                   "au point d'ancrage")
    add_float("Label size", 0.15, mn=0.0)
    add_float("Label vertical offset", 0.20)
    add_mat("Label material")
    # Per-point numeric labels of the field magnitude ‖V(x, y, z)‖,
    # rendered with the shared LabelNumber glyph-atlas node group
    # (same machinery as the 3D scalar field's per-point labels).
    add_bool("Show norm labels", False,
              desc="Affiche la norme ‖V(x,y,z)‖ à côté de chaque point "
                   "échantillonné (format DD.DD). Coûteux à haute "
                   "résolution — utiliser le pas ci-dessous")
    add_int("Norm label stride", 2, mn=1, mx=20,
             desc="Pas d'échantillonnage des étiquettes de norme : "
                  "1 = tous les points, 2 = un sur deux…")
    add_float("Norm label size", 0.08, mn=0.0,
               desc="Hauteur des chiffres des étiquettes de norme")
    add_float("Norm label offset", 0.10,
               desc="Hauteur des étiquettes au-dessus de leur point "
                    "(décalage vertical, le nombre est centré sur le "
                    "point)")
    add_int("Norm label decimals", 2, mn=0, mx=4,
             desc="Nombre de décimales affichées par les étiquettes "
                  "de norme (0 = entiers)")
    add_bool("Norm label vertical", False,
              desc="Redresse les étiquettes de norme à la verticale, "
                   "face à la vue de face (Numpad 1). Décoché : à "
                   "plat, lisibles depuis la vue de dessus")
    add_int("Norm label max points", 2000, mn=1, mx=100000,
             desc="Garde-fou : au-delà de ce nombre de points de "
                  "grille, aucune étiquette de norme n'est générée")
    add_mat("Norm label material",
             desc="Matériau des étiquettes de norme par-point")
    # --- Domain frame + graduated axes (pedagogical aids) ---
    add_bool("Show domain frame", True,
              desc="Affiche les 12 arêtes de la boîte du domaine en "
                   "tubes fins")
    add_float("Frame thickness", 0.01, mn=0.0,
               desc="Rayon des tubes du cadre du domaine")
    add_mat("Frame material",
             desc="Matériau du cadre du domaine")
    add_bool("Show graduated axes", False,
              desc="Affiche des graduations numérotées le long de "
                   "trois arêtes de la boîte (axes x, y, z)")
    add_float("Axis label size", 0.07, mn=0.0,
               desc="Hauteur des chiffres des graduations d'axes")
    add_int("Axis label decimals", 1, mn=0, mx=4,
             desc="Décimales des graduations d'axes")
    add_mat("Axis label material",
             desc="Matériau des graduations d'axes")
    for p in allowed_params:
        ps = nt.interface.new_socket(
            p, in_out="INPUT", socket_type="NodeSocketFloat",
        )
        ps.default_value = 1.0

    # ----- Build graph --------------------------------------------------
    nb = NodeBuilder(nt)
    group_in = nb.add("NodeGroupInput", x=-2200, y=0)
    group_out = nb.add("NodeGroupOutput", x=3600, y=0)

    free_param_sockets = {p: group_in.outputs[p] for p in allowed_params}
    basepoint_extra = dict(free_param_sockets)
    basepoint_extra["x_0"] = group_in.outputs["x_0"]
    basepoint_extra["y_0"] = group_in.outputs["y_0"]
    basepoint_extra["z_0"] = group_in.outputs["z_0"]

    # 1) Sample point cloud.
    points_geom = _build_3d_grid(
        nb,
        x_min_sock=group_in.outputs["x min"],
        x_max_sock=group_in.outputs["x max"],
        y_min_sock=group_in.outputs["y min"],
        y_max_sock=group_in.outputs["y max"],
        z_min_sock=group_in.outputs["z min"],
        z_max_sock=group_in.outputs["z max"],
        res_x_sock=group_in.outputs["Resolution X"],
        res_y_sock=group_in.outputs["Resolution Y"],
        res_z_sock=group_in.outputs["Resolution Z"],
    )

    # 2) Per-point arrows via For-Each.
    arrows_geom = _build_field_arrows(
        nb,
        points_geom_sock=points_geom,
        components=components,
        free_param_sockets=free_param_sockets,
        scale_sock=group_in.outputs["Arrow scale"],
        x_name=x_name, y_name=y_name, z_name=z_name,
    )
    arrows_mat = nb.add("GeometryNodeSetMaterial",
                         label="grid arrows: material",
                         x=2400, y=-1400)
    nb.link(arrows_geom, arrows_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Arrow material"],
             arrows_mat.inputs["Material"])

    # 2.5) Per-point norm labels via the shared LabelNumber group.
    # ‖V‖ = √(V_x² + V_y² + V_z²) compiled as a field driven by
    # InputPosition, displayed at each strided grid point.
    norm_expr = sp.sqrt(components[0]**2
                         + components[1]**2
                         + components[2]**2)
    nlbl_pos = nb.add("GeometryNodeInputPosition",
                       label="norm label: pos", x=-300, y=-2400)
    nlbl_sep = nb.add("ShaderNodeSeparateXYZ",
                       label="norm label: separate", x=-100, y=-2400)
    nb.link(nlbl_pos.outputs["Position"], nlbl_sep.inputs["Vector"])
    nlbl_compiler = SymPyCompiler(nb, {
        x_name: nlbl_sep.outputs["X"],
        y_name: nlbl_sep.outputs["Y"],
        z_name: nlbl_sep.outputs["Z"],
        **free_param_sockets,
    })
    nlbl_value = nlbl_compiler.compile(norm_expr)

    nlbl_ng = label_number.get_label_number_node_group()
    nlbl_group = nb.add("GeometryNodeGroup",
                         label="LabelNumber(‖V‖)", x=400, y=-2300)
    nlbl_group.node_tree = nlbl_ng
    nb.link(points_geom, nlbl_group.inputs["Points"])
    # ``nlbl_value`` may be a NodeSocket or, when ‖V‖ is constant (e.g.
    # the "Champ constant V = e_z" preset), a plain float. ``_to_socket``
    # links sockets and writes floats to ``default_value`` — a bare
    # ``link()`` would raise TypeError on the float case.
    nb._to_socket(nlbl_value, nlbl_group.inputs["Value"])
    nb.link(group_in.outputs["Norm label size"],
             nlbl_group.inputs["Size"])
    nb.link(group_in.outputs["Norm label stride"],
             nlbl_group.inputs["Stride"])
    nb.link(group_in.outputs["Norm label decimals"],
             nlbl_group.inputs["Decimals"])
    nb.link(group_in.outputs["Norm label vertical"],
             nlbl_group.inputs["Face front"])
    nb.link(group_in.outputs["Norm label max points"],
             nlbl_group.inputs["Max points"])
    nlbl_off_vec = nb.combine_xyz(0.0, 0.0,
                                    group_in.outputs["Norm label offset"],
                                    label="norm label offset vec",
                                    x=200, y=-2450)
    nb.link(nlbl_off_vec, nlbl_group.inputs["Offset"])

    nlbl_mat = nb.add("GeometryNodeSetMaterial",
                       label="norm labels: material", x=700, y=-2300)
    nb.link(nlbl_group.outputs["Geometry"], nlbl_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Norm label material"],
             nlbl_mat.inputs["Material"])

    nlbl_switch = nb.add("GeometryNodeSwitch",
                          label="show norm labels?", x=950, y=-2300)
    nlbl_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show norm labels"],
                 nlbl_switch.inputs["Switch"])
        nb.link(nlbl_mat.outputs["Geometry"], nlbl_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show norm labels"],
                 nlbl_switch.inputs[0])
        nb.link(nlbl_mat.outputs["Geometry"], nlbl_switch.inputs[2])
    nlbl_out = (nlbl_switch.outputs["Output"]
                if "Output" in nlbl_switch.outputs
                else nlbl_switch.outputs[0])

    # 3) Basepoint marker — small sphere at (x₀, y₀, z₀).
    marker_pos = nb.combine_xyz(group_in.outputs["x_0"],
                                  group_in.outputs["y_0"],
                                  group_in.outputs["z_0"],
                                  label="basepoint",
                                  x=400, y=600)
    sphere = nb.add("GeometryNodeMeshUVSphere",
                     label="marker sphere",
                     x=600, y=600)
    sphere.inputs["Segments"].default_value = 16
    sphere.inputs["Rings"].default_value = 8
    nb.link(group_in.outputs["Marker size"], sphere.inputs["Radius"])
    place_marker = nb.add("GeometryNodeSetPosition",
                           label="place marker", x=800, y=600)
    nb.link(sphere.outputs["Mesh"], place_marker.inputs["Geometry"])
    nb.link(marker_pos, place_marker.inputs["Offset"])
    marker_mat = nb.add("GeometryNodeSetMaterial",
                         label="marker: material", x=1000, y=600)
    nb.link(place_marker.outputs["Geometry"], marker_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Marker material"],
             marker_mat.inputs["Material"])

    # 4) Basepoint total arrow — compile V₀ = V(x₀,y₀,z₀), draw arrow
    # from (x₀, y₀, z₀) to (x₀+s·V₀_x, y₀+s·V₀_y, z₀+s·V₀_z).
    base_compiler = SymPyCompiler(nb, basepoint_extra)
    V0x = base_compiler.compile(V0_components[0])
    V0y = base_compiler.compile(V0_components[1])
    V0z = base_compiler.compile(V0_components[2])
    base_scale = group_in.outputs["Arrow scale"]
    base_ext_x = nb.math("ADD", group_in.outputs["x_0"],
                          nb.math("MULTIPLY", base_scale, V0x,
                                   x=400, y=1000),
                          x=600, y=1000)
    base_ext_y = nb.math("ADD", group_in.outputs["y_0"],
                          nb.math("MULTIPLY", base_scale, V0y,
                                   x=400, y=900),
                          x=600, y=900)
    base_ext_z = nb.math("ADD", group_in.outputs["z_0"],
                          nb.math("MULTIPLY", base_scale, V0z,
                                   x=400, y=800),
                          x=600, y=800)
    base_orig_vec = nb.combine_xyz(group_in.outputs["x_0"],
                                     group_in.outputs["y_0"],
                                     group_in.outputs["z_0"],
                                     label="V(p_0) orig",
                                     x=800, y=1100)
    base_ext_vec = nb.combine_xyz(base_ext_x, base_ext_y, base_ext_z,
                                    label="V(p_0) ext",
                                    x=800, y=900)
    base_arrow = nb.add("GeometryNodeGroup",
                         label="Vecteur — V(p_0)", x=1100, y=1000)
    base_arrow.node_tree = vecteur.get_vecteur_node_group()
    try:
        nb.link(base_orig_vec, base_arrow.inputs["orig"])
        nb.link(base_ext_vec, base_arrow.inputs["ext"])
    except KeyError:
        nb.link(base_orig_vec, base_arrow.inputs[0])
        nb.link(base_ext_vec, base_arrow.inputs[1])
    base_arrow_mat = nb.add("GeometryNodeSetMaterial",
                             label="V(p_0): material", x=1400, y=1000)
    nb.link(base_arrow.outputs[0], base_arrow_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Basepoint arrow material"],
             base_arrow_mat.inputs["Material"])

    # 5) Three component arrows at the basepoint:
    #    V_x·e_x  →  (x₀, y₀, z₀) → (x₀+s·V₀_x, y₀, z₀)
    #    V_y·e_y  →  (x₀, y₀, z₀) → (x₀, y₀+s·V₀_y, z₀)
    #    V_z·e_z  →  (x₀, y₀, z₀) → (x₀, y₀, z₀+s·V₀_z)
    # Each is a separate Vecteur instance. They visualise the
    # decomposition of V₀ into its Cartesian components.
    def _make_component_arrow(comp_axis, v_sock, x_pos, y_pos):
        """Build one component arrow. comp_axis ∈ {'x', 'y', 'z'}."""
        # ext = orig with the chosen axis replaced by axis_0 + s · V_axis.
        # We reuse base_ext_x/y/z for the chosen axis and pass-through
        # the others from x_0/y_0/z_0.
        s_v = nb.math("MULTIPLY", base_scale, v_sock,
                       label=f"s·V_{comp_axis}",
                       x=x_pos, y=y_pos + 100)
        if comp_axis == "x":
            ex = nb.math("ADD", group_in.outputs["x_0"], s_v,
                          x=x_pos + 200, y=y_pos + 100)
            ey, ez = group_in.outputs["y_0"], group_in.outputs["z_0"]
        elif comp_axis == "y":
            ey = nb.math("ADD", group_in.outputs["y_0"], s_v,
                          x=x_pos + 200, y=y_pos + 100)
            ex, ez = group_in.outputs["x_0"], group_in.outputs["z_0"]
        else:
            ez = nb.math("ADD", group_in.outputs["z_0"], s_v,
                          x=x_pos + 200, y=y_pos + 100)
            ex, ey = group_in.outputs["x_0"], group_in.outputs["y_0"]
        orig_vec = nb.combine_xyz(group_in.outputs["x_0"],
                                    group_in.outputs["y_0"],
                                    group_in.outputs["z_0"],
                                    label=f"V_{comp_axis}·e_{comp_axis} orig",
                                    x=x_pos + 400, y=y_pos + 50)
        ext_vec = nb.combine_xyz(ex, ey, ez,
                                   label=f"V_{comp_axis}·e_{comp_axis} ext",
                                   x=x_pos + 400, y=y_pos - 50)
        arrow = nb.add("GeometryNodeGroup",
                        label=f"Vecteur — V_{comp_axis}",
                        x=x_pos + 700, y=y_pos)
        arrow.node_tree = vecteur.get_vecteur_node_group()
        try:
            nb.link(orig_vec, arrow.inputs["orig"])
            nb.link(ext_vec, arrow.inputs["ext"])
        except KeyError:
            nb.link(orig_vec, arrow.inputs[0])
            nb.link(ext_vec, arrow.inputs[1])
        return arrow.outputs[0]

    comp_x_geom = _make_component_arrow("x", V0x, x_pos=1100, y_pos=400)
    comp_y_geom = _make_component_arrow("y", V0y, x_pos=1100, y_pos=100)
    comp_z_geom = _make_component_arrow("z", V0z, x_pos=1100, y_pos=-200)

    # Join the three component arrows, set their shared material, then
    # gate the lot through a visibility Switch.
    comp_join = nb.add("GeometryNodeJoinGeometry",
                        label="component arrows", x=2000, y=200)
    nb.link(comp_x_geom, comp_join.inputs["Geometry"])
    nb.link(comp_y_geom, comp_join.inputs["Geometry"])
    nb.link(comp_z_geom, comp_join.inputs["Geometry"])
    comp_mat = nb.add("GeometryNodeSetMaterial",
                       label="components: material", x=2200, y=200)
    nb.link(comp_join.outputs["Geometry"], comp_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Component arrow material"],
             comp_mat.inputs["Material"])

    comp_switch = nb.add("GeometryNodeSwitch",
                          label="show components?",
                          x=2400, y=200)
    comp_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show component arrows"],
                 comp_switch.inputs["Switch"])
        nb.link(comp_mat.outputs["Geometry"],
                 comp_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show component arrows"],
                 comp_switch.inputs[0])
        nb.link(comp_mat.outputs["Geometry"],
                 comp_switch.inputs[2])
    comp_out = (comp_switch.outputs["Output"]
                if "Output" in comp_switch.outputs
                else comp_switch.outputs[0])

    # 6) Norm label ‖V₀‖ = √(V0x² + V0y² + V0z²) at the basepoint.
    sq_x = nb.math("MULTIPLY", V0x, V0x, x=400, y=-200)
    sq_y = nb.math("MULTIPLY", V0y, V0y, x=400, y=-300)
    sq_z = nb.math("MULTIPLY", V0z, V0z, x=400, y=-400)
    sum_xy = nb.math("ADD", sq_x, sq_y, x=600, y=-250)
    sum_xyz = nb.math("ADD", sum_xy, sq_z, x=800, y=-300)
    norm = nb.math("SQRT", sum_xyz, x=1000, y=-300, label="‖V(p_0)‖")
    norm_v2s = nb.add("FunctionNodeValueToString",
                       label="‖V₀‖ → string",
                       x=1200, y=-300)
    nb.link(norm, norm_v2s.inputs["Value"])
    norm_v2s.inputs["Decimals"].default_value = 2
    norm_ecrit = nb.add("GeometryNodeGroup",
                         label="Ecrit(‖V₀‖)",
                         x=1400, y=-300)
    norm_ecrit.node_tree = ecrit.get_ecrit_node_group()
    nb.link(norm_v2s.outputs["String"], norm_ecrit.inputs["String"])
    norm_scale = nb.add("GeometryNodeScaleElements",
                         label="scale norm label",
                         x=1600, y=-300)
    norm_scale.domain = "FACE"
    nb.link(norm_ecrit.outputs["Geometry"],
             norm_scale.inputs["Geometry"])
    nb.link(group_in.outputs["Label size"], norm_scale.inputs["Scale"])
    # Place above basepoint.
    z_off = nb.math("ADD", group_in.outputs["z_0"],
                     group_in.outputs["Label vertical offset"],
                     label="z_0 + offset", x=1800, y=-300)
    norm_pos = nb.combine_xyz(group_in.outputs["x_0"],
                                group_in.outputs["y_0"],
                                z_off,
                                label="norm label position",
                                x=2000, y=-300)
    norm_place = nb.add("GeometryNodeTransform",
                         label="place norm label",
                         x=2200, y=-300)
    nb.link(norm_scale.outputs["Geometry"],
             norm_place.inputs["Geometry"])
    nb.link(norm_pos, norm_place.inputs["Translation"])
    norm_mat = nb.add("GeometryNodeSetMaterial",
                       label="norm label: material",
                       x=2400, y=-300)
    nb.link(norm_place.outputs["Geometry"],
             norm_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Label material"],
             norm_mat.inputs["Material"])
    norm_switch = nb.add("GeometryNodeSwitch",
                          label="show norm label?",
                          x=2700, y=-300)
    norm_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show basepoint norm label"],
                 norm_switch.inputs["Switch"])
        nb.link(norm_mat.outputs["Geometry"],
                 norm_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show basepoint norm label"],
                 norm_switch.inputs[0])
        nb.link(norm_mat.outputs["Geometry"],
                 norm_switch.inputs[2])
    norm_out = (norm_switch.outputs["Output"]
                if "Output" in norm_switch.outputs
                else norm_switch.outputs[0])

    # Gate the grid-arrows mesh through a visibility Switch driven by
    # ``Show arrows``. This lets the user toggle off the dense N³
    # grid while keeping the basepoint sub-tree (marker + total
    # arrow + component arrows + norm label) visible — useful in
    # cluttered scenes or when the basepoint is the pedagogical focus.
    arrows_switch = nb.add("GeometryNodeSwitch",
                             label="show grid arrows?",
                             x=2700, y=-1400)
    arrows_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show arrows"],
                 arrows_switch.inputs["Switch"])
        nb.link(arrows_mat.outputs["Geometry"],
                 arrows_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show arrows"],
                 arrows_switch.inputs[0])
        nb.link(arrows_mat.outputs["Geometry"],
                 arrows_switch.inputs[2])
    arrows_out = (arrows_switch.outputs["Output"]
                  if "Output" in arrows_switch.outputs
                  else arrows_switch.outputs[0])

    # 6.5) Domain frame + graduated axes (shared builders).
    frame_geom = domain_frame.build_domain_frame(
        nb,
        xmin=group_in.outputs["x min"], xmax=group_in.outputs["x max"],
        ymin=group_in.outputs["y min"], ymax=group_in.outputs["y max"],
        zmin=group_in.outputs["z min"], zmax=group_in.outputs["z max"],
        thickness_sock=group_in.outputs["Frame thickness"],
        x=-300, y=-3000)
    frame_mat = nb.add("GeometryNodeSetMaterial",
                        label="frame: material", x=900, y=-3000)
    nb.link(frame_geom, frame_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Frame material"], frame_mat.inputs["Material"])
    frame_switch = nb.add("GeometryNodeSwitch",
                           label="show frame?", x=1100, y=-3000)
    frame_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show domain frame"],
                 frame_switch.inputs["Switch"])
        nb.link(frame_mat.outputs["Geometry"], frame_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show domain frame"],
                 frame_switch.inputs[0])
        nb.link(frame_mat.outputs["Geometry"], frame_switch.inputs[2])
    frame_out = (frame_switch.outputs["Output"]
                 if "Output" in frame_switch.outputs
                 else frame_switch.outputs[0])

    axes_geom = domain_frame.build_graduated_axes(
        nb,
        label_ng=nlbl_ng,
        xmin=group_in.outputs["x min"], xmax=group_in.outputs["x max"],
        ymin=group_in.outputs["y min"], ymax=group_in.outputs["y max"],
        zmin=group_in.outputs["z min"], zmax=group_in.outputs["z max"],
        res_x=group_in.outputs["Resolution X"],
        res_y=group_in.outputs["Resolution Y"],
        res_z=group_in.outputs["Resolution Z"],
        size_sock=group_in.outputs["Axis label size"],
        decimals_sock=group_in.outputs["Axis label decimals"],
        x=-300, y=-3700)
    axes_mat = nb.add("GeometryNodeSetMaterial",
                       label="axes: material", x=1300, y=-3700)
    nb.link(axes_geom, axes_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Axis label material"],
             axes_mat.inputs["Material"])
    axes_switch = nb.add("GeometryNodeSwitch",
                          label="show axes?", x=1500, y=-3700)
    axes_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show graduated axes"],
                 axes_switch.inputs["Switch"])
        nb.link(axes_mat.outputs["Geometry"], axes_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show graduated axes"],
                 axes_switch.inputs[0])
        nb.link(axes_mat.outputs["Geometry"], axes_switch.inputs[2])
    axes_out = (axes_switch.outputs["Output"]
                if "Output" in axes_switch.outputs
                else axes_switch.outputs[0])

    # 7) Final join.
    join = nb.add("GeometryNodeJoinGeometry",
                   label="final", x=3100, y=0)
    nb.link(arrows_out, join.inputs["Geometry"])
    nb.link(nlbl_out, join.inputs["Geometry"])
    nb.link(marker_mat.outputs["Geometry"], join.inputs["Geometry"])
    nb.link(base_arrow_mat.outputs["Geometry"], join.inputs["Geometry"])
    nb.link(comp_out, join.inputs["Geometry"])
    nb.link(norm_out, join.inputs["Geometry"])
    nb.link(frame_out, join.inputs["Geometry"])
    nb.link(axes_out, join.inputs["Geometry"])
    nb.link(join.outputs["Geometry"], group_out.inputs[0])

    # ----- Metadata stash ------------------------------------------------
    nt["realfn_kind"] = "vector_field_3d"
    nt["realfn_mode"] = mode  # "explicit" or "from_potential"
    nt["realfn_components_source"] = list(components_source_clean)
    if mode == "from_potential":
        nt["realfn_potential"] = potential_source
    nt["realfn_var_x"] = x_name
    nt["realfn_var_y"] = y_name
    nt["realfn_var_z"] = z_name
    nt["realfn_params"] = list(allowed_params)
    nt["realfn_components_text"] = [str(sp_.sstr(c)) for c in components]
    nt["realfn_components_latex"] = [str(sp_.latex(c)) for c in components]
    nt["realfn_div_text"] = str(sp_.sstr(div_expr))
    nt["realfn_div_latex"] = str(sp_.latex(div_expr))
    nt["realfn_curl_text"] = [str(sp_.sstr(c)) for c in curl_expr]
    nt["realfn_curl_latex"] = [str(sp_.latex(c)) for c in curl_expr]
    return nt
