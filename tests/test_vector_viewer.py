"""Headless test of the Vector Viewer extension against the bpy module.

Usage: python -I tests/test_vector_viewer.py vector_viewer

For every built-in preset of both panels (simple r/v/a and composition):
apply + build, then check that
  * the host object evaluates to a non-empty mesh,
  * every driver variable path resolves on its target,
  * every driver evaluates (``is_valid``) and the arrows move with time,
  * the modifier sliders (scales, show flags) write through.
"""
import os
import shutil
import sys
import tempfile
import traceback
import importlib

SRC = os.path.abspath(sys.argv[1])
os.environ["BLENDER_USER_RESOURCES"] = tempfile.mkdtemp(prefix="vv_home_")

import bpy  # noqa: E402
import addon_utils  # noqa: E402

print("Blender", bpy.app.version_string)
repo = bpy.utils.user_resource("EXTENSIONS", path="user_default", create=True)
shutil.copytree(SRC, os.path.join(repo, "vector_viewer"),
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
PKG = "bl_ext.user_default.vector_viewer"
# Python drivers need auto-run.
bpy.context.preferences.filepaths.use_scripts_auto_execute = True
mod = addon_utils.enable(PKG, default_set=True,
                         handle_error=lambda e: traceback.print_exc())
assert mod is not None, "enable failed"
m = lambda name: importlib.import_module(PKG + "." + name)  # noqa: E731

FAIL = []


def check(label, fn):
    try:
        r = fn()
        print(f"  OK   {label}" + (f" -> {r}" if r is not None else ""))
    except Exception:
        FAIL.append(label)
        print(f"  FAIL {label}")
        traceback.print_exc()


scene = bpy.context.scene


def host(props):
    ob = bpy.data.objects.get(props.host_name)
    assert ob is not None, "no host object"
    md = [x for x in ob.modifiers if x.type == "NODES"][0]
    return ob, md


def bbox(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    vs = [v.co.copy() for v in ev.data.vertices]
    assert vs, "empty evaluated mesh"
    lo = [min(v[i] for v in vs) for i in range(3)]
    hi = [max(v[i] for v in vs) for i in range(3)]
    return len(vs), lo, hi


def drivers_ok(md):
    nt = md.node_group
    ad = nt.animation_data
    assert ad is not None and len(ad.drivers) > 0, "no drivers"
    n = 0
    for fc in ad.drivers:
        for var in fc.driver.variables:
            for t in var.targets:
                if t.id is None:
                    continue
                t.id.path_resolve(t.data_path)  # raises if invalid
                n += 1
        assert fc.driver.is_valid, f"invalid driver {fc.data_path}: {fc.driver.expression}"
    return len(ad.drivers), n


def run_preset(kind, props, op, pid):
    getattr(bpy.ops, op.split(".")[0]).__getattr__(op.split(".")[1])(preset_id=pid)
    ob, md = host(props)
    scene.frame_set(scene.frame_start + 5)
    n1, lo1, hi1 = bbox(ob)
    nd, nv = drivers_ok(md)
    scene.frame_set(scene.frame_start + 5 + max(10, (scene.frame_end - scene.frame_start) // 3))
    n2, lo2, hi2 = bbox(ob)
    moved = max(abs(a - b) for a, b in zip(lo1 + hi1, lo2 + hi2))
    assert moved > 1e-4, "arrows do not move with time (drivers not evaluated?)"
    return f"{n1} verts, {nd} drivers, {nv} vars"


pv = m("presets")
pc = m("composition_presets")
for pid in pv.PRESET_ORDER:
    check(f"simple/{pid}", lambda pid=pid: run_preset(
        "simple", scene.vector_viewer, "vector_viewer.apply_preset", pid))
for pid in pc.PRESET_ORDER:
    check(f"composition/{pid}", lambda pid=pid: run_preset(
        "comp", scene.vector_comp, "vector_comp.apply_preset", pid))
if hasattr(bpy.ops.vector_comp, "apply_foucault"):
    check("composition/foucault", lambda: bpy.ops.vector_comp.apply_foucault())


def sliders():
    """Scale slider must reach the modifier and change the arrows."""
    bpy.ops.vector_viewer.apply_preset(preset_id=pv.PRESET_ORDER[0])
    props = scene.vector_viewer
    ob, md = host(props)
    scene.frame_set(20)
    _, lo1, hi1 = bbox(ob)
    props.scale_v = props.scale_v * 3 + 1
    ob.update_tag()
    scene.frame_set(21)
    scene.frame_set(20)
    _, lo2, hi2 = bbox(ob)
    moved = max(abs(a - b) for a, b in zip(lo1 + hi1, lo2 + hi2))
    assert moved > 1e-4, "scale_v slider had no effect"
    # show flags
    flags = [p.identifier for p in props.bl_rna.properties
             if p.identifier.startswith("show_")]
    for f in flags:
        setattr(props, f, not getattr(props, f))
    return f"moved {moved:.3f}, toggled {len(flags)} flags"


check("simple sliders", sliders)


def materials():
    mats = m("materials")
    mats.ensure_all()
    found = [mt.name for mt in bpy.data.materials if mats._emission_node(mt) is not None]
    assert found, "no emission material created"
    return f"{len(found)} emission materials"


def old_driver_paths():
    """A .blend from Blender <= 5.1 stores modifiers["M"]["Socket_N"]
    in driver variables; the load handler must rewrite them."""
    bpy.ops.vector_viewer.apply_preset(preset_id=pv.PRESET_ORDER[0])
    ob, md = host(scene.vector_viewer)
    n = 0
    for fc in md.node_group.animation_data.drivers:
        for var in fc.driver.variables:
            for t in var.targets:
                if ".properties.inputs." in t.data_path:
                    ident = t.data_path.split(".properties.inputs.")[1].split(".")[0]
                    t.data_path = f'modifiers["{md.name}"]["{ident}"]'
                    n += 1
    assert n, "no modifier-reading driver variables found"
    mod._upgrade_driver_paths()
    return drivers_ok(md)


check("materials", materials)
if bpy.app.version >= (5, 2, 0):
    check("upgrade pre-5.2 driver paths", old_driver_paths)
blend = os.path.join(os.environ["BLENDER_USER_RESOURCES"], "t.blend")
check("save", lambda: bpy.ops.wm.save_as_mainfile(filepath=blend))
check("reload + drivers", lambda: (bpy.ops.wm.open_mainfile(filepath=blend),
                                    drivers_ok(host(bpy.context.scene.vector_viewer)[1]))[1])
check("clear", lambda: (bpy.ops.vector_viewer.clear(), bpy.ops.vector_comp.clear()))
check("disable", lambda: addon_utils.disable(PKG, default_set=True))
print("\nFAILURES:", FAIL if FAIL else "none")
sys.exit(1 if FAIL else 0)
