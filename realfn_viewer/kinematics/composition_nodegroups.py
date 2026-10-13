"""Construction du wrapper Geometry Nodes pour la visualisation de la
composition des référentiels non galiléens.

Le wrapper contient :

1. Onze flèches cinématiques (visibilité réglable indépendamment) :
       OO'  - vecteur position de O' dans R
       O'M  - vecteur position de M depuis O' (en coordonnées de R)
       OM   - vecteur position absolue de M depuis O (= OO' + O'M)
       vr, ve, va  - composition des vitesses
       ar, ae, ac, aa  - composition des accélérations (Coriolis incluse)
       Ω    - vecteur rotation instantanée de R'/R, ancré à O'(t)

2. Deux trièdres directs (un toggle par trièdre) :
       Trièdre R  : axes (ê_x, ê_y, ê_z) ancrés à l'origine du monde
       Trièdre R' : axes (R·ê_x, R·ê_y, R·ê_z) ancrés à O'(t)

3. Trois trajectoires (tubes courbes alimentés par des objets Curve
   échantillonnés à t = t_start..t_start+t_duration au build) :
       traj_OOp : chemin de O'(t) dans R
       traj_OM  : chemin absolu de M dans R
       traj_OpM : chemin de M tel que vu de R'  (= R(t)·r'(t))

Chaque flèche traverse :
    arrow sub-group → Set Material → Switch (geometry) → Join Geometry

Chaque trajectoire traverse :
    Object Info → Curve to Mesh ← Curve Circle (Radius) → Set Material
    → Switch (geometry) → Join Geometry

Les matériaux sont émissifs (cf. ``materials.PALETTE``) pour rester
lisibles indépendamment de l'éclairage de la scène.
"""

import bpy

from . import nodegroups
from . import materials


# Nom du wrapper (clé pour bpy.data.node_groups)
COMP_WRAPPER_NAME = "Geometry Nodes (Composition)"


# Spec des 11 flèches cinématiques :
#   (node_name, builder_fn, bool_socket_label, material_name)
ARROWS_SPEC = (
    ("OOp",   nodegroups.position_1_node_group,     "Afficher OO'",            "VV_OOp"),
    ("OpM",   nodegroups.position_1_node_group,     "Afficher O'M",            "VV_OpM"),
    ("OM",    nodegroups.position_1_node_group,     "Afficher OM",             "VV_OM"),
    ("vr",    nodegroups.vitesse_1_node_group,      "Afficher v_r",            "VV_vr"),
    ("ve",    nodegroups.vitesse_1_node_group,      "Afficher v_e",            "VV_ve"),
    ("va",    nodegroups.vitesse_1_node_group,      "Afficher v_a",            "VV_va"),
    ("ar",    nodegroups.acceleration_1_node_group, "Afficher a_r",            "VV_ar"),
    ("ae",    nodegroups.acceleration_1_node_group, "Afficher a_e",            "VV_ae"),
    ("ac",    nodegroups.acceleration_1_node_group, "Afficher a_c (Coriolis)", "VV_ac"),
    ("aa",    nodegroups.acceleration_1_node_group, "Afficher a_a",            "VV_aa"),
    ("Omega", nodegroups.vitesse_1_node_group,      "Afficher Omega",          "VV_Omega"),
)


# Spec des 6 axes de trièdres :
#   (node_name, builder_fn, material_name, frame_id)
# frame_id ∈ {"R", "Rp"} : indique à quel toggle l'axe est rattaché.
# Trièdre R  : sockets statiques (default_value, calé à axis_length au build).
# Trièdre R' : sockets pilotés par drivers (cf. composition.attach_socket_drivers).
TRIPOD_SPEC = (
    ("R_x",  nodegroups.position_1_node_group, "VV_R_x",  "R"),
    ("R_y",  nodegroups.position_1_node_group, "VV_R_y",  "R"),
    ("R_z",  nodegroups.position_1_node_group, "VV_R_z",  "R"),
    ("Rp_x", nodegroups.position_1_node_group, "VV_Rp_x", "Rp"),
    ("Rp_y", nodegroups.position_1_node_group, "VV_Rp_y", "Rp"),
    ("Rp_z", nodegroups.position_1_node_group, "VV_Rp_z", "Rp"),
)


# Labels des sockets booléens des trièdres
SHOW_R_LABEL  = "Afficher repère R"
SHOW_RP_LABEL = "Afficher repère R'"


