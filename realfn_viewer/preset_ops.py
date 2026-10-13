"""
Factory for the per-kind preset operators.

The six object kinds each used to carry six near-identical preset
operators (save / apply / delete / import / export / reinstall) — 36
classes, ~2000 lines, differing only in which ``presets.*`` functions
they call, which tree builder rebuilds the node group on *apply*, and a
few display strings.

This module generates those 36 classes from one :class:`OpsSpec` per
kind via :func:`build`. The generated classes keep the **exact original
``bl_idname``s** (e.g. ``realfn.save_vector_preset``) so the panels,
keymaps and any saved references keep working unchanged; only the source
duplication is gone.

The active-modifier finders (``_active_*_realfn_modifier``) live in
:mod:`operators`; to avoid an import cycle they are resolved lazily by
name at call time.
"""

from __future__ import annotations

import json
from pathlib import Path

import bpy

from . import presets, builtin_presets
from . import (tree, vector_tree, surface_tree, parametric_surface_tree,
               scalar_field_3d_tree, vector_field_3d_tree, bench_tree)


def _active(finder_name, context):
    """Resolve and call an ``operators._active_*`` finder lazily."""
    from . import operators
    return getattr(operators, finder_name)(context)


# --------------------------------------------------------------------------- #
# Per-kind tree rebuild (the only genuinely kind-specific apply logic)
# --------------------------------------------------------------------------- #
def _rebuild_scalar(data):
    f = data.get("formula", {})
    r = data.get("range", {})
    return tree.make_realfn_tree(
        f.get("expr", "0"),
        allowed_params=tuple(f.get("allowed_params", [])),
        derivative_order=int(f.get("derivative_order", 0)),
        taylor_order=int(f.get("taylor_order", 0)),
        x_default_range=(float(r.get("x_min", -5.0)),
                         float(r.get("x_max", 5.0))),
        x0_default=float(r.get("x_0", 0.0)),
    )


def _rebuild_vector(data):
    f = data.get("formula", {})
    r = data.get("range", {})
    return vector_tree.make_vectorfn_tree(
        f.get("expr", "0*N.x + 0*N.y + 0*N.z"),
        var_name=str(f.get("var_name", "t")),
        allowed_params=tuple(f.get("allowed_params", [])),
        t_default_range=(float(r.get("t_min", 0.0)),
                         float(r.get("t_max", 6.283))),
        t0_default=float(r.get("t_0", 0.0)),
    )


def _rebuild_surface(data):
    f = data.get("formula", {})
    r = data.get("range", {})
    return surface_tree.make_surfacefn_tree(
        f.get("expr", "0"),
        x_name=str(f.get("x_name", "x")),
        y_name=str(f.get("y_name", "y")),
        allowed_params=tuple(f.get("allowed_params", [])),
        x_default_range=(float(r.get("x_min", -3.0)),
                         float(r.get("x_max", 3.0))),
        y_default_range=(float(r.get("y_min", -3.0)),
                         float(r.get("y_max", 3.0))),
        x0_default=float(r.get("x_0", 0.5)),
        y0_default=float(r.get("y_0", 0.5)),
    )


def _rebuild_parametric(data):
    f = data.get("formula", {})
    r = data.get("range", {})
    comps = f.get("components", ["0", "0", "0"])
    return parametric_surface_tree.make_parametric_surface_tree(
        tuple(comps),
        u_name=str(f.get("u_name", "u")),
        v_name=str(f.get("v_name", "v")),
        allowed_params=tuple(f.get("allowed_params", [])),
        u_default_range=(float(r.get("u_min", 0.0)),
                         float(r.get("u_max", 6.283))),
        v_default_range=(float(r.get("v_min", 0.0)),
                         float(r.get("v_max", 3.142))),
        u0_default=float(r.get("u_0", 1.0)),
        v0_default=float(r.get("v_0", 1.0)),
    )


def _rebuild_scalar_field_3d(data):
    f = data.get("formula", {})
    r = data.get("range", {})
    return scalar_field_3d_tree.make_scalarfield3d_tree(
        f.get("expr", "0"),
        x_name=str(f.get("x_name", "x")),
        y_name=str(f.get("y_name", "y")),
        z_name=str(f.get("z_name", "z")),
        allowed_params=tuple(f.get("allowed_params", [])),
        x_default_range=(float(r.get("x_min", -1.0)),
                         float(r.get("x_max", 1.0))),
        y_default_range=(float(r.get("y_min", -1.0)),
                         float(r.get("y_max", 1.0))),
        z_default_range=(float(r.get("z_min", -1.0)),
                         float(r.get("z_max", 1.0))),
        x0_default=float(r.get("x_0", 0.5)),
        y0_default=float(r.get("y_0", 0.5)),
        z0_default=float(r.get("z_0", 0.5)),
    )


