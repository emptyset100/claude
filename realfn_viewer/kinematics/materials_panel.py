"""Panneau « Matériaux » de l'extension Vector Viewer.

Apparaît dans la N-zone de la 3D View, dans le tab « Vector Viewer »,
à côté des panneaux principaux. Replié par défaut.

Permet de gérer la bibliothèque de palettes de couleurs des flèches :
appliquer une palette, en enregistrer une nouvelle, mettre à jour une
palette existante, en supprimer une.
"""

import bpy
from bpy.types import Panel

from . import preset_storage


class VECTORVIEWER_MAT_PT_panel(Panel):
    bl_label = "Couleurs des flèches animées (2 · et 3 ·)"
    bl_parent_id = "REALFN_MAT_PT_panel"
    bl_idname = "VECTORVIEWER_MAT_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Maths"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.vector_viewer_materials

        # ── Bibliothèque de palettes ───────────────────────────────────
        box = layout.box()
        box.label(text="Bibliothèque de palettes", icon='COLOR')
        row = box.row(align=True)
        row.prop(props, "preset_choice", text="")
        op = row.operator(
            "vector_viewer.apply_materials_preset",
            text="Appliquer", icon='IMPORT',
        )
        op.preset_id = ""

        # Ligne d'actions sur les palettes utilisateur
        row = box.row(align=True)
        row.operator(
            "vector_viewer.save_materials_preset",
            text="Enregistrer", icon='ADD',
        )

        is_user = preset_storage.is_user_pid(props.preset_choice)

        sub = row.row(align=True)
        sub.enabled = is_user
        sub.operator(
            "vector_viewer.update_materials_preset",
            text="Mettre à jour", icon='FILE_REFRESH',
        )

        sub = row.row(align=True)
        sub.enabled = is_user
        sub.operator(
            "vector_viewer.delete_materials_preset",
            text="Supprimer", icon='REMOVE',
        )

        row.operator(
            "vector_viewer.refresh_materials_presets",
            text="", icon='FILE_REFRESH',
        )

        # Ligne d'I/O : Exporter / Importer
        row = box.row(align=True)
        row.operator(
            "vector_viewer.export_materials_presets",
            text="Exporter", icon='EXPORT',
        )
        row.operator(
            "vector_viewer.import_materials_presets",
            text="Importer", icon='IMPORT',
        )

        # ── Note d'utilisation ─────────────────────────────────────────
        col = layout.column(align=True)
        col.label(
            text="Pour modifier les couleurs : Properties › Material",
            icon='INFO',
        )
        col.label(
            text="ou Shader Editor sur un objet VV. Puis « Mettre à jour ».",
        )

        # ── Reset ──────────────────────────────────────────────────────
        layout.separator()
        layout.operator(
            "vector_viewer.reset_materials",
            text="Restaurer la palette par défaut",
            icon='LOOP_BACK',
        )
