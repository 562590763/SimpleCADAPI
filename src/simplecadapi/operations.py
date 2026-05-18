"""SimpleCAD API operation implementations based on the README design."""

from typing import List, Tuple, Union, Optional, Sequence, cast, Dict, Any
import math
import numpy as np
import cadquery as cq
from cadquery import Vector
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing  # type: ignore[reportAttributeAccessIssue]
from OCP.TopAbs import TopAbs_SHELL  # type: ignore[reportAttributeAccessIssue]
from OCP.TopExp import TopExp_Explorer  # type: ignore[reportAttributeAccessIssue]

from .feature_history import FeatureType
from .core import (
    Vertex,
    Edge,
    Wire,
    Face,
    Solid,
    AnyShape,
    get_current_cs,
)
from .field import (
    ScalarField,
    bounds_rbbox,
    eval_rarray,
    make_box_rscalarfield,
    intersect_rscalarfield,
)

from cadquery.occ_impl.shapes import cut, intersect, revolve


_DEFAULT_UNION_GLUE = True
_DEFAULT_UNION_TOL_FACTOR = 1e-7
_DEFAULT_UNION_TOL_MIN = 1e-7
_DEFAULT_UNION_TOL_MAX = 1e-5


def _resolve_union_tol(
    solids: Sequence[Solid], tol: Optional[float]
) -> Optional[float]:
    """Resolve a conservative fuzzy tolerance for boolean union.

    When callers do not specify `tol`, use a scale-aware value that is large enough
    to absorb small numerical noise but not aggressive enough to close meaningful
    modeling gaps by default.
    """

    if tol is not None:
        return tol

    bbox_min = np.array([np.inf, np.inf, np.inf], dtype=float)
    bbox_max = np.array([-np.inf, -np.inf, -np.inf], dtype=float)

    for solid in solids:
        bb = solid.cq_solid.BoundingBox()
        bbox_min = np.minimum(bbox_min, np.array([bb.xmin, bb.ymin, bb.zmin]))
        bbox_max = np.maximum(bbox_max, np.array([bb.xmax, bb.ymax, bb.zmax]))

    span = float(np.linalg.norm(bbox_max - bbox_min))
    if not np.isfinite(span) or span <= 0:
        return _DEFAULT_UNION_TOL_MIN

    return min(
        max(span * _DEFAULT_UNION_TOL_FACTOR, _DEFAULT_UNION_TOL_MIN),
        _DEFAULT_UNION_TOL_MAX,
    )


def _warn_if_union_results_remain_separated(
    results: Sequence[Solid], tol: Optional[float]
) -> None:
    """Print a clear stdout warning when union results remain separated beyond tol."""

    if len(results) < 2:
        return

    effective_tol = float(tol or 0.0)
    nearest_gap_above_tol: Optional[float] = None

    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            gap = float(results[i].cq_solid.distance(results[j].cq_solid))
            if gap > effective_tol:
                if nearest_gap_above_tol is None or gap < nearest_gap_above_tol:
                    nearest_gap_above_tol = gap

    if nearest_gap_above_tol is None:
        return

    if len(results) == 2:
        print(
            "[WARNING] union_rsolidlist returned 2 separated solids: the two objects do not touch, "
            f"and the gap between them is about {nearest_gap_above_tol:.6g}, which exceeds tol={effective_tol:.6g}. "
            "Please check the relationship between the two objects and decide whether to adjust them so they connect, "
            "or accept them as two separate solids."
        )
        return

    print(
        f"[WARNING] union_rsolidlist returned {len(results)} separated solids: "
        "at least one pair of objects does not touch, "
        f"and the smallest detected separation gap is about {nearest_gap_above_tol:.6g}, which exceeds tol={effective_tol:.6g}. "
        "Please check the relationship between these objects and decide whether to adjust them so they connect, "
        "or accept them as separate solids."
    )


# =============================================================================
# 基础图形创建函数
# =============================================================================


def make_point_rvertex(x: float, y: float, z: float) -> Vertex:
    """Create a point in 3D space and return it as a vertex."""
    try:
        cs = get_current_cs()
        global_point = cs.transform_point(np.array([x, y, z]))
        cq_vertex = cq.Vertex.makeVertex(*global_point)
        vertex = Vertex(cq_vertex)
        _record_profile_feature(vertex, "point", {"x": x, "y": y, "z": z})
        return vertex
    except Exception as e:
        raise ValueError(f"创建点失败: {e}. 请检查坐标值是否有效。")


def make_line_redge(
    start: Tuple[float, float, float], end: Tuple[float, float, float]
) -> Edge:
    """Create a straight edge between two points."""
    try:
        cs = get_current_cs()
        start_global = cs.transform_point(np.array(start))
        end_global = cs.transform_point(np.array(end))

        start_vec = Vector(*start_global)
        end_vec = Vector(*end_global)

        cq_edge = cq.Edge.makeLine(start_vec, end_vec)
        edge = Edge(cq_edge)
        _record_profile_feature(edge, "line", {"start": start, "end": end})
        return edge
    except Exception as e:
        raise ValueError(f"创建线段失败: {e}. 请检查起始点和结束点坐标是否有效。")


def make_segment_redge(
    start: Tuple[float, float, float], end: Tuple[float, float, float]
) -> Edge:
    """Create a straight segment edge."""
    try:
        cs = get_current_cs()
        start_global = cs.transform_point(np.array(start))
        end_global = cs.transform_point(np.array(end))

        start_vec = Vector(*start_global)
        end_vec = Vector(*end_global)

        cq_edge = cq.Edge.makeLine(start_vec, end_vec)
        edge = Edge(cq_edge)
        _record_profile_feature(edge, "segment", {"start": start, "end": end})
        return edge
    except Exception as e:
        raise ValueError(f"创建线段边失败: {e}. 请检查起点和终点坐标是否有效。")


def make_segment_rwire(
    start: Tuple[float, float, float], end: Tuple[float, float, float]
) -> Wire:
    """Create a wire containing a single straight segment."""
    try:
        cs = get_current_cs()
        start_global = cs.transform_point(np.array(start))
        end_global = cs.transform_point(np.array(end))

        start_vec = Vector(*start_global)
        end_vec = Vector(*end_global)

        cq_edge = cq.Edge.makeLine(start_vec, end_vec)
        cq_wire = cq.Wire.assembleEdges([cq_edge])
        wire = Wire(cq_wire)
        _record_profile_feature(wire, "segment", {"start": start, "end": end})
        return wire
    except Exception as e:
        raise ValueError(f"创建线段线框失败: {e}")


def make_circle_redge(
    center: Tuple[float, float, float],
    radius: float,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Edge:
    """Create a circular edge."""
    try:
        if radius <= 0:
            raise ValueError("半径必须大于0")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))
        normal_global = cs.transform_point(np.array(normal)) - cs.origin

        center_vec = Vector(*center_global)
        normal_vec = Vector(*normal_global)

        cq_edge = cq.Edge.makeCircle(radius, center_vec, normal_vec)
        edge = Edge(cq_edge)
        _record_profile_feature(
            edge,
            "circle",
            {"center": center, "radius": radius, "normal": normal},
        )
        return edge
    except Exception as e:
        raise ValueError(f"创建圆失败: {e}. 请检查圆心坐标、半径和法向量是否有效。")


def make_circle_rwire(
    center: Tuple[float, float, float],
    radius: float,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Wire:
    """Create a circular wire."""
    try:
        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))
        normal_global = cs.transform_point(np.array(normal)) - cs.origin

        center_vec = Vector(*center_global)
        normal_vec = Vector(*normal_global)

        cq_edge = cq.Edge.makeCircle(radius, center_vec, normal_vec)
        cq_wire = cq.Wire.assembleEdges([cq_edge])
        wire = Wire(cq_wire)
        _record_profile_feature(
            wire,
            "circle",
            {"center": center, "radius": radius, "normal": normal},
        )
        return wire
    except Exception as e:
        raise ValueError(f"创建圆线失败: {e}")


def make_circle_rface(
    center: Tuple[float, float, float],
    radius: float,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Face:
    """Create a circular face."""
    try:
        if radius <= 0:
            raise ValueError("半径必须大于0")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))
        normal_global = cs.transform_point(np.array(normal)) - cs.origin

        center_vec = Vector(*center_global)
        normal_vec = Vector(*normal_global)

        cq_edge = cq.Edge.makeCircle(radius, center_vec, normal_vec)
        cq_wire = cq.Wire.assembleEdges([cq_edge])
        cq_face = cq.Face.makeFromWires(cq_wire)
        face = Face(cq_face)
        _record_profile_feature(
            face,
            "circle",
            {"center": center, "radius": radius, "normal": normal},
        )
        return face
    except Exception as e:
        raise ValueError(f"创建圆面失败: {e}")


def make_rectangle_rwire(
    width: float,
    height: float,
    center: Tuple[float, float, float] = (0, 0, 0),
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Wire:
    """Create a rectangular wire."""
    try:
        if width <= 0 or height <= 0:
            raise ValueError("宽度和高度必须大于0")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))
        normal_global = cs.transform_point(np.array(normal)) - cs.origin

        # 标准化法向量
        normal_vec = normal_global / np.linalg.norm(normal_global)

        # 创建本地坐标系
        # 如果法向量接近Z轴，使用X轴作为参考
        if abs(normal_vec[2]) > 0.9:
            ref_vec = np.array([1.0, 0.0, 0.0])
        else:
            ref_vec = np.array([0.0, 0.0, 1.0])

        # 计算本地坐标系的X和Y轴
        local_x = np.cross(normal_vec, ref_vec)
        local_x = local_x / np.linalg.norm(local_x)
        local_y = np.cross(normal_vec, local_x)
        local_y = local_y / np.linalg.norm(local_y)

        # 创建矩形的四个顶点（在本地坐标系中）
        half_w, half_h = width / 2, height / 2
        local_points = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h),
        ]

        # 转换到全局坐标系
        global_points = []
        for local_point in local_points:
            # 在本地坐标系中的点
            point_3d = (
                center_global + local_point[0] * local_x + local_point[1] * local_y
            )
            global_points.append(Vector(*point_3d))

        # 创建边
        edges = []
        for i in range(len(global_points)):
            start = global_points[i]
            end = global_points[(i + 1) % len(global_points)]
            edges.append(cq.Edge.makeLine(start, end))

        cq_wire = cq.Wire.assembleEdges(edges)
        wire = Wire(cq_wire)
        
        # Record feature history for this profile
        _record_profile_feature(
            wire, 
            "rectangle", 
            {"width": width, "height": height, "center": center, "normal": normal}
        )
        
        return wire
    except Exception as e:
        raise ValueError(f"创建矩形失败: {e}. 请检查宽度、高度和中心点坐标是否有效。")


def make_rectangle_rface(
    width: float,
    height: float,
    center: Tuple[float, float, float] = (0, 0, 0),
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Face:
    """Create a rectangular face."""
    try:
        if width <= 0 or height <= 0:
            raise ValueError("宽度和高度必须大于0")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))
        normal_global = cs.transform_point(np.array(normal)) - cs.origin

        normal_vec = normal_global / np.linalg.norm(normal_global)
        if abs(normal_vec[2]) > 0.9:
            ref_vec = np.array([1.0, 0.0, 0.0])
        else:
            ref_vec = np.array([0.0, 0.0, 1.0])

        local_x = np.cross(normal_vec, ref_vec)
        local_x = local_x / np.linalg.norm(local_x)
        local_y = np.cross(normal_vec, local_x)
        local_y = local_y / np.linalg.norm(local_y)

        half_w, half_h = width / 2, height / 2
        local_points = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h),
        ]

        global_points = []
        for local_point in local_points:
            point_3d = (
                center_global + local_point[0] * local_x + local_point[1] * local_y
            )
            global_points.append(Vector(*point_3d))

        edges = []
        for i in range(len(global_points)):
            start = global_points[i]
            end = global_points[(i + 1) % len(global_points)]
            edges.append(cq.Edge.makeLine(start, end))

        cq_wire = cq.Wire.assembleEdges(edges)
        cq_face = cq.Face.makeFromWires(cq_wire)
        face = Face(cq_face)
        _record_profile_feature(
            face,
            "rectangle",
            {"width": width, "height": height, "center": center, "normal": normal},
        )
        return face
    except Exception as e:
        raise ValueError(f"创建矩形面失败: {e}")


def make_face_from_wire_rface(
    wire: Wire, normal: Tuple[float, float, float] = (0, 0, 1)
) -> Face:
    """Create a face from a closed wire."""
    try:
        if not isinstance(wire, Wire):
            raise ValueError("输入必须是Wire类型")

        # 检查Wire是否封闭
        if not wire.is_closed():
            raise ValueError("Wire必须是封闭的才能创建面")

        # 获取当前坐标系并转换法向量
        cs = get_current_cs()
        global_normal = cs.transform_point(np.array(normal)) - cs.origin

        # 标准化法向量
        normal_vec = global_normal / np.linalg.norm(global_normal)

        # 创建面
        cq_face = cq.Face.makeFromWires(wire.cq_wire)

        # 检查面的法向量是否与期望方向一致
        # normalAt方法返回tuple (normal_vector, u_vector)
        face_normal_tuple = cq_face.normalAt(0.5, 0.5)
        face_normal = face_normal_tuple[0]  # 取第一个元素作为法向量
        face_normal_vec = np.array([face_normal.x, face_normal.y, face_normal.z])

        # 计算法向量的点积，如果小于0则需要反向
        dot_product = np.dot(normal_vec, face_normal_vec)

        if dot_product < 0:
            # 反向面（通过反向Wire的方向）
            # CADQuery的Wire没有直接的reverse方法，我们需要重新构建
            # 简单的方法是使用makeFromWires的orientation参数
            # 或者我们接受当前面的方向，添加一个警告
            print(f"警告: 创建的面的法向量与期望方向相反 (点积: {dot_product:.3f})")

        face = Face(cq_face)

        # 复制标签和元数据
        face._tags = wire._tags.copy()
        face._metadata = wire._metadata.copy()

        face = _record_generic_feature(
            output_shape=face,
            name="Face_Profile",
            operation="make_face",
            feature_type=FeatureType.SKETCH,
            inputs=[wire],
            parameters={"normal": normal},
            description="Created face from wire",
        )

        return face
    except Exception as e:
        raise ValueError(f"创建面失败: {e}. 请检查输入的线是否有效且封闭。")


_TETRAHEDRA = (
    (0, 5, 1, 6),
    (0, 1, 2, 6),
    (0, 2, 3, 6),
    (0, 3, 7, 6),
    (0, 7, 4, 6),
    (0, 4, 5, 6),
)
_TETRA_EDGES = ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3))
_TETRA_TRI_TABLE = (
    (),
    (0, 3, 2),
    (0, 1, 4),
    (1, 4, 2, 2, 4, 3),
    (1, 2, 5),
    (0, 3, 5, 0, 5, 1),
    (0, 2, 5, 0, 5, 4),
    (5, 4, 3),
    (3, 4, 5),
    (4, 5, 0, 5, 2, 0),
    (1, 5, 0, 5, 3, 0),
    (5, 2, 1),
    (3, 4, 2, 2, 4, 1),
    (4, 1, 0),
    (2, 3, 0),
    (),
)
_CUBE_OFFSETS = np.array(
    [
        [0, 0, 0],
        [1, 0, 0],
        [1, 1, 0],
        [0, 1, 0],
        [0, 0, 1],
        [1, 0, 1],
        [1, 1, 1],
        [0, 1, 1],
    ],
    dtype=float,
)


def _evaluate_field_values(
    field, xs: np.ndarray, ys: np.ndarray, zs: np.ndarray
) -> np.ndarray:
    if isinstance(field, ScalarField):
        return eval_rarray(field, xs, ys, zs)

    if callable(field):
        try:
            values = field(xs, ys, zs)
            values = np.asarray(values, dtype=float)
            if values.shape != xs.shape:
                raise ValueError("field 输出形状不匹配")
            return values
        except Exception:
            vectorized = np.vectorize(field)
            return vectorized(xs, ys, zs).astype(float)

    raise ValueError("field 必须是 ScalarField 或可调用对象")


