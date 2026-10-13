"""
Lightweight French ⇄ English UI switching for RealFnViewer.

Why not ``bpy.app.translations``? Blender's i18n machinery keys off
the *application* locale and the global "Translate Interface"
checkbox — it cannot give one add-on its own language toggle, which
is what we want (a bilingual teacher switching languages per class,
without touching Blender's own language).

Design
------
* The UI source strings are **French** (the add-on's native tongue).
  :data:`_CATALOG` maps them to English. :func:`tr` is identity in
  French mode and a catalogue lookup in English mode — an unmapped
  string just stays French, so a missing entry degrades gracefully
  instead of crashing or blanking a button.

* The language is stored in the add-on **preferences**
  (``AddonPreferences.language``) so it persists across sessions with
  Blender's own preference saving.

* Strings drawn each frame (panel ``text=...``) translate live.
  Strings baked into *classes* (``bl_label``, dialog property names,
  enum item labels) only exist at registration time — so
  :func:`apply_language` re-registers every operator and panel class
  after swapping those attributes. Originals are stashed on first use
  so the toggle is loss-free in both directions, and property
  keywords are mutated through the ``_PropertyDeferred.keywords``
  dict, which Blender reads at ``register_class`` time.

Socket *descriptions* (tooltips) are baked onto each node tree at build
time, but :func:`panel.localize_socket_tooltips` rewrites them in the
active language — at object creation and again on every toggle (see the
re-localisation pass in :func:`apply_language`). So labels, panels,
dialogs *and* socket tooltips all follow the language switch.
"""

from __future__ import annotations

import bpy


# --------------------------------------------------------------------------
# Language state
# --------------------------------------------------------------------------
_PKG = __package__


def get_lang() -> str:
    """Current UI language: ``"FR"`` (default) or ``"EN"``."""
    try:
        prefs = bpy.context.preferences.addons[_PKG].preferences
        return getattr(prefs, "language", "FR")
    except (KeyError, AttributeError):
        return "FR"


def tr(s: str) -> str:
    """Translate a French UI string to the active language."""
    if get_lang() == "EN":
        return _CATALOG.get(s, s)
    return s


# --------------------------------------------------------------------------
# Class re-registration (bl_label, dialog properties, enum items)
# --------------------------------------------------------------------------
_LABEL_STASH: dict = {}      # cls -> original French bl_label
_PROP_STASH: dict = {}       # (cls qualname, prop) -> (fr name, fr desc, fr items)


def _translate_items(items, lang):
    out = []
    for it in items:
        it = list(it)
        if len(it) >= 2 and isinstance(it[1], str):
            it[1] = tr(it[1]) if lang == "EN" else it[1]
        if len(it) >= 3 and isinstance(it[2], str):
            it[2] = tr(it[2]) if lang == "EN" else it[2]
        out.append(tuple(it))
    return out


