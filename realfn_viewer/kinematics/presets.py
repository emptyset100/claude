"""Bibliothèque de presets pour le Vector Viewer simple.

Deux niveaux :

- ``PRESETS`` (et ``PRESET_ORDER``) : presets builtins, livrés avec
  l'extension, en lecture seule. Les expressions, durée et échelles ont
  été choisies pour que la flèche v et la flèche a soient lisibles
  sans réglage manuel.

- Presets utilisateur : enregistrés au format JSON dans le dossier
  config de Blender (cf. ``preset_storage.py``). Persistent à travers
  les sessions et indépendamment des fichiers .blend.

Tout le routage builtins ↔ utilisateur passe par l'instance ``STORE``
(``preset_storage.PresetStore``).
"""

import bpy
from bpy.props import StringProperty

from . import preset_storage


# ----------------------------------------------------------------------------
# Définition des presets builtins
# ----------------------------------------------------------------------------

_PI = 3.141592653589793

PRESETS = {
    "MCU": {
        "label":    "Circulaire uniforme (MCU)",
        "tip":      "Cercle unité parcouru à vitesse angulaire 1 rad/s. "
                    "v tangente unitaire, a centripète unitaire.",
        "x":        "cos(t)",
        "y":        "sin(t)",
        "z":        "0",
        "duration": 2 * _PI,
        "scale_v":  1.0,
        "scale_a":  1.0,
    },
    "MCV": {
        "label":    "Circulaire uniformément accéléré",
        "tip":      "θ(t) = t²/2 sur le cercle unité : v croît linéairement, "
                    "a possède une composante tangentielle ET centripète "
                    "(croissante en t²).",
        "x":        "cos(t**2/2)",
        "y":        "sin(t**2/2)",
        "z":        "0",
        "duration": 2 * _PI,
        "scale_v":  1.0,
        "scale_a":  1.0,
    },
    "OSC1D": {
        "label":    "Oscillateur harmonique 1D",
        "tip":      "x(t) = cos(2t). v et a alignés sur x. v et a en "
                    "quadrature : v ⟂ a aux extrema, ‖a‖ = ω²·‖x‖.",
        "x":        "cos(2*t)",
        "y":        "0",
        "z":        "0",
        "duration": 2 * _PI,
        "scale_v":  1.0,
        "scale_a":  1.0,
    },
    "PARABOLE": {
        "label":    "Tir parabolique (g=1)",
        "tip":      "Trajectoire balistique 2D dans le plan (x,z) : "
                    "vitesse initiale (1,0,2), gravité unitaire suivant "
                    "−z. a = (0, 0, −1) constante.",
        "x":        "t",
        "y":        "0",
        "z":        "2*t - t**2/2",
        "duration": 4.0,
        "scale_v":  1.0,
        "scale_a":  1.0,
    },
    "LISSAJOUS": {
        "label":    "Lissajous (3:2)",
        "tip":      "x = sin(3t), y = sin(2t). Courbe fermée caractéristique, "
                    "v et a tournent de manière non triviale.",
        "x":        "sin(3*t)",
        "y":        "sin(2*t)",
        "z":        "0",
        "duration": 2 * _PI,
        "scale_v":  1.0,
        "scale_a":  1.0,
    },
    "HELICE": {
        "label":    "Hélice circulaire",
        "tip":      "Cercle de rayon 1 dans (x,y) + montée régulière en z. "
                    "v et a constants en module ; v ⟂ a à chaque instant "
                    "(‖v‖ constante), a horizontale dirigée vers l'axe.",
        "x":        "cos(t)",
        "y":        "sin(t)",
        "z":        "t/(2*pi)",
        "duration": 4 * _PI,
        "scale_v":  1.0,
        "scale_a":  1.0,
    },
    "SPIRALE": {
        "label":    "Spirale d'Archimède",
        "tip":      "r = t en coordonnées polaires : x = t·cos(t), "
                    "y = t·sin(t). v et a non bornés, à croissance "
                    "linéaire : ‖v‖ = √(1+t²), ‖a‖ = √(4+t²).",
        "x":        "t*cos(t)",
        "y":        "t*sin(t)",
        "z":        "0",
        "duration": 4 * _PI,
        "scale_v":  1.0,
        "scale_a":  1.0,
    },
    "CYCLOIDE": {
        "label":    "Cycloïde",
        "tip":      "Trajectoire d'un point d'un cercle qui roule sans "
                    "glisser : v s'annule à chaque rebroussement, a "
                    "constante en module.",
        "x":        "t - sin(t)",
        "y":        "1 - cos(t)",
        "z":        "0",
        "duration": 4 * _PI,
        "scale_v":  1.0,
        "scale_a":  1.0,
    },

    # ── Mouvements rectilignes / 1D ─────────────────────────────────
    "MRUA": {
        "label":    "Rectiligne uniformément accéléré",
        "tip":      "x(t) = t²/2 selon ê_x : v(t) = t croît linéairement, "
                    "a = (1, 0, 0) constante. Cas modèle de la chute libre 1D.",
        "x":        "t**2/2",
        "y":        "0",
        "z":        "0",
        "duration": 3.0,
        "scale_v":  1.0,
        "scale_a":  1.0,
    },
    "OSC_AMORTI": {
        "label":    "Oscillation amortie 1D",
        "tip":      "x(t) = e^(-t/4)·cos(2t). v et a varient en module ET "
                    "en signe ; ‖v‖ et ‖a‖ décroissent exponentiellement. "
                    "Visualisation du déphasage v⟂x aux extrema.",
        "x":        "exp(-t/4)*cos(2*t)",
        "y":        "0",
        "z":        "0",
        "duration": 4 * _PI,
        "scale_v":  1.0,
        "scale_a":  1.0,
    },
    "BATTEMENT": {
        "label":    "Battement (2 oscillations 1D)",
        "tip":      "x(t) = cos(t) + cos(1.1·t). Modulation d'amplitude "
                    "à la fréquence demi-différence (0.05). v et a "
                    "présentent les mêmes battements.",
        "x":        "cos(t) + cos(1.1*t)",
        "y":        "0",
        "z":        "0",
        "duration": 40 * _PI,
        "scale_v":  1.0,
        "scale_a":  1.0,
    },

    # ── Courbes 2D classiques ───────────────────────────────────────
    "PENDULE_PLAN": {
        "label":    "Pendule plan (oscillation circulaire)",
        "tip":      "M se déplace sur un arc : x = sin(2t), z = -cos(2t). "
                    "Trajectoire = cercle unité, mais parcouru en va-et-vient "
                    "si on remplace 2t par sin(t). Ici parcours uniforme.",
        "x":        "sin(2*t)",
        "y":        "0",
        "z":        "-cos(2*t)",
        "duration": _PI,
        "scale_v":  1.0,
        "scale_a":  1.0,
    },
    "KEPLER_ELLIPSE": {
        "label":    "Orbite elliptique (Kepler simplifié)",
        "tip":      "Ellipse paramétrée x = 2cos(t), y = sin(t), z = 0. "
                    "Paramétrage uniforme (NON conforme à la 2e loi de "
                    "Kepler) : ici a = −OM pointe vers le CENTRE de "
                    "l'ellipse, pas vers un foyer — c'est un oscillateur "
                    "harmonique 2D, pas une orbite de planète.",
        "x":        "2*cos(t)",
        "y":        "sin(t)",
        "z":        "0",
        "duration": 2 * _PI,
        "scale_v":  1.0,
        "scale_a":  1.0,
    },
    "ROSE_3PETALES": {
        "label":    "Rosace polaire (3 pétales)",
        "tip":      "r(θ) = cos(3θ) en coordonnées polaires : "
                    "x = cos(3t)·cos(t), y = cos(3t)·sin(t). v ne "
                    "s'annule jamais (‖v‖² = 9 sin²3t + cos²3t ≥ 1) : "
                    "pas de rebroussement, M repasse par O avec ‖v‖ = 3.",
        "x":        "cos(3*t)*cos(t)",
        "y":        "cos(3*t)*sin(t)",
        "z":        "0",
        "duration": _PI,  # 3 pétales tracés sur [0, π]
        "scale_v":  1.0,
        "scale_a":  1.0,
    },
    "CARDIOIDE": {
        "label":    "Cardioïde",
        "tip":      "Épicycloïde 1:1 : x = (1-cos t)·cos t, "
                    "y = (1-cos t)·sin t. v s'annule au point de "
                    "rebroussement (t=0), a y est non nulle (norme finie).",
        "x":        "(1 - cos(t))*cos(t)",
        "y":        "(1 - cos(t))*sin(t)",
        "z":        "0",
        "duration": 2 * _PI,
        "scale_v":  1.0,
        "scale_a":  1.0,
    },
}


