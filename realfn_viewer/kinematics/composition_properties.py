"""Propriétés du panneau Composition (référentiels non galiléens),
stockées sur la Scene sous ``scene.vector_comp``."""

import bpy
import math
from bpy.props import (
    BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty,
)
from bpy.types import PropertyGroup

from . import composition_presets as _cmp_presets
from .. import modifier_inputs


# Modifier porté par l'objet hôte de composition (différent de l'hôte
# du Vector Viewer simple, donc même nom de modifier sans conflit).
COMP_MODIFIER_NAME = "VectorMod"


# Mapping nom_de_propriété → label du socket booléen exposé.
# Les labels DOIVENT être identiques à ceux d'``ARROWS_SPEC`` /
# ``SHOW_R_LABEL`` / ``SHOW_RP_LABEL`` dans composition_nodegroups.py
# — c'est ce qui les relie.
SHOW_FIELDS = (
    ("show_OOp",      "Afficher OO'"),
    ("show_OpM",      "Afficher O'M"),
    ("show_OM",       "Afficher OM"),
    ("show_vr",       "Afficher v_r"),
    ("show_ve",       "Afficher v_e"),
    ("show_va",       "Afficher v_a"),
    ("show_ar",       "Afficher a_r"),
    ("show_ae",       "Afficher a_e"),
    ("show_ac",       "Afficher a_c (Coriolis)"),
    ("show_aa",       "Afficher a_a"),
    ("show_Omega",    "Afficher Omega"),
    ("show_R_frame",  "Afficher repère R"),
    ("show_Rp_frame", "Afficher repère R'"),
    ("show_traj_OOp", "Afficher trajectoire OO'"),
    ("show_traj_OM",  "Afficher trajectoire OM"),
    ("show_traj_OpM", "Afficher trajectoire O'M"),
)


# ----------------------------------------------------------------------------
# Helpers d'écriture sur les sockets exposés du modifier
# ----------------------------------------------------------------------------

def _get_modifier(props):
    obj = bpy.data.objects.get(props.host_name)
    if obj is None:
        return None
    return obj.modifiers.get(COMP_MODIFIER_NAME)


def _socket_id(node_group, socket_name):
    if node_group is None:
        return None
    for item in node_group.interface.items_tree:
        if (item.item_type == 'SOCKET'
                and item.in_out == 'INPUT'
                and item.name == socket_name):
            return item.identifier
    return None


def _write_socket(props, socket_name, value, *, cast=bool):
    """Écrit ``value`` (cast par défaut en bool) sur le socket exposé
    ``socket_name`` du modifier hôte. ``cast`` peut être passé à ``float``
    pour les sockets numériques (ex. ``Rayon des trajectoires``)."""
    mod = _get_modifier(props)
    if mod is None or mod.node_group is None:
        return
    sid = _socket_id(mod.node_group, socket_name)
    if sid is None:
        return
    try:
        if not modifier_inputs.set_value(mod, sid, cast(value)):
            raise ValueError("valeur refusée par le modifier")
        obj = bpy.data.objects.get(props.host_name)
        if obj is not None:
            obj.update_tag()
    except (KeyError, RuntimeError, ReferenceError, ValueError) as e:
        print(f"[VectorComp] échec écriture {socket_name!r}: {e}")


def apply_show_flags(props):
    """Synchronise toutes les cases à cocher d'affichage et les
    propriétés numériques du modifier (rayon trajectoire, échelles)."""
    for prop_attr, sock_name in SHOW_FIELDS:
        _write_socket(props, sock_name, getattr(props, prop_attr))
    # Floats supplémentaires : rayon des tubes-trajectoires + 3 échelles
    _write_socket(props, "Rayon des trajectoires",
                  props.traj_radius, cast=float)
    _write_socket(props, "Échelle v",     props.scale_v,     cast=float)
    _write_socket(props, "Échelle a",     props.scale_a,     cast=float)
    _write_socket(props, "Échelle Ω",     props.scale_omega, cast=float)


def _make_update(prop_attr, sock_name):
    """Factory pour les callbacks ``update`` des BoolProperty."""
    def upd(self, _context):
        _write_socket(self, sock_name, getattr(self, prop_attr))
    return upd


def _make_update_float(prop_attr, sock_name):
    """Factory pour les callbacks ``update`` des FloatProperty."""
    def upd(self, _context):
        _write_socket(self, sock_name, getattr(self, prop_attr), cast=float)
    return upd


# ----------------------------------------------------------------------------
# PropertyGroup
# ----------------------------------------------------------------------------

