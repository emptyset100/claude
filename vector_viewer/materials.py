"""Création des matériaux émissifs pour les flèches du Vector Viewer
et les axes des trièdres.

Chaque matériau utilise un shader Emission (couleur + force) afin que
les flèches restent lisibles sans dépendre de l'éclairage de scène —
c'est le comportement souhaité pour une visualisation pédagogique.

Le module expose :
    - ``DEFAULT_PALETTE`` : valeurs constantes livrées avec l'extension.
    - ``PALETTE``         : palette mutable utilisée par les builds.
    - ``apply_palette``   : remplace ``PALETTE`` et propage aux matériaux.
    - ``snapshot_palette``: lit l'état effectif des matériaux.

``materials_presets`` pilote ``PALETTE`` via ``apply_palette``.
"""

import bpy


# ----------------------------------------------------------------------------
# Palette par défaut
# ----------------------------------------------------------------------------
# Toutes les valeurs sont en RGB linéaire (0-1). Conventions :
#   - Position / OO' / O'M : tons jaunes-blancs et gris (couleurs « neutres »)
#   - Vitesses : verts → cyans (« écoulement »)
#   - Accélérations : oranges → magentas → rouges (« forces »)
#   - Coriolis : rose vif (couleur saillante : c'est la flèche-clé en
#     pédagogie, on veut qu'elle saute aux yeux)
#   - Rotation instantanée Ω : jaune-or (pseudo-vecteur axial, distinct)
#   - Trièdre R  : RGB pur saturé (convention universelle)
#   - Trièdre R' : RGB pastel (même axe, repère mobile)
# ----------------------------------------------------------------------------

DEFAULT_PALETTE = {
    # Vector Viewer simple
    "VV_position":     (1.00, 0.85, 0.40),  # blanc-jaune
    "VV_velocity":     (0.20, 0.90, 0.30),  # vert
    "VV_acceleration": (0.95, 0.25, 0.20),  # rouge
    # Trajectoire OM du Vector Viewer simple : ton position désaturé/sombre
    "VV_traj_OM_simple": (0.55, 0.45, 0.20),  # jaune-ambre sombre

    # Composition — vecteurs de position
    "VV_OOp":          (0.50, 0.50, 0.60),  # gris-bleu
    "VV_OpM":          (1.00, 0.85, 0.40),  # blanc-jaune
    "VV_OM":           (1.00, 0.98, 0.92),  # ivoire (somme OOp + OpM)

    # Composition — vitesses (verts/cyans)
    "VV_vr":           (0.65, 1.00, 0.25),  # vert-jaune (relative)
    "VV_ve":           (0.00, 0.75, 0.75),  # turquoise (entraînement)
    "VV_va":           (0.10, 0.65, 0.10),  # vert sombre (absolue = somme)

    # Composition — accélérations (oranges/rouges/magenta)
    "VV_ar":           (1.00, 0.55, 0.05),  # orange (relative)
    "VV_ae":           (0.65, 0.15, 0.85),  # violet (entraînement)
    "VV_ac":           (1.00, 0.10, 0.55),  # rose vif (Coriolis)
    "VV_aa":           (0.75, 0.05, 0.05),  # rouge sombre (absolue = somme)

    # Composition — rotation instantanée Ω
    "VV_Omega":        (1.00, 0.92, 0.10),  # jaune-or

    # Composition — trajectoires (chemins parcourus, faded)
    # Versions désaturées des couleurs des vecteurs correspondants :
    # le "trail" reprend la teinte de la flèche dont il trace le chemin,
    # mais en sourdine pour ne pas voler la vedette à la flèche animée.
    "VV_traj_OOp":     (0.30, 0.30, 0.45),  # gris-bleu sombre (trace de O')
    "VV_traj_OM":      (0.55, 0.50, 0.42),  # beige sombre (trace de M absolu)
    "VV_traj_OpM":     (0.55, 0.42, 0.18),  # ambre sombre (trace de M dans R')

    # Trièdre R — RGB classique
    "VV_R_x":          (1.00, 0.10, 0.10),
    "VV_R_y":          (0.10, 1.00, 0.10),
    "VV_R_z":          (0.10, 0.20, 1.00),

    # Trièdre R' — RGB pastel
    "VV_Rp_x":         (1.00, 0.60, 0.55),
    "VV_Rp_y":         (0.55, 1.00, 0.55),
    "VV_Rp_z":         (0.55, 0.70, 1.00),
}

# Palette mutable utilisée par ``ensure_material``. Initialisée comme
# copie de DEFAULT_PALETTE ; ``apply_palette`` la mute en place.
PALETTE = dict(DEFAULT_PALETTE)