def _rebuild_vector_field_3d(data):
    f = data.get("formula", {})
    r = data.get("range", {})
    box = dict(
        x_name=str(f.get("x_name", "x")),
        y_name=str(f.get("y_name", "y")),
        z_name=str(f.get("z_name", "z")),
        allowed_params=tuple(f.get("allowed_params", [])),
        x_default_range=(float(r.get("x_min", -1.5)),
                         float(r.get("x_max", 1.5))),
        y_default_range=(float(r.get("y_min", -1.5)),
                         float(r.get("y_max", 1.5))),
        z_default_range=(float(r.get("z_min", -1.5)),
                         float(r.get("z_max", 1.5))),
        x0_default=float(r.get("x_0", 0.5)),
        y0_default=float(r.get("y_0", 0.5)),
        z0_default=float(r.get("z_0", 0.5)),
    )
    if str(f.get("mode", "explicit")) == "from_potential":
        return vector_field_3d_tree.make_vector_field_3d_tree(
            potential_source=str(f.get("potential", "0")), **box)
    return vector_field_3d_tree.make_vector_field_3d_tree(
        components_source=tuple(f.get("components", ["0", "0", "0"])), **box)


def _rebuild_vector_bench(data):
    f = data.get("formula", {})
    rows = [(str(r[0]), str(r[1])) for r in f.get("rows", []) if len(r) >= 2]
    if not rows:
        raise ValueError("preset banc sans vecteur")
    return bench_tree.make_vector_bench_tree(
        rows, allowed_params=tuple(f.get("allowed_params", [])))


# --------------------------------------------------------------------------- #
# Spec
# --------------------------------------------------------------------------- #
class OpsSpec:
    """Everything the factory needs to emit one kind's six operators."""

    __slots__ = ("idn", "finder", "rebuild", "object_name", "default_name",
                 "snapshot", "save", "load", "apply_fn", "delete", "find",
                 "reinstall", "not_active")

    def __init__(self, *, idn, finder, rebuild, object_name, default_name,
                 snapshot, save, load, apply_fn, delete, find, reinstall,
                 not_active):
        self.idn = idn                  # bl_idname infix ("" / "vector_" …)
        self.finder = finder            # name of operators._active_* function
        self.rebuild = rebuild          # data -> node_group
        self.object_name = object_name  # data -> str (renames the object)
        self.default_name = default_name  # expr -> str (save dialog prefill)
        self.snapshot = snapshot
        self.save = save
        self.load = load
        self.apply_fn = apply_fn
        self.delete = delete
        self.find = find
        self.reinstall = reinstall
        self.not_active = not_active    # error message when nothing active


def _short(expr, n=40):
    expr = str(expr)
    return expr if len(expr) < n else expr[:n - 3] + "…"


