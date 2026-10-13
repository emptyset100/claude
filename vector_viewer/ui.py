"""Panneau de l'extension dans la N-zone de la 3D View."""

import bpy
from bpy.types import Panel

from . import preset_storage


class VECTORVIEWER_PT_panel(Panel):
    bl_label = "Vector Viewer"
    bl_idname = "VECTORVIEWER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Vector Viewer"

    def draw(self, context):
        layout = self.layout
        props = context.scene.vector_viewer

        # ── Bibliothèque de presets ─────────────────────────────────────
        box = layout.box()
        box.label(text="Bibliothèque de presets", icon='PRESET')
        row = box.row(align=True)
        row.prop(props, "preset_choice", text="")
        op = row.operator(
            "vector_viewer.apply_preset", text="Appliquer", icon='IMPORT',
        )
        op.preset_id = ""  # → l'opérateur lit props.preset_choice

        # Ligne d'actions sur les presets utilisateur
        row = box.row(align=True)
        row.operator(
            "vector_viewer.save_user_preset",
            text="Enregistrer", icon='ADD',
        )

        is_user = preset_storage.is_user_pid(props.preset_choice)

        sub = row.row(align=True)
        sub.enabled = is_user
        sub.operator(
            "vector_viewer.update_user_preset",
            text="Mettre à jour", icon='FILE_REFRESH',
        )

        # Le bouton Supprimer est désactivé tant qu'un preset builtin
        # est sélectionné (poll() de l'opérateur sert de double-garde).
        sub = row.row(align=True)
        sub.enabled = is_user
        sub.operator(
            "vector_viewer.delete_user_preset",
            text="Supprimer", icon='REMOVE',
        )
        row.operator(
            "vector_viewer.refresh_user_presets",
            text="", icon='FILE_REFRESH',
        )

        # Ligne d'I/O : Exporter / Importer la bibliothèque utilisateur
        row = box.row(align=True)
        row.operator(
            "vector_viewer.export_user_presets",
            text="Exporter", icon='EXPORT',
        )
        row.operator(
            "vector_viewer.import_user_presets",
            text="Importer", icon='IMPORT',
        )

        # ── Vecteur position ────────────────────────────────────────────
        box = layout.box()
        box.label(text="Vecteur position r(t)", icon='IPO_SINE')
        col = box.column(align=True)
        col.prop(props, "x_expr")
        col.prop(props, "y_expr")
        col.prop(props, "z_expr")
        box.label(
            text="t : variable temps. Fonctions : cos, sin, exp, sqrt, …",
            icon='INFO',
        )

        # ── Animation / scène ──────────────────────────────────────────
        box = layout.box()
        box.label(text="Animation", icon='TIME')
        col = box.column(align=True)
        col.prop(props, "fps")
        col.prop(props, "t_start")
        col.prop(props, "t_duration")

        # ── Échelles d'affichage ────────────────────────────────────────
        box = layout.box()
        box.label(text="Échelles", icon='ARROW_LEFTRIGHT')
        col = box.column(align=True)
        col.prop(props, "scale_v")
        col.prop(props, "scale_a")

        # ── Affichage des flèches ───────────────────────────────────────
        box = layout.box()
        box.label(text="Affichage", icon='HIDE_OFF')
        col = box.column(align=True)
        col.prop(props, "show_position")
        col.prop(props, "show_vitesse")
        col.prop(props, "show_acceleration")

        # ── Trajectoire OM ──────────────────────────────────────────────
        box = layout.box()
        box.label(text="Trajectoire OM", icon='IPO_BEZIER')
        col = box.column(align=True)
        col.prop(props, "show_trajectory")
        col.prop(props, "traj_radius")
        box.label(
            text="Échantillonnée au build sur [t_start, t_start+T]",
            icon='INFO',
        )

        # ── Repère R (base orthonormée) ─────────────────────────────────
        box = layout.box()
        box.label(text="Repère R (base orthonormée)", icon='ORIENTATION_GLOBAL')
        col = box.column(align=True)
        col.prop(props, "show_frame")
        col.prop(props, "axis_length")
        box.label(
            text="Trièdre RGB ancré à l'origine. Longueur fixée au build.",
            icon='INFO',
        )

        # ── Objet hôte ──────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Objet hôte", icon='OBJECT_DATA')
        box.prop(props, "host_name")

        # ── Actions ─────────────────────────────────────────────────────
        layout.separator()
        col = layout.column(align=True)
        col.scale_y = 1.3
        col.operator("vector_viewer.build", icon='PLAY')
        col.operator("vector_viewer.clear", icon='TRASH')