# Force d'émission par défaut. La force ne fait pas partie du système
# de presets : ces presets visent les couleurs, pas l'intensité.
DEFAULT_STRENGTH = 2.0


# ----------------------------------------------------------------------------
# Construction d'un matériau émissif
# ----------------------------------------------------------------------------

def _build_emission_material(mat, rgb, strength):
    """Configure le node tree d'un matériau pour qu'il émette la couleur
    ``rgb`` à la force ``strength``."""
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (200.0, 0.0)

    em = nt.nodes.new("ShaderNodeEmission")
    em.location = (0.0, 0.0)
    em.inputs["Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    em.inputs["Strength"].default_value = float(strength)

    nt.links.new(em.outputs[0], out.inputs[0])


def _emission_node(mat):
    """Retourne le node ShaderNodeEmission d'un matériau Vector Viewer,
    ou None si introuvable (matériau modifié par l'utilisateur)."""
    if not mat.use_nodes or mat.node_tree is None:
        return None
    for node in mat.node_tree.nodes:
        if node.type == 'EMISSION':
            return node
    return None


def _read_color(mat):
    """Lit la couleur RGB du node Emission, ou None si pas trouvé."""
    em = _emission_node(mat)
    if em is None:
        return None
    c = em.inputs["Color"].default_value
    return (float(c[0]), float(c[1]), float(c[2]))


def _write_color(mat, rgb):
    """Écrit ``rgb`` dans le node Emission. Reconstruit le node tree
    s'il a été modifié et que le node Emission n'est plus reconnaissable."""
    em = _emission_node(mat)
    if em is None:
        _build_emission_material(mat, rgb, DEFAULT_STRENGTH)
    else:
        em.inputs["Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)


def ensure_material(name, *, strength=DEFAULT_STRENGTH):
    """Crée ou met à jour le matériau ``name`` selon la palette courante.
    Retourne le matériau."""
    if name not in PALETTE:
        raise KeyError(f"Couleur inconnue : {name}. Voir materials.PALETTE.")
    rgb = PALETTE[name]
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    _build_emission_material(mat, rgb, strength)
    return mat


def ensure_all():
    """Construit/rafraîchit tous les matériaux de la palette."""
    return {name: ensure_material(name) for name in PALETTE}


def remove_all_unused():
    """Supprime les matériaux Vector Viewer qui ne sont plus référencés
    (utile dans Clear)."""
    for name in PALETTE:
        mat = bpy.data.materials.get(name)
        if mat is not None and mat.users == 0:
            bpy.data.materials.remove(mat)


# ----------------------------------------------------------------------------
# Application / snapshot d'une palette (système de presets)
# ----------------------------------------------------------------------------

def apply_palette(palette_dict):
    """Remplace ``PALETTE`` par ``palette_dict`` (clés inconnues ignorées)
    et propage les nouvelles couleurs aux matériaux ``VV_*`` existants
    dans ``bpy.data.materials``.

    NE CRÉE PAS les matériaux manquants : ne touche que ceux qui existent
    déjà. Les matériaux pas encore construits (build pas encore lancé)
    seront créés avec les bonnes couleurs au prochain build, puisque la
    palette en mémoire est à jour.
    """
    # Filtre sur DEFAULT_PALETTE : un fichier JSON utilisateur peut
    # contenir des entrées obsolètes (renommage d'un matériau dans une
    # version future de l'extension), on les ignore en silence.
    for name, rgb in palette_dict.items():
        if name not in DEFAULT_PALETTE:
            continue
        rgb = (float(rgb[0]), float(rgb[1]), float(rgb[2]))
        PALETTE[name] = rgb
        mat = bpy.data.materials.get(name)
        if mat is not None:
            _write_color(mat, rgb)


def snapshot_palette():
    """Capture la palette actuellement effective.

    Pour chaque matériau de ``DEFAULT_PALETTE`` :
        - s'il existe et a un node Emission identifiable → on lit la
          couleur réellement appliquée (ce que voit l'utilisateur) ;
        - sinon → on retombe sur la valeur de ``PALETTE`` en mémoire.

    Cette stratégie garantit qu'un Save juste après modification d'un
    matériau dans le Shader Editor capture bien la couleur visible."""
    snap = {}
    for name in DEFAULT_PALETTE:
        mat = bpy.data.materials.get(name)
        if mat is not None:
            color = _read_color(mat)
            if color is not None:
                snap[name] = color
                continue
        snap[name] = PALETTE.get(name, DEFAULT_PALETTE[name])
    return snap


def reset_to_default():
    """Restaure la palette par défaut et l'applique aux matériaux existants."""
    apply_palette(DEFAULT_PALETTE)