# Ordre d'affichage dans la dropdown : organisé par famille
# (rectiligne → oscillation → courbe 2D → spatial), du plus simple
# au plus chargé pédagogiquement.
PRESET_ORDER = (
    # Rectilignes / 1D
    "MRUA", "OSC1D", "OSC_AMORTI", "BATTEMENT",
    # Mouvements 2D classiques
    "MCU", "MCV", "PENDULE_PLAN", "PARABOLE",
    "KEPLER_ELLIPSE", "LISSAJOUS",
    "ROSE_3PETALES", "CARDIOIDE", "CYCLOIDE", "SPIRALE",
    # Mouvements 3D
    "HELICE",
)


# ----------------------------------------------------------------------------
# Champs cinématiques d'un preset (sans label/tip) : pour snapshot et apply
# ----------------------------------------------------------------------------

def _apply_fields(props, p: dict):
    """Recopie les champs d'un preset sur les props du Vector Viewer simple."""
    props.x_expr     = p["x"]
    props.y_expr     = p["y"]
    props.z_expr     = p["z"]
    props.t_duration = float(p["duration"])
    props.scale_v    = float(p["scale_v"])
    props.scale_a    = float(p["scale_a"])


def _snapshot_fields(props) -> dict:
    """Capture les champs cinématiques courants pour enregistrement."""
    return {
        "x":        props.x_expr,
        "y":        props.y_expr,
        "z":        props.z_expr,
        "duration": float(props.t_duration),
        "scale_v":  float(props.scale_v),
        "scale_a":  float(props.scale_a),
    }


