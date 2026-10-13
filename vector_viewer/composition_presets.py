"""Bibliothèque de presets pour le panneau Composition (référentiels
non galiléens).

Deux niveaux : builtins livrés (lecture seule) et presets utilisateur
persistants (cf. ``preset_storage.PresetStore``).

Les flags d'affichage (les 13 cases à cocher show_OOp, show_OpM,
show_OM, …, show_Omega, show_R_frame, show_Rp_frame) ne sont PAS
modifiés par l'application d'un preset : ce sont des préférences
utilisateur qui persistent à travers les chargements.
"""

import bpy
from bpy.props import StringProperty

from . import preset_storage


# ----------------------------------------------------------------------------
# Définition des presets builtins
# ----------------------------------------------------------------------------
# Convention pour la rotation : Euler Z-Y-X intrinsèque.
#   « rotation autour de z » classique : ψ = ω·t, θ = φ = 0.
# ----------------------------------------------------------------------------

_PI = 3.141592653589793

PRESETS = {
    "TRANS_UNIFORME": {
        "label":       "Translation rectiligne uniforme",
        "tip":         "R' translaté à v=(1,0,0) dans R, sans rotation. "
                       "M fixe en r'=(0,1,0). Cas galiléen → tous les "
                       "a=0, Ω=0, v_a=v_e constante.",
        "Op":          ("t", "0", "0"),
        "euler":       ("0", "0", "0"),
        "rp":          ("0", "1", "0"),
        "duration":    4.0,
        "scale_v":     1.0,
        "scale_a":     1.0,
        "scale_omega": 1.0,
    },
    "TRANS_ACCEL": {
        "label":       "Translation uniformément accélérée",
        "tip":         "O' = (t²/2, 0, 0) : a_e = (1,0,0) constante, "
                       "Ω=0, a_c=0. M fixe dans R' donc a_r=0. "
                       "Apparition de la pseudo-force d'inertie.",
        "Op":          ("t**2/2", "0", "0"),
        "euler":       ("0", "0", "0"),
        "rp":          ("0", "1", "0"),
        "duration":    3.0,
        "scale_v":     1.0,
        "scale_a":     1.0,
        "scale_omega": 1.0,
    },
    "MANEGE_FIXE": {
        "label":       "Manège — point fixe sur la plateforme",
        "tip":         "Rotation pure autour de z (ψ=t), O' à l'origine, "
                       "M en (1,0,0) dans R'. v_r=a_r=0 (M fixe), v_e "
                       "tangente, a_e centripète, a_c=0.",
        "Op":          ("0", "0", "0"),
        "euler":       ("t", "0", "0"),
        "rp":          ("1", "0", "0"),
        "duration":    2 * _PI,
        "scale_v":     1.0,
        "scale_a":     1.0,
        "scale_omega": 1.0,
    },
    "CORIOLIS": {
        "label":       "Coriolis — trajectoire radiale sur disque tournant",
        "tip":         "ψ=t, M = (t, 0, 0) dans R' : déplacement radial "
                       "constant à vitesse 1 dans le repère tournant. "
                       "Cas d'école : a_c = 2 Ω × v_r non nul, "
                       "trajectoire en spirale dans R.",
        "Op":          ("0", "0", "0"),
        "euler":       ("t", "0", "0"),
        "rp":          ("t", "0", "0"),
        "duration":    2 * _PI,
        "scale_v":     1.0,
        "scale_a":     1.0,
        "scale_omega": 1.0,
    },
    "CABINE_ROUE": {
        "label":       "Cabine de grande roue (translation circulaire pure)",
        "tip":         "O' parcourt un cercle, mais R' ne tourne pas (tous "
                       "les angles à zéro). Ω=0, a_c=0, mais a_e ≠ 0 : "
                       "la rotation et l'accélération d'entraînement "
                       "sont indépendantes.",
        "Op":          ("cos(t)", "sin(t)", "0"),
        "euler":       ("0", "0", "0"),
        "rp":          ("0", "0", "0.4"),
        "duration":    2 * _PI,
        "scale_v":     1.0,
        "scale_a":     1.0,
        "scale_omega": 1.0,
    },
    "MANEGE_ASCEND": {
        "label":       "Manège tournant + montée verticale",
        "tip":         "Superposition d'une rotation autour de z (ψ=t) "
                       "et d'une translation verticale uniforme "
                       "(O'_z=t/3). M en (1,0,0) dans R'. Trajectoire "
                       "hélicoïdale dans R, Ω non nul mais constant.",
        "Op":          ("0", "0", "t/3"),
        "euler":       ("t", "0", "0"),
        "rp":          ("1", "0", "0"),
        "duration":    2 * _PI,
        "scale_v":     1.0,
        "scale_a":     1.0,
        "scale_omega": 1.0,
    },
    "PRECESSION": {
        "label":       "Précession (gyroscope)",
        "tip":         "Précession lente (ψ=0.3·t), nutation constante "
                       "(θ=π/6), spin rapide (φ=3·t). Ω(t) varie en "
                       "magnitude ET en direction. Cas riche pour "
                       "visualiser le pseudo-vecteur rotation.",
        "Op":          ("0", "0", "0"),
        "euler":       ("0.3*t", "pi/6", "3*t"),
        "rp":          ("1", "0", "0"),
        "duration":    2 * _PI,
        "scale_v":     1.0,
        "scale_a":     1.0,
        "scale_omega": 1.0,
    },
    "GALILEEN": {
        "label":       "Cas test : R' galiléen (R'=R)",
        "tip":         "O'=0, aucune rotation : R' coïncide avec R. "
                       "v_e=0, a_e=0, a_c=0, Ω=0. M en mouvement "
                       "circulaire dans R'. Vérification : v_a=v_r, "
                       "a_a=a_r (on retombe sur le viewer simple).",
        "Op":          ("0", "0", "0"),
        "euler":       ("0", "0", "0"),
        "rp":          ("cos(t)", "sin(t)", "0"),
        "duration":    2 * _PI,
        "scale_v":     1.0,
        "scale_a":     1.0,
        "scale_omega": 1.0,
    },

    # ── Manèges spéciaux ────────────────────────────────────────────
    "MANEGE_ACCEL": {
        "label":       "Manège uniformément accéléré",
        "tip":         "ψ(t) = t²/4 → Ω(t) = (0,0,t/2) croît linéairement, "
                       "et dΩ/dt non nulle fait apparaître une composante "
                       "tangentielle de a_e. M fixe en r'=(1,0,0).",
        "Op":          ("0", "0", "0"),
        "euler":       ("t**2/4", "0", "0"),
        "rp":          ("1", "0", "0"),
        "duration":    2 * _PI,
        "scale_v":     1.0,
        "scale_a":     1.0,
        "scale_omega": 1.0,
    },
    "RESSORT_TOURNANT": {
        "label":       "Masse oscillant radialement sur disque tournant",
        "tip":         "ψ(t) = t (Ω constant), M oscille dans R' selon "
                       "r' = (1 + 0.5·cos(2t), 0, 0). v_r non nulle, "
                       "v_e ≠ 0, et a_c = 2 Ω × v_r oscille en signe.",
        "Op":          ("0", "0", "0"),
        "euler":       ("t", "0", "0"),
        "rp":          ("1 + 0.5*cos(2*t)", "0", "0"),
        "duration":    2 * _PI,
        "scale_v":     1.0,
        "scale_a":     1.0,
        "scale_omega": 1.0,
    },

    # ── Référentiels physiques classiques ───────────────────────────
    "PROJECTILE_TERRE": {
        "label":       "Projectile vu de la Terre tournante",
        "tip":         "Référentiel terrestre simplifié : Ω lente autour "
                       "de z (ψ = 0.3·t), M en chute libre dans R "
                       "(z' = 2t - t²/2). Coriolis dévie le projectile "
                       "vers l'est.",
        "Op":          ("0", "0", "0"),
        "euler":       ("0.3*t", "0", "0"),
        "rp":          ("0", "0", "2*t - t**2/2"),
        "duration":    4.0,
        "scale_v":     1.0,
        "scale_a":     1.0,
        "scale_omega": 1.0,
    },
    "FOUCAULT_PARIS": {
        "label":       "Pendule de Foucault (Paris, φ=48.85°)",
        "tip":         "Pendule de Foucault à la latitude de Paris "
                       "(48.85°). Le plan d'oscillation précesse à la "
                       "vitesse Ω_z = sin(φ) ≈ 0.753 rad/s — un tour "
                       "complet en 2π/sin(φ) ≈ 8.34 s, soit ~8.3 "
                       "oscillations du pendule (T = 1 s). "
                       "Pour régler la latitude, utiliser le bouton "
                       "« Recalculer pour cette latitude » ci-dessous.",
        # ψ = sin(φ_Paris)·t  →  rotation autour de l'axe vertical local.
        # Modèle simplifié (latitude polaire effective) : on néglige les
        # composantes horizontales de Ω_T qui n'agissent pas sur le plan
        # d'oscillation à l'ordre dominant. C'est l'approximation
        # standard du pendule de Foucault.
        "Op":          ("0", "0", "0"),
        "euler":       ("0.752989*t", "0", "0"),
        "rp":          ("cos(2*pi*t)", "0", "0"),
        # Durée = 2 tours complets de précession à φ Paris : suffisamment
        # long pour voir clairement la rosace se former.
        "duration":    2 * 2 * _PI / 0.752989,
        "scale_v":     1.0,
        "scale_a":     1.0,
        "scale_omega": 1.0,
    },
    "CHUTE_LIBRE_TOURNANT": {
        "label":       "Repère en chute libre tournant",
        "tip":         "O' = (0, 0, -t²/2) en chute libre + ψ = t. "
                       "M fixe en R' à (0,1,0). Combine pseudo-gravité "
                       "(a_e selon -z dans le repère propre) et Coriolis "
                       "(a_c = 2 Ω × v_r ≠ 0 si M bouge).",
        "Op":          ("0", "0", "-t**2/2"),
        "euler":       ("t", "0", "0"),
        "rp":          ("0", "1", "0"),
        "duration":    2 * _PI,
        "scale_v":     1.0,
        "scale_a":     1.0,
        "scale_omega": 1.0,
    },
    "ROUE_QUI_ROULE": {
        "label":       "Roue qui roule sans glisser (cycloïde)",
        "tip":         "Centre de roue à (t, 0, 1), rotation θ = -t autour "
                       "de y, M au sommet de la roue r' = (0,0,1). "
                       "Trajectoire dans R = cycloïde classique. "
                       "v=0 au point de contact (rebroussement).",
        "Op":          ("t", "0", "1"),
        "euler":       ("0", "-t", "0"),
        "rp":          ("0", "0", "1"),
        "duration":    4 * _PI,
        "scale_v":     1.0,
        "scale_a":     1.0,
        "scale_omega": 1.0,
    },
}


