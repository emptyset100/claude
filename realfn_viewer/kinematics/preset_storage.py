"""Stockage persistant des presets utilisateur.

Encapsule la logique commune aux presets du Vector Viewer simple
et de la Composition :

- Lecture / écriture d'un fichier JSON dans le dossier de config
  utilisateur de Blender (``bpy.utils.user_resource('CONFIG', …)``),
  donc indépendant du .blend ouvert et partagé entre projets.
- Fusion d'une bibliothèque de presets builtins (lecture seule, livrée
  avec l'extension) avec une bibliothèque utilisateur (mutable).
- Génération des items pour ``EnumProperty.items`` sous forme de
  callback, avec cache invalidé explicitement à chaque mutation.

Format JSON (schéma version 1) :

    {
      "version": 1,
      "presets": {
        "usr:mon_preset": {
          "label": "Mon preset",
          "tip":   "Description libre",
          ... champs spécifiques au type de preset ...
        }
      }
    }

Les IDs utilisateur sont systématiquement préfixés ``usr:`` :
- distinction sans ambiguïté builtin / user (utile au polling de
  l'opérateur Delete),
- aucun risque de collision avec les IDs builtin (qui sont en MAJUSCULES,
  sans préfixe).
"""

from __future__ import annotations

import json
import os
import re
import unicodedata

import bpy


# Schéma actuel du fichier JSON utilisateur. À bumper lors de tout
# changement incompatible du format des presets ; `_read_user` accepte
# pour l'instant tout fichier portant ``version <= CURRENT_VERSION``
# pour faciliter une migration douce le jour venu.
CURRENT_VERSION = 1


# Préfixe imposé sur tous les IDs utilisateur. Les builtins sont en
# majuscules sans préfixe (ex. "MCU", "CORIOLIS"), donc préfixe distinct.
USER_PID_PREFIX = "usr:"


# Sous-dossier dans le répertoire de config utilisateur de Blender :
#   Linux/macOS : ~/.config/blender/<version>/config/vector_viewer/
#   Windows     : %APPDATA%/Blender Foundation/Blender/<ver>/config/vector_viewer/
USER_DIR_NAME = "vector_viewer"


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _slugify(label: str) -> str:
    """Convertit un label arbitraire en identifiant ASCII court.

    "Mon Super Préset !" → "mon_super_preset"

    Stratégie : décomposition Unicode NFKD pour séparer base + diacritique,
    on supprime les diacritiques (catégorie « Mn ») et on ne garde que les
    [A-Za-z0-9_]. Plus robuste qu'une table de translittération manuelle :
    couvre toute la latine étendue (à, é, ñ, ç, …) sans risque d'erreur
    d'alignement.
    """
    # Décomposition canonique compatible (NFKD) : « é » → « e » + combining acute
    nfkd = unicodedata.normalize('NFKD', label)
    # Filtre les marqueurs combinants → on récupère les bases ASCII
    stripped = ''.join(c for c in nfkd if not unicodedata.combining(c))
    # Tout ce qui n'est pas alphanumérique devient underscore
    s = re.sub(r'[^A-Za-z0-9]+', '_', stripped).strip('_').lower()
    return s or "sans_nom"


def _make_pid(label: str, existing_ids: set[str]) -> str:
    """Génère un ID utilisateur unique à partir d'un label libre."""
    base = USER_PID_PREFIX + _slugify(label)
    pid = base
    n = 2
    while pid in existing_ids:
        pid = f"{base}_{n}"
        n += 1
    return pid


def is_user_pid(pid: str) -> bool:
    """Test : ce PID est-il celui d'un preset utilisateur ?"""
    return isinstance(pid, str) and pid.startswith(USER_PID_PREFIX)


def _user_config_dir() -> str:
    """Retourne le sous-dossier ``vector_viewer`` du config utilisateur,
    crée-le si manquant. Lève ``OSError`` si écriture impossible."""
    return bpy.utils.user_resource('CONFIG', path=USER_DIR_NAME, create=True)


