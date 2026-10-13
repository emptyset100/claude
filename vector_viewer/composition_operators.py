"""Opérateurs build / clear pour la visualisation de composition
des référentiels non galiléens."""

import bpy
import typing

from . import (
    nodegroups,
    composition as cmp_mod,
    composition_nodegroups as cmp_ng,
    composition_properties as cmp_props_mod,
    materials,
)
from .composition_properties import COMP_MODIFIER_NAME
from .composition_nodegroups import COMP_WRAPPER_NAME, TRAJECTORIES_SPEC

# Réutilisation des helpers du Vector Viewer simple :
# _ensure_subgroups (crée Position/Vitesse/Acceleration si manquants),
# _purge_orphan_subgroups (les retire s'ils ne sont plus utilisés).
from .operators import _ensure_subgroups, _purge_orphan_subgroups


# Borne supérieure du nombre d'échantillons pour les trajectoires.
# Au-delà, la résolution n'apporte plus rien à l'œil et alourdit la scène.
TRAJ_MAX_SAMPLES = 2000


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _purge_composition_wrapper():
    """Supprime uniquement le wrapper de composition."""
    cw = bpy.data.node_groups.get(COMP_WRAPPER_NAME)
    if cw is not None:
        bpy.data.node_groups.remove(cw)


def _purge_trajectory_objects():
    """Supprime les courbes-trajectoires et leurs data-blocks Curve.

    Idempotent : ne fait rien si elles n'existent pas (cas du premier
    build, ou si l'utilisateur les a déjà supprimées manuellement)."""
    for _, _, _, obj_name in TRAJECTORIES_SPEC:
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            continue
        curve_data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if curve_data is not None and curve_data.users == 0:
            bpy.data.curves.remove(curve_data)


def _sample_trajectory(fn, t_start, t_duration, n):
    """Échantillonne ``fn(t) → Vector(3)`` en ``n`` points sur
    ``[t_start, t_start + t_duration]``. Retourne une liste de tuples
    ``(x, y, z)``."""
    if n < 2:
        n = 2
    out = []
    # numpy n'est pas une dépendance : on fait le linspace à la main
    # pour rester portable avec le runtime Python de Blender.
    step = t_duration / (n - 1) if n > 1 else 0.0
    for i in range(n):
        t = t_start + i * step
        v = fn(t)
        out.append((float(v[0]), float(v[1]), float(v[2])))
    return out


def _make_curve_object(name, points):
    """Crée un objet Curve POLY (lignes brisées 3D) à partir d'une
    liste de tuples (x, y, z), le lie à la collection courante,
    et le retourne. Les anciens objets de même nom sont supprimés."""
    # Suppression de l'ancien (double sécurité, cf. _purge_trajectory_objects)
    old = bpy.data.objects.get(name)
    if old is not None:
        old_data = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if old_data is not None and old_data.users == 0:
            bpy.data.curves.remove(old_data)

    cd = bpy.data.curves.new(name, 'CURVE')
    cd.dimensions = '3D'
    spline = cd.splines.new('POLY')
    # ``new('POLY')`` crée 1 point initial ; on ajoute les n-1 autres
    spline.points.add(len(points) - 1)
    for i, (x, y, z) in enumerate(points):
        # Le 4e composant w est le "weight" du point rationnel : sans
        # objet pour les splines POLY, mais doit valoir 1.0 pour ne pas
        # déformer la courbe.
        spline.points[i].co = (x, y, z, 1.0)

    obj = bpy.data.objects.new(name, cd)
    bpy.context.collection.objects.link(obj)
    # Caché à la vue mais resté dans le dépendence graph (Object Info
    # accède à la geometry évaluée même lorsque hide_set est True).
    obj.hide_set(True)
    obj.hide_render = True
    return obj


def _generate_trajectory_curves(props, scene=None):
    """Échantillonne les trois trajectoires depuis ``driver_namespace``
    et crée les objets Curve correspondants.

    Doit être appelé APRÈS ``cmp_mod.refresh_driver_namespace(props,
    scene=scene)`` qui peuple ``cmp_O_p_<scene>``, ``cmp_r_a_<scene>``,
    ``cmp_OpM_<scene>`` dans le namespace.

    Retourne ``{nom_objet: bpy.types.Object}`` à passer au wrapper."""
    dns = bpy.app.driver_namespace
    fn_OOp = dns.get(cmp_mod._dns_key(scene, "O_p"))
    fn_OM  = dns.get(cmp_mod._dns_key(scene, "r_a"))
    fn_OpM = dns.get(cmp_mod._dns_key(scene, "OpM"))
    if fn_OOp is None or fn_OM is None or fn_OpM is None:
        # Le driver_namespace n'a pas été peuplé — on retourne vide,
        # le wrapper utilisera des Object Info sans référence et les
        # trajectoires resteront simplement invisibles.
        return {}

    n = int(round(props.fps * props.t_duration)) + 1
    n = max(2, min(n, TRAJ_MAX_SAMPLES))

    pts_OOp = _sample_trajectory(fn_OOp, props.t_start, props.t_duration, n)
    pts_OM  = _sample_trajectory(fn_OM,  props.t_start, props.t_duration, n)
    pts_OpM = _sample_trajectory(fn_OpM, props.t_start, props.t_duration, n)

    return {
        "VV_traj_OOp": _make_curve_object("VV_traj_OOp", pts_OOp),
        "VV_traj_OM":  _make_curve_object("VV_traj_OM",  pts_OM),
        "VV_traj_OpM": _make_curve_object("VV_traj_OpM", pts_OpM),
    }


