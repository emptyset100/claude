"""Panneau « Composition (Référentiels) » de l'extension Vector Viewer.

Apparaît dans la N-zone de la 3D View, dans le même tab « Vector
Viewer » que le panneau principal, sous celui-ci, replié par défaut."""

import bpy
from bpy.types import Panel

from . import composition_presets, didactic, preset_storage


class VECTORCOMP_PT_panel(Panel):
    bl_label = "3 · Changement de référentiel"
    bl_order = 2
    bl_idname = "VECTORCOMP_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Maths"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.vector_comp

        # ── Bibliothèque de presets ────────────────────────────────────
        box = layout.box()
        box.label(text="Bibliothèque de presets", icon='PRESET')
        row = box.row(align=True)
        row.prop(props, "preset_choice", text="")
        op = row.operator(
            "vector_comp.apply_preset", text="Appliquer", icon='IMPORT',
        )
        op.preset_id = ""  # → l'opérateur lit props.preset_choice
        didactic.draw_tip(box, composition_presets.STORE, props.preset_choice)

        # Ligne d'actions sur les presets utilisateur
        row = box.row(align=True)
        row.operator(
            "vector_comp.save_user_preset",
            text="Enregistrer", icon='ADD',
        )

        is_user = preset_storage.is_user_pid(props.preset_choice)

        sub = row.row(align=True)
        sub.enabled = is_user
        sub.operator(
            "vector_comp.update_user_preset",
            text="Mettre à jour", icon='FILE_REFRESH',
        )

        sub = row.row(align=True)
        sub.enabled = is_user
        sub.operator(
            "vector_comp.delete_user_preset",
            text="Supprimer", icon='REMOVE',
        )
        row.operator(
            "vector_comp.refresh_user_presets",
            text="", icon='FILE_REFRESH',
        )

        # Ligne d'I/O : Exporter / Importer la bibliothèque utilisateur
        row = box.row(align=True)
        row.operator(
            "vector_comp.export_user_presets",
            text="Exporter", icon='EXPORT',
        )
        row.operator(
            "vector_comp.import_user_presets",
            text="Importer", icon='IMPORT',
        )

        # ── Sous-bloc Foucault (conditionnel) ──────────────────────────
        # Apparaît uniquement si un preset Foucault est sélectionné, ou
        # plus largement quand l'utilisateur veut tester d'autres
        # latitudes : on affiche aussi le bloc si aucune expression n'a
        # encore été modifiée (juste après application d'un preset).
        if props.preset_choice.startswith("FOUCAULT"):
            sub = box.box()
            sub.label(text="Latitude pour le pendule de Foucault",
                      icon='WORLD')
            sub.prop(props, "latitude_deg")
            sub.operator(
                "vector_comp.apply_foucault",
                text="Recalculer pour cette latitude",
                icon='FILE_REFRESH',
            )
            sub.label(
                text="Période de précession : 2π / sin(φ) (s simulées)",
                icon='INFO',
            )

        # ── Translation O'(t) ──────────────────────────────────────────
        box = layout.box()
        box.label(text="Translation O'(t) dans R", icon='ORIENTATION_GLOBAL')
        col = box.column(align=True)
        col.prop(props, "X0_expr")
        col.prop(props, "Y0_expr")
        col.prop(props, "Z0_expr")

        # ── Rotation R'/R (Euler ZYX intrinsèque) ──────────────────────
        box = layout.box()
        box.label(text="Rotation R'/R — Euler Z-Y-X intrinsèque",
                  icon='DRIVER_ROTATIONAL_DIFFERENCE')
        col = box.column(align=True)
        col.prop(props, "psi_expr")
        col.prop(props, "theta_expr")
        col.prop(props, "phi_expr")
        box.label(
            text="« rotation autour de z » : ψ seul, θ=φ=0",
            icon='INFO',
        )

        # ── Position M dans R' ─────────────────────────────────────────
        box = layout.box()
        box.label(text="Mouvement de M dans R'", icon='IPO_SINE')
        col = box.column(align=True)
        col.prop(props, "xp_expr")
        col.prop(props, "yp_expr")
        col.prop(props, "zp_expr")

        # ── Animation ──────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Animation", icon='TIME')
        col = box.column(align=True)
        col.prop(props, "fps")
        col.prop(props, "t_start")
        col.prop(props, "t_duration")

        # ── Échelles ───────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Échelles", icon='ARROW_LEFTRIGHT')
        col = box.column(align=True)
        col.prop(props, "scale_v")
        col.prop(props, "scale_a")
        col.prop(props, "scale_omega")

        # ── Visibilité des flèches ─────────────────────────────────────
        box = layout.box()
        box.label(text="Affichage des flèches", icon='HIDE_OFF')

        sub = box.column(align=True)
        sub.label(text="Position : OM = OO' + O'M")
        sub.prop(props, "show_OOp")
        sub.prop(props, "show_OpM")
        sub.prop(props, "show_OM")

        sub.separator()
        sub.label(text="Composition des vitesses : v_a = v_r + v_e")
        sub.prop(props, "show_vr")
        sub.prop(props, "show_ve")
        sub.prop(props, "show_va")

        sub.separator()
        sub.label(text="Composition des accélérations : a_a = a_r + a_e + a_c")
        sub.prop(props, "show_ar")
        sub.prop(props, "show_ae")
        sub.prop(props, "show_ac")
        sub.prop(props, "show_aa")

        sub.separator()
        sub.label(text="Rotation instantanée (axe de R'/R) :")
        sub.prop(props, "show_Omega")

        # ── Trièdres directs ───────────────────────────────────────────
        box = layout.box()
        box.label(text="Trièdres directs", icon='EMPTY_AXIS')
        col = box.column(align=True)
        col.prop(props, "show_R_frame")
        col.prop(props, "show_Rp_frame")
        col.separator()
        col.prop(props, "axis_length")
        box.label(
            text="R : RGB pur • R' : RGB pastel",
            icon='INFO',
        )

        # ── Trajectoires ───────────────────────────────────────────────
        box = layout.box()
        box.label(text="Trajectoires (chemins parcourus)", icon='IPO_BEZIER')
        col = box.column(align=True)
        col.prop(props, "show_traj_OOp")
        col.prop(props, "show_traj_OM")
        col.prop(props, "show_traj_OpM")
        col.separator()
        col.prop(props, "traj_radius")
        box.label(
            text="Échantillonnées au build sur [t_start, t_start+T]",
            icon='INFO',
        )

        # ── Hôte ───────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Objet hôte", icon='OBJECT_DATA')
        box.prop(props, "host_name")

        # ── Actions ────────────────────────────────────────────────────
        layout.separator()
        col = layout.column(align=True)
        col.scale_y = 1.3
        col.operator("vector_comp.build", icon='PLAY')
        col.operator("vector_comp.clear", icon='TRASH')
