"""Bibliothèque de presets de palette pour les matériaux des flèches.

Chaque preset est un dictionnaire ``{nom_matériau: (R, G, B)}`` où les
valeurs sont en RGB linéaire (0-1). Les noms suivent ceux de
``materials.DEFAULT_PALETTE`` ; les clés inconnues sont ignorées à
l'application (résilience aux renommages futurs).

Les builtins couvrent quelques contextes pédagogiques courants :
    - Defaut       : palette livrée avec l'extension
    - Vif          : couleurs saturées, fond sombre
    - Pastel       : couleurs douces, fond clair
    - Daltonien    : palette compatible deutéranopie/protanopie (Wong)
    - Monochrome   : nuances de gris pour publication N&B
    - Coriolis     : tout en gris discret sauf a_c en rose vif
                     (pour mettre l'accent sur la flèche-clé)

Les presets utilisateur sont enregistrés dans ::

    <user_config>/vector_viewer/materials_presets.json

et persistent à travers les sessions et les .blend.
"""

import bpy
from bpy.props import StringProperty
from bpy.types import PropertyGroup, Operator
from bpy.props import EnumProperty

from . import preset_storage, materials


# ----------------------------------------------------------------------------
# Définition des palettes builtins
# ----------------------------------------------------------------------------

# Référence rapide vers les noms de matériau, pour ne pas les retaper.
_M = materials.DEFAULT_PALETTE


def _palette_default():
    """Snapshot littéral de DEFAULT_PALETTE."""
    return dict(_M)


def _palette_vif():
    """Couleurs saturées, lisibles sur fond sombre."""
    return {
        "VV_position":     (1.00, 0.95, 0.20),
        "VV_velocity":     (0.10, 1.00, 0.20),
        "VV_acceleration": (1.00, 0.10, 0.10),
        "VV_traj_OM_simple": (0.55, 0.50, 0.10),
        "VV_OOp":          (0.70, 0.70, 0.95),
        "VV_OpM":          (1.00, 0.95, 0.20),
        "VV_OM":           (1.00, 1.00, 1.00),
        "VV_vr":           (0.70, 1.00, 0.10),
        "VV_ve":           (0.00, 0.95, 0.95),
        "VV_va":           (0.00, 0.85, 0.10),
        "VV_ar":           (1.00, 0.55, 0.00),
        "VV_ae":           (0.85, 0.10, 1.00),
        "VV_ac":           (1.00, 0.00, 0.50),
        "VV_aa":           (1.00, 0.05, 0.05),
        "VV_Omega":        (1.00, 0.95, 0.00),
        "VV_traj_OOp":     (0.40, 0.40, 0.65),
        "VV_traj_OM":      (0.70, 0.65, 0.55),
        "VV_traj_OpM":     (0.70, 0.55, 0.20),
        "VV_R_x":          (1.00, 0.00, 0.00),
        "VV_R_y":          (0.00, 1.00, 0.00),
        "VV_R_z":          (0.00, 0.20, 1.00),
        "VV_Rp_x":         (1.00, 0.55, 0.55),
        "VV_Rp_y":         (0.55, 1.00, 0.55),
        "VV_Rp_z":         (0.55, 0.65, 1.00),
    }


