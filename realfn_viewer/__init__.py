"""
RealFn Viewer — visualise a real-valued function y = f(x) and its
tangent at an interactively-chosen basepoint x₀, entirely through
Geometry Nodes.

Architecture
------------
Everything visible in the viewport is computed by a Geometry Nodes
graph; SymPy is used only as a symbolic compiler that lowers the
user-typed formula into Math sub-graphs. As a consequence:

* the tangent slides in real time when the user scrubs x₀ (no Python
  in the per-frame loop);
* the formula and its derivative are computed once at object-creation
  time, then evaluated by the GPU at every viewport update.

User-facing flow
----------------
1. View 3D > N-panel > "RealFn" > "Créer une courbe…"
2. Type ``f(x)`` (e.g. ``sin(x)``, ``exp(-x**2/sigma**2)``,
   ``x**3 - 3*x``); declare any extra free parameters.
3. The viewport gets a mesh object showing the curve, the tangent
   line, and a sphere marking (x₀, f(x₀)).
4. Open the modifier panel (or the "Paramètres du modifier" sub-panel
   in the side bar) to scrub x₀, x_min, x_max, and the parameters.

Security
--------
User-typed formulas are passed through a strict AST whitelist before
SymPy ever sees them (see :mod:`sympy_parser`). Arbitrary Python
execution via ``__import__``, ``open``, ``exec`` and the like is
blocked at parse time.
"""

from __future__ import annotations

__version__ = "5.5.0"

import bpy

from . import (bench_props, builtin_presets, edit_props, i18n, memorize,
               operators, panel, sync,
               materials_presets as _mat_presets,
               materials_panel)


# Display preferences live on the WindowManager (a "scratch" datablock
# that doesn't get saved to .blend). Toggle persists for the duration
# of the Blender session; users who want it saved per-file can change
# this to ``bpy.types.Scene`` instead.
def _register_display_props():
    bpy.types.WindowManager.realfn_display_latex = bpy.props.BoolProperty(
        name="Format LaTeX",
        description=(
            "Afficher les formules en LaTeX (\\sin{x}, x^{2}, …) "
            "plutôt qu'en notation SymPy texte (sin(x), x**2, …). "
            "Le LaTeX se copie sans modification dans un éditeur "
            "scientifique"
        ),
        default=False,
    )
    # Scene.realfn_sync_x0 is owned by :mod:`sync` (registered alongside
    # the depsgraph handler that consumes it) — keeping the toggle's
    # lifetime tied to the handler's avoids races where the handler
    # would read a freshly-removed property.


def _unregister_display_props():
    if hasattr(bpy.types.WindowManager, "realfn_display_latex"):
        del bpy.types.WindowManager.realfn_display_latex


def _auto_install_builtins():
    """First-run setup: if the user's presets directory is empty,
    write the built-in catalog there so the panel is populated
    immediately. Returns None for ``bpy.app.timers`` (the timer
    fires once and then stops).

    Why a deferred timer rather than a direct call in ``register()``?
    ``bpy.utils.extension_path_user`` can be flaky inside ``register``
    on certain Blender startup paths (the extension manager may not
    yet have finalised the per-user data location). Deferring one
    tick past the first idle dodges that whole class of issue at
    zero cost — by the time the timer fires, Blender is fully up.

    Errors are swallowed silently: a missing/unwritable presets
    directory is a degraded mode but not a reason to break the
    rest of the extension. The user can still install builtins
    manually via the "Réinstaller les builtin" button once the
    underlying problem (permissions, disk full…) is fixed.
    """
    try:
        from . import presets
        pdir = presets._presets_dir()
        existing = list(pdir.glob("*.json"))
        if not existing:
            n = builtin_presets.reinstall_builtins()
            print(f"[RealFn] First-run setup: installed {n} builtin presets")
    except Exception as exc:
        # Quietly degraded — log to console but don't raise. Users
        # rarely look at the console; reflecting this would also
        # be tricky from a timer with no context.
        print(f"[RealFn] Auto-install builtins skipped: {exc}")
    # Same treatment for the *vector* preset catalogue. Independent
    # try/except so a problem with one doesn't block the other —
    # users get whatever can be installed and a clear console log
    # for whatever can't.
    try:
        from . import presets
        vdir = presets._vector_presets_dir()
        existing_v = list(vdir.glob("*.json"))
        if not existing_v:
            n_v = builtin_presets.reinstall_vector_builtins()
            print(f"[RealFn] First-run setup: installed {n_v} "
                   f"vector builtin presets")
    except Exception as exc:
        print(f"[RealFn] Auto-install vector builtins skipped: {exc}")
    # Explicit-surface (z = f(x, y)) catalogue. Same idempotent pattern:
    # only install if the user directory is empty, so we don't clobber
    # the user's edits or re-add files they deliberately deleted.
    try:
        from . import presets
        sdir = presets._surface_presets_dir()
        if not list(sdir.glob("*.json")):
            n_s = builtin_presets.reinstall_surface_builtins()
            print(f"[RealFn] First-run setup: installed {n_s} "
                   f"surface builtin presets")
    except Exception as exc:
        print(f"[RealFn] Auto-install surface builtins skipped: {exc}")
    # Parametric-surface catalogue (sphere, torus, helicoid, …).
    try:
        from . import presets
        psdir = presets._parametric_surface_presets_dir()
        if not list(psdir.glob("*.json")):
            n_ps = builtin_presets.reinstall_parametric_surface_builtins()
            print(f"[RealFn] First-run setup: installed {n_ps} "
                   f"parametric surface builtin presets")
    except Exception as exc:
        print(f"[RealFn] Auto-install parametric surface builtins skipped: {exc}")
    # 3D scalar field catalogue (potentiel coulombien, gaussienne 3D, …).
    try:
        from . import presets
        sf3ddir = presets._scalar_field_3d_presets_dir()
        if not list(sf3ddir.glob("*.json")):
            n_sf3d = builtin_presets.reinstall_scalar_field_3d_builtins()
            print(f"[RealFn] First-run setup: installed {n_sf3d} "
                   f"3D scalar field builtin presets")
    except Exception as exc:
        print(f"[RealFn] Auto-install 3D scalar field builtins skipped: {exc}")
    # 3D vector field catalogue (rotation, force coulombienne, gradients…).
    try:
        from . import presets
        vf3ddir = presets._vector_field_3d_presets_dir()
        if not list(vf3ddir.glob("*.json")):
            n_vf3d = builtin_presets.reinstall_vector_field_3d_builtins()
            print(f"[RealFn] First-run setup: installed {n_vf3d} "
                   f"3D vector field builtin presets")
    except Exception as exc:
        print(f"[RealFn] Auto-install 3D vector field builtins skipped: {exc}")
    # Ensure the bundled "Ecrit" node group is in the .blend file so
    # users can plug it in anywhere (and it survives save/reload). The
    # 3D scalar field tree references this group, so this also doubles
    # as a robustness check for that pipeline.
    try:
        from . import ecrit
        ecrit.get_ecrit_node_group()
    except Exception as exc:
        print(f"[RealFn] Auto-install Ecrit node group skipped: {exc}")
    # Same idempotent installation for the "Vecteur" node group, which
    # the vector_field_3d tree relies on for its per-point arrows
    # (and which the vector_tree kinematic arrows also use). Without
    # this, the very first ``make_vector_field_3d_tree`` call would
    # have to create it implicitly — better to make sure it's there
    # from the start.
    try:
        from . import vecteur
        vecteur.get_vecteur_node_group()
    except Exception as exc:
        print(f"[RealFn] Auto-install Vecteur node group skipped: {exc}")
    return None  # timer fires once