# ----------------------------------------------------------------------------
# PresetStore
# ----------------------------------------------------------------------------

class PresetStore:
    """Façade unique pour une bibliothèque de presets (builtins + user).

    Toutes les opérations passent par ici :
        - ``apply_to(props, pid)`` : recopie les valeurs sur un PropertyGroup
        - ``enum_items()``         : items pour ``EnumProperty.items`` callback
        - ``save_user(label, …)``  : enregistre la config courante
        - ``delete_user(pid)``     : retire un preset utilisateur

    Le cache du callback Enum est invalidé automatiquement après chaque
    save/delete : le callback retournera des items frais à la prochaine
    interrogation par Blender.
    """

    def __init__(self,
                 builtin: dict,
                 builtin_order: tuple,
                 filename: str,
                 fields_apply,
                 fields_snapshot):
        """
        Args:
            builtin:        dict ID → preset_dict (lecture seule, livré).
            builtin_order:  tuple d'IDs (ordre d'affichage des builtins).
            filename:       nom du fichier JSON (ex. "vector_viewer_presets.json").
            fields_apply:   callable(props, preset_dict) qui copie le preset
                            sur le PropertyGroup.
            fields_snapshot: callable(props) → dict des champs cinématiques
                             à enregistrer (sans label/tip).
        """
        self.builtin = builtin
        self.builtin_order = builtin_order
        self.filename = filename
        self._fields_apply = fields_apply
        self._fields_snapshot = fields_snapshot

        # Caches lazy ; None signifie « non chargé ».
        self._user_cache: dict | None = None
        self._enum_cache: list | None = None

    # ── Chemin ────────────────────────────────────────────────────────

    @property
    def user_path(self) -> str:
        """Chemin absolu du fichier JSON utilisateur."""
        return os.path.join(_user_config_dir(), self.filename)

    # ── Lecture / écriture disque ─────────────────────────────────────

    def _read_user(self) -> dict:
        """Lit le JSON utilisateur. Tolérant : retourne {} sur fichier
        manquant, illisible, JSON invalide, ou schéma trop récent."""
        try:
            path = self.user_path
        except OSError as e:
            print(f"[VectorViewer] Config utilisateur indisponible : {e}")
            return {}

        if not os.path.isfile(path):
            return {}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"[VectorViewer] Lecture {path} échouée : {e}")
            return {}

        version = data.get("version", 0)
        if version > CURRENT_VERSION:
            print(f"[VectorViewer] Fichier {path} : version {version} "
                  f"non supportée (max = {CURRENT_VERSION}). Ignoré.")
            return {}

        presets = data.get("presets", {})
        if not isinstance(presets, dict):
            print(f"[VectorViewer] Fichier {path} : champ 'presets' invalide.")
            return {}

        return presets

    def _write_user(self, presets: dict) -> bool:
        """Écrit le JSON utilisateur. Retourne True si succès."""
        try:
            path = self.user_path
            os.makedirs(os.path.dirname(path), exist_ok=True)
            payload = {"version": CURRENT_VERSION, "presets": presets}
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            return True
        except OSError as e:
            print(f"[VectorViewer] Écriture {self.filename} échouée : {e}")
            return False

    # ── Cache ─────────────────────────────────────────────────────────

    def get_user(self) -> dict:
        """Dict des presets utilisateur (chargé paresseusement)."""
        if self._user_cache is None:
            self._user_cache = self._read_user()
        return self._user_cache

    def invalidate(self):
        """Force le re-chargement disque + reconstruction des items Enum."""
        self._user_cache = None
        self._enum_cache = None

    # ── Lookup ────────────────────────────────────────────────────────

    def get(self, pid: str) -> dict | None:
        """Retourne le preset dict associé à ``pid``, ou None si absent."""
        if pid in self.builtin:
            return self.builtin[pid]
        return self.get_user().get(pid)

    def label(self, pid: str) -> str:
        p = self.get(pid)
        return p["label"] if p else pid

    def is_user(self, pid: str) -> bool:
        return is_user_pid(pid) and pid in self.get_user()

    def is_builtin(self, pid: str) -> bool:
        return pid in self.builtin

    # ── EnumProperty items ────────────────────────────────────────────

    def enum_items(self) -> list:
        """Liste pour ``EnumProperty.items`` : (id, label_affiché, tip).

        Builtins d'abord (dans ``builtin_order``), suivis des presets
        utilisateur triés par label, préfixés ★ pour la distinction visuelle.

        IMPORTANT : la liste retournée est mémorisée au niveau de l'instance
        pour que les chaînes restent vivantes le temps que Blender les
        utilise (sinon corruption mémoire / crashs)."""
        if self._enum_cache is not None:
            return self._enum_cache

        items = []
        for pid in self.builtin_order:
            p = self.builtin[pid]
            items.append((pid, p["label"], p.get("tip", "")))

        user = self.get_user()
        # Tri stable par label affiché — l'utilisateur voit ses presets
        # ordonnés alphabétiquement, indépendamment de l'ordre de création.
        for pid in sorted(user.keys(), key=lambda k: user[k].get("label", k).lower()):
            p = user[pid]
            label = "★ " + p.get("label", pid)
            tip   = p.get("tip", "Preset utilisateur")
            items.append((pid, label, tip))

        self._enum_cache = items
        return items

    # ── Application ───────────────────────────────────────────────────

    def apply_to(self, props, pid: str):
        """Recopie le preset ``pid`` sur ``props``. Lève KeyError si absent."""
        p = self.get(pid)
        if p is None:
            raise KeyError(f"Preset inconnu : {pid}")
        self._fields_apply(props, p)

    # ── Mutations ─────────────────────────────────────────────────────

    def save_user(self, label: str, tip: str, props) -> str:
        """Capture l'état courant de ``props``, l'enregistre comme preset
        utilisateur, et retourne le PID généré."""
        label = label.strip()
        if not label:
            raise ValueError("Le nom du preset ne peut pas être vide.")

        existing_ids = set(self.builtin.keys()) | set(self.get_user().keys())
        pid = _make_pid(label, existing_ids)

        snapshot = self._fields_snapshot(props)
        snapshot["label"] = label
        snapshot["tip"]   = tip.strip() or f"Preset utilisateur — {label}"

        user = dict(self.get_user())  # copie pour ne pas muter le cache
        user[pid] = snapshot

        if not self._write_user(user):
            raise OSError("Échec de l'écriture du fichier de presets.")

        # Le write a réussi → on adopte le nouveau dict comme cache
        self._user_cache = user
        # … mais le cache des items Enum reste obsolète (liste différente)
        self._enum_cache = None

        return pid

    def update_user(self, pid: str, props) -> bool:
        """Réécrit le snapshot du preset utilisateur ``pid`` à partir de
        l'état courant de ``props``. Préserve le label et le tip d'origine.

        Returns:
            True si la mise à jour a été effectuée, False si ``pid`` n'est
            pas un preset utilisateur connu.

        Raises:
            OSError: échec d'écriture disque.
        """
        if not is_user_pid(pid):
            return False
        user = dict(self.get_user())
        if pid not in user:
            return False

        snapshot = self._fields_snapshot(props)
        # Les métadonnées (label/tip) restent celles du preset original :
        # update est une mise à jour des champs cinématiques uniquement.
        snapshot["label"] = user[pid].get("label", pid)
        snapshot["tip"]   = user[pid].get("tip", "")

        user[pid] = snapshot
        if not self._write_user(user):
            raise OSError("Échec de l'écriture du fichier de presets.")

        self._user_cache = user
        # Le label/tip n'ayant pas changé, le cache Enum reste valide ;
        # on l'invalide quand même par souci de cohérence si l'utilisateur
        # avait modifié des métadonnées dans le JSON entre-temps.
        self._enum_cache = None
        return True

    def delete_user(self, pid: str) -> bool:
        """Supprime un preset utilisateur. Retourne True si effectué."""
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

    # ── Export / Import ─────────────────────────────────────────────

    def export_to(self, path: str) -> int:
        """Écrit la bibliothèque utilisateur courante vers ``path`` au
        format JSON. Retourne le nombre de presets exportés.

        Le format est identique à celui du fichier interne — donc
        l'utilisateur peut aussi récupérer directement le fichier
        dans son user config s'il préfère.
        """
        user = self.get_user()
        payload = {
            "version": CURRENT_VERSION,
            "presets": user,
        }
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        return len(user)

    def import_from(self, path: str, *, overwrite: bool = False) -> tuple:
        """Lit le fichier JSON ``path`` et fusionne les presets dans la
        bibliothèque utilisateur courante.

        Args:
            path: chemin du fichier à importer.
            overwrite: si True, remplace les presets utilisateur
                existants quand un PID importé est déjà pris.
                Si False (défaut), génère de nouveaux PIDs en cas de
                collision (suffixe ``_2``, ``_3``…), et le compteur
                ``renamed`` reflète ces renommages.

        Returns:
            (added, replaced, renamed, skipped) — décompte par catégorie.

        Raises:
            ValueError si le fichier est mal formé.
            OSError si la lecture/écriture échoue.
        """
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or 'presets' not in data:
            raise ValueError(
                f"Fichier {path} : format inattendu (clé 'presets' absente)."
            )

        version = data.get('version', CURRENT_VERSION)
        if version != CURRENT_VERSION:
            # Pas de migration pour le moment — on warn et on tente
            # quand même, car le format peut rester compatible.
            print(f"[VectorViewer] Import {path} : version {version} "
                  f"≠ {CURRENT_VERSION}, importation au format actuel.")

        incoming = data.get('presets', {})
        if not isinstance(incoming, dict):
            raise ValueError(f"Fichier {path} : 'presets' n'est pas un dict.")

        user = dict(self.get_user())
        added = replaced = renamed = skipped = 0

        for pid, preset in incoming.items():
            if not isinstance(preset, dict):
                skipped += 1
                continue

            label = preset.get('label', pid)
            if pid in user:
                if overwrite:
                    user[pid] = preset
                    replaced += 1
                else:
                    # Collision : on génère un nouveau PID basé sur le
                    # même label, suffixé pour éviter le conflit.
                    existing = (set(self.builtin.keys()) | set(user.keys()))
                    new_pid = _make_pid(label, existing)
                    user[new_pid] = preset
                    renamed += 1
            else:
                # Vérifier aussi qu'on n'écrase pas un builtin (impossible
                # vu que les builtins n'ont pas le préfixe ``usr:`` mais
                # par sécurité)
                if pid in self.builtin:
                    skipped += 1
                    continue
                user[pid] = preset
                added += 1

        if not self._write_user(user):
            raise OSError(f"Écriture impossible vers {self.user_path}")
        self._user_cache = user
        self._enum_cache = None

        return (added, replaced, renamed, skipped)


