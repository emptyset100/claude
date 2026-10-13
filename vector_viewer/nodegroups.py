"""Construction des quatre node groups (Position, Vitesse, Accélération,
wrapper « Geometry Nodes ») via l'API ``bpy.data.node_groups``.

Code généré à l'origine par l'export NodeToPython, légèrement nettoyé :
les deux Transform Geometry du wrapper (translations fixes) ont été
supprimés car les drivers placent désormais les flèches directement
au point M(t).

Le wrapper expose en outre trois booléens (Afficher position / vitesse /
accélération) câblés sur des nodes Switch, qui permettent d'afficher ou
de masquer chaque flèche depuis le panneau Modifier de l'objet hôte.
"""

import bpy
import typing

# Noms des sockets booléens d'affichage exposés par le wrapper.
# Centralisés ici pour rester cohérents si on veut les piloter depuis
# d'autres modules (operators, ui, …).
SHOW_POSITION_SOCKET     = "Afficher position"
SHOW_VITESSE_SOCKET      = "Afficher vitesse"
SHOW_ACCELERATION_SOCKET = "Afficher accélération"

# Noms canoniques des sub-groups (préfixés ``VV_`` pour éviter toute
# collision avec d'autres node groups d'autres extensions ou des
# node groups que l'utilisateur aurait créés).
SUBGROUP_POSITION_NAME     = "VV_Position"
SUBGROUP_VITESSE_NAME      = "VV_Vitesse"
SUBGROUP_ACCELERATION_NAME = "VV_Acceleration"

# Version du schéma des sub-groups. Quand on modifie la structure
# interne (sockets, nodes), on incrémente : ``_ensure_subgroups`` détecte
# alors que les sub-groups stockés sont obsolètes et les recrée.
SUBGROUP_SCHEMA_VERSION = 2

# Trajectoire OM (= chemin parcouru par M, échantillonné au build sur
# [t_start, t_start+T]). Rendue via une chaîne Object Info → Curve to
# Mesh → Set Material → Switch, en miroir du système Composition.
SHOW_TRAJECTORY_SOCKET   = "Afficher trajectoire OM"
TRAJ_RADIUS_SOCKET       = "Rayon de la trajectoire"

# Trièdre du repère R (base orthonormée de référence) ancré à l'origine.
# Trois flèches statiques (longueur fixée au build, pas de driver). Un
# seul toggle pour les trois axes — pédagogiquement le repère R s'affiche
# ou se masque en bloc.
SHOW_FRAME_SOCKET        = "Afficher repère R"
AXIS_LENGTH_DEFAULT      = 1.0

# Échelles des flèches v et a, exposées comme sockets Float pour pouvoir
# les modifier en LIVE (sans rebuild). Les drivers Python lisent ces
# valeurs via une variable de driver pointant sur le socket — voir
# ``drivers.attach_socket_drivers``.
SCALE_V_SOCKET           = "Échelle v"
SCALE_A_SOCKET           = "Échelle a"

