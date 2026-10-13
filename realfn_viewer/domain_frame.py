"""
Domain frame and graduated axes for the 3D field visualisations.

Two pedagogical aids shared by the scalar-field-3D and
vector-field-3D trees:

* :func:`build_domain_frame` — the 12 edges of the domain box
  [x_min, x_max] × [y_min, y_max] × [z_min, z_max] rendered as thin
  tubes. Gives the sampled region a visible boundary so students see
  *where* the field is being probed.

* :func:`build_graduated_axes` — numeric graduations along three box
  edges (one per coordinate), reusing the :mod:`label_number` group:
  the x graduations run along the (y_min, z_min) edge, y along
  (x_min, z_min), z along the vertical (x_min, y_min) edge. Each
  graduation displays its own coordinate value, with one tick per
  grid plane (driven by the Resolution X/Y/Z sockets), so the numbers
  line up exactly with the sample positions.

Construction notes
------------------
The frame is a unit cube scaled/translated by the domain sockets,
then Mesh-to-Curve → Curve-to-Mesh with a small circular profile —
the standard wireframe-tube recipe (there is no Wireframe node in
Geometry Nodes).

The axes reuse ``LabelNumber`` exactly as the field labels do: a
Mesh Line of ``Resolution`` points spanning the edge, ``Value`` =
the matching coordinate of ``Input Position`` (a field — evaluated
per point by the group's Sample-Index machinery). The z axis is
rendered with ``Face front`` enabled (upright digits — flat numbers
on a vertical edge would be seen edge-on from the usual viewpoints);
x and y stay flat, readable from the top view.
"""

from __future__ import annotations

from . import label_number


def build_domain_frame(nb, *,
                        xmin, xmax, ymin, ymax, zmin, zmax,
                        thickness_sock,
                        x=0, y=0, label="domain frame"):
    """Build the wireframe box of the domain.

    All bound arguments are sockets (or constants accepted by
    ``NodeBuilder._to_socket``). Returns the Geometry socket of the
    tube mesh.
    """
    cube = nb.add("GeometryNodeMeshCube", label=f"{label}: cube",
                   x=x, y=y)
    try:
        cube.inputs["Size"].default_value = (1.0, 1.0, 1.0)
    except (KeyError, TypeError):
        pass

    # Scale = extents, translation = centre.
    sx = nb.math("SUBTRACT", xmax, xmin, x=x, y=y - 150)
    sy = nb.math("SUBTRACT", ymax, ymin, x=x, y=y - 230)
    sz = nb.math("SUBTRACT", zmax, zmin, x=x, y=y - 310)
    scale_vec = nb.combine_xyz(sx, sy, sz, label=f"{label}: extents",
                                x=x + 180, y=y - 200)
    cx = nb.math("MULTIPLY", nb.math("ADD", xmin, xmax,
                                       x=x, y=y - 420),
                  0.5, x=x + 150, y=y - 420)
    cy = nb.math("MULTIPLY", nb.math("ADD", ymin, ymax,
                                       x=x, y=y - 500),
                  0.5, x=x + 150, y=y - 500)
    cz = nb.math("MULTIPLY", nb.math("ADD", zmin, zmax,
                                       x=x, y=y - 580),
                  0.5, x=x + 150, y=y - 580)
    centre_vec = nb.combine_xyz(cx, cy, cz, label=f"{label}: centre",
                                 x=x + 330, y=y - 500)

    tr = nb.add("GeometryNodeTransform", label=f"{label}: fit",
                 x=x + 400, y=y)
    nb.link(cube.outputs["Mesh"], tr.inputs["Geometry"])
    nb.link(centre_vec, tr.inputs["Translation"])
    nb.link(scale_vec, tr.inputs["Scale"])

    # Edges → curve → tube.
    m2c = nb.add("GeometryNodeMeshToCurve", label=f"{label}: edges",
                  x=x + 600, y=y)
    nb.link(tr.outputs["Geometry"], m2c.inputs["Mesh"])
    profile = nb.add("GeometryNodeCurvePrimitiveCircle",
                      label=f"{label}: profile",
                      x=x + 600, y=y - 200)
    profile.mode = "RADIUS"
    try:
        profile.inputs["Resolution"].default_value = 6
    except (KeyError, TypeError):
        pass
    try:
        nb.link(thickness_sock, profile.inputs["Radius"])
    except KeyError:
        pass
    c2m = nb.add("GeometryNodeCurveToMesh", label=f"{label}: tubes",
                  x=x + 800, y=y)
    nb.link(m2c.outputs["Curve"], c2m.inputs["Curve"])
    nb.link(profile.outputs["Curve"], c2m.inputs["Profile Curve"])
    return c2m.outputs["Mesh"]


