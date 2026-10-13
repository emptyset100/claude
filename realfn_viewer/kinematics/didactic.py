"""Aides pédagogiques communes aux panneaux de cinématique."""

import textwrap


def draw_tip(layout, store, pid, *, width=46):
    """Affiche sous le menu des presets la note « À observer » du preset
    sélectionné (champ ``tip``), découpée en lignes : les labels Blender
    ne passent pas à la ligne d'eux-mêmes."""
    preset = store.get(pid) if pid else None
    tip = (preset or {}).get("tip", "").strip()
    if not tip:
        return
    col = layout.column(align=True)
    col.scale_y = 0.8
    for i, line in enumerate(textwrap.wrap(tip, width)):
        col.label(text=line, icon='INFO' if i == 0 else 'BLANK1')
