"""
Default material palette for RealFnViewer.

Provides a small set of pre-configured materials so users get something
visually distinct without having to dive into the Shader editor. Two
families of helpers live here:

1. :func:`ensure_default_materials` — installs the palette into
   ``bpy.data.materials`` on first run, idempotent. The palette is
   eight colours covering the typical kinematic / pedagogical needs:
   blue/green/red for the position/velocity/acceleration triad,
   grey for traces and underlay, plus yellow / magenta / cyan /
   orange for scalar curve families.

2. :func:`apply_kinematic_color_code` — one-click assignment of the
   canonical kinematic code (position → blue, velocity → green,
   acceleration → red) to a vector RealFn modifier. The wrapping
   operator (in operators.py) calls this on the active object.

Why is this in its own module rather than woven into operators.py?
Materials creation needs ``use_nodes=True`` set up correctly, with
a Principled BSDF node receiving the colour — there's a fair bit of
fiddly Blender API around that, and isolating it makes the rest of
the codebase easier to read.
"""

from __future__ import annotations

import bpy

from . import modifier_inputs


MATERIAL_PREFIX = "RealFn "


# Canonical palette. Tuples are ``(short_name, RGB)`` — the actual
# datablock name is ``f"{MATERIAL_PREFIX}{short_name}"``. RGB values
# are tuned so each colour reads distinctly against Blender's default
# grey background in Solid view, not just in Material/Rendered modes.
#
# La seconde série (suffixe "XPBR") reprend les teintes moyennes des
# matériaux Extreme PBR correspondants, converties en espace linéaire,
# pour assortir les courbes RealFn à une scène utilisant ces matériaux.
_PALETTE = [
    # Palette de base (8 couleurs pédagogiques)
    ("Bleu",     (0.10, 0.30, 0.90)),
    ("Vert",     (0.10, 0.70, 0.20)),
    ("Rouge",    (0.90, 0.15, 0.15)),
    ("Gris",     (0.40, 0.40, 0.40)),
    ("Jaune",    (0.95, 0.80, 0.10)),
    ("Magenta",  (0.85, 0.10, 0.60)),
    ("Cyan",     (0.10, 0.70, 0.85)),
    ("Orange",   (0.95, 0.45, 0.10)),
    # Palette XPBR — teintes extraites de la bibliothèque Extreme PBR
    # (valeur diffuse moyenne des textures 1k, convertie en linéaire sRGB).
    # Permet d'assortir les courbes à une scène PBR sans quitter le panneau.
    ("XPBR Bleu Plastique",  (0.03, 0.11, 0.42)),   # Blue Plastic 001
    ("XPBR Vert Plastique",  (0.02, 0.23, 0.06)),   # Green Plastic 001
    ("XPBR Rouge Plastique", (0.48, 0.01, 0.01)),   # Red/Orange Plastic approx
    ("XPBR Métal Brut",      (0.45, 0.45, 0.45)),   # Metal Raw (neutre)
    ("XPBR Métal Rouillé",   (0.38, 0.12, 0.03)),   # Metal Rusty (brun-rouge)
    ("XPBR Béton Lisse",     (0.52, 0.52, 0.50)),   # Concrete Smooth (gris chaud)
    ("XPBR Verre",           (0.70, 0.82, 0.90)),   # Glass 001 (bleu-gris pâle)
    ("XPBR Asphalte",        (0.06, 0.06, 0.06)),   # Asphalt Dark
]

# Dict form used by the palette preset system: name → (R, G, B).
# ``DEFAULT_PALETTE`` is the read-only reference; ``PALETTE`` is the
# mutable copy that ``apply_palette`` mutates in place.
DEFAULT_PALETTE = {short: rgb for short, rgb in _PALETTE}
PALETTE = dict(DEFAULT_PALETTE)


def _full_name(short: str) -> str:
    return MATERIAL_PREFIX + short


def _material_node_tree(mat):
    """Return ``mat``'s shader node tree, enabling nodes when needed.

    Blender 5.0+ always uses nodes for materials and deprecates the
    ``use_nodes`` toggle (setting it only emits a warning); older
    versions still need it switched on to create the default tree.
    """
    if bpy.app.version < (5, 0, 0) and not mat.use_nodes:
        mat.use_nodes = True
    return mat.node_tree


def _find_node(node_tree, bl_idname: str):
    """First node of the given type. Looked up by type rather than by
    name: with *Preferences › Interface › Translation › New Data*
    enabled the default node is called e.g. "BSDF Principled" in French
    and a name lookup silently misses it."""
    if node_tree is None:
        return None
    for node in node_tree.nodes:
        if node.bl_idname == bl_idname:
            return node
    return None


def _principled(mat):
    return _find_node(mat.node_tree, "ShaderNodeBsdfPrincipled")


