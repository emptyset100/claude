"""Headless smoke test of the RealFn Viewer extension against the bpy module.

Usage: python -I tests/test_presets_and_ops.py realfn_viewer [--quick]
(``--quick`` skips building every built-in preset.)
Installs the extension into the user_default repo, enables it, then
exercises every builtin preset of every kind, the create operators,
materials, save handler and the depsgraph sync handler.
"""
import os
import shutil
import sys
import tempfile
import traceback
import warnings
import time
import faulthandler
faulthandler.dump_traceback_later(120, repeat=True)

warnings.simplefilter("always")

SRC = os.path.abspath(sys.argv[1])
QUICK = "--quick" in sys.argv
HOME = tempfile.mkdtemp(prefix="rfn_home_")
os.environ["BLENDER_USER_RESOURCES"] = HOME

import bpy  # noqa: E402
import addon_utils  # noqa: E402

print("Blender", bpy.app.version_string)
repo = bpy.utils.user_resource("EXTENSIONS", path="user_default", create=True)
dst = os.path.join(repo, "realfn_viewer")
shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

PKG = "bl_ext.user_default.realfn_viewer"
mod = addon_utils.enable(PKG, default_set=True, handle_error=lambda e: traceback.print_exc())
assert mod is not None, "enable failed"
print("enabled", PKG)

import importlib  # noqa: E402
m = lambda name: importlib.import_module(PKG + "." + name)  # noqa: E731

FAIL = []


def check(label, fn):
    t0 = time.time()
    try:
        r = fn()
        print(f"  OK   {label} [{time.time()-t0:.1f}s]" + (f" -> {r}" if r not in (None, {"FINISHED"}) else ""))
        return r
    except Exception:
        FAIL.append(label)
        print(f"  FAIL {label}")
        traceback.print_exc()


# First-run timer body
check("auto_install_builtins", lambda: mod._auto_install_builtins())

po = m("preset_ops")
presets = m("presets")
bp = m("builtin_presets")
import json  # noqa: E402

kinds = [
    ("scalar", presets._presets_dir, po._rebuild_scalar),
    ("vector", presets._vector_presets_dir, po._rebuild_vector),
    ("surface", presets._surface_presets_dir, po._rebuild_surface),
    ("parametric", presets._parametric_surface_presets_dir, po._rebuild_parametric),
    ("sf3d", presets._scalar_field_3d_presets_dir, po._rebuild_scalar_field_3d),
    ("vf3d", presets._vector_field_3d_presets_dir, po._rebuild_vector_field_3d),
]
if hasattr(presets, "_vector_bench_presets_dir"):
    check("reinstall bench", bp.reinstall_vector_bench_builtins)
    kinds.append(("bench", presets._vector_bench_presets_dir, po._rebuild_vector_bench))

ops_mod = m("operators")
scene = bpy.context.scene
for kind, d, rebuild in ([] if QUICK else kinds):
    files = sorted(d().glob("*.json"))
    print(f"[{kind}] {len(files)} presets")
    for fp in files:
        data = json.loads(fp.read_text(encoding="utf-8"))

        def go(data=data, kind=kind):
            nt = rebuild(data)
            me = bpy.data.meshes.new("m")
            ob = bpy.data.objects.new(f"{kind}:{fp.stem}", me)
            scene.collection.objects.link(ob)
            md = ob.modifiers.new("RealFn", "NODES")
            md.node_group = nt
            dg = bpy.context.evaluated_depsgraph_get()
            dg.update()
            ev = ob.evaluated_get(dg)
            n = len(ev.data.vertices) if ev.type == "MESH" else -1
            if n <= 0:
                raise RuntimeError(f"empty evaluated geometry ({n})")
            return n
        check(f"{kind}/{fp.stem}", go)

# --- Numerical check of the SymPy -> Math nodes compiler -------------------
comp_mod = m("compiler")
spp = m("sympy_parser")
import sympy as _sp  # noqa: E402
import math as _math  # noqa: E402


