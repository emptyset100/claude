"""Opérateurs : construction et suppression de l'ensemble
(node groups + objet hôte + drivers + timeline)."""

import bpy
import typing

from . import nodegroups, drivers as drv_mod, properties as props_mod, materials
from .properties import MODIFIER_NAME


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

WRAPPER_GROUP_NAME = "Geometry Nodes"  # nom donné par geometry_nodes_1_node_group
SUBGROUP_NAMES     = (
    nodegroups.SUBGROUP_POSITION_NAME,
    nodegroups.SUBGROUP_VITESSE_NAME,
    nodegroups.SUBGROUP_ACCELERATION_NAME,
)

# Nom de l'objet Curve qui porte les points échantillonnés de la
# trajectoire OM. Caché ; sert uniquement de source au node Object Info
# du wrapper.
TRAJECTORY_OBJ_NAME = "VV_traj_OM"

# Borne supérieure du nombre d'échantillons : au-delà, la résolution
# n'apporte plus rien à l'œil et alourdit la scène.
TRAJ_MAX_SAMPLES = 2000


def _purge_simple_wrapper():
    """Supprime uniquement le wrapper du Vector Viewer simple.
    Les sub-groups Position/Vitesse/Acceleration sont conservés car
    ils peuvent être partagés avec le wrapper de composition."""
    wrapper = bpy.data.node_groups.get(WRAPPER_GROUP_NAME)
    if wrapper is not None:
        bpy.data.node_groups.remove(wrapper)


def _purge_orphan_subgroups():
    """Supprime Position/Vitesse/Acceleration s'ils n'ont plus aucun
    utilisateur (= aucun wrapper ne les référence)."""
    for name in SUBGROUP_NAMES:
        ng = bpy.data.node_groups.get(name)
        if ng is not None and ng.users == 0:
            bpy.data.node_groups.remove(ng)


def _ensure_subgroups(node_tree_names: dict[typing.Callable, str]):
    """Crée les sub-groups Position/Vitesse/Acceleration s'ils manquent
    ou s'ils sont d'une version obsolète ; sinon les réutilise (en
    peuplant ``node_tree_names``).

    La détection « obsolète » repose sur la propriété custom
    ``vv_subgroup_version`` posée à la création. Si cette propriété
    manque (sub-group d'une ancienne installation, ou groupe étranger
    portant le même nom), on supprime et on recrée — c'est plus sûr
    que de risquer un câblage sur un graphe inattendu."""
    expected_version = nodegroups.SUBGROUP_SCHEMA_VERSION
    for fn, default_name in (
        (nodegroups.position_1_node_group,     nodegroups.SUBGROUP_POSITION_NAME),
        (nodegroups.vitesse_1_node_group,      nodegroups.SUBGROUP_VITESSE_NAME),
        (nodegroups.acceleration_1_node_group, nodegroups.SUBGROUP_ACCELERATION_NAME),
    ):
        ng = bpy.data.node_groups.get(default_name)
        if ng is not None:
            stored_version = ng.get("vv_subgroup_version", None)
            if stored_version != expected_version:
                # Sub-group obsolète ou étranger → on le supprime
                # (on ne peut pas le retirer si encore référencé, mais
                # _purge_*_wrapper a déjà tourné donc users == 0).
                if ng.users == 0:
                    bpy.data.node_groups.remove(ng)
                    ng = None
                else:
                    print(f"[VectorViewer] {default_name} obsolète mais "
                          f"encore référencé ({ng.users} users) — "
                          f"réutilisation forcée, attention aux "
                          f"incohérences possibles.")
        if ng is None:
            ng = fn(node_tree_names)
        node_tree_names[fn] = ng.name


def _purge_trajectory_object():
    """Supprime l'objet Curve de la trajectoire OM et son data-block.
    Idempotent : ne fait rien si l'objet n'existe pas (premier build,
    suppression manuelle, …)."""
    obj = bpy.data.objects.get(TRAJECTORY_OBJ_NAME)
    if obj is None:
        return
    curve_data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if curve_data is not None and curve_data.users == 0:
        bpy.data.curves.remove(curve_data)


