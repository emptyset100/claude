"""
Side panel in the 3D View — entry point for creating and editing real
function curves.
"""

from __future__ import annotations

import bpy

from . import i18n

from . import (bench_tree, builtin_presets, memorize, modifier_inputs,
               operators, presets, tree)


# UI label translations
# ---------------------
# Socket names inside the node trees stay in English (so preset JSON
# files, helpers like ``presets.snapshot_modifier``, and possible
# external tooling all keep matching by stable identifiers). The
# *display* labels in our French panel are looked up here instead —
# the underlying ``item.name`` is the canonical English string, while
# what the user reads in the N-panel is the French translation.
#
# Helper sockets we don't know about (free parameters like ``a``,
# ``omega``, …) fall through unchanged. If at some point a socket
# name is renamed in ``tree.py`` or ``vector_tree.py``, just add a
# new entry here — no other code needs touching.
_SOCKET_LABELS_FR = {
    # Common to all kinds
    "Resolution": "Résolution",
    "Marker size": "Taille du marqueur",
    "Marker material": "Matériau du marqueur",
    # Scalar (x-axis sampling)
    "x min": "x min",
    "x max": "x max",
    "x_0": "x₀",
    "Curve thickness": "Épaisseur de la courbe",
    "Tangent thickness": "Épaisseur de la tangente",
    # Vector (t-axis sampling)
    "t min": "t min",
    "t max": "t max",
    "t_0": "t₀",
    "Trace thickness": "Épaisseur de la trajectoire",
    "Show position vector": "Afficher le vecteur position",
    "Show derivative vector": "Afficher le vecteur vitesse",
    "Show acceleration vector": "Afficher le vecteur accélération",
    # Surface (explicit z = f(x, y))
    "Resolution X": "Résolution en x",
    "Resolution Y": "Résolution en y",
    "y min": "y min",
    "y max": "y max",
    "y_0": "y₀",
    "Surface material": "Matériau de la surface",
    "Show tangent plane": "Afficher le plan tangent",
    "Tangent plane size": "Taille du plan tangent",
    "Tangent plane resolution": "Résolution du plan tangent",
    "Tangent plane material": "Matériau du plan tangent",
    "Show Taylor surface": "Afficher la surface de Taylor",
    "Taylor order": "Ordre de Taylor",
    "Taylor surface size": "Taille de la surface de Taylor",
    "Taylor surface resolution": "Résolution de la surface de Taylor",
    "Taylor surface material": "Matériau de la surface de Taylor",
    # Parametric surface (u, v)
    "Resolution U": "Résolution en u",
    "Resolution V": "Résolution en v",
    "u min": "u min",
    "u max": "u max",
    "v min": "v min",
    "v max": "v max",
    "u_0": "u₀",
    "v_0": "v₀",
    # 3D scalar field (Nx, Ny, Nz grid + basepoint + labels)
    "Resolution Z": "Résolution en z",
    "z min": "z min",
    "z max": "z max",
    "z_0": "z₀",
    "Label size": "Taille des étiquettes",
    "Label offset": "Décalage des étiquettes",
    "Label material": "Matériau des étiquettes",
    "Show basepoint": "Afficher le point d'ancrage",
    "Show value labels": "Afficher les étiquettes numériques",
    "Label stride": "Pas d'affichage des étiquettes",
    "Show norm labels": "Afficher les normes ‖V‖",
    "Norm label stride": "Pas d'affichage des normes",
    "Norm label size": "Taille des étiquettes de norme",
    "Norm label offset": "Décalage des étiquettes de norme",
    "Norm label material": "Matériau des étiquettes de norme",
    "Label decimals": "Décimales des étiquettes",
    "Label vertical": "Étiquettes verticales (face à la vue)",
    "Norm label decimals": "Décimales des étiquettes de norme",
    "Norm label vertical": "Étiquettes de norme verticales",
    "Label max points": "Seuil de points (étiquettes)",
    "Norm label max points": "Seuil de points (normes)",
    "Show domain frame": "Afficher le cadre du domaine",
    "Frame thickness": "Épaisseur du cadre",
    "Frame material": "Matériau du cadre",
    "Show graduated axes": "Afficher les axes gradués",
    "Axis label size": "Taille des graduations",
    "Axis label decimals": "Décimales des graduations",
    "Axis label material": "Matériau des graduations",
    "Basepoint marker size": "Taille du marqueur d'ancrage",
    "Basepoint marker material": "Matériau du marqueur d'ancrage",
    "Basepoint label size": "Taille de l'étiquette d'ancrage",
    "Basepoint label material": "Matériau de l'étiquette d'ancrage",
    # 3D vector field V: R³ → R³ — see vector_field_3d_tree.py for the
    # full list of sockets exposed on this kind of modifier.
    "Arrow scale": "Échelle des flèches",
    "Show arrows": "Afficher la grille de flèches",
    "Arrow material": "Matériau des flèches",
    "Basepoint arrow material": "Matériau de la flèche d'ancrage",
    "Show component arrows": "Afficher les composantes au point d'ancrage",
    "Component arrow material": "Matériau des flèches composantes",
    "Show basepoint norm label": "Afficher la norme ‖V‖ au point d'ancrage",
    "Label vertical offset": "Décalage vertical de l'étiquette",
}


def _socket_label(name: str) -> str:
    """Display label for a modifier socket, in the active language.

    Falls back to ``name`` itself when no translation is registered —
    the right behaviour for free-parameter sockets (``a``, ``omega``…)
    and any socket added later. Per-piece sockets (``Thickness · f``,
    ``Visible · T_2``…) get their *prefix* translated in French mode;
    the piece label is mathematical notation and is never localised.
    Socket names are English by convention, so English mode shows
    them raw (with a tiny map for legacy French-named sockets)."""
    if i18n.get_lang() == "EN":
        return _SOCKET_LABELS_EN.get(name, name)
    if name in _SOCKET_LABELS_FR:
        return _SOCKET_LABELS_FR[name]
    if name.startswith("Thickness · "):
        return "Épaisseur · " + name[len("Thickness · "):]
    if name.startswith("Material · "):
        return "Matériau · " + name[len("Material · "):]
    if name.startswith("Visible · "):
        return name
    return name


_SOCKET_LABELS_EN = {
    # Sockets whose internal names are (legacy) French — everything
    # else is English by convention and shows raw in English mode.
    "Material · vitesse": "Material · velocity",
    "Material · accélération": "Material · acceleration",
}