# ----------------------------------------------------------------------------
# Store : façade unique builtins + utilisateur
# ----------------------------------------------------------------------------

STORE = preset_storage.PresetStore(
    builtin=PRESETS,
    builtin_order=PRESET_ORDER,
    filename="vector_viewer_presets.json",
    fields_apply=_apply_fields,
    fields_snapshot=_snapshot_fields,
)


def enum_items_callback(self, context):
    """Callback pour ``EnumProperty.items``. Retourne la liste fusionnée
    builtins + utilisateur, mémorisée par STORE pour garantir la
    persistance des chaînes côté Blender."""
    return STORE.enum_items()


# ----------------------------------------------------------------------------
# Opérateurs
# ----------------------------------------------------------------------------

class VECTORVIEWER_OT_apply_preset(bpy.types.Operator):
    """Applique le preset sélectionné dans le menu et reconstruit
    immédiatement la visualisation."""

    bl_idname = "vector_viewer.apply_preset"
    bl_label = "Appliquer le preset"
    bl_description = (
        "Recopie les expressions, la durée et les échelles du preset "
        "sélectionné sur les champs du panneau, puis reconstruit la "
        "visualisation"
    )
    bl_options = {'REGISTER', 'UNDO'}

    preset_id: StringProperty(
        name="Preset",
        description="Identifiant du preset à appliquer",
        default="",
    )

    def execute(self, context):
        props = context.scene.vector_viewer

        pid = self.preset_id or props.preset_choice
        if not pid:
            self.report({'WARNING'}, "Aucun preset sélectionné.")
            return {'CANCELLED'}

        try:
            STORE.apply_to(props, pid)
        except KeyError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        if props.preset_choice != pid:
            props.preset_choice = pid

        result = bpy.ops.vector_viewer.build()
        if 'CANCELLED' in result:
            return {'CANCELLED'}

        self.report({'INFO'}, f"Preset « {STORE.label(pid)} » appliqué.")
        return {'FINISHED'}


class VECTORVIEWER_OT_save_user_preset(bpy.types.Operator):
    """Enregistre les valeurs courantes (expressions, durée, échelles)
    comme preset utilisateur, persistant à travers les sessions."""

    bl_idname = "vector_viewer.save_user_preset"
    bl_label = "Enregistrer comme preset"
    bl_description = (
        "Capture x(t), y(t), z(t), la durée et les échelles courantes "
        "et les enregistre comme preset utilisateur réutilisable"
    )
    bl_options = {'REGISTER'}

    label: StringProperty(
        name="Nom",
        description="Nom du preset tel qu'il apparaîtra dans le menu",
        default="Mon preset",
    )
    tip: StringProperty(
        name="Description",
        description="Description courte (facultative) — affichée en tooltip",
        default="",
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "label")
        layout.prop(self, "tip")
        layout.label(
            text="Enregistré dans le config utilisateur de Blender.",
            icon='INFO',
        )

    def execute(self, context):
        props = context.scene.vector_viewer
        try:
            new_pid = STORE.save_user(self.label, self.tip, props)
        except (ValueError, OSError) as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        # Bascule sur le preset fraîchement créé. L'invalidation du cache
        # Enum est déjà faite par save_user → la nouvelle valeur sera
        # acceptée par Blender lors de l'assignation.
        props.preset_choice = new_pid

        self.report(
            {'INFO'},
            f"Preset « {self.label} » enregistré (id : {new_pid})."
        )
        return {'FINISHED'}