def numeric_check(expr_str, xs, *, outline=False, params=None):
    params = params or {}
    e = spp.parse_expression(expr_str)
    nt = bpy.data.node_groups.new("numchk", "GeometryNodeTree")
    nt.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nb = comp_mod.NodeBuilder(nt)
    out = nb.add("NodeGroupOutput")
    line = nb.add("GeometryNodeMeshLine", mode="OFFSET", count_mode="TOTAL")
    line.inputs["Count"].default_value = len(xs)
    line.inputs["Start Location"].default_value = (xs[0], 0, 0)
    line.inputs["Offset"].default_value = ((xs[-1] - xs[0]) / (len(xs) - 1), 0, 0)
    pos = nb.add("GeometryNodeInputPosition")
    sep = nb.add("ShaderNodeSeparateXYZ")
    nb.link(pos.outputs[0], sep.inputs[0])
    var = {"x": sep.outputs["X"]}
    for k, v in params.items():
        var[k] = v
    c = comp_mod.SymPyCompiler(nb, var)
    if outline:
        y = comp_mod.compile_outlined(nb, c, e, name="numchk")
    else:
        y = c.compile(e)
    cx = nb.combine_xyz(sep.outputs["X"], 0.0, y)
    sp_ = nb.add("GeometryNodeSetPosition")
    nb.link(line.outputs[0], sp_.inputs["Geometry"])
    nb.link(cx, sp_.inputs["Position"])
    nb.link(sp_.outputs[0], out.inputs[0])
    me = bpy.data.meshes.new("nc")
    ob = bpy.data.objects.new("nc", me)
    scene.collection.objects.link(ob)
    md = ob.modifiers.new("n", "NODES")
    md.node_group = nt
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    zs = [v.co.z for v in ev.data.vertices]
    xs_real = [v.co.x for v in ev.data.vertices]
    sym = {s.name: s for s in e.free_symbols}
    f = _sp.lambdify(sym.get("x", _sp.Symbol("x")), e, "math")
    worst = 0.0
    for xv, zv in zip(xs_real, zs):
        try:
            ref = float(f(xv))
        except (ValueError, ZeroDivisionError, OverflowError):
            continue
        if _math.isfinite(ref):
            worst = max(worst, abs(ref - zv) / max(1.0, abs(ref)))
    bpy.data.objects.remove(ob)
    if worst > 1e-3:
        raise AssertionError(f"max rel err {worst:.3g}")
    return f"err {worst:.1e}"


XS = [(-3.0 + 6.0 * i / 120) + 0.0137 for i in range(121)]
for ex in ["sin(x)*exp(-x**2/4)", "Heaviside(x-1)", "atan2(x, 2)", "clamp(x, -1, 1)",
           "asinh(x)", "acosh(x**2+1)", "atanh(x/4)", "floor(x)+frac(x)", "Mod(x, 2)",
           "max(x, 0) - min(x, 0)", "ceil(x)", "sqrt(2)*pi*x + log(3)", "abs(x)**3",
           "sign(x)*x**2", "1/(1+x**2)", "log(x+4)", "log(x**2+1)/log(10)", "x*floor(x)"]:
    check(f"numeric {ex}", lambda ex=ex: numeric_check(ex, XS))
    check(f"numeric outlined {ex}", lambda ex=ex: numeric_check(ex, XS, outline=True))
big = "+".join(f"sin({k}*x)*cos(x/{k})/{k}" for k in range(1, 30))
check("numeric outlined big sum", lambda: numeric_check(big, XS, outline=True))

# derivative / Taylor of the new functions through the real builder
tr_mod = m("tree")
for ex in ["Heaviside(x-1)", "clamp(x,-1,1)", "atan2(x,2)", "asinh(x)", "abs(x)", "floor(x)", "x*frac(x)", "Mod(x**2, 3)"]:
    check(f"curve tree d2 t3 {ex}", lambda ex=ex: len(tr_mod.make_realfn_tree(ex, derivative_order=2, taylor_order=3).nodes))