# --------------------------------------------------------------------------- #
# Socket tooltips (descriptions) — bilingual, follow the language toggle
# --------------------------------------------------------------------------- #
# Socket *descriptions* are baked onto each node tree when it is built, in
# whatever language the source strings happened to be written (historically
# a FR/EN mix). :func:`localize_socket_tooltips` rewrites them in the active
# language so the hover tooltips match the rest of the UI. Rich entries are
# listed here; any socket without one falls back to its localised short
# label, guaranteeing total, consistent coverage.
#
# Each value is a ``(FR, EN)`` pair.
_SOCKET_TOOLTIPS = {
    "Resolution": (
        "Nombre d'échantillons le long de chaque courbe tracée. "
        "Plus élevé = plus lisse mais plus lourd",
        "Number of samples along each traced curve. "
        "Higher = smoother but heavier"),
    "x_0": (
        "Point de base x₀. Pilote la position de la sphère marqueur et "
        "(si des polynômes de Taylor sont tracés) le centre du "
        "développement. Scrubbez pour tout faire glisser en direct",
        "Basepoint x₀. Drives the marker sphere position and (if any "
        "Taylor polynomials are traced) the centre of expansion. "
        "Scrub to slide everything live"),
    "t_0": (
        "Point de base t₀ le long de la trajectoire. Scrubbez pour "
        "faire glisser les vecteurs cinématiques le long de la courbe",
        "Basepoint t₀ along the trajectory. Scrub to slide the "
        "kinematic vectors along the curve"),
    "Marker size": (
        "Rayon de la sphère marqueur au point de base",
        "Radius of the marker sphere at the basepoint"),
    "Marker material": (
        "Matériau de la sphère marqueur. Laisser vide pour le "
        "matériau par défaut",
        "Material of the marker sphere. Leave empty for the default "
        "material"),
    "Show tangent plane": (
        "Afficher le plan tangent affine au point d'ancrage (x₀, y₀)",
        "Show the affine tangent plane at the basepoint (x₀, y₀)"),
    "Show Taylor surface": (
        "Afficher la surface de Taylor osculatrice au point d'ancrage. "
        "L'analogue 2D des polynômes de Taylor d'une courbe",
        "Show the osculating Taylor surface at the basepoint. The 2D "
        "analogue of a curve's Taylor polynomials"),
    "Taylor order": (
        "Ordre du développement de Taylor en (x₀, y₀) : 0 = plan "
        "horizontal, 1 = plan tangent, 2 = paraboloïde osculateur, "
        "ordres supérieurs = approximation plus serrée. Scrubbez pour "
        "voir la surface épouser f en direct",
        "Order of the Taylor expansion at (x₀, y₀): 0 = horizontal "
        "plane, 1 = tangent plane, 2 = osculating paraboloid, higher "
        "orders = tighter fit. Scrub to watch the surface hug f live"),
    "Show arrows": (
        "Afficher la grille de flèches du champ de vecteurs",
        "Show the vector-field arrow grid"),
    "Show value labels": (
        "Afficher les étiquettes numériques de la valeur du champ "
        "à chaque point échantillonné",
        "Show numeric labels of the field value at each sampled point"),
    "Label stride": (
        "N'afficher qu'un point sur N pour les étiquettes — réduit la "
        "charge de rendu du texte",
        "Only label every Nth point — reduces text-rendering cost"),
}

# Templated tooltips for per-piece sockets (``Thickness · f``,
# ``Material · T_2``, ``Visible · f'``…): the prefix is localised, the
# piece label (mathematical notation) is substituted verbatim.
_SOCKET_TOOLTIP_PREFIXES = [
    ("Thickness · ", (
        "Rayon du tube de {piece}. Mettre à 0 pour un masquage léger "
        "(la géométrie reste calculée)",
        "Tube radius for {piece}. Set to 0 for a cheap soft-hide "
        "(geometry is still computed)")),
    ("Material · ", (
        "Matériau appliqué au tube de {piece}. Laisser vide pour le "
        "matériau par défaut",
        "Material applied to the {piece} tube. Leave empty for the "
        "default material")),
    ("Visible · ", (
        "Afficher ou masquer la courbe {piece} (la décocher retire la "
        "géométrie de la sortie)",
        "Show or hide the {piece} curve (unchecking removes the "
        "geometry from the output)")),
]


def _socket_tooltip(name: str) -> str:
    """Localised tooltip for a modifier socket, in the active language.

    Rich text from :data:`_SOCKET_TOOLTIPS` / the per-piece templates
    when available; otherwise the localised short label so every socket
    gets a coherent, language-appropriate tooltip."""
    en = i18n.get_lang() == "EN"
    entry = _SOCKET_TOOLTIPS.get(name)
    if entry is not None:
        return entry[1] if en else entry[0]
    for prefix, tip in _SOCKET_TOOLTIP_PREFIXES:
        if name.startswith(prefix):
            piece = name[len(prefix):]
            return (tip[1] if en else tip[0]).format(piece=piece)
    # Fallback: reuse the localised short label as a minimal tooltip.
    return _socket_label(name)


def localize_socket_tooltips(node_group) -> None:
    """Rewrite every input socket's tooltip in the active language.

    Called at object creation and after a language toggle. Idempotent —
    safe to run repeatedly. Stamps the applied language on the node group
    so callers can cheaply tell whether a refresh is needed."""
    if node_group is None:
        return
    try:
        items = node_group.interface.items_tree
    except AttributeError:
        return
    for it in items:
        if getattr(it, "item_type", "") != "SOCKET" or it.in_out != "INPUT":
            continue
        tip = _socket_tooltip(it.name)
        if tip:
            it.description = tip
    node_group["realfn_tooltip_lang"] = i18n.get_lang()


# Visible characters per panel line for formula display. Blender's
# N-panel is narrow (about 220–260px in typical setups), so a label
# starts wrapping or getting truncated around 50–60 characters. We
# split a long formula onto multiple lines at sensible boundaries
# (operators) up to a small line budget, and truncate the tail with
# an ellipsis if it overflows.
_FORMULA_LINE_CHARS = 50
_FORMULA_MAX_LINES = 3


def _wrap_formula(text: str, max_lines: int | None = _FORMULA_MAX_LINES) -> list[str]:
    """Split a long SymPy-rendered expression onto up to
    ``max_lines`` panel lines (``None`` = no cap, return every line —
    used by the "full polynomial" popup).

    Strategy: pre-tokenise the string at top-level ``" + "`` / ``" - "``
    boundaries (each token starts with its leading sign so it reads
    naturally on a fresh line), then greedily glue tokens together
    until adding the next one would exceed the per-line budget.

    "Top-level" matters here because Taylor polynomials contain
    sub-expressions like ``(x - x_0)`` whose internal ``-`` must not be
    treated as a term boundary — otherwise we'd split right through a
    factor. The split logic counts parentheses depth and only honours
    boundaries at depth 0.
    """
    text = text.strip()
    if len(text) <= _FORMULA_LINE_CHARS:
        return [text]

    # --- Step 1: split into top-level additive tokens. ---------------
    # Each token keeps the sign that connects it to the previous one
    # (or no sign for the first token), so concatenation reconstructs
    # the original string.
    tokens: list[str] = []
    depth = 0
    last_split = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and ch == " " and i + 2 < len(text):
            # Look for " + " or " - " — the surrounding spaces tell us
            # this is an additive operator, not part of an exponent
            # (** has no spaces) or a unary minus right after another
            # operator (those don't have a space *before* them either).
            op = text[i:i+3]
            if op == " + " or op == " - ":
                tokens.append(text[last_split:i])
                last_split = i + 1  # keep "+ ..." or "- ..." in next token
                i += 3
                continue
        i += 1
    tokens.append(text[last_split:])

    # --- Step 2: greedy line packing. --------------------------------
    lines: list[str] = []
    current = ""
    for tok in tokens:
        if not current:
            current = tok
            continue
        # +1 for the space that separates the previous token from this
        # one (since each token after the first starts with "+ " or
        # "- ", we just need a single space between them).
        candidate = f"{current} {tok}"
        if len(candidate) <= _FORMULA_LINE_CHARS:
            current = candidate
        else:
            lines.append(current)
            current = tok
    if current:
        lines.append(current)

    # --- Step 3: enforce max-line budget with ellipsis. --------------
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip() + " …"
    return lines


def _draw_formula_under_checkbox(layout, piece_label: str,
                                  formula: str) -> None:
    """Render a formula on one or more indented lines beneath a checkbox.

    The first line is followed by a small "copy to clipboard" button
    so the user can grab the formula in one click — useful when the
    LaTeX display mode is active and the user wants to paste into a
    document.

    Indentation is achieved by nesting a ``split`` so the formula
    sits visually under the checkbox text rather than starting from
    the left margin — that's the convention Blender's own UI uses
    for hint text under property rows.
    """
    lines = _wrap_formula(formula)
    for i, line in enumerate(lines):
        split = layout.split(factor=0.05)
        split.label(text="")
        if i == 0 and piece_label:
            # First line carries the Copy button on the far right,
            # leaving the rest of the row for the formula text. Using
            # a row with align=True compresses the spacing.
            row = split.row(align=True)
            row.label(text=line)
            op = row.operator(
                "realfn.copy_formula", text="", icon="COPYDOWN",
                emboss=False,
            )
            op.piece_label = piece_label
        else:
            split.label(text=line)


