"""
Blender operators for creating and editing real-function viewer objects.

Two operators:

* :class:`REALFN_OT_create` — popup that takes the user's f(x), parses
  it safely, builds a Geometry Nodes tree (see :mod:`tree`), spawns a
  mesh object backed by that tree, and selects it.

* :class:`REALFN_OT_edit` — for an already-created object, lets the
  user retype the formula and rebuild the tree in place. The object's
  modifier is rebound to the new tree, and the old tree is left
  orphaned (Blender purges orphan datablocks on .blend save).
"""

from __future__ import annotations

import bpy

from . import (bench_tree, builtin_presets, compiler, default_materials,
                i18n, memorize, modifier_inputs, parametric_surface_tree,
                preset_ops, presets,
                scalar_field_3d_tree, surface_tree, sympy_parser, tree,
                vector_field_3d_tree, vector_tree)


def _spawn_object(context, nt, name: str):
    """Create a mesh object hosting ``nt`` as a Geometry Nodes modifier."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    context.collection.objects.link(obj)
    mod = obj.modifiers.new(name="RealFnViewer", type="NODES")
    mod.node_group = nt
    # Localise the socket tooltips to the active language. Lazy import
    # avoids a circular dependency (panel imports operators at load).
    from . import panel
    panel.localize_socket_tooltips(nt)
    for o in context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    # Pre-fill the in-panel editable formula fields (no-op for the bench,
    # which carries its own editor).
    try:
        from . import edit_props
        edit_props.sync_from_tree(obj)
    except Exception:
        pass
    return obj


_REALFN_KINDS = frozenset({
    "scalar", "vector", "surface", "parametric_surface",
    "scalar_field_3d", "vector_field_3d", "vector_bench",
})


def _active_realfn_modifier(context):
    """Return the active object's RealFn modifier (any kind), or None.

    Detection uses ``realfn_kind`` metadata as primary method (robust
    against Blender auto-suffixing tree names with ".001" on duplicate),
    then falls back to name-prefix matching for legacy trees built before
    the metadata was stashed. For kind-specific queries, use the
    ``_active_<kind>_realfn_modifier`` helpers instead.
    """
    obj = context.active_object
    if obj is None:
        return None
    for m in obj.modifiers:
        if m.type != "NODES" or m.node_group is None:
            continue
        ng = m.node_group
        # Primary: metadata stash present on every tree since v2.
        if ng.get("realfn_kind") in _REALFN_KINDS:
            return m
        # Fallback: name-prefix check for legacy trees without metadata.
        name = ng.name
        if (name.startswith(tree.TREE_PREFIX)
                or name.startswith(vector_tree.VECTOR_TREE_PREFIX)
                or name.startswith(surface_tree.SURFACE_TREE_PREFIX)
                or name.startswith(
                    parametric_surface_tree.PARAMETRIC_SURFACE_TREE_PREFIX)
                or name.startswith(
                    scalar_field_3d_tree.SCALAR_FIELD_3D_TREE_PREFIX)
                or name.startswith(
                    vector_field_3d_tree.VECTOR_FIELD_3D_TREE_PREFIX)
                or name.startswith(bench_tree.BENCH_TREE_PREFIX)):
            return m
    return None


def _active_scalar_realfn_modifier(context):
    """Return the active modifier only if it's a *scalar* RealFn one.

    Used by the scalar parameters panel (REALFN_PT_params) so it
    doesn't try to draw scalar-specific controls (visibility per
    piece, Taylor formulas…) when the user has a vector function
    selected.
    """
    mod = _active_realfn_modifier(context)
    if mod is None:
        return None
    kind = mod.node_group.get("realfn_kind")
    # Legacy trees built before ``realfn_kind`` was stashed are
    # implicitly scalar — preserve that behaviour by treating a
    # missing key as scalar.
    if kind is None or kind == "scalar":
        return mod
    return None


def _active_vector_realfn_modifier(context):
    """Return the active modifier only if it's a *vector* RealFn one.

    Used by the vector parameters panel — symmetric to
    :func:`_active_scalar_realfn_modifier`.
    """
    mod = _active_realfn_modifier(context)
    if mod is None:
        return None
    if mod.node_group.get("realfn_kind") == "vector":
        return mod
    return None


def _active_surface_realfn_modifier(context):
    """Return the active modifier only if it's an *explicit surface*
    z = f(x, y) RealFn one."""
    mod = _active_realfn_modifier(context)
    if mod is None:
        return None
    if mod.node_group.get("realfn_kind") == "surface":
        return mod
    return None


def _active_parametric_surface_realfn_modifier(context):
    """Return the active modifier only if it's a *parametric surface*
    (x(u,v), y(u,v), z(u,v)) RealFn one."""
    mod = _active_realfn_modifier(context)
    if mod is None:
        return None
    if mod.node_group.get("realfn_kind") == "parametric_surface":
        return mod
    return None


def _active_scalar_field_3d_realfn_modifier(context):
    """Return the active modifier only if it's a 3D scalar field one."""
    mod = _active_realfn_modifier(context)
    if mod is None:
        return None
    if mod.node_group.get("realfn_kind") == "scalar_field_3d":
        return mod
    return None


def _active_vector_field_3d_realfn_modifier(context):
    """Return the active modifier only if it's a 3D vector field one.

    Used by the vector field 3D parameters panel and by the preset
    operators so they don't fire (or grey out their UI) when the
    active object is a different kind of RealFn function. Mirrors the
    pattern of the five other ``_active_<kind>_realfn_modifier``
    helpers above.
    """
    mod = _active_realfn_modifier(context)
    if mod is None:
        return None
    if mod.node_group.get("realfn_kind") == "vector_field_3d":
        return mod
    return None