def _make_material(short_name: str, rgb: tuple) -> "bpy.types.Material":
    """Create one palette material with a Principled BSDF feeding the colour.

    ``use_nodes=True`` is enabled and the default node tree (Principled
    BSDF → Material Output) is reused — Blender creates it automatically.
    The ``Base Color`` input is set to ``(*rgb, 1.0)``. ``diffuse_color``
    (which drives the Solid viewport shading) is set to the same RGB so
    the colour is visible even without Material Preview.
    """
    name = _full_name(short_name)
    mat = bpy.data.materials.new(name=name)
    _material_node_tree(mat)
    bsdf = _principled(mat)
    if bsdf is not None:
        # "Base Color" is the input name across Blender 3.x and 4.x.
        bc = bsdf.inputs.get("Base Color")
        if bc is not None:
            bc.default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    # Solid-view colour — independent of the node tree.
    mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    return mat


def ensure_default_materials() -> int:
    """Install missing palette materials into ``bpy.data.materials``.

    Returns the number of materials *created* (existing ones are not
    overwritten — the user may have customised them, and the typical
    case after first run is "all eight are already there, return 0").
    Uses the mutable ``PALETTE`` so any active palette preset is honoured.
    """
    created = 0
    for short, _default_rgb in _PALETTE:
        full = _full_name(short)
        if full in bpy.data.materials:
            continue
        try:
            _make_material(short, PALETTE.get(short, _default_rgb))
            created += 1
        except Exception as exc:
            # Don't let one bad creation block the rest. Log and move on.
            print(f"[RealFn] Could not create material {full!r}: {exc}")
    return created


def get_palette_material(short_name: str) -> "bpy.types.Material | None":
    """Return the named palette material, or None if not installed."""
    return bpy.data.materials.get(_full_name(short_name))


# --------------------------------------------------------------------------- #
# Kinematic colour code
# --------------------------------------------------------------------------- #
# Standard physics convention used in most textbooks:
#   position    → blue   (the radius vector, a "where you are" reference)
#   velocity    → green  (tangent to the trajectory)
#   acceleration → red   (curvature / change in velocity, the "force" colour)
#   trace       → grey   (background indication, less visually loud)

_KINEMATIC_MAPPING = {
    "Material · position":     "Bleu",
    "Material · vitesse":      "Vert",
    "Material · accélération": "Rouge",
    "Material · trace":        "Gris",
}


def apply_kinematic_color_code(modifier) -> dict:
    """Assign the standard kinematic colours to a vector modifier.

    Looks up each of the four arrow / trace material sockets in the
    modifier's node group and assigns the corresponding palette
    material if both the socket and the material exist.

    Returns ``{"applied": N, "skipped": M}`` so the calling operator
    can give meaningful feedback.
    """
    if modifier is None or modifier.node_group is None:
        return {"applied": 0, "skipped": 0}
    nt = modifier.node_group

    # Make sure the palette is installed — cheap if already done.
    ensure_default_materials()

    n_applied = 0
    n_skipped = 0
    for item in nt.interface.items_tree:
        if getattr(item, "in_out", None) != "INPUT":
            continue
        target_short = _KINEMATIC_MAPPING.get(item.name)
        if target_short is None:
            continue
        mat = get_palette_material(target_short)
        if mat is None:
            n_skipped += 1
            continue
        if modifier_inputs.set_value(modifier, item.identifier, mat):
            n_applied += 1
        else:
            n_skipped += 1
    return {"applied": n_applied, "skipped": n_skipped}


# --------------------------------------------------------------------------- #
# Color-ramp material for 3D scalar fields
# --------------------------------------------------------------------------- #
SCALAR_FIELD_3D_MATERIAL_NAME = "RealFn ScalarField 3D"