def _socket_value(mod, nt, name):
    """Read the live value of a named modifier input socket, or None.

    Used by the read-only formula displays that depend on a runtime
    socket (e.g. the Taylor-surface order): the modifier stores socket
    values under the socket *identifier*, which we resolve from the
    interface by display name."""
    for it in nt.interface.items_tree:
        if getattr(it, "in_out", None) == "INPUT" and it.name == name:
            return modifier_inputs.get_value(mod, it.identifier)
    return None


def _draw_taylor_poly(layout, mod, nt, use_latex, axes):
    """Draw the current-order Taylor polynomial(s) when the Taylor
    surface is enabled.

    ``axes`` selects the source stash and the rendered notation:
      * ``[("", "x, y")]`` for explicit surfaces — one polynomial
        ``realfn_taylor_poly_{text,latex}`` in (x, y);
      * ``[("x", "u, v"), ("y", …), ("z", …)]`` for parametric
        surfaces — three component polynomials
        ``realfn_taylor_poly_{axis}_{text,latex}``.

    The order is read live from the modifier so the displayed polynomial
    follows the order slider with no recompute (the strings were baked at
    build time, one per order)."""
    if not _socket_value(mod, nt, "Show Taylor surface"):
        return
    order = _socket_value(mod, nt, "Taylor order")
    if order is None:
        return
    suffix = "latex" if use_latex else "text"
    box = layout.box()
    # Header carries a copy button that grabs the full current-order
    # polynomial (all components for parametric surfaces) — the panel
    # itself truncates long polynomials to a few lines, so this is how
    # the user gets the complete expression onto the clipboard.
    header = box.row(align=True)
    header.label(
        text=i18n.tr("Polynôme de Taylor, ordre") + f" {int(order)} :",
        icon="RNDCURVE",
    )
    header.operator("realfn.show_taylor_poly", text="", icon="VIEWZOOM",
                    emboss=False)
    header.operator("realfn.copy_taylor_poly", text="", icon="COPYDOWN",
                    emboss=False)
    for axis_key, vars_label in axes:
        stash = (axis_key and f"realfn_taylor_poly_{axis_key}_") or \
                "realfn_taylor_poly_"
        polys = nt.get(stash + suffix) or nt.get(stash + "text")
        if not polys:
            continue
        try:
            polys = list(polys)
        except TypeError:
            continue
        n = max(0, min(int(order), len(polys) - 1))
        lhs = (f"T_{axis_key}" if axis_key else "T") + f"({vars_label})"
        _draw_formula_under_checkbox(box, "", f"{lhs} = {polys[n]}")


# Per-kind header icon for the "Fonction active" box — visually ties
# the active-object info back to the create button that produced it.
_KIND_HEADER_ICON = {
    "scalar": "FCURVE",
    "vector": "EMPTY_ARROWS",
    "surface": "SURFACE_NSURFACE",
    "parametric_surface": "SURFACE_DATA",
    "scalar_field_3d": "LIGHTPROBE_VOLUME",
    "vector_field_3d": "MOD_FLUIDSIM",
    "vector_bench": "EMPTY_ARROWS",
}

# Creation entry points, organised into three collapsible sections.
# Each entry: (panel_id, FR title, header icon, default_closed,
# [(operator, button icon, FR button text), …]). Courbes is the most
# common starting point so it opens by default; the other two stay
# collapsed to keep the empty-scene panel compact while remaining
# discoverable via their headers.
_CREATE_GROUPS = (
    ("realfn_new_curves", "Courbes", "FCURVE", False, (
        # Scalar y = f(x): the canonical case (curve + animated tangent).
        ("realfn.create", "GRAPH", "Créer une courbe…"),
        # Vector F(t): different input syntax (sympy.physics.vector) and
        # geometry (3D trace + kinematic arrows) than the scalar case.
        ("realfn.create_vector", "EMPTY_ARROWS",
         "Créer une courbe vectorielle F(t)…"),
    )),
    ("realfn_new_bench", "Banc de vecteurs", "EMPTY_ARROWS", True, (
        # Vector bench: several named arrows (vec/cross/rotate…) from the
        # origin, driven by live parameter sliders — for exploring vector
        # algebra and rotations.
        ("realfn.create_vector_bench", "EMPTY_ARROWS",
         "Créer un banc de vecteurs…"),
    )),
    ("realfn_new_surfaces", "Surfaces", "SURFACE_NSURFACE", True, (
        # Explicit z = f(x, y): one scalar expression.
        ("realfn.create_surface", "SURFACE_NSURFACE",
         "Créer une surface z = f(x, y)…"),
        # Parametric (x, y, z)(u, v): three expressions, for closed /
        # folded surfaces. Different dialog and node tree than explicit.
        ("realfn.create_parametric_surface", "SURFACE_DATA",
         "Créer une surface paramétrée…"),
    )),
    ("realfn_new_fields", "Champs 3D", "MOD_FLUIDSIM", True, (
        # 3D scalar field: the graph view breaks down (would need 4D),
        # so the field is shown via in-scene numeric labels per sample.
        ("realfn.create_scalar_field_3d", "LIGHTPROBE_VOLUME",
         "Créer un champ scalaire ƒ(x, y, z)…"),
        # 3D vector field V: R³ → R³, shown as a grid of arrows. Two
        # specification modes (explicit components vs gradient of a
        # potential) offered in the create dialog.
        ("realfn.create_vector_field_3d", "MOD_FLUIDSIM",
         "Créer un champ de vecteurs V(x, y, z)…"),
    )),
)


def _draw_auto_row(box, props, rebuild_op):
    """Auto-update toggle + (greyed-when-auto) manual rebuild button,
    shared by the bench editor and the generic formula editor."""
    rr = box.row(align=True)
    rr.prop(props, "auto_update", toggle=True, icon="FILE_REFRESH")
    sub = rr.row(align=True)
    sub.enabled = not props.auto_update
    sub.operator(rebuild_op, text=i18n.tr("Reconstruire"), icon="PLAY")