def _sample_trajectory(fn, t_start, t_duration, n):
    """Échantillonne ``fn(t) → (x, y, z)`` en ``n`` points sur
    ``[t_start, t_start + t_duration]``."""
    if n < 2:
        n = 2
    out = []
    step = t_duration / (n - 1)
    for i in range(n):
        t = t_start + i * step
        v = fn(t)
        out.append((float(v[0]), float(v[1]), float(v[2])))
    return out


def _make_trajectory_curve(name, points):
    """Crée un objet Curve POLY 3D à partir d'une liste de tuples (x,y,z),
    le lie à la collection courante, le cache, et le retourne. Les anciens
    objets de même nom sont supprimés au préalable."""
    old = bpy.data.objects.get(name)
    if old is not None:
        old_data = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if old_data is not None and old_data.users == 0:
            bpy.data.curves.remove(old_data)

    cd = bpy.data.curves.new(name, 'CURVE')
    cd.dimensions = '3D'
    spline = cd.splines.new('POLY')
    # ``new('POLY')`` crée 1 point initial ; on ajoute les n-1 autres.
    spline.points.add(len(points) - 1)
    for i, (x, y, z) in enumerate(points):
        # Le 4e composant w est le poids du point rationnel : sans objet
        # pour les splines POLY, mais doit valoir 1.0 pour ne pas déformer.
        spline.points[i].co = (x, y, z, 1.0)

    obj = bpy.data.objects.new(name, cd)
    bpy.context.collection.objects.link(obj)
    # Caché à la vue mais conservé dans le dépendence graph (Object Info
    # accède à la geometry évaluée même quand hide_set est True).
    obj.hide_set(True)
    obj.hide_render = True
    return obj


def _generate_trajectory_curve(props, scene=None):
    """Échantillonne r(t) depuis ``driver_namespace['r_num_<scene>']`` et crée
    l'objet Curve correspondant. Doit être appelé APRÈS
    ``drv_mod.refresh_driver_namespace(props, scene=scene)`` qui peuple
    le namespace.

    Retourne l'objet créé, ou None si ``r_num`` n'est pas disponible."""
    r_num = bpy.app.driver_namespace.get(drv_mod._dns_key(scene, 'r_num'))
    if r_num is None:
        return None

    # 1 échantillon par frame d'animation, plafonné, minimum 2.
    n = int(round(props.fps * props.t_duration)) + 1
    n = max(2, min(n, TRAJ_MAX_SAMPLES))

    points = _sample_trajectory(r_num, props.t_start, props.t_duration, n)
    return _make_trajectory_curve(TRAJECTORY_OBJ_NAME, points)


def _build_all_node_groups(trajectory_obj=None, traj_radius_default=0.015,
                            axis_length=1.0, scale_v=1.0, scale_a=1.0):
    """Reconstruit le wrapper du Vector Viewer simple.
    Réutilise les sub-groups existants (compatibilité avec un éventuel
    wrapper de composition vivant en parallèle).

    Si ``trajectory_obj`` est passé, il est référencé par le node
    Object Info de la chaîne trajectoire."""
    _purge_simple_wrapper()

    node_tree_names: dict[typing.Callable, str] = {}
    _ensure_subgroups(node_tree_names)

    wrapper = nodegroups.geometry_nodes_1_node_group(
        node_tree_names,
        trajectory_obj=trajectory_obj,
        traj_radius_default=traj_radius_default,
        axis_length=axis_length,
        scale_v_default=scale_v,
        scale_a_default=scale_a,
    )
    node_tree_names[nodegroups.geometry_nodes_1_node_group] = wrapper.name

    return wrapper


