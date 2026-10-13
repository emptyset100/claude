"""
Geometry Nodes tree for a "banc de vecteurs" (vector bench).

The bench is an *exploration* surface for vector algebra and rotations:
the user declares several named vectors (each an expression that may use
the Mathutils/vector helpers of :mod:`sympy_parser` and reference vectors
declared earlier), all drawn as coloured arrows from the world origin.

What makes it interactive is the **shared scalar parameters**: any free
symbol declared as a parameter (e.g. ``theta``) becomes a live ``Float``
modifier socket. Because helpers such as ``rotate`` and ``rot_z`` are
symbol-friendly, scrubbing that slider rotates the relevant arrows in
real time — you watch ``rotate(v, axis, theta)`` sweep, see ``cross(a, b)``
stay orthogonal, etc.

Each arrow reuses the bundled ``Vecteur`` node group (see :mod:`vecteur`)
with ``orig = (0, 0, 0)`` and ``ext`` = the compiled vector. A per-row
visibility boolean and material socket are exposed, mirroring the
per-piece convention of the scalar / vector-function trees.
"""

from __future__ import annotations

import bpy

from . import compiler, sympy_parser, vecteur


# Identifiable prefix — distinct from the five other RealFn kinds so the
# panel / active-modifier helpers can recognise a bench at a glance.
BENCH_TREE_PREFIX = "REALFNVB_"


# --------------------------------------------------------------------------- #
# Ready-to-use bench presets
# --------------------------------------------------------------------------- #
# Each entry: id, FR label (+ EN), declared parameters (csv), and an ordered
# list of (name, expression) rows. Applying one builds a bench straight away
# — a one-click tour of the vector / rotation helpers. Rows may reference
# earlier rows by name, exactly like the create dialog.
BUILTIN_BENCHES = (
    {
        "id": "rotation_quat",
        "label": "Rotation (quaternion)",
        "label_en": "Rotation (quaternion)",
        "params": "theta",
        "rows": [
            ("v", "vec(2, 0, 0)"),
            ("Rv", "qrotate(quat_axis(vec(0,0,1), theta), v)"),
        ],
    },
    {
        "id": "cross",
        "label": "Produit vectoriel a × b",
        "label_en": "Cross product a × b",
        "params": "theta",
        "rows": [
            ("a", "vec(2, 0, 0)"),
            ("b", "rotate(vec(2,0,0), vec(0,0,1), theta)"),
            ("axb", "cross(a, b)"),
        ],
    },
    {
        "id": "frame",
        "label": "Repère orthonormé tournant",
        "label_en": "Rotating orthonormal frame",
        "params": "theta",
        "rows": [
            ("e1", "rotate(vec(1.5,0,0), vec(0,0,1), theta)"),
            ("e2", "rotate(vec(0,1.5,0), vec(0,0,1), theta)"),
            ("e3", "vec(0, 0, 1.5)"),
        ],
    },
    {
        "id": "slerp",
        "label": "Slerp de quaternions",
        "label_en": "Quaternion slerp",
        "params": "theta",
        "rows": [
            ("v", "vec(2, 0, 0)"),
            ("slerp", "qrotate(qslerp(quat_axis(vec(0,1,0),0), "
                      "quat_axis(vec(0,1,0),3.14159), theta), v)"),
        ],
    },
    {
        "id": "euler",
        "label": "Angles d'Euler (XYZ)",
        "label_en": "Euler angles (XYZ)",
        "params": "rx, ry, rz",
        "rows": [
            ("v", "vec(2, 0, 0)"),
            ("Rv", "eul(rx, ry, rz) * v"),
        ],
    },
    {
        "id": "projection",
        "label": "Projection / décomposition",
        "label_en": "Projection / decomposition",
        "params": "theta",
        "rows": [
            ("v", "rotate(vec(2,0,1.5), vec(0,0,1), theta)"),
            ("v_para", "proj(v, vec(0,0,1))"),
            ("v_perp", "v - proj(v, vec(0,0,1))"),
        ],
    },
    {
        "id": "reflection",
        "label": "Réflexion (plan XY)",
        "label_en": "Reflection (XY plane)",
        "params": "theta",
        "rows": [
            ("v", "rotate(vec(2,0,1.2), vec(0,0,1), theta)"),
            ("n", "vec(0, 0, 1.5)"),
            ("refl", "v - 2*proj(v, vec(0,0,1))"),
        ],
    },
    {
        "id": "euler_compare",
        "label": "Ordres d'Euler comparés",
        "label_en": "Euler orders compared",
        "params": "a",
        "rows": [
            ("v", "vec(2, 0, 0)"),
            ("xyz", "eul_xyz(a, a, a) * v"),
            ("zyx", "eul_zyx(a, a, a) * v"),
        ],
    },
    {
        "id": "compose_quat",
        "label": "Composition de rotations (quaternions)",
        "label_en": "Composing rotations (quaternions)",
        "params": "theta",
        "rows": [
            ("v", "vec(2, 0, 0)"),
            ("Rz", "qrotate(quat_axis(vec(0,0,1), theta), v)"),
            ("RyRz", "qrotate(qmul(quat_axis(vec(0,1,0), theta), "
                     "quat_axis(vec(0,0,1), theta)), v)"),
        ],
    },
    {
        "id": "gram_schmidt",
        "label": "Gram–Schmidt (orthonormalisation)",
        "label_en": "Gram–Schmidt (orthonormalisation)",
        "params": "theta",
        "rows": [
            ("a", "vec(2, 1, 0)"),
            ("b", "rotate(vec(1,2,0), vec(0,0,1), theta)"),
            ("e1", "1.5 * normalize(a)"),
            ("e2", "1.5 * normalize(b - proj(b, a))"),
        ],
    },
    {
        "id": "circular_motion",
        "label": "Mouvement circulaire (position + vitesse)",
        "label_en": "Circular motion (position + velocity)",
        "params": "theta",
        "rows": [
            ("r", "rotate(vec(2,0,0), vec(0,0,1), theta)"),
            ("v", "rotate(r, vec(0,0,1), 1.5708)"),
        ],
    },
    {
        "id": "lerp_vs_slerp",
        "label": "Lerp vs Slerp",
        "label_en": "Lerp vs slerp",
        "params": "theta",
        "rows": [
            ("a", "vec(2, 0, 0)"),
            ("b", "vec(0, 2, 0)"),
            ("lin", "lerp(a, b, theta)"),
            ("arc", "qrotate(qslerp(quat_axis(vec(0,0,1),0), "
                    "quat_axis(vec(0,0,1),1.5708), theta), a)"),
        ],
    },
)