def _on_language_changed(self, context):
    """Property ``update`` callback for the language preference.

    A module-level def with a LOCAL import — not a lambda closing over
    the module-global ``i18n``. Blender invokes property callbacks in
    a bare scope where the enclosing module's globals are not
    necessarily resolvable, so a lambda referencing ``i18n`` raised
    ``NameError: name 'i18n' is not defined`` (harmless — the panel's
    self-healing redraw still applied the language — but it spammed
    the console). Importing inside the function sidesteps that."""
    from . import i18n
    i18n.schedule_apply_language()


class REALFN_AddonPreferences(bpy.types.AddonPreferences):
    """Add-on preferences — currently just the UI language, persisted
    by Blender's own preference saving."""

    bl_idname = __package__

    language: bpy.props.EnumProperty(
        name="Langue / Language",
        items=[
            ("FR", "Français", "Interface en français"),
            ("EN", "English", "Interface in English"),
        ],
        default="FR",
        update=_on_language_changed,
    )

    def draw(self, context):
        self.layout.prop(self, "language", expand=True)


def register():
    bpy.utils.register_class(REALFN_AddonPreferences)
    for c in operators.classes:
        bpy.utils.register_class(c)
    for c in panel.classes:
        bpy.utils.register_class(c)
    for c in _mat_presets.classes:
        bpy.utils.register_class(c)
    bpy.utils.register_class(materials_panel.REALFN_MAT_PT_panel)
    bpy.types.Scene.realfn_materials = bpy.props.PointerProperty(
        type=_mat_presets.RealFnMaterialsProperties
    )
    bench_props.register()
    edit_props.register()
    _register_display_props()
    # Register the x₀ propagation handler last — it relies on the
    # ``realfn_sync_x0`` scene property existing, and the operator
    # classes being registered (it consults their node-group
    # metadata to identify RealFn modifiers).
    sync.register()
    # The save_pre handler that snapshots RealFn modifiers into the
    # .blend on every save. Idempotent ``register`` so a script-reload
    # mid-session doesn't end up with the handler registered twice.
    memorize.register()
    # Schedule first-run setup for after Blender's startup is fully
    # done. ``first_interval=1.0`` (seconds) gives Blender time to
    # finalise its data paths; the timer then runs once and returns
    # None to deregister itself.
    bpy.app.timers.register(_auto_install_builtins, first_interval=1.0)
    # If the saved preference is English, relabel once everything is
    # registered (deferred so registration completes first).
    if i18n.get_lang() != "FR":
        i18n.schedule_apply_language()


def unregister():
    # Tear down in reverse order of register().
    memorize.unregister()
    sync.unregister()
    _unregister_display_props()
    edit_props.unregister()
    bench_props.unregister()
    if hasattr(bpy.types.Scene, "realfn_materials"):
        del bpy.types.Scene.realfn_materials
    bpy.utils.unregister_class(materials_panel.REALFN_MAT_PT_panel)
    for c in reversed(_mat_presets.classes):
        bpy.utils.unregister_class(c)
    for c in reversed(panel.classes):
        bpy.utils.unregister_class(c)
    for c in reversed(operators.classes):
        bpy.utils.unregister_class(c)
    bpy.utils.unregister_class(REALFN_AddonPreferences)