# Spec des 3 trajectoires :
#   (node_name, bool_socket_label, material_name, traj_object_name)
# Les courbes sources sont créées au build dans ``composition_operators``
# avec le nom donné par ``traj_object_name`` ; le wrapper les récupère
# par référence via le node Object Info.
TRAJECTORIES_SPEC = (
    ("traj_OOp", "Afficher trajectoire OO'", "VV_traj_OOp", "VV_traj_OOp"),
    ("traj_OM",  "Afficher trajectoire OM",  "VV_traj_OM",  "VV_traj_OM"),
    ("traj_OpM", "Afficher trajectoire O'M", "VV_traj_OpM", "VV_traj_OpM"),
)

# Label du socket flottant pour le rayon des tubes-trajectoires
TRAJ_RADIUS_LABEL = "Rayon des trajectoires"

# Labels des sockets Float pour les échelles, lus en LIVE par les
# drivers. Modifier ces sockets met à jour les flèches sans rebuild.
SCALE_V_LABEL     = "Échelle v"
SCALE_A_LABEL     = "Échelle a"
SCALE_OMEGA_LABEL = "Échelle Ω"


def composition_wrapper_node_group(node_tree_names: dict, axis_length: float,
                                    trajectory_objs: dict | None = None,
                                    traj_radius_default: float = 0.015,
                                    scale_v_default: float = 1.0,
                                    scale_a_default: float = 1.0,
                                    scale_omega_default: float = 1.0):
    """Construit le wrapper de composition.

    Args:
        node_tree_names: dict prérempli pour les sub-groups Position /
            Vitesse / Acceleration (cf. ``operators._ensure_subgroups``).
        axis_length: longueur des arêtes des trièdres. Bake-time, donc
            la modifier impose un Build pour la voir.
        trajectory_objs: dict ``{nom_objet: bpy.types.Object}`` pour
            les courbes-trajectoires créées en amont du build. Si None
            ou si une clé manque, le node Object Info correspondant est
            laissé sans référence (la trajectoire ne s'affichera pas).
        traj_radius_default: rayon initial du tube-trajectoire (les
            trajectoires sont rendues comme tubes via Curve Circle).
    """
    # Garantit que tous les matériaux existent
    materials.ensure_all()

    cw = bpy.data.node_groups.new(
        type='GeometryNodeTree', name=COMP_WRAPPER_NAME
    )
    cw.is_modifier = True
    cw.show_modifier_manage_panel = True

    # ── Interface ──────────────────────────────────────────────────────
    cw.interface.new_socket(
        name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry'
    )
    cw.interface.new_socket(
        name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry'
    )

    # 11 booléens d'affichage des flèches (ordre = ARROWS_SPEC)
    for _, _, label, _ in ARROWS_SPEC:
        s = cw.interface.new_socket(
            name=label, in_out='INPUT', socket_type='NodeSocketBool'
        )
        s.default_value = True

    # 2 booléens d'affichage des trièdres
    for label in (SHOW_R_LABEL, SHOW_RP_LABEL):
        s = cw.interface.new_socket(
            name=label, in_out='INPUT', socket_type='NodeSocketBool'
        )
        s.default_value = True

    # 3 booléens d'affichage des trajectoires (cachées par défaut :
    # elles encombrent vite la scène avec les flèches)
    for _, label, _, _ in TRAJECTORIES_SPEC:
        s = cw.interface.new_socket(
            name=label, in_out='INPUT', socket_type='NodeSocketBool'
        )
        s.default_value = False

    # 1 flottant pour le rayon des tubes-trajectoires
    s = cw.interface.new_socket(
        name=TRAJ_RADIUS_LABEL, in_out='INPUT', socket_type='NodeSocketFloat'
    )
    s.default_value = float(traj_radius_default)
    s.min_value = 0.0
    s.max_value = 10.0

    # 3 flottants d'échelle (lus par les drivers via variable de driver,
    # cf. composition.attach_socket_drivers). Modifier ces valeurs en
    # live met à jour les flèches sans rebuild.
    for label, default_val in (
        (SCALE_V_LABEL,     scale_v_default),
        (SCALE_A_LABEL,     scale_a_default),
        (SCALE_OMEGA_LABEL, scale_omega_default),
    ):
        s = cw.interface.new_socket(
            name=label, in_out='INPUT', socket_type='NodeSocketFloat'
        )
        s.default_value = float(default_val)
        s.min_value = 0.0
        s.max_value = 100.0

    # ── Nodes périphériques ────────────────────────────────────────────
    out_node = cw.nodes.new("NodeGroupOutput")
    out_node.name = "Group Output"
    out_node.is_active_output = True

    in_node = cw.nodes.new("NodeGroupInput")
    in_node.name = "Group Input"

    join = cw.nodes.new("GeometryNodeJoinGeometry")
    join.name = "Join Geometry"

    # ── Layout constantes ──────────────────────────────────────────────
    Y_TOP   = 1200.0
    Y_STEP  = -180.0
    X_INST  = -400.0
    X_MAT   =  -50.0
    X_SWCH  =  300.0

    # Indices Group Input :
    #   [0]                              = Geometry input
    #   [1 .. N_arr]                     = booléens des flèches
    #   [N_arr+1, N_arr+2]               = booléens R, R'
    #   [N_arr+3 .. N_arr+2+N_traj]      = booléens trajectoires
    #   [N_arr+3+N_traj]                 = rayon trajectoires (Float)
    #   [N_arr+4+N_traj]                 = scale_v (Float, lu par drivers)
    #   [N_arr+5+N_traj]                 = scale_a (Float, lu par drivers)
    #   [N_arr+6+N_traj]                 = scale_omega (Float, lu par drivers)
    N_ARR = len(ARROWS_SPEC)
    N_TRAJ = len(TRAJECTORIES_SPEC)
    BOOL_OFFSET_ARROWS = 1
    IDX_R_BOOL  = 1 + N_ARR
    IDX_RP_BOOL = 1 + N_ARR + 1
    IDX_TRAJ_FIRST = 1 + N_ARR + 2
    IDX_TRAJ_RADIUS = 1 + N_ARR + 2 + N_TRAJ
    IDX_SCALE_V     = 1 + N_ARR + 3 + N_TRAJ
    IDX_SCALE_A     = 1 + N_ARR + 4 + N_TRAJ
    IDX_SCALE_OMEGA = 1 + N_ARR + 5 + N_TRAJ

    def _make_arrow_chain(node_name, builder_fn, mat_name, y, sw_bool_idx):
        """Construit arrow → set_material → switch → join, et renvoie
        le node ``arrow`` (pour pouvoir le configurer après).
        Le booléen Switch est tiré de in_node.outputs[sw_bool_idx]."""
        sub_name = node_tree_names[builder_fn]

        arrow = cw.nodes.new("GeometryNodeGroup")
        arrow.name = node_name
        arrow.node_tree = bpy.data.node_groups[sub_name]
        arrow.inputs[0].default_value = (0.0, 0.0, 0.0)
        arrow.inputs[1].default_value = (0.0, 0.0, 0.0)
        arrow.location = (X_INST, y)

        sm = cw.nodes.new("GeometryNodeSetMaterial")
        sm.name = f"SetMat {node_name}"
        sm.inputs["Material"].default_value = bpy.data.materials[mat_name]
        sm.location = (X_MAT, y)

        sw = cw.nodes.new("GeometryNodeSwitch")
        sw.name = f"Switch {node_name}"
        sw.input_type = 'GEOMETRY'
        sw.location = (X_SWCH, y)

        # Câblage : arrow → set_material → switch.True → join
        cw.links.new(arrow.outputs[0], sm.inputs[0])
        cw.links.new(sm.outputs[0], sw.inputs[2])
        cw.links.new(in_node.outputs[sw_bool_idx], sw.inputs[0])
        cw.links.new(sw.outputs[0], join.inputs[0])

        return arrow

    # ── Les flèches cinématiques (11) ──────────────────────────────────
    for i, (node_name, builder_fn, _label, mat_name) in enumerate(ARROWS_SPEC):
        y = Y_TOP + i * Y_STEP
        _make_arrow_chain(
            node_name, builder_fn, mat_name, y, BOOL_OFFSET_ARROWS + i
        )

    # ── Les 6 axes de trièdres ─────────────────────────────────────────
    R_AXIS_TIPS = {
        "R_x": (axis_length, 0.0, 0.0),
        "R_y": (0.0, axis_length, 0.0),
        "R_z": (0.0, 0.0, axis_length),
    }

    for j, (node_name, builder_fn, mat_name, frame_id) in enumerate(TRIPOD_SPEC):
        y = Y_TOP + (len(ARROWS_SPEC) + j) * Y_STEP
        sw_bool_idx = IDX_R_BOOL if frame_id == "R" else IDX_RP_BOOL
        arrow = _make_arrow_chain(
            node_name, builder_fn, mat_name, y, sw_bool_idx
        )
        # Trièdre R : valeurs statiques. Trièdre R' : laissées à zéro
        # car les drivers prennent le relais.
        if frame_id == "R":
            arrow.inputs[0].default_value = (0.0, 0.0, 0.0)
            arrow.inputs[1].default_value = R_AXIS_TIPS[node_name]

    # ── Les 3 trajectoires ─────────────────────────────────────────────
    # Profile circle partagé : son socket Radius est piloté par l'input
    # `Rayon des trajectoires` du wrapper, ce qui permet à l'utilisateur
    # de modifier l'épaisseur sans rebuild.
    n_pre_traj_chains = len(ARROWS_SPEC) + len(TRIPOD_SPEC)
    y_traj_top = Y_TOP + n_pre_traj_chains * Y_STEP
    y_circle = y_traj_top + 0.5 * Y_STEP

    profile_circle = cw.nodes.new("GeometryNodeCurvePrimitiveCircle")
    profile_circle.name = "Profile Circle (trajectories)"
    profile_circle.mode = 'RADIUS'
    # Le socket Resolution garde sa valeur par défaut (32) ; on baisse
    # à 8 pour des tubes économiques (les trajectoires sont décoratives).
    profile_circle.inputs["Resolution"].default_value = 8
    profile_circle.location = (X_INST - 250.0, y_circle)
    cw.links.new(
        in_node.outputs[IDX_TRAJ_RADIUS],
        profile_circle.inputs["Radius"],
    )

    trajectory_objs = trajectory_objs or {}

    for k, (node_name, _label, mat_name, traj_obj_name) in enumerate(TRAJECTORIES_SPEC):
        y = y_traj_top + k * Y_STEP

        # Object Info : récupère la courbe-trajectoire pré-générée
        oi = cw.nodes.new("GeometryNodeObjectInfo")
        oi.name = f"ObjInfo {node_name}"
        oi.transform_space = 'ORIGINAL'  # coords objet, pas world
        oi.location = (X_INST, y)
        traj_obj = trajectory_objs.get(traj_obj_name)
        if traj_obj is not None:
            oi.inputs["Object"].default_value = traj_obj

        # Curve to Mesh : tube via le profile circle partagé
        ctm = cw.nodes.new("GeometryNodeCurveToMesh")
        ctm.name = f"CurveToMesh {node_name}"
        ctm.location = (X_INST + 200.0, y)
        cw.links.new(oi.outputs["Geometry"], ctm.inputs["Curve"])
        cw.links.new(profile_circle.outputs["Curve"], ctm.inputs["Profile Curve"])

        # Set Material
        sm = cw.nodes.new("GeometryNodeSetMaterial")
        sm.name = f"SetMat {node_name}"
        sm.inputs["Material"].default_value = bpy.data.materials[mat_name]
        sm.location = (X_MAT, y)
        cw.links.new(ctm.outputs[0], sm.inputs[0])

        # Switch (visibilité)
        sw = cw.nodes.new("GeometryNodeSwitch")
        sw.name = f"Switch {node_name}"
        sw.input_type = 'GEOMETRY'
        sw.location = (X_SWCH, y)
        cw.links.new(in_node.outputs[IDX_TRAJ_FIRST + k], sw.inputs[0])
        cw.links.new(sm.outputs[0], sw.inputs[2])

        # Vers Join
        cw.links.new(sw.outputs[0], join.inputs[0])

    # ── Layout des nodes périphériques ─────────────────────────────────
    n_chains = len(ARROWS_SPEC) + len(TRIPOD_SPEC) + len(TRAJECTORIES_SPEC)
    y_mid = Y_TOP + (n_chains // 2) * Y_STEP

    in_node.location  = (X_INST - 350.0, y_mid)
    join.location     = (X_SWCH + 250.0, y_mid)
    out_node.location = (X_SWCH + 500.0, y_mid)

    in_node.width  = 160.0
    join.width     = 140.0
    out_node.width = 140.0

    # Sortie
    cw.links.new(join.outputs[0], out_node.inputs[0])

    return cw
