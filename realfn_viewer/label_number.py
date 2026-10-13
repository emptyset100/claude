"""
Per-point numeric labels in Geometry Nodes — For-Each Element edition.

History — why this design
-------------------------
Displaying f(x, y, z) as readable text next to each sample point went
through several failed architectures:

1. **Naive StringToCurves** — its String input is read once per
   modifier evaluation; instancing yields N copies of one string.
2. **For-Each zone + ``input_items``** — the Python API for adding
   input items to ``GeometryNodeForeachGeometryElementInput`` is
   broken in Blender 5.1 (``input_items`` doesn't exist on the input
   node; adding sockets raises "Cannot add socket to built-in node").
3. **Glyph atlas + Index Switch** — ``Index Switch`` cannot be indexed
   per element (its Index requires a single value).
4. **Glyph atlas + Pick Instance** — worked in principle, but
   accumulated API traps: ``Geometry to Instance`` merges inputs into
   ONE instance; ``Translate Instances`` defaults to local space;
   MODULO can return its divisor; ``force_non_field`` was silently
   removed in 5.0… Each fix surfaced the next trap.

The architecture below uses the For-Each zone WITHOUT any broken API:

* ``pair_with_output()`` works (validated in production logs).
* The zone's **default Generation item** ("Geometry") is auto-created
  by pairing — no ``gen_items.new()`` needed.
* The zone input's **``Element`` output** is the single-element
  geometry of the current iteration (documented since 4.3).
* **``Sample Index``** — a plain, fully-scriptable node — evaluates
  any field on a geometry at a given index. Applied to ``Element``
  with index 0, it converts per-point fields into the per-iteration
  SINGLE VALUES that string nodes require:

      Element ─→ SampleIndex(Position, 0)     → the point's position
      Element ─→ SampleIndex(Value field, 0)  → f at the point

* **``Value to String``** then formats the number with Blender's own
  formatter (fixed decimals, true minus sign, true decimal point) —
  no hand-rolled digit arithmetic, no glyph atlas, no Pick Instance.

Per iteration, the string is rendered via StringToCurves → Fill →
Extrude, moved to the point's position (+ user offset), and emitted
through the zone's Generation output which joins all labels.

Sampling
--------
String rendering per point is moderately heavy. The zone input's
``Selection`` socket (present and functional) receives a MODULO-free
stride test — only every Nth point is iterated at all.
"""

from __future__ import annotations

import os

import bpy


# Debug logging is opt-in: set the ``REALFN_DEBUG`` environment variable
# (to any non-empty value) before launching Blender to surface the
# Geometry-Nodes API-probing traces below. Off by default so a normal
# session keeps a clean console — the probes still *run* and still fall
# back gracefully; they just don't narrate themselves.
_DEBUG = bool(os.environ.get("REALFN_DEBUG"))


def _dbg(msg):
    if _DEBUG:
        print(msg)


_NODE_GROUP_NAME = "LabelNumber"

# Bumped whenever the group's internal structure changes. A stale group
# saved in a .blend (the lookup is idempotent by name) is rebuilt when
# its stored version doesn't match.
_NODE_GROUP_VERSION = 8


def get_label_number_node_group():
    """Return the bundled ``LabelNumber`` node group, creating it if
    absent and rebuilding it if its version is outdated."""
    existing = bpy.data.node_groups.get(_NODE_GROUP_NAME)
    if existing is not None:
        if existing.get("rfn_version", 0) == _NODE_GROUP_VERSION:
            return existing
        try:
            bpy.data.node_groups.remove(existing)
        except Exception:
            existing.name = f"{_NODE_GROUP_NAME}.old"
    ng = _build_label_number_node_group()
    ng["rfn_version"] = _NODE_GROUP_VERSION
    return ng