def _make_host_object(wrapper_tree, name):
    """Crée (ou réutilise) un objet hôte minimal — mesh à 1 vertex —
    portant un modifier Geometry Nodes pointant vers ``wrapper_tree``."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        mesh = bpy.data.meshes.new(name + "_mesh")
        mesh.from_pydata([(0.0, 0.0, 0.0)], [], [])
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)

    # Récupère ou crée le modifier
    mod = obj.modifiers.get(MODIFIER_NAME)
    if mod is None:
        mod = obj.modifiers.new(MODIFIER_NAME, type='NODES')
    mod.node_group = wrapper_tree

    return obj


def _configure_timeline(scene, props):
    """Cale la timeline sur [0, durée·fps] et passe au frame 0."""
    scene.render.fps = props.fps
    scene.frame_start = 0
    scene.frame_end = int(round(props.t_duration * props.fps))
    scene.frame_set(0)


# ----------------------------------------------------------------------------
# Opérateurs
# ----------------------------------------------------------------------------

class VECTORVIEWER_OT_build(bpy.types.Operator):
    """Construit (ou reconstruit) les node groups, l'objet hôte, les
    drivers, et configure la timeline depuis les paramètres du panneau."""

    bl_idname = "vector_viewer.build"
    bl_label = "Construire / Mettre à jour"
    bl_description = (
        "Parse l'équation, (re)crée les node groups, l'objet hôte, "
        "attache les drivers et configure la timeline"
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        props = scene.vector_viewer

        # 1. Compile r/v/a et les place dans le driver_namespace
        try:
            drv_mod.refresh_driver_namespace(props, scene=scene)
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except ImportError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        # 2. Purge et regénération de la courbe-trajectoire (échantillonne
        # r(t) tout juste compilé sur [t_start, t_start+T])
        _purge_trajectory_object()
        traj_obj = _generate_trajectory_curve(props, scene=scene)

        # 3. (Re)construit le wrapper, en lui passant la référence à la
        # courbe-trajectoire pour que le node Object Info pointe dessus.
        wrapper = _build_all_node_groups(
            trajectory_obj=traj_obj,
            traj_radius_default=props.traj_radius,
            axis_length=props.axis_length,
            scale_v=props.scale_v,
            scale_a=props.scale_a,
        )

        # 4. Crée / met à jour l'objet hôte
        obj = _make_host_object(wrapper, props.host_name)

        # 5. Attache les drivers sur les sockets internes du wrapper
        drv_mod.attach_socket_drivers(
            wrapper,
            fps=props.fps,
            t0=props.t_start,
            host_name=props.host_name,
            scene=scene,
            scale_v=props.scale_v,
            scale_a=props.scale_a,
        )

        # 6. Synchronise les cases à cocher du panneau et le rayon de
        # la trajectoire vers les sockets exposés du modifier
        props_mod.apply_show_flags(props)

        # 7. Configure la timeline
        _configure_timeline(scene, props)

        # 8. Sélectionne et active l'objet
        for o in context.selected_objects:
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj

        self.report(
            {'INFO'},
            f"« {obj.name} » prêt — timeline 0 → {scene.frame_end} "
            f"(t ∈ [{props.t_start:.2f}, "
            f"{props.t_start + props.t_duration:.2f}] s)"
        )
        return {'FINISHED'}


class VECTORVIEWER_OT_clear(bpy.types.Operator):
    """Supprime l'objet hôte et les node groups associés."""

    bl_idname = "vector_viewer.clear"
    bl_label = "Supprimer"
    bl_description = "Supprime l'objet hôte et les quatre node groups"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.vector_viewer

        # Objet hôte
        obj = bpy.data.objects.get(props.host_name)
        if obj is not None:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)

        # Trajectoire (objet Curve dédié)
        _purge_trajectory_object()

        # Wrapper (toujours), sub-groups (seulement s'ils sont orphelins)
        _purge_simple_wrapper()
        _purge_orphan_subgroups()

        # Matériaux orphelins (ceux du Vector Comp sont préservés tant
        # qu'un objet/node-group les référence)
        materials.remove_all_unused()

        # Lambdas : utilise le scoping par scène pour ne pas toucher
        # aux fonctions des autres scènes.
        drv_mod.clear_driver_namespace(scene=context.scene)

        self.report({'INFO'}, "Vector Viewer supprimé.")
        return {'FINISHED'}