def _build_composition_groups(axis_length: float,
                               trajectory_objs: dict | None = None,
                               traj_radius_default: float = 0.015,
                               scale_v: float = 1.0,
                               scale_a: float = 1.0,
                               scale_omega: float = 1.0):
    """Construit le wrapper de composition et retourne sa référence.
    Crée les sub-groups Position/Vitesse/Acceleration si nécessaire,
    sinon les réutilise (peut donc cohabiter avec un Vector Viewer
    simple déjà construit)."""
    _purge_composition_wrapper()

    node_tree_names: dict[typing.Callable, str] = {}
    _ensure_subgroups(node_tree_names)

    wrapper = cmp_ng.composition_wrapper_node_group(
        node_tree_names,
        axis_length=axis_length,
        trajectory_objs=trajectory_objs,
        traj_radius_default=traj_radius_default,
        scale_v_default=scale_v,
        scale_a_default=scale_a,
        scale_omega_default=scale_omega,
    )
    return wrapper


def _make_host(wrapper, name):
    """Crée (ou réutilise) un objet hôte minimal portant le modifier
    Geometry Nodes pointant vers ``wrapper``."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        mesh = bpy.data.meshes.new(name + "_mesh")
        mesh.from_pydata([(0.0, 0.0, 0.0)], [], [])
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)

    mod = obj.modifiers.get(COMP_MODIFIER_NAME)
    if mod is None:
        mod = obj.modifiers.new(COMP_MODIFIER_NAME, type='NODES')
    mod.node_group = wrapper

    return obj


def _configure_timeline(scene, props):
    """Cale la timeline sur [0, durée·fps] et passe au frame 0."""
    scene.render.fps = props.fps
    scene.frame_start = 0
    scene.frame_end   = int(round(props.t_duration * props.fps))
    scene.frame_set(0)


# ----------------------------------------------------------------------------
# Opérateurs
# ----------------------------------------------------------------------------

class VECTORCOMP_OT_build(bpy.types.Operator):
    """Construit (ou reconstruit) la visualisation de composition à
    partir des expressions saisies dans le panneau."""

    bl_idname = "vector_comp.build"
    bl_label = "Construire / Mettre à jour"
    bl_description = (
        "Parse O'(t), les angles d'Euler et r'(t), construit les 9 "
        "flèches de la composition (référentiels non galiléens)"
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        props = scene.vector_comp

        # 1. Compile sympy → driver_namespace (cmp_O_p, cmp_v_r, …)
        try:
            cmp_mod.refresh_driver_namespace(props, scene=scene)
        except (ValueError, ImportError) as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        # 2. Purge et regénération des courbes-trajectoires (échantillonne
        # les fonctions tout juste compilées sur [t_start, t_start+T])
        _purge_trajectory_objects()
        traj_objs = _generate_trajectory_curves(props, scene=scene)

        # 3. (Re)construit le wrapper de composition, en lui passant les
        # références aux courbes-trajectoires pour que les nodes Object
        # Info pointent dessus.
        wrapper = _build_composition_groups(
            axis_length=props.axis_length,
            trajectory_objs=traj_objs,
            traj_radius_default=props.traj_radius,
            scale_v=props.scale_v,
            scale_a=props.scale_a,
            scale_omega=props.scale_omega,
        )

        # 4. Crée / met à jour l'objet hôte
        obj = _make_host(wrapper, props.host_name)

        # 5. Attache les drivers sur les sockets internes
        cmp_mod.attach_socket_drivers(
            wrapper,
            fps=props.fps,
            t0=props.t_start,
            host_name=props.host_name,
            modifier_name=COMP_MODIFIER_NAME,
            scene=scene,
            scale_v=props.scale_v,
            scale_a=props.scale_a,
            scale_omega=props.scale_omega,
            axis_length=props.axis_length,
        )

        # 6. Synchronise toutes les cases à cocher (incl. trajectoires)
        # et le rayon des trajectoires vers les sockets du modifier
        cmp_props_mod.apply_show_flags(props)

        # 7. Configure la timeline
        _configure_timeline(scene, props)

        # 8. Sélectionne et active l'objet
        for o in context.selected_objects:
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj

        self.report(
            {'INFO'},
            f"Composition « {obj.name} » prête — timeline 0 → "
            f"{scene.frame_end} (t ∈ [{props.t_start:.2f}, "
            f"{props.t_start + props.t_duration:.2f}] s)"
        )
        return {'FINISHED'}


class VECTORCOMP_OT_clear(bpy.types.Operator):
    """Supprime l'objet hôte et le wrapper de composition. Les
    sub-groups Position/Vitesse/Acceleration ne sont retirés que s'ils
    ne sont plus utilisés par un autre wrapper."""

    bl_idname = "vector_comp.clear"
    bl_label = "Supprimer"
    bl_description = "Supprime l'objet hôte et le wrapper de composition"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.vector_comp

        # Objet hôte
        obj = bpy.data.objects.get(props.host_name)
        if obj is not None:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)

        # Trajectoires (objets Curve dédiés)
        _purge_trajectory_objects()

        # Wrapper + sub-groups orphelins
        _purge_composition_wrapper()
        _purge_orphan_subgroups()

        # Matériaux orphelins (ceux du Vector Viewer simple sont conservés
        # tant qu'un objet/node-group les référence)
        materials.remove_all_unused()

        # Driver namespace (suffixé par scène)
        cmp_mod.clear_driver_namespace(scene=context.scene)

        self.report({'INFO'}, "Composition supprimée.")
        return {'FINISHED'}