def _build_label_number_node_group():
    ng = bpy.data.node_groups.new(_NODE_GROUP_NAME, "GeometryNodeTree")

    # ---- Interface (unchanged across versions — callers untouched) ----
    ng.interface.new_socket("Geometry", in_out="OUTPUT",
                            socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Points", in_out="INPUT",
                            socket_type="NodeSocketGeometry")
    val_s = ng.interface.new_socket("Value", in_out="INPUT",
                                    socket_type="NodeSocketFloat")
    # Value is a FIELD (varies per point). ``force_non_field`` was
    # removed in Blender 5.0; the 5.x declaration is the
    # ``structure_type`` enum. Logged — never a silent no-op.
    _field_decl = None
    for val in ("DYNAMIC", "FIELD"):
        try:
            val_s.structure_type = val
            _field_decl = f"structure_type={val!r}"
            break
        except (AttributeError, TypeError, ValueError):
            continue
    if _field_decl is None:
        try:
            val_s.force_non_field = False
            _field_decl = "force_non_field=False (API ≤4.x)"
        except AttributeError:
            _field_decl = "AUCUNE (ni structure_type ni force_non_field)"
    _dbg(f"[RealFn] LabelNumber : déclaration field du socket Value → "
         f"{_field_decl}")

    size_s = ng.interface.new_socket("Size", in_out="INPUT",
                                     socket_type="NodeSocketFloat")
    size_s.default_value = 0.1
    off_s = ng.interface.new_socket("Offset", in_out="INPUT",
                                    socket_type="NodeSocketVector")
    off_s.default_value = (0.0, 0.0, 0.12)
    stride_s = ng.interface.new_socket("Stride", in_out="INPUT",
                                       socket_type="NodeSocketInt")
    stride_s.default_value = 1
    stride_s.min_value = 1
    dec_s = ng.interface.new_socket("Decimals", in_out="INPUT",
                                    socket_type="NodeSocketInt")
    dec_s.default_value = 2
    dec_s.min_value = 0
    dec_s.max_value = 4
    face_s = ng.interface.new_socket("Face front", in_out="INPUT",
                                     socket_type="NodeSocketBool")
    face_s.default_value = False
    maxp_s = ng.interface.new_socket("Max points", in_out="INPUT",
                                     socket_type="NodeSocketInt")
    # Performance guard: if the incoming geometry has more points
    # than this, NO labels are generated at all (the For-Each
    # Selection collapses to False everywhere). Rendering a string
    # mesh per point is fine for classroom-sized grids but a 30³
    # grid would mean 27 000 StringToCurves evaluations — enough to
    # freeze a session. The guard makes the failure mode "labels
    # quietly absent" instead of "Blender unresponsive".
    maxp_s.default_value = 2000
    maxp_s.min_value = 1

    nodes = ng.nodes
    links = ng.links

    group_in = nodes.new("NodeGroupInput")
    group_in.location = (-1200, 0)
    group_out = nodes.new("NodeGroupOutput")
    group_out.location = (1600, 0)

    # ---- Stride selection (MODULO-free): idx − s·⌊idx/s⌋ < 0.5 --------
    idx = nodes.new("GeometryNodeInputIndex")
    idx.location = (-1200, -300)
    div = nodes.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.location = (-1050, -300)
    links.new(idx.outputs["Index"], div.inputs[0])
    links.new(group_in.outputs["Stride"], div.inputs[1])
    flo = nodes.new("ShaderNodeMath")
    flo.operation = "FLOOR"
    flo.location = (-920, -300)
    links.new(div.outputs[0], flo.inputs[0])
    mul = nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.location = (-790, -300)
    links.new(flo.outputs[0], mul.inputs[0])
    links.new(group_in.outputs["Stride"], mul.inputs[1])
    rem = nodes.new("ShaderNodeMath")
    rem.operation = "SUBTRACT"
    rem.location = (-660, -300)
    links.new(idx.outputs["Index"], rem.inputs[0])
    links.new(mul.outputs[0], rem.inputs[1])
    sel = nodes.new("FunctionNodeCompare")
    sel.data_type = "FLOAT"
    sel.operation = "LESS_THAN"
    sel.location = (-530, -300)
    links.new(rem.outputs[0], sel.inputs[0])
    try:
        sel.inputs[1].default_value = 0.5
    except (TypeError, IndexError):
        pass

    # ---- For-Each Element zone ----------------------------------------
    # Only API surfaces that are PROVEN to work in Blender 5.1 are
    # used (validated by production logs from this very extension):
    #   * creating the input/output pair
    #   * fe_out.domain = "POINT"
    #   * pair_with_output() — auto-creates the default Generation
    #     item "Geometry" on both sides
    #   * fe_in.outputs["Element"] — the current iteration's
    #     single-element geometry
    # NOT used: input_items / gen_items.new (broken in 5.1).
    fe_in = nodes.new("GeometryNodeForeachGeometryElementInput")
    fe_in.location = (-350, 0)
    fe_in.label = "labels: pour chaque point"
    fe_out = nodes.new("GeometryNodeForeachGeometryElementOutput")
    fe_out.location = (1100, 0)
    fe_out.label = "labels: fin"
    fe_out.domain = "POINT"
    fe_in.pair_with_output(fe_out)

    _dbg(f"[RealFn] LabelNumber For-Each : "
         f"fe_in.inputs={[s.name for s in fe_in.inputs]}, "
         f"fe_in.outputs={[s.name for s in fe_in.outputs]}, "
         f"fe_out.inputs={[s.name for s in fe_out.inputs]}, "
         f"fe_out.outputs={[s.name for s in fe_out.outputs]}")

    try:
        links.new(group_in.outputs["Points"], fe_in.inputs["Geometry"])
    except KeyError:
        links.new(group_in.outputs["Points"], fe_in.inputs[0])

    # ---- Performance guard: point count ≤ Max points -------------------
    # Domain Size yields the (single-value) point count of the input
    # mesh; comparing it to the Max points socket gives a single
    # boolean that gates the whole Selection. Above the threshold the
    # zone iterates nothing — labels are quietly absent instead of
    # the modifier freezing on tens of thousands of string meshes.
    dsize = nodes.new("GeometryNodeAttributeDomainSize")
    dsize.location = (-700, -480)
    dsize.label = "nombre de points"
    try:
        dsize.component = "MESH"
    except (AttributeError, TypeError):
        pass
    links.new(group_in.outputs["Points"], dsize.inputs["Geometry"])
    cnt_ok = nodes.new("FunctionNodeCompare")
    cnt_ok.data_type = "INT"
    cnt_ok.operation = "LESS_EQUAL"
    cnt_ok.location = (-540, -480)
    cnt_ok.label = "≤ Max points"
    # INT comparison sockets are "A"/"B" at indices 2/3 on Compare.
    try:
        links.new(dsize.outputs["Point Count"], cnt_ok.inputs["A"])
        links.new(group_in.outputs["Max points"], cnt_ok.inputs["B"])
    except KeyError:
        links.new(dsize.outputs[0], cnt_ok.inputs[2])
        links.new(group_in.outputs["Max points"], cnt_ok.inputs[3])
    sel_guarded = nodes.new("FunctionNodeBooleanMath")
    sel_guarded.operation = "AND"
    sel_guarded.location = (-400, -400)
    links.new(sel.outputs["Result"], sel_guarded.inputs[0])
    links.new(cnt_ok.outputs["Result"], sel_guarded.inputs[1])
    try:
        links.new(sel_guarded.outputs[0], fe_in.inputs["Selection"])
    except KeyError:
        pass  # selection socket absent → all points labelled

    elem_sock = None
    try:
        elem_sock = fe_in.outputs["Element"]
    except KeyError:
        # Defensive: second output by position (Index, Element).
        if len(fe_in.outputs) >= 2:
            elem_sock = fe_in.outputs[1]
    if elem_sock is None:
        raise RuntimeError(
            "RealFnViewer : la zone For-Each de cette version de "
            "Blender n'expose pas la sortie « Element » nécessaire "
            "aux étiquettes numériques."
        )

    # ---- Inside the zone: field → single value via Sample Index -------
    # Sample Index is attribute-aware ON THE GEOMETRY IT IS GIVEN.
    # Given the single-element geometry, index 0 IS the current point,
    # so any field evaluated here yields that point's value as a
    # SINGLE VALUE — exactly what the string nodes require.
    pos_field = nodes.new("GeometryNodeInputPosition")
    pos_field.location = (-150, -350)

    samp_pos = nodes.new("GeometryNodeSampleIndex")
    samp_pos.location = (50, -250)
    samp_pos.label = "position du point courant"
    samp_pos.data_type = "FLOAT_VECTOR"
    samp_pos.domain = "POINT"
    links.new(elem_sock, samp_pos.inputs["Geometry"])
    try:
        links.new(pos_field.outputs["Position"], samp_pos.inputs["Value"])
    except KeyError:
        # The Value socket name can carry a type suffix on some builds.
        for cand in ("Value", "Value_Vector"):
            try:
                links.new(pos_field.outputs["Position"],
                          samp_pos.inputs[cand])
                break
            except KeyError:
                continue
    # Index input defaults to 0 — the only point of the element.

    samp_val = nodes.new("GeometryNodeSampleIndex")
    samp_val.location = (50, -50)
    samp_val.label = "f au point courant"
    samp_val.data_type = "FLOAT"
    samp_val.domain = "POINT"
    links.new(elem_sock, samp_val.inputs["Geometry"])
    try:
        links.new(group_in.outputs["Value"], samp_val.inputs["Value"])
    except KeyError:
        for cand in ("Value", "Value_Float"):
            try:
                links.new(group_in.outputs["Value"],
                          samp_val.inputs[cand])
                break
            except KeyError:
                continue

    # ---- Number → string → solid text mesh ----------------------------
    v2s = nodes.new("FunctionNodeValueToString")
    v2s.location = (300, -50)
    v2s.label = "format ±D.DD"
    try:
        links.new(samp_val.outputs["Value"], v2s.inputs["Value"])
    except KeyError:
        links.new(samp_val.outputs[0], v2s.inputs[0])
    # Decimal count is user-driven via the group's Decimals input.
    try:
        links.new(group_in.outputs["Decimals"], v2s.inputs["Decimals"])
    except KeyError:
        try:
            links.new(group_in.outputs["Decimals"], v2s.inputs[1])
        except (IndexError, KeyError):
            pass

    s2c = nodes.new("GeometryNodeStringToCurves")
    s2c.location = (470, -50)
    try:
        s2c.align_x = "CENTER"
        s2c.align_y = "MIDDLE"
    except (AttributeError, TypeError):
        pass
    try:
        links.new(v2s.outputs["String"], s2c.inputs["String"])
    except KeyError:
        links.new(v2s.outputs[0], s2c.inputs[0])
    # Glyph height = the group's Size input, applied natively by the
    # font engine — no instance scaling involved.
    try:
        links.new(group_in.outputs["Size"], s2c.inputs["Size"])
    except KeyError:
        pass

    s2c_out = (s2c.outputs["Curve Instances"]
               if "Curve Instances" in s2c.outputs
               else s2c.outputs[0])
    realize = nodes.new("GeometryNodeRealizeInstances")
    realize.location = (650, -50)
    links.new(s2c_out, realize.inputs[0])

    fill = nodes.new("GeometryNodeFillCurve")
    fill.location = (790, -50)
    links.new(realize.outputs[0], fill.inputs[0])

    extr = nodes.new("GeometryNodeExtrudeMesh")
    extr.location = (930, -50)
    extr.mode = "FACES"
    links.new(fill.outputs[0], extr.inputs["Mesh"])
    # Extrusion depth proportional to glyph height (Size × 0.1).
    depth = nodes.new("ShaderNodeMath")
    depth.operation = "MULTIPLY"
    depth.location = (790, -220)
    links.new(group_in.outputs["Size"], depth.inputs[0])
    try:
        depth.inputs[1].default_value = 0.1
    except (TypeError, IndexError):
        pass
    try:
        links.new(depth.outputs[0], extr.inputs["Offset Scale"])
    except KeyError:
        pass

    # ---- Place at the point's position + user offset ------------------
    target = nodes.new("ShaderNodeVectorMath")
    target.operation = "ADD"
    target.location = (300, -250)
    target.label = "position + offset"
    try:
        links.new(samp_pos.outputs["Value"], target.inputs[0])
    except KeyError:
        links.new(samp_pos.outputs[0], target.inputs[0])
    links.new(group_in.outputs["Offset"], target.inputs[1])

    place = nodes.new("GeometryNodeTransform")
    place.location = (1000, 100)
    place.label = "placer l'étiquette"
    try:
        links.new(extr.outputs["Mesh"], place.inputs["Geometry"])
    except KeyError:
        links.new(extr.outputs[0], place.inputs[0])
    links.new(target.outputs["Vector"], place.inputs["Translation"])

    # ---- Orientation: flat (XY) or facing the front view --------------
    # Text from StringToCurves lies in the XY plane (readable from the
    # top view, normal +Z). With "Face front" enabled we rotate it 90°
    # about X: the glyphs stand upright in the XZ plane, normal −Y —
    # i.e. facing Blender's front view (Numpad 1). The Transform node
    # applies rotation about the text's own centre (it is centre-
    # aligned at the origin) BEFORE the translation, so the pivot is
    # correct by construction.
    rot_switch = nodes.new("GeometryNodeSwitch")
    rot_switch.input_type = "VECTOR"
    rot_switch.location = (800, 220)
    rot_switch.label = "orientation"
    try:
        links.new(group_in.outputs["Face front"],
                  rot_switch.inputs["Switch"])
    except KeyError:
        links.new(group_in.outputs["Face front"], rot_switch.inputs[0])
    # False → (0, 0, 0) : flat XY (default). True → (π/2, 0, 0).
    try:
        rot_switch.inputs["False"].default_value = (0.0, 0.0, 0.0)
        rot_switch.inputs["True"].default_value = (1.5707963, 0.0, 0.0)
    except (KeyError, TypeError):
        try:
            rot_switch.inputs[2].default_value = (0.0, 0.0, 0.0)
            rot_switch.inputs[3].default_value = (1.5707963, 0.0, 0.0)
        except (IndexError, TypeError):
            pass
    rot_out = (rot_switch.outputs["Output"]
               if "Output" in rot_switch.outputs
               else rot_switch.outputs[0])
    # Vector → Rotation implicit conversion (Euler XYZ) on the
    # Transform node's Rotation input.
    try:
        links.new(rot_out, place.inputs["Rotation"])
    except KeyError:
        pass

    # ---- Emit through the zone's default Generation output ------------
    # Socket layout of fe_out, MEASURED on Blender 5.1 (production
    # console log from this extension):
    #
    #   fe_out.inputs  = ['',  'Geometry', '']
    #                     sep   GENERATION  ext
    #   fe_out.outputs = ['Geometry', '', 'Geometry', '']
    #                     MAIN        sep  GENERATION   ext
    #                     pass-through      (joined labels)
    #
    # i.e. outputs[0] "Geometry" is the MAIN pass-through of the input
    # geometry (the points themselves — it exists even with main_items
    # empty), and the GENERATION join is the LAST "Geometry"-named
    # output, after the '' separator. Taking the FIRST match wired the
    # points pass-through to the group output and the labels never
    # left the zone. So: always select the LAST "Geometry"-named
    # socket, on both sides (generation items come after main items).
    gen_in = None
    for s in fe_out.inputs:
        if s.name == "Geometry":
            gen_in = s          # keep the LAST match
    if gen_in is None and len(fe_out.inputs) > 0:
        gen_in = fe_out.inputs[0]
    links.new(place.outputs["Geometry"]
              if "Geometry" in place.outputs else place.outputs[0],
              gen_in)

    gen_out = None
    for s in fe_out.outputs:
        if s.name == "Geometry":
            gen_out = s         # keep the LAST match
    if gen_out is None and len(fe_out.outputs) > 0:
        gen_out = fe_out.outputs[0]
    links.new(gen_out, group_out.inputs["Geometry"])

    return ng