def _active_vector_bench_realfn_modifier(context):
    """Return the active modifier only if it's a *vector bench* RealFn one.

    Used by the bench preset operators / sub-panel so they only fire when
    a bench is the active object."""
    mod = _active_realfn_modifier(context)
    if mod is None:
        return None
    if mod.node_group.get("realfn_kind") == "vector_bench":
        return mod
    return None


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #
class REALFN_OT_create(bpy.types.Operator):
    """Create a new mesh object visualising y = f(x), its derivatives,
    and/or its Taylor polynomials around a scrubbable basepoint."""

    bl_idname = "realfn.create"
    bl_label = "Créer une courbe y = f(x)"
    bl_description = (
        "Saisir f(x) (SymPy-compatible) et choisir combien de dérivées "
        "successives f, f', f''… et combien de polynômes de Taylor "
        "T₁, T₂… tracer. Les paramètres et x₀ restent réglables "
        "dans le modifier après création"
    )
    bl_options = {"REGISTER", "UNDO"}

    expr: bpy.props.StringProperty(
        name="f(x)",
        description="Expression mathématique en x (et paramètres libres)",
        default="sin(x)",
    )
    allowed_params: bpy.props.StringProperty(
        name="Paramètres libres",
        description=(
            "Liste de symboles, séparés par des virgules, autorisés "
            "dans la formule. Chacun deviendra un slider du modifier"
        ),
        default="a,b,c,omega,sigma",
    )
    derivative_order: bpy.props.IntProperty(
        name="Ordre max des dérivées",
        description=(
            "0 = tracer seulement f. 1 = ajouter f'. k = ajouter f, "
            "f', …, f^(k) comme courbes superposées avec chacune son "
            "épaisseur réglable"
        ),
        default=1, min=0, soft_max=4, max=10,
    )
    taylor_order: bpy.props.IntProperty(
        name="Ordre max des polynômes de Taylor",
        description=(
            "0 = aucun polynôme de Taylor. n ≥ 1 = ajouter T₁, T₂, …, "
            "Tₙ comme courbes superposées, centrés en x₀ "
            "(scrubbable). Au-delà de l'ordre 8-10, le calcul "
            "symbolique des dérivées f⁽ⁿ⁾ et la compilation des "
            "courbes peuvent prendre plusieurs secondes, surtout "
            "pour les fonctions rationnelles"
        ),
        default=1, min=0, soft_max=8, max=20,
    )
    x_min: bpy.props.FloatProperty(name="x min", default=-5.0)
    x_max: bpy.props.FloatProperty(name="x max", default=5.0)
    x0: bpy.props.FloatProperty(
        name="x₀", default=0.0,
        description="Position initiale du marqueur et centre des "
                    "polynômes de Taylor",
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=440)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "expr")
        col.prop(self, "allowed_params")
        row = layout.row(align=True)
        row.prop(self, "derivative_order")
        row.prop(self, "taylor_order")
        row = layout.row(align=True)
        row.prop(self, "x_min")
        row.prop(self, "x_max")
        layout.prop(self, "x0")

        # Live parsing + count-of-pieces feedback.
        try:
            params = self._params_tuple()
            f = sympy_parser.parse_expression(self.expr)
            free = sorted(
                s.name for s in f.free_symbols if s.name != "x"
            )
            unknown = [s for s in free if s not in params]
            box = layout.box()
            if unknown:
                box.label(
                    text=(f"Symboles non autorisés : "
                          f"{', '.join(unknown)}"),
                    icon="ERROR",
                )
                box.label(
                    text=("Ajoutez-les à 'Paramètres libres' "
                          "pour les exposer comme sliders"),
                    icon="INFO",
                )
            else:
                if free:
                    box.label(
                        text=i18n.tr("Paramètres détectés : ") + ", ".join(free),
                        icon="DRIVER",
                    )
                # Tell the user how many curves will be drawn so the
                # consequences of derivative_order / taylor_order are
                # obvious before clicking OK.
                n_pieces = self.derivative_order + 1 + self.taylor_order
                box.label(
                    text=f"{n_pieces} " + i18n.tr("courbe(s) tracée(s)"),
                    icon="GRAPH",
                )
                if self.taylor_order > 0:
                    box.label(
                        text=i18n.tr("Polynômes de Taylor centrés en x₀ "
                                      "(scrubbable)"),
                        icon="DRIVER_TRANSFORM",
                    )
        except ValueError as exc:
            layout.box().label(text=str(exc), icon="ERROR")

    def _params_tuple(self):
        return tuple(
            s.strip() for s in self.allowed_params.split(",") if s.strip()
        )

    def execute(self, context):
        try:
            nt = tree.make_realfn_tree(
                self.expr,
                allowed_params=self._params_tuple(),
                derivative_order=self.derivative_order,
                taylor_order=self.taylor_order,
                x_default_range=(self.x_min, self.x_max),
                x0_default=self.x0,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _spawn_object(context, nt, f"y = {self.expr}")
        n_pieces = self.derivative_order + 1 + self.taylor_order
        self.report({"INFO"},
                    f"{n_pieces} courbe(s) tracée(s) pour y = {self.expr}")
        return {"FINISHED"}


# --------------------------------------------------------------------------- #
# Edit (rebuild from new expression)
# --------------------------------------------------------------------------- #
class REALFN_OT_edit(bpy.types.Operator):
    """Re-parse the formula and rebuild the Geometry Nodes tree of the
    active RealFn object in place.

    Lets the user change the formula *and* the derivative / Taylor
    orders. The object keeps its identity (and its outliner position,
    materials, etc.); only the node tree is replaced. The previous
    tree is left as an orphan datablock — Blender will purge it on
    the next File > Clean Up.
    """

    bl_idname = "realfn.edit"
    bl_label = "Modifier la fonction"
    bl_description = (
        "Reparse la formule et reconstruit l'arbre Geometry Nodes "
        "sur l'objet actif. Permet de changer la formule, les "
        "paramètres autorisés et le nombre de dérivées / polynômes "
        "de Taylor à tracer"
    )
    bl_options = {"REGISTER", "UNDO"}

    expr: bpy.props.StringProperty(name="f(x)", default="sin(x)")
    allowed_params: bpy.props.StringProperty(
        name="Paramètres libres", default="a,b,c,omega,sigma",
    )
    derivative_order: bpy.props.IntProperty(
        name="Ordre max des dérivées",
        default=1, min=0, soft_max=4, max=10,
    )
    taylor_order: bpy.props.IntProperty(
        name="Ordre max des polynômes de Taylor",
        default=1, min=0, soft_max=8, max=20,
    )

    @classmethod
    def poll(cls, context):
        return _active_realfn_modifier(context) is not None

    def invoke(self, context, event):
        # Pre-fill the dialog with the current expression and orders so
        # the user can tweak instead of retyping from scratch.
        mod = _active_realfn_modifier(context)
        if mod is not None:
            nt = mod.node_group
            self.expr = str(nt.get("realfn_expr", "sin(x)"))
            params = nt.get("realfn_params", [])
            if params:
                self.allowed_params = ",".join(str(p) for p in params)
            # ``get`` on a missing ID property returns None — fall back
            # to legacy defaults for trees built by RealFn < 1.1.0
            # which didn't stash the orders.
            d = nt.get("realfn_derivative_order")
            self.derivative_order = int(d) if d is not None else 1
            t = nt.get("realfn_taylor_order")
            self.taylor_order = int(t) if t is not None else 0
        return context.window_manager.invoke_props_dialog(self, width=440)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "expr")
        col.prop(self, "allowed_params")
        row = layout.row(align=True)
        row.prop(self, "derivative_order")
        row.prop(self, "taylor_order")
        try:
            params = self._params_tuple()
            f = sympy_parser.parse_expression(self.expr)
            free = sorted(s.name for s in f.free_symbols if s.name != "x")
            unknown = [s for s in free if s not in params]
            box = layout.box()
            if unknown:
                box.label(
                    text=i18n.tr("Symboles non autorisés : ") + ", ".join(unknown),
                    icon="ERROR",
                )
            else:
                if free:
                    box.label(
                        text=i18n.tr("Paramètres détectés : ") + ", ".join(free),
                        icon="DRIVER",
                    )
                n_pieces = self.derivative_order + 1 + self.taylor_order
                box.label(text=f"{n_pieces} " + i18n.tr("courbe(s) tracée(s)"),
                          icon="GRAPH")
        except ValueError as exc:
            layout.box().label(text=str(exc), icon="ERROR")

    def _params_tuple(self):
        return tuple(
            s.strip() for s in self.allowed_params.split(",") if s.strip()
        )

    def execute(self, context):
        mod = _active_realfn_modifier(context)
        if mod is None:
            self.report({"ERROR"}, "Aucune courbe RealFn active")
            return {"CANCELLED"}
        old_nt = mod.node_group
        # Inherit x_min, x_max, x_0 from the current modifier so the
        # rebuild doesn't reset what the user already scrolled to.
        xmin, xmax, x0 = -5.0, 5.0, 0.0
        for item in old_nt.interface.items_tree:
            if getattr(item, "in_out", None) != "INPUT":
                continue
            try:
                v = float(modifier_inputs.get_value(mod, item.identifier))
            except (TypeError, ValueError):
                continue
            if item.name == "x min":
                xmin = v
            elif item.name == "x max":
                xmax = v
            elif item.name == "x_0":
                x0 = v

        try:
            new_nt = tree.make_realfn_tree(
                self.expr,
                allowed_params=self._params_tuple(),
                derivative_order=self.derivative_order,
                taylor_order=self.taylor_order,
                x_default_range=(xmin, xmax),
                x0_default=x0,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        old_nt = mod.node_group
        mod.node_group = new_nt
        compiler.release_tree(old_nt, keep=new_nt)
        obj = context.active_object
        if obj is not None:
            obj.name = f"y = {self.expr}"
        n_pieces = self.derivative_order + 1 + self.taylor_order
        self.report({"INFO"},
                    f"Reconstruite : {n_pieces} courbe(s) pour y = {self.expr}")
        return {"FINISHED"}


# --------------------------------------------------------------------------- #
# Bulk visibility operators
# --------------------------------------------------------------------------- #
# Three operators that flip the ``Visible · <label>`` booleans of the
# active RealFn modifier in bulk. They share a tiny piece of logic
# (locate the visibility sockets, apply a transform) which is factored
# out into the ``_apply_visibility_change`` helper below.
#
# A note on the depsgraph: changing an IDProperty on a modifier doesn't
# always trigger an automatic re-evaluation — different Blender builds
# behave inconsistently here. We call ``obj.update_tag()`` after
# mutating the sockets so the viewport refresh is guaranteed.

def _visibility_items(modifier):
    """Yield ``(item, identifier, current_value)`` for each Visible socket.

    ``item`` is the ``NodeTreeInterfaceSocketBool`` instance (carries the
    label "Visible · f", the socket type, etc.); ``identifier`` is the
    string key Blender uses to address it in the modifier's IDProperty
    dict; ``current_value`` is the bool currently stored.

    Note on the storage format: Blender stores ``NodeSocketBool`` values
    as integers ``0`` / ``1`` inside the modifier's IDProperty dict —
    *not* as Python ``bool``. We cast through ``int`` first then ``bool``
    so the truth check is robust regardless of which type the build is
    handing us back.
    """
    nt = modifier.node_group
    for item in nt.interface.items_tree:
        if getattr(item, "in_out", None) != "INPUT":
            continue
        if not item.name.startswith("Visible · "):
            continue
        # Bool sockets read back as bool (5.1+) or int (earlier builds)
        # — ``bool(x)`` normalises both.
        value = modifier_inputs.get_value(modifier, item.identifier)
        if value is None:
            value = getattr(item, "default_value", True)
        current = bool(value)
        yield item, item.identifier, current


def _apply_visibility_change(context, transform):
    """Apply ``transform(current_bool) -> new_bool`` to every Visible socket
    of the active modifier. Returns the count of sockets actually modified.

    Several Blender-isms make this trickier than ``mod[id] = value``:

    1. **Boolean storage type**: Blender stores ``NodeSocketBool`` values
       as integer 0/1 in the modifier's IDProperty dict. Writing a
       Python ``bool`` directly works on most builds but isn't the
       documented contract; we write ``int(new_value)`` for portability.

    2. **Depsgraph notification**: changing an IDProperty doesn't
       automatically tag the object's modifier stack for re-evaluation
       on every Blender build. ``obj.update_tag(refresh={'OBJECT'})``
       is the most reliable way to force a viewport refresh on
       Geometry Nodes modifiers in 4.x+ — a bare ``update_tag()``
       sometimes only invalidates transform-level caches.

    3. **Modifier-property poke**: as a belt-and-suspenders against
       any remaining build that doesn't honour update_tag for this,
       we also flip ``show_viewport`` off-then-on, which always
       forces a full re-evaluation.
    """
    mod = _active_realfn_modifier(context)
    if mod is None:
        return 0
    n_changed = 0
    for _item, identifier, current in _visibility_items(mod):
        new_value = bool(transform(current))
        if new_value != current:
            # Write as a real Python ``bool``. Blender 5.1 hardened
            # IDProperty type checking — a Boolean IDProperty now
            # rejects ``int`` assignment with
            # ``TypeError: Cannot assign a 'int' value to the
            # existing 'Socket_N' Boolean IDProperty``. Earlier
            # versions accepted both transparently. ``bool`` is the
            # documented and now-required write type.
            if modifier_inputs.set_value(mod, identifier, new_value):
                n_changed += 1
    if n_changed > 0:
        obj = context.active_object
        if obj is not None:
            # ----------- The reliable refresh strategy ------------------
            # There is a well-known issue on Blender 4.x+ where writing
            # to a NodeSocketBool IDProperty of a Geometry Nodes
            # modifier *does* land in the modifier (the checkbox in
            # the panel flips, status reports the new value) but the
            # ``GeometryNodeSwitch`` consuming that socket is not
            # marked dirty — so the viewport keeps showing the old
            # geometry until the next time something else triggers a
            # rebuild (a transform, a scene update, etc.).
            #
            # Neither ``update_tag()`` nor toggling ``show_viewport``
            # forces a re-evaluation reliably for this case. The trick
            # that works on every 4.x build I've tested is to
            # **reassign the modifier's ``node_group``** to itself.
            # This causes Blender to re-bind every socket of the
            # modifier from scratch, which forces a full re-evaluation
            # of the node graph against the modifier's current
            # IDProperty values.
            nt = mod.node_group
            if nt is not None:
                mod.node_group = nt
            # As a safety net we also tag the object for object-data
            # update. On most builds the reassignment above is enough
            # all by itself, but ``update_tag`` is essentially free
            # and protects against future Blender quirks.
            try:
                obj.update_tag(refresh={'OBJECT'})
            except TypeError:
                # Older Blender builds don't accept the ``refresh``
                # kwarg — fall back to the bare call.
                obj.update_tag()
    return n_changed


class REALFN_OT_visible_all_on(bpy.types.Operator):
    """Show every curve of the active RealFn object."""

    bl_idname = "realfn.visible_all_on"
    bl_label = "Tout afficher"
    bl_description = "Coche toutes les cases 'Visible · …' du modifier"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_realfn_modifier(context) is not None

    def execute(self, context):
        n = _apply_visibility_change(context, lambda _: True)
        self.report({"INFO"},
                    f"{n} courbe(s) affichée(s)")
        return {"FINISHED"}


class REALFN_OT_visible_all_off(bpy.types.Operator):
    """Hide every curve of the active RealFn object."""

    bl_idname = "realfn.visible_all_off"
    bl_label = "Tout cacher"
    bl_description = "Décoche toutes les cases 'Visible · …' du modifier"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_realfn_modifier(context) is not None

    def execute(self, context):
        n = _apply_visibility_change(context, lambda _: False)
        self.report({"INFO"},
                    f"{n} courbe(s) cachée(s)")
        return {"FINISHED"}


class REALFN_OT_visible_invert(bpy.types.Operator):
    """Invert the visibility of every curve (shown → hidden, hidden →
    shown)."""

    bl_idname = "realfn.visible_invert"
    bl_label = "Inverser"
    bl_description = (
        "Inverse l'état de chaque case 'Visible · …' : ce qui était "
        "affiché devient caché et vice-versa"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_realfn_modifier(context) is not None

    def execute(self, context):
        n = _apply_visibility_change(context, lambda v: not v)
        self.report({"INFO"},
                    f"{n} case(s) inversée(s)")
        return {"FINISHED"}


# --------------------------------------------------------------------------- #
# Copy formula to clipboard
# --------------------------------------------------------------------------- #
class REALFN_OT_copy_formula(bpy.types.Operator):
    """Copy the formula of one curve to the system clipboard.

    The operator looks up the piece by its label in the node group's
    stashed metadata; the format (plain SymPy text or LaTeX) follows
    the ``realfn_display_latex`` toggle on the WindowManager, matching
    what's currently shown in the panel. So if the user sees a LaTeX
    formula they want, they click and it ends up on the clipboard
    ready to paste into LaTeX/Markdown/Notion/anywhere.
    """

    bl_idname = "realfn.copy_formula"
    bl_label = "Copier la formule"
    bl_description = (
        "Copie la formule de cette courbe dans le presse-papiers, "
        "dans le format actuellement affiché (texte SymPy ou LaTeX)"
    )
    bl_options = {"REGISTER"}  # not UNDO — pure side effect on clipboard

    piece_label: bpy.props.StringProperty(
        name="Label de la courbe",
        description=("Étiquette de la pièce dont copier la formule "
                     "(f, f', T_2, …)"),
        default="",
    )

    @classmethod
    def poll(cls, context):
        return _active_realfn_modifier(context) is not None

    def execute(self, context):
        mod = _active_realfn_modifier(context)
        if mod is None:
            self.report({"ERROR"}, "Aucune courbe RealFn active")
            return {"CANCELLED"}
        nt = mod.node_group
        labels = nt.get("realfn_piece_labels")
        if not labels:
            self.report({"ERROR"},
                        "Cette courbe ne contient pas de formules "
                        "stockées (créée avec une version antérieure ?)")
            return {"CANCELLED"}
        labels = list(labels)
        try:
            idx = labels.index(self.piece_label)
        except ValueError:
            self.report({"ERROR"},
                        f"Label introuvable : {self.piece_label!r}")
            return {"CANCELLED"}

        # Pick text or LaTeX following the WindowManager toggle.
        use_latex = getattr(context.window_manager,
                            "realfn_display_latex", False)
        key = ("realfn_piece_formulas_latex" if use_latex
               else "realfn_piece_formulas")
        formulas = nt.get(key)
        if not formulas:
            # Fallback to text form if LaTeX is missing (old trees).
            formulas = nt.get("realfn_piece_formulas")
            if not formulas:
                self.report({"ERROR"}, "Aucune formule disponible")
                return {"CANCELLED"}
        formula = str(list(formulas)[idx])

        context.window_manager.clipboard = formula
        # Truncate very long formulas in the status report so it
        # doesn't overflow Blender's notification widget.
        preview = formula if len(formula) < 60 else formula[:57] + "…"
        fmt = "LaTeX" if use_latex else "texte"
        self.report({"INFO"},
                    f"Copié ({fmt}) : {preview}")
        return {"FINISHED"}


class REALFN_OT_copy_taylor_poly(bpy.types.Operator):
    """Copy the current-order Taylor polynomial of a surface to the
    clipboard.

    The order is read live from the modifier's ``Taylor order`` socket
    and used to index the cumulative polynomials baked at build time, so
    the copied text is exactly the (possibly truncated-on-screen) full
    polynomial shown in the panel. Explicit surfaces copy a single
    ``T(x, y) = …`` line; parametric surfaces copy the three component
    lines ``x(u, v) = …`` / ``y`` / ``z``. The format (plain SymPy text
    or LaTeX) follows the ``realfn_display_latex`` toggle.
    """

    bl_idname = "realfn.copy_taylor_poly"
    bl_label = "Copier le polynôme de Taylor"
    bl_description = (
        "Copie le polynôme de Taylor de l'ordre courant dans le "
        "presse-papiers, dans le format affiché (texte SymPy ou LaTeX)"
    )
    bl_options = {"REGISTER"}  # not UNDO — pure clipboard side effect

    @classmethod
    def poll(cls, context):
        mod = _active_realfn_modifier(context)
        if mod is None:
            return False
        return mod.node_group.get("realfn_kind") in {
            "surface", "parametric_surface"}

    @staticmethod
    def _socket_value(mod, nt, name):
        for it in nt.interface.items_tree:
            if getattr(it, "in_out", None) == "INPUT" and it.name == name:
                return modifier_inputs.get_value(mod, it.identifier)
        return None

    def execute(self, context):
        mod = _active_realfn_modifier(context)
        if mod is None:
            self.report({"ERROR"}, "Aucune surface RealFn active")
            return {"CANCELLED"}
        nt = mod.node_group
        kind = nt.get("realfn_kind")
        order = self._socket_value(mod, nt, "Taylor order")
        if order is None:
            self.report({"ERROR"},
                        "Cet objet n'a pas de surface de Taylor "
                        "(créé avec une version antérieure ?)")
            return {"CANCELLED"}
        order = int(order)
        use_latex = getattr(context.window_manager,
                            "realfn_display_latex", False)
        suffix = "latex" if use_latex else "text"

        def poly_at(base):
            polys = nt.get(f"{base}_{suffix}") or nt.get(f"{base}_text")
            if not polys:
                return None
            polys = list(polys)
            n = max(0, min(order, len(polys) - 1))
            return str(polys[n])

        if kind == "surface":
            p = poly_at("realfn_taylor_poly")
            if p is None:
                self.report({"ERROR"}, "Aucun polynôme stocké")
                return {"CANCELLED"}
            text = f"T(x, y) = {p}"
        else:  # parametric_surface
            lines = []
            for axis in "xyz":
                pa = poly_at(f"realfn_taylor_poly_{axis}")
                if pa is not None:
                    lines.append(f"{axis}(u, v) = {pa}")
            if not lines:
                self.report({"ERROR"}, "Aucun polynôme stocké")
                return {"CANCELLED"}
            text = "\n".join(lines)

        context.window_manager.clipboard = text
        fmt = "LaTeX" if use_latex else "texte"
        self.report({"INFO"},
                    f"Polynôme de Taylor (ordre {order}, {fmt}) copié")
        return {"FINISHED"}


class REALFN_OT_show_taylor_poly(bpy.types.Operator):
    """Show the full current-order Taylor polynomial in a popup.

    The panel box truncates long polynomials to a few lines; this popup
    renders the complete expression (every wrapped line, all three
    components for parametric surfaces), with a Copy button. Read-only —
    closes on click-away."""

    bl_idname = "realfn.show_taylor_poly"
    bl_label = "Polynôme de Taylor complet"
    bl_description = (
        "Affiche le polynôme de Taylor complet de l'ordre courant "
        "dans une fenêtre (non tronqué)"
    )
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        mod = _active_realfn_modifier(context)
        if mod is None:
            return False
        return mod.node_group.get("realfn_kind") in {
            "surface", "parametric_surface"}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=520)

    def draw(self, context):
        from . import panel
        layout = self.layout
        mod = _active_realfn_modifier(context)
        if mod is None:
            layout.label(text="Aucune surface RealFn active")
            return
        nt = mod.node_group
        kind = nt.get("realfn_kind")
        order = REALFN_OT_copy_taylor_poly._socket_value(
            mod, nt, "Taylor order")
        if order is None:
            layout.label(text="Pas de surface de Taylor sur cet objet")
            return
        order = int(order)
        use_latex = getattr(context.window_manager,
                            "realfn_display_latex", False)
        suffix = "latex" if use_latex else "text"
        layout.label(text=f"Polynôme de Taylor — ordre {order}",
                     icon="RNDCURVE")

        def emit(base, lhs):
            polys = nt.get(f"{base}_{suffix}") or nt.get(f"{base}_text")
            if not polys:
                return
            polys = list(polys)
            n = max(0, min(order, len(polys) - 1))
            col = layout.column(align=True)
            for line in panel._wrap_formula(f"{lhs} = {polys[n]}",
                                            max_lines=None):
                col.label(text=line)

        if kind == "surface":
            emit("realfn_taylor_poly", "T(x, y)")
        else:
            for axis in "xyz":
                emit(f"realfn_taylor_poly_{axis}", f"{axis}(u, v)")

        layout.separator()
        layout.operator("realfn.copy_taylor_poly", icon="COPYDOWN")

    def execute(self, context):
        return {"FINISHED"}


# --------------------------------------------------------------------------- #
# Preset operators
# --------------------------------------------------------------------------- #
# Saving a preset is straightforward: snapshot the active modifier
# and write it to JSON. Applying a preset is the interesting one
# because the formula or orders might differ from the current tree,
# so we rebuild the tree first (via the same code path that ``create``
# uses) and then restore the saved socket values into the new
# modifier. The split keeps the rebuild logic in one place.


# --------------------------------------------------------------------------- #
# Vector function creator
# --------------------------------------------------------------------------- #
class REALFN_OT_create_vector(bpy.types.Operator):
    """Create a 3D mesh object visualising a vector function F: R → R³.

    The viewport shows the trace curve t ↦ F(t) for t in the chosen
    range, together with one arrow at t₀ representing the derivative
    F'(t₀) anchored on the trace at F(t₀). Scrubbing t₀ slides the
    arrow along the curve in real time.

    The formula uses the ``sympy.physics.vector`` syntax: the
    reference frame is hardcoded as ``N``, and basis vectors are
    accessed as ``N.x``, ``N.y``, ``N.z``. Example::

        cos(t)*N.x + sin(t)*N.y + t*N.z   # circular helix
    """

    bl_idname = "realfn.create_vector"
    bl_label = "Créer une courbe vectorielle F(t)…"
    bl_description = (
        "Saisir une expression vectorielle dans le repère N (par "
        "exemple cos(t)*N.x + sin(t)*N.y + t*N.z). L'objet créé "
        "trace la courbe en 3D et affiche la dérivée F'(t₀) comme "
        "flèche glissable"
    )
    bl_options = {"REGISTER", "UNDO"}

    expr: bpy.props.StringProperty(
        name="F(t)",
        description=(
            "Expression vectorielle utilisant N.x, N.y, N.z et la "
            "variable t. Exemples : cos(t)*N.x + sin(t)*N.y + t*N.z, "
            "(t**2)*N.x + sin(t)*N.y"
        ),
        default="cos(t)*N.x + sin(t)*N.y + t*N.z",
    )
    allowed_params: bpy.props.StringProperty(
        name="Paramètres libres",
        description=(
            "Symboles supplémentaires autorisés, séparés par virgules. "
            "Chacun deviendra un slider du modifier"
        ),
        default="a,b,omega",
    )
    t_min: bpy.props.FloatProperty(name="t min", default=-3.14)
    t_max: bpy.props.FloatProperty(name="t max", default=3.14)
    t0: bpy.props.FloatProperty(
        name="t₀", default=0.0,
        description="Position initiale du marqueur sur la courbe",
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=440)

    def _params_tuple(self):
        return tuple(
            s.strip() for s in self.allowed_params.split(",") if s.strip()
        )

    def draw(self, context):
        layout = self.layout
        layout.label(text=i18n.tr("F(t) en syntaxe sympy.physics.vector :"))
        layout.prop(self, "expr")
        layout.prop(self, "allowed_params")
        row = layout.row(align=True)
        row.prop(self, "t_min")
        row.prop(self, "t_max")
        layout.prop(self, "t0")

        # Live parse feedback so the user can see errors before clicking OK.
        try:
            params = self._params_tuple()
            components = sympy_parser.parse_vector_expression(self.expr)
            sp_ = sympy_parser._sympy()
            box = layout.box()
            box.label(text=i18n.tr("Composantes détectées :"), icon="DRIVER")
            for axis, c in zip(("Fx", "Fy", "Fz"), components):
                box.label(text=f"  {axis} = {sp_.sstr(c)}")
            # Check free symbols
            free = set()
            for c in components:
                free |= c.free_symbols
            free_names = sorted(s.name for s in free if s.name != "t")
            unknown = [s for s in free_names if s not in params]
            if unknown:
                box.label(
                    text=i18n.tr("Non déclarés : ") + ", ".join(unknown),
                    icon="ERROR",
                )
                box.label(
                    text=i18n.tr("→ ajoutez à 'Paramètres libres'"),
                    icon="INFO",
                )
            elif free_names:
                box.label(
                    text=i18n.tr("Paramètres : ") + ", ".join(free_names),
                    icon="INFO",
                )
        except ValueError as exc:
            layout.box().label(text=str(exc), icon="ERROR")

    def execute(self, context):
        try:
            nt = vector_tree.make_vectorfn_tree(
                self.expr,
                allowed_params=self._params_tuple(),
                t_default_range=(self.t_min, self.t_max),
                t0_default=self.t0,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        # Spawn the host object — reusing the scalar helper, which
        # just creates a mesh + Geometry Nodes modifier and binds the
        # tree. There's nothing scalar-specific in there.
        _spawn_object(context, nt, f"F(t) = {self.expr}")
        self.report({"INFO"},
                    f"Courbe vectorielle créée : F(t) = {self.expr}")
        return {"FINISHED"}


# --------------------------------------------------------------------------- #
# Vector bench (banc de vecteurs)
# --------------------------------------------------------------------------- #
_BENCH_PALETTE = ("Bleu", "Vert", "Rouge", "Jaune",
                  "Magenta", "Cyan", "Orange", "Gris")


def _build_and_spawn_bench(context, rows, params, name="Banc de vecteurs"):
    """Build a vector-bench tree, spawn the host object, colour each arrow
    from the palette and nudge parameters off zero so the rotations read
    on creation. Returns the object; raises ``ValueError`` if a row fails
    to parse. Shared by the create operator and the preset operator."""
    nt = bench_tree.make_vector_bench_tree(rows, allowed_params=tuple(params))
    obj = _spawn_object(context, nt, name)
    default_materials.ensure_default_materials()
    mod = next((m for m in obj.modifiers
                if m.type == "NODES" and m.node_group is nt), None)
    if mod is not None:
        from . import preset_io
        by_name = {it.name: it for it in nt.interface.items_tree
                   if getattr(it, "in_out", None) == "INPUT"}
        for idx, (rname, _) in enumerate(rows):
            it = by_name.get(f"Matériau · {rname}")
            mat = default_materials.get_palette_material(
                _BENCH_PALETTE[idx % len(_BENCH_PALETTE)])
            if it is not None and mat is not None:
                preset_io.set_modifier_socket(mod, it, mat)
        for p in params:
            it = by_name.get(p)
            if it is not None:
                modifier_inputs.set_value(mod, it.identifier, 0.7)
    # Populate the editable definition so the panel fields are pre-filled
    # and the bench can be modified live afterwards.
    try:
        from . import bench_props
        bench_props.set_bench_props(obj, rows, tuple(params))
    except Exception:
        pass
    obj.data.update()
    return obj


class REALFN_OT_create_vector_bench(bpy.types.Operator):
    """Create a bench of named vector arrows to explore vector algebra
    and rotations, driven by live parameter sliders."""

    bl_idname = "realfn.create_vector_bench"
    bl_label = "Créer un banc de vecteurs"
    bl_description = (
        "Déclarer plusieurs vecteurs nommés (v1, v2, …) à l'aide des "
        "helpers (vec, cross, dot, rotate, normalize…). Chaque vecteur "
        "est une flèche colorée depuis l'origine ; une ligne peut "
        "réutiliser les précédentes (ex. v3 = cross(v1, v2)). Les "
        "paramètres (ex. theta) deviennent des sliders du modifier — "
        "scrubez pour voir les rotations en direct"
    )
    bl_options = {"REGISTER", "UNDO"}

    v1: bpy.props.StringProperty(name="v1", default="vec(2, 0, 0)")
    v2: bpy.props.StringProperty(
        name="v2", default="rotate(v1, vec(0, 0, 1), theta)")
    v3: bpy.props.StringProperty(name="v3", default="cross(v1, v2)")
    v4: bpy.props.StringProperty(name="v4", default="")
    v5: bpy.props.StringProperty(name="v5", default="")
    v6: bpy.props.StringProperty(name="v6", default="")
    params: bpy.props.StringProperty(
        name="Paramètres",
        description=("Symboles scalaires (séparés par des virgules) "
                     "autorisés dans les expressions ; chacun devient un "
                     "slider live du modifier"),
        default="theta",
    )

    def _params_tuple(self):
        return tuple(s.strip() for s in self.params.split(",") if s.strip())

    def _rows(self):
        out = []
        for i in range(1, 7):
            expr = getattr(self, f"v{i}").strip()
            if expr:
                out.append((f"v{i}", expr))
        return out

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=480)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        for i in range(1, 7):
            col.prop(self, f"v{i}")
        layout.prop(self, "params")
        layout.label(
            text="Vecteurs : vec, cross, dot, rotate, rot_z, normalize, "
                 "comp…", icon="INFO")
        layout.label(
            text="Matrices : mat, eul/eul_zyx…, rmx/rmy/rmz, rotmat, inv, "
                 "det, transpose  ·  produit avec *  (eul(0,0,a)*v1)",
            icon="BLANK1")
        layout.label(
            text="Quaternions : quat, quat_axis, qmul, qslerp, qrotate  "
                 "(qrotate(quat_axis(vec(0,0,1),a), v1))",
            icon="BLANK1")
        layout.label(
            text="Une ligne peut réutiliser les précédentes : "
                 "v3 = cross(v1, v2)", icon="BLANK1")

        # Live parse feedback (rows in order, with forward references).
        rows = self._rows()
        params = self._params_tuple()
        box = layout.box()
        if not rows:
            box.label(text="Renseignez au moins un vecteur", icon="ERROR")
            return
        sp = sympy_parser._sympy()
        prior = {}
        for name, expr_str in rows:
            try:
                comps = sympy_parser.parse_bench_vector(
                    expr_str, allowed_params=params, prior=prior)
                prior[name] = sp.Matrix(list(comps))
                txt = ", ".join(str(sp.sstr(c)) for c in comps)
                box.label(text=f"{name} = ({txt})", icon="CHECKMARK")
            except ValueError as exc:
                box.label(text=f"{name} : {exc}", icon="ERROR")
                return

    def execute(self, context):
        rows = self._rows()
        if not rows:
            self.report({"ERROR"}, "Le banc doit contenir au moins un vecteur")
            return {"CANCELLED"}
        try:
            _build_and_spawn_bench(context, rows, self._params_tuple())
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"},
                    f"Banc de vecteurs créé ({len(rows)} vecteurs)")
        return {"FINISHED"}