def _palette_pastel():
    """Couleurs douces (lisibles sur fond clair, en présentation papier)."""
    return {
        "VV_position":     (0.95, 0.90, 0.65),
        "VV_velocity":     (0.55, 0.85, 0.60),
        "VV_acceleration": (0.95, 0.65, 0.60),
        "VV_traj_OM_simple": (0.85, 0.78, 0.55),
        "VV_OOp":          (0.75, 0.75, 0.85),
        "VV_OpM":          (0.95, 0.90, 0.65),
        "VV_OM":           (0.95, 0.95, 0.90),
        "VV_vr":           (0.80, 0.95, 0.60),
        "VV_ve":           (0.55, 0.85, 0.85),
        "VV_va":           (0.55, 0.80, 0.55),
        "VV_ar":           (0.95, 0.80, 0.55),
        "VV_ae":           (0.85, 0.70, 0.95),
        "VV_ac":           (0.95, 0.70, 0.85),
        "VV_aa":           (0.85, 0.55, 0.55),
        "VV_Omega":        (0.95, 0.90, 0.50),
        "VV_traj_OOp":     (0.55, 0.55, 0.65),
        "VV_traj_OM":      (0.75, 0.70, 0.55),
        "VV_traj_OpM":     (0.75, 0.65, 0.45),
        "VV_R_x":          (0.95, 0.65, 0.65),
        "VV_R_y":          (0.65, 0.95, 0.65),
        "VV_R_z":          (0.65, 0.75, 0.95),
        "VV_Rp_x":         (0.85, 0.55, 0.55),
        "VV_Rp_y":         (0.55, 0.85, 0.55),
        "VV_Rp_z":         (0.55, 0.65, 0.85),
    }


def _palette_daltonien():
    """Palette de Wong (8 couleurs distinguables par les daltoniens
    deutéranopes et protanopes), réutilisée pour les 20 matériaux en
    réservant chaque couleur à une « famille » cinématique."""
    # 8 couleurs Wong (https://www.nature.com/articles/nmeth.1618)
    BLACK   = (0.00, 0.00, 0.00)
    ORANGE  = (0.90, 0.60, 0.00)
    SKY     = (0.35, 0.70, 0.90)
    GREEN   = (0.00, 0.60, 0.50)
    YELLOW  = (0.95, 0.90, 0.25)
    BLUE    = (0.00, 0.45, 0.70)
    VERMIL  = (0.80, 0.40, 0.00)
    PURPLE  = (0.80, 0.60, 0.70)

    # Couleurs Wong sombres pour les trajectoires (mêmes familles que
    # leurs vecteurs respectifs, mais à 50% de luminosité)
    DIM_SKY    = tuple(c * 0.5 for c in SKY)
    DIM_BLACK  = (0.20, 0.20, 0.20)  # noir → gris sombre (sinon invisible)
    DIM_YELLOW = tuple(c * 0.5 for c in YELLOW)

    return {
        "VV_position":     YELLOW,
        "VV_velocity":     GREEN,
        "VV_acceleration": VERMIL,
        # Trajectoire OM simple : version DIM_YELLOW (cohérent avec position)
        "VV_traj_OM_simple": DIM_YELLOW,
        # Position : nuances neutres (sky / yellow / black)
        "VV_OOp":          SKY,
        "VV_OpM":          YELLOW,
        "VV_OM":           BLACK,
        # Vitesses : famille verts/bleus
        "VV_vr":           GREEN,
        "VV_ve":           BLUE,
        "VV_va":           SKY,
        # Accélérations : famille oranges/violets
        "VV_ar":           ORANGE,
        "VV_ae":           PURPLE,
        "VV_ac":           VERMIL,   # Coriolis = vermillon, le plus saillant
        "VV_aa":           VERMIL,
        # Rotation : jaune (saillant, isolé)
        "VV_Omega":        YELLOW,
        # Trajectoires : versions assombries des couleurs des vecteurs
        "VV_traj_OOp":     DIM_SKY,
        "VV_traj_OM":      DIM_BLACK,
        "VV_traj_OpM":     DIM_YELLOW,
        # Trièdres : RGB Wong (pas de rouge pur)
        "VV_R_x":          VERMIL,
        "VV_R_y":          GREEN,
        "VV_R_z":          BLUE,
        "VV_Rp_x":         ORANGE,
        "VV_Rp_y":         SKY,
        "VV_Rp_z":         PURPLE,
    }