# Rebuild cycles must not leak node groups
def leak_test():
    before = len(bpy.data.node_groups)
    for _ in range(3):
        bpy.ops.realfn.create_surface()
        ob = bpy.context.active_object
        md = [mm for mm in ob.modifiers if mm.type == "NODES"][0]
        old = md.node_group
        st_mod = m("surface_tree")
        new = st_mod.make_surfacefn_tree("cos(x)*cos(y)*exp(-(x**2 + y**2)/6)")
        md.node_group = new
        comp_mod.release_tree(old, keep=new)
        bpy.data.objects.remove(ob)
        comp_mod.release_tree(new)
    return f"{before} -> {len(bpy.data.node_groups)}"
check("rebuild leak", leak_test)

# Operators via EXEC
check("op create", lambda: bpy.ops.realfn.create(expr="x**3-3*x", derivative_order=2, taylor_order=3))
check("op create_vector", lambda: bpy.ops.realfn.create_vector())
check("op create_surface", lambda: bpy.ops.realfn.create_surface())
check("op create_parametric_surface", lambda: bpy.ops.realfn.create_parametric_surface())
check("op create_scalar_field_3d", lambda: bpy.ops.realfn.create_scalar_field_3d())
check("op create_vector_field_3d", lambda: bpy.ops.realfn.create_vector_field_3d())
check("op create_vector_bench", lambda: bpy.ops.realfn.create_vector_bench())
check("op install_default_materials", lambda: bpy.ops.realfn.install_default_materials())

mi = m("modifier_inputs")
mem = m("memorize")


def _active_mod():
    ob = bpy.context.view_layer.objects.active
    return ob, [x for x in ob.modifiers if x.type == "NODES"][0]


def _ident(nt, name):
    for it in nt.interface.items_tree:
        if getattr(it, "in_out", None) == "INPUT" and it.name == name:
            return it.identifier


def roundtrip():
    bpy.ops.realfn.create(expr="sin(a*x)", allowed_params="a", derivative_order=1, taylor_order=2)
    ob, mod = _active_mod()
    nt = mod.node_group
    x0 = _ident(nt, "x_0")
    assert mi.set_value(mod, x0, 1.25)
    a = _ident(nt, "a")
    assert mi.set_value(mod, a, 2.5)
    snap = mem._snapshot_modifier(mod)
    assert abs(snap["range"]["x_0"] - 1.25) < 1e-6, snap["range"]
    assert abs(snap["params"]["a"] - 2.5) < 1e-6, snap["params"]
    mi.set_value(mod, x0, 0.0); mi.set_value(mod, a, 1.0)
    pio = m("preset_io")
    r = pio.apply(snap, mod, pio.SCALAR) if hasattr(pio, "SCALAR") else m("presets").apply_preset_to_modifier(snap, mod)
    assert abs(mi.get_value(mod, x0) - 1.25) < 1e-6
    assert abs(mi.get_value(mod, a) - 2.5) < 1e-6
    mod.node_group = mod.node_group
    assert abs(mi.get_value(mod, x0) - 1.25) < 1e-6, "value lost on node_group reassign"
    return r
check("snapshot/apply roundtrip", roundtrip)


def visibility():
    ob, mod = _active_mod()
    bpy.ops.realfn.visible_all_off()
    vis = [it for it in mod.node_group.interface.items_tree if getattr(it, "in_out", None) == "INPUT" and it.name.startswith("Visible · ")]
    vals = [bool(mi.get_value(mod, it.identifier)) for it in vis]
    assert vis and not any(vals), vals
    bpy.ops.realfn.visible_invert()
    vals = [bool(mi.get_value(mod, it.identifier)) for it in vis]
    assert all(vals), vals
    return len(vis)