class REALFN_OT_apply_bench_preset(bpy.types.Operator):
    """Create a ready-made vector bench (rotation, cross product, slerp…)
    in one click — a guided tour of the vector/rotation helpers."""

    bl_idname = "realfn.apply_bench_preset"
    bl_label = "Banc prêt à l'emploi"
    bl_description = (
        "Crée un banc de vecteurs prédéfini, prêt à explorer (scrubez le "
        "slider du modifier)")
    bl_options = {"REGISTER", "UNDO"}

    preset_id: bpy.props.StringProperty(default="")

    def execute(self, context):
        preset = bench_tree.get_bench_preset(self.preset_id)
        if preset is None:
            self.report({"ERROR"}, f"Preset inconnu : {self.preset_id!r}")
            return {"CANCELLED"}
        rows = [(n, e) for n, e in preset["rows"]]
        params = tuple(s.strip() for s in preset["params"].split(",")
                       if s.strip())
        label = preset["label"]
        if i18n.get_lang() == "EN":
            label = preset.get("label_en", label)
        try:
            _build_and_spawn_bench(context, rows, params,
                                   name=f"Banc — {label}")
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Banc « {label} » créé")
        return {"FINISHED"}


class REALFN_OT_bench_rebuild(bpy.types.Operator):
    """Rebuild the active bench from its edited formulas (manual update)."""

    bl_idname = "realfn.bench_rebuild"
    bl_label = "Reconstruire le banc"
    bl_description = ("Reconstruit le banc actif depuis les formules éditées "
                      "dans le panneau, en conservant sliders et matériaux")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_vector_bench_realfn_modifier(context) is not None

    def execute(self, context):
        from . import bench_props
        obj = context.active_object
        err = bench_props.rebuild_bench(obj)
        try:
            obj.realfn_bench.error = err
        except Exception:
            pass
        if err:
            self.report({"ERROR"}, err)
            return {"CANCELLED"}
        self.report({"INFO"}, "Banc reconstruit")
        return {"FINISHED"}


