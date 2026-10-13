"""
Bundled "Ecrit" Geometry Nodes group.

Wraps the user-provided node tree generator that turns a ``String``
input into a small 3D mesh (extruded glyphs from the font
``STIX Two Math Regular``). The tree's pipeline is:

    String  →  StringToCurves  →  FillCurve  →  ExtrudeMesh  →  RealizeInstances  →  Geometry

It's the workhorse for displaying floating-point values (forces,
field magnitudes, parameter readouts…) directly in 3D space as
sculpted text rather than as a viewport overlay — useful when the
camera moves and the labels need to live in world coordinates.

API
---
:func:`get_ecrit_node_group` is the cached, idempotent entry point.
Use it everywhere — calling it N times yields the same datablock,
not N copies. The verbatim generator :func:`ecrit_1_node_group` is
kept for fidelity to the original script.
"""

from __future__ import annotations

import bpy
import typing


_NODE_GROUP_NAME = "Ecrit"


def get_ecrit_node_group():
    """Return the bundled "Ecrit" node group, creating it if absent.

    Idempotent: subsequent calls return the same datablock by name.
    First-call cost: a one-shot tree build (cheap — half a dozen
    nodes). Subsequent calls are a single dict lookup in
    ``bpy.data.node_groups``.
    """
    existing = bpy.data.node_groups.get(_NODE_GROUP_NAME)
    if existing is not None:
        return existing
    return ecrit_1_node_group({})