# Ordre d'affichage : organisé par famille pédagogique.
# Du plus simple (galiléen, translations pures) au plus chargé (référentiels
# physiques avec Coriolis, gyroscope).
PRESET_ORDER = (
    # Cas dégénérés / translations sans rotation
    "GALILEEN", "TRANS_UNIFORME", "TRANS_ACCEL", "CABINE_ROUE",
    # Manèges (rotation pure ou avec translation simple)
    "MANEGE_FIXE", "MANEGE_ACCEL", "MANEGE_ASCEND",
    # Coriolis : disque tournant, ressort, Foucault
    "CORIOLIS", "RESSORT_TOURNANT", "FOUCAULT_PARIS",
    # Référentiels physiques
    "PROJECTILE_TERRE", "CHUTE_LIBRE_TOURNANT", "ROUE_QUI_ROULE",
    # Gyroscope (cas le plus riche)
    "PRECESSION",
)


# ----------------------------------------------------------------------------
# Champs cinématiques (sans label/tip) : pour snapshot et apply
# ----------------------------------------------------------------------------

def _apply_fields(props, p: dict):
    """Recopie les champs d'un preset sur les props du panneau Composition."""
    props.X0_expr,    props.Y0_expr,    props.Z0_expr    = p["Op"]
    props.psi_expr,   props.theta_expr, props.phi_expr   = p["euler"]
    props.xp_expr,    props.yp_expr,    props.zp_expr    = p["rp"]
    props.t_duration  = float(p["duration"])
    props.scale_v     = float(p["scale_v"])
    props.scale_a     = float(p["scale_a"])
    props.scale_omega = float(p["scale_omega"])