def _palette_mono():
    """Nuances de gris (publication noir et blanc). Les nuances varient
    pour différencier les flèches même en N&B."""
    g = lambda v: (v, v, v)
    return {
        "VV_position":     g(0.95),
        "VV_velocity":     g(0.70),
        "VV_acceleration": g(0.40),
        "VV_traj_OM_simple": g(0.50),
        "VV_OOp":          g(0.55),
        "VV_OpM":          g(0.85),
        "VV_OM":           g(1.00),
        "VV_vr":           g(0.85),
        "VV_ve":           g(0.65),
        "VV_va":           g(0.45),
        "VV_ar":           g(0.85),
        "VV_ae":           g(0.65),
        "VV_ac":           g(0.30),
        "VV_aa":           g(0.45),
        "VV_Omega":        g(0.95),
        "VV_traj_OOp":     g(0.40),
        "VV_traj_OM":      g(0.55),
        "VV_traj_OpM":     g(0.30),
        "VV_R_x":          g(0.95),
        "VV_R_y":          g(0.70),
        "VV_R_z":          g(0.45),
        "VV_Rp_x":         g(0.80),
        "VV_Rp_y":         g(0.55),
        "VV_Rp_z":         g(0.30),
    }


def _palette_focus_coriolis():
    """Tout en gris terne sauf a_c (rose vif) et Ω (jaune-or). Sert à
    isoler visuellement la flèche de Coriolis dans une démonstration
    pédagogique."""
    dim = (0.35, 0.35, 0.40)
    return {
        "VV_position":     dim,
        "VV_velocity":     dim,
        "VV_acceleration": dim,
        "VV_traj_OM_simple": dim,
        "VV_OOp":          dim,
        "VV_OpM":          dim,
        "VV_OM":           dim,
        "VV_vr":           dim,
        "VV_ve":           dim,
        "VV_va":           dim,
        "VV_ar":           dim,
        "VV_ae":           dim,
        "VV_ac":           (1.00, 0.10, 0.55),  # rose vif intact
        "VV_aa":           dim,
        "VV_Omega":        (1.00, 0.92, 0.10),  # jaune-or intact
        "VV_traj_OOp":     dim,
        "VV_traj_OM":      dim,
        "VV_traj_OpM":     dim,
        "VV_R_x":          dim,
        "VV_R_y":          dim,
        "VV_R_z":          dim,
        "VV_Rp_x":         dim,
        "VV_Rp_y":         dim,
        "VV_Rp_z":         dim,
    }


# Format de chaque entrée : {label, tip, palette}
# La palette est inlinée comme dict sous la clé "colors" pour rester en
# phase avec le format JSON utilisateur (pas de fonctions à sérialiser).
PRESETS = {
    "DEFAULT": {
        "label":   "Défaut",
        "tip":     "Palette livrée avec l'extension. Couleurs équilibrées.",
        "colors":  _palette_default(),
    },
    "VIF": {
        "label":   "Vif (fond sombre)",
        "tip":     "Couleurs saturées, optimisées pour rendu sur fond sombre.",
        "colors":  _palette_vif(),
    },
    "PASTEL": {
        "label":   "Pastel (fond clair)",
        "tip":     "Couleurs douces, lisibles sur fond clair (papier, "
                   "présentation projetée).",
        "colors":  _palette_pastel(),
    },
    "DALTONIEN": {
        "label":   "Daltonien-safe (Wong)",
        "tip":     "Palette de Wong (Nature Methods 2011) compatible "
                   "deutéranopie et protanopie.",
        "colors":  _palette_daltonien(),
    },
    "MONOCHROME": {
        "label":   "Monochrome (N&B)",
        "tip":     "Nuances de gris pour publication noir et blanc. "
                   "Les flèches restent distinguables par leur clarté.",
        "colors":  _palette_mono(),
    },
    "FOCUS_CORIOLIS": {
        "label":   "Focus Coriolis",
        "tip":     "Tous les vecteurs en gris discret sauf a_c (rose) "
                   "et Ω (jaune). Pour démo de la pseudo-force de Coriolis.",
        "colors":  _palette_focus_coriolis(),
    },
}


PRESET_ORDER = (
    "DEFAULT", "VIF", "PASTEL",
    "DALTONIEN", "MONOCHROME", "FOCUS_CORIOLIS",
)


