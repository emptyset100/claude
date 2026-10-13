"""Bibliothèque de presets de palette pour les matériaux RealFn.

Chaque preset est un dictionnaire ``{nom_court: (R, G, B)}`` pour les
8 couleurs de base de la palette. Les entrées XPBR ne sont pas
modifiées par les presets (leurs teintes ont une signification fixe).

Les presets builtins couvrent les contextes pédagogiques courants :
    - Défaut    : palette livrée avec l'extension
    - Vif       : couleurs saturées, fond sombre
    - Pastel    : couleurs douces, fond clair / présentation
    - Daltonien : palette compatible deutéranopie/protanopie (Wong 2011)
    - Monochrome: nuances de gris pour publication N&B

Les presets utilisateur sont enregistrés dans::

    ~/.config/blender/<ver>/config/realfn_viewer/materials_presets.json

et persistent à travers les sessions et les .blend.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata

import bpy
from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator, PropertyGroup

from . import default_materials


# ---------------------------------------------------------------------------
# Palettes builtins
# ---------------------------------------------------------------------------

def _palette_default() -> dict:
    return {k: v for k, v in default_materials.DEFAULT_PALETTE.items()
            if not k.startswith("XPBR")}


def _palette_vif() -> dict:
    return {
        "Bleu":    (0.10, 0.50, 1.00),
        "Vert":    (0.20, 1.00, 0.20),
        "Rouge":   (1.00, 0.10, 0.10),
        "Gris":    (0.55, 0.55, 0.55),
        "Jaune":   (1.00, 0.90, 0.00),
        "Magenta": (1.00, 0.00, 0.70),
        "Cyan":    (0.00, 0.95, 1.00),
        "Orange":  (1.00, 0.55, 0.00),
    }


def _palette_pastel() -> dict:
    return {
        "Bleu":    (0.55, 0.72, 0.95),
        "Vert":    (0.55, 0.87, 0.60),
        "Rouge":   (0.95, 0.60, 0.55),
        "Gris":    (0.72, 0.72, 0.72),
        "Jaune":   (0.98, 0.92, 0.55),
        "Magenta": (0.92, 0.60, 0.88),
        "Cyan":    (0.60, 0.90, 0.95),
        "Orange":  (0.98, 0.80, 0.55),
    }


def _palette_daltonien() -> dict:
    """Palette de Wong (Nature Methods 2011). Distinguable par les
    deutéranopes et protanopes."""
    return {
        "Bleu":    (0.00, 0.45, 0.70),
        "Vert":    (0.00, 0.60, 0.50),
        "Rouge":   (0.80, 0.40, 0.00),
        "Gris":    (0.50, 0.50, 0.50),
        "Jaune":   (0.95, 0.90, 0.25),
        "Magenta": (0.80, 0.60, 0.70),
        "Cyan":    (0.35, 0.70, 0.90),
        "Orange":  (0.90, 0.60, 0.00),
    }


def _palette_mono() -> dict:
    """Nuances de gris pour publication noir et blanc."""
    g = lambda v: (v, v, v)
    return {
        "Bleu":    g(0.85),
        "Vert":    g(0.65),
        "Rouge":   g(0.40),
        "Gris":    g(0.55),
        "Jaune":   g(0.95),
        "Magenta": g(0.30),
        "Cyan":    g(0.75),
        "Orange":  g(0.50),
    }


PRESETS = {
    "DEFAULT": {
        "label":  "Défaut",
        "tip":    "Palette livrée avec l'extension. Couleurs équilibrées "
                  "pour fond gris Blender.",
        "colors": _palette_default(),
    },
    "VIF": {
        "label":  "Vif (fond sombre)",
        "tip":    "Couleurs saturées, optimisées pour rendu sur fond sombre.",
        "colors": _palette_vif(),
    },
    "PASTEL": {
        "label":  "Pastel (fond clair)",
        "tip":    "Couleurs douces, lisibles sur fond clair (papier, "
                  "présentation projetée).",
        "colors": _palette_pastel(),
    },
    "DALTONIEN": {
        "label":  "Daltonien-safe (Wong)",
        "tip":    "Palette de Wong (Nature Methods 2011) compatible "
                  "deutéranopie et protanopie.",
        "colors": _palette_daltonien(),
    },
    "MONOCHROME": {
        "label":  "Monochrome (N&B)",
        "tip":    "Nuances de gris pour publication noir et blanc. "
                  "Les courbes restent distinguables par leur clarté.",
        "colors": _palette_mono(),
    },
}

PRESET_ORDER = ("DEFAULT", "VIF", "PASTEL", "DALTONIEN", "MONOCHROME")


# ---------------------------------------------------------------------------
# Persistent store (builtins + user JSON)
# ---------------------------------------------------------------------------

CURRENT_VERSION = 1
USER_PID_PREFIX = "usr:"
_USER_DIR_NAME = "realfn_viewer"


def _slugify(label: str) -> str:
    nfkd = unicodedata.normalize("NFKD", label)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "_", stripped).strip("_").lower()
    return s or "sans_nom"


def _make_pid(label: str, existing: set) -> str:
    base = USER_PID_PREFIX + _slugify(label)
    pid, n = base, 2
    while pid in existing:
        pid = f"{base}_{n}"
        n += 1
    return pid


def is_user_pid(pid: str) -> bool:
    return isinstance(pid, str) and pid.startswith(USER_PID_PREFIX)


def _user_config_dir() -> str:
    return bpy.utils.user_resource("CONFIG", path=_USER_DIR_NAME, create=True)


class _Store:
    """Tiny palette preset store: builtins + user JSON (single file)."""

    def __init__(self):
        self._user_cache: dict | None = None
        self._enum_cache: list | None = None

    @property
    def _json_path(self) -> str:
        return os.path.join(_user_config_dir(), "materials_presets.json")

    def _read_user(self) -> dict:
        try:
            p = self._json_path
        except OSError:
            return {}
        if not os.path.isfile(p):
            return {}
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"[RealFn] Lecture palettes.json échouée : {e}")
            return {}
        if data.get("version", 0) > CURRENT_VERSION:
            return {}
        return data.get("presets", {})

    def _write_user(self, user: dict) -> bool:
        try:
            p = self._json_path
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"version": CURRENT_VERSION, "presets": user},
                          f, indent=2, ensure_ascii=False)
            return True
        except OSError as e:
            print(f"[RealFn] Écriture palettes.json échouée : {e}")
            return False

    def get_user(self) -> dict:
        if self._user_cache is None:
            self._user_cache = self._read_user()
        return self._user_cache

    def invalidate(self):
        self._user_cache = None
        self._enum_cache = None

    def get(self, pid: str) -> dict | None:
        if pid in PRESETS:
            return PRESETS[pid]
        return self.get_user().get(pid)

    def label(self, pid: str) -> str:
        p = self.get(pid)
        return p["label"] if p else pid

    def is_user(self, pid: str) -> bool:
        return is_user_pid(pid) and pid in self.get_user()

    def enum_items(self) -> list:
        if self._enum_cache is not None:
            return self._enum_cache
        items = [(pid, PRESETS[pid]["label"], PRESETS[pid].get("tip", ""))
                 for pid in PRESET_ORDER]
        user = self.get_user()
        for pid in sorted(user, key=lambda k: user[k].get("label", k).lower()):
            p = user[pid]
            items.append((pid, "★ " + p.get("label", pid),
                          p.get("tip", "Preset utilisateur")))
        self._enum_cache = items
        return items

    def apply_to(self, pid: str):
        p = self.get(pid)
        if p is None:
            raise KeyError(f"Palette inconnue : {pid!r}")
        default_materials.apply_palette(p.get("colors", {}))

    def save_user(self, label: str, tip: str) -> str:
        label = label.strip()
        if not label:
            raise ValueError("Le nom du preset ne peut pas être vide.")
        existing = set(PRESETS) | set(self.get_user())
        pid = _make_pid(label, existing)
        snap = {
            "label":  label,
            "tip":    tip.strip() or f"Preset utilisateur — {label}",
            "colors": default_materials.snapshot_palette(),
        }
        user = dict(self.get_user())
        user[pid] = snap
        if not self._write_user(user):
            raise OSError("Échec de l'écriture du fichier de palettes.")
        self._user_cache = user
        self._enum_cache = None
        return pid

    def update_user(self, pid: str) -> bool:
        if not is_user_pid(pid):
            return False
        user = dict(self.get_user())
        if pid not in user:
            return False
        snap = {
            "label":  user[pid].get("label", pid),
            "tip":    user[pid].get("tip", ""),
            "colors": default_materials.snapshot_palette(),
        }
        user[pid] = snap
        if not self._write_user(user):
            raise OSError("Échec de l'écriture du fichier de palettes.")
        self._user_cache = user
        self._enum_cache = None
        return True

    def delete_user(self, pid: str) -> bool:
        if not is_user_pid(pid):
            return False
        user = dict(self.get_user())
        if pid not in user:
            return False
        del user[pid]
        if not self._write_user(user):
            return False
        self._user_cache = user
        self._enum_cache = None
        return True

    def export_to(self, path: str) -> int:
        user = self.get_user()
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"version": CURRENT_VERSION, "presets": user},
                      f, indent=2, ensure_ascii=False)
        return len(user)

    def import_from(self, path: str, *, overwrite: bool = False) -> tuple:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "presets" not in data:
            raise ValueError("Format inattendu : clé 'presets' absente.")
        incoming = data["presets"]
        if not isinstance(incoming, dict):
            raise ValueError("Champ 'presets' invalide.")
        user = dict(self.get_user())
        added = replaced = renamed = skipped = 0
        for pid, preset in incoming.items():
            if not isinstance(preset, dict):
                skipped += 1
                continue
            if pid in user:
                if overwrite:
                    user[pid] = preset
                    replaced += 1
                else:
                    existing = set(PRESETS) | set(user)
                    new_pid = _make_pid(preset.get("label", pid), existing)
                    user[new_pid] = preset
                    renamed += 1
            elif pid in PRESETS:
                skipped += 1
            else:
                user[pid] = preset
                added += 1
        if not self._write_user(user):
            raise OSError("Écriture impossible.")
        self._user_cache = user
        self._enum_cache = None
        return (added, replaced, renamed, skipped)


STORE = _Store()


# ---------------------------------------------------------------------------
# PropertyGroup
# ---------------------------------------------------------------------------

def enum_items_callback(self, context):
    return STORE.enum_items()


class RealFnMaterialsProperties(PropertyGroup):
    preset_choice: EnumProperty(
        name="Palette",
        description="Palette de couleurs de la bibliothèque RealFn. "
                    "Les presets ★ sont des palettes utilisateur.",
        items=enum_items_callback,
    )


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class REALFN_OT_apply_materials_preset(Operator):
    """Applique la palette sélectionnée aux matériaux RealFn."""

    bl_idname = "realfn.apply_materials_preset"
    bl_label = "Appliquer la palette"
    bl_description = (
        "Recopie les couleurs de la palette sélectionnée sur les "
        "matériaux RealFn existants dans la scène"
    )
    bl_options = {'REGISTER', 'UNDO'}

    preset_id: StringProperty(default="")

    def execute(self, context):
        props = context.scene.realfn_materials
        pid = self.preset_id or props.preset_choice
        if not pid:
            self.report({'WARNING'}, "Aucune palette sélectionnée.")
            return {'CANCELLED'}
        try:
            STORE.apply_to(pid)
        except KeyError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        if props.preset_choice != pid:
            props.preset_choice = pid
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        self.report({'INFO'}, f"Palette « {STORE.label(pid)} » appliquée.")
        return {'FINISHED'}


class REALFN_OT_save_materials_preset(Operator):
    """Enregistre la palette courante comme preset utilisateur."""

    bl_idname = "realfn.save_materials_preset"
    bl_label = "Enregistrer comme palette"
    bl_description = (
        "Enregistre les couleurs actuelles des matériaux RealFn "
        "comme palette utilisateur nommée"
    )
    bl_options = {'REGISTER'}

    label: StringProperty(name="Nom",
                          description="Nom de la palette",
                          default="Ma palette")
    tip: StringProperty(name="Description",
                        description="Description courte (facultative)",
                        default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        self.layout.prop(self, "label")
        self.layout.prop(self, "tip")
        self.layout.label(
            text="Enregistré dans le config utilisateur de Blender.",
            icon='INFO')

    def execute(self, context):
        try:
            pid = STORE.save_user(self.label, self.tip)
        except (ValueError, OSError) as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        context.scene.realfn_materials.preset_choice = pid
        self.report({'INFO'}, f"Palette « {self.label} » enregistrée.")
        return {'FINISHED'}


class REALFN_OT_update_materials_preset(Operator):
    """Réécrit le preset utilisateur sélectionné avec les couleurs actuelles."""

    bl_idname = "realfn.update_materials_preset"
    bl_label = "Mettre à jour cette palette"
    bl_description = (
        "Remplace les couleurs du preset utilisateur sélectionné "
        "par les couleurs actuelles des matériaux"
    )
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        sc = getattr(context, "scene", None)
        if sc is None:
            return False
        props = getattr(sc, "realfn_materials", None)
        return props is not None and STORE.is_user(props.preset_choice)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        props = context.scene.realfn_materials
        pid = props.preset_choice
        lbl = STORE.label(pid)
        try:
            ok = STORE.update_user(pid)
        except OSError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        if not ok:
            self.report({'ERROR'}, "Mise à jour impossible.")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Palette « {lbl} » mise à jour.")
        return {'FINISHED'}


class REALFN_OT_delete_materials_preset(Operator):
    """Supprime le preset utilisateur sélectionné."""

    bl_idname = "realfn.delete_materials_preset"
    bl_label = "Supprimer cette palette"
    bl_description = "Supprime définitivement cette palette utilisateur"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        sc = getattr(context, "scene", None)
        if sc is None:
            return False
        props = getattr(sc, "realfn_materials", None)
        return props is not None and STORE.is_user(props.preset_choice)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        props = context.scene.realfn_materials
        pid = props.preset_choice
        lbl = STORE.label(pid)
        if not STORE.delete_user(pid):
            self.report({'ERROR'}, "Suppression impossible.")
            return {'CANCELLED'}
        props.preset_choice = PRESET_ORDER[0]
        self.report({'INFO'}, f"Palette « {lbl} » supprimée.")
        return {'FINISHED'}


class REALFN_OT_refresh_materials_presets(Operator):
    """Recharge la bibliothèque de palettes depuis le disque."""

    bl_idname = "realfn.refresh_materials_presets"
    bl_label = "Rafraîchir depuis le disque"
    bl_description = "Recharge les palettes utilisateur depuis le fichier JSON"
    bl_options = {'REGISTER'}

    def execute(self, context):
        STORE.invalidate()
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        n = len(STORE.get_user())
        self.report({'INFO'}, f"Palettes rechargées ({n} utilisateur(s)).")
        return {'FINISHED'}


class REALFN_OT_reset_materials(Operator):
    """Restaure la palette par défaut."""

    bl_idname = "realfn.reset_materials"
    bl_label = "Restaurer la palette par défaut"
    bl_description = (
        "Recopie la palette « Défaut » sur les matériaux RealFn. "
        "Les palettes utilisateur enregistrées ne sont pas affectées."
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        default_materials.reset_to_default()
        context.scene.realfn_materials.preset_choice = "DEFAULT"
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        self.report({'INFO'}, "Palette par défaut restaurée.")
        return {'FINISHED'}


class REALFN_OT_export_materials_presets(Operator):
    """Exporte les palettes utilisateur vers un fichier JSON."""

    bl_idname = "realfn.export_materials_presets"
    bl_label = "Exporter mes palettes"
    bl_description = (
        "Exporte la bibliothèque de palettes utilisateur vers un fichier "
        "JSON partageable"
    )
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = "realfn_palettes.json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        try:
            n = STORE.export_to(self.filepath)
        except OSError as e:
            self.report({'ERROR'}, f"Échec export : {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"{n} palette(s) exportée(s) vers {self.filepath}")
        return {'FINISHED'}


class REALFN_OT_import_materials_presets(Operator):
    """Importe des palettes depuis un fichier JSON."""

    bl_idname = "realfn.import_materials_presets"
    bl_label = "Importer des palettes"
    bl_description = (
        "Importe des palettes depuis un fichier JSON, "
        "en fusionnant avec les palettes utilisateur existantes"
    )
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    overwrite: bpy.props.BoolProperty(
        name="Écraser les palettes existantes",
        description="Si activé, les palettes importées remplacent celles du "
                    "même PID. Sinon les collisions sont renommées.",
        default=False,
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        self.layout.prop(self, "overwrite")

    def execute(self, context):
        try:
            added, replaced, renamed, skipped = STORE.import_from(
                self.filepath, overwrite=self.overwrite)
        except (ValueError, OSError) as e:
            self.report({'ERROR'}, f"Échec import : {e}")
            return {'CANCELLED'}
        parts = []
        if added:    parts.append(f"{added} ajoutée(s)")
        if replaced: parts.append(f"{replaced} remplacée(s)")
        if renamed:  parts.append(f"{renamed} renommée(s)")
        if skipped:  parts.append(f"{skipped} ignorée(s)")
        msg = ", ".join(parts) or "aucun changement"
        self.report({'INFO'}, f"Import : {msg}")
        STORE.invalidate()
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


classes = (
    RealFnMaterialsProperties,
    REALFN_OT_apply_materials_preset,
    REALFN_OT_save_materials_preset,
    REALFN_OT_update_materials_preset,
    REALFN_OT_delete_materials_preset,
    REALFN_OT_refresh_materials_presets,
    REALFN_OT_reset_materials,
    REALFN_OT_export_materials_presets,
    REALFN_OT_import_materials_presets,
)