def _marching_tetrahedra(
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    values: np.ndarray,
    iso: float,
) -> List[List[Tuple[float, float, float]]]:
    triangles: List[List[Tuple[float, float, float]]] = []
    nx, ny, nz = values.shape
    for i in range(nx - 1):
        for j in range(ny - 1):
            for k in range(nz - 1):
                cube_vals = np.array(
                    [
                        values[i + int(o[0]), j + int(o[1]), k + int(o[2])]
                        for o in _CUBE_OFFSETS
                    ],
                    dtype=float,
                )
                cube_pos = np.array(
                    [
                        (xs[i + int(o[0])], ys[j + int(o[1])], zs[k + int(o[2])])
                        for o in _CUBE_OFFSETS
                    ],
                    dtype=float,
                )
                grad = np.array(
                    [
                        cube_vals[1] - cube_vals[0],
                        cube_vals[3] - cube_vals[0],
                        cube_vals[4] - cube_vals[0],
                    ],
                    dtype=float,
                )
                eps = 1e-9 * max(1.0, float(np.max(np.abs(cube_vals))))
                for tetra in _TETRAHEDRA:
                    idx = list(tetra)
                    tpos = cube_pos[idx]
                    tval = cube_vals[idx] - iso
                    tval = np.where(np.abs(tval) < eps, -eps, tval)
                    case_index = 0
                    for v_index, v_val in enumerate(tval):
                        if v_val < 0:
                            case_index |= 1 << v_index

                    table = _TETRA_TRI_TABLE[case_index]
                    if not table:
                        continue

                    edge_points: dict[int, np.ndarray] = {}
                    for edge_index in set(table):
                        a, b = _TETRA_EDGES[edge_index]
                        v0 = tval[a]
                        v1 = tval[b]
                        t = v0 / (v0 - v1)
                        edge_points[edge_index] = tpos[a] + t * (tpos[b] - tpos[a])

                    for tri_idx in range(0, len(table), 3):
                        p0 = edge_points[table[tri_idx]]
                        p1 = edge_points[table[tri_idx + 1]]
                        p2 = edge_points[table[tri_idx + 2]]
                        tri = [p0, p1, p2]
                        if np.linalg.norm(grad) > 1e-9:
                            normal = np.cross(p1 - p0, p2 - p0)
                            if float(np.dot(normal, grad)) < 0:
                                tri = [p0, p2, p1]
                        triangles.append([tuple(p.tolist()) for p in tri])
    return triangles


def make_field_surface_rsolid(
    field,
    bounds: Optional[
        Tuple[Tuple[float, float, float], Tuple[float, float, float]]
    ] = None,
    resolution: Tuple[int, int, int] = (24, 24, 24),
    iso: float = 0.0,
    cap_bounds: bool = True,
) -> Solid:
    """Build a closed solid from a scalar field isosurface."""
    try:
        if bounds is None:
            if isinstance(field, ScalarField):
                bounds = bounds_rbbox(field)
            else:
                raise ValueError("bounds 不能为空")

        (xmin, ymin, zmin), (xmax, ymax, zmax) = bounds
        if cap_bounds:
            center = ((xmin + xmax) / 2.0, (ymin + ymax) / 2.0, (zmin + zmax) / 2.0)
            size = (xmax - xmin, ymax - ymin, zmax - zmin)
            if isinstance(field, ScalarField):
                box_field = make_box_rscalarfield(center, size)
                field = intersect_rscalarfield(field, box_field)
            else:
                field_fn = field
                cx, cy, cz = center
                sx, sy, sz = size

                def box_eval(x, y, z):
                    dx = np.abs(x - cx) - sx / 2.0
                    dy = np.abs(y - cy) - sy / 2.0
                    dz = np.abs(z - cz) - sz / 2.0
                    return np.maximum.reduce([dx, dy, dz])

                def capped(x, y, z):
                    return np.maximum(field_fn(x, y, z), box_eval(x, y, z))

                field = capped
        nx, ny, nz = resolution
        if nx < 2 or ny < 2 or nz < 2:
            raise ValueError("resolution 每个维度必须 >= 2")

        xs = np.linspace(xmin, xmax, nx)
        ys = np.linspace(ymin, ymax, ny)
        zs = np.linspace(zmin, zmax, nz)
        grid_x, grid_y, grid_z = np.meshgrid(xs, ys, zs, indexing="ij")
        values = _evaluate_field_values(field, grid_x, grid_y, grid_z)
        triangles = _marching_tetrahedra(xs, ys, zs, values, iso)
        if not triangles:
            raise ValueError("未找到等势面，请调整 bounds 或 iso")

        faces = []
        edge_count: dict[
            Tuple[Tuple[float, float, float], Tuple[float, float, float]], int
        ] = {}
        for tri in triangles:
            if len({tri[0], tri[1], tri[2]}) < 3:
                continue
            try:
                wire = cq.Wire.makePolygon(tri, close=True)
                faces.append(cq.Face.makeFromWires(wire))
            except Exception:
                continue
            pts = [tuple(np.round(p, 8)) for p in tri]
            edges = [(pts[0], pts[1]), (pts[1], pts[2]), (pts[2], pts[0])]
            for a, b in edges:
                key = (a, b) if a <= b else (b, a)
                edge_count[key] = edge_count.get(key, 0) + 1
        sewing = BRepBuilderAPI_Sewing(1e-6)
        for face in faces:
            sewing.Add(face.wrapped)
        sewing.Perform()
        sewed = sewing.SewedShape()
        shells = []
        if sewed.ShapeType() == TopAbs_SHELL:
            shells.append(sewed)
        else:
            explorer = TopExp_Explorer(sewed, TopAbs_SHELL)
            while explorer.More():
                shells.append(explorer.Current())
                explorer.Next()

        if not shells:
            raise ValueError("未能从等势面构建闭合壳体")

        def _shell_metric(shell_obj):
            cq_shell = cq.Shell(shell_obj)
            bb = cq_shell.BoundingBox()
            volume = (bb.xmax - bb.xmin) * (bb.ymax - bb.ymin) * (bb.zmax - bb.zmin)
            face_count = len(cq_shell.Faces())
            return (face_count, volume)

        shell = max(shells, key=_shell_metric)

        solid = Solid(cq.Solid.makeSolid(cq.Shell(shell)))

        shell_closed_value = bool(cq.Shell(shell).Closed())

        mesh_closed = all(count == 2 for count in edge_count.values())
        report = {
            "bounds": {"min": (xmin, ymin, zmin), "max": (xmax, ymax, zmax)},
            "resolution": resolution,
            "iso": iso,
            "field_min": float(np.min(values)),
            "field_max": float(np.max(values)),
            "triangles": len(triangles),
            "shells": len(shells),
            "mesh_closed": mesh_closed,
            "shell_closed": shell_closed_value,
            "cap_bounds": bool(cap_bounds),
        }
        solid.set_metadata("field_report", report)
        field_inputs = [field] if isinstance(field, ScalarField) else []
        solid = _record_generic_feature(
            output_shape=solid,
            name="Field_Surface",
            operation="make_field_surface",
            feature_type=FeatureType.FIELD,
            inputs=field_inputs,
            parameters={
                "bounds": bounds,
                "resolution": resolution,
                "iso": iso,
                "cap_bounds": cap_bounds,
            },
            description="Created solid from scalar field isosurface",
        )
        return solid
    except Exception as e:
        raise ValueError(f"场函数等势面构建失败: {e}.")


def make_wire_from_edges_rwire(edges: List[Edge]) -> Wire:
    """Create a wire from a list of connected edges."""
    try:
        if not edges:
            raise ValueError("边列表不能为空")

        cq_wire = cq.Wire.assembleEdges([edge.cq_edge for edge in edges])
        wire = Wire(cq_wire)
        wire = _record_generic_feature(
            output_shape=wire,
            name="Wire_Profile",
            operation="make_wire",
            feature_type=FeatureType.SKETCH,
            inputs=edges,
            parameters={"edge_count": len(edges)},
            description=f"Created wire from {len(edges)} edges",
        )
        return wire
    except Exception as e:
        raise ValueError(f"创建线失败: {e}. 请检查输入的边是否有效。")


def make_box_rsolid(
    width: float,
    height: float,
    depth: float,
    bottom_face_center: Tuple[float, float, float] = (0, 0, 0),
) -> Solid:
    """Create a box solid."""
    try:
        if width <= 0 or height <= 0 or depth <= 0:
            raise ValueError("宽度、高度和深度必须大于0")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(bottom_face_center))
        pnt = center_global - np.array([width / 2, height / 2, 0])

        # 创建立方体
        cq_solid = cq.Solid.makeBox(width, height, depth, Vector(*pnt))
        solid = Solid(cq_solid)

        # 自动标记面
        solid.auto_tag_faces("box")
        solid.apply_tag("geom.primitive.box", propagate=False)
        solid.add_tag("box")
        solid.add_tag(f"bottom center: {bottom_face_center}")
        solid.add_tag(f"size: {width}x{height}x{depth}")
        solid.set_metadata(
            "geo",
            {
                "type": "box",
                "size": {"x": width, "y": height, "z": depth},
                "bottom_face_center": bottom_face_center,
            },
        )

        # Record feature history
        _record_primitive_feature(
            solid, "box", FeatureType.PRIMITIVE,
            {"width": width, "height": height, "depth": depth, "bottom_face_center": bottom_face_center}
        )

        return solid
    except Exception as e:
        raise ValueError(f"创建立方体失败: {e}. 请检查尺寸和中心点坐标是否有效。")


def make_cylinder_rsolid(
    radius: float,
    height: float,
    bottom_face_center: Tuple[float, float, float] = (0, 0, 0),
    axis: Tuple[float, float, float] = (0, 0, 1),
) -> Solid:
    """Create a cylinder solid."""
    try:
        if radius <= 0 or height <= 0:
            raise ValueError("半径和高度必须大于0")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(bottom_face_center))
        axis_global = cs.transform_vector(np.array(axis))

        center_vec = Vector(*center_global)
        axis_vec = Vector(*axis_global)

        cq_solid = cq.Solid.makeCylinder(radius, height, center_vec, axis_vec)
        solid = Solid(cq_solid)

        # 自动标记面
        solid.auto_tag_faces("cylinder")
        solid.apply_tag("geom.primitive.cylinder", propagate=False)
        solid.add_tag("cylinder")
        solid.add_tag(f"bottom center: {bottom_face_center}")
        solid.add_tag(f"size: {radius}x{height}")
        solid.set_metadata(
            "geo",
            {
                "type": "cylinder",
                "radius": radius,
                "height": height,
                "bottom_face_center": bottom_face_center,
                "axis": axis,
            },
        )

        _record_primitive_feature(
            solid,
            "cylinder",
            FeatureType.PRIMITIVE,
            {
                "radius": radius,
                "height": height,
                "bottom_face_center": bottom_face_center,
                "axis": axis,
            },
        )

        return solid
    except Exception as e:
        raise ValueError(
            f"创建圆柱体失败: {e}. 请检查半径、高度、中心点和轴向是否有效。"
        )


def make_cone_rsolid(
    bottom_radius: float,
    height: float,
    top_radius: float = 0.0,
    bottom_face_center: Tuple[float, float, float] = (0, 0, 0),
    axis: Tuple[float, float, float] = (0, 0, 1),
) -> Solid:
    """Create a cone or truncated cone solid."""
    try:
        if bottom_radius <= 0 or height <= 0:
            raise ValueError("底面半径和高度必须大于0")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(bottom_face_center))
        axis_global = cs.transform_vector(np.array(axis))

        center_vec = Vector(*center_global)
        axis_vec = Vector(*axis_global)

        # 使用正确的makeCone参数：bottom_radius, top_radius, height, center, direction
        cq_solid = cq.Solid.makeCone(
            bottom_radius, top_radius, height, center_vec, axis_vec
        )
        solid = Solid(cq_solid)

        # 自动标记面
        solid.apply_tag("geom.primitive.cone", propagate=False)
        solid.add_tag("cone")
        solid.add_tag(f"bottom center: {bottom_face_center}")
        solid.add_tag(
            f"size: bottom_radius: {bottom_radius}, top_radius: {top_radius}, height: {height}"
        )
        solid.set_metadata(
            "geo",
            {
                "type": "cone",
                "bottom_radius": bottom_radius,
                "top_radius": top_radius,
                "height": height,
                "bottom_face_center": bottom_face_center,
                "axis": axis,
            },
        )

        _record_primitive_feature(
            solid,
            "cone",
            FeatureType.PRIMITIVE,
            {
                "bottom_radius": bottom_radius,
                "top_radius": top_radius,
                "height": height,
                "bottom_face_center": bottom_face_center,
                "axis": axis,
            },
        )

        return solid
    except Exception as e:
        raise ValueError(
            f"创建圆锥体失败: {e}. 请检查半径、高度、中心点和轴向是否有效。"
        )


def make_sphere_rsolid(
    radius: float, center: Tuple[float, float, float] = (0, 0, 0)
) -> Solid:
    """Create a sphere solid."""
    try:
        if radius <= 0:
            raise ValueError("半径必须大于0")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))

        # 使用Workplane.sphere方法创建球体，然后移动到正确位置
        if center_global[0] != 0 or center_global[1] != 0 or center_global[2] != 0:
            cq_solid = (
                cq.Workplane("XY")
                .center(center_global[0], center_global[1])
                .workplane(offset=center_global[2])
                .sphere(radius)
                .val()
            )
        else:
            cq_solid = cq.Workplane("XY").sphere(radius).val()

        solid = Solid(cq_solid)

        # 自动标记面
        solid.auto_tag_faces("sphere")
        solid.apply_tag("geom.primitive.sphere", propagate=False)
        solid.add_tag("sphere")
        solid.add_tag(f"center: {center}")
        solid.add_tag(f"radius: {radius}")
        solid.set_metadata(
            "geo",
            {
                "type": "sphere",
                "radius": radius,
                "center": center,
            },
        )

        _record_primitive_feature(
            solid,
            "sphere",
            FeatureType.PRIMITIVE,
            {"radius": radius, "center": center},
        )

        return solid
    except Exception as e:
        raise ValueError(f"创建球体失败: {e}. 请检查半径和中心点坐标是否有效。")


def make_torus_rsolid(
    radius1: float,
    radius2: float,
    center: Tuple[float, float, float] = (0, 0, 0),
    axis: Tuple[float, float, float] = (0, 0, 1),
) -> Solid:
    """Create a torus (donut) solid.

    Args:
        radius1: Major radius (distance from center to tube center)
        radius2: Minor radius (tube radius)
        center: Center point of the torus
        axis: Normal axis of the torus (default: Z-axis)

    Returns:
        A Solid representing a torus

    Raises:
        ValueError: If radius1 <= radius2 or if radius2 <= 0

    Example:
        >>> torus = make_torus_rsolid(radius1=20, radius2=5)
    """
    try:
        if radius2 <= 0:
            raise ValueError("Minor radius must be greater than 0")
        if radius1 <= radius2:
            raise ValueError("Major radius must be greater than minor radius")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))
        axis_global = cs.transform_vector(np.array(axis))

        center_vec = Vector(*center_global)
        axis_vec = Vector(*axis_global)

        # Create torus using CadQuery's Solid.makeTorus method
        cq_solid = cq.Solid.makeTorus(radius1, radius2, center_vec, axis_vec)

        solid = Solid(cq_solid)
        
        # Auto tag faces
        solid.auto_tag_faces("torus")
        solid.apply_tag("geom.primitive.torus", propagate=False)
        solid.add_tag("torus")
        solid.add_tag(f"center: {center}")
        solid.add_tag(f"radius1: {radius1}")
        solid.add_tag(f"radius2: {radius2}")
        solid.set_metadata(
            "geo",
            {
                "type": "torus",
                "radius1": radius1,
                "radius2": radius2,
                "center": center,
                "axis": axis,
            },
        )

        _record_primitive_feature(
            solid,
            "torus",
            FeatureType.PRIMITIVE,
            {
                "radius1": radius1,
                "radius2": radius2,
                "center": center,
                "axis": axis,
            },
        )

        return solid
    except Exception as e:
        raise ValueError(f"Failed to create torus: {e}. Please check that radius1 > radius2 > 0.")


def make_three_point_arc_redge(
    start: Tuple[float, float, float],
    middle: Tuple[float, float, float],
    end: Tuple[float, float, float],
) -> Edge:
    """Create an arc edge from three points."""
    try:
        cs = get_current_cs()
        start_global = cs.transform_point(np.array(start))
        middle_global = cs.transform_point(np.array(middle))
        end_global = cs.transform_point(np.array(end))

        start_vec = Vector(*start_global)
        middle_vec = Vector(*middle_global)
        end_vec = Vector(*end_global)

        cq_edge = cq.Edge.makeThreePointArc(start_vec, middle_vec, end_vec)
        edge = Edge(cq_edge)
        _record_profile_feature(
            edge,
            "arc",
            {"start": start, "middle": middle, "end": end},
        )
        return edge
    except Exception as e:
        raise ValueError(f"创建三点圆弧失败: {e}. 请检查三个点的坐标是否有效且不共线。")


def make_three_point_arc_rwire(
    start: Tuple[float, float, float],
    middle: Tuple[float, float, float],
    end: Tuple[float, float, float],
) -> Wire:
    """Create a wire containing an arc defined by three points."""
    try:
        edge = make_three_point_arc_redge(start, middle, end)
        cq_wire = cq.Wire.assembleEdges([edge.cq_edge])
        wire = Wire(cq_wire)
        _record_profile_feature(
            wire,
            "arc",
            {"start": start, "middle": middle, "end": end},
        )
        return wire
    except Exception as e:
        raise ValueError(f"创建三点圆弧线失败: {e}")