class REALFN_OT_edit_rebuild(bpy.types.Operator):
    """Rebuild the active function from its edited formula (manual update)."""

    bl_idname = "realfn.edit_rebuild"
    bl_label = "Reconstruire la fonction"
    bl_description = ("Reconstruit la fonction active depuis la formule éditée "
                      "dans le panneau, en conservant domaine, ordres, "
                      "matériaux et paramètres")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        from . import edit_props
        mod = _active_realfn_modifier(context)
        if mod is None:
            return False
        kind = mod.node_group.get("realfn_kind") or "scalar"
        return kind in edit_props.EDITABLE_KINDS

    def execute(self, context):
        from . import edit_props
        obj = context.active_object
        err = edit_props.rebuild_edit(obj)
        try:
            obj.realfn_edit.error = err
        except Exception:
            pass
        if err:
            self.report({"ERROR"}, err)
            return {"CANCELLED"}
        self.report({"INFO"}, "Fonction reconstruite")
        return {"FINISHED"}


# =========================================================================== #
# Vector preset operators
# =========================================================================== #
# Symmetric to the scalar preset operators above. Each one targets the
# *vector* preset directory + helpers in ``presets`` and ``builtin_presets``,
# and uses :func:`_active_vector_realfn_modifier` as its gate.


# =========================================================================== #
# Snapshot restoration
# =========================================================================== #
# Snapshot / preset rebuild — shared dispatch
# =========================================================================== #
# Rebuilding a node tree from a preset/snapshot dict is the same logic
# whether the dict came from disk (apply preset) or from the .blend
# (restore snapshot). The three helpers below centralise that per-kind
# dispatch so snapshot restore reaches full parity with every preset
# type — curve, vector, surface, parametric surface, 3D scalar field
# and 3D vector field — instead of only curves and vectors.

