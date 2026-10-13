"""
Geometry-Nodes tree builder for 3D scalar fields f: R^3 -> R.

The visualisation
-----------------
A regular Nx × Ny × Nz grid spans the box [x_min, x_max] ×
[y_min, y_max] × [z_min, z_max]. At every grid point we display:

* a small marker sphere placed at (x, y, z);
* a numeric label rendered as extruded 3D text (via the bundled
  :mod:`ecrit` node group), showing the value f(x, y, z) rounded to
  two decimals.

This is the natural extension of the surface/curve viewers to one
more dimension. Whereas a 2D surface z = f(x, y) could *be* its own
height visualisation, a 3D scalar field has no spatial axis left to
encode the value — so we surface the value as a printed number next
to each sample point.

The marker at (x_0, y_0, z_0)
-----------------------------
On top of the grid, a distinguished marker (larger sphere + larger
label) sits at the user-controlled basepoint (x_0, y_0, z_0). The
label there shows ``f(x_0, y_0, z_0)`` and tracks the basepoint as
the user scrubs the sliders.

Resolution caveat
-----------------
A grid resolution of 8 per axis already yields 512 points; 16 yields
4096; 32 yields 32 768. Each grid point spawns a sphere *and* a text
instance, so render cost grows fast. The defaults below keep the
total under 1000 points; the panel exposes the resolution per-axis
so the user can dial it down for a complex field or up for a coarse
one.
"""

from __future__ import annotations

import bpy
import sympy as sp

from .compiler import NodeBuilder, SymPyCompiler
from . import sympy_parser
from . import label_number
from . import domain_frame


SCALAR_FIELD_3D_TREE_PREFIX = "REALFNSF3D_"


def _build_3d_grid(nb: NodeBuilder, *,
                    x_min_sock, x_max_sock,
                    y_min_sock, y_max_sock,
                    z_min_sock, z_max_sock,
                    res_x_sock, res_y_sock, res_z_sock,
                    y_offset=0):
    """Build a regular Nx × Ny × Nz grid of points spanning the given box.

    Strategy: stack three ``Mesh Line`` primitives via
    ``Instance on Points`` to materialise the Cartesian product as a
    point cloud, then ``Realize Instances`` to flatten the hierarchy
    so downstream nodes see one mesh with Nx·Ny·Nz vertices.

    Returns a Geometry socket carrying the resulting point cloud
    (mesh with all vertices, no edges/faces).

    Each line uses the ``OFFSET`` mode (Count + Start Location +
    Offset) rather than ``END_POINTS`` because in OFFSET mode each
    segment has a guaranteed equal step — important for the field
    sampling to be visually regular.
    """
    # X line: Nx points along +X starting at x_min.
    line_x = nb.add("GeometryNodeMeshLine",
                     label="x line", x=-2000, y=y_offset)
    line_x.mode = "OFFSET"
    line_x.count_mode = "TOTAL"
    nb.link(res_x_sock, line_x.inputs["Count"])
    # Start: (x_min, 0, 0)
    start_x = nb.combine_xyz(x_min_sock, 0.0, 0.0,
                              label="(x_min,0,0)", x=-2200, y=y_offset + 200)
    # Step = (x_max - x_min) / (Nx - 1). We compute it via Math nodes.
    span_x = nb.math("SUBTRACT", x_max_sock, x_min_sock,
                      label="x_max - x_min", x=-2200, y=y_offset + 100)
    nx_minus_1 = nb.math("SUBTRACT", res_x_sock, 1.0,
                          label="Nx - 1", x=-2200, y=y_offset + 50)
    step_x_scalar = nb.math("DIVIDE", span_x, nx_minus_1,
                             label="step x", x=-2000, y=y_offset + 100)
    offset_x = nb.combine_xyz(step_x_scalar, 0.0, 0.0,
                               label="offset x", x=-1800, y=y_offset + 100)
    nb.link(start_x, line_x.inputs["Start Location"])
    nb.link(offset_x, line_x.inputs["Offset"])

    # Y line: Ny points along +Y starting at y_min.
    line_y = nb.add("GeometryNodeMeshLine",
                     label="y line", x=-2000, y=y_offset - 400)
    line_y.mode = "OFFSET"
    line_y.count_mode = "TOTAL"
    nb.link(res_y_sock, line_y.inputs["Count"])
    start_y = nb.combine_xyz(0.0, y_min_sock, 0.0,
                              label="(0,y_min,0)", x=-2200, y=y_offset - 300)
    span_y = nb.math("SUBTRACT", y_max_sock, y_min_sock,
                      label="y_max - y_min", x=-2200, y=y_offset - 350)
    ny_minus_1 = nb.math("SUBTRACT", res_y_sock, 1.0,
                          label="Ny - 1", x=-2200, y=y_offset - 400)
    step_y_scalar = nb.math("DIVIDE", span_y, ny_minus_1,
                             label="step y", x=-2000, y=y_offset - 350)
    offset_y = nb.combine_xyz(0.0, step_y_scalar, 0.0,
                               label="offset y", x=-1800, y=y_offset - 350)
    nb.link(start_y, line_y.inputs["Start Location"])
    nb.link(offset_y, line_y.inputs["Offset"])

    # Z line: Nz points along +Z starting at z_min.
    line_z = nb.add("GeometryNodeMeshLine",
                     label="z line", x=-2000, y=y_offset - 800)
    line_z.mode = "OFFSET"
    line_z.count_mode = "TOTAL"
    nb.link(res_z_sock, line_z.inputs["Count"])
    start_z = nb.combine_xyz(0.0, 0.0, z_min_sock,
                              label="(0,0,z_min)", x=-2200, y=y_offset - 700)
    span_z = nb.math("SUBTRACT", z_max_sock, z_min_sock,
                      label="z_max - z_min", x=-2200, y=y_offset - 750)
    nz_minus_1 = nb.math("SUBTRACT", res_z_sock, 1.0,
                          label="Nz - 1", x=-2200, y=y_offset - 800)
    step_z_scalar = nb.math("DIVIDE", span_z, nz_minus_1,
                             label="step z", x=-2000, y=y_offset - 750)
    offset_z = nb.combine_xyz(0.0, 0.0, step_z_scalar,
                               label="offset z", x=-1800, y=y_offset - 750)
    nb.link(start_z, line_z.inputs["Start Location"])
    nb.link(offset_z, line_z.inputs["Offset"])

    # Build the Cartesian product:
    #   step 1: instance X-line on each point of Y-line  -> XY grid
    #   step 2: instance the result on each point of Z-line -> XYZ grid
    iop_xy = nb.add("GeometryNodeInstanceOnPoints",
                     label="X × Y", x=-1500, y=y_offset - 200)
    nb.link(line_y.outputs["Mesh"], iop_xy.inputs["Points"])
    nb.link(line_x.outputs["Mesh"], iop_xy.inputs["Instance"])

    # We need the XY grid as a single point cloud (not instances),
    # otherwise the next InstanceOnPoints won't broadcast correctly.
    realize_xy = nb.add("GeometryNodeRealizeInstances",
                         label="realize XY", x=-1200, y=y_offset - 200)
    nb.link(iop_xy.outputs["Instances"], realize_xy.inputs["Geometry"])

    iop_xyz = nb.add("GeometryNodeInstanceOnPoints",
                      label="(X × Y) × Z", x=-900, y=y_offset - 500)
    nb.link(line_z.outputs["Mesh"], iop_xyz.inputs["Points"])
    nb.link(realize_xy.outputs["Geometry"], iop_xyz.inputs["Instance"])

    realize_xyz = nb.add("GeometryNodeRealizeInstances",
                          label="realize XYZ", x=-600, y=y_offset - 500)
    nb.link(iop_xyz.outputs["Instances"], realize_xyz.inputs["Geometry"])
    return realize_xyz.outputs["Geometry"]