class VECTORVIEWER_OT_update_user_preset(bpy.types.Operator):
    """Met à jour le preset utilisateur courant avec les valeurs
    actuelles du panneau (expressions, durée, échelles). Le nom et la
    description du preset sont préservés."""

    bl_idname = "vector_viewer.update_user_preset"
    bl_label = "Mettre à jour ce preset"
    bl_description = (
        "Réécrit le preset utilisateur sélectionné avec les valeurs "
        "actuelles du panneau (le nom et la description sont préservés)"
    )
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        sc = getattr(context, "scene", None)
        if sc is None:
            return False
        props = getattr(sc, "vector_viewer", None)
        if props is None:
            return False
        return STORE.is_user(props.preset_choice)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        props = context.scene.vector_viewer
        pid = props.preset_choice
        label = STORE.label(pid)
        try:
            ok = STORE.update_user(pid, props)
        except OSError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        if not ok:
            self.report({'ERROR'},
                        "Mise à jour impossible (preset inconnu ou builtin).")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Preset « {label} » mis à jour.")
        return {'FINISHED'}


class VECTORVIEWER_OT_delete_user_preset(bpy.types.Operator):
    """Supprime le preset utilisateur actuellement sélectionné. Les
    presets builtins ne sont pas supprimables."""

    bl_idname = "vector_viewer.delete_user_preset"
    bl_label = "Supprimer ce preset"
    bl_description = (
        "Supprime définitivement le preset utilisateur sélectionné "
        "(les builtins sont protégés)"
    )
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        sc = getattr(context, "scene", None)
        if sc is None:
            return False
        props = getattr(sc, "vector_viewer", None)
        if props is None:
            return False
        return STORE.is_user(props.preset_choice)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        props = context.scene.vector_viewer
        pid = props.preset_choice
        label = STORE.label(pid)

        if not STORE.delete_user(pid):
            self.report({'ERROR'}, "Suppression impossible "
                                   "(preset builtin ou échec d'écriture).")
            return {'CANCELLED'}

        # Replie sur le premier builtin
        props.preset_choice = STORE.builtin_order[0]

        self.report({'INFO'}, f"Preset « {label} » supprimé.")
        return {'FINISHED'}


class VECTORVIEWER_OT_refresh_user_presets(bpy.types.Operator):
    """Recharge le fichier JSON des presets utilisateur depuis le disque.

    Utile lorsque le fichier a été édité manuellement à l'extérieur de
    Blender (sauvegarde, réception d'un preset partagé, …) : la dropdown
    ne se rafraîchit pas automatiquement dans ce cas, car elle s'appuie
    sur le cache mémoire de ``PresetStore``."""

    bl_idname = "vector_viewer.refresh_user_presets"
    bl_label = "Rafraîchir depuis le disque"
    bl_description = (
        "Recharge la bibliothèque des presets utilisateur depuis le "
        "fichier JSON (utile après une édition manuelle)"
    )
    bl_options = {'REGISTER'}

    def execute(self, context):
        STORE.invalidate()
        # Force l'UI à se redessiner pour faire apparaître la nouvelle
        # liste dans la dropdown.
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        n = len(STORE.get_user())
        self.report({'INFO'}, f"Presets utilisateur rechargés ({n}).")
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────
# Export / Import (factory dans preset_storage)
# ─────────────────────────────────────────────────────────────────────

def _refresh_panel_after_import(context):
    """Callback de rafraîchissement après import : invalide le cache du
    STORE et redemande un redessin de la 3D View."""
    STORE.invalidate()
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


VECTORVIEWER_OT_export_user_presets = preset_storage.make_export_operator(
    idname="vector_viewer.export_user_presets",
    label="Exporter mes presets",
    description=(
        "Exporte la bibliothèque de presets utilisateur courante du "
        "Vector Viewer simple vers un fichier JSON partageable"
    ),
    store_attr="presets:STORE",
    default_filename="vector_viewer_simple_presets.json",
)


VECTORVIEWER_OT_import_user_presets = preset_storage.make_import_operator(
    idname="vector_viewer.import_user_presets",
    label="Importer des presets",
    description=(
        "Importe une bibliothèque de presets depuis un fichier JSON, "
        "en fusionnant avec les presets utilisateur existants"
    ),
    store_attr="presets:STORE",
    refresh_callback=_refresh_panel_after_import,
)