class REALFN_PT_main(bpy.types.Panel):
    bl_label = "RealFn Viewer"
    bl_idname = "REALFN_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RealFn"

    def _draw_create_groups(self, layout):
        """Draw the three collapsible 'Créer…' sections.

        Uses ``layout.panel()`` (Blender ≥ 4.1) so each group folds
        away and remembers its state; on older builds it degrades to a
        labelled box with everything visible — no entry point is ever
        lost. Mirrors the fallback logic in :func:`_draw_sectioned_params`.
        """
        for sid, title, icon, closed, buttons in _CREATE_GROUPS:
            body = None
            used_panel = False
            if hasattr(layout, "panel"):
                try:
                    header, body = layout.panel(sid, default_closed=closed)
                    header.label(text=i18n.tr(title), icon=icon)
                    used_panel = True
                except (TypeError, RuntimeError):
                    used_panel = False
            if not used_panel:
                box = layout.box()
                box.label(text=i18n.tr(title), icon=icon)
                body = box
            if body is None:
                continue  # collapsed panel: header only
            col = body.column(align=True)
            for op_id, op_icon, op_text in buttons:
                col.operator(op_id, icon=op_icon, text=i18n.tr(op_text))
            # The vector-bench section also offers one-click ready-made
            # benches (rotation, cross product, slerp…) below its custom
            # create button.
            if sid == "realfn_new_bench":
                col.separator()
                col.label(text=i18n.tr("Bancs prêts à l'emploi :"),
                          icon="PRESET")
                pcol = body.column(align=True)
                for preset in bench_tree.BUILTIN_BENCHES:
                    label = preset["label"]
                    if i18n.get_lang() == "EN":
                        label = preset.get("label_en", label)
                    op = pcol.operator("realfn.apply_bench_preset",
                                       text=label, icon="EMPTY_ARROWS")
                    op.preset_id = preset["id"]

    def _draw_formula_readonly(self, box, kind, nt):
        """Read-only formula display for legacy objects that predate the
        editable ``realfn_edit`` property group."""
        col = box.column(align=True)
        if kind == "vector":
            col.label(text=f"F(t) = {nt.get('realfn_expr', '?')}")
        elif kind == "surface":
            col.label(text=f"z = {nt.get('realfn_expr', '?')}")
        elif kind == "scalar_field_3d":
            col.label(text=f"f(x, y, z) = {nt.get('realfn_expr', '?')}")
        elif kind == "parametric_surface":
            cl = list(nt.get("realfn_components_text") or [])
            if len(cl) == 3:
                col.label(text=f"x(u,v) = {cl[0]}")
                col.label(text=f"y(u,v) = {cl[1]}")
                col.label(text=f"z(u,v) = {cl[2]}")
        elif kind == "vector_field_3d":
            if str(nt.get("realfn_mode", "explicit")) == "from_potential":
                col.label(text=f"ϕ = {nt.get('realfn_potential', '?')}")
            else:
                cl = list(nt.get("realfn_components_text") or [])
                if len(cl) == 3:
                    col.label(text=f"Vx = {cl[0]}")
                    col.label(text=f"Vy = {cl[1]}")
                    col.label(text=f"Vz = {cl[2]}")
        else:
            col.label(text=f"y = {nt.get('realfn_expr', '?')}")
        params = nt.get("realfn_params", [])
        if params:
            col.label(text=i18n.tr("Paramètres : ")
                      + ", ".join(str(p) for p in params))

    def draw(self, context):
        layout = self.layout
        # Self-healing i18n: if the language baked into the class
        # labels differs from the preference (lost timer, add-on
        # reload, .blend load…), reschedule the relabel pass. The
        # console then shows the "[RealFn] i18n:" summary line.
        if i18n.get_lang() != i18n._APPLIED_LANG:
            i18n.schedule_apply_language()

        # ── 1. Language toggle ───────────────────────────────────────
        lang_row = layout.row(align=True)
        lang_row.operator(
            "realfn.toggle_language",
            text="🌐 English" if i18n.get_lang() == "FR" else "🌐 Français",
            emboss=True,
        )

        # ── 2. Fonction active + Affichage & animation ───────────────
        # Shown immediately under the language toggle so the user sees
        # the current function and its controls at a glance, without
        # having to scroll past the creation buttons.
        mod = operators._active_realfn_modifier(context)
        if mod is not None:
            nt = mod.node_group
            kind = nt.get("realfn_kind", "scalar")
            box = layout.box()
            box.label(text=i18n.tr("Fonction active :"),
                      icon=_KIND_HEADER_ICON.get(kind, "INFO"))
            # ── Editable formula fields (live, auto-update) ──────────
            # The vector bench has a row-based editor; the six classic
            # kinds share the generic one (Object.realfn_edit). A
            # legacy object without the property group falls back to
            # read-only labels.
            if kind == "vector_bench":
                bp = getattr(context.active_object, "realfn_bench", None)
                if bp is None:
                    col = box.column(align=True)
                    names = list(nt.get("realfn_bench_names") or [])
                    texts = list(nt.get("realfn_bench_text") or [])
                    for nm, tx in zip(names, texts):
                        col.label(text=f"{nm} = ({tx})")
                else:
                    ec = box.column(align=True)
                    for i in range(1, 7):
                        s = ec.split(factor=0.30, align=True)
                        s.prop(bp, f"name{i}", text="")
                        s.prop(bp, f"expr{i}", text="")
                    box.prop(bp, "params")
                    _draw_auto_row(box, bp, "realfn.bench_rebuild")
                    if bp.error:
                        box.label(text=bp.error, icon="ERROR")
                box.label(
                    text=i18n.tr("Sliders & affichage : panneau Modificateur"),
                    icon="MODIFIER")
            else:
                ep = getattr(context.active_object, "realfn_edit", None)
                if ep is None:
                    self._draw_formula_readonly(box, kind, nt)
                else:
                    col = box.column(align=True)
                    if kind == "parametric_surface":
                        col.prop(ep, "comp_x", text="x(u,v) =")
                        col.prop(ep, "comp_y", text="y(u,v) =")
                        col.prop(ep, "comp_z", text="z(u,v) =")
                    elif kind == "vector_field_3d":
                        if str(nt.get("realfn_mode", "explicit")) == "from_potential":
                            col.prop(ep, "potential", text="ϕ =")
                        else:
                            col.prop(ep, "comp_x", text="Vx =")
                            col.prop(ep, "comp_y", text="Vy =")
                            col.prop(ep, "comp_z", text="Vz =")
                    else:
                        _label = {"vector": "F(t) =", "surface": "z =",
                                  "scalar_field_3d": "f ="}.get(kind, "y =")
                        col.prop(ep, "expr", text=_label)
                    box.prop(ep, "params")
                    _draw_auto_row(box, ep, "realfn.edit_rebuild")
                    if ep.error:
                        box.label(text=ep.error, icon="ERROR")

                # Derivative/Taylor orders + dialog editor (scalar only).
                if kind == "scalar":
                    d_order = nt.get("realfn_derivative_order")
                    t_order = nt.get("realfn_taylor_order")
                    bits = []
                    if d_order is not None:
                        bits.append(i18n.tr("dérivées :") + f" 0–{d_order}")
                    if t_order is not None and int(t_order) > 0:
                        bits.append(i18n.tr("Taylor :") + f" 1–{t_order}")
                    if bits:
                        box.label(text="  •  ".join(bits))
                    box.operator("realfn.edit", icon="GREASEPENCIL",
                                 text=i18n.tr("Modifier la formule / les ordres"))

            # Snapshot section.
            snapshot = memorize.get_stored_snapshot(mod)
            if snapshot is not None:
                sbox = layout.box()
                sbox.label(text=i18n.tr("Snapshot mémorisé :"),
                           icon="FILE_TICK")
                ts = memorize.get_snapshot_timestamp(mod)
                if ts:
                    pretty = ts.replace("T", " ")
                    if len(pretty) >= 16:
                        pretty = pretty[:16]
                    sbox.label(text=i18n.tr("Sauvegardé le : ") + str(pretty),
                               icon="BLANK1")
                sbox.operator("realfn.restore_snapshot", icon="LOOP_BACK",
                              text=i18n.tr("Restaurer le snapshot"))

            # Affichage & animation — collapsible, open by default.
            disp = None
            used_panel = False
            if hasattr(layout, "panel"):
                try:
                    dheader, disp = layout.panel("realfn_display_anim",
                                                 default_closed=False)
                    dheader.label(text=i18n.tr("Affichage & animation"),
                                  icon="OPTIONS")
                    used_panel = True
                except (TypeError, RuntimeError):
                    used_panel = False
            if not used_panel:
                disp = layout.box()
                disp.label(text=i18n.tr("Affichage & animation"),
                           icon="OPTIONS")
            if disp is not None:
                if kind == "scalar":
                    disp.label(text=i18n.tr("Affichage des courbes :"),
                               icon="HIDE_OFF")
                    row = disp.row(align=True)
                    row.operator("realfn.visible_all_on", icon="CHECKBOX_HLT",
                                 text=i18n.tr("Tout afficher"))
                    row.operator("realfn.visible_all_off",
                                 icon="CHECKBOX_DEHLT",
                                 text=i18n.tr("Tout cacher"))
                    row.operator("realfn.visible_invert",
                                 icon="ARROW_LEFTRIGHT",
                                 text=i18n.tr("Inverser"))
                anim_row = disp.row(align=True)
                anim_row.operator("realfn.animate_basepoint", icon="PLAY",
                                  text=i18n.tr("Animer le point de base"))
                anim_row.operator("realfn.clear_basepoint_animation",
                                  icon="TRASH", text="")
                disp.prop(context.window_manager, "realfn_display_latex",
                          text=i18n.tr("Format LaTeX"),
                          icon="SYNTAX_OFF")
                disp.prop(context.scene, "realfn_sync_x0",
                          text=i18n.tr("Synchroniser x₀"),
                          icon="UV_SYNC_SELECT")

            # ── Matériaux ─────────────────────────────────────────────
            # Expose les sockets matériau du modificateur actif.
            # Compatible avec n'importe quel matériau, y compris Extreme PBR.
            mat_sockets = [
                item for item in nt.interface.items_tree
                if (getattr(item, "in_out", None) == "INPUT"
                    and getattr(item, "item_type", None) == "SOCKET"
                    and getattr(item, "socket_type", None) == "NodeSocketMaterial")
            ]
            if mat_sockets:
                mdisp = None
                used_mpanel = False
                if hasattr(layout, "panel"):
                    try:
                        mhdr, mdisp = layout.panel("realfn_materials",
                                                    default_closed=True)
                        mhdr.label(text=i18n.tr("Matériaux"),
                                   icon="MATERIAL")
                        used_mpanel = True
                    except (TypeError, RuntimeError):
                        used_mpanel = False
                if not used_mpanel:
                    mdisp = layout.box()
                    mdisp.label(text=i18n.tr("Matériaux"), icon="MATERIAL")
                if mdisp is not None:
                    col = mdisp.column(align=True)
                    for item in mat_sockets:
                        modifier_inputs.draw_input(
                            col, mod, item.identifier,
                            text=item.name.replace("Material · ", ""))

            layout.separator()

        # ── 3. Boutons de création ───────────────────────────────────
        # Always visible so the user can create a new function even
        # when one is already active.
        self._draw_create_groups(layout)