def _instance_sphere_on_points(nb: NodeBuilder, *,
                                 points_sock, radius_sock,
                                 material_sock,
                                 label="markers", y_offset=0):
    """Instance a small UV sphere on every point of ``points_sock``.

    Returns a Geometry socket carrying the realized sphere mesh
    (one merged mesh, not an Instances datablock). Realizing here
    lets us assign a material via a downstream SetMaterial without
    the per-instance complications.
    """
    sphere = nb.add("GeometryNodeMeshUVSphere",
                     label=f"{label}: source", x=200, y=y_offset)
    sphere.inputs["Segments"].default_value = 12
    sphere.inputs["Rings"].default_value = 6
    nb.link(radius_sock, sphere.inputs["Radius"])

    iop = nb.add("GeometryNodeInstanceOnPoints",
                  label=f"{label}: instance", x=500, y=y_offset)
    nb.link(points_sock, iop.inputs["Points"])
    nb.link(sphere.outputs["Mesh"], iop.inputs["Instance"])

    realize = nb.add("GeometryNodeRealizeInstances",
                      label=f"{label}: realize", x=800, y=y_offset)
    nb.link(iop.outputs["Instances"], realize.inputs["Geometry"])

    mat = nb.add("GeometryNodeSetMaterial",
                  label=f"{label}: material", x=1100, y=y_offset)
    nb.link(realize.outputs["Geometry"], mat.inputs["Geometry"])
    nb.link(material_sock, mat.inputs["Material"])
    return mat.outputs["Geometry"]


