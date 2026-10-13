"""Exercise every Vector Viewer panel's draw() with a validating mock layout,
before and after building each visualisation. layout.prop() calls are
checked against the real RNA of the data passed in; operator() calls
against registered operators and their properties."""
import sys, os, shutil, tempfile, traceback, importlib
SRC = os.path.abspath(sys.argv[1])
os.environ["BLENDER_USER_RESOURCES"] = tempfile.mkdtemp()
import bpy, addon_utils
repo = bpy.utils.user_resource("EXTENSIONS", path="user_default", create=True)
shutil.copytree(SRC, os.path.join(repo, "vector_viewer"), ignore=shutil.ignore_patterns("__pycache__"))
PKG = "bl_ext.user_default.vector_viewer"
bpy.context.preferences.filepaths.use_scripts_auto_execute = True
mod_addon = addon_utils.enable(PKG, default_set=True)
m = lambda n: importlib.import_module(PKG + "." + n)

VALID_ICONS = set(bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys())
ERRORS = []
COUNTS = {"prop": 0, "operator": 0}


class OpProps:
    def __init__(self, idname):
        self._idname = idname
        cat, name = idname.split(".")
        self._rna = getattr(getattr(bpy.ops, cat), name).get_rna_type()

    def __setattr__(self, k, v):
        if k.startswith("_"):
            return object.__setattr__(self, k, v)
        if k not in self._rna.properties:
            ERRORS.append(f"operator {self._idname} has no property {k!r}")


class L:
    def __init__(self, where):
        self.where = where
        self.enabled = True
        self.active = True
        self.alert = False
        self.scale_x = self.scale_y = 1.0
        self.use_property_split = False
        self.use_property_decorate = False
        self.alignment = "EXPAND"
        self.operator_context = "INVOKE_DEFAULT"

    def _icon(self, kw):
        ic = kw.get("icon")
        if ic and ic not in VALID_ICONS:
            ERRORS.append(f"{self.where}: invalid icon {ic}")

    def row(self, **kw): return L(self.where)
    column = box = split = grid_flow = column_flow = row
    def separator(self, **kw): pass
    separator_spacer = separator

    def label(self, **kw):
        self._icon(kw)
        if not isinstance(kw.get("text", ""), str):
            ERRORS.append(f"{self.where}: label text not str: {kw.get('text')!r}")

    def panel(self, idname, default_closed=False):
        return L(self.where), L(self.where)

    def panel_prop(self, data, prop):
        return L(self.where), L(self.where)

    def prop(self, data, prop, **kw):
        COUNTS["prop"] += 1
        self._icon(kw)
        if prop.startswith('["'):
            key = prop[2:-2]
            try:
                data[key]
            except Exception as exc:
                ERRORS.append(f"{self.where}: idprop {key} on {data!r}: {exc}")
            return
        rna = getattr(data, "bl_rna", None)
        if rna is None or prop not in rna.properties:
            ERRORS.append(f"{self.where}: {type(data).__name__} has no property {prop!r}")

    def prop_enum(self, data, prop, value, **kw):
        self.prop(data, prop, **kw)

    def props_enum(self, data, prop):
        self.prop(data, prop)

    def prop_search(self, data, prop, sdata, sprop, **kw):
        self.prop(data, prop, **kw)
        rna = getattr(sdata, "bl_rna", None)
        if rna is None or sprop not in rna.properties:
            ERRORS.append(f"{self.where}: search {sprop!r} missing")

    def operator(self, idname, **kw):
        COUNTS["operator"] += 1
        self._icon(kw)
        cat, name = idname.split(".")
        if not hasattr(getattr(bpy.ops, cat), name) or getattr(getattr(bpy.ops, cat), name).idname() is None:
            ERRORS.append(f"{self.where}: unknown operator {idname}")
        try:
            return OpProps(idname)
        except Exception as exc:
            ERRORS.append(f"{self.where}: operator {idname}: {exc}")
            return OpProps.__new__(OpProps)

    def menu(self, *a, **kw): self._icon(kw)
    def template_list(self, *a, **kw): pass
    def template_ID(self, *a, **kw): pass
    def popover(self, *a, **kw): pass
    def context_pointer_set(self, *a, **kw): pass


import types


class FakeSelf:
    def __init__(self, cls):
        self._cls = cls
        self.layout = L(cls.__name__)
        self.bl_idname = getattr(cls, "bl_idname", cls.__name__)

    def __getattr__(self, name):
        v = getattr(self._cls, name)
        if isinstance(v, types.FunctionType):
            return types.MethodType(v, self)
        return v


def draw_all(tag):
    panels = [c for c in mod_addon.classes if issubclass(c, bpy.types.Panel)]
    ctx = bpy.context
    n = 0
    for cls in panels:
        try:
            if hasattr(cls, "poll") and not cls.poll(ctx):
                continue
            fs = FakeSelf(cls)
            if hasattr(cls, "draw_header"):
                cls.draw_header(fs, ctx)
            cls.draw(fs, ctx)
            n += 1
        except Exception:
            ERRORS.append(f"[{tag}] {cls.__name__}: " + traceback.format_exc().strip().splitlines()[-1])
            traceback.print_exc()
    print(f"[{tag}] drew {n} panels")


draw_all("empty scene")
bpy.ops.vector_viewer.build()
draw_all("simple built")
bpy.ops.vector_comp.build()
draw_all("composition built")

print("counts", COUNTS)
print("UI ERRORS:", len(ERRORS))
for e in sorted(set(ERRORS)):
    print("  ", e)
sys.exit(1 if ERRORS else 0)
