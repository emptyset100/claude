"""Panneau « Matériaux (Palettes) » de l'extension RealFn Viewer.

Apparaît dans la N-zone de la 3D View, onglet « RealFn », à côté du
panneau principal. Replié par défaut.

Permet de gérer la bibliothèque de palettes de couleurs des courbes :
appliquer une palette, en enregistrer une nouvelle, mettre à jour ou
supprimer une palette utilisateur, exporter / importer la bibliothèque.
"""

import bpy
from bpy.types import Panel

from . import materials_presets


class REALFN_MAT_PT_panel(Panel):
    bl_label = "Couleurs (palettes)"
    bl_order = 3
    bl_idname = "REALFN_MAT_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Maths"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.realfn_materials

        # ── Bibliothèque de palettes ───────────────────────────────────
        box = layout.box()
        box.label(text="Bibliothèque de palettes", icon='COLOR')

        row = box.row(align=True)
        row.prop(props, "preset_choice", text="")
        op = row.operator(
            "realfn.apply_materials_preset",
            text="Appliquer", icon='IMPORT',
        )
        op.preset_id = ""

        # Actions CRUD
        row = box.row(align=True)
        row.operator(
            "realfn.save_materials_preset",
            text="Enregistrer", icon='ADD',
        )

        is_user = materials_presets.is_user_pid(props.preset_choice)

        sub = row.row(align=True)
        sub.enabled = is_user
        sub.operator(
            "realfn.update_materials_preset",
            text="Mettre à jour", icon='FILE_REFRESH',
        )

        sub = row.row(align=True)
        sub.enabled = is_user
        sub.operator(
            "realfn.delete_materials_preset",
            text="Supprimer", icon='REMOVE',
        )

        row.operator(
            "realfn.refresh_materials_presets",
            text="", icon='FILE_REFRESH',
        )

        # Export / Import
        row = box.row(align=True)
        row.operator(
            "realfn.export_materials_presets",
            text="Exporter", icon='EXPORT',
        )
        row.operator(
            "realfn.import_materials_presets",
            text="Importer", icon='IMPORT',
        )

        # ── Note d'utilisation ─────────────────────────────────────────
        col = layout.column(align=True)
        col.label(
            text="Pour modifier les couleurs : Properties › Material",
            icon='INFO',
        )
        col.label(
            text="ou Shader Editor. Puis « Mettre à jour ».",
        )

        # ── Reset ──────────────────────────────────────────────────────
        layout.separator()
        layout.operator(
            "realfn.reset_materials",
            text="Restaurer la palette par défaut",
            icon='LOOP_BACK',
        )