def _make_scalar_field_3d_material() -> "bpy.types.Material":
    """Create a material that colours geometry by the named float
    attribute ``rfn_f_value``.

    Shader graph
    ------------
    ``Attribute("rfn_f_value")`` → Fac (the scalar value at each vertex)
                                                ↓
                  ``MapRange`` ``From Min/Max`` ← ``f min`` / ``f max``
                              (from modifier sockets, but here as hardcoded
                               defaults since shaders can't read modifier
                               sockets directly. We use a Color Ramp with
                               its own positions instead.)
                                                ↓
                                      ``ColorRamp`` (perceptual viridis-like)
                                                ↓
                                       ``Principled BSDF.Base Color``
                                                ↓
                                       ``Material Output``

    Why this works without modifier-side min/max sockets
    ----------------------------------------------------
    Geometry-Nodes can't drive a *shader* socket directly (the
    modifier and the shader are separate eval contexts). To
    parameterise the colour range from the modifier, we'd need to
    bake a normalised attribute. For the default material we just
    use a ColorRamp with anchor points at fixed positions on a
    [0, 1] range and rely on the user setting reasonable f-min/max
    sockets on the modifier itself — those drive a normalisation
    inside the GN tree (StoreNamedAttribute with mapped value),
    so by the time the shader reads ``rfn_f_value`` it's already
    in [0, 1].

    Palette
    -------
    Three-stop perceptual ramp blue → cyan/green → red, in the
    spirit of viridis but with fewer stops to keep the shader cheap.
    The colour ramp's interpolation is left at the default linear
    RGB — close enough to viridis for educational purposes and
    cheaper than HSL with monotonic luminance.
    """
    mat = bpy.data.materials.new(name=SCALAR_FIELD_3D_MATERIAL_NAME)
    nt = _material_node_tree(mat)
    # Clean slate — Blender pre-populates Principled BSDF + Output, we
    # keep them but rewire.
    bsdf = _find_node(nt, "ShaderNodeBsdfPrincipled")
    output = _find_node(nt, "ShaderNodeOutputMaterial")
    if bsdf is None or output is None:
        # Defensive: in some unusual default trees these may be absent
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        output = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    bsdf.location = (300, 0)
    output.location = (600, 0)

    # Attribute node — reads the per-vertex rfn_f_value (already
    # normalised to [0, 1] by the modifier).
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "rfn_f_value"
    attr.location = (-400, 0)
    attr.label = "rfn_f_value"

    # Color ramp — viridis-like in three stops.
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-100, 0)
    ramp.label = "f → colour"
    # ColorRamp comes with two default stops (black at 0, white at 1).
    # We replace them with three stops: cold blue → green → warm red.
    cr = ramp.color_ramp
    cr.interpolation = "LINEAR"
    # Modify the two default stops in place and add a third.
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0.15, 0.20, 0.65, 1.0)   # deep blue
    cr.elements[1].position = 1.0
    cr.elements[1].color = (0.85, 0.20, 0.15, 1.0)   # warm red
    mid = cr.elements.new(0.5)
    mid.color = (0.30, 0.75, 0.40, 1.0)              # green

    # Wire: Attribute.Fac → ColorRamp.Fac → BSDF.Base Color.
    nt.links.new(attr.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    # A reasonable solid-view colour (greenish, the mid stop).
    mat.diffuse_color = (0.30, 0.75, 0.40, 1.0)
    return mat


def ensure_scalar_field_3d_material() -> "bpy.types.Material":
    """Idempotent getter for the scalar-field-3D color-ramp material.

    First call creates the material; subsequent calls return the
    existing one. Users may customise the ColorRamp stops without
    fear of overwrite — we only create when absent.
    """
    existing = bpy.data.materials.get(SCALAR_FIELD_3D_MATERIAL_NAME)
    if existing is not None:
        return existing
    return _make_scalar_field_3d_material()


# --------------------------------------------------------------------------- #
# Palette preset system
# --------------------------------------------------------------------------- #

def apply_palette(palette_dict: dict) -> None:
    """Replace mutable ``PALETTE`` entries and propagate to existing materials.

    Keys absent from ``DEFAULT_PALETTE`` are silently ignored (resilience
    against stale JSON from older versions). Only the Principled BSDF
    ``Base Color`` input and ``diffuse_color`` are touched — user-added
    nodes, roughness settings, etc. are left intact.
    """
    for short, rgb in palette_dict.items():
        if short not in DEFAULT_PALETTE:
            continue
        r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])
        PALETTE[short] = (r, g, b)
        mat = bpy.data.materials.get(_full_name(short))
        if mat is None:
            continue
        bsdf = _principled(mat)
        if bsdf is not None:
            bc = bsdf.inputs.get("Base Color")
            if bc is not None:
                bc.default_value = (r, g, b, 1.0)
        mat.diffuse_color = (r, g, b, 1.0)


def snapshot_palette() -> dict:
    """Capture the currently effective palette colors.

    For each entry in ``DEFAULT_PALETTE``:
    - if the material exists and has a Principled BSDF with a readable
      ``Base Color``, use that (what the user actually sees);
    - otherwise fall back to the in-memory ``PALETTE`` value.

    This ensures a Save immediately after Shader Editor edits captures
    the visible colour rather than the last-set-by-preset value.
    """
    snap = {}
    for short in DEFAULT_PALETTE:
        mat = bpy.data.materials.get(_full_name(short))
        if mat is not None:
            bsdf = _principled(mat)
            if bsdf is not None:
                bc = bsdf.inputs.get("Base Color")
                if bc is not None:
                    c = bc.default_value
                    snap[short] = (float(c[0]), float(c[1]), float(c[2]))
                    continue
        snap[short] = PALETTE.get(short, DEFAULT_PALETTE[short])
    return snap


def reset_to_default() -> None:
    """Restore the factory-default palette and apply to existing materials."""
    apply_palette(DEFAULT_PALETTE)
