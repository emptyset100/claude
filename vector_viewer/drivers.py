"""Gestion des drivers Python sur les sockets internes des nodes
Group/Group.001/Group.002 du wrapper « Geometry Nodes »."""

import re
import unicodedata

import bpy
from . import math_core, nodegroups
from .properties import MODIFIER_NAME as _MODIFIER_NAME


# Préfixes des fonctions injectées dans driver_namespace pour le
# Vector Viewer simple. Suffixées par un slug de la scène pour permettre
# à plusieurs scènes de coexister sans collision (le driver_namespace
# est globalement Blender, pas par scène).
DNS_BASE_KEYS = ("r_num", "v_num", "a_num")


def _scene_suffix(scene):
    """Slug ASCII dérivé du nom de la scène, vide si scene est None.

    "Scene"     → "_scene"
    "Compare A" → "_compare_a"
    """
    if scene is None:
        return ""
    nfkd = unicodedata.normalize('NFKD', scene.name)
    ascii_name = ''.join(c for c in nfkd if not unicodedata.combining(c))
    slug = re.sub(r'[^A-Za-z0-9]+', '_', ascii_name).strip('_').lower()
    return ('_' + slug) if slug else ""


def _dns_key(scene, base):
    """Nom complet d'une fonction dans driver_namespace (incl. suffixe scène)."""
    return base + _scene_suffix(scene)


def refresh_driver_namespace(props, *, scene=None):
    """(Re)compile r_num / v_num / a_num depuis ``props`` et les place
    dans ``bpy.app.driver_namespace`` avec un suffixe dérivé du nom de
    la scène."""
    r_num, v_num, a_num = math_core.build_kinematics(
        props.x_expr, props.y_expr, props.z_expr,
    )
    suffix = _scene_suffix(scene)
    bpy.app.driver_namespace['r_num' + suffix] = r_num
    bpy.app.driver_namespace['v_num' + suffix] = v_num
    bpy.app.driver_namespace['a_num' + suffix] = a_num


def clear_driver_namespace(*, scene=None):
    """Retire r_num/v_num/a_num du namespace pour la scène donnée."""
    suffix = _scene_suffix(scene)
    for k in DNS_BASE_KEYS:
        bpy.app.driver_namespace.pop(k + suffix, None)


def _socket_identifier(wrapper_tree, socket_name):
    """Retourne l'identifiant interne stable d'un socket d'interface
    (de la forme ``Socket_N`` ou ``Input_N``), pour pouvoir le référencer
    dans les expressions de driver. Retourne ``None`` si introuvable."""
    for item in wrapper_tree.interface.items_tree:
        if (getattr(item, 'in_out', None) == 'INPUT'
                and getattr(item, 'name', None) == socket_name):
            return item.identifier
    return None


def _add_modifier_var(driver, var_name, host_name, socket_id):
    """Ajoute à ``driver`` une variable ``var_name`` de type SINGLE_PROP
    qui lit ``bpy.data.objects[host].modifiers[MOD][socket_id]``."""
    var = driver.variables.new()
    var.name = var_name
    var.type = 'SINGLE_PROP'
    target = var.targets[0]
    target.id_type = 'OBJECT'
    target.id = bpy.data.objects.get(host_name)
    target.data_path = f'modifiers["{_MODIFIER_NAME}"]["{socket_id}"]'