class VectorCompositionProperties(PropertyGroup):
    # ──────────────────────────────────────────────────────────────────
    # Preset sélectionné dans le menu déroulant
    # ──────────────────────────────────────────────────────────────────
    preset_choice: EnumProperty(
        name="Preset",
        description="Configuration cinématique pré-définie ; cliquer sur "
                    "« Appliquer » pour remplacer les champs ci-dessous. "
                    "Les presets marqués ★ sont des presets utilisateur.",
        items=_cmp_presets.enum_items_callback,
    )

    # ──────────────────────────────────────────────────────────────────
    # Translation O'(t) — origine du repère mobile dans R
    # ──────────────────────────────────────────────────────────────────
    X0_expr: StringProperty(name="X₀(t)", default="0",
        description="Composante x de la translation de O' dans R (sympy)")
    Y0_expr: StringProperty(name="Y₀(t)", default="0",
        description="Composante y de la translation de O' dans R (sympy)")
    Z0_expr: StringProperty(name="Z₀(t)", default="0",
        description="Composante z de la translation de O' dans R (sympy)")

    # ──────────────────────────────────────────────────────────────────
    # Rotation R'/R — angles d'Euler Z-Y-X intrinsèque
    # « rotation autour de z » classique = ψ seul, θ=φ=0.
    # ──────────────────────────────────────────────────────────────────
    psi_expr: StringProperty(name="ψ(t)  yaw (z)", default="t",
        description="Angle de rotation autour de l'axe z (sympy)")
    theta_expr: StringProperty(name="θ(t)  pitch (y)", default="0",
        description="Angle de rotation autour de l'axe y (sympy)")
    phi_expr: StringProperty(name="φ(t)  roll (x)", default="0",
        description="Angle de rotation autour de l'axe x (sympy)")

    # ──────────────────────────────────────────────────────────────────
    # Position de M dans R'
    # Par défaut : mouvement rectiligne uniforme le long de l'axe x'
    # ──────────────────────────────────────────────────────────────────
    xp_expr: StringProperty(name="x'(t)", default="t",
        description="Coordonnée x' de M dans le repère mobile (sympy)")
    yp_expr: StringProperty(name="y'(t)", default="0",
        description="Coordonnée y' de M dans le repère mobile (sympy)")
    zp_expr: StringProperty(name="z'(t)", default="0",
        description="Coordonnée z' de M dans le repère mobile (sympy)")

    # ──────────────────────────────────────────────────────────────────
    # Animation
    # ──────────────────────────────────────────────────────────────────
    fps: IntProperty(name="FPS", default=30, min=1, max=240,
        description="Frames par seconde")
    t_start: FloatProperty(name="t₀ (s)", default=0.0, precision=4,
        description="Temps physique au premier frame")
    t_duration: FloatProperty(name="Durée (s)", default=2.0 * math.pi,
        min=1e-3, precision=4,
        description="Durée physique animée")

    # ──────────────────────────────────────────────────────────────────
    # Échelles
    # ──────────────────────────────────────────────────────────────────
    scale_v: FloatProperty(name="Échelle v", default=1.0, min=0.0, precision=4,
        description="Facteur d'échelle visuel pour les flèches vitesse "
                    "(1.0 = unitaire, 1 m affiché ↔ 1 m/s) — modifiable en live",
        update=_make_update_float("scale_v", "Échelle v"))
    scale_a: FloatProperty(name="Échelle a", default=1.0, min=0.0, precision=4,
        description="Facteur d'échelle visuel pour les flèches accélération "
                    "(1.0 = unitaire, 1 m affiché ↔ 1 m/s²) — modifiable en live",
        update=_make_update_float("scale_a", "Échelle a"))
    scale_omega: FloatProperty(name="Échelle Ω", default=1.0, min=0.0, precision=4,
        description=(
            "Facteur d'échelle visuel pour le vecteur rotation instantanée "
            "(1.0 = unitaire, 1 m affiché ↔ 1 rad/s) — modifiable en live ; "
            "indépendant des échelles de vitesse et d'accélération"
        ),
        update=_make_update_float("scale_omega", "Échelle Ω"))

    # ──────────────────────────────────────────────────────────────────
    # Visibilité des 9 flèches
    # Défauts : OO', O'M, v_r, v_e, v_a et Coriolis affichés ; les
    # autres composantes d'accélération masquées pour ne pas surcharger.
    # ──────────────────────────────────────────────────────────────────
    show_OOp: BoolProperty(name="OO'", default=True,
        update=_make_update("show_OOp", "Afficher OO'"))
    show_OpM: BoolProperty(name="O'M", default=True,
        update=_make_update("show_OpM", "Afficher O'M"))
    show_OM: BoolProperty(name="OM (= OO' + O'M)", default=True,
        description=("Position absolue de M depuis l'origine : ferme "
                     "le triangle OM = OO' + O'M"),
        update=_make_update("show_OM", "Afficher OM"))

    show_vr: BoolProperty(name="v_r (relative)", default=True,
        update=_make_update("show_vr", "Afficher v_r"))
    show_ve: BoolProperty(name="v_e (entraînement)", default=True,
        update=_make_update("show_ve", "Afficher v_e"))
    show_va: BoolProperty(name="v_a (absolue)", default=True,
        update=_make_update("show_va", "Afficher v_a"))

    show_ar: BoolProperty(name="a_r (relative)", default=False,
        update=_make_update("show_ar", "Afficher a_r"))
    show_ae: BoolProperty(name="a_e (entraînement)", default=False,
        update=_make_update("show_ae", "Afficher a_e"))
    show_ac: BoolProperty(name="a_c (Coriolis)", default=True,
        update=_make_update("show_ac", "Afficher a_c (Coriolis)"))
    show_aa: BoolProperty(name="a_a (absolue)", default=False,
        update=_make_update("show_aa", "Afficher a_a"))

    # ──────────────────────────────────────────────────────────────────
    # Vecteur rotation instantanée Ω, ancré à O'(t)
    # Affiché par défaut : c'est la quantité qui pilote v_e, a_e, a_c.
    # ──────────────────────────────────────────────────────────────────
    show_Omega: BoolProperty(
        name="Ω (rotation instantanée)", default=True,
        description=(
            "Vecteur rotation de R'/R, ancré à O'(t) le long de l'axe "
            "instantané de rotation"
        ),
        update=_make_update("show_Omega", "Afficher Omega"))

    # ──────────────────────────────────────────────────────────────────
    # Trièdres directs
    # ──────────────────────────────────────────────────────────────────
    show_R_frame: BoolProperty(
        name="Trièdre R (origine)", default=True,
        description="Afficher (ê_x, ê_y, ê_z) à l'origine du monde",
        update=_make_update("show_R_frame", "Afficher repère R"))
    show_Rp_frame: BoolProperty(
        name="Trièdre R' (mobile)", default=True,
        description="Afficher (R·ê_x, R·ê_y, R·ê_z) ancrés à O'(t)",
        update=_make_update("show_Rp_frame", "Afficher repère R'"))
    axis_length: FloatProperty(
        name="Longueur des axes", default=1.0, min=1e-3, precision=3,
        description=(
            "Longueur des arêtes des trièdres R et R'. "
            "La modifier nécessite un Build pour être prise en compte."
        ))

    # ──────────────────────────────────────────────────────────────────
    # Latitude pour le preset Foucault — réglable, lue par l'opérateur
    # ``vector_comp.apply_foucault`` qui régénère les expressions du
    # pendule en fonction de cette valeur. N'a d'effet que pour le
    # preset Foucault ; ignorée par les autres.
    # ──────────────────────────────────────────────────────────────────
    latitude_deg: FloatProperty(
        name="Latitude (°)",
        description=(
            "Latitude (en degrés) pour le pendule de Foucault. "
            "À utiliser avec le bouton « Recalculer pour cette latitude » "
            "qui régénère les expressions. "
            "Paris = 48.85, Greenwich = 51.48, équateur = 0, pôle = 90."
        ),
        default=48.85,
        min=-90.0, max=90.0,
        precision=2,
    )

    # ──────────────────────────────────────────────────────────────────
    # Trajectoires (chemins parcourus, sample-and-bake au build)
    # ──────────────────────────────────────────────────────────────────
    # Cachées par défaut : elles encombrent vite la scène. À activer
    # uniquement quand on veut visualiser le chemin parcouru en plus
    # des flèches animées.
    show_traj_OOp: BoolProperty(
        name="Trajectoire OO'", default=False,
        description="Chemin parcouru par O'(t) dans R",
        update=_make_update("show_traj_OOp", "Afficher trajectoire OO'"))
    show_traj_OM: BoolProperty(
        name="Trajectoire OM", default=False,
        description="Chemin absolu de M dans R (= OO' + O'M)",
        update=_make_update("show_traj_OM", "Afficher trajectoire OM"))
    show_traj_OpM: BoolProperty(
        name="Trajectoire O'M", default=False,
        description=(
            "Chemin de M tel que vu de R' (= R(t)·r'(t), dessiné "
            "depuis l'origine pour visualiser le mouvement relatif)"
        ),
        update=_make_update("show_traj_OpM", "Afficher trajectoire O'M"))
    traj_radius: FloatProperty(
        name="Rayon trajectoires", default=0.015, min=0.0, precision=4,
        description=(
            "Rayon des tubes-trajectoires (modifiable sans rebuild "
            "puisque le rayon est exposé sur le modifier Geometry Nodes)"
        ),
        update=_make_update_float("traj_radius", "Rayon des trajectoires"))

    # ──────────────────────────────────────────────────────────────────
    # Hôte
    # ──────────────────────────────────────────────────────────────────
    host_name: StringProperty(
        name="Nom objet",
        description="Nom de l'objet portant le modifier de composition",
        default="VectorComp",
    )