SPECS = [
    OpsSpec(
        idn="", finder="_active_realfn_modifier",
        rebuild=_rebuild_scalar,
        object_name=lambda d: f"y = {d.get('formula', {}).get('expr', '?')}",
        default_name=lambda e: f"y = {_short(e)}",
        snapshot=presets.snapshot_modifier, save=presets.save_preset,
        load=presets.load_preset, apply_fn=presets.apply_preset_to_modifier,
        delete=presets.delete_preset, find=presets.find_preset_file,
        reinstall=builtin_presets.reinstall_builtins,
        not_active="Aucune courbe RealFn active",
    ),
    OpsSpec(
        idn="vector_", finder="_active_vector_realfn_modifier",
        rebuild=_rebuild_vector,
        object_name=lambda d: f"F(t) = {d.get('formula', {}).get('expr', '?')}",
        default_name=lambda e: f"F(t) = {_short(e)}",
        snapshot=presets.snapshot_vector_modifier,
        save=presets.save_vector_preset, load=presets.load_vector_preset,
        apply_fn=presets.apply_vector_preset_to_modifier,
        delete=presets.delete_vector_preset,
        find=presets.find_vector_preset_file,
        reinstall=builtin_presets.reinstall_vector_builtins,
        not_active="Aucune courbe vectorielle RealFn active",
    ),
    OpsSpec(
        idn="surface_", finder="_active_surface_realfn_modifier",
        rebuild=_rebuild_surface,
        object_name=lambda d: f"z = {d.get('formula', {}).get('expr', '?')}",
        default_name=lambda e: f"z = {_short(e)}",
        snapshot=presets.snapshot_surface_modifier,
        save=presets.save_surface_preset, load=presets.load_surface_preset,
        apply_fn=presets.apply_surface_preset_to_modifier,
        delete=presets.delete_surface_preset,
        find=presets.find_surface_preset_file,
        reinstall=builtin_presets.reinstall_surface_builtins,
        not_active="Aucune surface RealFn active",
    ),
    OpsSpec(
        idn="parametric_surface_",
        finder="_active_parametric_surface_realfn_modifier",
        rebuild=_rebuild_parametric,
        object_name=lambda d: d.get("name", "Surface paramétrée"),
        default_name=lambda e: "Surface paramétrée",
        snapshot=presets.snapshot_parametric_surface_modifier,
        save=presets.save_parametric_surface_preset,
        load=presets.load_parametric_surface_preset,
        apply_fn=presets.apply_parametric_surface_preset_to_modifier,
        delete=presets.delete_parametric_surface_preset,
        find=presets.find_parametric_surface_preset_file,
        reinstall=builtin_presets.reinstall_parametric_surface_builtins,
        not_active="Aucune surface paramétrée RealFn active",
    ),
    OpsSpec(
        idn="scalar_field_3d_",
        finder="_active_scalar_field_3d_realfn_modifier",
        rebuild=_rebuild_scalar_field_3d,
        object_name=lambda d: d.get("name", "Champ scalaire 3D"),
        default_name=lambda e: "Champ scalaire 3D",
        snapshot=presets.snapshot_scalar_field_3d_modifier,
        save=presets.save_scalar_field_3d_preset,
        load=presets.load_scalar_field_3d_preset,
        apply_fn=presets.apply_scalar_field_3d_preset_to_modifier,
        delete=presets.delete_scalar_field_3d_preset,
        find=presets.find_scalar_field_3d_preset_file,
        reinstall=builtin_presets.reinstall_scalar_field_3d_builtins,
        not_active="Aucun champ scalaire 3D RealFn actif",
    ),
    OpsSpec(
        idn="vector_field_3d_",
        finder="_active_vector_field_3d_realfn_modifier",
        rebuild=_rebuild_vector_field_3d,
        object_name=lambda d: d.get("name", "Champ de vecteurs 3D"),
        default_name=lambda e: "Champ de vecteurs 3D",
        snapshot=presets.snapshot_vector_field_3d_modifier,
        save=presets.save_vector_field_3d_preset,
        load=presets.load_vector_field_3d_preset,
        apply_fn=presets.apply_vector_field_3d_preset_to_modifier,
        delete=presets.delete_vector_field_3d_preset,
        find=presets.find_vector_field_3d_preset_file,
        reinstall=builtin_presets.reinstall_vector_field_3d_builtins,
        not_active="Aucun champ de vecteurs 3D RealFn actif",
    ),
    OpsSpec(
        idn="vector_bench_",
        finder="_active_vector_bench_realfn_modifier",
        rebuild=_rebuild_vector_bench,
        object_name=lambda d: d.get("name", "Banc de vecteurs"),
        default_name=lambda e: "Banc de vecteurs",
        snapshot=presets.snapshot_vector_bench_modifier,
        save=presets.save_vector_bench_preset,
        load=presets.load_vector_bench_preset,
        apply_fn=presets.apply_vector_bench_preset_to_modifier,
        delete=presets.delete_vector_bench_preset,
        find=presets.find_vector_bench_preset_file,
        reinstall=builtin_presets.reinstall_vector_bench_builtins,
        not_active="Aucun banc de vecteurs RealFn actif",
    ),
]


# --------------------------------------------------------------------------- #
# Operator method bodies (closures over the spec)
# --------------------------------------------------------------------------- #
def _save_execute(spec):
    def execute(self, context):
        mod = _active(spec.finder, context)
        if mod is None:
            self.report({"ERROR"}, spec.not_active)
            return {"CANCELLED"}
        if not self.name.strip():
            self.report({"ERROR"}, "Le nom du preset ne peut pas être vide")
            return {"CANCELLED"}
        try:
            data = spec.snapshot(mod, self.name.strip())
            fp = spec.save(data, overwrite=self.overwrite)
        except FileExistsError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        except (OSError, ValueError) as exc:
            self.report({"ERROR"}, f"Erreur d'écriture : {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Preset enregistré : {fp.name}")
        return {"FINISHED"}
    return execute