def attach_socket_drivers(wrapper_tree, *, fps, t0, host_name, scene=None,
                          scale_v=1.0, scale_a=1.0):
    """Écrit les drivers Python sur ``inputs[0]/inputs[1].default_value``
    des nodes Group, Group.001, Group.002 du wrapper.

    Les échelles v et a sont lues en LIVE via des variables de driver
    pointant sur les sockets ``Échelle v`` et ``Échelle a`` exposés par
    le wrapper. Modifier ces sockets dans le panneau (ou directement
    dans Properties › Modifiers) actualise immédiatement les flèches.

    Args:
        wrapper_tree: le node tree du wrapper.
        fps, t0: cadence et offset temporel (frame 0 ↔ t0).
        host_name: nom de l'objet portant le modifier (nécessaire pour
            que les variables de driver puissent le référencer).
        scene: scène courante, utilisée pour suffixer les noms de
            fonctions r_num/v_num/a_num dans le driver_namespace.
        scale_v, scale_a: valeurs initiales des sockets d'échelle.
    """
    # Suffixe scène pour les noms de fonctions dans driver_namespace
    suffix = _scene_suffix(scene)
    r_num_name = 'r_num' + suffix
    v_num_name = 'v_num' + suffix
    a_num_name = 'a_num' + suffix

    # Pré-remplir les sockets d'échelle dans l'interface — les drivers
    # liront directement ces valeurs via les variables `sv` / `sa`.
    sv_id = _socket_identifier(wrapper_tree, nodegroups.SCALE_V_SOCKET)
    sa_id = _socket_identifier(wrapper_tree, nodegroups.SCALE_A_SOCKET)
    if sv_id is None or sa_id is None:
        raise RuntimeError(
            "Sockets d'échelle introuvables dans le wrapper — "
            "le wrapper doit avoir été reconstruit avec la version "
            "courante de geometry_nodes_1_node_group."
        )

    # On écrit les valeurs par défaut directement sur le modifier de
    # l'objet hôte, pas sur l'interface (l'interface est partagée entre
    # toutes les utilisations du node group).
    obj = bpy.data.objects.get(host_name)
    if obj is not None and _MODIFIER_NAME in obj.modifiers:
        mod = obj.modifiers[_MODIFIER_NAME]
        try:
            mod[sv_id] = float(scale_v)
            mod[sa_id] = float(scale_a)
        except (KeyError, RuntimeError):
            pass  # le modifier n'expose pas encore ces sockets — recréé au build

    # Conversion frame Blender → temps physique (en secondes), calée sur
    # frame 0 = t0
    time = f"(frame/{fps} + {t0})"

    plans = [
        # Position : ext = r(t) (pas d'échelle)
        ("Group",     1, [(f"{r_num_name}({time})[{a}]", False, False)
                          for a in range(3)]),

        # Vitesse : orig = r(t), ext = r(t) + sv·v(t)
        ("Group.001", 0, [(f"{r_num_name}({time})[{a}]", False, False)
                          for a in range(3)]),
        ("Group.001", 1, [(f"{r_num_name}({time})[{a}] "
                           f"+ sv*{v_num_name}({time})[{a}]",
                           True, False) for a in range(3)]),

        # Accélération : orig = r(t) + sv·v(t),
        #                ext  = orig + sa·a(t)
        ("Group.002", 0, [(f"{r_num_name}({time})[{a}] "
                           f"+ sv*{v_num_name}({time})[{a}]",
                           True, False) for a in range(3)]),
        ("Group.002", 1, [(f"{r_num_name}({time})[{a}] "
                           f"+ sv*{v_num_name}({time})[{a}]"
                           f" + sa*{a_num_name}({time})[{a}]",
                           True, True) for a in range(3)]),
    ]

    for node_name, sock_idx, exprs in plans:
        if node_name not in wrapper_tree.nodes:
            print(f"[VectorViewer] Node introuvable : {node_name}")
            continue
        sock = wrapper_tree.nodes[node_name].inputs[sock_idx]

        # Nettoie d'éventuels drivers existants sur ce socket
        try:
            sock.driver_remove("default_value")
        except Exception:
            pass

        # Crée 3 drivers (un par composante x/y/z)
        fcurves = sock.driver_add("default_value")
        for fc, (expr, needs_sv, needs_sa) in zip(fcurves, exprs):
            drv = fc.driver
            drv.type = 'SCRIPTED'
            drv.expression = expr
            # Variables de driver pour les échelles utilisées par cette
            # expression. On n'ajoute QUE celles qui sont référencées
            # dans l'expression — Blender émet un warning sinon.
            if needs_sv:
                _add_modifier_var(drv, "sv", host_name, sv_id)
            if needs_sa:
                _add_modifier_var(drv, "sa", host_name, sa_id)

        print(f"  ✓ {node_name}.inputs[{sock_idx}] : 3 drivers attachés")