class REALFN_PT_params(bpy.types.Panel):
    """Inline view of the modifier inputs so the user doesn't have to
    open the Properties editor every time they want to scrub x₀ or
    change the sampling resolution."""

    bl_label = "Paramètres du modifier"
    bl_idname = "REALFN_PT_params"
    bl_parent_id = "REALFN_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RealFn"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        # Scalar-only: vector functions have a separate sub-panel
        # (REALFN_PT_vector_params) with a different set of sockets.
        return operators._active_scalar_realfn_modifier(context) is not None

    def draw(self, context):
        layout = self.layout
        mod = operators._active_scalar_realfn_modifier(context)
        if mod is None:
            return
        nt = mod.node_group
        # Choose which formula list to display based on the WindowManager
        # toggle: plain SymPy text by default, LaTeX when requested.
        # If the stash is missing (old tree built before 1.4) the panel
        # just doesn't show formulas — sockets still draw normally.
        use_latex = getattr(context.window_manager,
                            "realfn_display_latex", False)
        labels = nt.get("realfn_piece_labels")
        formulas_key = ("realfn_piece_formulas_latex" if use_latex
                        else "realfn_piece_formulas")
        formulas = nt.get(formulas_key)
        # Fallback: if LaTeX list is missing on an older tree, fall
        # back to text so the panel still displays something useful.
        if use_latex and not formulas:
            formulas = nt.get("realfn_piece_formulas")
        formulas_by_visible_socket = {}
        if labels and formulas:
            try:
                labels = list(labels)
                formulas = list(formulas)
            except TypeError:
                labels, formulas = [], []
            for lab, formula in zip(labels, formulas):
                formulas_by_visible_socket[f"Visible · {lab}"] = (
                    lab, str(formula),
                )

        # Per-piece sockets are dynamic (f, f', f^(k), T_1…T_n at any
        # order) so the section contents are computed by pattern
        # instead of a fixed list: Taylor pieces are isolated from
        # the function/derivative pieces, everything else (free
        # formula parameters) lands in « Paramètres libres ».
        names = [it.name for it in nt.interface.items_tree
                 if getattr(it, "in_out", None) == "INPUT"]
        taylor_names = [n for n in names if "· T_" in n]
        piece_names = [n for n in names
                       if " · " in n and n not in taylor_names]

        def _formula_after(body, item):
            entry = formulas_by_visible_socket.get(item.name)
            if entry is not None:
                piece_label, formula = entry
                _draw_formula_under_checkbox(body, piece_label, formula)

        _draw_sectioned_params(layout, mod, nt, [
            ("c_dom", "Domaine & échantillonnage", "MESH_GRID",
             ["Resolution", "x min", "x max"], False),
            ("c_x0", "Point x₀ & marqueur", "EMPTY_AXIS",
             ["x_0", "Marker size", "Marker material"], False),
            ("c_pieces", "Courbe f et dérivées", "FCURVE",
             piece_names, True),
            ("c_taylor", "Polynômes de Taylor", "RNDCURVE",
             taylor_names, True),
        ], after_item=_formula_after)


class REALFN_PT_vector_params(bpy.types.Panel):
    """Inline view of the *vector* modifier inputs.

    Symmetric to :class:`REALFN_PT_params` but for vector functions:
    the sockets exposed by ``vector_tree.make_vectorfn_tree`` are
    different (no per-piece thickness or Visible toggles — instead,
    two checkboxes for the position and derivative arrows, plus the
    sampling controls).

    Component formulas of F(t) and F'(t) are also displayed below
    the controls so the user can read off the formulas without
    leaving the panel. The toggle ``realfn_display_latex`` (the same
    one used by the scalar panel) selects plain SymPy text vs LaTeX.
    """

    bl_label = "Paramètres du modifier (vectoriel)"
    bl_idname = "REALFN_PT_vector_params"
    bl_parent_id = "REALFN_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RealFn"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return operators._active_vector_realfn_modifier(context) is not None

    def draw(self, context):
        layout = self.layout
        mod = operators._active_vector_realfn_modifier(context)
        if mod is None:
            return
        nt = mod.node_group

        # ---- 1. Modifier sockets, grouped into sections -------------
        _draw_sectioned_params(layout, mod, nt, [
            ("v_dom", "Domaine & échantillonnage", "MESH_GRID",
             ["Resolution", "t min", "t max"], False),
            ("v_t0", "Point t₀", "EMPTY_AXIS",
             ["t_0"], False),
            ("v_trace", "Trajectoire", "FCURVE",
             ["Trace thickness", "Material · trace"], True),
            ("v_kin", "Vecteurs cinématiques", "EMPTY_ARROWS",
             ["Show position vector", "Show derivative vector",
              "Show acceleration vector", "Material · position",
              "Material · vitesse", "Material · accélération"], True),
        ])

        # ---- 1bis. Material shortcuts -----------------------------
        # Two convenience buttons related to the per-piece material
        # sockets shown just above:
        #
        #   * "Code couleur cinématique" : assigns the standard
        #     physics colour mapping (position=blue, vitesse=green,
        #     accélération=red, trace=grey) in one click. Installs
        #     the bundled palette if it's missing.
        #
        #   * "Installer la palette" : explicit re-install of the
        #     8-colour palette, useful in a fresh .blend that didn't
        #     start with our materials defined.
        box = layout.box()
        box.label(text=i18n.tr("Matériaux :"), icon="MATERIAL")
        box.operator("realfn.apply_kinematic_colors",
                      icon="BRUSHES_ALL",
                      text=i18n.tr("Code couleur cinématique"))
        box.operator("realfn.install_default_materials",
                      icon="ADD",
                      text=i18n.tr("Installer la palette"))

        # ---- 2. Component formulas (read-only display) -------------
        # Component lists are stashed by make_vectorfn_tree as parallel
        # arrays: index 0 = x, 1 = y, 2 = z.
        use_latex = getattr(context.window_manager,
                            "realfn_display_latex", False)
        comp_key = ("realfn_components_latex" if use_latex
                    else "realfn_components_text")
        deriv_key = ("realfn_derivatives_latex" if use_latex
                     else "realfn_derivatives_text")
        second_key = ("realfn_second_derivatives_latex" if use_latex
                       else "realfn_second_derivatives_text")
        components = nt.get(comp_key) or nt.get("realfn_components_text")
        derivatives = nt.get(deriv_key) or nt.get("realfn_derivatives_text")
        second_derivs = (nt.get(second_key)
                          or nt.get("realfn_second_derivatives_text"))
        if components and derivatives:
            try:
                components = list(components)
                derivatives = list(derivatives)
                second_derivs = list(second_derivs) if second_derivs else None
            except TypeError:
                components, derivatives, second_derivs = [], [], None
            if components and derivatives:
                box = layout.box()
                box.label(text=i18n.tr("F(t) :"), icon="FORCE_CURVE")
                for axis, c in zip(("Fx", "Fy", "Fz"), components):
                    _draw_formula_under_checkbox(
                        box, "", f"{axis} = {c}",
                    )
                box = layout.box()
                box.label(text=i18n.tr("F'(t) :"), icon="FORCE_VORTEX")
                for axis, d in zip(("F'x", "F'y", "F'z"), derivatives):
                    _draw_formula_under_checkbox(
                        box, "", f"{axis} = {d}",
                    )
                # F''(t) only displayed when the stash is present —
                # older vector trees built before 2.1.2 don't have it,
                # silently skip rather than show an empty box.
                if second_derivs:
                    box = layout.box()
                    box.label(text=i18n.tr("F''(t) :"), icon="FORCE_HARMONIC")
                    for axis, d in zip(("F''x", "F''y", "F''z"),
                                        second_derivs):
                        _draw_formula_under_checkbox(
                            box, "", f"{axis} = {d}",
                        )