def _rebuild_tree_from_data(kind, data):
    """Build a fresh node tree from a preset/snapshot dict for ``kind``.

    Mirrors the rebuild logic of each per-kind apply-preset operator.
    Raises ``ValueError`` if the stored formula can't be compiled.
    """
    formula = data.get("formula", {})
    range_d = data.get("range", {})

    if kind == "vector_bench":
        rows = [(str(r[0]), str(r[1])) for r in formula.get("rows", [])
                if len(r) >= 2]
        if not rows:
            raise ValueError("banc sans vecteur")
        return bench_tree.make_vector_bench_tree(
            rows, allowed_params=tuple(formula.get("allowed_params", [])))

    if kind == "vector":
        return vector_tree.make_vectorfn_tree(
            formula.get("expr", "0*N.x + 0*N.y + 0*N.z"),
            var_name=str(formula.get("var_name", "t")),
            allowed_params=tuple(formula.get("allowed_params", [])),
            t_default_range=(float(range_d.get("t_min", 0.0)),
                             float(range_d.get("t_max", 6.283))),
            t0_default=float(range_d.get("t_0", 0.0)),
        )
    if kind == "surface":
        return surface_tree.make_surfacefn_tree(
            formula.get("expr", "0"),
            x_name=str(formula.get("x_name", "x")),
            y_name=str(formula.get("y_name", "y")),
            allowed_params=tuple(formula.get("allowed_params", [])),
            x_default_range=(float(range_d.get("x_min", -3.0)),
                             float(range_d.get("x_max", 3.0))),
            y_default_range=(float(range_d.get("y_min", -3.0)),
                             float(range_d.get("y_max", 3.0))),
            x0_default=float(range_d.get("x_0", 0.5)),
            y0_default=float(range_d.get("y_0", 0.5)),
        )
    if kind == "parametric_surface":
        components = formula.get("components", ["0", "0", "0"])
        return parametric_surface_tree.make_parametric_surface_tree(
            tuple(components),
            u_name=str(formula.get("u_name", "u")),
            v_name=str(formula.get("v_name", "v")),
            allowed_params=tuple(formula.get("allowed_params", [])),
            u_default_range=(float(range_d.get("u_min", 0.0)),
                             float(range_d.get("u_max", 6.283))),
            v_default_range=(float(range_d.get("v_min", 0.0)),
                             float(range_d.get("v_max", 3.142))),
            u0_default=float(range_d.get("u_0", 1.0)),
            v0_default=float(range_d.get("v_0", 1.0)),
        )
    if kind == "scalar_field_3d":
        return scalar_field_3d_tree.make_scalarfield3d_tree(
            formula.get("expr", "0"),
            x_name=str(formula.get("x_name", "x")),
            y_name=str(formula.get("y_name", "y")),
            z_name=str(formula.get("z_name", "z")),
            allowed_params=tuple(formula.get("allowed_params", [])),
            x_default_range=(float(range_d.get("x_min", -1.0)),
                             float(range_d.get("x_max", 1.0))),
            y_default_range=(float(range_d.get("y_min", -1.0)),
                             float(range_d.get("y_max", 1.0))),
            z_default_range=(float(range_d.get("z_min", -1.0)),
                             float(range_d.get("z_max", 1.0))),
            x0_default=float(range_d.get("x_0", 0.5)),
            y0_default=float(range_d.get("y_0", 0.5)),
            z0_default=float(range_d.get("z_0", 0.5)),
        )
    if kind == "vector_field_3d":
        mode = str(formula.get("mode", "explicit"))
        common = dict(
            x_name=str(formula.get("x_name", "x")),
            y_name=str(formula.get("y_name", "y")),
            z_name=str(formula.get("z_name", "z")),
            allowed_params=tuple(formula.get("allowed_params", [])),
            x_default_range=(float(range_d.get("x_min", -1.5)),
                             float(range_d.get("x_max", 1.5))),
            y_default_range=(float(range_d.get("y_min", -1.5)),
                             float(range_d.get("y_max", 1.5))),
            z_default_range=(float(range_d.get("z_min", -1.5)),
                             float(range_d.get("z_max", 1.5))),
            x0_default=float(range_d.get("x_0", 0.5)),
            y0_default=float(range_d.get("y_0", 0.5)),
            z0_default=float(range_d.get("z_0", 0.5)),
        )
        if mode == "from_potential":
            return vector_field_3d_tree.make_vector_field_3d_tree(
                potential_source=str(formula.get("potential", "0")),
                **common)
        return vector_field_3d_tree.make_vector_field_3d_tree(
            components_source=tuple(formula.get("components",
                                                ["0", "0", "0"])),
            **common)

    # Default: scalar curve y = f(x).
    return tree.make_realfn_tree(
        formula.get("expr", "0"),
        allowed_params=tuple(formula.get("allowed_params", [])),
        derivative_order=int(formula.get("derivative_order", 0)),
        taylor_order=int(formula.get("taylor_order", 0)),
        x_default_range=(float(range_d.get("x_min", -5.0)),
                         float(range_d.get("x_max", 5.0))),
        x0_default=float(range_d.get("x_0", 0.0)),
    )


# Per-kind "apply socket values" function — restores range, basepoint,
# visibility flags, materials and free parameters onto the rebuilt tree.
_APPLY_BY_KIND = {
    "vector": "apply_vector_preset_to_modifier",
    "surface": "apply_surface_preset_to_modifier",
    "parametric_surface": "apply_parametric_surface_preset_to_modifier",
    "scalar_field_3d": "apply_scalar_field_3d_preset_to_modifier",
    "vector_field_3d": "apply_vector_field_3d_preset_to_modifier",
    "scalar": "apply_preset_to_modifier",
}


def _apply_data_to_modifier(kind, data, modifier):
    """Dispatch to the kind-appropriate ``apply_*_preset_to_modifier``."""
    fn = getattr(presets, _APPLY_BY_KIND.get(kind, "apply_preset_to_modifier"))
    return fn(data, modifier)


def _object_name_for(kind, data):
    """Human-readable object name for a rebuilt RealFn object."""
    formula = data.get("formula", {})
    if kind == "vector":
        return f"F(t) = {formula.get('expr', '?')}"
    if kind == "surface":
        return f"z = {formula.get('expr', '?')}"
    if kind == "scalar":
        return f"y = {formula.get('expr', '?')}"
    # Parametric surface / 3D fields keep the stored display name.
    return data.get("name", "RealFn")


# =========================================================================== #
# A single operator that restores the snapshot of *any* RealFn kind, since
# the dispatch is mechanical (look at the snapshot's ``kind`` field) and
# users see this as one feature. The panel buttons in every sub-panel
# call this same operator.