def position_1_node_group(node_tree_names: dict[typing.Callable, str]):
    """Initialize Position node group"""
    position_1 = bpy.data.node_groups.new(type='GeometryNodeTree', name=SUBGROUP_POSITION_NAME)
    position_1["vv_subgroup_version"] = SUBGROUP_SCHEMA_VERSION

    position_1.color_tag = 'NONE'
    position_1.description = ""
    position_1.default_group_node_width = 140
    position_1.show_modifier_manage_panel = True

    # position_1 interface

    # Socket Geometry
    geometry_socket = position_1.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'
    geometry_socket.default_input = 'VALUE'
    geometry_socket.structure_type = 'AUTO'

    # Socket orig
    orig_socket = position_1.interface.new_socket(name="orig", in_out='INPUT', socket_type='NodeSocketVector')
    orig_socket.default_value = (0.0, 0.0, 0.0)
    orig_socket.min_value = -10000.0
    orig_socket.max_value = 10000.0
    orig_socket.subtype = 'NONE'
    orig_socket.attribute_domain = 'POINT'
    orig_socket.default_input = 'VALUE'
    orig_socket.structure_type = 'AUTO'

    # Socket ext
    ext_socket = position_1.interface.new_socket(name="ext", in_out='INPUT', socket_type='NodeSocketVector')
    ext_socket.default_value = (0.0, 0.0, 0.0)
    ext_socket.min_value = -10000.0
    ext_socket.max_value = 10000.0
    ext_socket.subtype = 'NONE'
    ext_socket.attribute_domain = 'POINT'
    ext_socket.default_input = 'VALUE'
    ext_socket.structure_type = 'AUTO'

    # Initialize position_1 nodes

    # Node Group Output
    group_output = position_1.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    # Node Group Input
    group_input = position_1.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"

    # Node Curve Line
    curve_line = position_1.nodes.new("GeometryNodeCurvePrimitiveLine")
    curve_line.name = "Curve Line"
    curve_line.mode = 'POINTS'

    # Node Cone
    cone = position_1.nodes.new("GeometryNodeMeshCone")
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
    join_geometry = position_1.nodes.new("GeometryNodeJoinGeometry")
    join_geometry.name = "Join Geometry"

    # Node Align Rotation to Vector
    align_rotation_to_vector = position_1.nodes.new("FunctionNodeAlignRotationToVector")
    align_rotation_to_vector.name = "Align Rotation to Vector"
    align_rotation_to_vector.axis = 'Z'
    align_rotation_to_vector.pivot_axis = 'AUTO'
    # Rotation
    align_rotation_to_vector.inputs[0].default_value = (0.0, 0.0, 0.0)
    # Factor
    align_rotation_to_vector.inputs[1].default_value = 1.0

    # Node Curve to Mesh
    curve_to_mesh = position_1.nodes.new("GeometryNodeCurveToMesh")
    curve_to_mesh.name = "Curve to Mesh"
    # Scale
    curve_to_mesh.inputs[2].default_value = 1.0
    # Fill Caps
    curve_to_mesh.inputs[3].default_value = True

    # Node Curve Circle
    curve_circle = position_1.nodes.new("GeometryNodeCurvePrimitiveCircle")
    curve_circle.name = "Curve Circle"
    curve_circle.mode = 'RADIUS'
    # Resolution
    curve_circle.inputs[0].default_value = 32

    # Node Transform Geometry
    transform_geometry = position_1.nodes.new("GeometryNodeTransform")
    transform_geometry.name = "Transform Geometry"
    # Mode
    transform_geometry.inputs[1].default_value = 'Components'
    # Scale
    transform_geometry.inputs[4].default_value = (1.0, 1.0, 1.0)

    # Node Vector Math
    vector_math = position_1.nodes.new("ShaderNodeVectorMath")
    vector_math.name = "Vector Math"
    vector_math.operation = 'SUBTRACT'

    # Node Set Position
    set_position = position_1.nodes.new("GeometryNodeSetPosition")
    set_position.name = "Set Position"
    # Selection
    set_position.inputs[1].default_value = True
    # Position
    set_position.inputs[2].default_value = (0.0, 0.0, 0.0)

    # Node Vector Math.001
    vector_math_001 = position_1.nodes.new("ShaderNodeVectorMath")
    vector_math_001.name = "Vector Math.001"
    vector_math_001.operation = 'NORMALIZE'

    # Node Vector Math.002
    vector_math_002 = position_1.nodes.new("ShaderNodeVectorMath")
    vector_math_002.name = "Vector Math.002"
    vector_math_002.operation = 'MULTIPLY'
    # Vector_001
    vector_math_002.inputs[1].default_value = (-1.0, -1.0, -1.0)

    # Node Vector Math.003
    vector_math_003 = position_1.nodes.new("ShaderNodeVectorMath")
    vector_math_003.name = "Vector Math.003"
    vector_math_003.operation = 'SCALE'

    # Node Mesh to Points
    mesh_to_points = position_1.nodes.new("GeometryNodeMeshToPoints")
    mesh_to_points.name = "Mesh to Points"
    mesh_to_points.mode = 'FACES'
    # Position
    mesh_to_points.inputs[2].default_value = (0.0, 0.0, 0.0)
    # Radius
    mesh_to_points.inputs[3].default_value = 0.05000000074505806

    # Node Realize Instances
    realize_instances = position_1.nodes.new("GeometryNodeRealizeInstances")
    realize_instances.name = "Realize Instances"
    realize_instances.realize_to_point_domain = True
    # Selection
    realize_instances.inputs[1].default_value = True
    # Realize All
    realize_instances.inputs[2].default_value = True
    # Depth
    realize_instances.inputs[3].default_value = 0

    # Node Sample Index
    sample_index = position_1.nodes.new("GeometryNodeSampleIndex")
    sample_index.name = "Sample Index"
    sample_index.clamp = False
    sample_index.data_type = 'FLOAT_VECTOR'
    sample_index.domain = 'POINT'
    # Index
    sample_index.inputs[2].default_value = 0

    # Node Position
    position_2 = position_1.nodes.new("GeometryNodeInputPosition")
    position_2.name = "Position"

    # Node Value
    value = position_1.nodes.new("ShaderNodeValue")
    value.name = "Value"

    value.outputs[0].default_value = 0.30000001192092896
    # Node Math
    math = position_1.nodes.new("ShaderNodeMath")
    math.name = "Math"
    math.operation = 'SUBTRACT'
    math.use_clamp = False
    # Value_001
    math.inputs[1].default_value = 0.20000000298023224

    # Node Math.001
    math_001 = position_1.nodes.new("ShaderNodeMath")
    math_001.name = "Math.001"
    math_001.operation = 'SUBTRACT'
    math_001.use_clamp = False
    # Value_001
    math_001.inputs[1].default_value = 0.3199999928474426

    # Node Set Shade Smooth
    set_shade_smooth = position_1.nodes.new("GeometryNodeSetShadeSmooth")
    set_shade_smooth.name = "Set Shade Smooth"
    set_shade_smooth.domain = 'FACE'
    # Selection
    set_shade_smooth.inputs[1].default_value = True
    # Shade Smooth
    set_shade_smooth.inputs[2].default_value = True

    # Node Reroute
    reroute = position_1.nodes.new("NodeReroute")
    reroute.name = "Reroute"
    reroute.socket_idname = "NodeSocketVector"
    # Node Reroute.001
    reroute_001 = position_1.nodes.new("NodeReroute")
    reroute_001.name = "Reroute.001"
    reroute_001.socket_idname = "NodeSocketFloat"
    # Node Reroute.002
    reroute_002 = position_1.nodes.new("NodeReroute")
    reroute_002.name = "Reroute.002"
    reroute_002.socket_idname = "NodeSocketFloat"
    # Node Reroute.003
    reroute_003 = position_1.nodes.new("NodeReroute")
    reroute_003.name = "Reroute.003"
    reroute_003.socket_idname = "NodeSocketVector"
    # Node Reroute.004
    reroute_004 = position_1.nodes.new("NodeReroute")
    reroute_004.name = "Reroute.004"
    reroute_004.socket_idname = "NodeSocketVector"
    # Node Reroute.005
    reroute_005 = position_1.nodes.new("NodeReroute")
    reroute_005.name = "Reroute.005"
    reroute_005.socket_idname = "NodeSocketBool"
    # Node Reroute.006
    reroute_006 = position_1.nodes.new("NodeReroute")
    reroute_006.name = "Reroute.006"
    reroute_006.socket_idname = "NodeSocketBool"
    # Node Reroute.007
    reroute_007 = position_1.nodes.new("NodeReroute")
    reroute_007.name = "Reroute.007"
    reroute_007.socket_idname = "NodeSocketGeometry"
    # Node Reroute.008
    reroute_008 = position_1.nodes.new("NodeReroute")
    reroute_008.name = "Reroute.008"
    reroute_008.socket_idname = "NodeSocketVector"
    # Node Reroute.009
    reroute_009 = position_1.nodes.new("NodeReroute")
    reroute_009.name = "Reroute.009"
    reroute_009.socket_idname = "NodeSocketVector"
    # Set locations
    position_1.nodes["Group Output"].location = (1457.876953125, 60.35575485229492)
    position_1.nodes["Group Input"].location = (-1326.938232421875, 255.12811279296875)
    position_1.nodes["Curve Line"].location = (672.876953125, 73.52409362792969)
    position_1.nodes["Cone"].location = (-433.33642578125, 16.64124298095703)
    position_1.nodes["Join Geometry"].location = (1077.876953125, 34.02409744262695)
    position_1.nodes["Align Rotation to Vector"].location = (-405.229736328125, 314.89276123046875)
    position_1.nodes["Curve to Mesh"].location = (875.376953125, -47.97590255737305)
    position_1.nodes["Curve Circle"].location = (672.876953125, -548.6061401367188)
    position_1.nodes["Transform Geometry"].location = (-149.623046875, 343.89276123046875)
    position_1.nodes["Vector Math"].location = (-863.33642578125, 49.710208892822266)
    position_1.nodes["Set Position"].location = (52.876953125, 190.8927459716797)
    position_1.nodes["Vector Math.001"].location = (-635.83642578125, -406.9115905761719)
    position_1.nodes["Vector Math.002"].location = (-149.623046875, -10.37497615814209)
    position_1.nodes["Vector Math.003"].location = (-405.229736328125, -406.9115905761719)
    position_1.nodes["Mesh to Points"].location = (267.876953125, 126.64057922363281)
    position_1.nodes["Realize Instances"].location = (875.376953125, 601.1000366210938)
    position_1.nodes["Sample Index"].location = (470.376953125, -26.622249603271484)
    position_1.nodes["Position"].location = (267.876953125, -194.62713623046875)
    position_1.nodes["Value"].location = (-863.33642578125, -345.5478210449219)
    position_1.nodes["Math"].location = (-635.83642578125, -208.91159057617188)
    position_1.nodes["Math.001"].location = (470.376953125, -548.6061401367188)
    position_1.nodes["Set Shade Smooth"].location = (1267.876953125, 60.35575485229492)
    position_1.nodes["Reroute"].location = (-635.83642578125, 185.9512176513672)
    position_1.nodes["Reroute.001"].location = (-635.83642578125, -657.191162109375)
    position_1.nodes["Reroute.002"].location = (-495.83642578125, -657.191162109375)
    position_1.nodes["Reroute.003"].location = (-863.33642578125, 372.89276123046875)
    position_1.nodes["Reroute.004"].location = (-237.123046875, 372.89276123046875)
    position_1.nodes["Reroute.005"].location = (-149.623046875, -245.37496948242188)
    position_1.nodes["Reroute.006"].location = (192.876953125, -245.37496948242188)
    position_1.nodes["Reroute.007"].location = (267.876953125, 566.9782104492188)
    position_1.nodes["Reroute.008"].location = (-863.33642578125, 430.89276123046875)
    position_1.nodes["Reroute.009"].location = (610.376953125, 430.89276123046875)

    # Set dimensions
    position_1.nodes["Group Output"].width  = 140.0
    position_1.nodes["Group Output"].height = 100.0

    position_1.nodes["Group Input"].width  = 140.0
    position_1.nodes["Group Input"].height = 100.0

    position_1.nodes["Curve Line"].width  = 140.0
    position_1.nodes["Curve Line"].height = 100.0

    position_1.nodes["Cone"].width  = 196.21337890625
    position_1.nodes["Cone"].height = 100.0

    position_1.nodes["Join Geometry"].width  = 140.0
    position_1.nodes["Join Geometry"].height = 100.0

    position_1.nodes["Align Rotation to Vector"].width  = 140.0
    position_1.nodes["Align Rotation to Vector"].height = 100.0

    position_1.nodes["Curve to Mesh"].width  = 140.0
    position_1.nodes["Curve to Mesh"].height = 100.0

    position_1.nodes["Curve Circle"].width  = 140.0
    position_1.nodes["Curve Circle"].height = 100.0

    position_1.nodes["Transform Geometry"].width  = 140.0
    position_1.nodes["Transform Geometry"].height = 100.0

    position_1.nodes["Vector Math"].width  = 140.0
    position_1.nodes["Vector Math"].height = 100.0

    position_1.nodes["Set Position"].width  = 140.0
    position_1.nodes["Set Position"].height = 100.0

    position_1.nodes["Vector Math.001"].width  = 140.0
    position_1.nodes["Vector Math.001"].height = 100.0

    position_1.nodes["Vector Math.002"].width  = 140.0
    position_1.nodes["Vector Math.002"].height = 100.0

    position_1.nodes["Vector Math.003"].width  = 140.0
    position_1.nodes["Vector Math.003"].height = 100.0

    position_1.nodes["Mesh to Points"].width  = 140.0
    position_1.nodes["Mesh to Points"].height = 100.0

    position_1.nodes["Realize Instances"].width  = 140.0
    position_1.nodes["Realize Instances"].height = 100.0

    position_1.nodes["Sample Index"].width  = 140.0
    position_1.nodes["Sample Index"].height = 100.0

    position_1.nodes["Position"].width  = 140.0
    position_1.nodes["Position"].height = 100.0

    position_1.nodes["Value"].width  = 140.0
    position_1.nodes["Value"].height = 100.0

    position_1.nodes["Math"].width  = 140.0
    position_1.nodes["Math"].height = 100.0

    position_1.nodes["Math.001"].width  = 140.0
    position_1.nodes["Math.001"].height = 100.0

    position_1.nodes["Set Shade Smooth"].width  = 140.0
    position_1.nodes["Set Shade Smooth"].height = 100.0

    position_1.nodes["Reroute"].width  = 10.0
    position_1.nodes["Reroute"].height = 100.0

    position_1.nodes["Reroute.001"].width  = 10.0
    position_1.nodes["Reroute.001"].height = 100.0

    position_1.nodes["Reroute.002"].width  = 10.0
    position_1.nodes["Reroute.002"].height = 100.0

    position_1.nodes["Reroute.003"].width  = 10.0
    position_1.nodes["Reroute.003"].height = 100.0

    position_1.nodes["Reroute.004"].width  = 10.0
    position_1.nodes["Reroute.004"].height = 100.0

    position_1.nodes["Reroute.005"].width  = 10.0
    position_1.nodes["Reroute.005"].height = 100.0

    position_1.nodes["Reroute.006"].width  = 10.0
    position_1.nodes["Reroute.006"].height = 100.0

    position_1.nodes["Reroute.007"].width  = 10.0
    position_1.nodes["Reroute.007"].height = 100.0

    position_1.nodes["Reroute.008"].width  = 10.0
    position_1.nodes["Reroute.008"].height = 100.0

    position_1.nodes["Reroute.009"].width  = 10.0
    position_1.nodes["Reroute.009"].height = 100.0


    # Initialize position_1 links

    # align_rotation_to_vector.Rotation -> transform_geometry.Rotation
    position_1.links.new(
        position_1.nodes["Align Rotation to Vector"].outputs[0],
        position_1.nodes["Transform Geometry"].inputs[3]
    )
    # math.Value -> cone.Radius Bottom
    position_1.links.new(
        position_1.nodes["Math"].outputs[0],
        position_1.nodes["Cone"].inputs[4]
    )
    # curve_line.Curve -> curve_to_mesh.Curve
    position_1.links.new(
        position_1.nodes["Curve Line"].outputs[0],
        position_1.nodes["Curve to Mesh"].inputs[0]
    )
    # vector_math.Vector -> vector_math_001.Vector
    position_1.links.new(
        position_1.nodes["Vector Math"].outputs[0],
        position_1.nodes["Vector Math.001"].inputs[0]
    )
    # vector_math_003.Vector -> vector_math_002.Vector
    position_1.links.new(
        position_1.nodes["Vector Math.003"].outputs[0],
        position_1.nodes["Vector Math.002"].inputs[0]
    )
    # vector_math_002.Vector -> set_position.Offset
    position_1.links.new(
        position_1.nodes["Vector Math.002"].outputs[0],
        position_1.nodes["Set Position"].inputs[3]
    )
    # math_001.Value -> curve_circle.Radius
    position_1.links.new(
        position_1.nodes["Math.001"].outputs[0],
        position_1.nodes["Curve Circle"].inputs[4]
    )
    # curve_to_mesh.Mesh -> join_geometry.Geometry
    position_1.links.new(
        position_1.nodes["Curve to Mesh"].outputs[0],
        position_1.nodes["Join Geometry"].inputs[0]
    )
    # set_position.Geometry -> mesh_to_points.Mesh
    position_1.links.new(
        position_1.nodes["Set Position"].outputs[0],
        position_1.nodes["Mesh to Points"].inputs[0]
    )
    # mesh_to_points.Points -> sample_index.Geometry
    position_1.links.new(
        position_1.nodes["Mesh to Points"].outputs[0],
        position_1.nodes["Sample Index"].inputs[0]
    )
    # vector_math_001.Vector -> vector_math_003.Vector
    position_1.links.new(
        position_1.nodes["Vector Math.001"].outputs[0],
        position_1.nodes["Vector Math.003"].inputs[0]
    )
    # position_2.Position -> sample_index.Value
    position_1.links.new(
        position_1.nodes["Position"].outputs[0],
        position_1.nodes["Sample Index"].inputs[1]
    )
    # sample_index.Value -> curve_line.End
    position_1.links.new(
        position_1.nodes["Sample Index"].outputs[0],
        position_1.nodes["Curve Line"].inputs[1]
    )
    # transform_geometry.Geometry -> set_position.Geometry
    position_1.links.new(
        position_1.nodes["Transform Geometry"].outputs[0],
        position_1.nodes["Set Position"].inputs[0]
    )
    # value.Value -> math.Value
    position_1.links.new(
        position_1.nodes["Value"].outputs[0],
        position_1.nodes["Math"].inputs[0]
    )
    # curve_circle.Curve -> curve_to_mesh.Profile Curve
    position_1.links.new(
        position_1.nodes["Curve Circle"].outputs[0],
        position_1.nodes["Curve to Mesh"].inputs[1]
    )
    # cone.Mesh -> transform_geometry.Geometry
    position_1.links.new(
        position_1.nodes["Cone"].outputs[0],
        position_1.nodes["Transform Geometry"].inputs[0]
    )
    # group_input.ext -> vector_math.Vector
    position_1.links.new(
        position_1.nodes["Group Input"].outputs[1],
        position_1.nodes["Vector Math"].inputs[0]
    )
    # group_input.orig -> vector_math.Vector
    position_1.links.new(
        position_1.nodes["Group Input"].outputs[0],
        position_1.nodes["Vector Math"].inputs[1]
    )
    # set_shade_smooth.Mesh -> group_output.Geometry
    position_1.links.new(
        position_1.nodes["Set Shade Smooth"].outputs[0],
        position_1.nodes["Group Output"].inputs[0]
    )
    # join_geometry.Geometry -> set_shade_smooth.Mesh
    position_1.links.new(
        position_1.nodes["Join Geometry"].outputs[0],
        position_1.nodes["Set Shade Smooth"].inputs[0]
    )
    # group_input.orig -> reroute_008.Input
    position_1.links.new(
        position_1.nodes["Group Input"].outputs[0],
        position_1.nodes["Reroute.008"].inputs[0]
    )
    # group_input.ext -> reroute_003.Input
    position_1.links.new(
        position_1.nodes["Group Input"].outputs[1],
        position_1.nodes["Reroute.003"].inputs[0]
    )
    # cone.Bottom -> reroute_005.Input
    position_1.links.new(
        position_1.nodes["Cone"].outputs[2],
        position_1.nodes["Reroute.005"].inputs[0]
    )
    # vector_math.Vector -> reroute.Input
    position_1.links.new(
        position_1.nodes["Vector Math"].outputs[0],
        position_1.nodes["Reroute"].inputs[0]
    )
    # set_position.Geometry -> reroute_007.Input
    position_1.links.new(
        position_1.nodes["Set Position"].outputs[0],
        position_1.nodes["Reroute.007"].inputs[0]
    )
    # value.Value -> reroute_001.Input
    position_1.links.new(
        position_1.nodes["Value"].outputs[0],
        position_1.nodes["Reroute.001"].inputs[0]
    )
    # reroute_001.Output -> reroute_002.Input
    position_1.links.new(
        position_1.nodes["Reroute.001"].outputs[0],
        position_1.nodes["Reroute.002"].inputs[0]
    )
    # reroute_008.Output -> reroute_009.Input
    position_1.links.new(
        position_1.nodes["Reroute.008"].outputs[0],
        position_1.nodes["Reroute.009"].inputs[0]
    )
    # reroute_003.Output -> reroute_004.Input
    position_1.links.new(
        position_1.nodes["Reroute.003"].outputs[0],
        position_1.nodes["Reroute.004"].inputs[0]
    )
    # reroute_005.Output -> reroute_006.Input
    position_1.links.new(
        position_1.nodes["Reroute.005"].outputs[0],
        position_1.nodes["Reroute.006"].inputs[0]
    )
    # reroute.Output -> align_rotation_to_vector.Vector
    position_1.links.new(
        position_1.nodes["Reroute"].outputs[0],
        position_1.nodes["Align Rotation to Vector"].inputs[2]
    )
    # reroute_007.Output -> realize_instances.Geometry
    position_1.links.new(
        position_1.nodes["Reroute.007"].outputs[0],
        position_1.nodes["Realize Instances"].inputs[0]
    )
    # reroute_002.Output -> cone.Depth
    position_1.links.new(
        position_1.nodes["Reroute.002"].outputs[0],
        position_1.nodes["Cone"].inputs[5]
    )
    # reroute_002.Output -> vector_math_003.Scale
    position_1.links.new(
        position_1.nodes["Reroute.002"].outputs[0],
        position_1.nodes["Vector Math.003"].inputs[3]
    )
    # reroute_002.Output -> math_001.Value
    position_1.links.new(
        position_1.nodes["Reroute.002"].outputs[0],
        position_1.nodes["Math.001"].inputs[0]
    )
    # reroute_004.Output -> transform_geometry.Translation
    position_1.links.new(
        position_1.nodes["Reroute.004"].outputs[0],
        position_1.nodes["Transform Geometry"].inputs[2]
    )
    # reroute_006.Output -> mesh_to_points.Selection
    position_1.links.new(
        position_1.nodes["Reroute.006"].outputs[0],
        position_1.nodes["Mesh to Points"].inputs[1]
    )
    # reroute_009.Output -> curve_line.Start
    position_1.links.new(
        position_1.nodes["Reroute.009"].outputs[0],
        position_1.nodes["Curve Line"].inputs[0]
    )
    # realize_instances.Geometry -> join_geometry.Geometry
    position_1.links.new(
        position_1.nodes["Realize Instances"].outputs[0],
        position_1.nodes["Join Geometry"].inputs[0]
    )

    return position_1