def _axis(nb, *, label_ng, count_sock, start_vec, end_vec,
          coord: str, offset_vec, size_sock, decimals_sock,
          face_front: bool, x=0, y=0, label="axis"):
    """One graduated axis: a Mesh Line of ``count_sock`` points from
    ``start_vec`` to ``end_vec``, each point labelled with its
    ``coord`` ("X" | "Y" | "Z") coordinate via LabelNumber."""
    line = nb.add("GeometryNodeMeshLine", label=f"{label}: line",
                   x=x, y=y)
    try:
        line.mode = "END_POINTS"
    except (AttributeError, TypeError):
        pass
    nb.link(count_sock, line.inputs["Count"])
    try:
        nb.link(start_vec, line.inputs["Start Location"])
    except KeyError:
        nb.link(start_vec, line.inputs[2])
    try:
        nb.link(end_vec, line.inputs["End Location"])
    except KeyError:
        try:
            nb.link(end_vec, line.inputs["Offset"])
        except KeyError:
            nb.link(end_vec, line.inputs[3])

    pos = nb.add("GeometryNodeInputPosition",
                  label=f"{label}: pos", x=x, y=y - 160)
    sep = nb.add("ShaderNodeSeparateXYZ",
                  label=f"{label}: sep", x=x + 160, y=y - 160)
    nb.link(pos.outputs["Position"], sep.inputs["Vector"])

    grp = nb.add("GeometryNodeGroup", label=f"{label}: numbers",
                  x=x + 360, y=y)
    grp.node_tree = label_ng
    nb.link(line.outputs["Mesh"], grp.inputs["Points"])
    nb.link(sep.outputs[coord], grp.inputs["Value"])
    nb.link(size_sock, grp.inputs["Size"])
    nb.link(decimals_sock, grp.inputs["Decimals"])
    nb.link(offset_vec, grp.inputs["Offset"])
    try:
        grp.inputs["Face front"].default_value = bool(face_front)
    except (KeyError, TypeError):
        pass
    # Stride defaults to 1 (every tick), Max points default is far
    # above any Resolution (≤ 64) — both left at group defaults.
    return grp.outputs["Geometry"]


def build_graduated_axes(nb, *,
                          label_ng=None,
                          xmin, xmax, ymin, ymax, zmin, zmax,
                          res_x, res_y, res_z,
                          size_sock, decimals_sock,
                          x=0, y=0):
    """Build the three graduated axes along the domain box edges.

    Returns a Geometry socket with the joined numbers of the three
    axes. ``label_ng`` defaults to the shared LabelNumber group.
    """
    if label_ng is None:
        label_ng = label_number.get_label_number_node_group()

    corner = nb.combine_xyz(xmin, ymin, zmin, label="axes: origin",
                             x=x, y=y - 700)
    x_end = nb.combine_xyz(xmax, ymin, zmin, label="axes: x end",
                            x=x, y=y - 780)
    y_end = nb.combine_xyz(xmin, ymax, zmin, label="axes: y end",
                            x=x, y=y - 860)
    z_end = nb.combine_xyz(xmin, ymin, zmax, label="axes: z end",
                            x=x, y=y - 940)

    # Offsets push the numbers OUTSIDE the box, proportionally to the
    # glyph size so they scale with the user's setting.
    two_s = nb.math("MULTIPLY", size_sock, 2.0, x=x, y=y - 1020,
                     label="2·size")
    neg_two_s = nb.math("MULTIPLY", two_s, -1.0, x=x + 150, y=y - 1020)
    s15 = nb.math("MULTIPLY", size_sock, -1.5, x=x, y=y - 1100,
                   label="−1.5·size")
    off_x = nb.combine_xyz(0.0, neg_two_s, 0.0,
                            label="x ticks offset", x=x + 300, y=y - 1020)
    off_y = nb.combine_xyz(neg_two_s, 0.0, 0.0,
                            label="y ticks offset", x=x + 300, y=y - 1100)
    off_z = nb.combine_xyz(s15, s15, 0.0,
                            label="z ticks offset", x=x + 300, y=y - 1180)

    gx = _axis(nb, label_ng=label_ng, count_sock=res_x,
               start_vec=corner, end_vec=x_end, coord="X",
               offset_vec=off_x, size_sock=size_sock,
               decimals_sock=decimals_sock, face_front=False,
               x=x + 500, y=y, label="axe x")
    gy = _axis(nb, label_ng=label_ng, count_sock=res_y,
               start_vec=corner, end_vec=y_end, coord="Y",
               offset_vec=off_y, size_sock=size_sock,
               decimals_sock=decimals_sock, face_front=False,
               x=x + 500, y=y - 350, label="axe y")
    gz = _axis(nb, label_ng=label_ng, count_sock=res_z,
               start_vec=corner, end_vec=z_end, coord="Z",
               offset_vec=off_z, size_sock=size_sock,
               decimals_sock=decimals_sock, face_front=True,
               x=x + 500, y=y - 700, label="axe z")

    join = nb.add("GeometryNodeJoinGeometry", label="axes: join",
                   x=x + 1100, y=y - 350)
    nb.link(gx, join.inputs["Geometry"])
    nb.link(gy, join.inputs["Geometry"])
    nb.link(gz, join.inputs["Geometry"])
    return join.outputs["Geometry"]