def _snapshot_fields(props) -> dict:
    """Capture les champs cinématiques courants pour enregistrement.

    Note : tuples convertis en listes pour rester JSON-friendly."""
    return {
        "Op":          [props.X0_expr,  props.Y0_expr,  props.Z0_expr],
        "euler":       [props.psi_expr, props.theta_expr, props.phi_expr],
        "rp":          [props.xp_expr,  props.yp_expr,  props.zp_expr],
        "duration":    float(props.t_duration),
        "scale_v":     float(props.scale_v),
        "scale_a":     float(props.scale_a),
        "scale_omega": float(props.scale_omega),
    }


# ----------------------------------------------------------------------------
# Store
# ----------------------------------------------------------------------------

STORE = preset_storage.PresetStore(
    builtin=PRESETS,
    builtin_order=PRESET_ORDER,
    filename="vector_viewer_comp_presets.json",
    fields_apply=_apply_fields,
    fields_snapshot=_snapshot_fields,
)


def enum_items_callback(self, context):
    """Callback pour ``EnumProperty.items`` du panneau Composition."""
    return STORE.enum_items()


# ----------------------------------------------------------------------------
# Opérateurs
# ----------------------------------------------------------------------------

class VECTORCOMP_OT_apply_preset(bpy.types.Operator):
    """Applique le preset sélectionné dans le menu et reconstruit
    immédiatement la visualisation de composition."""

    bl_idname = "vector_comp.apply_preset"
    bl_label = "Appliquer le preset"
    bl_description = (
        "Recopie O'(t), les angles d'Euler, r'(t), la durée et les "
        "échelles du preset sélectionné, puis reconstruit la "
        "visualisation de composition"
    )
    bl_options = {'REGISTER', 'UNDO'}

    preset_id: StringProperty(
        name="Preset",
        description="Identifiant du preset à appliquer",
        default="",
    )

    def execute(self, context):
        props = context.scene.vector_comp

        pid = self.preset_id or props.preset_choice
        if not pid:
            self.report({'WARNING'}, "Aucun preset sélectionné.")
            return {'CANCELLED'}

        try:
            STORE.apply_to(props, pid)
        except KeyError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        if props.preset_choice != pid:
            props.preset_choice = pid

        result = bpy.ops.vector_comp.build()
        if 'CANCELLED' in result:
            return {'CANCELLED'}

        self.report({'INFO'}, f"Preset « {STORE.label(pid)} » appliqué.")
        return {'FINISHED'}