class REALFN_PT_surface_params(bpy.types.Panel):
    """Inline view of the explicit-surface modifier inputs.

    Same direct-render strategy as the scalar / vector parameter
    panels: iterate the tree's input sockets, expose each as a panel
    line, and translate the display labels via :func:`_socket_label`.

    Closed by default. Useful read-only display: text of f(x, y),
    ∂f/∂x, ∂f/∂y stashed in the tree metadata at construction time.
    """

    bl_label = "Paramètres du modifier (surface)"
    bl_idname = "REALFN_PT_surface_params"
    bl_parent_id = "REALFN_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RealFn"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return operators._active_surface_realfn_modifier(context) is not None

    def draw(self, context):
        layout = self.layout
        mod = operators._active_surface_realfn_modifier(context)
        if mod is None:
            return
        nt = mod.node_group

        # Sockets grouped into collapsible sections.
        _draw_sectioned_params(layout, mod, nt, [
            ("s_dom", "Domaine & grille", "MESH_GRID",
             ["Resolution X", "Resolution Y",
              "x min", "x max", "y min", "y max"], False),
            ("s_surf", "Surface", "SURFACE_NSURFACE",
             ["Surface material"], True),
            ("s_bp", "Point d'ancrage & plan tangent", "EMPTY_AXIS",
             ["x_0", "y_0", "Marker size", "Marker material",
              "Show tangent plane", "Tangent plane size",
              "Tangent plane resolution", "Tangent plane material"],
             True),
            ("s_taylor", "Surface de Taylor", "RNDCURVE",
             ["Show Taylor surface", "Taylor order",
              "Taylor surface size", "Taylor surface resolution",
              "Taylor surface material"],
             True),
        ])

        # Stashed formulas: f(x, y), ∂f/∂x, ∂f/∂y.
        use_latex = getattr(context.window_manager,
                            "realfn_display_latex", False)
        f_key = "realfn_f_latex" if use_latex else "realfn_f_text"
        dx_key = "realfn_dfdx_latex" if use_latex else "realfn_dfdx_text"
        dy_key = "realfn_dfdy_latex" if use_latex else "realfn_dfdy_text"
        f_text = nt.get(f_key) or nt.get("realfn_f_text")
        dx_text = nt.get(dx_key) or nt.get("realfn_dfdx_text")
        dy_text = nt.get(dy_key) or nt.get("realfn_dfdy_text")
        if f_text:
            box = layout.box()
            box.label(text=i18n.tr("f(x, y) :"), icon="FORCE_FORCE")
            _draw_formula_under_checkbox(box, "", str(f_text))
        if dx_text:
            box = layout.box()
            box.label(text=i18n.tr("∂f/∂x :"), icon="ANIM_DATA")
            _draw_formula_under_checkbox(box, "", str(dx_text))
        if dy_text:
            box = layout.box()
            box.label(text=i18n.tr("∂f/∂y :"), icon="ANIM_DATA")
            _draw_formula_under_checkbox(box, "", str(dy_text))

        # Current-order Taylor polynomial (live with the order slider).
        _draw_taylor_poly(layout, mod, nt, use_latex, [("", "x, y")])


class REALFN_PT_parametric_surface_params(bpy.types.Panel):
    """Inline view of the parametric-surface modifier inputs."""

    bl_label = "Paramètres du modifier (surface paramétrée)"
    bl_idname = "REALFN_PT_parametric_surface_params"
    bl_parent_id = "REALFN_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RealFn"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return operators._active_parametric_surface_realfn_modifier(context) is not None

    def draw(self, context):
        layout = self.layout
        mod = operators._active_parametric_surface_realfn_modifier(context)
        if mod is None:
            return
        nt = mod.node_group

        _draw_sectioned_params(layout, mod, nt, [
            ("ps_dom", "Domaine & grille", "MESH_GRID",
             ["Resolution U", "Resolution V",
              "u min", "u max", "v min", "v max"], False),
            ("ps_surf", "Surface", "SURFACE_NSURFACE",
             ["Surface material"], True),
            ("ps_bp", "Point d'ancrage & plan tangent", "EMPTY_AXIS",
             ["u_0", "v_0", "Marker size", "Marker material",
              "Show tangent plane", "Tangent plane size",
              "Tangent plane resolution", "Tangent plane material"],
             True),
            ("ps_taylor", "Surface de Taylor", "RNDCURVE",
             ["Show Taylor surface", "Taylor order",
              "Taylor surface size", "Taylor surface resolution",
              "Taylor surface material"],
             True),
        ])

        # F(u, v) and its partials, stashed as 3-element lists.
        use_latex = getattr(context.window_manager,
                            "realfn_display_latex", False)
        comps_key = ("realfn_components_latex" if use_latex
                     else "realfn_components_text")
        comps = nt.get(comps_key) or nt.get("realfn_components_text")
        d_u = nt.get("realfn_dFdu_text")
        d_v = nt.get("realfn_dFdv_text")
        try:
            comps_list = list(comps) if comps else []
            du_list = list(d_u) if d_u else []
            dv_list = list(d_v) if d_v else []
        except TypeError:
            comps_list, du_list, dv_list = [], [], []
        if comps_list:
            box = layout.box()
            box.label(text=i18n.tr("F(u, v) :"), icon="FORCE_FORCE")
            for axis, c in zip(("x", "y", "z"), comps_list):
                _draw_formula_under_checkbox(box, "", f"{axis} = {c}")
        if du_list:
            box = layout.box()
            box.label(text=i18n.tr("∂F/∂u :"), icon="ANIM_DATA")
            for axis, d in zip(("x", "y", "z"), du_list):
                _draw_formula_under_checkbox(box, "", f"{axis} = {d}")
        if dv_list:
            box = layout.box()
            box.label(text=i18n.tr("∂F/∂v :"), icon="ANIM_DATA")
            for axis, d in zip(("x", "y", "z"), dv_list):
                _draw_formula_under_checkbox(box, "", f"{axis} = {d}")

        # Current-order Taylor polynomial per component (live with order).
        _draw_taylor_poly(layout, mod, nt, use_latex,
                          [("x", "u, v"), ("y", "u, v"), ("z", "u, v")])