check("visibility ops", visibility)


def animate():
    ob, mod = _active_mod()
    scene.frame_start, scene.frame_end = 1, 101
    r = bpy.ops.realfn.animate_basepoint()
    x0 = _ident(mod.node_group, "x_0")
    scene.frame_set(51)
    mid = mi.get_value(mod, x0)
    scene.frame_set(1)
    lo = mi.get_value(mod, x0)
    assert abs(mid) < 0.2 and lo < -4, (lo, mid)
    r2 = bpy.ops.realfn.clear_basepoint_animation()
    return (r, r2, lo, mid)
check("animate basepoint", animate)


def sync_x0():
    scene.realfn_sync_x0 = True
    bpy.ops.realfn.create(expr="cos(x)")
    ob2, mod2 = _active_mod()
    bpy.ops.realfn.create(expr="x**2")
    ob1, mod1 = _active_mod()
    x1 = _ident(mod1.node_group, "x_0")
    mi.set_value(mod1, x1, 0.75)
    # depsgraph_update_post never fires in headless bpy: call it directly.
    m("sync")._depsgraph_handler(scene, None)
    v2 = mi.get_value(mod2, _ident(mod2.node_group, "x_0"))
    scene.realfn_sync_x0 = False
    assert abs(v2 - 0.75) < 1e-6, v2
    return v2
check("sync x0", sync_x0)


def kinematic():
    bpy.ops.realfn.create_vector()
    ob, mod = _active_mod()
    r = m("default_materials").apply_kinematic_color_code(mod)
    assert r["applied"] >= 3, r
    return r
check("kinematic colours", kinematic)



def edit_flows():
    out = []
    # Preset apply operator on the active scalar object (rebuild + release)
    bpy.ops.realfn.create(expr="sin(x)")
    ob, mod = _active_mod()
    old = mod.node_group.name
    fp = sorted(presets._presets_dir().glob("*.json"))[0]
    out.append(bpy.ops.realfn.apply_preset(preset_path=str(fp)))
    ob, mod = _active_mod()
    assert old not in bpy.data.node_groups, "old tree leaked after preset apply"
    # Formula editor rebuild on a surface
    bpy.ops.realfn.create_surface()
    ob, mod = _active_mod()
    old = mod.node_group.name
    ob.realfn_edit.expr = "cos(x)*exp(-y**2)"
    out.append(bpy.ops.realfn.edit_rebuild())
    assert ob.realfn_edit.error == "", ob.realfn_edit.error
    assert old not in bpy.data.node_groups, "old tree leaked after edit"
    # Restore snapshot after save handler wrote one
    mem._snapshot_on_save(None)
    out.append(bpy.ops.realfn.restore_snapshot())
    return out
check("edit / preset / snapshot flows", edit_flows)

dm = m("default_materials")
check("scalar field material", lambda: dm.ensure_scalar_field_3d_material().name)
check("apply palette", lambda: dm.apply_palette({k: (0.1, 0.2, 0.3) for k in dm.DEFAULT_PALETTE}))
check("snapshot palette", lambda: len(dm.snapshot_palette()))

# Edit-props round trip on last created object
ep = m("edit_props")

# Save (memorize save_pre handler) and reload
blend = os.path.join(HOME, "t.blend")
check("save_as_mainfile", lambda: bpy.ops.wm.save_as_mainfile(filepath=blend))
check("frame change / depsgraph", lambda: scene.frame_set(5))

# Language switch
i18n = m("i18n")
check("apply EN", lambda: (bpy.context.preferences.addons[PKG].preferences.__setattr__("language", "EN"), i18n.apply_language(ops_mod, m("panel")))[1])

check("disable", lambda: addon_utils.disable(PKG, default_set=True))
print("\nFAILURES:", FAIL if FAIL else "none")
sys.exit(1 if FAIL else 0)