def vitesse_1_node_group(node_tree_names: dict[typing.Callable, str]):
    """Initialize Vitesse node group"""
    vitesse_1 = bpy.data.node_groups.new(type='GeometryNodeTree', name=SUBGROUP_VITESSE_NAME)
    vitesse_1["vv_subgroup_version"] = SUBGROUP_SCHEMA_VERSION

    vitesse_1.color_tag = 'NONE'
    vitesse_1.description = ""
    vitesse_1.default_group_node_width = 140
    vitesse_1.show_modifier_manage_panel = True

    # vitesse_1 interface

    # Socket Geometry
    geometry_socket = vitesse_1.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'
    geometry_socket.default_input = 'VALUE'
    geometry_socket.structure_type = 'AUTO'

    # Socket orig
    orig_socket = vitesse_1.interface.new_socket(name="orig", in_out='INPUT', socket_type='NodeSocketVector')
    orig_socket.default_value = (0.0, 0.0, 0.0)
    orig_socket.min_value = -10000.0
    orig_socket.max_value = 10000.0
    orig_socket.subtype = 'NONE'
    orig_socket.attribute_domain = 'POINT'
    orig_socket.default_input = 'VALUE'
    orig_socket.structure_type = 'AUTO'

    # Socket ext
    ext_socket = vitesse_1.interface.new_socket(name="ext", in_out='INPUT', socket_type='NodeSocketVector')
    ext_socket.default_value = (0.0, 0.0, 0.0)
    ext_socket.min_value = -10000.0
    ext_socket.max_value = 10000.0
    ext_socket.subtype = 'NONE'
    ext_socket.attribute_domain = 'POINT'
    ext_socket.default_input = 'VALUE'
    ext_socket.structure_type = 'AUTO'

    # Initialize vitesse_1 nodes

    # Node Group Output
    group_output = vitesse_1.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    # Node Group Input
    group_input = vitesse_1.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"

    # Node Curve Line
    curve_line = vitesse_1.nodes.new("GeometryNodeCurvePrimitiveLine")
    curve_line.name = "Curve Line"
    curve_line.mode = 'POINTS'

    # Node Cone
    cone = vitesse_1.nodes.new("GeometryNodeMeshCone")
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
    join_geometry = vitesse_1.nodes.new("GeometryNodeJoinGeometry")
    join_geometry.name = "Join Geometry"

    # Node Align Rotation to Vector
    align_rotation_to_vector = vitesse_1.nodes.new("FunctionNodeAlignRotationToVector")
    align_rotation_to_vector.name = "Align Rotation to Vector"
    align_rotation_to_vector.axis = 'Z'
    align_rotation_to_vector.pivot_axis = 'AUTO'
    # Rotation
    align_rotation_to_vector.inputs[0].default_value = (0.0, 0.0, 0.0)
    # Factor
    align_rotation_to_vector.inputs[1].default_value = 1.0

    # Node Curve to Mesh
    curve_to_mesh = vitesse_1.nodes.new("GeometryNodeCurveToMesh")
    curve_to_mesh.name = "Curve to Mesh"
    # Scale
    curve_to_mesh.inputs[2].default_value = 1.0
    # Fill Caps
    curve_to_mesh.inputs[3].default_value = True

    # Node Curve Circle
    curve_circle = vitesse_1.nodes.new("GeometryNodeCurvePrimitiveCircle")
    curve_circle.name = "Curve Circle"
    curve_circle.mode = 'RADIUS'
    # Resolution
    curve_circle.inputs[0].default_value = 32

    # Node Transform Geometry
    transform_geometry = vitesse_1.nodes.new("GeometryNodeTransform")
    transform_geometry.name = "Transform Geometry"
    # Mode
    transform_geometry.inputs[1].default_value = 'Components'
    # Scale
    transform_geometry.inputs[4].default_value = (1.0, 1.0, 1.0)

    # Node Vector Math
    vector_math = vitesse_1.nodes.new("ShaderNodeVectorMath")
    vector_math.name = "Vector Math"
    vector_math.operation = 'SUBTRACT'

    # Node Set Position
    set_position = vitesse_1.nodes.new("GeometryNodeSetPosition")
    set_position.name = "Set Position"
    # Selection
    set_position.inputs[1].default_value = True
    # Position
    set_position.inputs[2].default_value = (0.0, 0.0, 0.0)

    # Node Vector Math.001
    vector_math_001 = vitesse_1.nodes.new("ShaderNodeVectorMath")
    vector_math_001.name = "Vector Math.001"
    vector_math_001.operation = 'NORMALIZE'

    # Node Vector Math.002
    vector_math_002 = vitesse_1.nodes.new("ShaderNodeVectorMath")
    vector_math_002.name = "Vector Math.002"
    vector_math_002.operation = 'MULTIPLY'
    # Vector_001
    vector_math_002.inputs[1].default_value = (-1.0, -1.0, -1.0)

    # Node Vector Math.003
    vector_math_003 = vitesse_1.nodes.new("ShaderNodeVectorMath")
    vector_math_003.name = "Vector Math.003"
    vector_math_003.operation = 'SCALE'

    # Node Mesh to Points
    mesh_to_points = vitesse_1.nodes.new("GeometryNodeMeshToPoints")
    mesh_to_points.name = "Mesh to Points"
    mesh_to_points.mode = 'FACES'
    # Position
    mesh_to_points.inputs[2].default_value = (0.0, 0.0, 0.0)
    # Radius
    mesh_to_points.inputs[3].default_value = 0.05000000074505806

    # Node Realize Instances
    realize_instances = vitesse_1.nodes.new("GeometryNodeRealizeInstances")
    realize_instances.name = "Realize Instances"
    realize_instances.realize_to_point_domain = True
    # Selection
    realize_instances.inputs[1].default_value = True
    # Realize All
    realize_instances.inputs[2].default_value = True
    # Depth
    realize_instances.inputs[3].default_value = 0

    # Node Sample Index
    sample_index = vitesse_1.nodes.new("GeometryNodeSampleIndex")
    sample_index.name = "Sample Index"
    sample_index.clamp = False
    sample_index.data_type = 'FLOAT_VECTOR'
    sample_index.domain = 'POINT'
    # Index
    sample_index.inputs[2].default_value = 0

    # Node Position
    position = vitesse_1.nodes.new("GeometryNodeInputPosition")
    position.name = "Position"

    # Node Value
    value = vitesse_1.nodes.new("ShaderNodeValue")
    value.name = "Value"

    value.outputs[0].default_value = 0.30000001192092896
    # Node Math
    math = vitesse_1.nodes.new("ShaderNodeMath")
    math.name = "Math"
    math.operation = 'SUBTRACT'
    math.use_clamp = False
    # Value_001
    math.inputs[1].default_value = 0.20000000298023224

    # Node Math.001
    math_001 = vitesse_1.nodes.new("ShaderNodeMath")
    math_001.name = "Math.001"
    math_001.operation = 'SUBTRACT'
    math_001.use_clamp = False
    # Value_001
    math_001.inputs[1].default_value = 0.3199999928474426

    # Node Set Shade Smooth
    set_shade_smooth = vitesse_1.nodes.new("GeometryNodeSetShadeSmooth")
    set_shade_smooth.name = "Set Shade Smooth"
    set_shade_smooth.domain = 'FACE'
    # Selection
    set_shade_smooth.inputs[1].default_value = True
    # Shade Smooth
    set_shade_smooth.inputs[2].default_value = True

    # Node Reroute
    reroute = vitesse_1.nodes.new("NodeReroute")
    reroute.name = "Reroute"
    reroute.socket_idname = "NodeSocketVector"
    # Node Reroute.001
    reroute_001 = vitesse_1.nodes.new("NodeReroute")
    reroute_001.name = "Reroute.001"
    reroute_001.socket_idname = "NodeSocketFloat"
    # Node Reroute.002
    reroute_002 = vitesse_1.nodes.new("NodeReroute")
    reroute_002.name = "Reroute.002"
    reroute_002.socket_idname = "NodeSocketFloat"
    # Node Reroute.003
    reroute_003 = vitesse_1.nodes.new("NodeReroute")
    reroute_003.name = "Reroute.003"
    reroute_003.socket_idname = "NodeSocketVector"
    # Node Reroute.004
    reroute_004 = vitesse_1.nodes.new("NodeReroute")
    reroute_004.name = "Reroute.004"
    reroute_004.socket_idname = "NodeSocketVector"
    # Node Reroute.005
    reroute_005 = vitesse_1.nodes.new("NodeReroute")
    reroute_005.name = "Reroute.005"
    reroute_005.socket_idname = "NodeSocketBool"
    # Node Reroute.006
    reroute_006 = vitesse_1.nodes.new("NodeReroute")
    reroute_006.name = "Reroute.006"
    reroute_006.socket_idname = "NodeSocketBool"
    # Node Reroute.007
    reroute_007 = vitesse_1.nodes.new("NodeReroute")
    reroute_007.name = "Reroute.007"
    reroute_007.socket_idname = "NodeSocketGeometry"
    # Node Reroute.008
    reroute_008 = vitesse_1.nodes.new("NodeReroute")
    reroute_008.name = "Reroute.008"
    reroute_008.socket_idname = "NodeSocketVector"
    # Node Reroute.009
    reroute_009 = vitesse_1.nodes.new("NodeReroute")
    reroute_009.name = "Reroute.009"
    reroute_009.socket_idname = "NodeSocketVector"
    # Set locations
    vitesse_1.nodes["Group Output"].location = (1457.876953125, 60.35575485229492)
    vitesse_1.nodes["Group Input"].location = (-1326.938232421875, 255.12811279296875)
    vitesse_1.nodes["Curve Line"].location = (672.876953125, 73.52409362792969)
    vitesse_1.nodes["Cone"].location = (-433.33642578125, 16.64124298095703)
    vitesse_1.nodes["Join Geometry"].location = (1077.876953125, 34.02409744262695)
    vitesse_1.nodes["Align Rotation to Vector"].location = (-405.229736328125, 314.89276123046875)
    vitesse_1.nodes["Curve to Mesh"].location = (875.376953125, -47.97590255737305)
    vitesse_1.nodes["Curve Circle"].location = (672.876953125, -548.6061401367188)
    vitesse_1.nodes["Transform Geometry"].location = (-149.623046875, 343.89276123046875)
    vitesse_1.nodes["Vector Math"].location = (-863.33642578125, 49.710208892822266)
    vitesse_1.nodes["Set Position"].location = (52.876953125, 190.8927459716797)
    vitesse_1.nodes["Vector Math.001"].location = (-635.83642578125, -406.9115905761719)
    vitesse_1.nodes["Vector Math.002"].location = (-149.623046875, -10.37497615814209)
    vitesse_1.nodes["Vector Math.003"].location = (-405.229736328125, -406.9115905761719)
    vitesse_1.nodes["Mesh to Points"].location = (267.876953125, 126.64057922363281)
    vitesse_1.nodes["Realize Instances"].location = (875.376953125, 601.1000366210938)
    vitesse_1.nodes["Sample Index"].location = (470.376953125, -26.622249603271484)
    vitesse_1.nodes["Position"].location = (267.876953125, -194.62713623046875)
    vitesse_1.nodes["Value"].location = (-863.33642578125, -345.5478210449219)
    vitesse_1.nodes["Math"].location = (-635.83642578125, -208.91159057617188)
    vitesse_1.nodes["Math.001"].location = (470.376953125, -548.6061401367188)
    vitesse_1.nodes["Set Shade Smooth"].location = (1267.876953125, 60.35575485229492)
    vitesse_1.nodes["Reroute"].location = (-635.83642578125, 185.9512176513672)
    vitesse_1.nodes["Reroute.001"].location = (-635.83642578125, -657.191162109375)
    vitesse_1.nodes["Reroute.002"].location = (-495.83642578125, -657.191162109375)
    vitesse_1.nodes["Reroute.003"].location = (-863.33642578125, 372.89276123046875)
    vitesse_1.nodes["Reroute.004"].location = (-237.123046875, 372.89276123046875)
    vitesse_1.nodes["Reroute.005"].location = (-149.623046875, -245.37496948242188)
    vitesse_1.nodes["Reroute.006"].location = (192.876953125, -245.37496948242188)
    vitesse_1.nodes["Reroute.007"].location = (267.876953125, 566.9782104492188)
    vitesse_1.nodes["Reroute.008"].location = (-863.33642578125, 430.89276123046875)
    vitesse_1.nodes["Reroute.009"].location = (610.376953125, 430.89276123046875)

    # Set dimensions
    vitesse_1.nodes["Group Output"].width  = 140.0
    vitesse_1.nodes["Group Output"].height = 100.0

    vitesse_1.nodes["Group Input"].width  = 140.0
    vitesse_1.nodes["Group Input"].height = 100.0

    vitesse_1.nodes["Curve Line"].width  = 140.0
    vitesse_1.nodes["Curve Line"].height = 100.0

    vitesse_1.nodes["Cone"].width  = 196.21337890625
    vitesse_1.nodes["Cone"].height = 100.0

    vitesse_1.nodes["Join Geometry"].width  = 140.0
    vitesse_1.nodes["Join Geometry"].height = 100.0

    vitesse_1.nodes["Align Rotation to Vector"].width  = 140.0
    vitesse_1.nodes["Align Rotation to Vector"].height = 100.0

    vitesse_1.nodes["Curve to Mesh"].width  = 140.0
    vitesse_1.nodes["Curve to Mesh"].height = 100.0

    vitesse_1.nodes["Curve Circle"].width  = 140.0
    vitesse_1.nodes["Curve Circle"].height = 100.0

    vitesse_1.nodes["Transform Geometry"].width  = 140.0
    vitesse_1.nodes["Transform Geometry"].height = 100.0

    vitesse_1.nodes["Vector Math"].width  = 140.0
    vitesse_1.nodes["Vector Math"].height = 100.0

    vitesse_1.nodes["Set Position"].width  = 140.0
    vitesse_1.nodes["Set Position"].height = 100.0

    vitesse_1.nodes["Vector Math.001"].width  = 140.0
    vitesse_1.nodes["Vector Math.001"].height = 100.0

    vitesse_1.nodes["Vector Math.002"].width  = 140.0
    vitesse_1.nodes["Vector Math.002"].height = 100.0

    vitesse_1.nodes["Vector Math.003"].width  = 140.0
    vitesse_1.nodes["Vector Math.003"].height = 100.0

    vitesse_1.nodes["Mesh to Points"].width  = 140.0
    vitesse_1.nodes["Mesh to Points"].height = 100.0

    vitesse_1.nodes["Realize Instances"].width  = 140.0
    vitesse_1.nodes["Realize Instances"].height = 100.0

    vitesse_1.nodes["Sample Index"].width  = 140.0
    vitesse_1.nodes["Sample Index"].height = 100.0

    vitesse_1.nodes["Position"].width  = 140.0
    vitesse_1.nodes["Position"].height = 100.0

    vitesse_1.nodes["Value"].width  = 140.0
    vitesse_1.nodes["Value"].height = 100.0

    vitesse_1.nodes["Math"].width  = 140.0
    vitesse_1.nodes["Math"].height = 100.0

    vitesse_1.nodes["Math.001"].width  = 140.0
    vitesse_1.nodes["Math.001"].height = 100.0

    vitesse_1.nodes["Set Shade Smooth"].width  = 140.0
    vitesse_1.nodes["Set Shade Smooth"].height = 100.0

    vitesse_1.nodes["Reroute"].width  = 10.0
    vitesse_1.nodes["Reroute"].height = 100.0

    vitesse_1.nodes["Reroute.001"].width  = 10.0
    vitesse_1.nodes["Reroute.001"].height = 100.0

    vitesse_1.nodes["Reroute.002"].width  = 10.0
    vitesse_1.nodes["Reroute.002"].height = 100.0

    vitesse_1.nodes["Reroute.003"].width  = 10.0
    vitesse_1.nodes["Reroute.003"].height = 100.0

    vitesse_1.nodes["Reroute.004"].width  = 10.0
    vitesse_1.nodes["Reroute.004"].height = 100.0

    vitesse_1.nodes["Reroute.005"].width  = 10.0
    vitesse_1.nodes["Reroute.005"].height = 100.0

    vitesse_1.nodes["Reroute.006"].width  = 10.0
    vitesse_1.nodes["Reroute.006"].height = 100.0

    vitesse_1.nodes["Reroute.007"].width  = 10.0
    vitesse_1.nodes["Reroute.007"].height = 100.0

    vitesse_1.nodes["Reroute.008"].width  = 10.0
    vitesse_1.nodes["Reroute.008"].height = 100.0

    vitesse_1.nodes["Reroute.009"].width  = 10.0
    vitesse_1.nodes["Reroute.009"].height = 100.0


    # Initialize vitesse_1 links

    # align_rotation_to_vector.Rotation -> transform_geometry.Rotation
    vitesse_1.links.new(
        vitesse_1.nodes["Align Rotation to Vector"].outputs[0],
        vitesse_1.nodes["Transform Geometry"].inputs[3]
    )
    # math.Value -> cone.Radius Bottom
    vitesse_1.links.new(
        vitesse_1.nodes["Math"].outputs[0],
        vitesse_1.nodes["Cone"].inputs[4]
    )
    # curve_line.Curve -> curve_to_mesh.Curve
    vitesse_1.links.new(
        vitesse_1.nodes["Curve Line"].outputs[0],
        vitesse_1.nodes["Curve to Mesh"].inputs[0]
    )
    # vector_math.Vector -> vector_math_001.Vector
    vitesse_1.links.new(
        vitesse_1.nodes["Vector Math"].outputs[0],
        vitesse_1.nodes["Vector Math.001"].inputs[0]
    )
    # vector_math_003.Vector -> vector_math_002.Vector
    vitesse_1.links.new(
        vitesse_1.nodes["Vector Math.003"].outputs[0],
        vitesse_1.nodes["Vector Math.002"].inputs[0]
    )
    # vector_math_002.Vector -> set_position.Offset
    vitesse_1.links.new(
        vitesse_1.nodes["Vector Math.002"].outputs[0],
        vitesse_1.nodes["Set Position"].inputs[3]
    )
    # math_001.Value -> curve_circle.Radius
    vitesse_1.links.new(
        vitesse_1.nodes["Math.001"].outputs[0],
        vitesse_1.nodes["Curve Circle"].inputs[4]
    )
    # curve_to_mesh.Mesh -> join_geometry.Geometry
    vitesse_1.links.new(
        vitesse_1.nodes["Curve to Mesh"].outputs[0],
        vitesse_1.nodes["Join Geometry"].inputs[0]
    )
    # set_position.Geometry -> mesh_to_points.Mesh
    vitesse_1.links.new(
        vitesse_1.nodes["Set Position"].outputs[0],
        vitesse_1.nodes["Mesh to Points"].inputs[0]
    )
    # mesh_to_points.Points -> sample_index.Geometry
    vitesse_1.links.new(
        vitesse_1.nodes["Mesh to Points"].outputs[0],
        vitesse_1.nodes["Sample Index"].inputs[0]
    )
    # vector_math_001.Vector -> vector_math_003.Vector
    vitesse_1.links.new(
        vitesse_1.nodes["Vector Math.001"].outputs[0],
        vitesse_1.nodes["Vector Math.003"].inputs[0]
    )
    # position.Position -> sample_index.Value
    vitesse_1.links.new(
        vitesse_1.nodes["Position"].outputs[0],
        vitesse_1.nodes["Sample Index"].inputs[1]
    )
    # sample_index.Value -> curve_line.End
    vitesse_1.links.new(
        vitesse_1.nodes["Sample Index"].outputs[0],
        vitesse_1.nodes["Curve Line"].inputs[1]
    )
    # transform_geometry.Geometry -> set_position.Geometry
    vitesse_1.links.new(
        vitesse_1.nodes["Transform Geometry"].outputs[0],
        vitesse_1.nodes["Set Position"].inputs[0]
    )
    # value.Value -> math.Value
    vitesse_1.links.new(
        vitesse_1.nodes["Value"].outputs[0],
        vitesse_1.nodes["Math"].inputs[0]
    )
    # curve_circle.Curve -> curve_to_mesh.Profile Curve
    vitesse_1.links.new(
        vitesse_1.nodes["Curve Circle"].outputs[0],
        vitesse_1.nodes["Curve to Mesh"].inputs[1]
    )
    # cone.Mesh -> transform_geometry.Geometry
    vitesse_1.links.new(
        vitesse_1.nodes["Cone"].outputs[0],
        vitesse_1.nodes["Transform Geometry"].inputs[0]
    )
    # group_input.ext -> vector_math.Vector
    vitesse_1.links.new(
        vitesse_1.nodes["Group Input"].outputs[1],
        vitesse_1.nodes["Vector Math"].inputs[0]
    )
    # group_input.orig -> vector_math.Vector
    vitesse_1.links.new(
        vitesse_1.nodes["Group Input"].outputs[0],
        vitesse_1.nodes["Vector Math"].inputs[1]
    )
    # set_shade_smooth.Mesh -> group_output.Geometry
    vitesse_1.links.new(
        vitesse_1.nodes["Set Shade Smooth"].outputs[0],
        vitesse_1.nodes["Group Output"].inputs[0]
    )
    # join_geometry.Geometry -> set_shade_smooth.Mesh
    vitesse_1.links.new(
        vitesse_1.nodes["Join Geometry"].outputs[0],
        vitesse_1.nodes["Set Shade Smooth"].inputs[0]
    )
    # group_input.orig -> reroute_008.Input
    vitesse_1.links.new(
        vitesse_1.nodes["Group Input"].outputs[0],
        vitesse_1.nodes["Reroute.008"].inputs[0]
    )
    # group_input.ext -> reroute_003.Input
    vitesse_1.links.new(
        vitesse_1.nodes["Group Input"].outputs[1],
        vitesse_1.nodes["Reroute.003"].inputs[0]
    )
    # cone.Bottom -> reroute_005.Input
    vitesse_1.links.new(
        vitesse_1.nodes["Cone"].outputs[2],
        vitesse_1.nodes["Reroute.005"].inputs[0]
    )
    # vector_math.Vector -> reroute.Input
    vitesse_1.links.new(
        vitesse_1.nodes["Vector Math"].outputs[0],
        vitesse_1.nodes["Reroute"].inputs[0]
    )
    # set_position.Geometry -> reroute_007.Input
    vitesse_1.links.new(
        vitesse_1.nodes["Set Position"].outputs[0],
        vitesse_1.nodes["Reroute.007"].inputs[0]
    )
    # value.Value -> reroute_001.Input
    vitesse_1.links.new(
        vitesse_1.nodes["Value"].outputs[0],
        vitesse_1.nodes["Reroute.001"].inputs[0]
    )
    # reroute_001.Output -> reroute_002.Input
    vitesse_1.links.new(
        vitesse_1.nodes["Reroute.001"].outputs[0],
        vitesse_1.nodes["Reroute.002"].inputs[0]
    )
    # reroute_008.Output -> reroute_009.Input
    vitesse_1.links.new(
        vitesse_1.nodes["Reroute.008"].outputs[0],
        vitesse_1.nodes["Reroute.009"].inputs[0]
    )
    # reroute_003.Output -> reroute_004.Input
    vitesse_1.links.new(
        vitesse_1.nodes["Reroute.003"].outputs[0],
        vitesse_1.nodes["Reroute.004"].inputs[0]
    )
    # reroute_005.Output -> reroute_006.Input
    vitesse_1.links.new(
        vitesse_1.nodes["Reroute.005"].outputs[0],
        vitesse_1.nodes["Reroute.006"].inputs[0]
    )
    # reroute.Output -> align_rotation_to_vector.Vector
    vitesse_1.links.new(
        vitesse_1.nodes["Reroute"].outputs[0],
        vitesse_1.nodes["Align Rotation to Vector"].inputs[2]
    )
    # reroute_007.Output -> realize_instances.Geometry
    vitesse_1.links.new(
        vitesse_1.nodes["Reroute.007"].outputs[0],
        vitesse_1.nodes["Realize Instances"].inputs[0]
    )
    # reroute_002.Output -> cone.Depth
    vitesse_1.links.new(
        vitesse_1.nodes["Reroute.002"].outputs[0],
        vitesse_1.nodes["Cone"].inputs[5]
    )
    # reroute_002.Output -> vector_math_003.Scale
    vitesse_1.links.new(
        vitesse_1.nodes["Reroute.002"].outputs[0],
        vitesse_1.nodes["Vector Math.003"].inputs[3]
    )
    # reroute_002.Output -> math_001.Value
    vitesse_1.links.new(
        vitesse_1.nodes["Reroute.002"].outputs[0],
        vitesse_1.nodes["Math.001"].inputs[0]
    )
    # reroute_004.Output -> transform_geometry.Translation
    vitesse_1.links.new(
        vitesse_1.nodes["Reroute.004"].outputs[0],
        vitesse_1.nodes["Transform Geometry"].inputs[2]
    )
    # reroute_006.Output -> mesh_to_points.Selection
    vitesse_1.links.new(
        vitesse_1.nodes["Reroute.006"].outputs[0],
        vitesse_1.nodes["Mesh to Points"].inputs[1]
    )
    # reroute_009.Output -> curve_line.Start
    vitesse_1.links.new(
        vitesse_1.nodes["Reroute.009"].outputs[0],
        vitesse_1.nodes["Curve Line"].inputs[0]
    )
    # realize_instances.Geometry -> join_geometry.Geometry
    vitesse_1.links.new(
        vitesse_1.nodes["Realize Instances"].outputs[0],
        vitesse_1.nodes["Join Geometry"].inputs[0]
    )

    return vitesse_1