class VECTORCOMP_OT_apply_foucault(bpy.types.Operator):
    """Régénère les expressions du pendule de Foucault à partir de la
    latitude saisie dans le panneau, puis reconstruit la visualisation.

    Modèle :
        ψ(t) = sin(φ)·t      (rotation autour de l'axe vertical local)
        θ(t) = φ(t) = 0
        r'(t) = (cos(2π·t), 0, 0)   (oscillation horizontale, T = 1 s)

    À latitude φ, la précession du plan d'oscillation a une période de
    2π/sin(φ) secondes (en temps simulé). À l'équateur (φ = 0), il n'y
    a pas de précession ; au pôle (φ = ±90°), un cycle complet par
    2π secondes (~6.28 s).

    L'opérateur écrit les expressions dans ``props.psi_expr``,
    ``props.xp_expr``, ``props.t_duration``, etc., puis chaîne sur Build.
    """

    bl_idname = "vector_comp.apply_foucault"
    bl_label = "Recalculer pour cette latitude"
    bl_description = (
        "Régénère les expressions du pendule de Foucault à partir de la "
        "latitude saisie ci-dessus, puis reconstruit la visualisation"
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import math
        props = context.scene.vector_comp

        phi_deg = float(props.latitude_deg)
        phi_rad = math.radians(phi_deg)
        sin_phi = math.sin(phi_rad)

        # Cas dégénéré : à l'équateur (sin(φ) = 0), pas de précession,
        # le pendule oscille en ligne droite. La durée par défaut perd
        # son sens (division par zéro), on tombe sur 4·T_pendule.
        if abs(sin_phi) < 1e-6:
            duration = 4.0  # 4 oscillations du pendule
            psi_expr = "0"
            self.report(
                {'INFO'},
                f"Latitude {phi_deg:.2f}° ≈ équateur : pas de précession "
                f"(le pendule oscille en ligne droite)."
            )
        else:
            # 2 tours complets de précession pour bien voir la rosace.
            # Plafonné à 60s (≈60 oscillations du pendule) pour éviter
            # une animation interminable près de l'équateur.
            duration = min(60.0, 2.0 * 2.0 * math.pi / abs(sin_phi))
            # Note : on garde le signe — sin(φ) < 0 dans l'hémisphère sud
            # → précession dans le sens opposé, ce qui est physiquement
            # correct.
            psi_expr = f"{sin_phi:.6f}*t"

        # Chargement des champs cinématiques
        props.X0_expr = "0"
        props.Y0_expr = "0"
        props.Z0_expr = "0"
        props.psi_expr   = psi_expr
        props.theta_expr = "0"
        props.phi_expr   = "0"
        props.xp_expr = "cos(2*pi*t)"
        props.yp_expr = "0"
        props.zp_expr = "0"
        props.t_duration = duration
        # Échelles unitaires (cohérentes avec les autres presets)
        props.scale_v     = 1.0
        props.scale_a     = 1.0
        props.scale_omega = 1.0

        # Aligne le sélecteur de preset sur Foucault Paris (ou laisse
        # tel quel si autre preset Foucault était sélectionné).
        if not props.preset_choice.startswith("FOUCAULT"):
            try:
                props.preset_choice = "FOUCAULT_PARIS"
            except TypeError:
                pass  # Enum item peut ne pas exister selon la config

        # Chaîne sur Build pour reconstruire la visualisation
        result = bpy.ops.vector_comp.build()
        if 'CANCELLED' in result:
            return {'CANCELLED'}

        if abs(sin_phi) >= 1e-6:
            T_prec = 2.0 * math.pi / abs(sin_phi)
            self.report(
                {'INFO'},
                f"Foucault à φ = {phi_deg:.2f}° : "
                f"sin(φ) = {sin_phi:.4f}, "
                f"période de précession = {T_prec:.2f} s "
                f"(~{T_prec / 1.0:.1f} oscillations du pendule)."
            )
        return {'FINISHED'}


class VECTORCOMP_OT_save_user_preset(bpy.types.Operator):
    """Enregistre la configuration cinématique courante du panneau
    Composition comme preset utilisateur, persistant à travers les
    sessions."""

    bl_idname = "vector_comp.save_user_preset"
    bl_label = "Enregistrer comme preset"
    bl_description = (
        "Capture O'(t), les angles d'Euler, r'(t), la durée et les "
        "échelles courantes et les enregistre comme preset utilisateur"
    )
    bl_options = {'REGISTER'}

    label: StringProperty(
        name="Nom",
        description="Nom du preset tel qu'il apparaîtra dans le menu",
        default="Ma composition",
    )
    tip: StringProperty(
        name="Description",
        description="Description courte (facultative) — affichée en tooltip",
        default="",
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "label")
        layout.prop(self, "tip")
        layout.label(
            text="Enregistré dans le config utilisateur de Blender.",
            icon='INFO',
        )

    def execute(self, context):
        props = context.scene.vector_comp
        try:
            new_pid = STORE.save_user(self.label, self.tip, props)
        except (ValueError, OSError) as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        props.preset_choice = new_pid

        self.report(
            {'INFO'},
            f"Preset « {self.label} » enregistré (id : {new_pid})."
        )
        return {'FINISHED'}


class VECTORCOMP_OT_update_user_preset(bpy.types.Operator):
    """Met à jour le preset utilisateur courant avec la configuration
    cinématique actuelle. Le nom et la description sont préservés."""

    bl_idname = "vector_comp.update_user_preset"
    bl_label = "Mettre à jour ce preset"
    bl_description = (
        "Réécrit le preset utilisateur sélectionné avec O'(t), les "
        "angles d'Euler, r'(t), la durée et les échelles actuels "
        "(le nom et la description sont préservés)"
    )
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        sc = getattr(context, "scene", None)
        if sc is None:
            return False
        props = getattr(sc, "vector_comp", None)
        if props is None:
            return False
        return STORE.is_user(props.preset_choice)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        props = context.scene.vector_comp
        pid = props.preset_choice
        label = STORE.label(pid)
        try:
            ok = STORE.update_user(pid, props)
        except OSError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        if not ok:
            self.report({'ERROR'},
                        "Mise à jour impossible (preset inconnu ou builtin).")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Preset « {label} » mis à jour.")
        return {'FINISHED'}


class VECTORCOMP_OT_delete_user_preset(bpy.types.Operator):
    """Supprime le preset utilisateur actuellement sélectionné. Les
    presets builtins ne sont pas supprimables."""

    bl_idname = "vector_comp.delete_user_preset"
    bl_label = "Supprimer ce preset"
    bl_description = (
        "Supprime définitivement le preset utilisateur sélectionné "
        "(les builtins sont protégés)"
    )
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        sc = getattr(context, "scene", None)
        if sc is None:
            return False
        props = getattr(sc, "vector_comp", None)
        if props is None:
            return False
        return STORE.is_user(props.preset_choice)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        props = context.scene.vector_comp
        pid = props.preset_choice
        label = STORE.label(pid)

        if not STORE.delete_user(pid):
            self.report({'ERROR'}, "Suppression impossible "
                                   "(preset builtin ou échec d'écriture).")
            return {'CANCELLED'}

        props.preset_choice = STORE.builtin_order[0]

        self.report({'INFO'}, f"Preset « {label} » supprimé.")
        return {'FINISHED'}


class VECTORCOMP_OT_refresh_user_presets(bpy.types.Operator):
    """Recharge le fichier JSON des presets utilisateur depuis le disque
    (utile après une édition manuelle)."""

    bl_idname = "vector_comp.refresh_user_presets"
    bl_label = "Rafraîchir depuis le disque"
    bl_description = (
        "Recharge la bibliothèque des presets utilisateur depuis le "
        "fichier JSON (utile après une édition manuelle)"
    )
    bl_options = {'REGISTER'}

    def execute(self, context):
        STORE.invalidate()
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        n = len(STORE.get_user())
        self.report({'INFO'}, f"Presets utilisateur rechargés ({n}).")
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────
# Export / Import
# ─────────────────────────────────────────────────────────────────────

def _refresh_panel_after_import(context):
    STORE.invalidate()
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


VECTORCOMP_OT_export_user_presets = preset_storage.make_export_operator(
    idname="vector_comp.export_user_presets",
    label="Exporter mes presets",
    description=(
        "Exporte la bibliothèque de presets utilisateur courante du "
        "panneau Composition vers un fichier JSON partageable"
    ),
    store_attr="composition_presets:STORE",
    default_filename="vector_viewer_composition_presets.json",
)


VECTORCOMP_OT_import_user_presets = preset_storage.make_import_operator(
    idname="vector_comp.import_user_presets",
    label="Importer des presets",
    description=(
        "Importe une bibliothèque de presets de composition depuis un "
        "fichier JSON, en fusionnant avec les presets utilisateur existants"
    ),
    store_attr="composition_presets:STORE",
    refresh_callback=_refresh_panel_after_import,
)