def ecrit_1_node_group(node_tree_names: dict[typing.Callable, str]):
    """Initialize Ecrit node group.

    Verbatim copy of the user-provided generator. Returns the newly
    created tree; if a tree with the same name already exists, Blender
    auto-suffixes (``Ecrit.001`` etc.) — that's why
    :func:`get_ecrit_node_group` is the recommended entry point, since
    it caches by name and avoids the suffix proliferation.
    """
    ecrit_1 = bpy.data.node_groups.new(type='GeometryNodeTree',
                                         name=_NODE_GROUP_NAME)

    ecrit_1.color_tag = 'NONE'
    ecrit_1.description = ""
    ecrit_1.default_group_node_width = 140
    # Newer Blender attribute — wrap in try so older 4.x still loads.
    try:
        ecrit_1.show_modifier_manage_panel = True
    except AttributeError:
        pass

    # ecrit_1 interface

    # Socket Geometry (output)
    geometry_socket = ecrit_1.interface.new_socket(
        name="Geometry", in_out='OUTPUT',
        socket_type='NodeSocketGeometry',
    )
    try:
        geometry_socket.attribute_domain = 'POINT'
        geometry_socket.default_input = 'VALUE'
        geometry_socket.structure_type = 'AUTO'
    except (AttributeError, TypeError):
        # ``default_input`` / ``structure_type`` only exist on recent
        # Blender 4.x — silently skip on older versions.
        pass

    # Socket String (input)
    string_socket = ecrit_1.interface.new_socket(
        name="String", in_out='INPUT', socket_type='NodeSocketString',
    )
    string_socket.default_value = ""
    try:
        string_socket.subtype = 'NONE'
        string_socket.attribute_domain = 'POINT'
        string_socket.default_input = 'VALUE'
        string_socket.structure_type = 'AUTO'
    except (AttributeError, TypeError):
        pass

    # --- Nodes ----------------------------------------------------------
    group_output = ecrit_1.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    group_input = ecrit_1.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"

    # Fill Curve: turns the closed glyph contours into a filled mesh.
    fill_curve = ecrit_1.nodes.new("GeometryNodeFillCurve")
    fill_curve.name = "Fill Curve"
    # Default Group ID / Mode / Fill Rule — defensive index access in
    # case Blender ever renames internal sockets.
    try:
        fill_curve.inputs[1].default_value = 0
        fill_curve.inputs[2].default_value = 'Triangles'
        fill_curve.inputs[3].default_value = 'Even-Odd'
    except (IndexError, KeyError, TypeError):
        pass

    # Flip Faces: needed because the extruded base lives on the other
    # side of the glyph; flipping makes the front face the visible one.
    flip_faces = ecrit_1.nodes.new("GeometryNodeFlipFaces")
    flip_faces.name = "Flip Faces"
    flip_faces.hide = True
    try:
        flip_faces.inputs[1].hide = True
        flip_faces.inputs[1].default_value = True
    except (IndexError, KeyError):
        pass

    # Extrude Mesh: pulls the filled glyph out into 3D.
    extrude_mesh = ecrit_1.nodes.new("GeometryNodeExtrudeMesh")
    extrude_mesh.name = "Extrude Mesh"
    extrude_mesh.hide = True
    extrude_mesh.mode = 'FACES'
    for sock_idx in (1, 2, 3, 4):
        try:
            extrude_mesh.inputs[sock_idx].hide = True
        except (IndexError, KeyError):
            pass
    for sock_idx in (1, 2):
        try:
            extrude_mesh.outputs[sock_idx].hide = True
        except (IndexError, KeyError):
            pass
    try:
        extrude_mesh.inputs[1].default_value = True            # Selection
        extrude_mesh.inputs[2].default_value = (0.0, 0.0, 0.0)  # Offset
        extrude_mesh.inputs[3].default_value = 0.03            # Offset Scale
        extrude_mesh.inputs[4].default_value = True            # Individual
    except (IndexError, KeyError, TypeError):
        pass

    # Join Geometry: merge the front (flipped) face with the extruded body.
    join_geometry = ecrit_1.nodes.new("GeometryNodeJoinGeometry")
    join_geometry.name = "Join Geometry.002"

    # Realize Instances: each glyph in the input string is an instance;
    # we realize them so downstream nodes see one mesh with all glyphs.
    realize_instances = ecrit_1.nodes.new("GeometryNodeRealizeInstances")
    realize_instances.name = "Realize Instances"
    try:
        realize_instances.realize_to_point_domain = True
    except AttributeError:
        pass
    try:
        realize_instances.inputs[1].default_value = True
        realize_instances.inputs[2].default_value = True
        realize_instances.inputs[3].default_value = 0
    except (IndexError, KeyError):
        pass

    # String to Curves: the heart of the pipeline.
    string_to_curves = ecrit_1.nodes.new("GeometryNodeStringToCurves")
    string_to_curves.name = "String to Curves"
    # Hide rarely-used sockets so the node group is tidy in the editor.
    for sock_idx in (1, 6, 7, 8, 10, 11):
        try:
            string_to_curves.inputs[sock_idx].hide = True
        except (IndexError, KeyError):
            pass
    for sock_idx in (1, 2, 4):
        try:
            string_to_curves.outputs[sock_idx].hide = True
        except (IndexError, KeyError):
            pass
    # Default values.
    try:
        string_to_curves.inputs[1].default_value = 1.0
    except (IndexError, KeyError):
        pass
    # Font: try the math font if the user has it; otherwise leave
    # default (Blender's built-in BMonofont). Don't fail if absent —
    # numeric labels render fine in any monospace-ish font.
    for font_name in ("STIX Two Math Regular.001",
                       "STIX Two Math Regular",
                       "STIXTwoMath-Regular"):
        if font_name in bpy.data.fonts:
            try:
                string_to_curves.inputs[2].default_value = bpy.data.fonts[font_name]
            except (IndexError, KeyError, TypeError):
                pass
            break
    try:
        string_to_curves.inputs[3].default_value = 'Center'         # Align X
        string_to_curves.inputs[4].default_value = 'Top Baseline'   # Align Y
        string_to_curves.inputs[5].default_value = 'Bottom Left'    # Pivot Point
        string_to_curves.inputs[6].default_value = 1.0              # Character Spacing
        string_to_curves.inputs[7].default_value = 1.0              # Word Spacing
        string_to_curves.inputs[8].default_value = 1.0              # Line Spacing
        string_to_curves.inputs[9].default_value = 'Overflow'
        string_to_curves.inputs[10].default_value = 0.0             # Text Box Width
        string_to_curves.inputs[11].default_value = 0.0             # Text Box Height
    except (IndexError, KeyError, TypeError):
        pass

    # --- Layout ---------------------------------------------------------
    ecrit_1.nodes["Group Output"].location = (611.75, 11.0)
    ecrit_1.nodes["Group Input"].location = (-695.24, -31.0)
    ecrit_1.nodes["Fill Curve"].location = (-148.25, 12.0)
    ecrit_1.nodes["Flip Faces"].location = (41.75, -52.0)
    ecrit_1.nodes["Extrude Mesh"].location = (41.75, 26.0)
    ecrit_1.nodes["Join Geometry.002"].location = (231.75, 11.0)
    ecrit_1.nodes["Realize Instances"].location = (421.75, 11.0)
    ecrit_1.nodes["String to Curves"].location = (-505.24, 12.0)
    for n_name in ("Group Output", "Group Input", "Fill Curve", "Flip Faces",
                    "Extrude Mesh", "Join Geometry.002", "Realize Instances"):
        ecrit_1.nodes[n_name].width = 140.0
        ecrit_1.nodes[n_name].height = 100.0
    ecrit_1.nodes["String to Curves"].width = 306.985
    ecrit_1.nodes["String to Curves"].height = 100.0

    # --- Links ----------------------------------------------------------
    ecrit_1.links.new(join_geometry.outputs[0], realize_instances.inputs[0])
    ecrit_1.links.new(fill_curve.outputs[0], flip_faces.inputs[0])
    ecrit_1.links.new(fill_curve.outputs[0], extrude_mesh.inputs[0])
    ecrit_1.links.new(string_to_curves.outputs[0], fill_curve.inputs[0])
    ecrit_1.links.new(flip_faces.outputs[0], join_geometry.inputs[0])
    ecrit_1.links.new(group_input.outputs[0], string_to_curves.inputs[0])
    ecrit_1.links.new(realize_instances.outputs[0], group_output.inputs[0])
    ecrit_1.links.new(extrude_mesh.outputs[0], join_geometry.inputs[0])

    return ecrit_1