def _bake_f_value_on_geometry(nb: NodeBuilder, *,
                                geom_sock,
                                f_expr,
                                x_name, y_name, z_name,
                                free_param_sockets,
                                f_min_sock, f_max_sock,
                                y_offset=-700):
    """Bake the normalised value of f(x, y, z) onto every point of
    the input geometry as a named float attribute ``rfn_f_value``.

    Why this and not For-Each labels
    --------------------------------
    Per-vertex *numeric labels* (instancing the bundled Ecrit text
    mesh, one per grid point) require a For-Each Geometry Element
    zone with a custom Input Item carrying the iteration's position.
    In Blender 5.1 the Python API rejects adding input items to that
    zone with "Cannot add socket to built-in node" — a known
    limitation of the API. So we drop labels per-point and switch
    to a colour-coded visualisation: each sphere is shaded by the
    value of f(x, y, z) at its centre, via a shader-side
    ``Attribute("rfn_f_value")`` lookup feeding a ColorRamp.

    How this works
    --------------
    Inside Geometry Nodes:

        Position field → SeparateXYZ → SymPy(f) → raw float f(x, y, z)
                                                       ↓
                              (raw - f_min) / (f_max - f_min)
                                                       ↓
                              clamped to [0, 1]
                                                       ↓
                       StoreNamedAttribute("rfn_f_value", FLOAT, POINT)
                                                       ↓
                                            geometry (unchanged) ──→

    The normalisation puts f into [0, 1] so the shader can use a
    fixed-anchor ColorRamp without needing to read modifier
    sockets (which it can't, by design). The user controls the
    color range through ``f min`` / ``f max`` sockets on the
    modifier — moving them updates the normalisation live.

    Because the consumer of the field (StoreNamedAttribute) IS
    attribute-aware (it has a ``domain="POINT"``), the field
    evaluates per-point of the input geometry. No For-Each zone
    needed. This is precisely the "field evaluation is faster than
    For-Each" case mentioned in Blender's own documentation.

    Returns the Geometry socket with the attribute attached.
    """
    # Read the per-point position via the (attribute-aware-when-
    # consumed) field, separate into scalars.
    pos = nb.add("GeometryNodeInputPosition",
                  label="vertex pos (for f)", x=-300, y=y_offset)
    sep = nb.add("ShaderNodeSeparateXYZ",
                  label="separate xyz", x=-100, y=y_offset)
    nb.link(pos.outputs["Position"], sep.inputs["Vector"])

    # Compile f using SymPy → Math nodes.
    var_sockets = {
        x_name: sep.outputs["X"],
        y_name: sep.outputs["Y"],
        z_name: sep.outputs["Z"],
        **free_param_sockets,
    }
    compiler = SymPyCompiler(nb, var_sockets)
    f_value = compiler.compile(f_expr)

    # Normalise to [0, 1]: (f - f_min) / (f_max - f_min), then clamp.
    # Two paths to write this cleanly: MapRange (one node) or three
    # Math nodes. MapRange handles the clamping for us with a
    # checkbox, so we prefer it.
    map_range = nb.add("ShaderNodeMapRange",
                        label="normalise f to [0, 1]",
                        x=400, y=y_offset)
    # MapRange has named inputs in 4.x+; defensive fallback otherwise.
    try:
        nb.link(f_value, map_range.inputs["Value"])
        nb.link(f_min_sock, map_range.inputs["From Min"])
        nb.link(f_max_sock, map_range.inputs["From Max"])
        map_range.inputs["To Min"].default_value = 0.0
        map_range.inputs["To Max"].default_value = 1.0
    except KeyError:
        # ShaderNodeMapRange socket order (positional):
        #   0=Value, 1=From Min, 2=From Max, 3=To Min, 4=To Max
        nb.link(f_value, map_range.inputs[0])
        nb.link(f_min_sock, map_range.inputs[1])
        nb.link(f_max_sock, map_range.inputs[2])
        map_range.inputs[3].default_value = 0.0
        map_range.inputs[4].default_value = 1.0
    # Enable clamping so values outside [f_min, f_max] saturate to
    # the ends of the colour ramp instead of being mapped outside
    # [0, 1] (where the ramp output would be undefined).
    try:
        map_range.clamp = True
    except AttributeError:
        # In some versions ``clamp`` is exposed as a node property
        # rather than an attribute; safe to ignore — the ColorRamp
        # itself extrapolates with its end-stop colours.
        pass

    # Bake the normalised value as a named float attribute on the
    # geometry's POINT domain.
    store = nb.add("GeometryNodeStoreNamedAttribute",
                    label="bake 'rfn_f_value'", x=700, y=y_offset)
    store.domain = "POINT"
    store.data_type = "FLOAT"
    # The Name input is a String socket; set its default value.
    try:
        store.inputs["Name"].default_value = "rfn_f_value"
    except (KeyError, TypeError):
        # Positional fallback: input index 2 is typically "Name".
        store.inputs[2].default_value = "rfn_f_value"

    nb.link(geom_sock, store.inputs["Geometry"])

    # Value input — the named-float socket. The MapRange output is
    # "Result" in 4.x+.
    try:
        nb.link(map_range.outputs["Result"], store.inputs["Value"])
    except KeyError:
        # Defensive: try common alternates. StoreNamedAttribute has
        # one Value socket per data_type; for FLOAT it's the float
        # input which appears among the inputs at a higher index.
        for cand in ("Value", "Value_Float", "Value Float"):
            try:
                nb.link(map_range.outputs[0], store.inputs[cand])
                break
            except KeyError:
                continue
        else:
            # Last-ditch: positional. Inputs are [Geometry, Selection,
            # Name, Value_Vector, Value_Float, Value_Color, ...] so
            # FLOAT is typically at index 4. We try 4 then fall back.
            for idx in (4, 3):
                try:
                    nb.link(map_range.outputs[0], store.inputs[idx])
                    break
                except (IndexError, KeyError):
                    continue

    return store.outputs["Geometry"]