def acceleration_1_node_group(node_tree_names: dict[typing.Callable, str]):
    """Initialize acceleration node group"""
    acceleration_1 = bpy.data.node_groups.new(type='GeometryNodeTree', name=SUBGROUP_ACCELERATION_NAME)
    acceleration_1["vv_subgroup_version"] = SUBGROUP_SCHEMA_VERSION

    acceleration_1.color_tag = 'NONE'
    acceleration_1.description = ""
    acceleration_1.default_group_node_width = 140
    acceleration_1.show_modifier_manage_panel = True

    # acceleration_1 interface

    # Socket Geometry
    geometry_socket = acceleration_1.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'
    geometry_socket.default_input = 'VALUE'
    geometry_socket.structure_type = 'AUTO'

    # Socket orig
    orig_socket = acceleration_1.interface.new_socket(name="orig", in_out='INPUT', socket_type='NodeSocketVector')
    orig_socket.default_value = (0.0, 0.0, 0.0)
    orig_socket.min_value = -10000.0
    orig_socket.max_value = 10000.0
    orig_socket.subtype = 'NONE'
    orig_socket.attribute_domain = 'POINT'
    orig_socket.default_input = 'VALUE'
    orig_socket.structure_type = 'AUTO'

    # Socket ext
    ext_socket = acceleration_1.interface.new_socket(name="ext", in_out='INPUT', socket_type='NodeSocketVector')
    ext_socket.default_value = (0.0, 0.0, 0.0)
    ext_socket.min_value = -10000.0
    ext_socket.max_value = 10000.0
    ext_socket.subtype = 'NONE'
    ext_socket.attribute_domain = 'POINT'
    ext_socket.default_input = 'VALUE'
    ext_socket.structure_type = 'AUTO'

    # Initialize acceleration_1 nodes

    # Node Group Output
    group_output = acceleration_1.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    # Node Group Input
    group_input = acceleration_1.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"

    # Node Curve Line
    curve_line = acceleration_1.nodes.new("GeometryNodeCurvePrimitiveLine")
    curve_line.name = "Curve Line"
    curve_line.mode = 'POINTS'

    # Node Cone
    cone = acceleration_1.nodes.new("GeometryNodeMeshCone")
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
    join_geometry = acceleration_1.nodes.new("GeometryNodeJoinGeometry")
    join_geometry.name = "Join Geometry"

    # Node Align Rotation to Vector
    align_rotation_to_vector = acceleration_1.nodes.new("FunctionNodeAlignRotationToVector")
    align_rotation_to_vector.name = "Align Rotation to Vector"
    align_rotation_to_vector.axis = 'Z'
    align_rotation_to_vector.pivot_axis = 'AUTO'
    # Rotation
    align_rotation_to_vector.inputs[0].default_value = (0.0, 0.0, 0.0)
    # Factor
    align_rotation_to_vector.inputs[1].default_value = 1.0

    # Node Curve to Mesh
    curve_to_mesh = acceleration_1.nodes.new("GeometryNodeCurveToMesh")
    curve_to_mesh.name = "Curve to Mesh"
    # Scale
    curve_to_mesh.inputs[2].default_value = 1.0
    # Fill Caps
    curve_to_mesh.inputs[3].default_value = True

    # Node Curve Circle
    curve_circle = acceleration_1.nodes.new("GeometryNodeCurvePrimitiveCircle")
    curve_circle.name = "Curve Circle"
    curve_circle.mode = 'RADIUS'
    # Resolution
    curve_circle.inputs[0].default_value = 32

    # Node Transform Geometry
    transform_geometry = acceleration_1.nodes.new("GeometryNodeTransform")
    transform_geometry.name = "Transform Geometry"
    # Mode
    transform_geometry.inputs[1].default_value = 'Components'
    # Scale
    transform_geometry.inputs[4].default_value = (1.0, 1.0, 1.0)

    # Node Vector Math
    vector_math = acceleration_1.nodes.new("ShaderNodeVectorMath")
    vector_math.name = "Vector Math"
    vector_math.operation = 'SUBTRACT'

    # Node Set Position
    set_position = acceleration_1.nodes.new("GeometryNodeSetPosition")
    set_position.name = "Set Position"
    # Selection
    set_position.inputs[1].default_value = True
    # Position
    set_position.inputs[2].default_value = (0.0, 0.0, 0.0)

    # Node Vector Math.001
    vector_math_001 = acceleration_1.nodes.new("ShaderNodeVectorMath")
    vector_math_001.name = "Vector Math.001"
    vector_math_001.operation = 'NORMALIZE'

    # Node Vector Math.002
    vector_math_002 = acceleration_1.nodes.new("ShaderNodeVectorMath")
    vector_math_002.name = "Vector Math.002"
    vector_math_002.operation = 'MULTIPLY'
    # Vector_001
    vector_math_002.inputs[1].default_value = (-1.0, -1.0, -1.0)

    # Node Vector Math.003
    vector_math_003 = acceleration_1.nodes.new("ShaderNodeVectorMath")
    vector_math_003.name = "Vector Math.003"
    vector_math_003.operation = 'SCALE'

    # Node Mesh to Points
    mesh_to_points = acceleration_1.nodes.new("GeometryNodeMeshToPoints")
    mesh_to_points.name = "Mesh to Points"
    mesh_to_points.mode = 'FACES'
    # Position
    mesh_to_points.inputs[2].default_value = (0.0, 0.0, 0.0)
    # Radius
    mesh_to_points.inputs[3].default_value = 0.05000000074505806

    # Node Realize Instances
    realize_instances = acceleration_1.nodes.new("GeometryNodeRealizeInstances")
    realize_instances.name = "Realize Instances"
    realize_instances.realize_to_point_domain = True
    # Selection
    realize_instances.inputs[1].default_value = True
    # Realize All
    realize_instances.inputs[2].default_value = True
    # Depth
    realize_instances.inputs[3].default_value = 0

    # Node Sample Index
    sample_index = acceleration_1.nodes.new("GeometryNodeSampleIndex")
    sample_index.name = "Sample Index"
    sample_index.clamp = False
    sample_index.data_type = 'FLOAT_VECTOR'
    sample_index.domain = 'POINT'
    # Index
    sample_index.inputs[2].default_value = 0

    # Node Position
    position = acceleration_1.nodes.new("GeometryNodeInputPosition")
    position.name = "Position"

    # Node Value
    value = acceleration_1.nodes.new("ShaderNodeValue")
    value.name = "Value"

    value.outputs[0].default_value = 0.30000001192092896
    # Node Math
    math = acceleration_1.nodes.new("ShaderNodeMath")
    math.name = "Math"
    math.operation = 'SUBTRACT'
    math.use_clamp = False
    # Value_001
    math.inputs[1].default_value = 0.20000000298023224

    # Node Math.001
    math_001 = acceleration_1.nodes.new("ShaderNodeMath")
    math_001.name = "Math.001"
    math_001.operation = 'SUBTRACT'
    math_001.use_clamp = False
    # Value_001
    math_001.inputs[1].default_value = 0.3199999928474426

    # Node Set Shade Smooth
    set_shade_smooth = acceleration_1.nodes.new("GeometryNodeSetShadeSmooth")
    set_shade_smooth.name = "Set Shade Smooth"
    set_shade_smooth.domain = 'FACE'
    # Selection
    set_shade_smooth.inputs[1].default_value = True
    # Shade Smooth
    set_shade_smooth.inputs[2].default_value = True

    # Node Reroute
    reroute = acceleration_1.nodes.new("NodeReroute")
    reroute.name = "Reroute"
    reroute.socket_idname = "NodeSocketVector"
    # Node Reroute.001
    reroute_001 = acceleration_1.nodes.new("NodeReroute")
    reroute_001.name = "Reroute.001"
    reroute_001.socket_idname = "NodeSocketFloat"
    # Node Reroute.002
    reroute_002 = acceleration_1.nodes.new("NodeReroute")
    reroute_002.name = "Reroute.002"
    reroute_002.socket_idname = "NodeSocketFloat"
    # Node Reroute.003
    reroute_003 = acceleration_1.nodes.new("NodeReroute")
    reroute_003.name = "Reroute.003"
    reroute_003.socket_idname = "NodeSocketVector"
    # Node Reroute.004
    reroute_004 = acceleration_1.nodes.new("NodeReroute")
    reroute_004.name = "Reroute.004"
    reroute_004.socket_idname = "NodeSocketVector"
    # Node Reroute.005
    reroute_005 = acceleration_1.nodes.new("NodeReroute")
    reroute_005.name = "Reroute.005"
    reroute_005.socket_idname = "NodeSocketBool"
    # Node Reroute.006
    reroute_006 = acceleration_1.nodes.new("NodeReroute")
    reroute_006.name = "Reroute.006"
    reroute_006.socket_idname = "NodeSocketBool"
    # Node Reroute.007
    reroute_007 = acceleration_1.nodes.new("NodeReroute")
    reroute_007.name = "Reroute.007"
    reroute_007.socket_idname = "NodeSocketGeometry"
    # Node Reroute.008
    reroute_008 = acceleration_1.nodes.new("NodeReroute")
    reroute_008.name = "Reroute.008"
    reroute_008.socket_idname = "NodeSocketVector"
    # Node Reroute.009
    reroute_009 = acceleration_1.nodes.new("NodeReroute")
    reroute_009.name = "Reroute.009"
    reroute_009.socket_idname = "NodeSocketVector"
    # Set locations
    acceleration_1.nodes["Group Output"].location = (1457.876953125, 60.35575485229492)
    acceleration_1.nodes["Group Input"].location = (-1326.938232421875, 255.12811279296875)
    acceleration_1.nodes["Curve Line"].location = (672.876953125, 73.52409362792969)
    acceleration_1.nodes["Cone"].location = (-433.33642578125, 16.64124298095703)
    acceleration_1.nodes["Join Geometry"].location = (1077.876953125, 34.02409744262695)
    acceleration_1.nodes["Align Rotation to Vector"].location = (-405.229736328125, 314.89276123046875)
    acceleration_1.nodes["Curve to Mesh"].location = (875.376953125, -47.97590255737305)
    acceleration_1.nodes["Curve Circle"].location = (672.876953125, -548.6061401367188)
    acceleration_1.nodes["Transform Geometry"].location = (-149.623046875, 343.89276123046875)
    acceleration_1.nodes["Vector Math"].location = (-863.33642578125, 49.710208892822266)
    acceleration_1.nodes["Set Position"].location = (52.876953125, 190.8927459716797)
    acceleration_1.nodes["Vector Math.001"].location = (-635.83642578125, -406.9115905761719)
    acceleration_1.nodes["Vector Math.002"].location = (-149.623046875, -10.37497615814209)
    acceleration_1.nodes["Vector Math.003"].location = (-405.229736328125, -406.9115905761719)
    acceleration_1.nodes["Mesh to Points"].location = (267.876953125, 126.64057922363281)
    acceleration_1.nodes["Realize Instances"].location = (875.376953125, 601.1000366210938)
    acceleration_1.nodes["Sample Index"].location = (470.376953125, -26.622249603271484)
    acceleration_1.nodes["Position"].location = (267.876953125, -194.62713623046875)
    acceleration_1.nodes["Value"].location = (-863.33642578125, -345.5478210449219)
    acceleration_1.nodes["Math"].location = (-635.83642578125, -208.91159057617188)
    acceleration_1.nodes["Math.001"].location = (470.376953125, -548.6061401367188)
    acceleration_1.nodes["Set Shade Smooth"].location = (1267.876953125, 60.35575485229492)
    acceleration_1.nodes["Reroute"].location = (-635.83642578125, 185.9512176513672)
    acceleration_1.nodes["Reroute.001"].location = (-635.83642578125, -657.191162109375)
    acceleration_1.nodes["Reroute.002"].location = (-495.83642578125, -657.191162109375)
    acceleration_1.nodes["Reroute.003"].location = (-863.33642578125, 372.89276123046875)
    acceleration_1.nodes["Reroute.004"].location = (-237.123046875, 372.89276123046875)
    acceleration_1.nodes["Reroute.005"].location = (-149.623046875, -245.37496948242188)
    acceleration_1.nodes["Reroute.006"].location = (192.876953125, -245.37496948242188)
    acceleration_1.nodes["Reroute.007"].location = (267.876953125, 566.9782104492188)
    acceleration_1.nodes["Reroute.008"].location = (-863.33642578125, 430.89276123046875)
    acceleration_1.nodes["Reroute.009"].location = (610.376953125, 430.89276123046875)

    # Set dimensions
    acceleration_1.nodes["Group Output"].width  = 140.0
    acceleration_1.nodes["Group Output"].height = 100.0

    acceleration_1.nodes["Group Input"].width  = 140.0
    acceleration_1.nodes["Group Input"].height = 100.0

    acceleration_1.nodes["Curve Line"].width  = 140.0
    acceleration_1.nodes["Curve Line"].height = 100.0

    acceleration_1.nodes["Cone"].width  = 196.21337890625
    acceleration_1.nodes["Cone"].height = 100.0

    acceleration_1.nodes["Join Geometry"].width  = 140.0
    acceleration_1.nodes["Join Geometry"].height = 100.0

    acceleration_1.nodes["Align Rotation to Vector"].width  = 140.0
    acceleration_1.nodes["Align Rotation to Vector"].height = 100.0

    acceleration_1.nodes["Curve to Mesh"].width  = 140.0
    acceleration_1.nodes["Curve to Mesh"].height = 100.0

    acceleration_1.nodes["Curve Circle"].width  = 140.0
    acceleration_1.nodes["Curve Circle"].height = 100.0

    acceleration_1.nodes["Transform Geometry"].width  = 140.0
    acceleration_1.nodes["Transform Geometry"].height = 100.0

    acceleration_1.nodes["Vector Math"].width  = 140.0
    acceleration_1.nodes["Vector Math"].height = 100.0

    acceleration_1.nodes["Set Position"].width  = 140.0
    acceleration_1.nodes["Set Position"].height = 100.0

    acceleration_1.nodes["Vector Math.001"].width  = 140.0
    acceleration_1.nodes["Vector Math.001"].height = 100.0

    acceleration_1.nodes["Vector Math.002"].width  = 140.0
    acceleration_1.nodes["Vector Math.002"].height = 100.0

    acceleration_1.nodes["Vector Math.003"].width  = 140.0
    acceleration_1.nodes["Vector Math.003"].height = 100.0

    acceleration_1.nodes["Mesh to Points"].width  = 140.0
    acceleration_1.nodes["Mesh to Points"].height = 100.0

    acceleration_1.nodes["Realize Instances"].width  = 140.0
    acceleration_1.nodes["Realize Instances"].height = 100.0

    acceleration_1.nodes["Sample Index"].width  = 140.0
    acceleration_1.nodes["Sample Index"].height = 100.0

    acceleration_1.nodes["Position"].width  = 140.0
    acceleration_1.nodes["Position"].height = 100.0

    acceleration_1.nodes["Value"].width  = 140.0
    acceleration_1.nodes["Value"].height = 100.0

    acceleration_1.nodes["Math"].width  = 140.0
    acceleration_1.nodes["Math"].height = 100.0

    acceleration_1.nodes["Math.001"].width  = 140.0
    acceleration_1.nodes["Math.001"].height = 100.0

    acceleration_1.nodes["Set Shade Smooth"].width  = 140.0
    acceleration_1.nodes["Set Shade Smooth"].height = 100.0

    acceleration_1.nodes["Reroute"].width  = 10.0
    acceleration_1.nodes["Reroute"].height = 100.0

    acceleration_1.nodes["Reroute.001"].width  = 10.0
    acceleration_1.nodes["Reroute.001"].height = 100.0

    acceleration_1.nodes["Reroute.002"].width  = 10.0
    acceleration_1.nodes["Reroute.002"].height = 100.0

    acceleration_1.nodes["Reroute.003"].width  = 10.0
    acceleration_1.nodes["Reroute.003"].height = 100.0

    acceleration_1.nodes["Reroute.004"].width  = 10.0
    acceleration_1.nodes["Reroute.004"].height = 100.0

    acceleration_1.nodes["Reroute.005"].width  = 10.0
    acceleration_1.nodes["Reroute.005"].height = 100.0

    acceleration_1.nodes["Reroute.006"].width  = 10.0
    acceleration_1.nodes["Reroute.006"].height = 100.0

    acceleration_1.nodes["Reroute.007"].width  = 10.0
    acceleration_1.nodes["Reroute.007"].height = 100.0

    acceleration_1.nodes["Reroute.008"].width  = 10.0
    acceleration_1.nodes["Reroute.008"].height = 100.0

    acceleration_1.nodes["Reroute.009"].width  = 10.0
    acceleration_1.nodes["Reroute.009"].height = 100.0


    # Initialize acceleration_1 links

    # align_rotation_to_vector.Rotation -> transform_geometry.Rotation
    acceleration_1.links.new(
        acceleration_1.nodes["Align Rotation to Vector"].outputs[0],
        acceleration_1.nodes["Transform Geometry"].inputs[3]
    )
    # math.Value -> cone.Radius Bottom
    acceleration_1.links.new(
        acceleration_1.nodes["Math"].outputs[0],
        acceleration_1.nodes["Cone"].inputs[4]
    )
    # curve_line.Curve -> curve_to_mesh.Curve
    acceleration_1.links.new(
        acceleration_1.nodes["Curve Line"].outputs[0],
        acceleration_1.nodes["Curve to Mesh"].inputs[0]
    )
    # vector_math.Vector -> vector_math_001.Vector
    acceleration_1.links.new(
        acceleration_1.nodes["Vector Math"].outputs[0],
        acceleration_1.nodes["Vector Math.001"].inputs[0]
    )
    # vector_math_003.Vector -> vector_math_002.Vector
    acceleration_1.links.new(
        acceleration_1.nodes["Vector Math.003"].outputs[0],
        acceleration_1.nodes["Vector Math.002"].inputs[0]
    )
    # vector_math_002.Vector -> set_position.Offset
    acceleration_1.links.new(
        acceleration_1.nodes["Vector Math.002"].outputs[0],
        acceleration_1.nodes["Set Position"].inputs[3]
    )
    # math_001.Value -> curve_circle.Radius
    acceleration_1.links.new(
        acceleration_1.nodes["Math.001"].outputs[0],
        acceleration_1.nodes["Curve Circle"].inputs[4]
    )
    # curve_to_mesh.Mesh -> join_geometry.Geometry
    acceleration_1.links.new(
        acceleration_1.nodes["Curve to Mesh"].outputs[0],
        acceleration_1.nodes["Join Geometry"].inputs[0]
    )
    # set_position.Geometry -> mesh_to_points.Mesh
    acceleration_1.links.new(
        acceleration_1.nodes["Set Position"].outputs[0],
        acceleration_1.nodes["Mesh to Points"].inputs[0]
    )
    # mesh_to_points.Points -> sample_index.Geometry
    acceleration_1.links.new(
        acceleration_1.nodes["Mesh to Points"].outputs[0],
        acceleration_1.nodes["Sample Index"].inputs[0]
    )
    # vector_math_001.Vector -> vector_math_003.Vector
    acceleration_1.links.new(
        acceleration_1.nodes["Vector Math.001"].outputs[0],
        acceleration_1.nodes["Vector Math.003"].inputs[0]
    )
    # position.Position -> sample_index.Value
    acceleration_1.links.new(
        acceleration_1.nodes["Position"].outputs[0],
        acceleration_1.nodes["Sample Index"].inputs[1]
    )
    # sample_index.Value -> curve_line.End
    acceleration_1.links.new(
        acceleration_1.nodes["Sample Index"].outputs[0],
        acceleration_1.nodes["Curve Line"].inputs[1]
    )
    # transform_geometry.Geometry -> set_position.Geometry
    acceleration_1.links.new(
        acceleration_1.nodes["Transform Geometry"].outputs[0],
        acceleration_1.nodes["Set Position"].inputs[0]
    )
    # value.Value -> math.Value
    acceleration_1.links.new(
        acceleration_1.nodes["Value"].outputs[0],
        acceleration_1.nodes["Math"].inputs[0]
    )
    # curve_circle.Curve -> curve_to_mesh.Profile Curve
    acceleration_1.links.new(
        acceleration_1.nodes["Curve Circle"].outputs[0],
        acceleration_1.nodes["Curve to Mesh"].inputs[1]
    )
    # cone.Mesh -> transform_geometry.Geometry
    acceleration_1.links.new(
        acceleration_1.nodes["Cone"].outputs[0],
        acceleration_1.nodes["Transform Geometry"].inputs[0]
    )
    # group_input.ext -> vector_math.Vector
    acceleration_1.links.new(
        acceleration_1.nodes["Group Input"].outputs[1],
        acceleration_1.nodes["Vector Math"].inputs[0]
    )
    # group_input.orig -> vector_math.Vector
    acceleration_1.links.new(
        acceleration_1.nodes["Group Input"].outputs[0],
        acceleration_1.nodes["Vector Math"].inputs[1]
    )
    # set_shade_smooth.Mesh -> group_output.Geometry
    acceleration_1.links.new(
        acceleration_1.nodes["Set Shade Smooth"].outputs[0],
        acceleration_1.nodes["Group Output"].inputs[0]
    )
    # join_geometry.Geometry -> set_shade_smooth.Mesh
    acceleration_1.links.new(
        acceleration_1.nodes["Join Geometry"].outputs[0],
        acceleration_1.nodes["Set Shade Smooth"].inputs[0]
    )
    # group_input.orig -> reroute_008.Input
    acceleration_1.links.new(
        acceleration_1.nodes["Group Input"].outputs[0],
        acceleration_1.nodes["Reroute.008"].inputs[0]
    )
    # group_input.ext -> reroute_003.Input
    acceleration_1.links.new(
        acceleration_1.nodes["Group Input"].outputs[1],
        acceleration_1.nodes["Reroute.003"].inputs[0]
    )
    # cone.Bottom -> reroute_005.Input
    acceleration_1.links.new(
        acceleration_1.nodes["Cone"].outputs[2],
        acceleration_1.nodes["Reroute.005"].inputs[0]
    )
    # vector_math.Vector -> reroute.Input
    acceleration_1.links.new(
        acceleration_1.nodes["Vector Math"].outputs[0],
        acceleration_1.nodes["Reroute"].inputs[0]
    )
    # set_position.Geometry -> reroute_007.Input
    acceleration_1.links.new(
        acceleration_1.nodes["Set Position"].outputs[0],
        acceleration_1.nodes["Reroute.007"].inputs[0]
    )
    # value.Value -> reroute_001.Input
    acceleration_1.links.new(
        acceleration_1.nodes["Value"].outputs[0],
        acceleration_1.nodes["Reroute.001"].inputs[0]
    )
    # reroute_001.Output -> reroute_002.Input
    acceleration_1.links.new(
        acceleration_1.nodes["Reroute.001"].outputs[0],
        acceleration_1.nodes["Reroute.002"].inputs[0]
    )
    # reroute_008.Output -> reroute_009.Input
    acceleration_1.links.new(
        acceleration_1.nodes["Reroute.008"].outputs[0],
        acceleration_1.nodes["Reroute.009"].inputs[0]
    )
    # reroute_003.Output -> reroute_004.Input
    acceleration_1.links.new(
        acceleration_1.nodes["Reroute.003"].outputs[0],
        acceleration_1.nodes["Reroute.004"].inputs[0]
    )
    # reroute_005.Output -> reroute_006.Input
    acceleration_1.links.new(
        acceleration_1.nodes["Reroute.005"].outputs[0],
        acceleration_1.nodes["Reroute.006"].inputs[0]
    )
    # reroute.Output -> align_rotation_to_vector.Vector
    acceleration_1.links.new(
        acceleration_1.nodes["Reroute"].outputs[0],
        acceleration_1.nodes["Align Rotation to Vector"].inputs[2]
    )
    # reroute_007.Output -> realize_instances.Geometry
    acceleration_1.links.new(
        acceleration_1.nodes["Reroute.007"].outputs[0],
        acceleration_1.nodes["Realize Instances"].inputs[0]
    )
    # reroute_002.Output -> cone.Depth
    acceleration_1.links.new(
        acceleration_1.nodes["Reroute.002"].outputs[0],
        acceleration_1.nodes["Cone"].inputs[5]
    )
    # reroute_002.Output -> vector_math_003.Scale
    acceleration_1.links.new(
        acceleration_1.nodes["Reroute.002"].outputs[0],
        acceleration_1.nodes["Vector Math.003"].inputs[3]
    )
    # reroute_002.Output -> math_001.Value
    acceleration_1.links.new(
        acceleration_1.nodes["Reroute.002"].outputs[0],
        acceleration_1.nodes["Math.001"].inputs[0]
    )
    # reroute_004.Output -> transform_geometry.Translation
    acceleration_1.links.new(
        acceleration_1.nodes["Reroute.004"].outputs[0],
        acceleration_1.nodes["Transform Geometry"].inputs[2]
    )
    # reroute_006.Output -> mesh_to_points.Selection
    acceleration_1.links.new(
        acceleration_1.nodes["Reroute.006"].outputs[0],
        acceleration_1.nodes["Mesh to Points"].inputs[1]
    )
    # reroute_009.Output -> curve_line.Start
    acceleration_1.links.new(
        acceleration_1.nodes["Reroute.009"].outputs[0],
        acceleration_1.nodes["Curve Line"].inputs[0]
    )
    # realize_instances.Geometry -> join_geometry.Geometry
    acceleration_1.links.new(
        acceleration_1.nodes["Realize Instances"].outputs[0],
        acceleration_1.nodes["Join Geometry"].inputs[0]
    )

    return acceleration_1