def make_angle_arc_redge(
    center: Tuple[float, float, float],
    radius: float,
    start_angle: float,
    end_angle: float,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Edge:
    """Create an arc edge from a center, radius, and angle range."""
    try:
        if radius <= 0:
            raise ValueError("半径必须大于0")
        if start_angle == end_angle:
            raise ValueError("起始角度和结束角度不能相同")

        cs = get_current_cs()
        center_global = cs.transform_point(np.array(center))
        normal_global = cs.transform_point(np.array(normal)) - cs.origin

        # 标准化法向量
        normal_vec = normal_global / np.linalg.norm(normal_global)

        # 创建本地坐标系
        # 如果法向量接近Z轴，使用X轴作为参考
        if abs(normal_vec[2]) > 0.9:
            ref_vec = np.array([1.0, 0.0, 0.0])
        else:
            ref_vec = np.array([0.0, 0.0, 1.0])

        # 计算本地坐标系的X和Y轴
        local_x = np.cross(normal_vec, ref_vec)
        local_x = local_x / np.linalg.norm(local_x)
        local_y = np.cross(normal_vec, local_x)
        local_y = local_y / np.linalg.norm(local_y)

        # 在本地坐标系中计算起始、结束和中间点
        start_local = np.array(
            [radius * np.cos(start_angle), radius * np.sin(start_angle), 0]
        )
        end_local = np.array(
            [radius * np.cos(end_angle), radius * np.sin(end_angle), 0]
        )
        mid_angle = (start_angle + end_angle) / 2
        mid_local = np.array(
            [radius * np.cos(mid_angle), radius * np.sin(mid_angle), 0]
        )

        # 转换到全局坐标系
        start_global = (
            center_global + start_local[0] * local_x + start_local[1] * local_y
        )
        end_global = center_global + end_local[0] * local_x + end_local[1] * local_y
        mid_global = center_global + mid_local[0] * local_x + mid_local[1] * local_y

        start_vec = Vector(*start_global)
        end_vec = Vector(*end_global)
        mid_vec = Vector(*mid_global)

        # 使用三点圆弧方法
        cq_edge = cq.Edge.makeThreePointArc(start_vec, mid_vec, end_vec)
        edge = Edge(cq_edge)
        _record_profile_feature(
            edge,
            "arc",
            {
                "center": center,
                "radius": radius,
                "start_angle": start_angle,
                "end_angle": end_angle,
                "normal": normal,
            },
        )
        return edge
    except Exception as e:
        raise ValueError(f"创建角度圆弧失败: {e}. 请检查参数是否有效。")


def make_angle_arc_rwire(
    center: Tuple[float, float, float],
    radius: float,
    start_angle: float,
    end_angle: float,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Wire:
    """Create a wire containing an arc defined by a center, radius, and angle range."""

    try:
        edge = make_angle_arc_redge(center, radius, start_angle, end_angle, normal)
        cq_wire = cq.Wire.assembleEdges([edge.cq_edge])
        wire = Wire(cq_wire)
        _record_profile_feature(
            wire,
            "arc",
            {
                "center": center,
                "radius": radius,
                "start_angle": start_angle,
                "end_angle": end_angle,
                "normal": normal,
            },
        )
        return wire
    except Exception as e:
        raise ValueError(f"创建角度圆弧线失败: {e}")


def make_spline_redge(
    points: List[Tuple[float, float, float]],
    tangents: Optional[List[Tuple[float, float, float]]] = None,
) -> Edge:
    """Create a spline edge through control points."""
    try:
        if len(points) < 2:
            raise ValueError("至少需要2个控制点")

        cs = get_current_cs()

        # 转换控制点到全局坐标系
        global_points = []
        for point in points:
            global_point = cs.transform_point(np.array(point))
            global_points.append(Vector(*global_point))

        # 转换切线向量（如果提供）
        global_tangents = None
        if tangents:
            if len(tangents) != len(points):
                raise ValueError("切线向量数量必须与控制点数量一致")
            global_tangents = []
            for tangent in tangents:
                global_tangent = cs.transform_point(np.array(tangent)) - cs.origin
                global_tangents.append(Vector(*global_tangent))

        if global_tangents:
            # CADQuery的makeSpline不支持tangents参数，使用makeSplineApprox
            cq_edge = cq.Edge.makeSplineApprox(global_points)
        else:
            cq_edge = cq.Edge.makeSpline(global_points)

        edge = Edge(cq_edge)
        _record_profile_feature(
            edge,
            "spline",
            {"points": points, "tangents": tangents, "closed": False},
        )
        return edge
    except Exception as e:
        raise ValueError(f"创建样条曲线失败: {e}. 请检查控制点和切线向量是否有效。")


def make_spline_rwire(
    points: List[Tuple[float, float, float]],
    tangents: Optional[List[Tuple[float, float, float]]] = None,
    closed: bool = False,
) -> Wire:
    """Create a spline wire through control points."""
    try:
        edge = make_spline_redge(points, tangents)
        cq_wire = cq.Wire.assembleEdges([edge.cq_edge])
        if closed:
            cq_wire = cq_wire.close()  # 确保线是闭合的
        rv = Wire(cq_wire)
        _record_profile_feature(
            rv,
            "spline",
            {"points": points, "tangents": tangents, "closed": closed},
        )
        return rv
    except Exception as e:
        raise ValueError(f"创建样条曲线线失败: {e}")


def make_polyline_rwire(
    points: List[Tuple[float, float, float]], closed: bool = False
) -> Wire:
    """Create a polyline wire from a point list."""
    try:
        if len(points) < 2:
            raise ValueError("至少需要2个点")

        cs = get_current_cs()

        # 转换所有点到全局坐标系
        global_points = []
        for point in points:
            global_point = cs.transform_point(np.array(point))
            global_points.append(Vector(*global_point))

        # 创建边列表
        edges = []
        num_points = len(global_points)

        # 创建连接相邻点的边
        for i in range(num_points - 1):
            start_vec = global_points[i]
            end_vec = global_points[i + 1]
            edge = cq.Edge.makeLine(start_vec, end_vec)
            edges.append(edge)

        # 如果闭合，添加最后一条边
        if closed and num_points > 2:
            start_vec = global_points[-1]
            end_vec = global_points[0]
            edge = cq.Edge.makeLine(start_vec, end_vec)
            edges.append(edge)

        cq_wire = cq.Wire.assembleEdges(edges)
        wire = Wire(cq_wire.close() if closed else cq_wire)
        _record_profile_feature(
            wire,
            "polyline",
            {"points": points, "closed": closed},
        )
        return wire
    except Exception as e:
        raise ValueError(f"创建多段线失败: {e}. 请检查点坐标是否有效。")


def make_helix_redge(
    pitch: float,
    height: float,
    radius: float,
    center: Tuple[float, float, float] = (0, 0, 0),
    dir: Tuple[float, float, float] = (0, 0, 1),
) -> Edge:
    """Create a helix edge."""
    try:
        if pitch <= 0:
            raise ValueError("螺距必须大于0")
        if height <= 0:
            raise ValueError("高度必须大于0")
        if radius <= 0:
            raise ValueError("半径必须大于0")

        cs = get_current_cs()
        global_center = cs.transform_point(np.array(center))
        global_dir = cs.transform_point(np.array(dir)) - cs.origin

        center_vec = Vector(*global_center)
        dir_vec = Vector(*global_dir)

        # 使用CADQuery的Wire.makeHelix方法创建螺旋线，然后提取边
        cq_wire = cq.Wire.makeHelix(pitch, height, radius, center_vec, dir_vec)
        # 螺旋线通常是连续的，所以我们取第一个边
        edges = cq_wire.Edges()
        if edges:
            edge = Edge(edges[0])
            _record_profile_feature(
                edge,
                "helix",
                {
                    "pitch": pitch,
                    "height": height,
                    "radius": radius,
                    "center": center,
                    "dir": dir,
                },
            )
            return edge
        else:
            raise ValueError("无法从螺旋线中提取边")
    except Exception as e:
        raise ValueError(f"创建螺旋线边失败: {e}. 请检查参数是否有效。")


def make_helix_rwire(
    pitch: float,
    height: float,
    radius: float,
    center: Tuple[float, float, float] = (0, 0, 0),
    dir: Tuple[float, float, float] = (0, 0, 1),
) -> Wire:
    """Create a helix wire."""
    try:
        cs = get_current_cs()
        global_center = cs.transform_point(np.array(center))
        global_dir = cs.transform_point(np.array(dir)) - cs.origin

        center_vec = Vector(*global_center)
        dir_vec = Vector(*global_dir)

        # 使用CADQuery的Wire.makeHelix方法
        cq_wire = cq.Wire.makeHelix(pitch, height, radius, center_vec, dir_vec)
        wire = Wire(cq_wire)
        _record_profile_feature(
            wire,
            "helix",
            {
                "pitch": pitch,
                "height": height,
                "radius": radius,
                "center": center,
                "dir": dir,
            },
        )
        return wire
    except Exception as e:
        raise ValueError(f"创建螺旋线失败: {e}. 请检查参数是否有效。")


# =============================================================================
# 变换操作函数
# =============================================================================


def translate_shape(shape: AnyShape, vector: Tuple[float, float, float]) -> AnyShape:
    """Translate a shape by an offset vector."""
    try:
        cs = get_current_cs()
        global_vector = cs.transform_point(np.array(vector)) - cs.origin

        translation_vec = Vector(*global_vector)

        if isinstance(shape, Vertex):
            new_cq_shape = shape.cq_vertex.translate(translation_vec)
            new_shape = Vertex(new_cq_shape)
        elif isinstance(shape, Edge):
            new_cq_shape = shape.cq_edge.translate(translation_vec)
            new_shape = Edge(new_cq_shape)
        elif isinstance(shape, Wire):
            new_cq_shape = shape.cq_wire.translate(translation_vec)
            new_shape = Wire(new_cq_shape)
        elif isinstance(shape, Face):
            new_cq_shape = shape.cq_face.translate(translation_vec)
            new_shape = Face(new_cq_shape)
        elif isinstance(shape, Solid):
            new_cq_shape = shape.cq_solid.translate(translation_vec)
            new_shape = Solid(new_cq_shape)

        # 复制标签和元数据
        new_shape._tags = shape._tags.copy()
        new_shape._metadata = shape._metadata.copy()

        # 记录变换特征
        from .feature_history import FeatureType
        new_shape = _record_transformed_feature(
            shape=new_shape,
            operation="translate_shape",
            input_shapes=[shape],
            parameters={"vector": vector},
            feature_type=FeatureType.TRANSFORM,
        )

        return new_shape
    except Exception as e:
        raise ValueError(f"平移几何体失败: {e}. 请检查几何体和平移向量是否有效。")


def rotate_shape(
    shape: AnyShape,
    angle: float,
    axis: Tuple[float, float, float] = (0, 0, 1),
    origin: Tuple[float, float, float] = (0, 0, 0),
) -> AnyShape:
    """Rotate a shape around an axis."""
    if angle == 0:
        return shape
    else:
        try:
            cs = get_current_cs()
            global_axis = cs.transform_point(np.array(axis)) - cs.origin
            global_origin = cs.transform_point(np.array(origin))

            origin_vec = Vector(*global_origin)
            axis_vec = Vector(*global_axis).normalized() + origin_vec

            if isinstance(shape, Vertex):
                new_cq_shape = shape.cq_vertex.rotate(origin_vec, axis_vec, angle)
                new_shape = Vertex(new_cq_shape)
            elif isinstance(shape, Edge):
                new_cq_shape = shape.cq_edge.rotate(origin_vec, axis_vec, angle)
                new_shape = Edge(new_cq_shape)
            elif isinstance(shape, Wire):
                new_cq_shape = shape.cq_wire.rotate(origin_vec, axis_vec, angle)
                new_shape = Wire(new_cq_shape)
            elif isinstance(shape, Face):
                new_cq_shape = shape.cq_face.rotate(origin_vec, axis_vec, angle)
                new_shape = Face(new_cq_shape)
            elif isinstance(shape, Solid):
                new_cq_shape = shape.cq_solid.rotate(origin_vec, axis_vec, angle)
                new_shape = Solid(new_cq_shape)
            else:
                raise ValueError(f"不支持的几何体类型: {type(shape)}")  # type: ignore[unreachable]

            # 复制标签和元数据
            new_shape._tags = shape._tags.copy()
            new_shape._metadata = shape._metadata.copy()

            # 记录变换特征
            from .feature_history import FeatureType
            new_shape = _record_transformed_feature(
                shape=new_shape,
                operation="rotate_shape",
                input_shapes=[shape],
                parameters={"angle": angle, "axis": axis, "origin": origin},
                feature_type=FeatureType.TRANSFORM,
            )

            return new_shape
        except Exception as e:
            raise ValueError(
                f"旋转几何体失败: {e}. 请检查几何体、角度、轴向和中心点是否有效。"
            )


def scale_shape(
    shape: AnyShape,
    factor: float,
) -> AnyShape:
    """Scale a shape uniformly about the world origin."""
    if factor <= 0:
        raise ValueError("缩放因子必须大于0")

    try:
        if isinstance(shape, Vertex):
            new_cq_shape = shape.cq_vertex.scale(factor)
            new_shape = Vertex(new_cq_shape)
        elif isinstance(shape, Edge):
            new_cq_shape = shape.cq_edge.scale(factor)
            new_shape = Edge(new_cq_shape)
        elif isinstance(shape, Wire):
            new_cq_shape = shape.cq_wire.scale(factor)
            new_shape = Wire(new_cq_shape)
        elif isinstance(shape, Face):
            new_cq_shape = shape.cq_face.scale(factor)
            new_shape = Face(new_cq_shape)
        elif isinstance(shape, Solid):
            new_cq_shape = shape.cq_solid.scale(factor)
            new_shape = Solid(new_cq_shape)
        else:
            raise ValueError(f"不支持的几何体类型: {type(shape)}")  # type: ignore[unreachable]

        new_shape._tags = shape._tags.copy()
        new_shape._metadata = shape._metadata.copy()

        from .feature_history import FeatureType

        new_shape = _record_transformed_feature(
            shape=new_shape,
            operation="scale_shape",
            input_shapes=[shape],
            parameters={"factor": factor, "center": (0, 0, 0)},
            feature_type=FeatureType.TRANSFORM,
        )

        return new_shape
    except Exception as e:
        raise ValueError(f"缩放几何体失败: {e}. 请检查几何体和缩放因子是否有效。")


# =============================================================================
# 3D操作函数
# =============================================================================


def extrude_rsolid(
    profile: Union[Wire, Face], direction: Tuple[float, float, float], distance: float
) -> Solid:
    """Create a solid by extruding a profile."""
    try:
        if distance <= 0:
            raise ValueError("拉伸距离必须大于0")

        cs = get_current_cs()
        global_direction = cs.transform_point(np.array(direction)) - cs.origin

        direction_vec = Vector(*global_direction).normalized() * distance

        if isinstance(profile, Wire):
            # 如果是线，先转换为面
            if profile.is_closed():
                face = Face(cq.Face.makeFromWires(profile.cq_wire))
            else:
                raise ValueError(
                    "如果传入线框作为拉伸对象，那么线框必须是闭合的, 而你的线框没有闭合，请检查构成线框的点是否正确"
                )
        elif isinstance(profile, Face):
            face = profile
        else:
            raise ValueError("只能拉伸线或面")  # type: ignore[unreachable]

        # 使用CADQuery的Solid.extrudeLinear方法
        cq_solid = cq.Solid.extrudeLinear(face.cq_face, direction_vec)
        solid = Solid(cq_solid)

        side_face_count = 0
        profile_face_normal = None
        for face_after_extrusion in solid.get_faces():
            if face_after_extrusion.cq_face.Center() == face.cq_face.Center():
                face_after_extrusion._tags = profile._tags.copy()
                face_after_extrusion.add_tag("extrusion start face")
                face_after_extrusion._metadata = profile._metadata.copy()
                profile_face_normal = face_after_extrusion.cq_face.normalAt(
                    face.cq_face.Center().x, face.cq_face.Center().y
                )[0]

        if profile_face_normal is None:
            raise ValueError("没有找到和Profile一致的面对象")

        for face_after_extrusion in solid.get_faces():
            # 开始根据法向量判断顶面底面和侧面
            face_center = face_after_extrusion.cq_face.Center()
            # 如果法向量和dir正交，认为是侧面
            face_normal, _ = face_after_extrusion.cq_face.normalAt(
                face_center.x, face_center.y
            )
            if face_normal.dot(direction_vec) == 0:
                face_after_extrusion._tags = profile._tags.copy()
                face_after_extrusion.add_tag("extrusion side face")
                side_face_count += 1
                face_after_extrusion.add_tag(f"{side_face_count}")

            # 法向量夹角180度，是顶面
            if face_normal.getAngle(profile_face_normal) == math.pi:
                face_after_extrusion._tags = profile._tags.copy()
                face_after_extrusion.add_tag("extrusion end face")

        # 复制标签和元数据
        solid._tags = profile._tags.copy()
        solid.add_tag("extrusion solid")
        solid._metadata = profile._metadata.copy()

        _record_extrude_feature(solid, profile, direction, distance, direction_vec)

        return solid
    except Exception as e:
        raise ValueError(f"拉伸失败: {e}. 请检查轮廓、方向和距离是否有效。")


def _record_extrude_feature(
    solid: Solid,
    profile: Union[Wire, Face],
    direction: Tuple[float, float, float],
    distance: float,
    direction_vec: Vector,
) -> None:
    """Record extrude operation in feature history."""
    from .feature_history import (
        FeatureHistory,
        FeatureType,
        get_global_history,
        create_new_history,
    )

    history = get_global_history()
    if history is None:
        history = create_new_history("SimpleCAD Model")

    # Get input feature IDs if profile has them
    input_ids = []
    parent_ids = []
    
    # Try to get feature ID from profile's _feature attribute
    if hasattr(profile, "_feature") and profile._feature:
        if hasattr(profile._feature, "feature_id"):
            input_ids.append(profile._feature.feature_id)
            parent_ids.append(profile._feature.feature_id)
    
    # Also try _feature_id attribute directly on profile
    if hasattr(profile, "_feature_id") and profile._feature_id:
        if profile._feature_id not in input_ids:
            input_ids.append(profile._feature_id)
            if profile._feature_id not in parent_ids:
                parent_ids.append(profile._feature_id)
    
    # If still no parent IDs, check if the profile itself was recorded as a feature
    # This handles cases where profile comes from a make_* operation
    if not parent_ids and hasattr(profile, '_feature') and profile._feature:
        # Ensure the profile feature is properly linked
        profile_feature = profile._feature
        if hasattr(profile_feature, 'feature_id'):
            parent_ids.append(profile_feature.feature_id)
            if profile_feature.feature_id not in input_ids:
                input_ids.append(profile_feature.feature_id)

    # Determine feature name
    profile_name = getattr(profile, "_feature", None)
    if profile_name and hasattr(profile_name, "name"):
        profile_name = profile_name.name
    else:
        profile_name = type(profile).__name__

    feature = history.add_feature(
        name=f"Extrude_{profile_name}",
        operation="extrude",
        feature_type=FeatureType.EXTRUDE,
        inputs=[profile],
        input_ids=input_ids,
        parameters={
            "direction": direction,
            "distance": distance,
            "direction_vector": (direction_vec.x, direction_vec.y, direction_vec.z),
        },
        output=solid,
        description=f"Extruded {profile_name} by {distance} units",
        parent_ids=parent_ids,
    )

    # Associate solid with feature
    solid.set_feature(feature)


def _record_boolean_feature(
    result_solids: List[Solid],
    operation: str,
    input_solids: List[Solid],
    parameters: Optional[Dict[str, Any]] = None,
) -> List[Solid]:
    """Record boolean operation in feature history.
    
    Args:
        result_solids: Resulting solids from boolean operation
        operation: Boolean operation type ('boolean_union', 'boolean_cut', 'boolean_intersect')
        input_solids: Input solids involved in the operation
        parameters: Additional parameters for the operation
        
    Returns:
        The result solids with features recorded
    """
    from .feature_history import get_global_history, Feature, FeatureType, Parameter
    
    history = get_global_history()
    if history is None:
        return result_solids
    
    parent_ids = []
    input_ids = []
    for solid in input_solids:
        if hasattr(solid, '_feature') and solid._feature is not None:
            feature_id = solid._feature.feature_id
            parent_ids.append(feature_id)
            input_ids.append(feature_id)
    
    for solid in result_solids:
        # Build parameters dict with Parameter objects
        params = {}
        if parameters:
            for param_name, value in parameters.items():
                if isinstance(value, Parameter):
                    params[param_name] = value
                else:
                    params[param_name] = Parameter(param_name, value)

        # Map operation to correct FeatureType
        feature_type_map = {
            "boolean_union": FeatureType.BOOLEAN_UNION,
            "boolean_cut": FeatureType.BOOLEAN_CUT,
            "boolean_intersect": FeatureType.BOOLEAN_INTERSECT,
        }
        ft_type = feature_type_map.get(operation, FeatureType.BOOLEAN_UNION)

        # Map operation to correct FeatureType
        feature_type_map = {
            "boolean_union": FeatureType.BOOLEAN_UNION,
            "boolean_cut": FeatureType.BOOLEAN_CUT,
            "boolean_intersect": FeatureType.BOOLEAN_INTERSECT,
        }
        ft_type = feature_type_map.get(operation, FeatureType.BOOLEAN_UNION)

        # Create feature through history.add_feature with proper parameters
        feature = history.add_feature(
            name=f"Boolean_{operation}",
            operation=operation,
            feature_type=ft_type,
            inputs=input_solids,
            input_ids=input_ids,
            parameters=params,
            output=solid,
            parent_ids=parent_ids if parent_ids else None,
        )
        solid._feature = feature

    return result_solids


def _record_transformed_feature(
    shape: Any,
    operation: str,
    input_shapes: List[Any],
    parameters: Dict[str, Any],
    feature_type: Any,
) -> Any:
    """Record transformed feature in feature history.
    
    Args:
        shape: The transformed shape
        operation: Operation type ('translate_shape', 'rotate_shape', etc.)
        input_shapes: Input shapes
        parameters: Operation parameters
        feature_type: FeatureType enum value
        
    Returns:
        The shape with feature recorded
    """
    from .feature_history import (
        get_global_history,
        create_new_history,
        get_registered_feature_id,
        Parameter,
    )
    
    history = get_global_history()
    if history is None:
        history = create_new_history("SimpleCAD Model")
    
    parent_ids = []
    input_ids = []
    for item in input_shapes:
        feature_id = get_registered_feature_id(item)
        if feature_id is not None:
            parent_ids.append(feature_id)
            input_ids.append(feature_id)
    
    # Build parameters dict with Parameter objects
    params = {}
    for param_name, value in parameters.items():
        if isinstance(value, Parameter):
            params[param_name] = value
        else:
            params[param_name] = Parameter(param_name, value)

    # Create feature through history.add_feature with proper parameters
    feature = history.add_feature(
        name=f"Transformed_{operation}",
        operation=operation,
        feature_type=feature_type,
        inputs=input_shapes,
        input_ids=input_ids,
        parameters=params,
        output=shape,
        parent_ids=parent_ids if parent_ids else None,
    )
    if hasattr(shape, "set_feature"):
        shape.set_feature(feature)
    else:
        setattr(shape, "_feature", feature)
        setattr(shape, "_feature_id", feature.feature_id)

    return shape


def _find_edge_indices(base_solid: Solid, selected_edges: List[Edge]) -> List[int]:
    """Map selected edge objects back to edge indices on the base solid."""
    base_edges = base_solid.get_edges()
    indices: List[int] = []
    for selected_edge in selected_edges:
        for index, base_edge in enumerate(base_edges):
            if base_edge.cq_edge.wrapped.IsSame(selected_edge.cq_edge.wrapped):
                indices.append(index)
                break
    return indices


def _point_tuple(point: Any) -> Tuple[float, float, float]:
    """Convert a CadQuery/OCC vector-like object to a serializable point tuple."""
    return (float(point.x), float(point.y), float(point.z))


def _edge_signature(edge: Edge) -> Dict[str, Any]:
    """Create a geometry-based edge selector for CAD script replay.

    Topological edge indices are not stable after replaying booleans in another
    kernel/session.  The signature gives exporters a more robust way to find
    the intended edge while keeping the modifier feature in the history tree.
    """
    cq_edge = edge.cq_edge
    signature: Dict[str, Any] = {
        "length": float(cq_edge.Length()),
    }

    try:
        signature["center"] = _point_tuple(cq_edge.Center())
    except Exception:
        pass

    try:
        signature["geom_type"] = str(cq_edge.geomType())
    except Exception:
        pass

    try:
        vertices = cq_edge.Vertices()
        if len(vertices) >= 2:
            signature["start"] = _point_tuple(vertices[0].Center())
            signature["end"] = _point_tuple(vertices[-1].Center())
    except Exception:
        pass

    try:
        bbox = cq_edge.BoundingBox()
        signature["bbox"] = [
            float(bbox.xmin),
            float(bbox.ymin),
            float(bbox.zmin),
            float(bbox.xmax),
            float(bbox.ymax),
            float(bbox.zmax),
        ]
    except Exception:
        pass

    return signature


def _edge_signatures(edges: List[Edge]) -> List[Dict[str, Any]]:
    """Create geometry-based selectors for a list of edges."""
    return [_edge_signature(edge) for edge in edges]


def _find_face_indices(base_solid: Solid, selected_faces: List[Face]) -> List[int]:
    """Map selected face objects back to face indices on the base solid."""
    base_faces = base_solid.get_faces()
    indices: List[int] = []
    for selected_face in selected_faces:
        for index, base_face in enumerate(base_faces):
            if base_face.cq_face.wrapped.IsSame(selected_face.cq_face.wrapped):
                indices.append(index)
                break
    return indices


def _record_modifier_feature(
    result_solid: Solid,
    operation: str,
    base_solid: Solid,
    parameters: Dict[str, Any],
    feature_type: Any,
) -> Solid:
    """Record a single-input solid modifier feature such as fillet/chamfer/shell."""
    from .feature_history import get_global_history, get_registered_feature_id, Parameter

    history = get_global_history()
    if history is None:
        return result_solid

    parent_ids = []
    input_ids = []
    feature_id = get_registered_feature_id(base_solid)
    if feature_id is not None:
        parent_ids.append(feature_id)
        input_ids.append(feature_id)

    params = {}
    for param_name, value in parameters.items():
        if isinstance(value, Parameter):
            params[param_name] = value
        else:
            params[param_name] = Parameter(param_name, value)

    feature = history.add_feature(
        name=f"{operation.capitalize()}_{getattr(base_solid._feature, 'name', 'Solid')}",
        operation=operation,
        feature_type=feature_type,
        inputs=[base_solid],
        input_ids=input_ids,
        parameters=params,
        output=result_solid,
        parent_ids=parent_ids if parent_ids else None,
    )
    result_solid.set_feature(feature)
    return result_solid


def _record_generic_feature(
    output_shape: Any,
    name: str,
    operation: str,
    feature_type: Any,
    inputs: List[Any],
    parameters: Dict[str, Any],
    description: str = "",
):
    """Record a general feature with arbitrary inputs and output."""
    from .feature_history import (
        get_global_history,
        create_new_history,
        get_registered_feature_id,
        Parameter,
    )

    history = get_global_history()
    if history is None:
        history = create_new_history("SimpleCAD Model")

    parent_ids: List[str] = []
    input_ids: List[str] = []
    for item in inputs:
        feature_id = get_registered_feature_id(item)
        if feature_id and feature_id not in input_ids:
            input_ids.append(feature_id)
            parent_ids.append(feature_id)

    params = {}
    for param_name, value in parameters.items():
        if isinstance(value, Parameter):
            params[param_name] = value
        else:
            params[param_name] = Parameter(param_name, value)

    feature = history.add_feature(
        name=name,
        operation=operation,
        feature_type=feature_type,
        inputs=inputs,
        input_ids=input_ids,
        parameters=params,
        output=output_shape,
        description=description,
        parent_ids=parent_ids if parent_ids else None,
    )

    if hasattr(output_shape, "set_feature"):
        output_shape.set_feature(feature)
    else:
        setattr(output_shape, "_feature", feature)
        setattr(output_shape, "_feature_id", feature.feature_id)

    return output_shape


def _record_profile_feature(
    profile: Any,
    profile_type: str,
    parameters: Dict[str, Any],
) -> None:
    """Record a 2D profile (Edge/Wire/Face) creation in feature history.
    
    This function creates a SKETCH feature for primitive 2D geometry
    like rectangles, circles, etc. This allows downstream operations
    (extrude, revolve) to properly reference their parent profiles.
    
    Args:
        profile: The Edge, Wire, or Face to record
        profile_type: Type of profile (e.g., 'rectangle', 'circle', 'polygon')
        parameters: Dictionary of creation parameters
    """
    from .feature_history import (
        FeatureHistory,
        FeatureType,
        get_global_history,
        create_new_history,
    )

    history = get_global_history()
    if history is None:
        history = create_new_history("SimpleCAD Model")

    profile_kind = type(profile).__name__

    feature = history.add_feature(
        name=f"{profile_type.capitalize()}_{profile_kind}_Profile",
        operation=f"make_{profile_type}",
        feature_type=FeatureType.SKETCH,
        inputs=[],
        input_ids=[],
        parameters=parameters,
        output=profile,
        description=f"Created {profile_type} {type(profile).__name__.lower()}",
    )

    # Associate profile with feature
    # Always try set_feature method first (proper encapsulation)
    if hasattr(profile, 'set_feature'):
        profile.set_feature(feature)
    else:
        # Fallback: set attributes directly for objects without set_feature
        setattr(profile, "_feature", feature)
        setattr(profile, "_feature_id", feature.feature_id)


def _record_revolve_feature(
    solid: Solid,
    profile: Union[Wire, Face],
    axis: Tuple[float, float, float],
    angle: float,
    origin: Tuple[float, float, float],
    global_axis: np.ndarray,
    global_origin: np.ndarray,
) -> None:
    """Record revolve operation in feature history."""
    from .feature_history import (
        FeatureHistory,
        FeatureType,
        get_global_history,
        create_new_history,
    )

    history = get_global_history()
    if history is None:
        history = create_new_history("SimpleCAD Model")

    input_ids = []
    parent_ids = []
    
    # Try to get feature ID from profile's _feature attribute
    if hasattr(profile, "_feature") and profile._feature:
        if hasattr(profile._feature, "feature_id"):
            input_ids.append(profile._feature.feature_id)
            parent_ids.append(profile._feature.feature_id)
    
    # Also try _feature_id attribute
    if hasattr(profile, "_feature_id") and profile._feature_id:
        if profile._feature_id not in input_ids:
            input_ids.append(profile._feature_id)
            if profile._feature_id not in parent_ids:
                parent_ids.append(profile._feature_id)

    profile_name = getattr(profile, "_feature", None)
    if profile_name and hasattr(profile_name, "name"):
        profile_name = profile_name.name
    else:
        profile_name = type(profile).__name__

    feature = history.add_feature(
        name=f"Revolve_{profile_name}",
        operation="revolve",
        feature_type=FeatureType.REVOLVE,
        inputs=[profile],
        input_ids=input_ids,
        parameters={
            "axis": axis,
            "angle": angle,
            "origin": origin,
            "global_axis": global_axis.tolist() if isinstance(global_axis, np.ndarray) else global_axis,
            "global_origin": global_origin.tolist() if isinstance(global_origin, np.ndarray) else global_origin,
        },
        output=solid,
        description=f"Revolved {profile_name} by {angle} degrees",
        parent_ids=parent_ids,
    )

    solid.set_feature(feature)


def _record_primitive_feature(
    solid: Solid,
    primitive_type: str,
    feature_type: Any,
    parameters: Dict[str, Any],
) -> None:
    """Record primitive geometry creation in feature history."""
    from .feature_history import (
        FeatureHistory,
        FeatureType,
        get_global_history,
        create_new_history,
    )

    history = get_global_history()
    if history is None:
        history = create_new_history("SimpleCAD Model")

    # Map primitive type to FeatureType
    type_mapping = {
        "box": FeatureType.PRIMITIVE,
        "cylinder": FeatureType.PRIMITIVE,
        "sphere": FeatureType.PRIMITIVE,
        "cone": FeatureType.PRIMITIVE,
    }
    feat_type = type_mapping.get(primitive_type, FeatureType.PRIMITIVE)

    feature = history.add_feature(
        name=f"{primitive_type.capitalize()}_Primitive",
        operation=f"make_{primitive_type}",
        feature_type=feat_type,
        inputs=[],
        input_ids=[],
        parameters=parameters,
        output=solid,
        description=f"Created {primitive_type} primitive",
    )

    solid.set_feature(feature)


def revolve_rsolid(
    profile: Union[Wire, Face],
    axis: Tuple[float, float, float] = (0, 0, 1),
    angle: float = 360,
    origin: Tuple[float, float, float] = (0, 0, 0),
) -> Solid:
    """Create a solid by revolving a profile around an axis."""
    try:
        if angle <= 0:
            raise ValueError("旋转角度必须大于0")

        cs = get_current_cs()
        global_axis = cs.transform_point(np.array(axis)) - cs.origin
        global_origin = cs.transform_point(np.array(origin))

        # 获取轮廓对应的面
        if isinstance(profile, Wire):
            # 如果是线，先转换为面
            if profile.is_closed():
                face = Face(cq.Face.makeFromWires(profile.cq_wire))
            else:
                raise ValueError("旋转的线必须是闭合的")
        elif isinstance(profile, Face):
            face = profile
        else:
            raise ValueError("只能旋转线或面")

        print(f"revolve_rsolid: profile type: {type(profile)}, face type: {type(face)}")
        print(
            f"with parameters: axis={global_axis}, angle={angle}, origin={global_origin}"
        )

        rv = revolve(
            face.cq_face,
            p=Vector((global_origin[0], global_origin[1], global_origin[2])),
            d=Vector(
                (
                    global_axis[0],
                    global_axis[1],
                    global_axis[2],
                )
            ).normalized(),
            a=angle,
        )

        print(f"Revolve result type: {type(rv)}")

        if hasattr(rv, "Solids") and rv.Solids():
            cq_solid = rv.Solids()[0]
        else:
            cq_solid = rv

        solid = Solid(cq_solid)

        # 复制标签和元数据
        solid._tags = profile._tags.copy()
        solid._metadata = profile._metadata.copy()

        # Record feature history
        _record_revolve_feature(solid, profile, axis, angle, origin, global_axis, global_origin)

        return solid
    except Exception as e:
        raise ValueError(f"旋转失败: {e}. 请检查轮廓、轴向、角度和中心点是否有效。")


# =============================================================================
# 标签和选择函数
# =============================================================================


def set_tag(shape: AnyShape, tag: str) -> AnyShape:
    """Attach a tag to a shape."""
    try:
        shape.add_tag(tag)
        return shape
    except Exception as e:
        raise ValueError(f"设置标签失败: {e}. 请检查几何体和标签名称是否有效。")


def select_faces_by_tag(solid: Solid, tag: str) -> List[Face]:
    """Select faces by tag."""
    try:
        faces = solid.get_faces()
        return [face for face in faces if face.has_tag(tag)]
    except Exception as e:
        raise ValueError(f"选择面失败: {e}. 请检查实体和标签名称是否有效。")


def select_edges_by_tag(shape: Union[Face, Solid], tag: str) -> List[Edge]:
    """Select edges by tag."""
    try:
        if isinstance(shape, Face):
            edges = [Edge(edge) for edge in shape.cq_face.Edges()]
        elif isinstance(shape, Solid):
            edges = shape.get_edges()
        else:
            raise ValueError("只能从面或实体中选择边")

        return [edge for edge in edges if edge.has_tag(tag)]
    except Exception as e:
        raise ValueError(f"选择边失败: {e}. 请检查几何体和标签名称是否有效。")


# =============================================================================
# 布尔运算函数
# =============================================================================


def _topology_items(shape: AnyShape, domain: str) -> List[Any]:
    """Return topology items for a ql_select domain."""
    domain = domain.strip().lower()
    if domain in {"face", "faces"}:
        if not isinstance(shape, Solid):
            raise ValueError("faces domain requires a Solid")
        return list(shape.get_faces())
    if domain in {"edge", "edges"}:
        if isinstance(shape, Solid):
            return list(shape.get_edges())
        if isinstance(shape, Face):
            return list(shape.get_outer_wire().get_edges())
        if isinstance(shape, Wire):
            return list(shape.get_edges())
        raise ValueError("edges domain requires a Solid, Face, or Wire")
    if domain in {"wire", "wires"}:
        if isinstance(shape, Face):
            return [shape.get_outer_wire(), *shape.get_inner_wires()]
        if isinstance(shape, Solid):
            wires: List[Wire] = []
            for face in shape.get_faces():
                wires.append(face.get_outer_wire())
                wires.extend(face.get_inner_wires())
            return wires
        raise ValueError("wires domain requires a Solid or Face")
    if domain in {"vertex", "vertices"}:
        vertices: List[Vertex] = []
        for edge in _topology_items(shape, "edges"):
            vertices.extend(edge.get_children())
        return vertices
    raise ValueError(f"unsupported ql_select domain: {domain}")


def _wrapped_shape(item: Any) -> Any:
    if isinstance(item, Face):
        return item.cq_face.wrapped
    if isinstance(item, Edge):
        return item.cq_edge.wrapped
    if isinstance(item, Wire):
        return item.cq_wire.wrapped
    if isinstance(item, Vertex):
        return item.cq_vertex.wrapped
    return None


def _shape_index(base_items: List[Any], selected: Any) -> Optional[int]:
    selected_wrapped = _wrapped_shape(selected)
    if selected_wrapped is None:
        return None
    for index, item in enumerate(base_items):
        item_wrapped = _wrapped_shape(item)
        if item_wrapped is not None and item_wrapped.IsSame(selected_wrapped):
            return index
    return None


def _bbox_signature(shape: Any) -> Optional[List[float]]:
    try:
        bbox = shape.BoundingBox()
        return [
            float(bbox.xmin),
            float(bbox.ymin),
            float(bbox.zmin),
            float(bbox.xmax),
            float(bbox.ymax),
            float(bbox.zmax),
        ]
    except Exception:
        return None


def _topology_signature(item: Any) -> Dict[str, Any]:
    if isinstance(item, Edge):
        return _edge_signature(item)

    signature: Dict[str, Any] = {}
    if isinstance(item, Face):
        cq_face = item.cq_face
        try:
            signature["area"] = float(cq_face.Area())
        except Exception:
            pass
        try:
            signature["center"] = _point_tuple(cq_face.Center())
        except Exception:
            pass
        try:
            normal = item.get_normal_at()
            signature["normal"] = _point_tuple(normal)
        except Exception:
            pass
        bbox = _bbox_signature(cq_face)
        if bbox is not None:
            signature["bbox"] = bbox
        try:
            signature["edge_count"] = len(cq_face.Edges())
        except Exception:
            pass
        return signature

    if isinstance(item, Wire):
        cq_wire = item.cq_wire
        try:
            signature["length"] = float(cq_wire.Length())
        except Exception:
            pass
        try:
            signature["center"] = _point_tuple(cq_wire.Center())
        except Exception:
            pass
        bbox = _bbox_signature(cq_wire)
        if bbox is not None:
            signature["bbox"] = bbox
        try:
            signature["edge_count"] = len(cq_wire.Edges())
        except Exception:
            pass
        return signature

    if isinstance(item, Vertex):
        try:
            signature["point"] = _point_tuple(item.cq_vertex.Center())
        except Exception:
            pass
        return signature

    return signature


def ql_select(
    shape: AnyShape,
    domain: str,
    query: Any,
    name: str = "QL_Selection",
) -> List[Any]:
    """Select topology with QL and record the selected CAD objects as a feature.

    Args:
        shape: Base SimpleCAD shape to select from.
        domain: Topology domain: `faces`, `edges`, `wires`, or `vertices`.
        query: A `simplecadapi.ql.QuerySpec` or a runtime predicate/lambda.
        name: Feature name used in exported history and FreeCAD scripts.

    Returns:
        List[Any]: Selected topology objects.

    Usage:
        top_face = scad.ql_select_one(
            cylinder,
            "faces",
            scad.ql.query()
                .where(scad.ql.tag("extrusion end face"))
                .take(1)
                .exactly(1),
            name="Selected_Extrusion_Top_Face",
        )

        Lambdas are supported as snapshot selections:

        selected_edges = scad.ql_select(
            body,
            "edges",
            lambda edge: edge.get_length() > 10.0,
        )

        The lambda runs when the SimpleCAD script runs. FreeCAD export does
        not re-run arbitrary Python lambdas; it re-binds the selected result
        using topology indices and geometry signatures.
    """
    try:
        items = _topology_items(shape, domain)
        if hasattr(query, "resolve"):
            selected = list(query.resolve(items))
            query_data = query.to_dict() if hasattr(query, "to_dict") else {}
        else:
            selected = [item for item in items if query(item)]
            query_data = {"where": [getattr(query, "_ql_expr", None)]}

        indices = [
            index for item in selected if (index := _shape_index(items, item)) is not None
        ]
        signatures = [_topology_signature(item) for item in selected]

        from .feature_history import (
            bind_feature_output,
            create_new_history,
            get_global_history,
            get_registered_feature_id,
            Parameter,
        )

        history = get_global_history()
        if history is None:
            history = create_new_history("SimpleCAD Model")

        input_ids = []
        parent_ids = []
        feature_id = get_registered_feature_id(shape)
        if feature_id:
            input_ids.append(feature_id)
            parent_ids.append(feature_id)

        feature = history.add_feature(
            name=name,
            operation="ql_select",
            feature_type=FeatureType.CUSTOM,
            inputs=[shape],
            input_ids=input_ids,
            parameters={
                "domain": Parameter("domain", domain),
                "query": Parameter("query", query_data),
                "indices": Parameter("indices", indices),
                "signatures": Parameter("signatures", signatures),
                "count": Parameter("count", len(selected)),
            },
            output=selected[0] if len(selected) == 1 else selected,
            description=f"Selected {len(selected)} {domain} item(s) with QL",
            parent_ids=parent_ids or None,
        )
        for item in selected:
            bind_feature_output(item, feature)

        return selected
    except Exception as e:
        raise ValueError(f"QL topology selection failed: {e}")


def ql_select_one(
    shape: AnyShape,
    domain: str,
    query: Any,
    name: str = "QL_Selection",
) -> Any:
    """Select exactly one topology item with `ql_select`.

    Args:
        shape: Base SimpleCAD shape to select from.
        domain: Topology domain: `faces`, `edges`, `wires`, or `vertices`.
        query: A `simplecadapi.ql.QuerySpec` or a runtime predicate/lambda.
        name: Feature name used in exported history and FreeCAD scripts.

    Returns:
        Any: The single selected topology object.
    """
    selected = ql_select(shape, domain, query, name=name)
    if len(selected) != 1:
        raise ValueError(f"expected exactly one selected item, got {len(selected)}")
    return selected[0]


def _resolve_query(query: Any, items: List[Any]) -> Tuple[List[Any], Dict[str, Any]]:
    if hasattr(query, "resolve"):
        selected = list(query.resolve(items))
        query_data = query.to_dict() if hasattr(query, "to_dict") else {}
    else:
        selected = [item for item in items if query(item)]
        query_data = {"where": [getattr(query, "_ql_expr", None)]}
    return selected, query_data


def ql_select_from(
    items: Sequence[Any],
    query: Any,
    name: str = "QL_List_Selection",
) -> List[Any]:
    """Select from an explicit list of feature outputs and record the result.

    Args:
        items: Sequence of SimpleCAD feature outputs.
        query: A `simplecadapi.ql.QuerySpec` or a runtime predicate/lambda.
        name: Feature name used in exported history and FreeCAD scripts.

    Returns:
        List[Any]: Selected feature outputs.

    Usage:
        largest_part = scad.ql_select_one_from(
            [box, cylinder, bracket],
            scad.ql.query()
                .order_by(scad.ql.geo("volume"), desc=True)
                .take(1)
                .exactly(1),
        )

        Export works for SimpleCAD CAD objects that have feature ids. Plain
        dictionaries or arbitrary Python objects are runtime-only unless they
        implement a future export protocol.
    """
    try:
        item_list = list(items)
        selected, query_data = _resolve_query(query, item_list)

        from .feature_history import (
            bind_feature_output,
            create_new_history,
            get_global_history,
            get_registered_feature_id,
            Parameter,
        )

        history = get_global_history()
        if history is None:
            history = create_new_history("SimpleCAD Model")

        input_ids: List[str] = []
        parent_ids: List[str] = []
        item_feature_ids: List[Optional[str]] = []
        for item in item_list:
            feature_id = get_registered_feature_id(item)
            item_feature_ids.append(feature_id)
            if feature_id and feature_id not in input_ids:
                input_ids.append(feature_id)
                parent_ids.append(feature_id)

        selected_feature_ids: List[str] = []
        selected_positions: List[int] = []
        for selected_item in selected:
            for index, item in enumerate(item_list):
                if selected_item is item:
                    selected_positions.append(index)
                    feature_id = item_feature_ids[index]
                    if feature_id:
                        selected_feature_ids.append(feature_id)
                    break

        feature = history.add_feature(
            name=name,
            operation="ql_select_from",
            feature_type=FeatureType.CUSTOM,
            inputs=item_list,
            input_ids=input_ids,
            parameters={
                "query": Parameter("query", query_data),
                "item_feature_ids": Parameter("item_feature_ids", item_feature_ids),
                "selected_feature_ids": Parameter("selected_feature_ids", selected_feature_ids),
                "selected_positions": Parameter("selected_positions", selected_positions),
                "count": Parameter("count", len(selected)),
            },
            output=selected[0] if len(selected) == 1 else selected,
            description=f"Selected {len(selected)} item(s) from feature list with QL",
            parent_ids=parent_ids or None,
        )
        for item in selected:
            bind_feature_output(item, feature)

        return selected
    except Exception as e:
        raise ValueError(f"QL feature-list selection failed: {e}")


def ql_select_one_from(
    items: Sequence[Any],
    query: Any,
    name: str = "QL_List_Selection",
) -> Any:
    """Select exactly one item from a feature-output list."""
    selected = ql_select_from(items, query, name=name)
    if len(selected) != 1:
        raise ValueError(f"expected exactly one selected item, got {len(selected)}")
    return selected[0]


def ql_select_from_topology(
    sources: Sequence[Tuple[AnyShape, str]],
    query: Any,
    name: str = "QL_Multi_Topology_Selection",
) -> List[Any]:
    """Select topology across multiple base shapes and record replay references.

    Args:
        sources: Sequence of `(shape, domain)` pairs. Domains are `faces`,
            `edges`, `wires`, or `vertices`.
        query: A `simplecadapi.ql.QuerySpec` or a runtime predicate/lambda.
        name: Feature name used in exported history and FreeCAD scripts.

    Returns:
        List[Any]: Selected topology objects.

    Usage:
        largest_face = scad.ql_select_one_from_topology(
            [(left_body, "faces"), (right_body, "faces")],
            scad.ql.query()
                .order_by(scad.ql.geo("area"), desc=True)
                .take(1)
                .exactly(1),
        )

        Lambda predicates are exported as result snapshots: SimpleCAD runs the
        lambda, then FreeCAD re-binds the selected face/edge/wire/vertex by
        base feature id, topology index, and geometry signature.
    """
    try:
        all_items: List[Any] = []
        item_refs: List[Dict[str, Any]] = []
        source_list = list(sources)
        from .feature_history import (
            bind_feature_output,
            create_new_history,
            get_global_history,
            get_registered_feature_id,
            Parameter,
        )

        input_ids: List[str] = []
        parent_ids: List[str] = []
        for source_index, (shape, domain) in enumerate(source_list):
            feature_id = get_registered_feature_id(shape)
            if feature_id and feature_id not in input_ids:
                input_ids.append(feature_id)
                parent_ids.append(feature_id)
            items = _topology_items(shape, domain)
            for index, item in enumerate(items):
                all_items.append(item)
                item_refs.append(
                    {
                        "source_index": source_index,
                        "base_feature_id": feature_id,
                        "domain": domain,
                        "index": index,
                        "signature": _topology_signature(item),
                    }
                )

        selected, query_data = _resolve_query(query, all_items)
        selected_refs: List[Dict[str, Any]] = []
        for selected_item in selected:
            for index, item in enumerate(all_items):
                if selected_item is item:
                    selected_refs.append(item_refs[index])
                    break

        history = get_global_history()
        if history is None:
            history = create_new_history("SimpleCAD Model")

        feature = history.add_feature(
            name=name,
            operation="ql_select_from_topology",
            feature_type=FeatureType.CUSTOM,
            inputs=[shape for shape, _domain in source_list],
            input_ids=input_ids,
            parameters={
                "query": Parameter("query", query_data),
                "selected_refs": Parameter("selected_refs", selected_refs),
                "count": Parameter("count", len(selected)),
            },
            output=selected[0] if len(selected) == 1 else selected,
            description=f"Selected {len(selected)} topology item(s) from multiple sources",
            parent_ids=parent_ids or None,
        )
        for item in selected:
            bind_feature_output(item, feature)

        return selected
    except Exception as e:
        raise ValueError(f"QL multi-topology selection failed: {e}")


def ql_select_one_from_topology(
    sources: Sequence[Tuple[AnyShape, str]],
    query: Any,
    name: str = "QL_Multi_Topology_Selection",
) -> Any:
    """Select exactly one topology item from multiple sources."""
    selected = ql_select_from_topology(sources, query, name=name)
    if len(selected) != 1:
        raise ValueError(f"expected exactly one selected item, got {len(selected)}")
    return selected[0]


def union_rsolidlist(
    *solids: Union[Solid, Sequence[Solid]],
    clean: bool = True,
    glue: bool = _DEFAULT_UNION_GLUE,
    tol: Optional[float] = None,
) -> List[Solid]:
    """Compute the boolean union of one or more solids.

    Args:
        solids: One or more Solid objects or sequences of Solid. Nested sequences are
            flattened before processing.
        clean: Call CadQuery's `clean()` after the union to unify same-domain faces
            and remove splitter edges when possible.
        glue: Enable OCC glue mode for touching or partially overlapping inputs.
            Defaults to True for SimpleCAD's standard union behavior.
        tol: Optional fuzzy-boolean tolerance used by the OCC union kernel. When
            omitted, SimpleCAD chooses a conservative scale-aware tolerance.

    Returns:
        List[Solid]: Resulting solids after union attempts. Solids that can be fused
        are merged; disjoint or tangent-only contacts remain separate, so the
        list may contain multiple solids.

    Usage:
        All boolean operations (union/cut/intersect) accept a mix of Solid and
        sequences; results are always returned as a list of Solid.
        Keep the list result unless you have explicitly verified `len(result) == 1`.
        SimpleCAD enables glue mode by default and applies a conservative internal
        fuzzy tolerance so normal code does not need to tune boolean parameters.
        Touching-but-not-intersecting inputs can legitimately return multiple solids.
        If that happens, keep using the list: pass it directly into later union calls,
        or iterate over the solids for later cut/intersect steps. When returned
        solids remain separated by more than the active tolerance, SimpleCAD prints
        a stdout warning describing the detected gap. If you truly need exactly one
        merged solid, you must check the list length before using `result[0]`.

    Examples:
        # Rounded-bar style input: end caps only touch the center body.
        main_body = make_box_rsolid(10, 4, 4, bottom_face_center=(0, 0, 0))
        left_cap = make_sphere_rsolid(2.0, center=(-2.0, 2.0, 2.0))
        right_cap = make_sphere_rsolid(2.0, center=(12.0, 2.0, 2.0))

        body_parts = union_rsolidlist(main_body, [left_cap, right_cap])
        print(f"Union result count: {len(body_parts)}")
        # This is acceptable: tangent-only contact can stay as multiple solids.
        for solid in body_parts:
            print(f"- volume: {solid.get_volume():.6f}")

        # Keep using the returned list in later boolean steps.
        rib = make_box_rsolid(2, 4, 4, bottom_face_center=(4, 0, 0))
        combined_parts = union_rsolidlist(body_parts, rib)
        print(f"Combined result count: {len(combined_parts)}")

        # Only unwrap to one solid after an explicit length check.
        left_cap_embedded = make_sphere_rsolid(2.0, center=(-1.8, 2.0, 2.0))
        right_cap_embedded = make_sphere_rsolid(2.0, center=(11.8, 2.0, 2.0))
        merged = union_rsolidlist(main_body, [left_cap_embedded, right_cap_embedded])
        if len(merged) != 1:
            raise ValueError(
                "Adjust part placement so each cap overlaps the body slightly before "
                "using merged[0]."
            )
        final_body = merged[0]
    """

    try:
        # 递归展开所有参数：将Solid直接添加，将序列展开
        def _flatten_solids(args):
            result = []
            for arg in args:
                if isinstance(arg, Solid):
                    result.append(arg)
                elif isinstance(arg, Sequence) and not isinstance(arg, (str, bytes)):
                    result.extend(_flatten_solids(arg))
                else:
                    result.append(arg)  # 保留非Solid对象，后续会进行类型检查
            return result

        remaining = _flatten_solids(solids)

        if not remaining:
            return []

        for solid in remaining:
            if not isinstance(solid, Solid):
                raise ValueError("union_rsolidlist函数只接受Solid类型的对象")
            if solid.cq_solid.isNull():
                raise ValueError("输入实体无效，无法进行并集运算。")

        if len(remaining) == 1 and not clean:
            return [remaining[0]]

        effective_tol = _resolve_union_tol(remaining, tol)
        cq_shapes = [solid.cq_solid for solid in remaining]

        if len(cq_shapes) == 1:
            fused_shape = cq_shapes[0]
        else:
            fused_shape = cq_shapes[0].fuse(
                *cq_shapes[1:], glue=glue, tol=effective_tol
            )

        if clean:
            fused_shape = fused_shape.clean()

        if hasattr(fused_shape, "Solids"):
            cq_results = list(fused_shape.Solids())
        elif hasattr(fused_shape, "ShapeType") and fused_shape.ShapeType() == "Solid":
            cq_results = [fused_shape]
        else:
            cq_results = []

        if not cq_results:
            raise ValueError("并集结果中未找到有效实体。")

        all_tags = set()
        all_metadata = {}
        for solid in remaining:
            all_tags.update(solid._tags)
            all_metadata.update(solid._metadata)

        result: List[Solid] = []
        for cq_result in cq_results:
            fused_solid = Solid(cq_result)
            fused_solid._tags = all_tags.copy()
            fused_solid._metadata = all_metadata.copy()
            result.append(fused_solid)

        _warn_if_union_results_remain_separated(result, effective_tol)

        # 记录布尔并集特征
        result = _record_boolean_feature(
            result_solids=result,
            operation="boolean_union",
            input_solids=remaining,
        )

        return result
    except Exception as e:
        raise ValueError(f"并集运算失败: {e}. 请检查实体列表是否有效。")


def cut_rsolidlist(*solids: Union[Solid, Sequence[Solid]]) -> List[Solid]:
    """Compute the boolean difference of solids.

    Args:
        solids: One or more Solid objects or sequences of Solid. Nested sequences are
            flattened before processing; the first solid is the base, the rest are
            subtracted in order.

    Returns:
        List[Solid]: A list containing the cut result solid, or an empty list when
            there is no valid input. The result is returned as a list for consistency
            with other boolean operations.

    Usage:
        All boolean operations (union/cut/intersect) accept a mix of Solid and
        sequences; results are always returned as a list of Solid.
        `cut_rsolidlist(base, [tool_a, tool_b])` is valid input.
        If an earlier union returned multiple solids, keep that list and process each
        solid intentionally instead of collapsing it to `result[0]` without proof.
        If a later step truly requires one solid, first verify `len(results) == 1`.
        When a preceding union produced multiple tangent-only solids, adjust the part
        placement so the intended bodies overlap slightly, re-run the union, and only
        then unwrap the single result.

    Examples:
        body = make_box_rsolid(12, 4, 4, bottom_face_center=(0, 0, 0))
        slot = make_box_rsolid(2, 2, 6, bottom_face_center=(2, 1, -1))
        relief = make_cylinder_rsolid(radius=0.8, height=6, center=(8, 2, 2))

        results = cut_rsolidlist(body, [slot, relief])
        print(f"Cut result count: {len(results)}")

        # If a previous union returned multiple solids, keep the list and cut each part.
        tangent_parts = union_rsolidlist(
            body,
            [
                make_sphere_rsolid(2.0, center=(-2.0, 2.0, 2.0)),
                make_sphere_rsolid(2.0, center=(14.0, 2.0, 2.0)),
            ],
        )
        trimmed_parts = []
        for part in tangent_parts:
            trimmed_parts.extend(cut_rsolidlist(part, [slot, relief]))
    """
    try:
        # 递归展开所有参数：将Solid直接添加，将序列展开
        def _flatten_solids(args):
            result = []
            for arg in args:
                if isinstance(arg, Solid):
                    result.append(arg)
                elif isinstance(arg, Sequence) and not isinstance(arg, (str, bytes)):
                    result.extend(_flatten_solids(arg))
                else:
                    result.append(arg)  # 保留非Solid对象，后续会进行类型检查
            return result

        remaining = _flatten_solids(solids)

        if not remaining:
            return []

        if len(remaining) == 1:
            return [remaining[0]]

        for solid in remaining:
            if not isinstance(solid, Solid):
                raise ValueError("cut_rsolidlist函数只接受Solid类型的对象")

        # 从第一个实体开始，依次减去其他实体
        result_solid = remaining[0]

        for i in range(1, len(remaining)):
            candidate = remaining[i]

            s1 = result_solid.cq_solid
            s2 = candidate.cq_solid

            if s1.isNull() or s2.isNull():
                raise ValueError("输入实体无效，无法进行差集运算。")

            # 检查是否有交集
            intersection = intersect(s1, s2)
            if hasattr(intersection, "Solids") and intersection.Solids():
                intersection_solid = intersection.Solids()[0]
            else:
                intersection_solid = intersection

            intersection_obj = Solid(intersection_solid)

            if intersection_obj.get_volume() < 1e-12:
                # 没有有效的交集，跳过此次切割
                continue

            # 执行差集操作
            rv = cut(s1, s2)

            if hasattr(rv, "Solids") and rv.Solids():
                cq_result = rv.Solids()[0]
            else:
                cq_result = rv

            result_solid = Solid(cq_result)

        # 保留第一个实体的标签和元数据
        result_solid._tags = remaining[0]._tags.copy()
        result_solid._metadata = remaining[0]._metadata.copy()
        result_solid.add_tag("cut_result")

        # 记录布尔差集特征
        result = _record_boolean_feature(
            result_solids=[result_solid],
            operation="boolean_cut",
            input_solids=remaining,
        )

        return result
    except Exception as e:
        raise ValueError(f"差集运算失败: {e}. 请检查实体列表是否有效。")


def intersect_rsolidlist(*solids: Union[Solid, Sequence[Solid]]) -> List[Solid]:
    """Compute the boolean intersection of solids.

    Args:
        solids: One or more Solid objects or sequences of Solid. Nested sequences are
            flattened before processing.

    Returns:
        List[Solid]: A list containing the intersection result, or an empty list if
            the solids do not overlap. The result is returned as a list for
            consistency with other boolean operations.

    Usage:
        All boolean operations (union/cut/intersect) accept a mix of Solid and
        sequences; results are always returned as a list of Solid.
        `intersect_rsolidlist(body, [clip_a, clip_b])` is valid input.
        If an earlier union returned multiple solids, keep that list and intersect
        each solid intentionally instead of collapsing it to `result[0]`.
        If a later step truly requires one solid, first verify `len(results) == 1`.
        When a preceding union produced multiple tangent-only solids, adjust the part
        placement so the intended bodies overlap slightly, re-run the union, and only
        then unwrap the single result.

    Examples:
        body = make_box_rsolid(12, 4, 4, bottom_face_center=(0, 0, 0))
        clip_a = make_box_rsolid(8, 4, 4, bottom_face_center=(2, 0, 0))
        clip_b = make_box_rsolid(6, 6, 6, bottom_face_center=(3, -1, -1))

        results = intersect_rsolidlist(body, [clip_a, clip_b])
        print(f"Intersect result count: {len(results)}")

        # A previous union may return multiple solids; keep the list and intersect each part.
        tangent_parts = union_rsolidlist(
            body,
            [
                make_sphere_rsolid(2.0, center=(-2.0, 2.0, 2.0)),
                make_sphere_rsolid(2.0, center=(14.0, 2.0, 2.0)),
            ],
        )
        clipped_parts = []
        for part in tangent_parts:
            clipped_parts.extend(intersect_rsolidlist(part, clip_a))
    """
    try:
        # 递归展开所有参数：将Solid直接添加，将序列展开
        def _flatten_solids(args):
            result = []
            for arg in args:
                if isinstance(arg, Solid):
                    result.append(arg)
                elif isinstance(arg, Sequence) and not isinstance(arg, (str, bytes)):
                    result.extend(_flatten_solids(arg))
                else:
                    result.append(arg)  # 保留非Solid对象，后续会进行类型检查
            return result

        remaining = _flatten_solids(solids)

        if not remaining:
            return []

        for solid in remaining:
            if not isinstance(solid, Solid):
                raise ValueError("intersect_rsolidlist函数只接受Solid类型的对象")

        if len(remaining) == 1:
            # 只有一个实体，直接返回
            return [remaining[0]]

        # 从第一个实体开始，依次与后续实体进行交集运算
        result_solid = remaining[0]

        for i in range(1, len(remaining)):
            candidate = remaining[i]

            s1 = result_solid.cq_solid
            s2 = candidate.cq_solid

            if s1.isNull() or s2.isNull():
                raise ValueError("输入实体无效，无法进行交集运算。")

            rv = intersect(s1, s2)

            if hasattr(rv, "Solids") and rv.Solids():
                cq_result = rv.Solids()[0]
            else:
                cq_result = rv

            result_solid = Solid(cq_result)

            # 检查交集是否为空
            if result_solid.get_volume() < 1e-12:
                # 交集体积太小，视为无交集
                return []

        # 合并所有输入实体的标签和元数据
        all_tags: set = set()
        all_metadata: dict = {}
        for solid in remaining:
            all_tags = (
                all_tags.intersection(solid._tags) if all_tags else solid._tags.copy()
            )
            all_metadata.update(solid._metadata)

        result_solid._tags = all_tags
        result_solid._metadata = all_metadata
        result_solid.add_tag("intersect_result")

        result = _record_boolean_feature(
            result_solids=[result_solid],
            operation="boolean_intersect",
            input_solids=remaining,
        )
        return result
    except Exception as e:
        raise ValueError(f"交集运算失败: {e}. 请检查实体列表是否有效。")


# =============================================================================
# 导出函数
# =============================================================================


_EXPORTABLE_TYPES = (Solid, Face, Wire, Edge, Vertex)


def _normalize_shape_input(
    shapes: Union[AnyShape, Sequence[AnyShape]],
) -> List[AnyShape]:
    """Normalize export input into a flat list of shapes."""

    if isinstance(shapes, _EXPORTABLE_TYPES):
        return [shapes]

    if isinstance(shapes, Sequence) and not isinstance(shapes, (str, bytes)):
        normalized: List[AnyShape] = []
        for item in shapes:
            normalized.extend(_normalize_shape_input(cast(AnyShape, item)))
        return normalized

    raise ValueError(
        "export 函数只支持 Solid、Face、Wire、Edge、Vertex 或其序列类型的输入"
    )


def export_step(shapes: Union[AnyShape, Sequence[AnyShape]], filename: str) -> None:
    """Export shapes to STEP.

    Args:
        shapes: A single exportable shape or any nested sequence of exportable
            shapes. Lists of Solid are supported directly, including list results
            returned by boolean operations.
        filename: Output STEP file path.

    Returns:
        None: Writes the provided shapes into one STEP file.

    Usage:
        Use this function when you want to export one shape or many shapes into the
        same STEP file. Passing `List[Solid]` is valid and often preferred when a
        previous boolean operation returned multiple solids.

    Examples:
        main_body = make_box_rsolid(10, 4, 4, bottom_face_center=(0, 0, 0))
        left_cap = make_sphere_rsolid(2.0, center=(-2.0, 2.0, 2.0))
        right_cap = make_sphere_rsolid(2.0, center=(12.0, 2.0, 2.0))
        body_parts = union_rsolidlist(main_body, [left_cap, right_cap])

        # Export the full list directly; no need to collapse to body_parts[0].
        export_step(body_parts, "rounded_bar.step")
    """
    try:
        shape_list = _normalize_shape_input(shapes)

        # 创建CADQuery的Workplane并添加所有几何体
        wp = cq.Workplane()
        for shape in shape_list:
            if isinstance(shape, Solid):
                wp = wp.add(shape.cq_solid)
            elif isinstance(shape, Face):
                wp = wp.add(shape.cq_face)
            elif isinstance(shape, Wire):
                wp = wp.add(shape.cq_wire)
            elif isinstance(shape, Edge):
                wp = wp.add(shape.cq_edge)
            elif isinstance(shape, Vertex):
                wp = wp.add(shape.cq_vertex)
            else:
                raise ValueError(
                    "export_step函数只支持Solid、Face、Wire、Edge和Vertex类型的几何体"
                )

        # 导出到STEP文件
        cq.exporters.export(wp, filename)
    except Exception as e:
        raise ValueError(f"导出STEP文件失败: {e}. 请检查几何体和文件名是否有效。")


def export_stl(shapes: Union[AnyShape, Sequence[AnyShape]], filename: str) -> None:
    """Export shapes to STL.

    Args:
        shapes: A single Solid or Face, or any nested sequence of Solid/Face.
            Lists of Solid are supported directly, including list results returned
            by boolean operations.
        filename: Output STL file path.

    Returns:
        None: Writes the provided shapes into one STL file.

    Usage:
        Use this function when you want to export one solid or many solids/faces into
        the same STL file. Passing `List[Solid]` is valid and often preferred when a
        previous boolean operation returned multiple solids.

    Examples:
        main_body = make_box_rsolid(10, 4, 4, bottom_face_center=(0, 0, 0))
        left_cap = make_sphere_rsolid(2.0, center=(-2.0, 2.0, 2.0))
        right_cap = make_sphere_rsolid(2.0, center=(12.0, 2.0, 2.0))
        body_parts = union_rsolidlist(main_body, [left_cap, right_cap])

        # Export the list result directly.
        export_stl(body_parts, "rounded_bar.stl")
    """
    try:
        shape_list = _normalize_shape_input(shapes)

        # 创建CADQuery的Workplane并添加所有几何体
        wp = cq.Workplane()
        for shape in shape_list:
            if isinstance(shape, Solid):
                wp = wp.add(shape.cq_solid)
            elif isinstance(shape, Face):
                wp = wp.add(shape.cq_face)
            else:
                raise ValueError("export_stl函数只支持Solid和Face类型的几何体")

        # 导出到STL文件
        cq.exporters.export(wp, filename)
    except Exception as e:
        raise ValueError(f"导出STL文件失败: {e}. 请检查几何体和文件名是否有效。")


def render_screenshot_rpath(
    shapes: Union[Solid, Sequence[Solid]],
    output_path: str,
    highlight_tags: Optional[Sequence[str]] = None,
    tag_labels: Optional[Dict[str, str]] = None,
    image_size: Tuple[int, int] = (1400, 900),
    view: Union[Tuple[float, float], str] = "auto",
    show_axes: bool = True,
    show_legend: bool = True,
    zoom: float = 4.0,
) -> str:
    """Render a screenshot of shapes and save it to a file."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import to_rgb
        from mpl_toolkits.mplot3d import proj3d
        from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

        shape_list = _normalize_shape_input(shapes)
        solids = [shape for shape in shape_list if isinstance(shape, Solid)]
        if not solids:
            raise ValueError("render_screenshot_rpath 仅支持 Solid 类型")

        background = "#111111"
        base_color = (0.6, 0.62, 0.64)
        highlight_colors: Dict[str, Tuple[float, float, float]] = {}
        fit_mode = "model"
        axis_scale = 1.6
        axis_fit_weight = 0.0
        wireframe_only = False
        mesh_tolerance = 0.35
        mesh_angular_tolerance = 0.22

        highlight_list = [tag for tag in (highlight_tags or [])]
        labels = tag_labels or {}
        label_points: Dict[str, Tuple[float, float, float]] = {}

        all_polys: List[List[Tuple[float, float, float]]] = []
        all_colors: List[Tuple[float, float, float, float]] = []
        triangles: List[np.ndarray] = []
        tri_normals: List[np.ndarray] = []
        bbox_min = np.array([np.inf, np.inf, np.inf])
        bbox_max = np.array([-np.inf, -np.inf, -np.inf])

        base_rgb = np.array(to_rgb(base_color))
        palette = [
            "#f39c12",
            "#9b59b6",
            "#f1c40f",
            "#1abc9c",
            "#e67e22",
            "#e84393",
            "#16a085",
            "#d35400",
        ]
        highlight_colors = highlight_colors or {}
        highlight_color_map: Dict[str, np.ndarray] = {}
        for idx, tag in enumerate(highlight_list):
            if tag in highlight_colors:
                highlight_color_map[tag] = np.array(to_rgb(highlight_colors[tag]))
            else:
                highlight_color_map[tag] = np.array(to_rgb(palette[idx % len(palette)]))

        light_dirs = [
            np.array([0.7, -0.1, 0.7]),
            np.array([-0.6, 0.25, 0.32]),
            np.array([0.15, -0.9, 0.2]),
            np.array([0.0, 0.0, 1.0]),
            np.array([-0.15, -0.1, -0.98]),
        ]
        light_dirs = [vec / np.linalg.norm(vec) for vec in light_dirs]
        light_weights = [1.35, 0.4, 0.3, 0.18, 0.08]

        def _shade(normals: np.ndarray, color: np.ndarray) -> np.ndarray:
            ambient = 0.12
            intensity = np.full((normals.shape[0],), ambient, dtype=float)
            for w, light in zip(light_weights, light_dirs):
                intensity += w * np.maximum(0.0, normals @ light)
            intensity = np.clip(intensity, 0.0, 1.0)
            intensity = np.power(intensity, 1.35)
            shaded = color[None, :] * intensity[:, None]
            shaded = np.clip(shaded, 0.0, 1.0)
            alpha = np.ones((shaded.shape[0], 1))
            return np.hstack([shaded, alpha])

        for solid in solids:
            bb = solid.cq_solid.BoundingBox()
            bbox_min = np.minimum(bbox_min, np.array([bb.xmin, bb.ymin, bb.zmin]))
            bbox_max = np.maximum(bbox_max, np.array([bb.xmax, bb.ymax, bb.zmax]))

        model_min = bbox_min.copy()
        model_max = bbox_max.copy()

        axis_solids: List[Solid] = []
        axis_colors: Dict[str, np.ndarray] = {}
        axis_len_x = 0.0
        axis_len_y = 0.0
        axis_len_z = 0.0
        if show_axes:
            span = float(np.max(model_max - model_min))
            if span <= 0:
                span = 1.0
            axis_margin = span * 0.08
            axis_len_x_base = max(span * 0.3, max(0.0, bbox_max[0]) + axis_margin)
            axis_len_y_base = max(span * 0.3, max(0.0, bbox_max[1]) + axis_margin)
            axis_len_z_base = max(span * 0.3, max(0.0, bbox_max[2]) + axis_margin)
            axis_len_x = max(0.0, axis_len_x_base + axis_margin * (axis_scale - 1.0))
            axis_len_y = max(0.0, axis_len_y_base + axis_margin * (axis_scale - 1.0))
            axis_len_z = max(0.0, axis_len_z_base + axis_margin * (axis_scale - 1.0))
            axis_radius = max(
                span * 0.004, min(axis_len_x, axis_len_y, axis_len_z) * 0.02
            )
            head_len_factor = 0.2
            head_radius = axis_radius * 2.0

            def _axis_solid(axis: Tuple[float, float, float], length: float) -> Solid:
                shaft_len = length * (1.0 - head_len_factor)
                head_len = length * head_len_factor
                axis_vec = Vector(*axis)
                shaft = cq.Solid.makeCylinder(
                    axis_radius,
                    shaft_len,
                    Vector(0.0, 0.0, 0.0),
                    axis_vec,
                )
                cone = cq.Solid.makeCone(
                    head_radius,
                    0.0,
                    head_len,
                    Vector(*(np.array(axis) * shaft_len)),
                    axis_vec,
                )
                return Solid(shaft.fuse(cone, glue=True, tol=1e-7).clean())

            axis_x = _axis_solid((1.0, 0.0, 0.0), axis_len_x)
            axis_y = _axis_solid((0.0, 1.0, 0.0), axis_len_y)
            axis_z = _axis_solid((0.0, 0.0, 1.0), axis_len_z)

            axis_x.apply_tag("axis.x")
            axis_y.apply_tag("axis.y")
            axis_z.apply_tag("axis.z")
            axis_solids = [axis_x, axis_y, axis_z]
            axis_colors = {
                "axis.x": np.array([1.0, 0.35, 0.35]),
                "axis.y": np.array([0.35, 1.0, 0.55]),
                "axis.z": np.array([0.45, 0.65, 1.0]),
            }

        render_solids = solids + axis_solids

        for solid in render_solids:
            bb = solid.cq_solid.BoundingBox()
            if solid not in solids and fit_mode == "axes":
                bbox_min = np.minimum(bbox_min, np.array([bb.xmin, bb.ymin, bb.zmin]))
                bbox_max = np.maximum(bbox_max, np.array([bb.xmax, bb.ymax, bb.zmax]))

            highlight_tag = next(
                (tag for tag in highlight_list if solid.has_tag(tag)), None
            )
            axis_tag = next((tag for tag in axis_colors if solid.has_tag(tag)), None)
            if highlight_tag and highlight_tag not in label_points:
                label_points[highlight_tag] = (
                    0.5 * (bb.xmin + bb.xmax),
                    0.5 * (bb.ymin + bb.ymax),
                    0.5 * (bb.zmin + bb.zmax),
                )

            for face in solid.get_faces():
                face_tag = next(
                    (tag for tag in highlight_list if face.has_tag(tag)), None
                )
                face_highlight_tag = face_tag or highlight_tag
                if face_highlight_tag and face_tag and face_tag not in label_points:
                    center = face.get_center()
                    label_points[face_tag] = (center.x, center.y, center.z)

                verts, tri_indices = face.cq_face.tessellate(
                    mesh_tolerance, mesh_angular_tolerance
                )
                if not tri_indices:
                    continue

                vertices = np.array([[v.x, v.y, v.z] for v in verts], dtype=float)
                tris = np.array(tri_indices, dtype=int)
                tri_pts = vertices[tris]
                normals = np.cross(
                    tri_pts[:, 1] - tri_pts[:, 0], tri_pts[:, 2] - tri_pts[:, 0]
                )
                norms = np.linalg.norm(normals, axis=1)
                normals = np.divide(
                    normals,
                    norms[:, None],
                    out=np.zeros_like(normals),
                    where=norms[:, None] != 0,
                )

                if axis_tag:
                    color = axis_colors[axis_tag]
                elif face_highlight_tag:
                    color = highlight_color_map.get(face_highlight_tag, base_rgb)
                else:
                    color = base_rgb
                colors = _shade(normals, color)
                all_polys.extend(tri_pts.tolist())
                all_colors.extend(colors.tolist())
                triangles.extend(list(tri_pts))
                tri_normals.extend(list(normals))

        if not all_polys:
            raise ValueError("未生成任何可渲染三角面")

        fig = plt.figure(figsize=(image_size[0] / 100, image_size[1] / 100), dpi=100)
        fig.patch.set_facecolor(background)
        ax = fig.add_subplot(111, projection="3d")
        ax.set_facecolor(background)
        ax.set_axis_off()
        fig.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=1.0)
        ax.set_position((0.0, 0.0, 1.0, 1.0))

        if wireframe_only:
            face_colors = np.array(all_colors, dtype=float)
            face_colors[:, 3] = 0.0
            collection = Poly3DCollection(
                all_polys, facecolors=face_colors, linewidths=0.0
            )
        else:
            collection = Poly3DCollection(
                all_polys, facecolors=all_colors, linewidths=0.0
            )
        collection.set_edgecolor((0, 0, 0, 0))
        collection.set_zsort("average")
        ax.add_collection3d(collection)

        bbox_min = model_min
        bbox_max = model_max
        axis_origin = np.array([0.0, 0.0, 0.0])
        if show_axes:
            axis_points = np.array(
                [
                    axis_origin,
                    axis_origin + np.array([axis_len_x, 0.0, 0.0]),
                    axis_origin + np.array([0.0, axis_len_y, 0.0]),
                    axis_origin + np.array([0.0, 0.0, axis_len_z]),
                ]
            )
        else:
            axis_points = np.array([axis_origin])

        extent_min = model_min.copy()
        extent_max = model_max.copy()
        if fit_mode == "axes":
            extent_min = np.minimum(extent_min, axis_points.min(axis=0))
            extent_max = np.maximum(extent_max, axis_points.max(axis=0))
        elif fit_mode == "model":
            weight = float(axis_fit_weight)
            if weight > 0 and show_axes:
                weight = max(0.0, min(1.0, weight))
                axis_min = axis_points.min(axis=0)
                axis_max = axis_points.max(axis=0)
                extent_min = np.where(
                    axis_min < extent_min,
                    extent_min + (axis_min - extent_min) * weight,
                    extent_min,
                )
                extent_max = np.where(
                    axis_max > extent_max,
                    extent_max + (axis_max - extent_max) * weight,
                    extent_max,
                )
        else:
            raise ValueError("fit_mode 仅支持 'model' 或 'axes'")

        span = float(np.max(extent_max - extent_min))
        if span <= 0:
            span = 1.0
        if zoom <= 0:
            raise ValueError("zoom 必须大于 0")
        size = extent_max - extent_min
        pad_ratio = 0.08
        pad_min = span * 0.01
        pad_vec = np.maximum(size * (pad_ratio / zoom), pad_min)
        min_extent = extent_min - pad_vec
        max_extent = extent_max + pad_vec
        ax.set_xlim(min_extent[0], max_extent[0])
        ax.set_ylim(min_extent[1], max_extent[1])
        ax.set_zlim(min_extent[2], max_extent[2])
        try:
            ax.set_box_aspect(max_extent - min_extent)
        except Exception:
            pass

        def _resolve_view(view_spec):
            if isinstance(view_spec, str):
                token = view_spec.strip().lower()
                spans = bbox_max - bbox_min
                if token == "auto":
                    azim = 35.0 if spans[0] >= spans[1] else 125.0
                    elev = 22.0 if spans[2] <= max(spans[0], spans[1]) else 35.0
                    return elev, azim
                if token in {"iso", "isometric"}:
                    return 25.0, 35.0
                if token == "top":
                    return 90.0, 0.0
                if token == "bottom":
                    return -90.0, 0.0
                if token == "front":
                    return 0.0, -90.0
                if token == "back":
                    return 0.0, 90.0
                if token == "left":
                    return 0.0, 180.0
                if token == "right":
                    return 0.0, 0.0
                if token == "front_right":
                    return 20.0, -45.0
                if token == "front_left":
                    return 20.0, 135.0
                if token == "rear_right":
                    return 20.0, 45.0
                if token == "rear_left":
                    return 20.0, -135.0
                raise ValueError(f"不支持的 view 预设: {view_spec}")

            if isinstance(view_spec, (list, tuple)) and len(view_spec) == 2:
                return float(view_spec[0]), float(view_spec[1])

            raise ValueError("view 必须为 (elev, azim) 或预设名称")

        elev, azim = _resolve_view(view)
        ax.view_init(elev=elev, azim=azim)

        if triangles:
            elev_rad = math.radians(elev)
            azim_rad = math.radians(azim)
            view_dir = np.array(
                [
                    math.cos(elev_rad) * math.cos(azim_rad),
                    math.cos(elev_rad) * math.sin(azim_rad),
                    math.sin(elev_rad),
                ],
                dtype=float,
            )
            edge_quant = max(mesh_tolerance * 0.001, 1e-6)

            def _quantize_point(point: np.ndarray) -> Tuple[float, float, float]:
                snapped = np.round(point / edge_quant) * edge_quant
                return (float(snapped[0]), float(snapped[1]), float(snapped[2]))

            edge_to_tris: Dict[
                Tuple[Tuple[float, float, float], Tuple[float, float, float]],
                List[int],
            ] = {}
            edge_to_seg: Dict[
                Tuple[Tuple[float, float, float], Tuple[float, float, float]],
                Tuple[np.ndarray, np.ndarray],
            ] = {}

            for tri_idx, tri in enumerate(triangles):
                for i0, i1 in ((0, 1), (1, 2), (2, 0)):
                    p0 = tri[i0]
                    p1 = tri[i1]
                    q0 = _quantize_point(p0)
                    q1 = _quantize_point(p1)
                    key = (q0, q1) if q0 <= q1 else (q1, q0)
                    edge_to_tris.setdefault(key, []).append(tri_idx)
                    edge_to_seg.setdefault(key, (p0, p1))

            hard_segments: List[np.ndarray] = []
            silhouette_segments: List[np.ndarray] = []
            angle_threshold = max(math.radians(40.0), mesh_angular_tolerance * 3.0)

            for key, tri_indices in edge_to_tris.items():
                seg = edge_to_seg[key]
                if len(tri_indices) == 1:
                    silhouette_segments.append(np.array(seg, dtype=float))
                    continue

                normals = [tri_normals[i] for i in tri_indices]
                facing = [float(np.dot(n, view_dir)) for n in normals]
                if min(facing) <= 0.0 <= max(facing):
                    silhouette_segments.append(np.array(seg, dtype=float))

                max_angle = 0.0
                for i in range(len(normals)):
                    for j in range(i + 1, len(normals)):
                        dot = float(np.clip(np.dot(normals[i], normals[j]), -1.0, 1.0))
                        angle = math.acos(dot)
                        if angle > max_angle:
                            max_angle = angle
                if max_angle >= angle_threshold:
                    hard_segments.append(np.array(seg, dtype=float))

            if hard_segments:
                hard_collection = Line3DCollection(
                    hard_segments,
                    colors=[(0.62, 0.64, 0.68, 0.75)],
                    linewidths=0.6,
                )
                ax.add_collection3d(hard_collection)
            if silhouette_segments:
                sil_collection = Line3DCollection(
                    silhouette_segments,
                    colors=[(0.88, 0.89, 0.92, 0.9)],
                    linewidths=1.1,
                )
                ax.add_collection3d(sil_collection)

        def _project_to_fig(point: Tuple[float, float, float]) -> Tuple[float, float]:
            x2, y2, _ = proj3d.proj_transform(
                point[0], point[1], point[2], ax.get_proj()
            )
            display = ax.transData.transform((x2, y2))
            return tuple(fig.transFigure.inverted().transform(display))

        def _clamp(value: float, low: float, high: float) -> float:
            return max(low, min(high, value))

        if show_axes:
            axis_label_offset = 0.008
            axis_label_specs = (
                ("X", axis_origin + np.array([axis_len_x, 0.0, 0.0]), "axis.x"),
                ("Y", axis_origin + np.array([0.0, axis_len_y, 0.0]), "axis.y"),
                ("Z", axis_origin + np.array([0.0, 0.0, axis_len_z]), "axis.z"),
            )
            for label, point, tag in axis_label_specs:
                color = axis_colors.get(tag, np.array([1.0, 1.0, 1.0]))
                xfig, yfig = _project_to_fig(
                    (float(point[0]), float(point[1]), float(point[2]))
                )
                xfig = _clamp(xfig + axis_label_offset, 0.02, 0.98)
                yfig = _clamp(yfig + axis_label_offset, 0.02, 0.98)
                fig.text(
                    xfig,
                    yfig,
                    label,
                    color=color,
                    fontsize=16,
                    ha="left",
                    va="center",
                )

        if show_legend and (highlight_list or show_axes):
            y = 0.98
            if highlight_list:
                for tag in highlight_list:
                    label = labels.get(tag, tag)
                    color = highlight_color_map.get(tag, base_rgb)
                    fig.text(
                        0.02,
                        y,
                        f"■ {label}",
                        color=color,
                        fontsize=10,
                        ha="left",
                        va="top",
                    )
                    y -= 0.035

            if show_axes:
                for label, color in (
                    ("+X", axis_colors.get("axis.x", np.array([1.0, 0.35, 0.35]))),
                    ("+Y", axis_colors.get("axis.y", np.array([0.35, 1.0, 0.55]))),
                    ("+Z", axis_colors.get("axis.z", np.array([0.45, 0.65, 1.0]))),
                ):
                    fig.text(
                        0.02,
                        y,
                        f"■ {label}",
                        color=color,
                        fontsize=10,
                        ha="left",
                        va="top",
                    )
                    y -= 0.035

        label_offset = 0.012
        for idx, (tag, point) in enumerate(label_points.items()):
            label = labels.get(tag, tag)
            xfig, yfig = _project_to_fig(point)
            xfig = _clamp(xfig + label_offset, 0.02, 0.98)
            yfig = _clamp(yfig + label_offset, 0.02, 0.98)
            yfig = _clamp(yfig - idx * 0.02, 0.02, 0.98)
            fig.text(
                xfig,
                yfig,
                label,
                color="#ffd27a",
                fontsize=10,
                ha="left",
                va="center",
                bbox=dict(
                    boxstyle="round,pad=0.2", fc="#111111", ec="#ffaa33", alpha=0.9
                ),
            )

        plt.savefig(output_path, facecolor=background)
        plt.close(fig)
        return output_path
    except Exception as e:
        raise ValueError(f"渲染截图失败: {e}.")


# =============================================================================
# 高级特征操作函数
# =============================================================================


def fillet_rsolid(solid: Solid, edges: List[Edge], radius: float) -> Solid:
    """Apply fillets to selected solid edges."""
    try:
        if radius <= 0:
            raise ValueError("圆角半径必须大于0")

        # 转换为CADQuery边对象
        cq_edges = [edge.cq_edge for edge in edges]

        # 执行圆角操作
        cq_result = solid.cq_solid.fillet(radius, cq_edges)
        result = Solid(cq_result)

        # 复制标签和元数据
        result._tags = solid._tags.copy()
        result._metadata = solid._metadata.copy()
        result = _record_modifier_feature(
            result_solid=result,
            operation="fillet",
            base_solid=solid,
            parameters={
                "radius": radius,
                "edge_indices": _find_edge_indices(solid, edges),
                "edge_signatures": _edge_signatures(edges),
            },
            feature_type=FeatureType.FILLET,
        )

        return result
    except Exception as e:
        raise ValueError(f"圆角操作失败: {e}. 请检查实体、边和半径是否有效。")


def chamfer_rsolid(solid: Solid, edges: List[Edge], distance: float) -> Solid:
    """Apply chamfers to selected solid edges."""
    try:
        if distance <= 0:
            raise ValueError("倒角距离必须大于0")

        # 转换为CADQuery边对象
        cq_edges = [edge.cq_edge for edge in edges]

        # 执行倒角操作
        cq_result = solid.cq_solid.chamfer(distance, None, cq_edges)
        result = Solid(cq_result)

        # 复制标签和元数据
        result._tags = solid._tags.copy()
        result._metadata = solid._metadata.copy()
        result = _record_modifier_feature(
            result_solid=result,
            operation="chamfer",
            base_solid=solid,
            parameters={
                "distance": distance,
                "edge_indices": _find_edge_indices(solid, edges),
                "edge_signatures": _edge_signatures(edges),
            },
            feature_type=FeatureType.CHAMFER,
        )

        return result
    except Exception as e:
        raise ValueError(f"倒角操作失败: {e}. 请检查实体、边和距离是否有效。")


def shell_rsolid(solid: Solid, faces_to_remove: List[Face], thickness: float) -> Solid:
    """Shell a solid to create a hollow part."""
    try:
        if thickness <= 0:
            raise ValueError("壁厚必须大于0")

        # 转换为CADQuery面对象
        cq_faces = (
            [face.cq_face for face in faces_to_remove] if faces_to_remove else None
        )

        # 执行抽壳操作
        cq_result = solid.cq_solid.shell(cq_faces, thickness)
        result = Solid(cq_result)

        # 复制标签和元数据
        result._tags = solid._tags.copy()
        result._metadata = solid._metadata.copy()
        result = _record_modifier_feature(
            result_solid=result,
            operation="shell",
            base_solid=solid,
            parameters={
                "thickness": thickness,
                "face_indices": _find_face_indices(solid, faces_to_remove),
            },
            feature_type=FeatureType.SHELL,
        )

        return result
    except Exception as e:
        raise ValueError(f"抽壳操作失败: {e}. 请检查实体、面和壁厚是否有效。")


def loft_rsolid(profiles: List[Wire], ruled: bool = False) -> Solid:
    """Create a solid by lofting multiple profiles."""
    try:
        if len(profiles) < 2:
            raise ValueError("放样至少需要2个轮廓")

        # 转换为CADQuery线对象
        cq_wires = [profile.cq_wire for profile in profiles]

        # 执行放样操作
        cq_result = cq.Solid.makeLoft(cq_wires, ruled)
        result = Solid(cq_result)

        # 合并所有轮廓的标签和元数据
        all_tags = set()
        all_metadata = {}
        for profile in profiles:
            all_tags.update(profile._tags)
            all_metadata.update(profile._metadata)

        result._tags = all_tags
        result._metadata = all_metadata
        result = _record_generic_feature(
            output_shape=result,
            name="Loft_Profile_Stack",
            operation="loft",
            feature_type=FeatureType.LOFT,
            inputs=profiles,
            parameters={"ruled": ruled, "profile_count": len(profiles)},
            description=f"Lofted {len(profiles)} profiles",
        )

        return result
    except Exception as e:
        raise ValueError(f"放样操作失败: {e}. 请检查轮廓是否有效。")


def sweep_rsolid(profile: Face, path: Wire, is_frenet: bool = False) -> Solid:
    """Create a solid by sweeping a profile along a path."""
    make_solid = True  # 默认创建实体
    try:
        # 执行扫掠操作
        cq_result = cq.Solid.sweep(
            profile.cq_face, path.cq_wire, makeSolid=make_solid, isFrenet=is_frenet
        )

        result = Solid(cq_result)

        # 合并轮廓和路径的标签和元数据
        result._tags = profile._tags.union(path._tags)
        result._metadata = {**profile._metadata, **path._metadata}
        result = _record_generic_feature(
            output_shape=result,
            name="Sweep_Profile_Along_Path",
            operation="sweep",
            feature_type=FeatureType.SWEEP,
            inputs=[profile, path],
            parameters={"is_frenet": is_frenet},
            description="Swept profile along path",
        )

        return result
    except Exception as e:
        raise ValueError(f"扫掠操作失败: {e}. 请检查轮廓和路径是否有效。")


def linear_pattern_rsolidlist(
    shape: AnyShape, direction: Tuple[float, float, float], count: int, spacing: float
) -> List[Solid]:
    """Create a linear pattern of solids."""
    try:
        if count <= 0:
            raise ValueError("阵列数量必须大于0")
        if spacing <= 0:
            raise ValueError("阵列间距必须大于0")

        cs = get_current_cs()
        global_direction = cs.transform_point(np.array(direction)) - cs.origin
        direction_vec = Vector(*global_direction).normalized()

        if not isinstance(shape, Solid):
            raise ValueError(
                "linear_pattern_rsolidlist currently only supports Solid inputs"
            )

        shapes: List[Solid] = []
        for i in range(count):
            offset = direction_vec * (spacing * i)
            cq_shape = shape.cq_solid.copy().translate(offset)
            patterned_shape = Solid(cq_shape)
            patterned_shape._tags = shape._tags.copy()
            patterned_shape._metadata = shape._metadata.copy()
            patterned_shape = _record_generic_feature(
                output_shape=patterned_shape,
                name=f"LinearPattern_{i + 1}",
                operation="linear_pattern",
                feature_type=FeatureType.PATTERN,
                inputs=[shape],
                parameters={
                    "direction": direction,
                    "count": count,
                    "spacing": spacing,
                    "instance_index": i,
                    "offset": (offset.x, offset.y, offset.z),
                },
                description=f"Linear pattern instance {i + 1} of {count}",
            )
            shapes.append(patterned_shape)

        rv = []
        for i, s in enumerate(shapes):
            s.add_tag(f"linear_pattern_{i + 1}")
            rv.append(s)

        return rv

    except Exception as e:
        raise ValueError(f"线性阵列失败: {e}. 请检查参数是否有效。")


def radial_pattern_rsolidlist(
    shape: AnyShape,
    center: Tuple[float, float, float],
    axis: Tuple[float, float, float],
    count: int,
    total_rotation_angle: float,
) -> List[Solid]:
    """Create a radial pattern of solids."""
    try:
        if count <= 0:
            raise ValueError("阵列数量必须大于0")
        if total_rotation_angle <= 0:
            raise ValueError("角度必须大于0")

        if not isinstance(shape, Solid):
            raise ValueError(
                "radial_pattern_rsolidlist currently only supports Solid inputs"
            )

        cs = get_current_cs()
        global_center = cs.transform_point(np.array(center))
        global_axis = cs.transform_point(np.array(axis)) - cs.origin
        center_vec = Vector(*global_center)
        axis_vec = Vector(*global_axis).normalized()

        shapes: List[Solid] = []
        angle_step = total_rotation_angle / count

        for i in range(count):
            rotation_angle = angle_step * i
            cq_shape = shape.cq_solid.copy().rotate(center_vec, axis_vec, rotation_angle)
            patterned_shape = Solid(cq_shape)
            patterned_shape._tags = shape._tags.copy()
            patterned_shape._metadata = shape._metadata.copy()
            patterned_shape = _record_generic_feature(
                output_shape=patterned_shape,
                name=f"RadialPattern_{i + 1}",
                operation="radial_pattern",
                feature_type=FeatureType.PATTERN,
                inputs=[shape],
                parameters={
                    "center": center,
                    "axis": axis,
                    "count": count,
                    "total_rotation_angle": total_rotation_angle,
                    "instance_index": i,
                    "angle": rotation_angle,
                },
                description=f"Radial pattern instance {i + 1} of {count}",
            )
            shapes.append(patterned_shape)

        rv = []
        for i, s in enumerate(shapes):
            s.add_tag(f"radial_pattern_{i + 1}")
            rv.append(s)

        return rv
    except Exception as e:
        raise ValueError(f"径向阵列失败: {e}. 请检查参数是否有效。")


def mirror_shape(
    shape: AnyShape,
    plane_origin: Tuple[float, float, float],
    plane_normal: Tuple[float, float, float],
) -> AnyShape:
    """Mirror a shape across a plane."""
    try:
        cs = get_current_cs()
        global_origin = cs.transform_point(np.array(plane_origin))
        global_normal = cs.transform_vector(np.array(plane_normal))

        # 确保法向量不是零向量
        if np.linalg.norm(global_normal) < 1e-10:
            raise ValueError("镜像平面法向量不能是零向量")

        cq_origin = Vector(global_origin[0], global_origin[1], global_origin[2])
        cq_normal = Vector(global_normal[0], global_normal[1], global_normal[2])

        if isinstance(shape, Vertex):
            new_shape = Vertex(shape.cq_vertex.mirror(cq_normal, cq_origin))
        elif isinstance(shape, Edge):
            new_shape = Edge(shape.cq_edge.mirror(cq_normal, cq_origin))
        elif isinstance(shape, Wire):
            new_shape = Wire(shape.cq_wire.mirror(cq_normal, cq_origin))
        elif isinstance(shape, Face):
            new_shape = Face(shape.cq_face.mirror(cq_normal, cq_origin))
        elif isinstance(shape, Solid):
            new_shape = Solid(shape.cq_solid.mirror(cq_normal, cq_origin))
        else:
            raise ValueError(f"暂不支持镜像 {type(shape).__name__} 类型的几何体")

        # 复制标签和元数据
        new_shape._tags = shape._tags.copy()
        new_shape._metadata = shape._metadata.copy()
        new_shape.add_tag("mirrored")

        from .feature_history import FeatureType

        new_shape = _record_transformed_feature(
            shape=new_shape,
            operation="mirror_shape",
            input_shapes=[shape],
            parameters={
                "plane_origin": plane_origin,
                "plane_normal": plane_normal,
            },
            feature_type=FeatureType.TRANSFORM,
        )

        return new_shape
    except Exception as e:
        raise ValueError(f"镜像操作失败: {e}. 请检查几何体和镜像平面是否有效。")


def helical_sweep_rsolid(
    profile: Wire,
    pitch: float,
    height: float,
    radius: float,
    center: Tuple[float, float, float] = (0, 0, 0),
    dir: Tuple[float, float, float] = (0, 0, 1),
) -> Solid:
    """Create a solid by sweeping a profile along a helical path."""
    try:
        if pitch <= 0:
            raise ValueError("螺距必须大于0")
        if height <= 0:
            raise ValueError("高度必须大于0")
        if radius <= 0:
            raise ValueError("半径必须大于0")

        cs = get_current_cs()
        global_center = cs.transform_point(np.array(center))
        global_dir = cs.transform_point(np.array(dir)) - cs.origin

        center_vec = Vector(*global_center)
        dir_vec = Vector(*global_dir).normalized()

        # 复制profile以避免修改原始轮廓
        corrected_profile = Wire(profile.cq_wire.copy())

        # 将Wire转换为Face用于扫掠
        try:
            profile_face = cq.Face.makeFromWires(corrected_profile.cq_wire)
        except Exception as _:
            raise ValueError("螺旋扫掠轮廓必须是闭合的")

        # 1. 矫正profile的法向量：确保法向量朝向X轴正方向
        # 获取profile的法向量（在面的中心点）
        try:
            # 获取face的法向量，normalAt返回(Vector, Vector)，取第一个
            profile_normal = profile_face.normalAt(0.5, 0.5)[0]
        except Exception as _:
            try:
                profile_normal = profile_face.normalAt(0, 0)[0]
            except Exception as _:
                # 最后的fallback，假设法向量为Z轴方向
                profile_normal = Vector(0, 0, 1)

        # 定义目标法向量：Y轴正方向
        target_normal = Vector(0, 1, 0)

        # 检查当前法向量与目标法向量的夹角
        dot_product = profile_normal.dot(target_normal)

        # 如果法向量不朝向X轴正方向，需要旋转
        if abs(dot_product) < 0.99:  # 容差，允许约8度的偏差
            # 计算旋转轴（叉积）
            rotation_axis = profile_normal.cross(target_normal)

            # 如果法向量与X轴相反（dot_product < 0），需要180度旋转
            if dot_product < -0.99:
                # 使用Y轴或Z轴作为旋转轴
                rotation_axis = Vector(0, 1, 0)
                rotation_angle = math.pi
            elif rotation_axis.Length > 1e-6:
                # 计算旋转角度
                rotation_angle = math.acos(max(-1, min(1, abs(dot_product))))
                rotation_axis = rotation_axis.normalized()
            else:
                # 如果叉积为零向量，说明已经平行，不需要旋转
                rotation_angle = 0
                rotation_axis = Vector(0, 0, 1)

            # 如果需要旋转
            if rotation_angle > 1e-6:
                # 获取profile的中心点作为旋转中心
                profile_center = profile_face.Center()
                rotation_center = Vector(
                    profile_center.x, profile_center.y, profile_center.z
                )

                # 应用旋转
                profile_face = profile_face.rotate(
                    rotation_center, rotation_axis, math.degrees(rotation_angle)
                )

        # 2. 矫正profile的位置：将profile移动到指定半径的位置
        # 获取旋转后的profile中心点
        profile_center = profile_face.Center()

        # 计算当前profile中心到旋转中心的距离
        current_center = Vector(profile_center.x, profile_center.y, profile_center.z)
        spiral_center = center_vec

        # 计算在垂直于旋转轴的平面上的投影
        to_profile = current_center - spiral_center
        projection_on_axis = to_profile.dot(dir_vec) * dir_vec
        radial_vector = to_profile - projection_on_axis

        # 如果radial_vector太小，默认使用X轴方向
        if radial_vector.Length < 1e-6:
            radial_vector = Vector(1, 0, 0)

        # 归一化径向向量并缩放到目标半径
        radial_direction = radial_vector.normalized()
        target_position = spiral_center + radial_direction * radius + projection_on_axis

        # 计算平移向量
        translation = target_position - current_center

        # 应用平移
        profile_face = profile_face.translate(translation)

        # 创建螺旋路径
        helix = cq.Wire.makeHelix(pitch, height, radius, center_vec, dir_vec)

        # 沿螺旋路径扫掠
        cq_result = cq.Solid.sweep(profile_face, helix, makeSolid=True, isFrenet=True)
        result = Solid(cq_result)

        # 复制轮廓的标签和元数据
        result._tags = profile._tags.copy()
        result._metadata = profile._metadata.copy()
        result.add_tag("helical_sweep")
        result = _record_generic_feature(
            output_shape=result,
            name="HelicalSweep_Profile",
            operation="helical_sweep",
            feature_type=FeatureType.SWEEP,
            inputs=[profile],
            parameters={
                "pitch": pitch,
                "height": height,
                "radius": radius,
                "center": center,
                "dir": dir,
            },
            description="Swept profile along a helix",
        )

        return result
    except Exception as e:
        raise ValueError(f"螺旋扫掠失败: {e}. 请检查参数是否有效。")
