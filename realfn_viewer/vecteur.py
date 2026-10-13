"""
Bundled "Vecteur" Geometry Nodes group.

This module embeds the node-tree generator originally provided as
``vecteur.py``. The tree draws a 3D arrow from an ``orig`` point to an
``ext`` point: a thin tube along the line plus a cone at the tip,
oriented and scaled automatically from the end-to-end displacement.

API
---
The bottom-level function ``vecteur_1_node_group`` is the verbatim
generator from the original file — kept untouched for fidelity. It
unconditionally creates a fresh node tree named ``"Vecteur"`` (or
``"Vecteur.001"``, etc., if one already exists).

Callers should normally use :func:`get_vecteur_node_group` instead:
it caches the tree by name so a Blender session ends up with exactly
one ``Vecteur`` group regardless of how many vector functions the
user creates.
"""

from __future__ import annotations

import bpy
import mathutils  # noqa: F401  (kept for parity with original)
import os         # noqa: F401
import typing


_NODE_GROUP_NAME = "Vecteur"


def get_vecteur_node_group():
    """Return the bundled "Vecteur" node group, creating it if absent.

    Idempotent: subsequent calls return the same datablock. The
    cached lookup is by name in ``bpy.data.node_groups``, so if a
    user-renamed or duplicated copy exists with the same name they
    get that one — which is the documented Blender convention for
    asset-style sharing of node groups.
    """
    existing = bpy.data.node_groups.get(_NODE_GROUP_NAME)
    if existing is not None:
        return existing
    return vecteur_1_node_group({})