# ----------------------------------------------------------------------------
# Adaptation au schéma PresetStore (apply / snapshot)
# ----------------------------------------------------------------------------
# PresetStore attend des fonctions ``fields_apply(props, preset_dict)``
# et ``fields_snapshot(props)``. Pour les matériaux, ``props`` n'est pas
# utilisé (les couleurs vivent dans bpy.data.materials, pas dans un
# PropertyGroup) — l'argument est accepté mais ignoré. Cette signature
# uniforme permet le partage de PresetStore entre tous les types de presets.

def _apply_fields(_props, preset_dict):
    """Applique le preset : extrait ``colors`` et le passe à
    ``materials.apply_palette``."""
    colors = preset_dict.get("colors", {})
    materials.apply_palette(colors)


def _snapshot_fields(_props):
    """Capture l'état effectif des matériaux. Encapsulé sous la clé
    ``colors`` pour rester en phase avec le format des builtins."""
    return {"colors": materials.snapshot_palette()}


# ----------------------------------------------------------------------------
# Store
# ----------------------------------------------------------------------------

STORE = preset_storage.PresetStore(
    builtin=PRESETS,
    builtin_order=PRESET_ORDER,
    filename="materials_presets.json",
    fields_apply=_apply_fields,
    fields_snapshot=_snapshot_fields,
)


def enum_items_callback(self, context):
    """Callback ``EnumProperty.items`` : builtins + utilisateur."""
    return STORE.enum_items()


# ----------------------------------------------------------------------------
# PropertyGroup (juste un sélecteur de palette par scène)
# ----------------------------------------------------------------------------

class VectorViewerMaterialsProperties(PropertyGroup):
    preset_choice: EnumProperty(
        name="Palette",
        description="Palette de couleurs des flèches. Les presets ★ "
                    "sont des palettes utilisateur enregistrées.",
        items=enum_items_callback,
    )


# ----------------------------------------------------------------------------
# Opérateurs
# ----------------------------------------------------------------------------

class VECTORVIEWER_OT_apply_materials_preset(Operator):
    """Applique la palette sélectionnée aux matériaux des flèches."""

    bl_idname = "vector_viewer.apply_materials_preset"
    bl_label = "Appliquer la palette"
    bl_description = (
        "Recopie les couleurs de la palette sélectionnée sur les "
        "matériaux des flèches (les matériaux pas encore créés "
        "auront ces couleurs au prochain Build)"
    )
    bl_options = {'REGISTER', 'UNDO'}

    preset_id: StringProperty(default="")

    def execute(self, context):
        props = context.scene.vector_viewer_materials
        pid = self.preset_id or props.preset_choice
        if not pid:
            self.report({'WARNING'}, "Aucune palette sélectionnée.")
            return {'CANCELLED'}

        try:
            STORE.apply_to(None, pid)
        except KeyError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        if props.preset_choice != pid:
            props.preset_choice = pid

        # Force redraw 3D View pour montrer les nouvelles couleurs
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        self.report({'INFO'}, f"Palette « {STORE.label(pid)} » appliquée.")
        return {'FINISHED'}


class VECTORVIEWER_OT_save_materials_preset(Operator):
    """Enregistre les couleurs courantes des matériaux comme palette
    utilisateur, persistante à travers les sessions."""

    bl_idname = "vector_viewer.save_materials_preset"
    bl_label = "Enregistrer la palette"
    bl_description = (
        "Capture les couleurs effectives des matériaux VV_* et les "
        "enregistre comme palette utilisateur réutilisable"
    )
    bl_options = {'REGISTER'}

    label: StringProperty(name="Nom", default="Ma palette")
    tip: StringProperty(name="Description", default="")

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
        try:
            new_pid = STORE.save_user(self.label, self.tip, None)
        except (ValueError, OSError) as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        context.scene.vector_viewer_materials.preset_choice = new_pid
        self.report({'INFO'}, f"Palette « {self.label} » enregistrée.")
        return {'FINISHED'}