def geometry_nodes_1_node_group(node_tree_names: dict[typing.Callable, str],
                                  *,
                                  trajectory_obj=None,
                                  traj_radius_default: float = 0.015,
                                  axis_length: float = AXIS_LENGTH_DEFAULT,
                                  scale_v_default: float = 1.0,
                                  scale_a_default: float = 1.0):
    """Initialize Geometry Nodes node group.

    Args:
        node_tree_names: dict prérempli pour les sub-groups
            Position / Vitesse / Acceleration.
        trajectory_obj: objet Curve POLY échantillonnant r(t).
        traj_radius_default: rayon initial du tube-trajectoire.
        axis_length: longueur des arêtes du trièdre R (statique).
        scale_v_default, scale_a_default: valeurs initiales des
            échelles de flèches v et a, exposées comme sockets Float
            modifiables en live.
    """
    geometry_nodes_1 = bpy.data.node_groups.new(type='GeometryNodeTree', name="Geometry Nodes")

    geometry_nodes_1.color_tag = 'NONE'
    geometry_nodes_1.description = ""
    geometry_nodes_1.default_group_node_width = 140
    geometry_nodes_1.is_modifier = True
    geometry_nodes_1.show_modifier_manage_panel = True

    # geometry_nodes_1 interface

    # Socket Geometry
    geometry_socket = geometry_nodes_1.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'
    geometry_socket.default_input = 'VALUE'
    geometry_socket.structure_type = 'AUTO'

    # Socket Geometry
    geometry_socket_1 = geometry_nodes_1.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    geometry_socket_1.attribute_domain = 'POINT'
    geometry_socket_1.default_input = 'VALUE'
    geometry_socket_1.structure_type = 'AUTO'

    # Sockets booléens d'affichage (exposés sur le modifier)
    show_pos_socket = geometry_nodes_1.interface.new_socket(
        name=SHOW_POSITION_SOCKET, in_out='INPUT', socket_type='NodeSocketBool')
    show_pos_socket.default_value = True
    show_pos_socket.description = "Afficher la flèche de position r(t)"

    show_vit_socket = geometry_nodes_1.interface.new_socket(
        name=SHOW_VITESSE_SOCKET, in_out='INPUT', socket_type='NodeSocketBool')
    show_vit_socket.default_value = True
    show_vit_socket.description = "Afficher la flèche de vitesse v(t)"

    show_acc_socket = geometry_nodes_1.interface.new_socket(
        name=SHOW_ACCELERATION_SOCKET, in_out='INPUT', socket_type='NodeSocketBool')
    show_acc_socket.default_value = True
    show_acc_socket.description = "Afficher la flèche d'accélération a(t)"

    # Trajectoire OM : cachée par défaut (peut encombrer la scène avec
    # les trois flèches déjà visibles).
    show_traj_socket = geometry_nodes_1.interface.new_socket(
        name=SHOW_TRAJECTORY_SOCKET, in_out='INPUT', socket_type='NodeSocketBool')
    show_traj_socket.default_value = False
    show_traj_socket.description = (
        "Afficher la trajectoire OM, échantillonnée au build sur "
        "[t_start, t_start + t_duration]"
    )

    # Rayon du tube-trajectoire : socket Float exposé sur le modifier
    # pour que l'utilisateur puisse ajuster l'épaisseur sans rebuild.
    traj_radius_socket = geometry_nodes_1.interface.new_socket(
        name=TRAJ_RADIUS_SOCKET, in_out='INPUT', socket_type='NodeSocketFloat')
    traj_radius_socket.default_value = float(traj_radius_default)
    traj_radius_socket.min_value = 0.0
    traj_radius_socket.max_value = 10.0
    traj_radius_socket.description = (
        "Rayon du tube de la trajectoire OM (modifiable en live)"
    )

    # Trièdre du repère R : un seul toggle pour les trois axes ê_x, ê_y,
    # ê_z. Affiché par défaut — c'est utile à voir dès le premier Build
    # pour donner un repère visuel à r(t).
    show_frame_socket = geometry_nodes_1.interface.new_socket(
        name=SHOW_FRAME_SOCKET, in_out='INPUT', socket_type='NodeSocketBool')
    show_frame_socket.default_value = True
    show_frame_socket.description = (
        "Afficher le trièdre du repère R (axes ê_x, ê_y, ê_z) à l'origine"
    )

    # Échelles v et a : modifiables en live via les drivers. Lus par
    # variable de driver pointant sur ces sockets (cf. drivers.py).
    scale_v_socket = geometry_nodes_1.interface.new_socket(
        name=SCALE_V_SOCKET, in_out='INPUT', socket_type='NodeSocketFloat')
    scale_v_socket.default_value = float(scale_v_default)
    scale_v_socket.min_value = 0.0
    scale_v_socket.max_value = 100.0
    scale_v_socket.description = (
        "Facteur d'échelle de la flèche vitesse, modifiable en live "
        "(1.0 = unitaire : 1 m affiché ↔ 1 m/s)"
    )
    scale_a_socket = geometry_nodes_1.interface.new_socket(
        name=SCALE_A_SOCKET, in_out='INPUT', socket_type='NodeSocketFloat')
    scale_a_socket.default_value = float(scale_a_default)
    scale_a_socket.min_value = 0.0
    scale_a_socket.max_value = 100.0
    scale_a_socket.description = (
        "Facteur d'échelle de la flèche accélération, modifiable en live "
        "(1.0 = unitaire : 1 m affiché ↔ 1 m/s²)"
    )

    # Initialize geometry_nodes_1 nodes

    # Node Group Output
    group_output = geometry_nodes_1.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    # Node Group Input — expose les booléens d'affichage
    group_input = geometry_nodes_1.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"

    # Node Group (Position)
    group = geometry_nodes_1.nodes.new("GeometryNodeGroup")
    group.name = "Group"
    group.node_tree = bpy.data.node_groups[node_tree_names[position_1_node_group]]
    # Socket_2
    group.inputs[0].default_value = (0.0, 0.0, 0.0)
    # Socket_1
    group.inputs[1].default_value = (1.0, 0.0, 0.0)

    # Node Group.001 (Vitesse)
    group_001 = geometry_nodes_1.nodes.new("GeometryNodeGroup")
    group_001.name = "Group.001"
    group_001.node_tree = bpy.data.node_groups[node_tree_names[vitesse_1_node_group]]
    # Socket_2
    group_001.inputs[0].default_value = (0.0, 0.0, 0.0)
    # Socket_1
    group_001.inputs[1].default_value = (0.0, 1.5707963705062866, 0.0)

    # Node Group.002 (Acceleration)
    group_002 = geometry_nodes_1.nodes.new("GeometryNodeGroup")
    group_002.name = "Group.002"
    group_002.node_tree = bpy.data.node_groups[node_tree_names[acceleration_1_node_group]]
    # Socket_2
    group_002.inputs[0].default_value = (0.0, 0.0, 0.0)
    # Socket_1
    group_002.inputs[1].default_value = (-2.4674010276794434, 0.0, 0.0)

    # Node Join Geometry
    join_geometry = geometry_nodes_1.nodes.new("GeometryNodeJoinGeometry")
    join_geometry.name = "Join Geometry"

    # ── Matériaux émissifs (couleurs distinctes par flèche) ────────────
    # Position : blanc-jaune ; Vitesse : vert ; Accélération : rouge.
    from . import materials as _materials
    _materials.ensure_material("VV_position")
    _materials.ensure_material("VV_velocity")
    _materials.ensure_material("VV_acceleration")

    setmat_pos = geometry_nodes_1.nodes.new("GeometryNodeSetMaterial")
    setmat_pos.name = "SetMat Position"
    setmat_pos.inputs["Material"].default_value = bpy.data.materials["VV_position"]

    setmat_vit = geometry_nodes_1.nodes.new("GeometryNodeSetMaterial")
    setmat_vit.name = "SetMat Vitesse"
    setmat_vit.inputs["Material"].default_value = bpy.data.materials["VV_velocity"]

    setmat_acc = geometry_nodes_1.nodes.new("GeometryNodeSetMaterial")
    setmat_acc.name = "SetMat Acceleration"
    setmat_acc.inputs["Material"].default_value = bpy.data.materials["VV_acceleration"]

    # Switch nodes — pour chaque vecteur, on route soit la géométrie de la
    # flèche (Switch=True), soit rien (Switch=False, géométrie vide) vers
    # Join Geometry. Le booléen est piloté par le Group Input correspondant.
    switch_pos = geometry_nodes_1.nodes.new("GeometryNodeSwitch")
    switch_pos.name = "Switch Position"
    switch_pos.input_type = 'GEOMETRY'

    switch_vit = geometry_nodes_1.nodes.new("GeometryNodeSwitch")
    switch_vit.name = "Switch Vitesse"
    switch_vit.input_type = 'GEOMETRY'

    switch_acc = geometry_nodes_1.nodes.new("GeometryNodeSwitch")
    switch_acc.name = "Switch Acceleration"
    switch_acc.input_type = 'GEOMETRY'

    # ── Chaîne trajectoire OM ──────────────────────────────────────────
    # Object Info → Curve to Mesh → Set Material → Switch → Join.
    # Le profil du tube est un Curve Circle (8 segments, économique) dont
    # le rayon est piloté par le socket Float exposé du wrapper, ce qui
    # permet de modifier l'épaisseur en live sans rebuild.
    _materials.ensure_material("VV_traj_OM_simple")

    profile_circle = geometry_nodes_1.nodes.new("GeometryNodeCurvePrimitiveCircle")
    profile_circle.name = "Profile Circle (trajectory)"
    profile_circle.mode = 'RADIUS'
    profile_circle.inputs["Resolution"].default_value = 8

    objinfo_traj = geometry_nodes_1.nodes.new("GeometryNodeObjectInfo")
    objinfo_traj.name = "ObjInfo Trajectory"
    objinfo_traj.transform_space = 'ORIGINAL'
    if trajectory_obj is not None:
        objinfo_traj.inputs["Object"].default_value = trajectory_obj

    curvetomesh_traj = geometry_nodes_1.nodes.new("GeometryNodeCurveToMesh")
    curvetomesh_traj.name = "CurveToMesh Trajectory"

    setmat_traj = geometry_nodes_1.nodes.new("GeometryNodeSetMaterial")
    setmat_traj.name = "SetMat Trajectory"
    setmat_traj.inputs["Material"].default_value = bpy.data.materials["VV_traj_OM_simple"]

    switch_traj = geometry_nodes_1.nodes.new("GeometryNodeSwitch")
    switch_traj.name = "Switch Trajectory"
    switch_traj.input_type = 'GEOMETRY'

    # ── Trièdre du repère R ────────────────────────────────────────────
    # Trois flèches statiques (longueur = axis_length) ancrées à l'origine,
    # avec leurs matériaux dédiés (RGB pur saturé). Toutes pilotées par
    # le même booléen Switch — un toggle global pour le trièdre R.
    _materials.ensure_material("VV_R_x")
    _materials.ensure_material("VV_R_y")
    _materials.ensure_material("VV_R_z")

    R_AXIS_TIPS = {
        "R_x": (axis_length, 0.0, 0.0),
        "R_y": (0.0, axis_length, 0.0),
        "R_z": (0.0, 0.0, axis_length),
    }
    R_AXIS_MATS = {
        "R_x": "VV_R_x",
        "R_y": "VV_R_y",
        "R_z": "VV_R_z",
    }

    pos_subgroup_name = node_tree_names[position_1_node_group]
    for axis_name in ("R_x", "R_y", "R_z"):
        # Sous-groupe Position avec extrémité fixée
        arrow = geometry_nodes_1.nodes.new("GeometryNodeGroup")
        arrow.name = f"Group {axis_name}"
        arrow.node_tree = bpy.data.node_groups[pos_subgroup_name]
        arrow.inputs[0].default_value = (0.0, 0.0, 0.0)
        arrow.inputs[1].default_value = R_AXIS_TIPS[axis_name]

        # Set Material dédié
        sm = geometry_nodes_1.nodes.new("GeometryNodeSetMaterial")
        sm.name = f"SetMat {axis_name}"
        sm.inputs["Material"].default_value = bpy.data.materials[R_AXIS_MATS[axis_name]]

        # Switch piloté par show_frame_socket (output[6]) — même booléen
        # pour les trois axes, donc le trièdre s'affiche en bloc.
        sw = geometry_nodes_1.nodes.new("GeometryNodeSwitch")
        sw.name = f"Switch {axis_name}"
        sw.input_type = 'GEOMETRY'

    # Set locations
    geometry_nodes_1.nodes["Group Input"].location   = (-700.0, -100.0)
    geometry_nodes_1.nodes["Group"].location         = (-367.5355529785156, 231.15252685546875)
    geometry_nodes_1.nodes["Group.001"].location     = (-374.5213317871094, -75.69499969482422)
    geometry_nodes_1.nodes["Group.002"].location     = (-350.87677001953125, -434.520751953125)
    geometry_nodes_1.nodes["SetMat Position"].location     = (-100.0, 230.0)
    geometry_nodes_1.nodes["SetMat Vitesse"].location      = (-100.0, -75.0)
    geometry_nodes_1.nodes["SetMat Acceleration"].location = (-100.0, -434.0)
    geometry_nodes_1.nodes["Switch Position"].location     = (180.0, 230.0)
    geometry_nodes_1.nodes["Switch Vitesse"].location      = (180.0, -75.0)
    geometry_nodes_1.nodes["Switch Acceleration"].location = (180.0, -434.0)
    # Chaîne trajectoire (en bas)
    geometry_nodes_1.nodes["Profile Circle (trajectory)"].location = (-700.0, -750.0)
    geometry_nodes_1.nodes["ObjInfo Trajectory"].location = (-450.0, -670.0)
    geometry_nodes_1.nodes["CurveToMesh Trajectory"].location = (-200.0, -670.0)
    geometry_nodes_1.nodes["SetMat Trajectory"].location = (-100.0, -740.0)
    geometry_nodes_1.nodes["Switch Trajectory"].location = (180.0, -740.0)
    # Trièdre R (encore en dessous)
    geometry_nodes_1.nodes["Group R_x"].location  = (-370.0, -1050.0)
    geometry_nodes_1.nodes["Group R_y"].location  = (-370.0, -1230.0)
    geometry_nodes_1.nodes["Group R_z"].location  = (-370.0, -1410.0)
    geometry_nodes_1.nodes["SetMat R_x"].location = (-100.0, -1050.0)
    geometry_nodes_1.nodes["SetMat R_y"].location = (-100.0, -1230.0)
    geometry_nodes_1.nodes["SetMat R_z"].location = (-100.0, -1410.0)
    geometry_nodes_1.nodes["Switch R_x"].location = (180.0, -1050.0)
    geometry_nodes_1.nodes["Switch R_y"].location = (180.0, -1230.0)
    geometry_nodes_1.nodes["Switch R_z"].location = (180.0, -1410.0)
    geometry_nodes_1.nodes["Join Geometry"].location = (601.1710205078125, -11.675125122070312)
    geometry_nodes_1.nodes["Group Output"].location  = (790.26513671875, -13.80057144165039)

    # Set dimensions
    for node_name in ("Group Output", "Group Input", "Join Geometry",
                      "Switch Position", "Switch Vitesse", "Switch Acceleration",
                      "SetMat Position", "SetMat Vitesse", "SetMat Acceleration",
                      "Profile Circle (trajectory)", "ObjInfo Trajectory",
                      "CurveToMesh Trajectory", "SetMat Trajectory",
                      "Switch Trajectory",
                      "SetMat R_x", "SetMat R_y", "SetMat R_z",
                      "Switch R_x", "Switch R_y", "Switch R_z"):
        geometry_nodes_1.nodes[node_name].width  = 140.0
        geometry_nodes_1.nodes[node_name].height = 100.0

    for node_name in ("Group", "Group.001", "Group.002",
                      "Group R_x", "Group R_y", "Group R_z"):
        geometry_nodes_1.nodes[node_name].width  = 246.7626953125
        geometry_nodes_1.nodes[node_name].height = 100.0


    # Initialize geometry_nodes_1 links
    #
    # Convention pour GeometryNodeSwitch (input_type='GEOMETRY'), Blender 4.4+ :
    #   inputs[0]  = "Switch"  (NodeSocketBool)
    #   inputs[1]  = "False"   (géométrie renvoyée si Switch=False)
    #   inputs[2]  = "True"    (géométrie renvoyée si Switch=True)
    #   outputs[0] = "Output"  (géométrie résultante)
    #
    # Sorties du Group Input dans l'ordre des sockets d'interface :
    #   [0] Geometry (entrée),
    #   [1] Afficher position,
    #   [2] Afficher vitesse,
    #   [3] Afficher accélération,
    #   [4] Afficher trajectoire OM,
    #   [5] Rayon de la trajectoire (Float),
    #   [6] Afficher repère R,
    #   [7] Échelle v (Float, lue par drivers),
    #   [8] Échelle a (Float, lue par drivers)

    # Sous-groupes -> Set Material correspondant
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["Group"].outputs[0],
        geometry_nodes_1.nodes["SetMat Position"].inputs[0]
    )
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["Group.001"].outputs[0],
        geometry_nodes_1.nodes["SetMat Vitesse"].inputs[0]
    )
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["Group.002"].outputs[0],
        geometry_nodes_1.nodes["SetMat Acceleration"].inputs[0]
    )

    # Set Material -> entrée True du Switch correspondant
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["SetMat Position"].outputs[0],
        geometry_nodes_1.nodes["Switch Position"].inputs[2]
    )
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["SetMat Vitesse"].outputs[0],
        geometry_nodes_1.nodes["Switch Vitesse"].inputs[2]
    )
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["SetMat Acceleration"].outputs[0],
        geometry_nodes_1.nodes["Switch Acceleration"].inputs[2]
    )

    # Booléens du Group Input -> entrée Switch (bool) de chaque Switch
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["Group Input"].outputs[1],
        geometry_nodes_1.nodes["Switch Position"].inputs[0]
    )
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["Group Input"].outputs[2],
        geometry_nodes_1.nodes["Switch Vitesse"].inputs[0]
    )
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["Group Input"].outputs[3],
        geometry_nodes_1.nodes["Switch Acceleration"].inputs[0]
    )

    # Sortie de chaque Switch -> Join Geometry
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["Switch Position"].outputs[0],
        geometry_nodes_1.nodes["Join Geometry"].inputs[0]
    )
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["Switch Vitesse"].outputs[0],
        geometry_nodes_1.nodes["Join Geometry"].inputs[0]
    )
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["Switch Acceleration"].outputs[0],
        geometry_nodes_1.nodes["Join Geometry"].inputs[0]
    )

    # ── Chaîne trajectoire ─────────────────────────────────────────────
    # Group Input[5] (Float Rayon) -> Profile Circle.Radius
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["Group Input"].outputs[5],
        geometry_nodes_1.nodes["Profile Circle (trajectory)"].inputs["Radius"]
    )
    # Object Info -> Curve to Mesh.Curve
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["ObjInfo Trajectory"].outputs["Geometry"],
        geometry_nodes_1.nodes["CurveToMesh Trajectory"].inputs["Curve"]
    )
    # Profile Circle -> Curve to Mesh.Profile Curve
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["Profile Circle (trajectory)"].outputs["Curve"],
        geometry_nodes_1.nodes["CurveToMesh Trajectory"].inputs["Profile Curve"]
    )
    # Curve to Mesh -> SetMat Trajectory -> Switch Trajectory.True
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["CurveToMesh Trajectory"].outputs[0],
        geometry_nodes_1.nodes["SetMat Trajectory"].inputs[0]
    )
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["SetMat Trajectory"].outputs[0],
        geometry_nodes_1.nodes["Switch Trajectory"].inputs[2]
    )
    # Group Input[4] (Bool Afficher trajectoire) -> Switch Trajectory.Switch
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["Group Input"].outputs[4],
        geometry_nodes_1.nodes["Switch Trajectory"].inputs[0]
    )
    # Switch Trajectory -> Join Geometry
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["Switch Trajectory"].outputs[0],
        geometry_nodes_1.nodes["Join Geometry"].inputs[0]
    )

    # ── Trièdre R : Group → SetMat → Switch (booléen output[6]) → Join ─
    for axis_name in ("R_x", "R_y", "R_z"):
        # Group → SetMat
        geometry_nodes_1.links.new(
            geometry_nodes_1.nodes[f"Group {axis_name}"].outputs[0],
            geometry_nodes_1.nodes[f"SetMat {axis_name}"].inputs[0]
        )
        # SetMat → Switch.True
        geometry_nodes_1.links.new(
            geometry_nodes_1.nodes[f"SetMat {axis_name}"].outputs[0],
            geometry_nodes_1.nodes[f"Switch {axis_name}"].inputs[2]
        )
        # show_frame_socket (Group Input output[6]) → Switch.Switch
        geometry_nodes_1.links.new(
            geometry_nodes_1.nodes["Group Input"].outputs[6],
            geometry_nodes_1.nodes[f"Switch {axis_name}"].inputs[0]
        )
        # Switch → Join Geometry
        geometry_nodes_1.links.new(
            geometry_nodes_1.nodes[f"Switch {axis_name}"].outputs[0],
            geometry_nodes_1.nodes["Join Geometry"].inputs[0]
        )

    # Join Geometry -> Group Output
    geometry_nodes_1.links.new(
        geometry_nodes_1.nodes["Join Geometry"].outputs[0],
        geometry_nodes_1.nodes["Group Output"].inputs[0]
    )

    return geometry_nodes_1