class REALFN_OT_restore_snapshot(bpy.types.Operator):
    """Rebuild the active RealFn object from its stored snapshot.

    The snapshot is the JSON dict saved on the modifier's node_group
    by the ``save_pre`` handler whenever the .blend is saved. Restoring
    re-runs exactly the same pipeline as applying a preset:
    rebuild the tree from the snapshot's formula, then re-apply all
    socket values (range, t₀, visibility flags, materials, parameters).
    Use case: the user has tweaked the curve and wants to roll back
    to the state captured at the last save.
    """

    bl_idname = "realfn.restore_snapshot"
    bl_label = "Restaurer le snapshot stocké"
    bl_description = (
        "Reconstruit l'objet actif à partir du snapshot mémorisé "
        "lors de la dernière sauvegarde du fichier .blend. Annule "
        "toutes les modifications faites depuis"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        mod = _active_realfn_modifier(context)
        if mod is None:
            return False
        return memorize.get_stored_snapshot(mod) is not None

    def execute(self, context):
        mod = _active_realfn_modifier(context)
        if mod is None:
            self.report({"ERROR"}, "Aucune courbe RealFn active")
            return {"CANCELLED"}

        snapshot = memorize.get_stored_snapshot(mod)
        if snapshot is None:
            self.report({"ERROR"},
                        "Aucun snapshot mémorisé sur cet objet")
            return {"CANCELLED"}

        # Dispatch on snapshot kind. We don't trust the live modifier's
        # ``realfn_kind`` here — the snapshot's own ``kind`` is more
        # reliable in case the user has somehow swapped the tree manually.
        # The rebuild + apply logic is shared with the preset operators
        # via the module-level helpers, so every kind is supported.
        kind = snapshot.get("kind", "scalar")

        try:
            new_nt = _rebuild_tree_from_data(kind, snapshot)
        except ValueError as exc:
            self.report({"ERROR"},
                        f"Reconstruction depuis snapshot : {exc}")
            return {"CANCELLED"}

        # Preserve the snapshot on the new node_group so the user can
        # restore again after another round of changes. Without this,
        # restoring would wipe the snapshot (the new tree has no IDProps).
        import json
        new_nt[memorize.SNAPSHOT_PROP] = json.dumps(
            snapshot, ensure_ascii=False,
        )
        old_ts = memorize.get_snapshot_timestamp(mod)
        if old_ts:
            new_nt[memorize.SNAPSHOT_SAVED_AT_PROP] = old_ts

        old_nt = mod.node_group
        mod.node_group = new_nt
        compiler.release_tree(old_nt, keep=new_nt)
        obj = context.active_object
        if obj is not None:
            obj.name = _object_name_for(kind, snapshot)

        # Restore socket values via the kind-appropriate apply function.
        report = _apply_data_to_modifier(kind, snapshot, mod)

        # Viewport refresh — same Blender-5.x trick as the other applies.
        if obj is not None:
            mod.node_group = mod.node_group
            try:
                obj.update_tag(refresh={'OBJECT'})
            except TypeError:
                obj.update_tag()

        self.report(
            {"INFO"},
            f"Snapshot restauré — "
            f"{report.get('applied', 0)} valeur(s) restaurée(s)"
            + (f", {report.get('skipped', 0)} ignorée(s)"
               if report.get('skipped') else ""),
        )
        return {"FINISHED"}


# =========================================================================== #
# Default materials operators
# =========================================================================== #

class REALFN_OT_install_default_materials(bpy.types.Operator):
    """(Re)install the bundled material palette into the .blend.

    Idempotent: existing materials with the right name are left
    untouched (the user may have customised them). Only missing
    palette entries are created. Returns the count of newly created
    materials in the operator report.
    """

    bl_idname = "realfn.install_default_materials"
    bl_label = "Installer la palette de matériaux"
    bl_description = (
        "Installe les 8 matériaux RealFn (Bleu, Vert, Rouge, Gris, "
        "Jaune, Magenta, Cyan, Orange) dans le .blend courant. "
        "N'écrase pas un matériau existant du même nom"
    )
    bl_options = {"REGISTER"}

    def execute(self, context):
        n = default_materials.ensure_default_materials()
        # Also install the scalar field 3D color-ramp material — it's
        # not part of the palette but lives in the same module, and
        # users want it pre-installed for the same reasons (so the
        # default sphere shading works out of the box on a fresh
        # scalar_field_3d modifier).
        default_materials.ensure_scalar_field_3d_material()
        if n == 0:
            self.report({"INFO"}, "Palette déjà installée — aucun ajout")
        else:
            self.report({"INFO"},
                        f"{n} matériau(x) ajouté(s) à la palette")
        return {"FINISHED"}


class REALFN_OT_apply_kinematic_colors(bpy.types.Operator):
    """Assign the canonical kinematic colour code to the active vector
    RealFn: position → bleu, vitesse → vert, accélération → rouge,
    trajectoire → gris.

    Installs the palette first if needed, so the user can run this
    once without thinking about whether the materials exist yet.
    """

    bl_idname = "realfn.apply_kinematic_colors"
    bl_label = "Appliquer le code couleur cinématique"
    bl_description = (
        "Affecte d'un clic le code couleur standard : position en "
        "bleu, vitesse en vert, accélération en rouge, trajectoire "
        "en gris. Installe la palette de matériaux si nécessaire"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_vector_realfn_modifier(context) is not None

    def execute(self, context):
        mod = _active_vector_realfn_modifier(context)
        if mod is None:
            self.report({"ERROR"}, "Aucune courbe vectorielle RealFn active")
            return {"CANCELLED"}
        report = default_materials.apply_kinematic_color_code(mod)
        # Force a viewport refresh so the assignment is visible
        # without needing a manual scrub.
        obj = context.active_object
        if obj is not None:
            mod.node_group = mod.node_group
            try:
                obj.update_tag(refresh={'OBJECT'})
            except TypeError:
                obj.update_tag()
        self.report({"INFO"},
                    f"Code couleur appliqué : "
                    f"{report['applied']} matériau(x) assigné(s)"
                    + (f", {report['skipped']} ignoré(s)"
                       if report['skipped'] else ""))
        return {"FINISHED"}


# =========================================================================== #
# Explicit surface z = f(x, y) — create + preset operators
# =========================================================================== #

class REALFN_OT_create_surface(bpy.types.Operator):
    """Create a 3D mesh object visualising an explicit surface z = f(x, y).

    The user types a single scalar expression in two variables (``x``
    and ``y``); the resulting mesh is a quadrilateral grid in the (x, y)
    plane lifted to the graph of f. A marker sphere and a tangent
    plane (toggleable) sit at the basepoint (x₀, y₀).
    """

    bl_idname = "realfn.create_surface"
    bl_label = "Créer une surface z = f(x, y)…"
    bl_description = (
        "Saisir une expression de deux variables (par exemple x**2 - y**2). "
        "L'objet créé est un maillage quadrillé représentant la surface "
        "graphe de f, avec marqueur et plan tangent affine au point "
        "d'ancrage (x₀, y₀)"
    )
    bl_options = {"REGISTER", "UNDO"}

    expr: bpy.props.StringProperty(
        name="f(x, y)",
        description=(
            "Expression scalaire utilisant x et y. Exemples : "
            "x**2 - y**2, sin(x)*cos(y), exp(-(x**2+y**2))"
        ),
        default="x**2 - y**2",
    )
    allowed_params: bpy.props.StringProperty(
        name="Paramètres libres",
        description="Symboles supplémentaires autorisés, séparés par virgules",
        default="",
    )
    x_min: bpy.props.FloatProperty(name="x min", default=-3.0)
    x_max: bpy.props.FloatProperty(name="x max", default=3.0)
    y_min: bpy.props.FloatProperty(name="y min", default=-3.0)
    y_max: bpy.props.FloatProperty(name="y max", default=3.0)
    x0: bpy.props.FloatProperty(name="x_0", default=0.5)
    y0: bpy.props.FloatProperty(name="y_0", default=0.5)

    def _params_tuple(self):
        return tuple(p.strip() for p in self.allowed_params.split(",")
                     if p.strip())

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "expr")
        layout.prop(self, "allowed_params")
        row = layout.row(align=True)
        row.prop(self, "x_min"); row.prop(self, "x_max")
        row = layout.row(align=True)
        row.prop(self, "y_min"); row.prop(self, "y_max")
        row = layout.row(align=True)
        row.prop(self, "x0"); row.prop(self, "y0")

        # Live parse feedback.
        try:
            params = self._params_tuple()
            f_expr = sympy_parser.parse_surface_expression(self.expr)
            sp_ = sympy_parser._sympy()
            box = layout.box()
            box.label(text=f"f(x, y) = {sp_.sstr(f_expr)}", icon="FORCE_FORCE")
            fx, fy = sympy_parser.surface_gradient(f_expr)
            box.label(text=f"∂f/∂x = {sp_.sstr(fx)}")
            box.label(text=f"∂f/∂y = {sp_.sstr(fy)}")
            free_names = sorted(s.name for s in f_expr.free_symbols
                                if s.name not in ("x", "y"))
            unknown = [s for s in free_names if s not in params]
            if unknown:
                box.label(text=i18n.tr("Non déclarés : ") + ", ".join(unknown),
                          icon="ERROR")
        except ValueError as exc:
            layout.box().label(text=str(exc), icon="ERROR")

    def execute(self, context):
        try:
            nt = surface_tree.make_surfacefn_tree(
                self.expr,
                allowed_params=self._params_tuple(),
                x_default_range=(self.x_min, self.x_max),
                y_default_range=(self.y_min, self.y_max),
                x0_default=self.x0,
                y0_default=self.y0,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        obj = _spawn_object(context, nt, f"z = {self.expr}")
        self.report({"INFO"}, f"Surface créée : {obj.name}")
        return {"FINISHED"}


# =========================================================================== #
# Parametric surface (x(u,v), y(u,v), z(u,v)) — create + preset operators
# =========================================================================== #

class REALFN_OT_create_parametric_surface(bpy.types.Operator):
    """Create a 3D mesh object visualising a parametric surface."""

    bl_idname = "realfn.create_parametric_surface"
    bl_label = "Créer une surface paramétrée…"
    bl_description = (
        "Saisir les trois composantes x(u, v), y(u, v), z(u, v). L'objet "
        "créé maille le domaine (u, v) et place chaque sommet à F(u, v), "
        "avec marqueur et plan tangent affine en F(u₀, v₀)"
    )
    bl_options = {"REGISTER", "UNDO"}

    x_expr: bpy.props.StringProperty(
        name="x(u, v)", default="sin(u)*cos(v)",
    )
    y_expr: bpy.props.StringProperty(
        name="y(u, v)", default="sin(u)*sin(v)",
    )
    z_expr: bpy.props.StringProperty(
        name="z(u, v)", default="cos(u)",
    )
    allowed_params: bpy.props.StringProperty(
        name="Paramètres libres",
        description="Symboles supplémentaires autorisés, séparés par virgules",
        default="",
    )
    u_min: bpy.props.FloatProperty(name="u min", default=0.0)
    u_max: bpy.props.FloatProperty(name="u max", default=3.142)
    v_min: bpy.props.FloatProperty(name="v min", default=0.0)
    v_max: bpy.props.FloatProperty(name="v max", default=6.283)
    u0: bpy.props.FloatProperty(name="u_0", default=1.0)
    v0: bpy.props.FloatProperty(name="v_0", default=1.0)

    def _params_tuple(self):
        return tuple(p.strip() for p in self.allowed_params.split(",")
                     if p.strip())

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "x_expr")
        layout.prop(self, "y_expr")
        layout.prop(self, "z_expr")
        layout.prop(self, "allowed_params")
        row = layout.row(align=True); row.prop(self, "u_min"); row.prop(self, "u_max")
        row = layout.row(align=True); row.prop(self, "v_min"); row.prop(self, "v_max")
        row = layout.row(align=True); row.prop(self, "u0"); row.prop(self, "v0")

        try:
            components = sympy_parser.parse_parametric_surface_components(
                (self.x_expr, self.y_expr, self.z_expr),
            )
            sp_ = sympy_parser._sympy()
            box = layout.box()
            box.label(text="F(u, v) :", icon="DRIVER")
            for axis, c in zip(("x", "y", "z"), components):
                box.label(text=f"  {axis} = {sp_.sstr(c)}")
            params = self._params_tuple()
            free = set()
            for c in components:
                free |= c.free_symbols
            free_names = sorted(s.name for s in free
                                if s.name not in ("u", "v"))
            unknown = [s for s in free_names if s not in params]
            if unknown:
                box.label(text=i18n.tr("Non déclarés : ") + ", ".join(unknown),
                          icon="ERROR")
        except ValueError as exc:
            layout.box().label(text=str(exc), icon="ERROR")

    def execute(self, context):
        try:
            nt = parametric_surface_tree.make_parametric_surface_tree(
                (self.x_expr, self.y_expr, self.z_expr),
                allowed_params=self._params_tuple(),
                u_default_range=(self.u_min, self.u_max),
                v_default_range=(self.v_min, self.v_max),
                u0_default=self.u0,
                v0_default=self.v0,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        obj = _spawn_object(context, nt, "Surface paramétrée")
        self.report({"INFO"}, f"Surface paramétrée créée : {obj.name}")
        return {"FINISHED"}


# =========================================================================== #
# 3D scalar field f(x, y, z) — create + preset operators
# =========================================================================== #

class REALFN_OT_create_scalar_field_3d(bpy.types.Operator):
    """Create a 3D mesh object visualising a scalar field f: R^3 -> R.

    The user types a single scalar expression in three variables
    (``x``, ``y``, ``z``); the resulting object samples f on a regular
    grid spanning a 3D box, with a marker + label at each point and a
    distinguished marker + label at the user-controlled basepoint.
    """

    bl_idname = "realfn.create_scalar_field_3d"
    bl_label = "Créer un champ scalaire ƒ(x, y, z)…"
    bl_description = (
        "Saisir une expression de trois variables (par exemple 1/√(x²+y²+z²)). "
        "L'objet créé est une grille NxNxN d'échantillons avec marqueur en "
        "chaque point. Une étiquette agrandie affiche ƒ(x₀, y₀, z₀) au point "
        "d'ancrage déplaçable"
    )
    bl_options = {"REGISTER", "UNDO"}

    expr: bpy.props.StringProperty(
        name="f(x, y, z)",
        description=(
            "Expression scalaire utilisant x, y, z. Exemples : "
            "x**2 + y**2 + z**2, 1/sqrt(x**2+y**2+z**2), "
            "exp(-(x**2+y**2+z**2)/sigma**2)"
        ),
        default="x**2 + y**2 + z**2",
    )
    allowed_params: bpy.props.StringProperty(
        name="Paramètres libres",
        description="Symboles supplémentaires autorisés, séparés par virgules",
        default="",
    )
    x_min: bpy.props.FloatProperty(name="x min", default=-1.0)
    x_max: bpy.props.FloatProperty(name="x max", default=1.0)
    y_min: bpy.props.FloatProperty(name="y min", default=-1.0)
    y_max: bpy.props.FloatProperty(name="y max", default=1.0)
    z_min: bpy.props.FloatProperty(name="z min", default=-1.0)
    z_max: bpy.props.FloatProperty(name="z max", default=1.0)
    x0: bpy.props.FloatProperty(name="x_0", default=0.5)
    y0: bpy.props.FloatProperty(name="y_0", default=0.5)
    z0: bpy.props.FloatProperty(name="z_0", default=0.5)

    def _params_tuple(self):
        return tuple(p.strip() for p in self.allowed_params.split(",")
                     if p.strip())

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=450)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "expr")
        layout.prop(self, "allowed_params")
        row = layout.row(align=True)
        row.prop(self, "x_min"); row.prop(self, "x_max")
        row = layout.row(align=True)
        row.prop(self, "y_min"); row.prop(self, "y_max")
        row = layout.row(align=True)
        row.prop(self, "z_min"); row.prop(self, "z_max")
        row = layout.row(align=True)
        row.prop(self, "x0"); row.prop(self, "y0"); row.prop(self, "z0")

        # Live parse feedback.
        try:
            params = self._params_tuple()
            f_expr = sympy_parser.parse_scalar_field_3d_expression(self.expr)
            sp_ = sympy_parser._sympy()
            box = layout.box()
            box.label(text=f"f(x, y, z) = {sp_.sstr(f_expr)}",
                      icon="FORCE_FORCE")
            grad = sympy_parser.scalar_field_3d_gradient(f_expr)
            box.label(text="∇f :")
            for axis, g in zip("xyz", grad):
                box.label(text=f"  ∂f/∂{axis} = {sp_.sstr(g)}")
            free_names = sorted(s.name for s in f_expr.free_symbols
                                if s.name not in ("x", "y", "z"))
            unknown = [s for s in free_names if s not in params]
            if unknown:
                box.label(text=i18n.tr("Non déclarés : ") + ", ".join(unknown),
                          icon="ERROR")
        except ValueError as exc:
            layout.box().label(text=str(exc), icon="ERROR")

    def execute(self, context):
        try:
            nt = scalar_field_3d_tree.make_scalarfield3d_tree(
                self.expr,
                allowed_params=self._params_tuple(),
                x_default_range=(self.x_min, self.x_max),
                y_default_range=(self.y_min, self.y_max),
                z_default_range=(self.z_min, self.z_max),
                x0_default=self.x0,
                y0_default=self.y0,
                z0_default=self.z0,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        obj = _spawn_object(context, nt, f"f(x,y,z) = {self.expr}")
        # Auto-assign the color-ramp material to the Marker material
        # socket so the user sees f(x, y, z) colour-coded on the
        # spheres out of the box. Without this the modifier defaults
        # to no material and the user gets blank-white spheres until
        # they manually pick the material.
        mod = obj.modifiers[-1]   # the modifier we just added
        scalar_field_mat = default_materials.ensure_scalar_field_3d_material()
        # Make sure the palette (incl. "Gris") exists for the labels.
        default_materials.ensure_default_materials()
        label_mat = default_materials.get_palette_material("Gris")
        for item in nt.interface.items_tree:
            if getattr(item, "in_out", None) != "INPUT":
                continue
            if item.name == "Marker material":
                modifier_inputs.set_value(mod, item.identifier,
                                          scalar_field_mat)
            elif (item.name in ("Label material", "Frame material",
                                  "Axis label material")
                    and label_mat is not None):
                modifier_inputs.set_value(mod, item.identifier, label_mat)
        self.report({"INFO"}, f"Champ scalaire 3D créé : {obj.name}")
        return {"FINISHED"}


# =========================================================================== #
# 3D vector field V: R^3 -> R^3 — create + preset operators
# =========================================================================== #

class REALFN_OT_create_vector_field_3d(bpy.types.Operator):
    """Create a 3D mesh object visualising a vector field V: R³ → R³.

    Two input modes are supported via the ``mode`` enum:

    * ``"explicit"``: the user types three scalar expressions
      V_x(x,y,z), V_y(x,y,z), V_z(x,y,z);
    * ``"from_potential"``: the user types a single scalar potential
      ϕ(x,y,z); the field is V = ∇ϕ (gradient computed symbolically
      by SymPy at construction time).

    The two modes share the same dialog — three component fields and
    one potential field are always present, but the draw method dims
    the irrelevant block. ``execute`` reads only the active block.
    """

    bl_idname = "realfn.create_vector_field_3d"
    bl_label = "Créer un champ de vecteurs V(x, y, z)…"
    bl_description = (
        "Saisir un champ de vecteurs 3D : soit explicitement par ses trois "
        "composantes V_x, V_y, V_z, soit comme gradient d'un potentiel "
        "scalaire ϕ. L'objet créé est une grille NxNxN de flèches, "
        "avec mise en évidence du vecteur au point d'ancrage et "
        "décomposition en composantes cartésiennes"
    )
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        name="Mode",
        description=(
            "Comment spécifier le champ : V explicite (3 composantes) ou "
            "V = ∇ϕ (gradient d'un potentiel scalaire — toujours "
            "conservatif, rotationnel nul)"
        ),
        items=[
            ("explicit",       "Champ explicite V(x,y,z)",
             "Saisir directement les 3 composantes V_x, V_y, V_z"),
            ("from_potential", "Gradient d'un potentiel ϕ(x,y,z)",
             "Saisir un potentiel scalaire ; V = ∇ϕ est calculé "
             "symboliquement (champ conservatif)"),
        ],
        default="explicit",
    )

    # --- Composantes explicites ---
    Vx_expr: bpy.props.StringProperty(
        name="V_x(x, y, z)", default="-y",
    )
    Vy_expr: bpy.props.StringProperty(
        name="V_y(x, y, z)", default="x",
    )
    Vz_expr: bpy.props.StringProperty(
        name="V_z(x, y, z)", default="0",
    )

    # --- Potentiel scalaire ---
    phi_expr: bpy.props.StringProperty(
        name="ϕ(x, y, z)", default="x**2 + y**2 + z**2",
    )

    allowed_params: bpy.props.StringProperty(
        name="Paramètres libres",
        description="Symboles supplémentaires autorisés, séparés par virgules",
        default="",
    )

    # Domain box & basepoint.
    x_min: bpy.props.FloatProperty(name="x min", default=-1.5)
    x_max: bpy.props.FloatProperty(name="x max", default=1.5)
    y_min: bpy.props.FloatProperty(name="y min", default=-1.5)
    y_max: bpy.props.FloatProperty(name="y max", default=1.5)
    z_min: bpy.props.FloatProperty(name="z min", default=-1.5)
    z_max: bpy.props.FloatProperty(name="z max", default=1.5)
    x0: bpy.props.FloatProperty(name="x_0", default=0.5)
    y0: bpy.props.FloatProperty(name="y_0", default=0.5)
    z0: bpy.props.FloatProperty(name="z_0", default=0.5)

    def _params_tuple(self):
        return tuple(p.strip() for p in self.allowed_params.split(",")
                     if p.strip())

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=480)

    def draw(self, context):
        layout = self.layout

        # Mode picker — radio-button style for clarity. The user reads
        # both options in full rather than a collapsed dropdown.
        layout.prop(self, "mode", expand=True)

        # Two input groups; we dim the inactive one rather than hide it
        # entirely so the user can compare/experiment without dialog
        # reopens. Disabled fields are still visible — a clearer UX
        # than abruptly disappearing controls.
        explicit_active = (self.mode == "explicit")
        explicit_box = layout.box()
        explicit_box.enabled = explicit_active
        explicit_box.label(text=i18n.tr("Composantes V :"),
                            icon="ORIENTATION_GLOBAL")
        explicit_box.prop(self, "Vx_expr")
        explicit_box.prop(self, "Vy_expr")
        explicit_box.prop(self, "Vz_expr")

        potential_box = layout.box()
        potential_box.enabled = not explicit_active
        potential_box.label(text=i18n.tr("Potentiel scalaire :"), icon="FORCE_FORCE")
        potential_box.prop(self, "phi_expr")

        layout.prop(self, "allowed_params")
        row = layout.row(align=True); row.prop(self, "x_min"); row.prop(self, "x_max")
        row = layout.row(align=True); row.prop(self, "y_min"); row.prop(self, "y_max")
        row = layout.row(align=True); row.prop(self, "z_min"); row.prop(self, "z_max")
        row = layout.row(align=True); row.prop(self, "x0"); row.prop(self, "y0"); row.prop(self, "z0")

        # Live parse feedback — symbolic computation of div + curl as a
        # sanity check for the user. Errors render in red below the box.
        try:
            sp_ = sympy_parser._sympy()
            params = self._params_tuple()
            if self.mode == "explicit":
                components = sympy_parser.parse_vector_field_3d_components(
                    (self.Vx_expr, self.Vy_expr, self.Vz_expr),
                )
                preview_lines = [
                    f"V_x = {sp_.sstr(components[0])}",
                    f"V_y = {sp_.sstr(components[1])}",
                    f"V_z = {sp_.sstr(components[2])}",
                ]
            else:
                phi = sympy_parser.parse_scalar_field_3d_expression(
                    self.phi_expr,
                )
                components = sympy_parser.scalar_field_3d_gradient(phi)
                preview_lines = [
                    f"ϕ = {sp_.sstr(phi)}",
                    f"V_x = ∂ϕ/∂x = {sp_.sstr(components[0])}",
                    f"V_y = ∂ϕ/∂y = {sp_.sstr(components[1])}",
                    f"V_z = ∂ϕ/∂z = {sp_.sstr(components[2])}",
                ]

            preview = layout.box()
            for ln in preview_lines:
                preview.label(text=ln)

            div = sympy_parser.vector_field_3d_divergence(components)
            curl = sympy_parser.vector_field_3d_curl(components)
            preview.label(text=f"div V = {sp_.sstr(div)}", icon="DOT")
            curl_zero = all(c == 0 for c in curl)
            preview.label(
                text=f"curl V = {tuple(sp_.sstr(c) for c in curl)}"
                     + ("  (champ conservatif)" if curl_zero else ""),
                icon="CON_ROTLIKE",
            )

            # Catch undeclared free symbols early.
            free = set()
            for c in components:
                free |= c.free_symbols
            free_names = sorted(s.name for s in free
                                if s.name not in ("x", "y", "z"))
            unknown = [s for s in free_names if s not in params]
            if unknown:
                preview.label(
                    text=i18n.tr("Non déclarés : ") + ", ".join(unknown),
                    icon="ERROR",
                )
        except ValueError as exc:
            layout.box().label(text=str(exc), icon="ERROR")

    def execute(self, context):
        try:
            if self.mode == "explicit":
                nt = vector_field_3d_tree.make_vector_field_3d_tree(
                    components_source=(self.Vx_expr,
                                         self.Vy_expr,
                                         self.Vz_expr),
                    allowed_params=self._params_tuple(),
                    x_default_range=(self.x_min, self.x_max),
                    y_default_range=(self.y_min, self.y_max),
                    z_default_range=(self.z_min, self.z_max),
                    x0_default=self.x0,
                    y0_default=self.y0,
                    z0_default=self.z0,
                )
                obj_name = (f"V = ({self.Vx_expr}, "
                            f"{self.Vy_expr}, {self.Vz_expr})")
            else:
                nt = vector_field_3d_tree.make_vector_field_3d_tree(
                    potential_source=self.phi_expr,
                    allowed_params=self._params_tuple(),
                    x_default_range=(self.x_min, self.x_max),
                    y_default_range=(self.y_min, self.y_max),
                    z_default_range=(self.z_min, self.z_max),
                    x0_default=self.x0,
                    y0_default=self.y0,
                    z0_default=self.z0,
                )
                obj_name = f"V = ∇({self.phi_expr})"
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        obj = _spawn_object(context, nt, obj_name)
        # Auto-assign a readable material to the per-point norm labels
        # so they're legible without manual setup.
        mod = obj.modifiers[-1]
        default_materials.ensure_default_materials()
        nlbl_mat = default_materials.get_palette_material("Gris")
        if nlbl_mat is not None:
            for item in nt.interface.items_tree:
                if (getattr(item, "in_out", None) == "INPUT"
                        and item.name in ("Norm label material",
                                           "Frame material",
                                           "Axis label material")):
                    modifier_inputs.set_value(mod, item.identifier, nlbl_mat)
        self.report({"INFO"}, f"Champ de vecteurs 3D créé : {obj.name}")
        return {"FINISHED"}


