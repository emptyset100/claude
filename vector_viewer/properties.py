"""Propriétés exposées dans le panneau (stockées sur la Scene).

Inclut aussi les helpers chargés de propager les cases à cocher
« Afficher position / vitesse / accélération » vers les sockets
correspondants du modifier Geometry Nodes de l'objet hôte."""

import bpy
import math
from bpy.props import (
    BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty,
)
from bpy.types import PropertyGroup

from .nodegroups import (
    SHOW_POSITION_SOCKET,
    SHOW_VITESSE_SOCKET,
    SHOW_ACCELERATION_SOCKET,
    SHOW_TRAJECTORY_SOCKET,
    TRAJ_RADIUS_SOCKET,
    SHOW_FRAME_SOCKET,
    AXIS_LENGTH_DEFAULT,
    SCALE_V_SOCKET,
    SCALE_A_SOCKET,
)
from . import presets as _presets


# Nom du modifier porté par l'objet hôte. Constante partagée avec
# ``operators.py`` (qui le crée) et utilisée ici pour le retrouver.
MODIFIER_NAME = "VectorMod"


# ----------------------------------------------------------------------------
# Helpers d'écriture sur les sockets exposés du modifier
# ----------------------------------------------------------------------------

def _get_modifier(props):
    """Retourne le modifier Geometry Nodes lié à l'objet hôte ``props.host_name``,
    ou ``None`` si l'objet ou le modifier n'existe pas encore."""
    obj = bpy.data.objects.get(props.host_name)
    if obj is None:
        return None
    return obj.modifiers.get(MODIFIER_NAME)


def _socket_id(node_group, socket_name):
    """Retourne l'``identifier`` (auto-généré, ex. ``"Socket_2"``) du socket
    d'entrée du node group dont le ``name`` (label utilisateur) correspond.

    L'API modifier indexe les sockets par identifier, pas par name."""
    if node_group is None:
        return None
    for item in node_group.interface.items_tree:
        if (item.item_type == 'SOCKET'
                and item.in_out == 'INPUT'
                and item.name == socket_name):
            return item.identifier
    return None


def _write_socket(props, socket_name, value, *, cast=bool):
    """Écrit ``value`` dans le socket d'entrée ``socket_name`` du modifier
    de l'objet hôte. ``cast`` est appliqué à la valeur avant écriture
    (``bool`` pour les booléens, ``float`` pour les sockets Float).
    No-op silencieux si le modifier n'est pas (encore) construit."""
    mod = _get_modifier(props)
    if mod is None or mod.node_group is None:
        return  # construction pas encore lancée → on ignore
    sid = _socket_id(mod.node_group, socket_name)
    if sid is None:
        return  # socket introuvable (wrapper d'une ancienne version ?)
    try:
        mod[sid] = cast(value)
        # Force le depsgraph à rejouer le modifier — la simple écriture
        # de la propriété personnalisée ne déclenche pas toujours un
        # redessin immédiat dans la 3D View.
        obj = bpy.data.objects.get(props.host_name)
        if obj is not None:
            obj.update_tag()
    except (KeyError, RuntimeError, ReferenceError, ValueError) as e:
        print(f"[VectorViewer] échec écriture {socket_name!r}: {e}")


def apply_show_flags(props):
    """Force la synchronisation des cases à cocher du panneau et du
    rayon de la trajectoire vers les sockets du modifier. Appelé par
    l'opérateur de construction juste après création du modifier."""
    _write_socket(props, SHOW_POSITION_SOCKET,     props.show_position)
    _write_socket(props, SHOW_VITESSE_SOCKET,      props.show_vitesse)
    _write_socket(props, SHOW_ACCELERATION_SOCKET, props.show_acceleration)
    _write_socket(props, SHOW_TRAJECTORY_SOCKET,   props.show_trajectory)
    _write_socket(props, TRAJ_RADIUS_SOCKET, props.traj_radius, cast=float)
    _write_socket(props, SHOW_FRAME_SOCKET,        props.show_frame)
    _write_socket(props, SCALE_V_SOCKET, props.scale_v, cast=float)
    _write_socket(props, SCALE_A_SOCKET, props.scale_a, cast=float)
    # Note : axis_length n'a pas de socket (calé en dur au build).


# ----------------------------------------------------------------------------
# Update callbacks : écrivent la valeur courante de la BoolProperty dans
# le socket correspondant. Signature standard Blender : (self, context).
# ----------------------------------------------------------------------------

def _update_show_position(self, context):
    _write_socket(self, SHOW_POSITION_SOCKET, self.show_position)


def _update_show_vitesse(self, context):
    _write_socket(self, SHOW_VITESSE_SOCKET, self.show_vitesse)


def _update_show_acceleration(self, context):
    _write_socket(self, SHOW_ACCELERATION_SOCKET, self.show_acceleration)


def _update_show_trajectory(self, context):
    _write_socket(self, SHOW_TRAJECTORY_SOCKET, self.show_trajectory)


def _update_traj_radius(self, context):
    _write_socket(self, TRAJ_RADIUS_SOCKET, self.traj_radius, cast=float)