def _draw_sectioned_params(layout, mod, nt, sections, after_item=None):
    """Draw a modifier's input sockets grouped into collapsible
    thematic sections instead of one flat 35-row wall.

    ``sections`` is an ordered list of ``(section_id, title, icon,
    [socket names], default_closed)``. Sockets not claimed by any
    section fall into a trailing « Paramètres libres » section — so a
    new socket added to a tree still surfaces automatically, exactly
    like the old flat loop, just less tidily until it's assigned.

    ``after_item``, if given, is called as ``after_item(body, item)``
    after each property row — the curve panel uses it to draw the
    piece formula under its « Visible · … » checkbox.

    Collapsing uses ``layout.panel()`` (Blender ≥ 4.1; state persists
    per section id). On older builds it degrades to labelled boxes —
    everything visible, nothing lost.
    """
    claimed = {}
    for sid, _t, _i, names, _c in sections:
        for n in names:
            claimed[n] = sid
    buckets = {sid: [] for sid, *_ in sections}
    extra = []
    for item in nt.interface.items_tree:
        if getattr(item, "in_out", None) != "INPUT":
            continue
        sid = claimed.get(item.name)
        if sid is None:
            extra.append(item)
        else:
            buckets[sid].append(item)

    all_sections = list(sections)
    if extra:
        all_sections.append(
            ("free", "Paramètres libres", "DRIVER", [], True))
        buckets["free"] = extra

    for sid, title, icon, _names, closed in all_sections:
        items = buckets.get(sid) or []
        if not items:
            continue
        body = None
        used_panel = False
        if hasattr(layout, "panel"):
            try:
                header, body = layout.panel(f"realfn_sec_{sid}",
                                            default_closed=closed)
                header.label(text=i18n.tr(title), icon=icon)
                used_panel = True
            except (TypeError, RuntimeError):
                used_panel = False
        if not used_panel:
            box = layout.box()
            box.label(text=i18n.tr(title), icon=icon)
            body = box
        if body is None:
            continue  # collapsed panel: header only
        for item in items:
            try:
                if not modifier_inputs.draw_input(
                        body, mod, item.identifier,
                        text=_socket_label(item.name)):
                    continue
            except (TypeError, RuntimeError):
                continue
            if after_item is not None:
                after_item(body, item)


class REALFN_PT_scalar_field_3d_params(bpy.types.Panel):
    """Inline view of the 3D scalar field modifier inputs."""

    bl_label = "Paramètres du modifier (champ scalaire 3D)"
    bl_idname = "REALFN_PT_scalar_field_3d_params"
    bl_parent_id = "REALFN_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RealFn"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return operators._active_scalar_field_3d_realfn_modifier(context) is not None

    def draw(self, context):
        layout = self.layout
        mod = operators._active_scalar_field_3d_realfn_modifier(context)
        if mod is None:
            return
        nt = mod.node_group

        _draw_sectioned_params(layout, mod, nt, [
            ("sf_dom", "Domaine & grille", "MESH_GRID",
             ["Resolution X", "Resolution Y", "Resolution Z",
              "x min", "x max", "y min", "y max", "z min", "z max"],
             False),
            ("sf_mark", "Sphères & couleurs", "SHADING_RENDERED",
             ["Marker size", "Marker material", "f min", "f max"],
             True),
            ("sf_lbl", "Étiquettes numériques", "OUTLINER_OB_FONT",
             ["Show value labels", "Label stride", "Label size",
              "Label offset", "Label decimals", "Label vertical",
              "Label max points", "Label material"],
             True),
            ("sf_frame", "Cadre & axes gradués", "MOD_WIREFRAME",
             ["Show domain frame", "Frame thickness", "Frame material",
              "Show graduated axes", "Axis label size",
              "Axis label decimals", "Axis label material"],
             True),
            ("sf_bp", "Point d'ancrage", "EMPTY_AXIS",
             ["x_0", "y_0", "z_0", "Show basepoint",
              "Basepoint marker size", "Basepoint marker material",
              "Basepoint label size", "Basepoint label offset",
              "Basepoint label material"],
             True),
        ])

        # Display of f(x, y, z) and its gradient — stashed at build time.
        use_latex = getattr(context.window_manager,
                            "realfn_display_latex", False)
        f_key = "realfn_f_latex" if use_latex else "realfn_f_text"
        f_text = nt.get(f_key) or nt.get("realfn_f_text")
        if f_text:
            box = layout.box()
            box.label(text=i18n.tr("f(x, y, z) :"), icon="FORCE_FORCE")
            _draw_formula_under_checkbox(box, "", str(f_text))
        grad_key = "realfn_grad_latex" if use_latex else "realfn_grad_text"
        grad_data = nt.get(grad_key) or nt.get("realfn_grad_text")
        try:
            grad_list = list(grad_data) if grad_data else []
        except TypeError:
            grad_list = []
        if grad_list:
            box = layout.box()
            box.label(text=i18n.tr("∇f :"), icon="ANIM_DATA")
            for axis, g in zip(("∂f/∂x", "∂f/∂y", "∂f/∂z"), grad_list):
                _draw_formula_under_checkbox(box, "", f"{axis} = {g}")


class REALFN_PT_vector_field_3d_params(bpy.types.Panel):
    """Inline view of the 3D vector field modifier inputs.

    Same direct-render pattern as the scalar / vector / surface
    parameter panels: iterate input sockets in their declaration order,
    expose each through ``layout.prop``, translate the display label
    via :func:`_socket_label`. The trick — same as for every kind — is
    that **adding a new socket in vector_field_3d_tree.py
    automatically surfaces it here** without panel changes, provided
    the label is added to ``_SOCKET_LABELS_FR`` for translation.

    Read-only display: V_x, V_y, V_z (or the potential ϕ if the field
    was built from one), the divergence div V, and the curl ∇×V. All
    computed symbolically by SymPy at tree-build time and stashed in
    metadata — no runtime cost here.
    """

    bl_label = "Paramètres du modifier (champ de vecteurs 3D)"
    bl_idname = "REALFN_PT_vector_field_3d_params"
    bl_parent_id = "REALFN_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RealFn"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return operators._active_vector_field_3d_realfn_modifier(context) is not None

    def draw(self, context):
        layout = self.layout
        mod = operators._active_vector_field_3d_realfn_modifier(context)
        if mod is None:
            return
        nt = mod.node_group

        _draw_sectioned_params(layout, mod, nt, [
            ("vf_dom", "Domaine & grille", "MESH_GRID",
             ["Resolution X", "Resolution Y", "Resolution Z",
              "x min", "x max", "y min", "y max", "z min", "z max"],
             False),
            ("vf_arr", "Flèches du champ", "EMPTY_ARROWS",
             ["Show arrows", "Arrow scale", "Arrow material",
              "Marker size", "Marker material"],
             True),
            ("vf_lbl", "Étiquettes de norme", "OUTLINER_OB_FONT",
             ["Show norm labels", "Norm label stride", "Norm label size",
              "Norm label offset", "Norm label decimals",
              "Norm label vertical", "Norm label max points",
              "Norm label material"],
             True),
            ("vf_frame", "Cadre & axes gradués", "MOD_WIREFRAME",
             ["Show domain frame", "Frame thickness", "Frame material",
              "Show graduated axes", "Axis label size",
              "Axis label decimals", "Axis label material"],
             True),
            ("vf_bp", "Point d'ancrage", "EMPTY_AXIS",
             ["x_0", "y_0", "z_0", "Basepoint arrow material",
              "Show component arrows", "Component arrow material",
              "Show basepoint norm label", "Label size",
              "Label vertical offset", "Label material"],
             True),
        ])

        # Source potential first if the field came from one — visually
        # ranking it above the derived components since it's the
        # primary mathematical object the user typed.
        use_latex = getattr(context.window_manager,
                            "realfn_display_latex", False)
        mode = str(nt.get("realfn_mode", "explicit"))
        if mode == "from_potential":
            phi_text = nt.get("realfn_potential")
            if phi_text:
                box = layout.box()
                box.label(text=i18n.tr("ϕ(x, y, z) :"), icon="FORCE_FORCE")
                _draw_formula_under_checkbox(box, "", str(phi_text))

        comps_key = ("realfn_components_latex" if use_latex
                     else "realfn_components_text")
        comps = nt.get(comps_key) or nt.get("realfn_components_text")
        try:
            comps_list = list(comps) if comps else []
        except TypeError:
            comps_list = []
        if comps_list:
            box = layout.box()
            box.label(text=i18n.tr("V :"), icon="ORIENTATION_GLOBAL")
            for axis, c in zip(("V_x", "V_y", "V_z"), comps_list):
                _draw_formula_under_checkbox(box, "", f"{axis} = {c}")

        # Divergence and curl — vector-calculus invariants worth
        # showing because they're "diagnostic" labels: a zero curl
        # confirms the field is conservative, a zero divergence
        # confirms it's incompressible. Useful as a sanity check
        # when toggling between explicit and from-potential modes.
        div_key = "realfn_div_latex" if use_latex else "realfn_div_text"
        div_text = nt.get(div_key) or nt.get("realfn_div_text")
        if div_text:
            box = layout.box()
            box.label(text=i18n.tr("Divergence ∇·V :"), icon="DOT")
            _draw_formula_under_checkbox(box, "", str(div_text))

        curl_key = "realfn_curl_latex" if use_latex else "realfn_curl_text"
        curl_data = nt.get(curl_key) or nt.get("realfn_curl_text")
        try:
            curl_list = list(curl_data) if curl_data else []
        except TypeError:
            curl_list = []
        if curl_list:
            box = layout.box()
            box.label(text=i18n.tr("Rotationnel ∇×V :"), icon="CON_ROTLIKE")
            for axis, c in zip(("(∇×V)_x", "(∇×V)_y", "(∇×V)_z"), curl_list):
                _draw_formula_under_checkbox(box, "", f"{axis} = {c}")