class REALFN_OT_toggle_language(bpy.types.Operator):
    """Bascule l'interface de l'extension entre français et anglais.
    La préférence est persistée avec les préférences Blender."""

    bl_idname = "realfn.toggle_language"
    bl_label = "Basculer français / anglais"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            prefs = context.preferences.addons[__package__].preferences
        except KeyError:
            self.report({"ERROR"}, "Préférences de l'extension introuvables")
            return {"CANCELLED"}
        prefs.language = "EN" if prefs.language == "FR" else "FR"
        # The EnumProperty's update callback schedules the deferred
        # relabel+re-registration (deferred so THIS operator's class
        # isn't re-registered while it is still executing).
        return {"FINISHED"}


# --------------------------------------------------------------------------- #
# Animate the basepoint along its domain (timeline sweep)
# --------------------------------------------------------------------------- #
# The whole add-on is built around scrubbing the basepoint (x₀ / t₀ / u₀)
# in real time. This turns that manual scrub into a playable animation:
# two keyframes sweep the basepoint across the full domain over the scene
# frame range, so the tangent / marker / Taylor centre rolls along the
# curve automatically on playback — ideal for lectures and turntable
# renders. Per kind: (basepoint socket, domain-min socket, domain-max).
_BASEPOINT_SWEEP = {
    "scalar": ("x_0", "x min", "x max"),
    "vector": ("t_0", "t min", "t max"),
    "surface": ("x_0", "x min", "x max"),
    "parametric_surface": ("u_0", "u min", "u max"),
    "scalar_field_3d": ("x_0", "x min", "x max"),
    "vector_field_3d": ("x_0", "x min", "x max"),
}