def _update_show_frame(self, context):
    _write_socket(self, SHOW_FRAME_SOCKET, self.show_frame)


def _update_scale_v(self, context):
    _write_socket(self, SCALE_V_SOCKET, self.scale_v, cast=float)


def _update_scale_a(self, context):
    _write_socket(self, SCALE_A_SOCKET, self.scale_a, cast=float)


# ----------------------------------------------------------------------------
# PropertyGroup
# ----------------------------------------------------------------------------

class VectorViewerProperties(PropertyGroup):
    # ------------------------------------------------------------------
    # Preset sélectionné dans le menu déroulant
    # ------------------------------------------------------------------
    preset_choice: EnumProperty(
        name="Preset",
        description="Trajectoire pré-définie ; cliquer sur « Appliquer » "
                    "pour remplacer les expressions ci-dessous. "
                    "Les presets marqués ★ sont des presets utilisateur.",
        items=_presets.enum_items_callback,
    )

    # ------------------------------------------------------------------
    # Composantes du vecteur position r(t) = x(t)·êx + y(t)·êy + z(t)·êz
    # ------------------------------------------------------------------
    x_expr: StringProperty(
        name="x(t)",
        description="Composante x du vecteur position (syntaxe sympy)",
        default="cos(pi*t/2)",
    )
    y_expr: StringProperty(
        name="y(t)",
        description="Composante y du vecteur position (syntaxe sympy)",
        default="sin(pi*t/2)",
    )
    z_expr: StringProperty(
        name="z(t)",
        description="Composante z du vecteur position (syntaxe sympy)",
        default="0",
    )

    # ------------------------------------------------------------------
    # Réglages de la scène / de l'animation
    # ------------------------------------------------------------------
    fps: IntProperty(
        name="FPS",
        description="Frames par seconde (timeline et drivers)",
        default=30, min=1, max=240,
    )
    t_start: FloatProperty(
        name="t₀ (s)",
        description="Temps physique au premier frame (frame 0)",
        default=0.0, precision=4,
    )
    t_duration: FloatProperty(
        name="Durée (s)",
        description="Durée physique animée",
        default=2.0 * math.pi, min=1e-3, precision=4,
    )
    scale_v: FloatProperty(
        name="Échelle v",
        description="Facteur d'échelle visuel pour la flèche vitesse "
                    "(1.0 = unitaire, 1 m affiché ↔ 1 m/s) — modifiable en live",
        default=1.0, min=0.0, precision=4,
        update=_update_scale_v,
    )
    scale_a: FloatProperty(
        name="Échelle a",
        description="Facteur d'échelle visuel pour la flèche accélération "
                    "(1.0 = unitaire, 1 m affiché ↔ 1 m/s²) — modifiable en live",
        default=1.0, min=0.0, precision=4,
        update=_update_scale_a,
    )

    # ------------------------------------------------------------------
    # Visibilité des trois flèches (pilotage des Switch via les sockets
    # exposés du modifier)
    # ------------------------------------------------------------------
    show_position: BoolProperty(
        name="Afficher position",
        description="Affiche / masque la flèche de position r(t)",
        default=True,
        update=_update_show_position,
    )
    show_vitesse: BoolProperty(
        name="Afficher vitesse",
        description="Affiche / masque la flèche de vitesse v(t)",
        default=True,
        update=_update_show_vitesse,
    )
    show_acceleration: BoolProperty(
        name="Afficher accélération",
        description="Affiche / masque la flèche d'accélération a(t)",
        default=True,
        update=_update_show_acceleration,
    )

    # Trajectoire OM : echantillonnée au build. Cachée par défaut pour
    # éviter de surcharger la scène avec les trois flèches déjà visibles.
    show_trajectory: BoolProperty(
        name="Afficher trajectoire OM",
        description=(
            "Affiche / masque la trajectoire OM (courbe parcourue par M, "
            "échantillonnée au build sur [t_start, t_start + t_duration])"
        ),
        default=False,
        update=_update_show_trajectory,
    )
    traj_radius: FloatProperty(
        name="Rayon trajectoire",
        description="Rayon du tube de la trajectoire OM (modifiable en live)",
        default=0.015,
        min=0.0,
        max=10.0,
        precision=4,
        update=_update_traj_radius,
    )

    # Trièdre du repère R (base orthonormée ê_x, ê_y, ê_z à l'origine)
    show_frame: BoolProperty(
        name="Afficher repère R",
        description=(
            "Afficher / masquer le trièdre du repère R (axes ê_x, ê_y, "
            "ê_z) ancré à l'origine du monde"
        ),
        default=True,
        update=_update_show_frame,
    )
    axis_length: FloatProperty(
        name="Longueur des axes",
        description=(
            "Longueur des arêtes du trièdre R (statique : modifier puis "
            "Build pour appliquer)"
        ),
        default=AXIS_LENGTH_DEFAULT,
        min=0.0,
        max=100.0,
        precision=3,
    )

    # ------------------------------------------------------------------
    # Objet hôte
    # ------------------------------------------------------------------
    host_name: StringProperty(
        name="Nom objet",
        description="Nom de l'objet portant le modifier Geometry Nodes",
        default="VectorViewer",
    )
