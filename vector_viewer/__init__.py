"""Vector Viewer — extension Blender pour la visualisation animée
de vecteurs cinématiques.

Deux panneaux dans la N-zone de la 3D View, onglet « Vector Viewer » :

1. Vector Viewer (simple)
   Saisie de x(t), y(t), z(t) → trois flèches chaînées r/v/a depuis
   l'origine.

2. Composition (référentiels non galiléens)
   Saisie de la translation O'(t), des angles d'Euler (ψ, θ, φ) du
   repère mobile R'/R, et de la position r'(t) de M dans R'. Produit
   les 10 flèches de la décomposition :
       OO', O'M, v_r, v_e, v_a, a_r, a_e, a_c (Coriolis), a_a, Ω.
   Avec switches d'affichage indépendants pour chacune.

Auto-Run Python Scripts doit être activé (Edit ▸ Preferences ▸ Save &
Load) pour que les drivers Python fonctionnent.
"""

import bpy
from bpy.app.handlers import persistent

from . import (
    properties, operators, ui, drivers as drv_mod,
    presets as _presets,
    composition as cmp_mod,
    composition_properties, composition_operators, composition_panel,
    composition_presets as _cmp_presets,
    materials_presets as _mat_presets,
    materials_panel,
)


classes = (
    # Vector Viewer simple
    properties.VectorViewerProperties,
    operators.VECTORVIEWER_OT_build,
    operators.VECTORVIEWER_OT_clear,
    _presets.VECTORVIEWER_OT_apply_preset,
    _presets.VECTORVIEWER_OT_save_user_preset,
    _presets.VECTORVIEWER_OT_update_user_preset,
    _presets.VECTORVIEWER_OT_delete_user_preset,
    _presets.VECTORVIEWER_OT_refresh_user_presets,
    _presets.VECTORVIEWER_OT_export_user_presets,
    _presets.VECTORVIEWER_OT_import_user_presets,
    ui.VECTORVIEWER_PT_panel,
    # Composition
    composition_properties.VectorCompositionProperties,
    composition_operators.VECTORCOMP_OT_build,
    composition_operators.VECTORCOMP_OT_clear,
    _cmp_presets.VECTORCOMP_OT_apply_preset,
    _cmp_presets.VECTORCOMP_OT_apply_foucault,
    _cmp_presets.VECTORCOMP_OT_save_user_preset,
    _cmp_presets.VECTORCOMP_OT_update_user_preset,
    _cmp_presets.VECTORCOMP_OT_delete_user_preset,
    _cmp_presets.VECTORCOMP_OT_refresh_user_presets,
    _cmp_presets.VECTORCOMP_OT_export_user_presets,
    _cmp_presets.VECTORCOMP_OT_import_user_presets,
    composition_panel.VECTORCOMP_PT_panel,
    # Matériaux (palettes)
    _mat_presets.VectorViewerMaterialsProperties,
    _mat_presets.VECTORVIEWER_OT_apply_materials_preset,
    _mat_presets.VECTORVIEWER_OT_save_materials_preset,
    _mat_presets.VECTORVIEWER_OT_update_materials_preset,
    _mat_presets.VECTORVIEWER_OT_delete_materials_preset,
    _mat_presets.VECTORVIEWER_OT_refresh_materials_presets,
    _mat_presets.VECTORVIEWER_OT_reset_materials,
    _mat_presets.VECTORVIEWER_OT_export_materials_presets,
    _mat_presets.VECTORVIEWER_OT_import_materials_presets,
    materials_panel.VECTORVIEWER_MAT_PT_panel,
)


# ----------------------------------------------------------------------------
# Persistent load handler
# ----------------------------------------------------------------------------
# bpy.app.driver_namespace est volatile : il est vidé à chaque ouverture
# de .blend. Ce handler relit les expressions stockées sur les Scene et
# réinjecte les fonctions {r,v,a}_num + cmp_* pour que les drivers se
# réévaluent.
# ----------------------------------------------------------------------------

@persistent
def _on_load(_dummy):
    """Réinjecte les fonctions {r,v,a}_num et cmp_* dans le
    driver_namespace pour CHAQUE scène, scopées par leur slug. C'est
    crucial : ``bpy.app.driver_namespace`` est globalement vidé à
    l'ouverture du .blend, et plusieurs scènes peuvent coexister avec
    leurs propres viewers."""
    for scene in bpy.data.scenes:
        # Vector Viewer simple
        sprops = getattr(scene, "vector_viewer", None)
        if sprops is not None:
            try:
                drv_mod.refresh_driver_namespace(sprops, scene=scene)
            except Exception as e:
                print(f"[VectorViewer] Réinjection des drivers échouée "
                      f"pour la scène {scene.name!r} : {e}")

        # Composition
        cprops = getattr(scene, "vector_comp", None)
        if cprops is not None:
            try:
                cmp_mod.refresh_driver_namespace(cprops, scene=scene)
            except Exception as e:
                print(f"[VectorComp] Réinjection des drivers échouée "
                      f"pour la scène {scene.name!r} : {e}")


# ----------------------------------------------------------------------------
# Register / unregister
# ----------------------------------------------------------------------------

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.vector_viewer = bpy.props.PointerProperty(
        type=properties.VectorViewerProperties
    )
    bpy.types.Scene.vector_comp = bpy.props.PointerProperty(
        type=composition_properties.VectorCompositionProperties
    )
    bpy.types.Scene.vector_viewer_materials = bpy.props.PointerProperty(
        type=_mat_presets.VectorViewerMaterialsProperties
    )
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister():
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    if hasattr(bpy.types.Scene, "vector_viewer_materials"):
        del bpy.types.Scene.vector_viewer_materials
    if hasattr(bpy.types.Scene, "vector_comp"):
        del bpy.types.Scene.vector_comp
    if hasattr(bpy.types.Scene, "vector_viewer"):
        del bpy.types.Scene.vector_viewer
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