def _save_invoke(spec):
    def invoke(self, context, event):
        mod = _active(spec.finder, context)
        if mod is not None:
            expr = str(mod.node_group.get("realfn_expr", "preset"))
            self.name = spec.default_name(expr)
        return context.window_manager.invoke_props_dialog(self, width=400)
    return invoke


def _apply_execute(spec):
    def execute(self, context):
        mod = _active(spec.finder, context)
        if mod is None:
            self.report({"ERROR"}, spec.not_active)
            return {"CANCELLED"}
        try:
            data = spec.load(self.preset_path)
        except (OSError, ValueError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        try:
            new_nt = spec.rebuild(data)
        except ValueError as exc:
            self.report({"ERROR"}, f"Construction depuis preset : {exc}")
            return {"CANCELLED"}
        old_nt = mod.node_group
        mod.node_group = new_nt
        from .compiler import release_tree
        release_tree(old_nt, keep=new_nt)
        obj = context.active_object
        if obj is not None:
            obj.name = spec.object_name(data)
        report = spec.apply_fn(data, mod)
        # Viewport refresh (Blender 5.1 IDProperty propagation, see the
        # note this pattern came from in the old per-kind operators).
        if obj is not None:
            mod.node_group = mod.node_group
            try:
                obj.update_tag(refresh={'OBJECT'})
            except TypeError:
                obj.update_tag()
        # Keep the in-panel editable fields in sync after a preset rebuild
        # (bench rows + the generic formula editor; each is a no-op for the
        # other's kind).
        if obj is not None:
            try:
                from . import bench_props, edit_props
                bench_props.sync_from_tree(obj)
                edit_props.sync_from_tree(obj)
            except Exception:
                pass
        self.report(
            {"INFO"},
            f"« {data.get('name', '?')} » appliqué — "
            f"{report['applied']} valeur(s) restaurée(s)"
            + (f", {report['skipped']} ignorée(s)"
               if report['skipped'] else ""),
        )
        return {"FINISHED"}
    return execute


def _delete_execute(spec):
    def execute(self, context):
        if not self.preset_name:
            self.report({"ERROR"}, "Aucun preset sélectionné")
            return {"CANCELLED"}
        if spec.delete(self.preset_name):
            self.report({"INFO"}, f"Preset supprimé : {self.preset_name}")
            return {"FINISHED"}
        self.report({"ERROR"}, f"Preset introuvable : {self.preset_name}")
        return {"CANCELLED"}
    return execute


def _import_execute(spec):
    def execute(self, context):
        if not self.filepath:
            self.report({"ERROR"}, "Aucun fichier sélectionné")
            return {"CANCELLED"}
        try:
            data = spec.load(self.filepath)
            fp = spec.save(data, overwrite=True)
        except (OSError, ValueError) as exc:
            self.report({"ERROR"}, f"Import impossible : {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Preset importé : {fp.name}")
        return {"FINISHED"}
    return execute


def _export_invoke(spec):
    def invoke(self, context, event):
        if not self.preset_name:
            self.report({"ERROR"}, "Aucun preset sélectionné")
            return {"CANCELLED"}
        self.filepath = presets._slugify(self.preset_name) + ".json"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
    return invoke


def _export_execute(spec):
    def execute(self, context):
        if not self.filepath:
            return {"CANCELLED"}
        try:
            src = spec.find(self.preset_name)
            if src is None:
                raise OSError(f"Preset introuvable : {self.preset_name}")
            data = spec.load(src)
            dst = Path(self.filepath)
            with dst.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except (OSError, ValueError) as exc:
            self.report({"ERROR"}, f"Export impossible : {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Preset exporté : {dst.name}")
        return {"FINISHED"}
    return execute


def _reinstall_execute(spec):
    def execute(self, context):
        try:
            n = spec.reinstall()
        except OSError as exc:
            self.report({"ERROR"}, f"Réinstallation impossible : {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"{n} preset(s) intégré(s) (ré)installé(s)")
        return {"FINISHED"}
    return execute


def _fileselect_invoke(self, context, event):
    context.window_manager.fileselect_add(self)
    return {"RUNNING_MODAL"}


def _confirm_invoke(self, context, event):
    return context.window_manager.invoke_confirm(self, event)


def _save_poll(spec):
    return classmethod(lambda cls, context: _active(spec.finder, context)
                       is not None)


# --------------------------------------------------------------------------- #
# Class factory
# --------------------------------------------------------------------------- #
def _make_class(name, bl_idname, bl_label, bl_description, bl_options,
                annotations, methods):
    ns = {
        "bl_idname": bl_idname,
        "bl_label": bl_label,
        "bl_description": bl_description,
        "bl_options": bl_options,
        "__annotations__": dict(annotations),
    }
    ns.update(methods)
    return type(name, (bpy.types.Operator,), ns)


_S = bpy.props.StringProperty
_B = bpy.props.BoolProperty


def build(spec: OpsSpec) -> list:
    """Return the six operator classes for one kind."""
    idn = spec.idn
    cap = "".join(p.capitalize() for p in idn.split("_") if p)
    out = []

    # save -----------------------------------------------------------------
    out.append(_make_class(
        f"REALFN_OT_save_{idn}preset",
        f"realfn.save_{idn}preset",
        "Enregistrer comme preset…",
        "Enregistre l'état complet de l'objet actif sous un nom de preset",
        {"REGISTER"},
        {
            "name": _S(name="Nom du preset",
                       description="Nom affiché dans la liste",
                       default="Mon preset"),
            "overwrite": _B(name="Écraser si existe",
                            description="Remplace un preset du même nom",
                            default=True),
        },
        {
            "poll": _save_poll(spec),
            "invoke": _save_invoke(spec),
            "draw": lambda self, context: (self.layout.prop(self, "name"),
                                           self.layout.prop(self, "overwrite")),
            "execute": _save_execute(spec),
        },
    ))

    # apply ----------------------------------------------------------------
    out.append(_make_class(
        f"REALFN_OT_apply_{idn}preset",
        f"realfn.apply_{idn}preset",
        "Appliquer le preset",
        "Reconstruit l'objet actif depuis le preset et restaure ses valeurs",
        {"REGISTER", "UNDO"},
        {"preset_path": _S(name="Chemin du preset", subtype="FILE_PATH")},
        {
            "poll": _save_poll(spec),
            "execute": _apply_execute(spec),
        },
    ))

    # delete ---------------------------------------------------------------
    out.append(_make_class(
        f"REALFN_OT_delete_{idn}preset",
        f"realfn.delete_{idn}preset",
        "Supprimer le preset",
        "Supprime définitivement ce preset du dossier utilisateur",
        {"REGISTER"},
        {"preset_name": _S(name="Nom du preset à supprimer")},
        {
            "invoke": _confirm_invoke,
            "execute": _delete_execute(spec),
        },
    ))

    # import ---------------------------------------------------------------
    out.append(_make_class(
        f"REALFN_OT_import_{idn}preset",
        f"realfn.import_{idn}preset",
        "Importer un preset…",
        "Copier un fichier .json de preset dans le dossier utilisateur",
        {"REGISTER"},
        {
            "filepath": _S(subtype="FILE_PATH"),
            "filter_glob": _S(default="*.json", options={"HIDDEN"}),
        },
        {
            "invoke": _fileselect_invoke,
            "execute": _import_execute(spec),
        },
    ))

    # export ---------------------------------------------------------------
    out.append(_make_class(
        f"REALFN_OT_export_{idn}preset",
        f"realfn.export_{idn}preset",
        "Exporter le preset…",
        "Copier le preset sélectionné vers un emplacement de votre choix",
        {"REGISTER"},
        {
            "preset_name": _S(name="Nom du preset à exporter"),
            "filepath": _S(subtype="FILE_PATH"),
            "filter_glob": _S(default="*.json", options={"HIDDEN"}),
        },
        {
            "invoke": _export_invoke(spec),
            "execute": _export_execute(spec),
        },
    ))

    # reinstall ------------------------------------------------------------
    out.append(_make_class(
        f"REALFN_OT_reinstall_{idn}builtins",
        f"realfn.reinstall_{idn}builtins",
        "Réinstaller les presets intégrés",
        "(Ré)installe le catalogue de presets intégrés dans le dossier "
        "utilisateur",
        {"REGISTER"},
        {},
        {"execute": _reinstall_execute(spec)},
    ))

    return out


def build_all() -> list:
    """All 36 preset operator classes, ready to register."""
    classes = []
    for spec in SPECS:
        classes.extend(build(spec))
    return classes