def apply_language(operators_mod, panel_mod):
    """Relabel and re-register all operator + panel classes for the
    current language. Safe to call repeatedly; originals are stashed
    on first call so FR → EN → FR round-trips exactly.

    Every class is processed in isolation: one failing class can no
    longer abort the loop and leave the UI half-relabelled (or half-
    unregistered). A summary line is always printed so the mechanism
    is verifiable from the console."""
    global _APPLIED_LANG
    lang = get_lang()
    all_classes = list(operators_mod.classes) + list(panel_mod.classes)
    errors = []

    for cls in reversed(all_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    n_ok = 0
    for cls in all_classes:
        try:
            # bl_label
            if cls not in _LABEL_STASH:
                _LABEL_STASH[cls] = getattr(cls, "bl_label", "")
            fr_label = _LABEL_STASH[cls]
            cls.bl_label = tr(fr_label) if lang == "EN" else fr_label

            # Dialog properties: name / description / enum items live
            # in the _PropertyDeferred keywords dict until
            # register_class.
            for pname, pdef in list(getattr(cls, "__annotations__",
                                            {}).items()):
                kw = getattr(pdef, "keywords", None)
                if not isinstance(kw, dict):
                    continue
                key = (cls.__qualname__, pname)
                if key not in _PROP_STASH:
                    _PROP_STASH[key] = (kw.get("name"),
                                        kw.get("description"),
                                        kw.get("items"))
                fr_name, fr_desc, fr_items = _PROP_STASH[key]
                if isinstance(fr_name, str):
                    kw["name"] = tr(fr_name) if lang == "EN" else fr_name
                if isinstance(fr_desc, str):
                    kw["description"] = (tr(fr_desc) if lang == "EN"
                                         else fr_desc)
                if isinstance(fr_items, (list, tuple)):
                    kw["items"] = (_translate_items(fr_items, lang)
                                   if lang == "EN" else fr_items)
        except Exception as exc:
            errors.append(f"{cls.__name__}/relabel: {exc}")

        try:
            bpy.utils.register_class(cls)
            n_ok += 1
        except Exception as exc:
            # Last-resort: try to register untouched so the UI never
            # loses a panel/operator because of a translation issue.
            errors.append(f"{cls.__name__}/register: {exc}")
            try:
                bpy.utils.register_class(cls)
            except Exception:
                pass

    _APPLIED_LANG = lang
    print(f"[RealFn] i18n: langue={lang}, {n_ok}/{len(all_classes)} "
          f"classes ré-enregistrées"
          + (f", erreurs: {errors}" if errors else ""))

    # Re-localise socket tooltips on every existing RealFn node group so
    # hover descriptions follow the toggle (not just panel labels). The
    # node groups are identified by the ``realfn_kind`` stash. Wrapped
    # broadly: a tooltip refresh must never break the language switch.
    try:
        import bpy as _bpy
        n_tt = 0
        for ng in _bpy.data.node_groups:
            if "realfn_kind" in ng:
                panel_mod.localize_socket_tooltips(ng)
                n_tt += 1
        if n_tt:
            print(f"[RealFn] i18n: tooltips re-localisés sur {n_tt} "
                  f"arbre(s) RealFn")
    except Exception as exc:
        print(f"[RealFn] i18n: re-localisation tooltips ignorée : {exc}")

    # Repaint every UI area so the new labels show immediately.
    try:
        for wm_win in bpy.context.window_manager.windows:
            for area in wm_win.screen.areas:
                area.tag_redraw()
    except (AttributeError, RuntimeError):
        pass


# Language whose labels are currently baked into the registered
# classes. Compared against get_lang() by the main panel's draw as a
# self-healing check: if a scheduled relabel was lost (add-on reload,
# missed timer…), the next redraw reschedules it.
_APPLIED_LANG = "FR"


def schedule_apply_language():
    """Deferred relabel — used by the toggle operator so the running
    operator's own class isn't re-registered mid-execute."""
    from . import operators, panel

    def _go():
        apply_language(operators, panel)
        return None  # one-shot timer
    bpy.app.timers.register(_go, first_interval=0.0)


# --------------------------------------------------------------------------
# Catalogue — French source → English
# --------------------------------------------------------------------------
_CATALOG = {
    # ---- Main panel & creation buttons --------------------------------
    "RealFn Viewer": "RealFn Viewer",
    "y = f(x) avec tangente animée": "y = f(x) with animated tangent",
    # Collapsible creation group headers + active-object display section
    "Courbes": "Curves",
    "Surfaces": "Surfaces",
    "Champs 3D": "3D fields",
    "Affichage & animation": "Display & animation",
    "dérivées :": "derivatives:",
    "Taylor :": "Taylor:",
    "Créer une courbe…": "Create a curve…",
    "Créer une courbe y = f(x)": "Create a curve y = f(x)",
    "Créer une courbe vectorielle F(t)…": "Create a vector curve F(t)…",
    "Créer une surface z = f(x, y)…": "Create a surface z = f(x, y)…",
    "Créer une surface paramétrée…": "Create a parametric surface…",
    "Créer un champ scalaire ƒ(x, y, z)…": "Create a scalar field ƒ(x, y, z)…",
    "Créer un champ de vecteurs V(x, y, z)…":
        "Create a vector field V(x, y, z)…",
    "Fonction active :": "Active function:",
    "Modifier la fonction": "Edit the function",
    "Modifier la formule / les ordres": "Edit the formula / orders",
    "Copier la formule": "Copy the formula",
    "Copier le polynôme de Taylor": "Copy the Taylor polynomial",
    "Polynôme de Taylor complet": "Full Taylor polynomial",

    # ---- Parameter panels ----------------------------------------------
    "Paramètres du modifier": "Modifier parameters",
    "Paramètres du modifier (vectoriel)": "Modifier parameters (vector)",
    "Paramètres du modifier (surface)": "Modifier parameters (surface)",
    "Paramètres du modifier (surface paramétrée)":
        "Modifier parameters (parametric surface)",
    "Paramètres du modifier (champ scalaire 3D)":
        "Modifier parameters (3D scalar field)",
    "Paramètres du modifier (champ de vecteurs 3D)":
        "Modifier parameters (3D vector field)",

    # ---- Sections (collapsible) ----------------------------------------
    "Domaine & grille": "Domain & grid",
    "Domaine & échantillonnage": "Domain & sampling",
    "Point x₀ & marqueur": "Point x₀ & marker",
    "Courbe f et dérivées": "Curve f and derivatives",
    "Polynômes de Taylor": "Taylor polynomials",
    "Point t₀": "Point t₀",
    "Trajectoire": "Trajectory",
    "Vecteurs cinématiques": "Kinematic vectors",
    "Surface": "Surface",
    "Point d'ancrage & plan tangent": "Basepoint & tangent plane",
    "Surface de Taylor": "Taylor surface",
    "Polynôme de Taylor, ordre": "Taylor polynomial, order",
    "Sphères & couleurs": "Spheres & colours",
    "Étiquettes numériques": "Numeric labels",
    "Cadre & axes gradués": "Frame & graduated axes",
    "Point d'ancrage": "Basepoint",
    "Flèches du champ": "Field arrows",
    "Étiquettes de norme": "Norm labels",
    "Paramètres libres": "Free parameters",

    # ---- Socket labels (French display names) ---------------------------
    "Résolution": "Resolution",
    "Taille des étiquettes": "Label size",
    "Décalage des étiquettes": "Label offset",
    "Matériau des étiquettes": "Label material",
    "Afficher les étiquettes numériques": "Show numeric labels",
    "Pas d'affichage des étiquettes": "Label stride",
    "Afficher les normes ‖V‖": "Show ‖V‖ norms",
    "Pas d'affichage des normes": "Norm label stride",
    "Taille des étiquettes de norme": "Norm label size",
    "Décalage des étiquettes de norme": "Norm label offset",
    "Matériau des étiquettes de norme": "Norm label material",
    "Décimales des étiquettes": "Label decimals",
    "Étiquettes verticales (face à la vue)": "Vertical labels (face view)",
    "Décimales des étiquettes de norme": "Norm label decimals",
    "Étiquettes de norme verticales": "Vertical norm labels",
    "Seuil de points (étiquettes)": "Point limit (labels)",
    "Seuil de points (normes)": "Point limit (norms)",
    "Afficher le cadre du domaine": "Show domain frame",
    "Épaisseur du cadre": "Frame thickness",
    "Matériau du cadre": "Frame material",
    "Afficher les axes gradués": "Show graduated axes",
    "Taille des graduations": "Graduation size",
    "Décimales des graduations": "Graduation decimals",
    "Matériau des graduations": "Graduation material",

    # ---- Presets panels --------------------------------------------------
    "Presets": "Presets",
    "Presets vectoriels": "Vector presets",
    "Presets surface": "Surface presets",
    "Presets surface paramétrée": "Parametric surface presets",
    "Presets champ scalaire 3D": "3D scalar field presets",
    "Presets champ de vecteurs 3D": "3D vector field presets",
    "Aucun preset enregistré": "No saved preset",
    "Aucun preset utilisateur": "No user preset",
    "Aucun preset vectoriel enregistré": "No saved vector preset",
    "Aucun preset surface enregistré": "No saved surface preset",
    "Aucun preset surface paramétrée enregistré":
        "No saved parametric surface preset",
    "Cliquer ↻ pour installer les fonctions classiques":
        "Click ↻ to install the classic functions",
    "Cliquez « Enregistrer… » ou « Réinstaller… »":
        "Click “Save…” or “Reinstall…”",
    "Cliquez « Enregistrer… » pour démarrer": "Click “Save…” to start",
    "Enregistrer…": "Save…",
    "Importer…": "Import…",
    "Réinstaller les presets intégrés": "Reinstall built-in presets",
    "Appliquer le preset": "Apply preset",
    "Appliquer le preset vectoriel": "Apply vector preset",
    "Appliquer le preset surface": "Apply surface preset",
    "Appliquer le preset champ scalaire 3D": "Apply 3D scalar field preset",
    "Appliquer le preset champ de vecteurs 3D":
        "Apply 3D vector field preset",
    "Supprimer le preset": "Delete preset",
    "Supprimer le preset vectoriel": "Delete vector preset",
    "Supprimer le preset surface": "Delete surface preset",
    "Enregistrer comme preset…": "Save as preset…",
    "Enregistrer comme preset vectoriel…": "Save as vector preset…",
    "Enregistrer comme preset surface…": "Save as surface preset…",
    "Enregistrer comme preset surface paramétrée…":
        "Save as parametric surface preset…",
    "Enregistrer comme preset champ scalaire 3D…":
        "Save as 3D scalar field preset…",
    "Enregistrer comme preset champ de vecteurs 3D…":
        "Save as 3D vector field preset…",
    "Exporter le preset…": "Export preset…",
    "Exporter le preset vectoriel…": "Export vector preset…",
    "Exporter le preset surface…": "Export surface preset…",
    "Importer un preset…": "Import a preset…",
    "Importer un preset vectoriel…": "Import a vector preset…",
    "Importer un preset surface…": "Import a surface preset…",
    "Importer un preset surface paramétrée…":
        "Import a parametric surface preset…",
    "Importer un preset champ scalaire 3D…":
        "Import a 3D scalar field preset…",
    "Importer un preset champ de vecteurs 3D…":
        "Import a 3D vector field preset…",
    "Réinstaller les presets builtin": "Reinstall built-in presets",
    "Réinstaller les presets vectoriels intégrés":
        "Reinstall built-in vector presets",
    "Réinstaller les presets surface intégrés":
        "Reinstall built-in surface presets",
    "Réinstaller les presets surfaces paramétrées intégrés":
        "Reinstall built-in parametric surface presets",
    "Réinstaller les presets champ scalaire 3D intégrés":
        "Reinstall built-in 3D scalar field presets",
    "Réinstaller les presets champ de vecteurs 3D intégrés":
        "Reinstall built-in 3D vector field presets",

    # ---- Curve display / misc -------------------------------------------
    "Affichage des courbes :": "Curve display:",
    "Tout afficher": "Show all",
    "Tout cacher": "Hide all",
    "Inverser": "Invert",
    "Matériaux :": "Materials:",
    "Installer la palette": "Install the palette",
    "Installer la palette de matériaux": "Install the material palette",
    "Code couleur cinématique": "Kinematic colour code",
    "Appliquer le code couleur cinématique":
        "Apply the kinematic colour code",
    "Snapshot mémorisé :": "Stored snapshot:",
    "Restaurer le snapshot": "Restore snapshot",
    "Restaurer le snapshot stocké": "Restore the stored snapshot",
    "Animer le point de base": "Animate the basepoint",
    "Effacer l'animation du point de base": "Clear basepoint animation",
    "(composantes indisponibles)": "(components unavailable)",
    "Fonction active :": "Active function:",
    "Divergence ∇·V :": "Divergence ∇·V:",
    "Rotationnel ∇×V :": "Curl ∇×V:",

    # ---- Dialog property names ------------------------------------------
    "Nom du preset": "Preset name",
    "Nom du preset à exporter": "Name of the preset to export",
    "Nom du preset à supprimer": "Name of the preset to delete",
    "Nom du preset vectoriel à exporter":
        "Name of the vector preset to export",
    "Nom du preset vectoriel à supprimer":
        "Name of the vector preset to delete",
    "Chemin du preset": "Preset path",
    "Écraser si existe": "Overwrite if exists",
    "Label de la courbe": "Curve label",
    "Ordre max des dérivées": "Max derivative order",
    "Ordre max des polynômes de Taylor": "Max Taylor polynomial order",
    "Paramètres libres": "Free parameters",
    "Mode": "Mode",
    "Champ explicite V(x,y,z)": "Explicit field V(x,y,z)",
    "Gradient d'un potentiel ϕ(x,y,z)": "Gradient of a potential ϕ(x,y,z)",
    "Saisir directement les 3 composantes V_x, V_y, V_z":
        "Enter the 3 components V_x, V_y, V_z directly",
    "Saisir un potentiel scalaire ; V = ∇ϕ est calculé "
    "symboliquement (champ conservatif)":
        "Enter a scalar potential; V = ∇ϕ is computed "
        "symbolically (conservative field)",

    # ---- Language toggle --------------------------------------------------
    "Langue / Language": "Langue / Language",
    "Basculer français / anglais": "Switch French / English",
    "Interface en anglais": "Interface in English",
    "Interface en français": "Interface in French",
    # ---- Dialog draw() strings (operators.py) ----------------------------
    "Composantes V :": "Components V:",
    "Composantes détectées :": "Detected components:",
    "F(t) en syntaxe sympy.physics.vector :":
        "F(t) in sympy.physics.vector syntax:",
    "Polynômes de Taylor centrés en x₀ (scrubbable)":
        "Taylor polynomials centred at x₀ (scrubbable)",
    "Potentiel scalaire :": "Scalar potential:",
    "→ ajoutez à 'Paramètres libres'": "→ add to 'Free parameters'",
    "Paramètres détectés : ": "Detected parameters: ",
    "courbe(s) tracée(s)": "curve(s) traced",
    "Symboles non autorisés : ": "Disallowed symbols: ",
    "Non déclarés : ": "Undeclared: ",
    "Paramètres : ": "Parameters: ",
    # ---- WindowManager / Scene display props -----------------------------
    "Format LaTeX": "LaTeX format",
    "Synchroniser x₀": "Sync x₀",
    # ---- Preset panel headers (f-string prefixes) ------------------------
    "Catalogue builtin": "Built-in catalogue",
    "Mes presets": "My presets",
    "Erreur dossier : ": "Folder error: ",
    "Sauvegardé le : ": "Saved on: ",
    "preset(s) :": "preset(s):",
}