def _socket_identifier(node_group, name):
    """Modifier-side identifier of the input socket called ``name``."""
    for it in node_group.interface.items_tree:
        if (getattr(it, "item_type", "") == "SOCKET"
                and it.in_out == "INPUT" and it.name == name):
            return it.identifier
    return None


def _basepoint_data_path(mod, bp_id):
    return modifier_inputs.input_data_path(mod, bp_id)


def _basepoint_data_paths(mod, bp_id):
    """Every path a basepoint sweep may live under: the current API's
    and the pre-5.2 IDProperty form (animations made in older files)."""
    name = mod.name.replace("\\", "\\\\").replace('"', '\\"')
    return {
        _basepoint_data_path(mod, bp_id),
        f'modifiers["{name}"]["{bp_id}"]',
        f'modifiers["{name}"].properties.inputs.{bp_id}.value',
    }


def _iter_action_fcurves(obj):
    """Yield ``(collection, fcurve)`` for every F-curve on ``obj``'s
    action, across both Action APIs.

    Blender 4.4 introduced "slotted/layered" actions where F-curves live
    under ``action.layers[].strips[].channelbags[]`` instead of the
    legacy flat ``action.fcurves``. Yielding the owning *collection*
    alongside each curve lets callers remove curves on either API.
    """
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    action = ad.action
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        for fc in legacy:
            yield legacy, fc
        return
    for layer in getattr(action, "layers", []):
        for strip in getattr(layer, "strips", []):
            for cbag in getattr(strip, "channelbags", []):
                for fc in cbag.fcurves:
                    yield cbag.fcurves, fc


class REALFN_OT_animate_basepoint(bpy.types.Operator):
    """Keyframe the basepoint so it sweeps the whole domain across the
    scene frame range — the tangent, marker and Taylor centre then roll
    along the curve automatically during playback."""

    bl_idname = "realfn.animate_basepoint"
    bl_label = "Animer le point de base"
    bl_description = (
        "Pose deux keyframes sur le point de base (x₀ / t₀ / u₀) pour le "
        "faire balayer tout le domaine entre la première et la dernière "
        "frame de la scène. La tangente, le marqueur et les polynômes de "
        "Taylor s'animent automatiquement à la lecture"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_realfn_modifier(context) is not None

    def execute(self, context):
        mod = _active_realfn_modifier(context)
        if mod is None:
            self.report({"ERROR"}, "Aucun objet RealFn actif")
            return {"CANCELLED"}
        obj = context.active_object
        nt = mod.node_group
        kind = nt.get("realfn_kind", "scalar")
        bp_name, lo_name, hi_name = _BASEPOINT_SWEEP.get(
            kind, _BASEPOINT_SWEEP["scalar"])
        bp_id = _socket_identifier(nt, bp_name)
        lo_id = _socket_identifier(nt, lo_name)
        hi_id = _socket_identifier(nt, hi_name)
        if not bp_id or lo_id is None or hi_id is None:
            self.report({"ERROR"}, "Sockets de domaine introuvables")
            return {"CANCELLED"}
        try:
            lo = float(modifier_inputs.get_value(mod, lo_id))
            hi = float(modifier_inputs.get_value(mod, hi_id))
        except (TypeError, ValueError):
            self.report({"ERROR"}, "Bornes du domaine illisibles")
            return {"CANCELLED"}

        scene = context.scene
        f0, f1 = scene.frame_start, scene.frame_end
        if f1 <= f0:
            f1 = f0 + 100
        dp = _basepoint_data_path(mod, bp_id)
        old_paths = _basepoint_data_paths(mod, bp_id)

        # Replace (not stack) any prior sweep on this exact path.
        for coll, fc in list(_iter_action_fcurves(obj)):
            if fc.data_path in old_paths:
                coll.remove(fc)

        modifier_inputs.set_value(mod, bp_id, lo)
        obj.keyframe_insert(data_path=dp, frame=f0)
        modifier_inputs.set_value(mod, bp_id, hi)
        obj.keyframe_insert(data_path=dp, frame=f1)

        # Linear interpolation → constant-speed sweep.
        for _coll, fc in _iter_action_fcurves(obj):
            if fc.data_path == dp:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"

        mod.node_group = mod.node_group
        try:
            obj.update_tag(refresh={'OBJECT'})
        except TypeError:
            obj.update_tag()

        self.report(
            {"INFO"},
            f"Point de base animé de {lo:.3g} à {hi:.3g} "
            f"(frames {f0}–{f1})")
        return {"FINISHED"}


class REALFN_OT_clear_basepoint_animation(bpy.types.Operator):
    """Remove the basepoint sweep animation from the active object."""

    bl_idname = "realfn.clear_basepoint_animation"
    bl_label = "Effacer l'animation du point de base"
    bl_description = (
        "Supprime les keyframes du point de base posées par « Animer le "
        "point de base ». Le point redevient réglable manuellement"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        mod = _active_realfn_modifier(context)
        if mod is None:
            return False
        obj = context.active_object
        return (obj is not None and obj.animation_data is not None
                and obj.animation_data.action is not None)

    def execute(self, context):
        mod = _active_realfn_modifier(context)
        obj = context.active_object
        if mod is None or obj is None:
            return {"CANCELLED"}
        nt = mod.node_group
        kind = nt.get("realfn_kind", "scalar")
        bp_name = _BASEPOINT_SWEEP.get(kind, _BASEPOINT_SWEEP["scalar"])[0]
        bp_id = _socket_identifier(nt, bp_name)
        paths = _basepoint_data_paths(mod, bp_id) if bp_id else set()
        removed = 0
        if paths:
            for coll, fc in list(_iter_action_fcurves(obj)):
                if fc.data_path in paths:
                    coll.remove(fc)
                    removed += 1
        mod.node_group = mod.node_group
        try:
            obj.update_tag(refresh={'OBJECT'})
        except TypeError:
            obj.update_tag()
        if removed:
            self.report({"INFO"}, "Animation du point de base supprimée")
            return {"FINISHED"}
        self.report({"INFO"}, "Aucune animation à supprimer")
        return {"CANCELLED"}


classes = (
    REALFN_OT_toggle_language,
    REALFN_OT_animate_basepoint,
    REALFN_OT_clear_basepoint_animation,
    REALFN_OT_create,
    REALFN_OT_edit,
    REALFN_OT_visible_all_on,
    REALFN_OT_visible_all_off,
    REALFN_OT_visible_invert,
    REALFN_OT_copy_formula,
    REALFN_OT_copy_taylor_poly,
    REALFN_OT_show_taylor_poly,
    REALFN_OT_create_vector,
    REALFN_OT_create_vector_bench,
    REALFN_OT_apply_bench_preset,
    REALFN_OT_bench_rebuild,
    REALFN_OT_edit_rebuild,
    REALFN_OT_restore_snapshot,
    REALFN_OT_install_default_materials,
    REALFN_OT_apply_kinematic_colors,
    # Surface (explicit z = f(x, y))
    REALFN_OT_create_surface,
    # Parametric surface (x(u,v), y(u,v), z(u,v))
    REALFN_OT_create_parametric_surface,
    # 3D scalar field f(x, y, z)
    REALFN_OT_create_scalar_field_3d,
    # 3D vector field V(x, y, z)
    REALFN_OT_create_vector_field_3d,
)

# Per-kind preset operators (save/apply/delete/import/export/reinstall)
# are generated from one spec each — see preset_ops.py.
classes = classes + tuple(preset_ops.build_all())