def vecteur_1_node_group(node_tree_names: dict[typing.Callable, str]):
    """Initialize Vecteur node group"""
    vecteur_1 = bpy.data.node_groups.new(type='GeometryNodeTree', name="Vecteur")

    vecteur_1.color_tag = 'NONE'
    vecteur_1.description = ""
    vecteur_1.default_group_node_width = 140
    vecteur_1.show_modifier_manage_panel = True

    # vecteur_1 interface

    # Socket Geometry
    geometry_socket = vecteur_1.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'
    geometry_socket.default_input = 'VALUE'
    geometry_socket.structure_type = 'AUTO'

    # Socket orig
    orig_socket = vecteur_1.interface.new_socket(name="orig", in_out='INPUT', socket_type='NodeSocketVector')
    orig_socket.default_value = (0.0, 0.0, 0.0)
    orig_socket.min_value = -10000.0
    orig_socket.max_value = 10000.0
    orig_socket.subtype = 'NONE'
    orig_socket.attribute_domain = 'POINT'
    orig_socket.default_input = 'VALUE'
    orig_socket.structure_type = 'AUTO'

    # Socket ext
    ext_socket = vecteur_1.interface.new_socket(name="ext", in_out='INPUT', socket_type='NodeSocketVector')
    ext_socket.default_value = (0.0, 0.0, 0.0)
    ext_socket.min_value = -10000.0
    ext_socket.max_value = 10000.0
    ext_socket.subtype = 'NONE'
    ext_socket.attribute_domain = 'POINT'
    ext_socket.default_input = 'VALUE'
    ext_socket.structure_type = 'AUTO'

    # Initialize vecteur_1 nodes

    # Node Group Output
    group_output = vecteur_1.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    # Node Group Input
    group_input = vecteur_1.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"

    # Node Curve Line
    curve_line = vecteur_1.nodes.new("GeometryNodeCurvePrimitiveLine")
    curve_line.name = "Curve Line"
    curve_line.mode = 'POINTS'

    # Node Cone
    cone = vecteur_1.nodes.new("GeometryNodeMeshCone")
    cone.name = "Cone"
    cone.fill_type = 'NGON'
    # Vertices
    cone.inputs[0].default_value = 32
    # Side Segments
    cone.inputs[1].default_value = 1
    # Fill Segments
    cone.inputs[2].default_value = 1
    # Radius Top
    cone.inputs[3].default_value = 0.0

    # Node Join Geometry
    join_geometry = vecteur_1.nodes.new("GeometryNodeJoinGeometry")
    join_geometry.name = "Join Geometry"

    # Node Align Rotation to Vector
    align_rotation_to_vector = vecteur_1.nodes.new("FunctionNodeAlignRotationToVector")
    align_rotation_to_vector.name = "Align Rotation to Vector"
    align_rotation_to_vector.axis = 'Z'
    align_rotation_to_vector.pivot_axis = 'AUTO'
    # Rotation
    align_rotation_to_vector.inputs[0].default_value = (0.0, 0.0, 0.0)
    # Factor
    align_rotation_to_vector.inputs[1].default_value = 1.0

    # Node Curve to Mesh
    curve_to_mesh = vecteur_1.nodes.new("GeometryNodeCurveToMesh")
    curve_to_mesh.name = "Curve to Mesh"
    # Scale
    curve_to_mesh.inputs[2].default_value = 1.0
    # Fill Caps
    curve_to_mesh.inputs[3].default_value = True

    # Node Curve Circle
    curve_circle = vecteur_1.nodes.new("GeometryNodeCurvePrimitiveCircle")
    curve_circle.name = "Curve Circle"
    curve_circle.mode = 'RADIUS'
    # Resolution
    curve_circle.inputs[0].default_value = 32

    # Node Transform Geometry
    transform_geometry = vecteur_1.nodes.new("GeometryNodeTransform")
    transform_geometry.name = "Transform Geometry"
    # Mode
    transform_geometry.inputs[1].default_value = 'Components'
    # Scale
    transform_geometry.inputs[4].default_value = (1.0, 1.0, 1.0)

    # Node Vector Math
    vector_math = vecteur_1.nodes.new("ShaderNodeVectorMath")
    vector_math.name = "Vector Math"
    vector_math.operation = 'SUBTRACT'

    # Node Set Position
    set_position = vecteur_1.nodes.new("GeometryNodeSetPosition")
    set_position.name = "Set Position"
    # Selection
    set_position.inputs[1].default_value = True
    # Position
    set_position.inputs[2].default_value = (0.0, 0.0, 0.0)

    # Node Vector Math.001
    vector_math_001 = vecteur_1.nodes.new("ShaderNodeVectorMath")
    vector_math_001.name = "Vector Math.001"
    vector_math_001.operation = 'NORMALIZE'

    # Node Vector Math.002
    vector_math_002 = vecteur_1.nodes.new("ShaderNodeVectorMath")
    vector_math_002.name = "Vector Math.002"
    vector_math_002.operation = 'MULTIPLY'
    # Vector_001
    vector_math_002.inputs[1].default_value = (-1.0, -1.0, -1.0)

    # Node Vector Math.003
    vector_math_003 = vecteur_1.nodes.new("ShaderNodeVectorMath")
    vector_math_003.name = "Vector Math.003"
    vector_math_003.operation = 'SCALE'

    # Node Mesh to Points
    mesh_to_points = vecteur_1.nodes.new("GeometryNodeMeshToPoints")
    mesh_to_points.name = "Mesh to Points"
    mesh_to_points.mode = 'FACES'
    # Position
    mesh_to_points.inputs[2].default_value = (0.0, 0.0, 0.0)
    # Radius
    mesh_to_points.inputs[3].default_value = 0.05000000074505806

    # Node Realize Instances
    realize_instances = vecteur_1.nodes.new("GeometryNodeRealizeInstances")
    realize_instances.name = "Realize Instances"
    realize_instances.realize_to_point_domain = True
    # Selection
    realize_instances.inputs[1].default_value = True
    # Realize All
    realize_instances.inputs[2].default_value = True
    # Depth
    realize_instances.inputs[3].default_value = 0

    # Node Sample Index
    sample_index = vecteur_1.nodes.new("GeometryNodeSampleIndex")
    sample_index.name = "Sample Index"
    sample_index.clamp = False
    sample_index.data_type = 'FLOAT_VECTOR'
    sample_index.domain = 'POINT'
    # Index
    sample_index.inputs[2].default_value = 0

    # Node Position
    position = vecteur_1.nodes.new("GeometryNodeInputPosition")
    position.name = "Position"

    # Node Value
    value = vecteur_1.nodes.new("ShaderNodeValue")
    value.name = "Value"

    value.outputs[0].default_value = 0.30000001192092896
    # Node Math
    math = vecteur_1.nodes.new("ShaderNodeMath")
    math.name = "Math"
    math.operation = 'SUBTRACT'
    math.use_clamp = False
    # Value_001
    math.inputs[1].default_value = 0.20000000298023224

    # Node Math.001
    math_001 = vecteur_1.nodes.new("ShaderNodeMath")
    math_001.name = "Math.001"
    math_001.operation = 'SUBTRACT'
    math_001.use_clamp = False
    # Value_001
    math_001.inputs[1].default_value = 0.3199999928474426

    # Node Reroute
    reroute = vecteur_1.nodes.new("NodeReroute")
    reroute.name = "Reroute"
    reroute.socket_idname = "NodeSocketVector"
    # Node Reroute.001
    reroute_001 = vecteur_1.nodes.new("NodeReroute")
    reroute_001.name = "Reroute.001"
    reroute_001.socket_idname = "NodeSocketFloat"
    # Node Reroute.002
    reroute_002 = vecteur_1.nodes.new("NodeReroute")
    reroute_002.name = "Reroute.002"
    reroute_002.socket_idname = "NodeSocketFloat"
    # Node Reroute.003
    reroute_003 = vecteur_1.nodes.new("NodeReroute")
    reroute_003.name = "Reroute.003"
    reroute_003.socket_idname = "NodeSocketVector"
    # Node Reroute.004
    reroute_004 = vecteur_1.nodes.new("NodeReroute")
    reroute_004.name = "Reroute.004"
    reroute_004.socket_idname = "NodeSocketVector"
    # Node Reroute.005
    reroute_005 = vecteur_1.nodes.new("NodeReroute")
    reroute_005.name = "Reroute.005"
    reroute_005.socket_idname = "NodeSocketBool"
    # Node Reroute.006
    reroute_006 = vecteur_1.nodes.new("NodeReroute")
    reroute_006.name = "Reroute.006"
    reroute_006.socket_idname = "NodeSocketGeometry"
    # Node Reroute.007
    reroute_007 = vecteur_1.nodes.new("NodeReroute")
    reroute_007.name = "Reroute.007"
    reroute_007.socket_idname = "NodeSocketFloat"
    # Node Reroute.008
    reroute_008 = vecteur_1.nodes.new("NodeReroute")
    reroute_008.name = "Reroute.008"
    reroute_008.socket_idname = "NodeSocketVector"
    # Node Reroute.009
    reroute_009 = vecteur_1.nodes.new("NodeReroute")
    reroute_009.name = "Reroute.009"
    reroute_009.socket_idname = "NodeSocketVector"
    # Set locations
    vecteur_1.nodes["Group Output"].location = (1270.711669921875, 78.59925079345703)
    vecteur_1.nodes["Group Input"].location = (-1000.5017700195312, 277.2523193359375)
    vecteur_1.nodes["Curve Line"].location = (675.7116088867188, 118.09925079345703)
    vecteur_1.nodes["Cone"].location = (-393.00177001953125, -157.01817321777344)
    vecteur_1.nodes["Join Geometry"].location = (1080.711669921875, 78.59925079345703)
    vecteur_1.nodes["Align Rotation to Vector"].location = (-364.89501953125, 261.9818420410156)
    vecteur_1.nodes["Curve to Mesh"].location = (878.2116088867188, -3.4007503986358643)
    vecteur_1.nodes["Curve Circle"].location = (675.7116088867188, -443.36090087890625)
    vecteur_1.nodes["Transform Geometry"].location = (-134.28836059570312, 290.9818420410156)
    vecteur_1.nodes["Vector Math"].location = (-785.5018310546875, 90.60682678222656)
    vecteur_1.nodes["Set Position"].location = (68.21163940429688, 139.3643798828125)
    vecteur_1.nodes["Vector Math.001"].location = (-595.5017700195312, 13.981825828552246)
    vecteur_1.nodes["Vector Math.002"].location = (-134.28836059570312, 13.981825828552246)
    vecteur_1.nodes["Vector Math.003"].location = (-364.89501953125, 13.981825828552246)
    vecteur_1.nodes["Mesh to Points"].location = (283.2116394042969, 66.89669036865234)
    vecteur_1.nodes["Realize Instances"].location = (878.2116088867188, 547.7446899414062)
    vecteur_1.nodes["Sample Index"].location = (473.2116394042969, 18.139131546020508)
    vecteur_1.nodes["Position"].location = (283.2116394042969, -149.48587036132812)
    vecteur_1.nodes["Value"].location = (-785.5018310546875, -499.3608703613281)
    vecteur_1.nodes["Math"].location = (-595.5017700195312, -381.57098388671875)
    vecteur_1.nodes["Math.001"].location = (473.2116394042969, -443.36090087890625)
    vecteur_1.nodes["Reroute"].location = (-595.5017700195312, 132.49693298339844)
    vecteur_1.nodes["Reroute.001"].location = (-595.5017700195312, -579.5709838867188)
    vecteur_1.nodes["Reroute.002"].location = (-455.5017395019531, -579.5709838867188)
    vecteur_1.nodes["Reroute.003"].location = (-785.5018310546875, 319.9818420410156)
    vecteur_1.nodes["Reroute.004"].location = (-196.78836059570312, 319.9818420410156)
    vecteur_1.nodes["Reroute.005"].location = (208.21163940429688, -236.50306701660156)
    vecteur_1.nodes["Reroute.006"].location = (283.2116394042969, 514.13916015625)
    vecteur_1.nodes["Reroute.007"].location = (423.2116394042969, -579.5709838867188)
    vecteur_1.nodes["Reroute.008"].location = (-785.5018310546875, 377.9818420410156)
    vecteur_1.nodes["Reroute.009"].location = (613.2116088867188, 377.9818420410156)

    # Set dimensions
    vecteur_1.nodes["Group Output"].width  = 140.0
    vecteur_1.nodes["Group Output"].height = 100.0

    vecteur_1.nodes["Group Input"].width  = 140.0
    vecteur_1.nodes["Group Input"].height = 100.0

    vecteur_1.nodes["Curve Line"].width  = 140.0
    vecteur_1.nodes["Curve Line"].height = 100.0

    vecteur_1.nodes["Cone"].width  = 196.21337890625
    vecteur_1.nodes["Cone"].height = 100.0

    vecteur_1.nodes["Join Geometry"].width  = 140.0
    vecteur_1.nodes["Join Geometry"].height = 100.0

    vecteur_1.nodes["Align Rotation to Vector"].width  = 140.0
    vecteur_1.nodes["Align Rotation to Vector"].height = 100.0

    vecteur_1.nodes["Curve to Mesh"].width  = 140.0
    vecteur_1.nodes["Curve to Mesh"].height = 100.0

    vecteur_1.nodes["Curve Circle"].width  = 140.0
    vecteur_1.nodes["Curve Circle"].height = 100.0

    vecteur_1.nodes["Transform Geometry"].width  = 140.0
    vecteur_1.nodes["Transform Geometry"].height = 100.0

    vecteur_1.nodes["Vector Math"].width  = 140.0
    vecteur_1.nodes["Vector Math"].height = 100.0

    vecteur_1.nodes["Set Position"].width  = 140.0
    vecteur_1.nodes["Set Position"].height = 100.0

    vecteur_1.nodes["Vector Math.001"].width  = 140.0
    vecteur_1.nodes["Vector Math.001"].height = 100.0

    vecteur_1.nodes["Vector Math.002"].width  = 140.0
    vecteur_1.nodes["Vector Math.002"].height = 100.0

    vecteur_1.nodes["Vector Math.003"].width  = 140.0
    vecteur_1.nodes["Vector Math.003"].height = 100.0

    vecteur_1.nodes["Mesh to Points"].width  = 140.0
    vecteur_1.nodes["Mesh to Points"].height = 100.0

    vecteur_1.nodes["Realize Instances"].width  = 140.0
    vecteur_1.nodes["Realize Instances"].height = 100.0

    vecteur_1.nodes["Sample Index"].width  = 140.0
    vecteur_1.nodes["Sample Index"].height = 100.0

    vecteur_1.nodes["Position"].width  = 140.0
    vecteur_1.nodes["Position"].height = 100.0

    vecteur_1.nodes["Value"].width  = 140.0
    vecteur_1.nodes["Value"].height = 100.0

    vecteur_1.nodes["Math"].width  = 140.0
    vecteur_1.nodes["Math"].height = 100.0

    vecteur_1.nodes["Math.001"].width  = 140.0
    vecteur_1.nodes["Math.001"].height = 100.0

    vecteur_1.nodes["Reroute"].width  = 140.0
    vecteur_1.nodes["Reroute"].height = 100.0

    vecteur_1.nodes["Reroute.001"].width  = 140.0
    vecteur_1.nodes["Reroute.001"].height = 100.0

    vecteur_1.nodes["Reroute.002"].width  = 140.0
    vecteur_1.nodes["Reroute.002"].height = 100.0

    vecteur_1.nodes["Reroute.003"].width  = 140.0
    vecteur_1.nodes["Reroute.003"].height = 100.0

    vecteur_1.nodes["Reroute.004"].width  = 140.0
    vecteur_1.nodes["Reroute.004"].height = 100.0

    vecteur_1.nodes["Reroute.005"].width  = 140.0
    vecteur_1.nodes["Reroute.005"].height = 100.0

    vecteur_1.nodes["Reroute.006"].width  = 140.0
    vecteur_1.nodes["Reroute.006"].height = 100.0

    vecteur_1.nodes["Reroute.007"].width  = 140.0
    vecteur_1.nodes["Reroute.007"].height = 100.0

    vecteur_1.nodes["Reroute.008"].width  = 140.0
    vecteur_1.nodes["Reroute.008"].height = 100.0

    vecteur_1.nodes["Reroute.009"].width  = 140.0
    vecteur_1.nodes["Reroute.009"].height = 100.0


    # Initialize vecteur_1 links

    # align_rotation_to_vector.Rotation -> transform_geometry.Rotation
    vecteur_1.links.new(
        vecteur_1.nodes["Align Rotation to Vector"].outputs[0],
        vecteur_1.nodes["Transform Geometry"].inputs[3]
    )
    # math.Value -> cone.Radius Bottom
    vecteur_1.links.new(
        vecteur_1.nodes["Math"].outputs[0],
        vecteur_1.nodes["Cone"].inputs[4]
    )
    # curve_line.Curve -> curve_to_mesh.Curve
    vecteur_1.links.new(
        vecteur_1.nodes["Curve Line"].outputs[0],
        vecteur_1.nodes["Curve to Mesh"].inputs[0]
    )
    # vector_math.Vector -> vector_math_001.Vector
    vecteur_1.links.new(
        vecteur_1.nodes["Vector Math"].outputs[0],
        vecteur_1.nodes["Vector Math.001"].inputs[0]
    )
    # vector_math_003.Vector -> vector_math_002.Vector
    vecteur_1.links.new(
        vecteur_1.nodes["Vector Math.003"].outputs[0],
        vecteur_1.nodes["Vector Math.002"].inputs[0]
    )
    # vector_math_002.Vector -> set_position.Offset
    vecteur_1.links.new(
        vecteur_1.nodes["Vector Math.002"].outputs[0],
        vecteur_1.nodes["Set Position"].inputs[3]
    )
    # math_001.Value -> curve_circle.Radius
    vecteur_1.links.new(
        vecteur_1.nodes["Math.001"].outputs[0],
        vecteur_1.nodes["Curve Circle"].inputs[4]
    )
    # curve_to_mesh.Mesh -> join_geometry.Geometry
    vecteur_1.links.new(
        vecteur_1.nodes["Curve to Mesh"].outputs[0],
        vecteur_1.nodes["Join Geometry"].inputs[0]
    )
    # set_position.Geometry -> mesh_to_points.Mesh
    vecteur_1.links.new(
        vecteur_1.nodes["Set Position"].outputs[0],
        vecteur_1.nodes["Mesh to Points"].inputs[0]
    )
    # mesh_to_points.Points -> sample_index.Geometry
    vecteur_1.links.new(
        vecteur_1.nodes["Mesh to Points"].outputs[0],
        vecteur_1.nodes["Sample Index"].inputs[0]
    )
    # vector_math_001.Vector -> vector_math_003.Vector
    vecteur_1.links.new(
        vecteur_1.nodes["Vector Math.001"].outputs[0],
        vecteur_1.nodes["Vector Math.003"].inputs[0]
    )
    # position.Position -> sample_index.Value
    vecteur_1.links.new(
        vecteur_1.nodes["Position"].outputs[0],
        vecteur_1.nodes["Sample Index"].inputs[1]
    )
    # sample_index.Value -> curve_line.End
    vecteur_1.links.new(
        vecteur_1.nodes["Sample Index"].outputs[0],
        vecteur_1.nodes["Curve Line"].inputs[1]
    )
    # transform_geometry.Geometry -> set_position.Geometry
    vecteur_1.links.new(
        vecteur_1.nodes["Transform Geometry"].outputs[0],
        vecteur_1.nodes["Set Position"].inputs[0]
    )
    # value.Value -> math.Value
    vecteur_1.links.new(
        vecteur_1.nodes["Value"].outputs[0],
        vecteur_1.nodes["Math"].inputs[0]
    )
    # curve_circle.Curve -> curve_to_mesh.Profile Curve
    vecteur_1.links.new(
        vecteur_1.nodes["Curve Circle"].outputs[0],
        vecteur_1.nodes["Curve to Mesh"].inputs[1]
    )
    # cone.Mesh -> transform_geometry.Geometry
    vecteur_1.links.new(
        vecteur_1.nodes["Cone"].outputs[0],
        vecteur_1.nodes["Transform Geometry"].inputs[0]
    )
    # group_input.ext -> vector_math.Vector
    vecteur_1.links.new(
        vecteur_1.nodes["Group Input"].outputs[1],
        vecteur_1.nodes["Vector Math"].inputs[0]
    )
    # group_input.orig -> vector_math.Vector
    vecteur_1.links.new(
        vecteur_1.nodes["Group Input"].outputs[0],
        vecteur_1.nodes["Vector Math"].inputs[1]
    )
    # join_geometry.Geometry -> group_output.Geometry
    vecteur_1.links.new(
        vecteur_1.nodes["Join Geometry"].outputs[0],
        vecteur_1.nodes["Group Output"].inputs[0]
    )
    # group_input.orig -> reroute_008.Input
    vecteur_1.links.new(
        vecteur_1.nodes["Group Input"].outputs[0],
        vecteur_1.nodes["Reroute.008"].inputs[0]
    )
    # group_input.ext -> reroute_003.Input
    vecteur_1.links.new(
        vecteur_1.nodes["Group Input"].outputs[1],
        vecteur_1.nodes["Reroute.003"].inputs[0]
    )
    # cone.Bottom -> reroute_005.Input
    vecteur_1.links.new(
        vecteur_1.nodes["Cone"].outputs[2],
        vecteur_1.nodes["Reroute.005"].inputs[0]
    )
    # vector_math.Vector -> reroute.Input
    vecteur_1.links.new(
        vecteur_1.nodes["Vector Math"].outputs[0],
        vecteur_1.nodes["Reroute"].inputs[0]
    )
    # set_position.Geometry -> reroute_006.Input
    vecteur_1.links.new(
        vecteur_1.nodes["Set Position"].outputs[0],
        vecteur_1.nodes["Reroute.006"].inputs[0]
    )
    # value.Value -> reroute_001.Input
    vecteur_1.links.new(
        vecteur_1.nodes["Value"].outputs[0],
        vecteur_1.nodes["Reroute.001"].inputs[0]
    )
    # reroute_001.Output -> reroute_002.Input
    vecteur_1.links.new(
        vecteur_1.nodes["Reroute.001"].outputs[0],
        vecteur_1.nodes["Reroute.002"].inputs[0]
    )
    # reroute_008.Output -> reroute_009.Input
    vecteur_1.links.new(
        vecteur_1.nodes["Reroute.008"].outputs[0],
        vecteur_1.nodes["Reroute.009"].inputs[0]
    )
    # reroute_003.Output -> reroute_004.Input
    vecteur_1.links.new(
        vecteur_1.nodes["Reroute.003"].outputs[0],
        vecteur_1.nodes["Reroute.004"].inputs[0]
    )
    # reroute.Output -> align_rotation_to_vector.Vector
    vecteur_1.links.new(
        vecteur_1.nodes["Reroute"].outputs[0],
        vecteur_1.nodes["Align Rotation to Vector"].inputs[2]
    )
    # reroute_006.Output -> realize_instances.Geometry
    vecteur_1.links.new(
        vecteur_1.nodes["Reroute.006"].outputs[0],
        vecteur_1.nodes["Realize Instances"].inputs[0]
    )
    # reroute_002.Output -> cone.Depth
    vecteur_1.links.new(
        vecteur_1.nodes["Reroute.002"].outputs[0],
        vecteur_1.nodes["Cone"].inputs[5]
    )
    # reroute_002.Output -> vector_math_003.Scale
    vecteur_1.links.new(
        vecteur_1.nodes["Reroute.002"].outputs[0],
        vecteur_1.nodes["Vector Math.003"].inputs[3]
    )
    # reroute_002.Output -> reroute_007.Input
    vecteur_1.links.new(
        vecteur_1.nodes["Reroute.002"].outputs[0],
        vecteur_1.nodes["Reroute.007"].inputs[0]
    )
    # reroute_004.Output -> transform_geometry.Translation
    vecteur_1.links.new(
        vecteur_1.nodes["Reroute.004"].outputs[0],
        vecteur_1.nodes["Transform Geometry"].inputs[2]
    )
    # reroute_005.Output -> mesh_to_points.Selection
    vecteur_1.links.new(
        vecteur_1.nodes["Reroute.005"].outputs[0],
        vecteur_1.nodes["Mesh to Points"].inputs[1]
    )
    # reroute_007.Output -> math_001.Value
    vecteur_1.links.new(
        vecteur_1.nodes["Reroute.007"].outputs[0],
        vecteur_1.nodes["Math.001"].inputs[0]
    )
    # reroute_009.Output -> curve_line.Start
    vecteur_1.links.new(
        vecteur_1.nodes["Reroute.009"].outputs[0],
        vecteur_1.nodes["Curve Line"].inputs[0]
    )
    # realize_instances.Geometry -> join_geometry.Geometry
    vecteur_1.links.new(
        vecteur_1.nodes["Realize Instances"].outputs[0],
        vecteur_1.nodes["Join Geometry"].inputs[0]
    )

    return vecteur_1