# --------------------------------------------------------------------------- #
# Preset panels — one generic draw, six thin generated classes
# --------------------------------------------------------------------------- #
# The six preset sub-panels used to be six ~70-line ``draw`` methods that
# differed only in which list/is-builtin/operator names they referenced.
# They are now generated from :data:`_PRESET_PANELS`; the layout is the
# scalar panel's built-in/user split (strictly nicer than the flat list
# the other five used before), so every kind now looks consistent.
def _draw_preset_rows(layout, entries, idn, has_active):
    """One row per preset: apply (full width) + export + delete."""
    for disp, name, path in entries:
        row = layout.row(align=True)
        apply_row = row.row(align=True)
        apply_row.enabled = has_active
        op = apply_row.operator(f"realfn.apply_{idn}preset",
                                text=disp, icon="PLAY")
        op.preset_path = str(path)
        sub = row.row(align=True)
        sub.scale_x = 0.9
        sub.operator(f"realfn.export_{idn}preset",
                     text="", icon="EXPORT").preset_name = name
        sub.operator(f"realfn.delete_{idn}preset",
                     text="", icon="X").preset_name = name


def _draw_preset_panel(layout, context, *, idn, finder, list_fn, is_builtin):
    """Generic body for every preset sub-panel: a save/import row, then
    the built-in catalogue and the user presets as two labelled boxes."""
    has_active = getattr(operators, finder)(context) is not None

    row = layout.row(align=True)
    save_row = row.row(align=True)
    save_row.enabled = has_active
    save_row.operator(f"realfn.save_{idn}preset", icon="FILE_TICK",
                      text=i18n.tr("Enregistrer…"))
    row.operator(f"realfn.import_{idn}preset", icon="IMPORT",
                 text=i18n.tr("Importer…"))

    try:
        entries = list_fn()
    except OSError as exc:
        layout.label(text=i18n.tr("Erreur dossier : ") + str(exc),
                     icon="ERROR")
        return

    builtin = [e for e in entries if is_builtin(e[2])]
    user = [e for e in entries if not is_builtin(e[2])]

    box = layout.box()
    header = box.row(align=True)
    header.label(text=i18n.tr("Catalogue builtin") + f" ({len(builtin)})",
                 icon="ASSET_MANAGER")
    header.operator(f"realfn.reinstall_{idn}builtins", text="",
                    icon="FILE_REFRESH")
    if not builtin:
        box.label(
            text=i18n.tr("Cliquer ↻ pour installer les fonctions classiques"),
            icon="INFO")
    else:
        _draw_preset_rows(box, builtin, idn, has_active)

    box = layout.box()
    box.label(text=i18n.tr("Mes presets") + f" ({len(user)})", icon="USER")
    if not user:
        box.label(text=i18n.tr("Aucun preset utilisateur"), icon="INFO")
        box.label(text=i18n.tr("Cliquez « Enregistrer… » pour démarrer"),
                  icon="BLANK1")
    else:
        _draw_preset_rows(box, user, idn, has_active)


# (bl_idname, FR label, bl_idname infix, active-finder name, list fn,
#  is-builtin predicate)
_PRESET_PANELS = [
    ("REALFN_PT_presets", "Presets", "",
     "_active_realfn_modifier",
     presets.list_presets, builtin_presets.is_builtin_file),
    ("REALFN_PT_vector_presets", "Presets vectoriels", "vector_",
     "_active_vector_realfn_modifier",
     presets.list_vector_presets, builtin_presets.is_vector_builtin_file),
    ("REALFN_PT_surface_presets", "Presets surface", "surface_",
     "_active_surface_realfn_modifier",
     presets.list_surface_presets, builtin_presets.is_surface_builtin_file),
    ("REALFN_PT_parametric_surface_presets", "Presets surface paramétrée",
     "parametric_surface_",
     "_active_parametric_surface_realfn_modifier",
     presets.list_parametric_surface_presets,
     builtin_presets.is_parametric_surface_builtin_file),
    ("REALFN_PT_scalar_field_3d_presets", "Presets champ scalaire 3D",
     "scalar_field_3d_",
     "_active_scalar_field_3d_realfn_modifier",
     presets.list_scalar_field_3d_presets,
     builtin_presets.is_scalar_field_3d_builtin_file),
    ("REALFN_PT_vector_field_3d_presets", "Presets champ de vecteurs 3D",
     "vector_field_3d_",
     "_active_vector_field_3d_realfn_modifier",
     presets.list_vector_field_3d_presets,
     builtin_presets.is_vector_field_3d_builtin_file),
    ("REALFN_PT_vector_bench_presets", "Presets banc de vecteurs",
     "vector_bench_",
     "_active_vector_bench_realfn_modifier",
     presets.list_vector_bench_presets,
     builtin_presets.is_vector_bench_builtin_file),
]


def build_preset_panels():
    """Generate the six preset sub-panel classes from `_PRESET_PANELS`."""
    out = []
    for idname, label, idn, finder, list_fn, is_builtin in _PRESET_PANELS:
        def draw(self, context, *, _idn=idn, _finder=finder,
                 _list=list_fn, _isb=is_builtin):
            _draw_preset_panel(self.layout, context, idn=_idn,
                               finder=_finder, list_fn=_list, is_builtin=_isb)
        out.append(type(idname, (bpy.types.Panel,), {
            "bl_label": label,
            "bl_idname": idname,
            "bl_parent_id": "REALFN_PT_main",
            "bl_space_type": "VIEW_3D",
            "bl_region_type": "UI",
            "bl_category": "RealFn",
            "bl_options": {"DEFAULT_CLOSED"},
            "draw": draw,
        }))
    return out


# The six preset sub-panels are generated (build_preset_panels) and
# appended; they register after the parameter panels so they keep
# appearing last in the N-panel.
classes = (REALFN_PT_main, REALFN_PT_params,
           REALFN_PT_vector_params, REALFN_PT_surface_params,
           REALFN_PT_parametric_surface_params,
           REALFN_PT_scalar_field_3d_params,
           REALFN_PT_vector_field_3d_params,
           ) + tuple(build_preset_panels())