def get_bench_preset(preset_id):
    """Return the built-in bench preset dict with ``id == preset_id``,
    or ``None``."""
    for p in BUILTIN_BENCHES:
        if p["id"] == preset_id:
            return p
    return None


def make_vector_bench_tree(rows, *, allowed_params=(), key_suffix=""):
    """Build a Geometry Nodes tree drawing a bench of vector arrows.

    Parameters
    ----------
    rows : sequence of (name, expr_str)
        Ordered vector rows. ``name`` is the row's identifier (e.g.
        ``"v1"``) usable by later rows; ``expr_str`` is the vector
        expression (``vec(2,0,0)``, ``rotate(v1, vec(0,0,1), theta)``,
        ``cross(v1, v2)``…).
    allowed_params : tuple of str
        Declared scalar parameters; each becomes a live ``Float`` socket.
    key_suffix : str
        Optional suffix for the node-group name.

    Returns
    -------
    bpy.types.NodeTree
        Fresh tree, ready to bind to a Geometry Nodes modifier.
    """
    rows = [(str(n), str(e)) for n, e in rows]
    if not rows:
        raise ValueError("Le banc doit contenir au moins un vecteur")

    sp = sympy_parser._sympy()

    # Parse every row in order, exposing each result to subsequent rows.
    parsed = []          # list of (name, (Fx, Fy, Fz))
    prior = {}           # name -> sympy.Matrix, injected into later rows
    for name, expr_str in rows:
        try:
            comps = sympy_parser.parse_bench_vector(
                expr_str, allowed_params=tuple(allowed_params), prior=prior,
            )
        except ValueError as e:
            raise ValueError(f"{name} : {e}") from None
        parsed.append((name, comps))
        prior[name] = sp.Matrix(list(comps))

    nt = bpy.data.node_groups.new(
        f"{BENCH_TREE_PREFIX}{key_suffix or 'bench'}", "GeometryNodeTree",
    )

    # --- interface ------------------------------------------------------
    nt.interface.new_socket(
        "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry",
    )
    # Shared parameter sliders.
    for p in allowed_params:
        ps = nt.interface.new_socket(
            p, in_out="INPUT", socket_type="NodeSocketFloat",
        )
        ps.default_value = 0.0
        ps.min_value = -100.0
        ps.max_value = 100.0
        ps.description = (
            f"Paramètre « {p} » — slider live ; faire varier fait bouger "
            f"les vecteurs qui en dépendent"
        )
    # Per-row visibility + material.
    for name, _ in parsed:
        b = nt.interface.new_socket(
            f"Afficher {name}", in_out="INPUT", socket_type="NodeSocketBool",
        )
        b.default_value = True
        b.description = f"Affiche/masque la flèche {name}"
        nt.interface.new_socket(
            f"Matériau · {name}", in_out="INPUT",
            socket_type="NodeSocketMaterial",
        ).description = f"Matériau (couleur) de la flèche {name}"

    # --- build ----------------------------------------------------------
    nb = compiler.NodeBuilder(nt)
    group_in = nb.add("NodeGroupInput", x=-1200, y=0)
    group_out = nb.add("NodeGroupOutput", x=1800, y=0)
    param_sockets = {p: group_in.outputs[p] for p in allowed_params}

    vec_ng = vecteur.get_vecteur_node_group()
    # Constant origin (0, 0, 0): a CombineXYZ with default-zero inputs.
    origin = nb.add("ShaderNodeCombineXYZ", label="Origine (0,0,0)",
                    x=200, y=400)

    join = nb.add("GeometryNodeJoinGeometry", label="Banc", x=1500, y=0)

    y = 0
    for name, comps in parsed:
        ext_sock = compiler.compile_vector_components(
            nb, comps, param_sockets, x=300, y=y, label=name,
        )
        arrow = nb.add("GeometryNodeGroup", label=f"{name}", x=700, y=y)
        arrow.node_tree = vec_ng
        try:
            nb.link(origin.outputs["Vector"], arrow.inputs["orig"])
            nb.link(ext_sock, arrow.inputs["ext"])
        except (KeyError, AttributeError):
            nb.link(origin.outputs[0], arrow.inputs[0])
            nb.link(ext_sock, arrow.inputs[1])
        out = (arrow.outputs["Geometry"]
               if "Geometry" in arrow.outputs else arrow.outputs[0])

        set_mat = nb.add("GeometryNodeSetMaterial",
                         label=f"{name}: matériau", x=950, y=y)
        nb.link(out, set_mat.inputs["Geometry"])
        nb.link(group_in.outputs[f"Matériau · {name}"],
                set_mat.inputs["Material"])
        out = set_mat.outputs["Geometry"]

        switch = nb.add("GeometryNodeSwitch", label=f"Afficher {name}?",
                        x=1200, y=y)
        switch.input_type = "GEOMETRY"
        try:
            nb.link(group_in.outputs[f"Afficher {name}"],
                    switch.inputs["Switch"])
            nb.link(out, switch.inputs["True"])
        except KeyError:
            nb.link(group_in.outputs[f"Afficher {name}"], switch.inputs[0])
            nb.link(out, switch.inputs[2])
        sw_out = (switch.outputs["Output"]
                  if "Output" in switch.outputs else switch.outputs[0])
        nb.link(sw_out, join.inputs["Geometry"])
        y -= 350

    nb.link(join.outputs["Geometry"], group_out.inputs[0])

    # --- metadata -------------------------------------------------------
    nt["realfn_kind"] = "vector_bench"
    nt["realfn_params"] = list(allowed_params)
    nt["realfn_bench_names"] = [n for n, _ in parsed]
    nt["realfn_bench_exprs"] = [e for _, e in rows]
    # Stringified components, one comma-joined entry per row, for the panel.
    nt["realfn_bench_text"] = [
        ", ".join(str(sp.sstr(c)) for c in comps) for _, comps in parsed
    ]
    return nt