# ─────────────────────────────────────────────────────────────────────
# Opérateurs Export / Import génériques
# ─────────────────────────────────────────────────────────────────────
# Plutôt que dupliquer 80 lignes par module de presets (3 modules ×
# 2 opérateurs), on factorise dans une fonction-factory qui produit
# des classes prêtes à enregistrer.

def make_export_operator(*, idname: str, label: str, description: str,
                          store_attr: str, default_filename: str):
    """Crée une classe ``Operator`` qui exporte la bibliothèque utilisateur
    d'un ``PresetStore``.

    Args:
        idname: bl_idname (ex. ``"vector_viewer.export_user_presets"``).
        label: bl_label (ex. ``"Exporter mes presets"``).
        description: bl_description.
        store_attr: chemin d'attribut depuis le module appelant pour
            récupérer le store (ex. ``"presets:STORE"`` signifie
            ``importlib.import_module(...presets).STORE``). Format :
            ``"<module relatif>:<attribut>"``.
        default_filename: nom de fichier par défaut dans le dialogue.
    """
    # Import retardé : ces helpers ne sont disponibles qu'à l'exécution
    # dans Blender, pas au chargement du module.
    import importlib

    def _resolve_store():
        modname, attr = store_attr.split(":")
        # Le module est sous le package vector_viewer.<modname>
        from . import __name__ as pkgname  # = "vector_viewer"
        mod = importlib.import_module(f"{pkgname}.{modname}")
        return getattr(mod, attr)

    class _ExportPresetsOp(bpy.types.Operator):
        bl_idname = idname
        bl_label = label
        bl_description = description
        bl_options = {'REGISTER'}

        # ExportHelper expose ``filepath`` ; on définit le filtre.
        filepath: bpy.props.StringProperty(subtype='FILE_PATH')
        filename_ext = ".json"
        filter_glob: bpy.props.StringProperty(
            default="*.json", options={'HIDDEN'})

        def invoke(self, context, event):
            if not self.filepath:
                self.filepath = default_filename
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}

        def execute(self, context):
            store = _resolve_store()
            try:
                n = store.export_to(self.filepath)
            except OSError as e:
                self.report({'ERROR'}, f"Échec export : {e}")
                return {'CANCELLED'}
            self.report(
                {'INFO'},
                f"{n} preset(s) exporté(s) vers {self.filepath}",
            )
            return {'FINISHED'}

    return _ExportPresetsOp