class VECTORVIEWER_OT_update_materials_preset(Operator):
    """Met à jour la palette utilisateur courante avec les couleurs
    actuelles des matériaux. Préserve le nom et la description du preset."""

    bl_idname = "vector_viewer.update_materials_preset"
    bl_label = "Mettre à jour la palette"
    bl_description = (
        "Réécrit la palette utilisateur sélectionnée avec les couleurs "
        "actuelles des matériaux (le nom et la description sont préservés)"
    )
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        sc = getattr(context, "scene", None)
        if sc is None:
            return False
        props = getattr(sc, "vector_viewer_materials", None)
        if props is None:
            return False
        return STORE.is_user(props.preset_choice)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        pid = context.scene.vector_viewer_materials.preset_choice
        label = STORE.label(pid)
        try:
            ok = STORE.update_user(pid, None)
        except OSError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        if not ok:
            self.report({'ERROR'},
                        "Mise à jour impossible (palette inconnue ou builtin).")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Palette « {label} » mise à jour.")
        return {'FINISHED'}


class VECTORVIEWER_OT_delete_materials_preset(Operator):
    """Supprime la palette utilisateur sélectionnée."""

    bl_idname = "vector_viewer.delete_materials_preset"
    bl_label = "Supprimer cette palette"
    bl_description = (
        "Supprime définitivement la palette utilisateur sélectionnée "
        "(les builtins sont protégées)"
    )
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        sc = getattr(context, "scene", None)
        if sc is None:
            return False
        props = getattr(sc, "vector_viewer_materials", None)
        if props is None:
            return False
        return STORE.is_user(props.preset_choice)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        props = context.scene.vector_viewer_materials
        pid = props.preset_choice
        label = STORE.label(pid)

        if not STORE.delete_user(pid):
            self.report({'ERROR'}, "Suppression impossible "
                                   "(palette builtin ou échec d'écriture).")
            return {'CANCELLED'}

        # Replie sur le premier builtin
        props.preset_choice = STORE.builtin_order[0]
        self.report({'INFO'}, f"Palette « {label} » supprimée.")
        return {'FINISHED'}


class VECTORVIEWER_OT_refresh_materials_presets(Operator):
    """Recharge le fichier JSON des palettes utilisateur depuis le disque."""

    bl_idname = "vector_viewer.refresh_materials_presets"
    bl_label = "Rafraîchir depuis le disque"
    bl_description = (
        "Recharge la bibliothèque des palettes utilisateur depuis le "
        "fichier JSON (utile après une édition manuelle)"
    )
    bl_options = {'REGISTER'}

    def execute(self, context):
        STORE.invalidate()
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        n = len(STORE.get_user())
        self.report({'INFO'}, f"Palettes utilisateur rechargées ({n}).")
        return {'FINISHED'}


class VECTORVIEWER_OT_reset_materials(Operator):
    """Restaure la palette par défaut (sans toucher aux palettes
    utilisateur enregistrées)."""

    bl_idname = "vector_viewer.reset_materials"
    bl_label = "Restaurer la palette par défaut"
    bl_description = (
        "Recopie la palette « Défaut » sur les matériaux. "
        "Les palettes utilisateur enregistrées ne sont pas affectées."
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        materials.reset_to_default()
        context.scene.vector_viewer_materials.preset_choice = "DEFAULT"
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        self.report({'INFO'}, "Palette par défaut restaurée.")
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────
# Export / Import
# ─────────────────────────────────────────────────────────────────────

def _refresh_panel_after_import(context):
    STORE.invalidate()
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


VECTORVIEWER_OT_export_materials_presets = preset_storage.make_export_operator(
    idname="vector_viewer.export_materials_presets",
    label="Exporter mes palettes",
    description=(
        "Exporte la bibliothèque de palettes utilisateur courante vers "
        "un fichier JSON partageable"
    ),
    store_attr="materials_presets:STORE",
    default_filename="vector_viewer_palettes.json",
)


VECTORVIEWER_OT_import_materials_presets = preset_storage.make_import_operator(
    idname="vector_viewer.import_materials_presets",
    label="Importer des palettes",
    description=(
        "Importe une bibliothèque de palettes depuis un fichier JSON, "
        "en fusionnant avec les palettes utilisateur existantes"
    ),
    store_attr="materials_presets:STORE",
    refresh_callback=_refresh_panel_after_import,
)