def make_scalarfield3d_tree(expr_str: str, *,
                              x_name: str = "x",
                              y_name: str = "y",
                              z_name: str = "z",
                              allowed_params: tuple[str, ...] = (),
                              x_default_range: tuple[float, float] = (-1.0, 1.0),
                              y_default_range: tuple[float, float] = (-1.0, 1.0),
                              z_default_range: tuple[float, float] = (-1.0, 1.0),
                              x0_default: float = 0.0,
                              y0_default: float = 0.0,
                              z0_default: float = 0.0,
                              key_suffix: str = ""):
    """Build a Geometry-Nodes tree visualising f: R^3 -> R.

    The output object is a point cloud (Nx × Ny × Nz spheres) with a
    floating numeric label next to each point showing the local
    value f(x, y, z). A distinguished marker + label sits at
    (x_0, y_0, z_0) with its own size and material slots so it
    stands out from the grid.

    Sockets exposed on the modifier
    -------------------------------
    Resolution X / Y / Z, x/y/z min/max, x_0/y_0/z_0,
    Marker size / Marker material (use the auto-installed
        "RealFn ScalarField 3D" material for colour-coded display),
    f min / f max (scalar value range for the colour ramp),
    Basepoint marker size / Basepoint marker material,
    Basepoint label size / Basepoint label offset / Basepoint label material,
    Show basepoint (toggle),
    + one float socket per free parameter declared in ``allowed_params``.

    Returns
    -------
    bpy.types.NodeTree
    """
    sp_ = sympy_parser._sympy()
    f_expr = sympy_parser.parse_scalar_field_3d_expression(
        expr_str, x_name=x_name, y_name=y_name, z_name=z_name,
    )
    grad = sympy_parser.scalar_field_3d_gradient(
        f_expr, x_name=x_name, y_name=y_name, z_name=z_name,
    )
    # Basepoint-evaluated version: substitute x→x_0, y→y_0, z→z_0.
    x_sym = sp_.Symbol(x_name, real=True)
    y_sym = sp_.Symbol(y_name, real=True)
    z_sym = sp_.Symbol(z_name, real=True)
    x0_sym = sp_.Symbol("x_0", real=True)
    y0_sym = sp_.Symbol("y_0", real=True)
    z0_sym = sp_.Symbol("z_0", real=True)
    subs = {x_sym: x0_sym, y_sym: y0_sym, z_sym: z0_sym}
    f0_expr = f_expr.subs(subs)

    # Validate free symbols.
    all_free = f_expr.free_symbols | f0_expr.free_symbols
    for g in grad:
        all_free |= g.free_symbols
    known = {x_name, y_name, z_name, "x_0", "y_0", "z_0"} | set(allowed_params)
    unknown = sorted(s.name for s in all_free if s.name not in known)
    if unknown:
        raise ValueError(
            f"Symboles non autorisés : {', '.join(unknown)}. "
            f"Autorisés : {sorted(known)}"
        )

    # --- Tree skeleton --------------------------------------------------
    nt = bpy.data.node_groups.new(
        f"{SCALAR_FIELD_3D_TREE_PREFIX}{key_suffix or 'fn'}",
        "GeometryNodeTree",
    )
    nt.interface.new_socket(
        "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry",
    )

    def add_int(name, default, mn=2, mx=64, desc=""):
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

    add_int("Resolution X", 5, mn=2, mx=64,
             desc="Nombre d'échantillons en x. Coût total : Nx·Ny·Nz "
                  "sphères ET autant de labels — gardez les résolutions "
                  "modérées (5·5·5 = 125, 8·8·8 = 512, 16·16·16 = 4096)")
    add_int("Resolution Y", 5, mn=2, mx=64,
             desc="Nombre d'échantillons en y")
    add_int("Resolution Z", 5, mn=2, mx=64,
             desc="Nombre d'échantillons en z")
    add_float("x min", float(x_default_range[0]))
    add_float("x max", float(x_default_range[1]))
    add_float("y min", float(y_default_range[0]))
    add_float("y max", float(y_default_range[1]))
    add_float("z min", float(z_default_range[0]))
    add_float("z max", float(z_default_range[1]))
    add_float("x_0", float(x0_default),
               desc="Coordonnée x du point d'ancrage où s'affiche la valeur "
                    "f(x₀, y₀, z₀) avec un marqueur distinct")
    add_float("y_0", float(y0_default),
               desc="Coordonnée y du point d'ancrage")
    add_float("z_0", float(z0_default),
               desc="Coordonnée z du point d'ancrage")
    add_float("Marker size", 0.04, mn=0.0,
               desc="Rayon des petites sphères marqueuses à chaque point "
                    "de la grille")
    add_mat("Marker material",
             desc="Matériau des marqueurs de la grille. Utiliser le "
                  "matériau « RealFn ScalarField 3D » (auto-installé) "
                  "pour bénéficier de la coloration par f(x, y, z) ; "
                  "ce matériau lit l'attribut 'rfn_f_value' du modificateur "
                  "et applique une color ramp dessus")
    add_float("f min", -1.0,
               desc="Valeur de f mappée à l'extrémité froide de la color "
                    "ramp (bleu). Les valeurs < f_min sont saturées au "
                    "bleu")
    add_float("f max", 1.0,
               desc="Valeur de f mappée à l'extrémité chaude de la color "
                    "ramp (rouge). Les valeurs > f_max sont saturées au "
                    "rouge. Ajuster (f_min, f_max) pour serrer la "
                    "dynamique des couleurs sur la plage d'intérêt")
    # Per-point numeric labels (glyph-atlas instancing — see
    # label_number.py). Displayed in fixed format [-]DD.DD.
    add_bool("Show value labels", False,
              desc="Affiche la valeur numérique f(x,y,z) à côté de "
                   "chaque sphère échantillonnée (format ±DD.DD). "
                   "Coûteux à haute résolution — utiliser le pas "
                   "ci-dessous pour n'étiqueter qu'un point sur N")
    add_int("Label stride", 2, mn=1, mx=20,
             desc="Pas d'échantillonnage des étiquettes : 1 = toutes "
                  "les sphères, 2 = une sur deux, 3 = une sur trois… "
                  "Augmenter pour désencombrer une grille dense")
    add_float("Label size", 0.08, mn=0.0,
               desc="Hauteur des chiffres des étiquettes numériques")
    add_float("Label offset", 0.10,
               desc="Hauteur des étiquettes au-dessus de leur sphère "
                    "(décalage vertical, le nombre est centré sur le "
                    "point)")
    add_int("Label decimals", 2, mn=0, mx=4,
             desc="Nombre de décimales affichées par les étiquettes "
                  "numériques (0 = entiers)")
    add_bool("Label vertical", False,
              desc="Redresse les étiquettes à la verticale, face à la "
                   "vue de face (Numpad 1). Décoché : à plat, lisibles "
                   "depuis la vue de dessus")
    add_int("Label max points", 2000, mn=1, mx=100000,
             desc="Garde-fou : au-delà de ce nombre de points de "
                  "grille, aucune étiquette n'est générée (protège "
                  "contre le gel de Blender à haute résolution)")
    add_mat("Label material",
             desc="Matériau des étiquettes numériques par-point")
    # --- Domain frame + graduated axes (pedagogical aids) ---
    add_bool("Show domain frame", True,
              desc="Affiche les 12 arêtes de la boîte du domaine "
                   "[x min, x max]×[y min, y max]×[z min, z max] en "
                   "tubes fins")
    add_float("Frame thickness", 0.01, mn=0.0,
               desc="Rayon des tubes du cadre du domaine")
    add_mat("Frame material",
             desc="Matériau du cadre du domaine")
    add_bool("Show graduated axes", False,
              desc="Affiche des graduations numérotées le long de "
                   "trois arêtes de la boîte (axes x, y, z), une par "
                   "plan de grille")
    add_float("Axis label size", 0.07, mn=0.0,
               desc="Hauteur des chiffres des graduations d'axes")
    add_int("Axis label decimals", 1, mn=0, mx=4,
             desc="Décimales des graduations d'axes")
    add_mat("Axis label material",
             desc="Matériau des graduations d'axes")
    add_bool("Show basepoint", True,
              desc="Affiche un marqueur et une étiquette plus grands au "
                   "point d'ancrage (x₀, y₀, z₀). Décocher pour cacher")
    add_float("Basepoint marker size", 0.10, mn=0.0,
               desc="Rayon du marqueur du point d'ancrage")
    add_mat("Basepoint marker material",
             desc="Matériau du marqueur du point d'ancrage")
    add_float("Basepoint label size", 0.16, mn=0.0,
               desc="Taille de l'étiquette au point d'ancrage")
    add_float("Basepoint label offset", 0.10, mn=0.0,
               desc="Décalage horizontal et vertical de l'étiquette du "
                    "point d'ancrage par rapport au marqueur — pour "
                    "éviter le chevauchement")
    add_mat("Basepoint label material",
             desc="Matériau de l'étiquette du point d'ancrage")
    for p in allowed_params:
        ps = nt.interface.new_socket(p, in_out="INPUT",
                                       socket_type="NodeSocketFloat")
        ps.default_value = 1.0

    # --- Build the graph ------------------------------------------------
    nb = NodeBuilder(nt)
    group_in = nb.add("NodeGroupInput", x=-2400, y=0)
    group_out = nb.add("NodeGroupOutput", x=3000, y=0)

    free_param_sockets = {p: group_in.outputs[p] for p in allowed_params}
    basepoint_extra = dict(free_param_sockets)
    basepoint_extra["x_0"] = group_in.outputs["x_0"]
    basepoint_extra["y_0"] = group_in.outputs["y_0"]
    basepoint_extra["z_0"] = group_in.outputs["z_0"]

    # 1) Grid of points.
    grid_geom = _build_3d_grid(
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
        y_offset=400,
    )

    # 2) Bake f(x, y, z) as a named float attribute "rfn_f_value" on
    # the grid points. Normalised to [0, 1] via (f min, f max). The
    # attribute propagates onto the sphere vertices when we instance
    # spheres on points and realize — so the shader's
    # ``Attribute("rfn_f_value")`` lookup finds it.
    grid_geom_with_attr = _bake_f_value_on_geometry(
        nb,
        geom_sock=grid_geom,
        f_expr=f_expr,
        x_name=x_name, y_name=y_name, z_name=z_name,
        free_param_sockets=free_param_sockets,
        f_min_sock=group_in.outputs["f min"],
        f_max_sock=group_in.outputs["f max"],
        y_offset=-700,
    )

    # 3) Sphere markers at each grid point. The attribute baked above
    # rides along on the realized sphere vertices, which is what the
    # "RealFn ScalarField 3D" shader reads.
    spheres_geom = _instance_sphere_on_points(
        nb,
        points_sock=grid_geom_with_attr,
        radius_sock=group_in.outputs["Marker size"],
        material_sock=group_in.outputs["Marker material"],
        label="grid markers", y_offset=0,
    )
    # 3.5) Per-point numeric labels via the LabelNumber node group.
    # We compile f again as a *field* (driven by InputPosition) and
    # feed it to the LabelNumber group, which decomposes the value
    # into glyphs and instances them next to each strided point. The
    # whole thing is gated by the "Show value labels" toggle.
    label_pos = nb.add("GeometryNodeInputPosition",
                        label="label: vertex pos", x=-300, y=-2100)
    label_sep = nb.add("ShaderNodeSeparateXYZ",
                        label="label: separate", x=-100, y=-2100)
    nb.link(label_pos.outputs["Position"], label_sep.inputs["Vector"])
    label_compiler = SymPyCompiler(nb, {
        x_name: label_sep.outputs["X"],
        y_name: label_sep.outputs["Y"],
        z_name: label_sep.outputs["Z"],
        **free_param_sockets,
    })
    label_f_value = label_compiler.compile(f_expr)

    label_ng = label_number.get_label_number_node_group()
    label_group = nb.add("GeometryNodeGroup",
                          label="LabelNumber(f)", x=400, y=-2000)
    label_group.node_tree = label_ng
    nb.link(grid_geom, label_group.inputs["Points"])
    nb.link(label_f_value, label_group.inputs["Value"])
    nb.link(group_in.outputs["Label size"], label_group.inputs["Size"])
    nb.link(group_in.outputs["Label stride"], label_group.inputs["Stride"])
    nb.link(group_in.outputs["Label decimals"],
             label_group.inputs["Decimals"])
    nb.link(group_in.outputs["Label vertical"],
             label_group.inputs["Face front"])
    nb.link(group_in.outputs["Label max points"],
             label_group.inputs["Max points"])
    # Offset = (0, 0, Label offset) — the label floats ABOVE its
    # sphere. A horizontal offset drifts the number toward the next
    # grid sphere (spacing ~0.5, number width ~0.3) and the reader
    # pairs it with the wrong point; vertical placement keeps the
    # number unambiguously over its own sphere.
    label_off_vec = nb.combine_xyz(0.0, 0.0,
                                     group_in.outputs["Label offset"],
                                     label="label offset vec",
                                     x=200, y=-2150)
    nb.link(label_off_vec, label_group.inputs["Offset"])

    # Material for the labels.
    label_mat = nb.add("GeometryNodeSetMaterial",
                        label="labels: material", x=700, y=-2000)
    nb.link(label_group.outputs["Geometry"], label_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Label material"], label_mat.inputs["Material"])

    # Gate via Show value labels.
    label_switch = nb.add("GeometryNodeSwitch",
                           label="show value labels?", x=950, y=-2000)
    label_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show value labels"],
                 label_switch.inputs["Switch"])
        nb.link(label_mat.outputs["Geometry"], label_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show value labels"],
                 label_switch.inputs[0])
        nb.link(label_mat.outputs["Geometry"], label_switch.inputs[2])
    label_out = (label_switch.outputs["Output"]
                 if "Output" in label_switch.outputs
                 else label_switch.outputs[0])

    # 4) Basepoint marker + basepoint label.
    bp_pos = nb.combine_xyz(
        group_in.outputs["x_0"],
        group_in.outputs["y_0"],
        group_in.outputs["z_0"],
        label="basepoint", x=-200, y=-1400,
    )
    # Basepoint sphere
    bp_sphere = nb.add("GeometryNodeMeshUVSphere",
                        label="bp sphere", x=0, y=-1400)
    bp_sphere.inputs["Segments"].default_value = 24
    bp_sphere.inputs["Rings"].default_value = 12
    nb.link(group_in.outputs["Basepoint marker size"],
             bp_sphere.inputs["Radius"])
    bp_place = nb.add("GeometryNodeSetPosition",
                       label="bp place", x=300, y=-1400)
    nb.link(bp_sphere.outputs["Mesh"], bp_place.inputs["Geometry"])
    nb.link(bp_pos, bp_place.inputs["Offset"])
    bp_mat = nb.add("GeometryNodeSetMaterial",
                     label="bp material", x=600, y=-1400)
    nb.link(bp_place.outputs["Geometry"], bp_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Basepoint marker material"],
             bp_mat.inputs["Material"])

    # Basepoint label: compile f(x₀, y₀, z₀) as a scalar driven by the
    # x_0, y_0, z_0 sockets (and free params), convert to string, run
    # through StringToCurves → FillCurve → ExtrudeMesh, place at the
    # basepoint.
    bp_compiler = SymPyCompiler(nb, basepoint_extra)
    f0_sock = bp_compiler.compile(f0_expr)
    bp_v2s = nb.add("FunctionNodeValueToString",
                     label="f₀ → str (2 dec.)", x=0, y=-1800)
    nb.link(f0_sock, bp_v2s.inputs["Value"])
    try:
        bp_v2s.inputs["Decimals"].default_value = 2
    except KeyError:
        bp_v2s.inputs[1].default_value = 2
    bp_stc = nb.add("GeometryNodeStringToCurves",
                     label="bp label", x=300, y=-1800)
    nb.link(bp_v2s.outputs[0], bp_stc.inputs[0])
    nb.link(group_in.outputs["Basepoint label size"],
             bp_stc.inputs["Size"])
    try:
        bp_stc.inputs[3].default_value = "Center"
        bp_stc.inputs[4].default_value = "Top Baseline"
        bp_stc.inputs[5].default_value = "Bottom Left"
    except (IndexError, KeyError, TypeError):
        pass
    bp_fill = nb.add("GeometryNodeFillCurve",
                      label="bp fill", x=600, y=-1800)
    nb.link(bp_stc.outputs[0], bp_fill.inputs[0])
    bp_extrude = nb.add("GeometryNodeExtrudeMesh",
                         label="bp extrude", x=900, y=-1800)
    bp_extrude.mode = "FACES"
    nb.link(bp_fill.outputs[0], bp_extrude.inputs[0])
    try:
        bp_extrude.inputs[3].default_value = 0.03
        bp_extrude.inputs[4].default_value = True
    except (IndexError, KeyError, TypeError):
        pass
    bp_realize = nb.add("GeometryNodeRealizeInstances",
                         label="bp realize", x=1200, y=-1800)
    nb.link(bp_extrude.outputs[0], bp_realize.inputs[0])

    # Position the basepoint label slightly above and right of the
    # basepoint sphere so the two are both visible.
    bp_label_offset = nb.combine_xyz(
        group_in.outputs["Basepoint label offset"],
        0.0,
        group_in.outputs["Basepoint label offset"],
        label="bp label offset", x=1300, y=-2000,
    )
    bp_full_pos = nb.add("ShaderNodeVectorMath",
                          label="bp label total pos",
                          x=1500, y=-1900)
    bp_full_pos.operation = "ADD"
    nb.link(bp_pos, bp_full_pos.inputs[0])
    nb.link(bp_label_offset, bp_full_pos.inputs[1])
    bp_label_place = nb.add("GeometryNodeSetPosition",
                              label="bp label place",
                              x=1700, y=-1800)
    nb.link(bp_realize.outputs[0], bp_label_place.inputs["Geometry"])
    nb.link(bp_full_pos.outputs[0], bp_label_place.inputs["Offset"])
    bp_label_mat = nb.add("GeometryNodeSetMaterial",
                            label="bp label material",
                            x=2000, y=-1800)
    nb.link(bp_label_place.outputs["Geometry"],
             bp_label_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Basepoint label material"],
             bp_label_mat.inputs["Material"])

    # Wrap basepoint (sphere + label) in a Show-basepoint toggle.
    bp_join = nb.add("GeometryNodeJoinGeometry",
                      label="bp join", x=2300, y=-1600)
    nb.link(bp_mat.outputs["Geometry"], bp_join.inputs["Geometry"])
    nb.link(bp_label_mat.outputs["Geometry"], bp_join.inputs["Geometry"])
    bp_switch = nb.add("GeometryNodeSwitch",
                        label="show basepoint?", x=2500, y=-1600)
    bp_switch.input_type = "GEOMETRY"
    try:
        nb.link(group_in.outputs["Show basepoint"],
                 bp_switch.inputs["Switch"])
        nb.link(bp_join.outputs["Geometry"], bp_switch.inputs["True"])
    except KeyError:
        nb.link(group_in.outputs["Show basepoint"], bp_switch.inputs[0])
        nb.link(bp_join.outputs["Geometry"], bp_switch.inputs[2])
    bp_out = (bp_switch.outputs["Output"]
              if "Output" in bp_switch.outputs
              else bp_switch.outputs[0])

    # 4.5) Domain frame + graduated axes (shared builders).
    frame_geom = domain_frame.build_domain_frame(
        nb,
        xmin=group_in.outputs["x min"], xmax=group_in.outputs["x max"],
        ymin=group_in.outputs["y min"], ymax=group_in.outputs["y max"],
        zmin=group_in.outputs["z min"], zmax=group_in.outputs["z max"],
        thickness_sock=group_in.outputs["Frame thickness"],
        x=-300, y=-2700)
    frame_mat = nb.add("GeometryNodeSetMaterial",
                        label="frame: material", x=900, y=-2700)
    nb.link(frame_geom, frame_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Frame material"], frame_mat.inputs["Material"])
    frame_switch = nb.add("GeometryNodeSwitch",
                           label="show frame?", x=1100, y=-2700)
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
        label_ng=label_ng,
        xmin=group_in.outputs["x min"], xmax=group_in.outputs["x max"],
        ymin=group_in.outputs["y min"], ymax=group_in.outputs["y max"],
        zmin=group_in.outputs["z min"], zmax=group_in.outputs["z max"],
        res_x=group_in.outputs["Resolution X"],
        res_y=group_in.outputs["Resolution Y"],
        res_z=group_in.outputs["Resolution Z"],
        size_sock=group_in.outputs["Axis label size"],
        decimals_sock=group_in.outputs["Axis label decimals"],
        x=-300, y=-3400)
    axes_mat = nb.add("GeometryNodeSetMaterial",
                       label="axes: material", x=1300, y=-3400)
    nb.link(axes_geom, axes_mat.inputs["Geometry"])
    nb.link(group_in.outputs["Axis label material"],
             axes_mat.inputs["Material"])
    axes_switch = nb.add("GeometryNodeSwitch",
                          label="show axes?", x=1500, y=-3400)
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

    # 5) Final join: grid spheres (coloured by 'rfn_f_value' via the
    # shader) + per-point numeric labels (gated) + basepoint subtree
    # + domain frame + graduated axes (both gated).
    final_join = nb.add("GeometryNodeJoinGeometry",
                          label="final join", x=2700, y=0)
    nb.link(spheres_geom, final_join.inputs["Geometry"])
    nb.link(label_out, final_join.inputs["Geometry"])
    nb.link(bp_out, final_join.inputs["Geometry"])
    nb.link(frame_out, final_join.inputs["Geometry"])
    nb.link(axes_out, final_join.inputs["Geometry"])
    nb.link(final_join.outputs["Geometry"], group_out.inputs[0])

    # --- Metadata stash -------------------------------------------------
    nt["realfn_kind"] = "scalar_field_3d"
    nt["realfn_expr"] = expr_str
    nt["realfn_var_x"] = x_name
    nt["realfn_var_y"] = y_name
    nt["realfn_var_z"] = z_name
    nt["realfn_params"] = list(allowed_params)
    nt["realfn_f_text"] = str(sp_.sstr(f_expr))
    nt["realfn_f_latex"] = str(sp_.latex(f_expr))
    nt["realfn_grad_text"] = [str(sp_.sstr(g)) for g in grad]
    nt["realfn_grad_latex"] = [str(sp_.latex(g)) for g in grad]
    return nt