def make_import_operator(*, idname: str, label: str, description: str,
                          store_attr: str, refresh_callback=None):
    """Crée une classe ``Operator`` qui importe une bibliothèque depuis
    un fichier JSON.

    Args:
        idname, label, description, store_attr : voir ``make_export_operator``.
        refresh_callback: optionnel, fonction(context) appelée après import
            réussi pour rafraîchir l'UI (typiquement tag_redraw des
            zones 3D).
    """
    import importlib

    def _resolve_store():
        modname, attr = store_attr.split(":")
        from . import __name__ as pkgname
        mod = importlib.import_module(f"{pkgname}.{modname}")
        return getattr(mod, attr)

    class _ImportPresetsOp(bpy.types.Operator):
        bl_idname = idname
        bl_label = label
        bl_description = description
        bl_options = {'REGISTER', 'UNDO'}

        filepath: bpy.props.StringProperty(subtype='FILE_PATH')
        filter_glob: bpy.props.StringProperty(
            default="*.json", options={'HIDDEN'})
        overwrite: bpy.props.BoolProperty(
            name="Écraser les presets existants",
            description="Si activé, les presets importés remplacent les "
                        "presets utilisateur de même PID. Sinon, les "
                        "collisions sont renommées (suffixe _2, _3, …).",
            default=False,
        )

        def invoke(self, context, event):
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}

        def draw(self, context):
            self.layout.prop(self, "overwrite")

        def execute(self, context):
            store = _resolve_store()
            try:
                added, replaced, renamed, skipped = store.import_from(
                    self.filepath, overwrite=self.overwrite,
                )
            except (ValueError, OSError) as e:
                self.report({'ERROR'}, f"Échec import : {e}")
                return {'CANCELLED'}

            parts = []
            if added:    parts.append(f"{added} ajouté(s)")
            if replaced: parts.append(f"{replaced} remplacé(s)")
            if renamed:  parts.append(f"{renamed} renommé(s)")
            if skipped:  parts.append(f"{skipped} ignoré(s)")
            msg = ", ".join(parts) if parts else "aucun changement"
            self.report({'INFO'}, f"Import : {msg}")

            if refresh_callback is not None:
                try:
                    refresh_callback(context)
                except Exception as e:  # noqa: BLE001
                    print(f"[VectorViewer] refresh_callback échoue : {e}")

            return {'FINISHED'}

    return _ImportPresetsOp
