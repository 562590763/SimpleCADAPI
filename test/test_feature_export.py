"""
Comprehensive SimpleCADAPI feature-history and FreeCAD export validation.

This script focuses on grouped export scenarios instead of one-test-per-feature:
1. Creation features: primitives, point, spline, field surface
2. Advanced modeled features: extrude, revolve, fillet, chamfer, shell
3. Extended features: intersect, loft, sweep, helical sweep, patterns
4. Boolean composition flow: transforms + boolean modeling
5. Hierarchical assembly flow: parent-child parts + solved placements

Run with:
    uv run python test/test_feature_export.py
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence


def _configure_stdio() -> None:
    """Force UTF-8 output on Windows terminals when possible."""
    if sys.platform != "win32":
        return

    import codecs

    if sys.stdout.encoding != "utf-8":
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    if sys.stderr.encoding != "utf-8":
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


_configure_stdio()

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
OUTPUT_DIR = PROJECT_ROOT / "sandbox" / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

print("=" * 80)
print("SimpleCADAPI Comprehensive Feature Export Test")
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

print("\n【模块导入】")
try:
    import simplecadapi as scad
    from simplecadapi import (
        FeatureExporter,
        create_new_history,
        export_assembly_result_to_freecad_script,
        export_feature_history_to_json,
        generate_freecad_assembly_script,
        get_global_history,
    )

    print("✓ 所有模块导入成功")
except ImportError as exc:
    print(f"✗ 导入失败: {exc}")
    sys.exit(1)


all_tests_passed = True
test_results: list[dict[str, str]] = []
generated_script_paths: list[Path] = []


def load_json_file(filepath: Path) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def assert_feature_operations(json_path: Path, required_operations: Sequence[str]) -> None:
    data = load_json_file(json_path)
    operations = [feature.get("operation") for feature in data.get("features", [])]
    missing = [operation for operation in required_operations if operation not in operations]
    if missing:
        raise AssertionError(
            f"{json_path.name} 缺少特征操作: {', '.join(missing)}; 当前操作: {operations}"
        )


def assert_script_contains(script_path: Path, required_fragments: Sequence[str]) -> None:
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    missing = [fragment for fragment in required_fragments if fragment not in content]
    if missing:
        raise AssertionError(f"{script_path.name} 缺少脚本片段: {', '.join(missing)}")


def export_history_bundle(
    base_name: str,
    *,
    include_geometry_json: bool = False,
) -> tuple:
    """Export current global history to JSON and a FreeCAD script."""
    history = get_global_history()
    if history is None:
        raise AssertionError("当前没有可导出的 feature history")

    json_path = OUTPUT_DIR / f"{base_name}.json"
    script_path = OUTPUT_DIR / f"{base_name}.fcstd.py"

    export_feature_history_to_json(history, str(json_path))

    exporter = FeatureExporter(history)
    geometry_json_path = None
    if include_geometry_json:
        geometry_json_path = OUTPUT_DIR / f"{base_name}.geometry.json"
        exporter.to_json(str(geometry_json_path), include_geometry=True)

    script = exporter._generate_freecad_script()
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    if script_path not in generated_script_paths:
        generated_script_paths.append(script_path)

    return history, json_path, script_path, geometry_json_path


def print_export_summary(
    history,
    json_path: Path,
    script_path: Path,
    geometry_json_path: Path | None = None,
) -> None:
    print(f"  特征数量: {len(history.features)}")
    print(f"  JSON 导出: {json_path}")
    if geometry_json_path is not None:
        print(f"  带几何 JSON: {geometry_json_path}")
    print(f"  FreeCAD 脚本: {script_path}")


def run_test(test_name: str, test_func: Callable[[], None]) -> None:
    """Run one test and record the result."""
    global all_tests_passed

    print(f"\n【测试: {test_name}】")
    try:
        test_func()
        print(f"✓ {test_name} 通过")
        test_results.append({"name": test_name, "status": "PASS"})
    except Exception as exc:
        print(f"✗ {test_name} 失败: {exc}")
        traceback.print_exc()
        test_results.append({"name": test_name, "status": "FAIL", "error": str(exc)})
        all_tests_passed = False


# =============================================================================
# 测试 1: 创建类特征导出
# =============================================================================
def test_creation_feature_export() -> None:
    create_new_history("创建类特征导出测试")

    box = scad.make_box_rsolid(50, 30, 20)
    cylinder = scad.make_cylinder_rsolid(radius=10, height=40)
    sphere = scad.make_sphere_rsolid(radius=15)
    cone = scad.make_cone_rsolid(bottom_radius=15, top_radius=5, height=25)
    torus = scad.make_torus_rsolid(radius1=20, radius2=5)
    point = scad.make_point_rvertex(5, 10, 15)
    segment_edge = scad.make_segment_redge((0, 0, 0), (15, 0, 0))
    segment_wire = scad.make_segment_rwire((0, 5, 0), (15, 5, 0))
    circle_wire = scad.make_circle_rwire(center=(25, 0, 0), radius=6)
    circle_face = scad.make_circle_rface((0, 0, 0), 8)
    rectangle_face = scad.make_rectangle_rface(18, 12)
    face_from_wire = scad.make_face_from_wire_rface(scad.make_rectangle_rwire(14, 6))
    spline_wire = scad.make_spline_rwire(
        [(0, 0, 0), (10, 5, 0), (20, -5, 0), (30, 0, 0)],
        closed=False,
    )

    sphere_field = scad.field.make_sphere_rscalarfield((0.0, 0.0, 0.0), 10.0)
    field_solid = scad.make_field_surface_rsolid(
        sphere_field,
        bounds=((-12.0, -12.0, -12.0), (12.0, 12.0, 12.0)),
        resolution=(10, 10, 10),
        iso=0.0,
    )

    print(f"  立方体体积: {box.get_volume():.2f}")
    print(f"  圆柱体积: {cylinder.get_volume():.2f}")
    print(f"  球体体积: {sphere.get_volume():.2f}")
    print(f"  圆锥体积: {cone.get_volume():.2f}")
    print(f"  圆环体积: {torus.get_volume():.2f}")
    print(f"  点创建成功: {point}")
    print(f"  线段边创建成功: {segment_edge}")
    print(f"  线段线创建成功: {segment_wire}")
    print(f"  圆面创建成功: {circle_face}")
    print(f"  矩形面创建成功: {rectangle_face}")
    print(f"  由线生成面成功: {face_from_wire}")
    print(f"  样条线创建成功: {spline_wire}")
    print(f"  场函数等势面体积: {field_solid.get_volume():.2f}")

    history, json_path, script_path, _ = export_history_bundle("test_creation_feature_export")

    assert_feature_operations(
        json_path,
        [
            "make_box",
            "make_cylinder",
            "make_sphere",
            "make_cone",
            "make_torus",
            "make_point",
            "make_segment",
            "make_rectangle",
            "make_circle",
            "make_face",
            "make_spline",
            "make_field_surface",
        ],
    )
    assert_script_contains(
        script_path,
        [
            "# Box:",
            "# Cylinder:",
            "# Sphere:",
            "# Sketch:",
            "# Face:",
            "# Field Surface:",
            "Part.Vertex(",
            "Part.Wire([",
            "Part.Face(",
            "Part.BSplineCurve([",
            "importBrepFromString",
        ],
    )

    print_export_summary(history, json_path, script_path)


# =============================================================================
# 测试 2: 高级建模特征导出
# =============================================================================
def test_advanced_feature_export() -> None:
    create_new_history("高级建模特征导出测试")

    rect = scad.make_rectangle_rwire(width=80, height=60)
    extruded = scad.extrude_rsolid(rect, direction=(0, 0, 1), distance=30)

    circle_wire = scad.make_circle_rwire(center=(100, 0, 0), radius=25)
    revolved = scad.revolve_rsolid(circle_wire, axis=(0, 1, 0), angle=360)

    profile_wire = scad.make_spline_rwire(
        [(0, 0, 0), (8, 3, 0), (16, -2, 0), (24, 0, 0)],
        closed=False,
    )
    moved_wire = scad.translate_shape(profile_wire, (5, 0, 0))
    rotated_wire = scad.rotate_shape(moved_wire, 30, (0, 0, 1), (0, 0, 0))
    scaled_wire = scad.scale_shape(rotated_wire, 1.2)
    mirrored_wire = scad.mirror_shape(scaled_wire, (0, 0, 0), (1, 0, 0))

    base_body = scad.make_box_rsolid(100, 80, 50)
    base_edges = base_body.get_edges()
    filleted = scad.fillet_rsolid(base_body, base_edges[:4], 3.0)
    chamfered = scad.chamfer_rsolid(base_body, base_edges[4:8], 2.0)
    top_faces = [face for face in base_body.get_faces() if face.has_tag("top")]
    shelled = scad.shell_rsolid(base_body, top_faces[:1], 2.0)

    print("  创建矩形轮廓并拉伸")
    print(f"  拉伸后体积: {extruded.get_volume():.2f}")
    print("  创建圆形轮廓并旋转")
    print(f"  旋转后体积: {revolved.get_volume():.2f}")
    print(f"  非 Solid 变换后线框: {mirrored_wire}")
    print(f"  基础体体积: {base_body.get_volume():.2f}")
    print(f"  圆角后体积: {filleted.get_volume():.2f}")
    print(f"  倒角后体积: {chamfered.get_volume():.2f}")
    print(f"  抽壳后体积: {shelled.get_volume():.2f}")

    history, json_path, script_path, _ = export_history_bundle("test_advanced_feature_export")

    assert_feature_operations(
        json_path,
        [
            "make_rectangle",
            "extrude",
            "make_circle",
            "revolve",
            "make_spline",
            "translate_shape",
            "rotate_shape",
            "scale_shape",
            "mirror_shape",
            "make_box",
            "fillet",
            "chamfer",
            "shell",
        ],
    )
    assert_script_contains(
        script_path,
        [
            "# Extrude:",
            "# Revolve:",
            "# Translate:",
            "# Rotate:",
            "# Scale:",
            "# Mirror:",
            "# Fillet:",
            "# Chamfer:",
            "# Shell:",
            "App::Link",
            "Part::Mirroring",
            ".scale(",
            ".makeFillet(",
            ".makeChamfer(",
            ".makeThickness(",
        ],
    )

    print_export_summary(history, json_path, script_path)


# =============================================================================
# 测试 3: 扩展特征导出
# =============================================================================
def test_generation_pattern_export() -> None:
    create_new_history("扩展特征导出测试")

    intersect_a = scad.make_box_rsolid(40, 40, 40)
    intersect_b = scad.make_box_rsolid(40, 40, 40, bottom_face_center=(15, 15, 10))
    intersect_result = scad.intersect_rsolidlist(intersect_a, intersect_b)
    if not intersect_result:
        raise AssertionError("intersect_rsolidlist 未生成交集结果")

    loft_bottom = scad.make_circle_rwire(center=(0, 0, 0), radius=12)
    loft_top = scad.make_circle_rwire(center=(0, 0, 30), radius=6)
    lofted = scad.loft_rsolid([loft_bottom, loft_top])

    sweep_profile = scad.make_circle_rface(center=(0, 0, 0), radius=4)
    sweep_path = scad.make_segment_rwire((0, 0, 0), (0, 0, 45))
    swept = scad.sweep_rsolid(sweep_profile, sweep_path, is_frenet=False)

    helix_profile = scad.make_circle_rwire(center=(18, 0, 0), radius=2.5)
    helical = scad.helical_sweep_rsolid(
        helix_profile,
        pitch=8,
        height=24,
        radius=18,
    )

    pattern_seed = scad.make_box_rsolid(8, 6, 4)
    linear_pattern = scad.linear_pattern_rsolidlist(
        pattern_seed,
        direction=(1, 0, 0),
        count=3,
        spacing=14,
    )
    radial_pattern = scad.radial_pattern_rsolidlist(
        pattern_seed,
        center=(0, 0, 0),
        axis=(0, 0, 1),
        count=4,
        total_rotation_angle=360,
    )

    print(f"  相交后体积: {intersect_result[0].get_volume():.2f}")
    print(f"  放样后体积: {lofted.get_volume():.2f}")
    print(f"  扫掠后体积: {swept.get_volume():.2f}")
    print(f"  螺旋扫掠后体积: {helical.get_volume():.2f}")
    print(f"  线性阵列数量: {len(linear_pattern)}")
    print(f"  径向阵列数量: {len(radial_pattern)}")

    history, json_path, script_path, geometry_json_path = export_history_bundle(
        "test_extended_feature_export",
        include_geometry_json=True,
    )

    assert_feature_operations(
        json_path,
        [
            "boolean_intersect",
            "loft",
            "sweep",
            "helical_sweep",
            "linear_pattern",
            "radial_pattern",
        ],
    )
    assert_script_contains(
        script_path,
        [
            "# Boolean boolean_intersect:",
            "# Loft:",
            "# Sweep:",
            "# Helical Sweep:",
            "# Linear Pattern:",
            "# Radial Pattern:",
            "Part::Loft",
            ".Sections = [",
            "Part::Sweep",
            ".Spine = (",
            "Part::Helix",
            "Part.makeLine(",
            "App::Link",
        ],
    )

    if geometry_json_path is None:
        raise AssertionError("扩展导出缺少带几何 JSON 文件")

    geometry_data = load_json_file(geometry_json_path)
    if not any("output" in feature for feature in geometry_data.get("features", [])):
        raise AssertionError("include_geometry=True 时未导出 output 字段")

    print_export_summary(history, json_path, script_path, geometry_json_path)


# =============================================================================
# 测试 4: 复杂装配导出
# =============================================================================
def test_boolean_feature_export() -> None:
    create_new_history("复杂布尔组合导出测试")

    base = scad.make_box_rsolid(200, 150, 20)

    pillar = scad.make_cylinder_rsolid(radius=15, height=80)
    pillar = scad.translate_shape(pillar, (50, 50, 20))

    beam = scad.make_box_rsolid(120, 30, 25)
    beam = scad.translate_shape(beam, (-10, 35, 75))

    hole = scad.make_cylinder_rsolid(radius=8, height=30)
    hole = scad.translate_shape(hole, (100, 75, 70))

    step1 = scad.union_rsolidlist(base, pillar)
    if not step1:
        raise AssertionError("base 与 pillar 联合失败")
    step2 = scad.union_rsolidlist(step1[0], beam)
    if not step2:
        raise AssertionError("step1 与 beam 联合失败")
    final_result = scad.cut_rsolidlist(step2[0], hole)
    if not final_result:
        raise AssertionError("复杂布尔组合最终切除失败")

    print(f"  底座体积: {base.get_volume():.2f}")
    print(f"  立柱体积: {pillar.get_volume():.2f}")
    print(f"  横梁体积: {beam.get_volume():.2f}")
    print(f"  底座+立柱体积: {step1[0].get_volume():.2f}")
    print(f"  底座+立柱+横梁体积: {step2[0].get_volume():.2f}")
    print(f"  最终装配体体积: {final_result[0].get_volume():.2f}")

    history, json_path, script_path, _ = export_history_bundle("test_boolean_composition_export")

    assert_feature_operations(
        json_path,
        [
            "make_box",
            "make_cylinder",
            "translate_shape",
            "boolean_union",
            "boolean_cut",
        ],
    )
    assert_script_contains(
        script_path,
        [
            "# Translate:",
            "# Boolean boolean_union:",
            "# Boolean boolean_cut:",
        ],
    )

    print_export_summary(history, json_path, script_path)


# =============================================================================
# 测试 5: 声明式装配脚本导出
# =============================================================================
def test_legacy_declarative_assembly_export() -> None:
    base = scad.make_box_rsolid(160, 100, 12)
    left_column = scad.make_cylinder_rsolid(radius=8, height=55)
    right_column = scad.make_cylinder_rsolid(radius=8, height=55)
    top_beam = scad.make_box_rsolid(96, 20, 12)

    assembly = scad.make_assembly_rassembly(
        [
            ("base", base),
            ("left_column", left_column),
            ("right_column", right_column),
            ("top_beam", top_beam),
        ],
        parents={
            "left_column": "base",
            "right_column": "base",
            "top_beam": "base",
        },
        local_transforms={
            "left_column": [
                [1.0, 0.0, 0.0, -40.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 12.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            "right_column": [
                [1.0, 0.0, 0.0, 40.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 12.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            "top_beam": [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 67.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
        },
        name="test_assembly",
    )
    assembly = scad.rotate_part_rassembly(
        assembly,
        "top_beam",
        90,
        axis="z",
        origin=(0, 0, 67),
    )

    result = scad.solve_assembly_rresult(assembly)
    script_path = OUTPUT_DIR / "test_declarative_assembly_export.fcstd.py"
    export_assembly_result_to_freecad_script(assembly, str(script_path))

    if script_path not in generated_script_paths:
        generated_script_paths.append(script_path)

    script_preview = generate_freecad_assembly_script(assembly)
    if "Assembly imported successfully" not in script_preview:
        raise AssertionError("Assembly FreeCAD 脚本生成失败")

    assert_script_contains(
        script_path,
        [
            "# Assembly Part: base",
            "# Assembly Part: left_column",
            "# Assembly Part: right_column",
            "# Assembly Part: top_beam",
            "App::Part",
            ".addObject(",
            ".Placement = App.Placement(App.Matrix(",
            "importBrepFromString",
            "Part::Feature",
            "Assembly imported successfully with 4 parts",
        ],
    )

    print(f"  装配求解是否收敛: {result.report.converged}")
    print(f"  装配零件数量: {len(result.part_names())}")
    print(f"  Assembly FreeCAD 脚本: {script_path}")


def test_connected_assembly_export() -> None:
    base_plate = scad.make_box_rsolid(180, 120, 10)
    front_left_post = scad.make_box_rsolid(12, 12, 80)
    front_right_post = scad.make_box_rsolid(12, 12, 80)
    rear_left_post = scad.make_box_rsolid(12, 12, 80)
    rear_right_post = scad.make_box_rsolid(12, 12, 80)
    top_plate = scad.make_box_rsolid(180, 120, 8)
    lower_shelf = scad.make_box_rsolid(156, 96, 6)

    assembly = scad.make_assembly_rassembly(
        [
            ("base_plate", base_plate),
            ("front_left_post", front_left_post),
            ("front_right_post", front_right_post),
            ("rear_left_post", rear_left_post),
            ("rear_right_post", rear_right_post),
            ("top_plate", top_plate),
            ("lower_shelf", lower_shelf),
        ],
        parents={
            "front_left_post": "base_plate",
            "front_right_post": "base_plate",
            "rear_left_post": "base_plate",
            "rear_right_post": "base_plate",
            "top_plate": "base_plate",
            "lower_shelf": "base_plate",
        },
        local_transforms={
            "front_left_post": [
                [1.0, 0.0, 0.0, -78.0],
                [0.0, 1.0, 0.0, -48.0],
                [0.0, 0.0, 1.0, 10.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            "front_right_post": [
                [1.0, 0.0, 0.0, 78.0],
                [0.0, 1.0, 0.0, -48.0],
                [0.0, 0.0, 1.0, 10.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            "rear_left_post": [
                [1.0, 0.0, 0.0, -78.0],
                [0.0, 1.0, 0.0, 48.0],
                [0.0, 0.0, 1.0, 10.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            "rear_right_post": [
                [1.0, 0.0, 0.0, 78.0],
                [0.0, 1.0, 0.0, 48.0],
                [0.0, 0.0, 1.0, 10.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            "top_plate": [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 90.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            "lower_shelf": [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 42.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
        },
        name="storage_rack_assembly",
    )

    result = scad.solve_assembly_rresult(assembly)
    script_path = OUTPUT_DIR / "test_declarative_assembly_export.fcstd.py"
    export_assembly_result_to_freecad_script(assembly, str(script_path))

    if script_path not in generated_script_paths:
        generated_script_paths.append(script_path)

    script_preview = generate_freecad_assembly_script(assembly)
    if "Assembly imported successfully" not in script_preview:
        raise AssertionError("Assembly FreeCAD script generation failed")

    assert_script_contains(
        script_path,
        [
            "# Assembly Part: base_plate",
            "# Assembly Part: front_left_post",
            "# Assembly Part: front_right_post",
            "# Assembly Part: rear_left_post",
            "# Assembly Part: rear_right_post",
            "# Assembly Part: top_plate",
            "# Assembly Part: lower_shelf",
            "App::Part",
            ".addObject(",
            ".Placement = App.Placement(App.Matrix(",
            "importBrepFromString",
            "Part::Feature",
            "Assembly imported successfully with 7 parts",
        ],
    )

    print(f"  assembly converged: {result.report.converged}")
    print(f"  connected parts: {len(result.part_names())}")
    print(f"  Assembly FreeCAD script: {script_path}")


def test_generation_pattern_export_v2() -> None:
    create_new_history("Generation and pattern export test")

    loft_bottom = scad.make_circle_rwire(center=(0, 0, 0), radius=12)
    loft_top = scad.make_circle_rwire(center=(0, 0, 30), radius=6)
    lofted = scad.loft_rsolid([loft_bottom, loft_top])

    sweep_profile = scad.make_circle_rface(center=(0, 0, 0), radius=4)
    sweep_path = scad.make_segment_rwire((0, 0, 0), (0, 0, 45))
    swept = scad.sweep_rsolid(sweep_profile, sweep_path, is_frenet=False)

    helix_profile = scad.make_circle_rwire(center=(18, 0, 0), radius=2.5)
    helical = scad.helical_sweep_rsolid(
        helix_profile,
        pitch=8,
        height=24,
        radius=18,
    )

    pattern_seed = scad.make_box_rsolid(8, 6, 4)
    linear_pattern = scad.linear_pattern_rsolidlist(
        pattern_seed,
        direction=(1, 0, 0),
        count=3,
        spacing=14,
    )
    radial_pattern = scad.radial_pattern_rsolidlist(
        pattern_seed,
        center=(0, 0, 0),
        axis=(0, 0, 1),
        count=4,
        total_rotation_angle=360,
    )

    print(f"  loft volume: {lofted.get_volume():.2f}")
    print(f"  sweep volume: {swept.get_volume():.2f}")
    print(f"  helical sweep volume: {helical.get_volume():.2f}")
    print(f"  linear pattern count: {len(linear_pattern)}")
    print(f"  radial pattern count: {len(radial_pattern)}")

    history, json_path, script_path, geometry_json_path = export_history_bundle(
        "test_extended_feature_export",
        include_geometry_json=True,
    )

    assert_feature_operations(
        json_path,
        [
            "loft",
            "sweep",
            "helical_sweep",
            "linear_pattern",
            "radial_pattern",
        ],
    )
    assert_script_contains(
        script_path,
        [
            "# Loft:",
            "# Sweep:",
            "# Helical Sweep:",
            "# Linear Pattern:",
            "# Radial Pattern:",
            "Part::Loft",
            ".Sections = [",
            "Part::Sweep",
            ".Spine = (",
            "Part::Helix",
            "Part.makeLine(",
            "App::Link",
        ],
    )

    if geometry_json_path is None:
        raise AssertionError("Generation export missing geometry JSON")

    geometry_data = load_json_file(geometry_json_path)
    if not any("output" in feature for feature in geometry_data.get("features", [])):
        raise AssertionError("include_geometry=True did not export output data")

    print_export_summary(history, json_path, script_path, geometry_json_path)


def test_boolean_feature_export_v2() -> None:
    create_new_history("Boolean feature export test")

    intersect_a = scad.make_box_rsolid(40, 40, 40)
    intersect_b = scad.make_box_rsolid(40, 40, 40, bottom_face_center=(15, 15, 10))
    intersect_result = scad.intersect_rsolidlist(intersect_a, intersect_b)
    if not intersect_result:
        raise AssertionError("intersect_rsolidlist did not produce a result")

    base = scad.make_box_rsolid(200, 150, 20)
    pillar = scad.make_cylinder_rsolid(radius=15, height=80)
    pillar = scad.translate_shape(pillar, (50, 50, 20))
    beam = scad.make_box_rsolid(120, 30, 25)
    beam = scad.translate_shape(beam, (-10, 35, 75))
    hole = scad.make_cylinder_rsolid(radius=8, height=30)
    hole = scad.translate_shape(hole, (100, 75, 70))

    step1 = scad.union_rsolidlist(base, pillar)
    if not step1:
        raise AssertionError("Boolean union step1 failed")
    step2 = scad.union_rsolidlist(step1[0], beam)
    if not step2:
        raise AssertionError("Boolean union step2 failed")
    final_result = scad.cut_rsolidlist(step2[0], hole)
    if not final_result:
        raise AssertionError("Boolean cut failed")

    print(f"  intersect volume: {intersect_result[0].get_volume():.2f}")
    print(f"  union volume: {step2[0].get_volume():.2f}")
    print(f"  cut volume: {final_result[0].get_volume():.2f}")

    history, json_path, script_path, _ = export_history_bundle("test_boolean_composition_export")

    assert_feature_operations(
        json_path,
        [
            "make_box",
            "make_cylinder",
            "translate_shape",
            "boolean_intersect",
            "boolean_union",
            "boolean_cut",
        ],
    )
    assert_script_contains(
        script_path,
        [
            "# Boolean boolean_intersect:",
            "# Translate:",
            "# Boolean boolean_union:",
            "# Boolean boolean_cut:",
            "Part::Common",
            "Part::Fuse",
            "Part::Cut",
        ],
    )

    print_export_summary(history, json_path, script_path)


SCRIPT_SPECIFIC_FRAGMENTS: dict[str, list[str]] = {
    "test_creation_feature_export.fcstd.py": [
        "# Box:",
        "# Cylinder:",
        "# Sphere:",
        "# Face:",
        "# Field Surface:",
        "Part.Vertex(",
        "Part.Wire([",
        "Part.Face(",
        "Part.BSplineCurve([",
        "importBrepFromString",
    ],
    "test_advanced_feature_export.fcstd.py": [
        "# Extrude:",
        "# Revolve:",
        "# Translate:",
        "# Rotate:",
        "# Scale:",
        "# Mirror:",
        "# Fillet:",
        "# Chamfer:",
        "# Shell:",
        "App::Link",
        "Part::Mirroring",
        ".scale(",
        ".makeFillet(",
        ".makeChamfer(",
        ".makeThickness(",
    ],
    "test_extended_feature_export.fcstd.py": [
        "# Loft:",
        "# Sweep:",
        "# Helical Sweep:",
        "# Linear Pattern:",
        "# Radial Pattern:",
        "Part::Loft",
        ".Sections = [",
        "Part::Sweep",
        ".Spine = (",
        "Part::Helix",
        "Part.makeLine(",
        "App::Link",
    ],
    "test_boolean_composition_export.fcstd.py": [
        "# Boolean boolean_intersect:",
        "# Translate:",
        "# Boolean boolean_union:",
        "# Boolean boolean_cut:",
        "Part::Common",
        "Part::Fuse",
        "Part::Cut",
    ],
    "test_declarative_assembly_export.fcstd.py": [
        "# Assembly Part: base_plate",
        "# Assembly Part: front_left_post",
        "# Assembly Part: front_right_post",
        "# Assembly Part: rear_left_post",
        "# Assembly Part: rear_right_post",
        "# Assembly Part: top_plate",
        "# Assembly Part: lower_shelf",
        "App::Part",
        ".addObject(",
        ".Placement = App.Placement(App.Matrix(",
        "importBrepFromString",
        "Part::Feature",
        "Assembly imported successfully with 7 parts",
    ],
}


def validate_freecad_script_outputs() -> bool:
    print("\n【FreeCAD 脚本验证】")

    validation_errors: list[str] = []
    script_files = list(generated_script_paths)
    print(f"  找到 {len(script_files)} 个脚本文件")

    for script_file in script_files:
        print(f"\n  检查: {script_file.name}")

        with open(script_file, "r", encoding="utf-8") as f:
            script_content = f.read()

        if "import FreeCAD" not in script_content:
            validation_errors.append(f"{script_file.name}: 缺少 FreeCAD 导入")
            print("    ✗ 缺少 FreeCAD 导入")
        else:
            print("    ✓ 包含 FreeCAD 导入")

        if "import Part" not in script_content:
            validation_errors.append(f"{script_file.name}: 缺少 Part 导入")
            print("    ✗ 缺少 Part 导入")
        else:
            print("    ✓ 包含 Part 导入")

        if "doc.recompute()" not in script_content:
            validation_errors.append(f"{script_file.name}: 缺少 doc.recompute()")
            print("    ✗ 缺少 doc.recompute()")
        else:
            print("    ✓ 包含 doc.recompute()")

        if ".Length =" in script_content and ".LengthFwd =" not in script_content:
            if "Part::Extrusion" in script_content:
                validation_errors.append(f"{script_file.name}: 可能存在 Length 属性问题")
                print("    ! 警告: 可能存在 Length 属性问题")
            else:
                print("    ✓ Length 使用在正确的对象上")
        else:
            print("    ✓ Length 属性使用正确")

        base_not_found_count = script_content.count("Base object not found")
        if base_not_found_count > 0:
            print(f"    ! 警告: {base_not_found_count} 个 'Base object not found'")
        else:
            print("    ✓ 没有 Base object not found 警告")

        required_fragments = SCRIPT_SPECIFIC_FRAGMENTS.get(script_file.name, [])
        if required_fragments:
            missing_fragments = [
                fragment for fragment in required_fragments if fragment not in script_content
            ]
            if missing_fragments:
                validation_errors.append(
                    f"{script_file.name}: 缺少脚本片段 {', '.join(missing_fragments)}"
                )
                print(f"    ✗ 缺少脚本片段: {', '.join(missing_fragments)}")
            else:
                print("    ✓ 包含专项导出片段")

        print(f"    统计: {len(script_content.splitlines())} 行")

    print("\n" + "=" * 80)
    print("FreeCAD 脚本验证总结")
    print("=" * 80)

    if validation_errors:
        print(f"\n✗ 发现 {len(validation_errors)} 个问题")
        for index, error in enumerate(validation_errors, 1):
            print(f"  {index}. {error}")
        return False

    print("\n✓ 所有脚本验证通过！")
    print(f"  - 检查了 {len(script_files)} 个脚本文件")
    print("  - 所有脚本都包含必要的导入和调用")
    return True


def print_final_summary(script_validation_passed: bool) -> None:
    print("\n" + "=" * 80)
    print("测试完成总结")
    print("=" * 80)

    print(f"\n总测试数: {len(test_results)}")
    print(f"通过: {sum(1 for item in test_results if item['status'] == 'PASS')}")
    print(f"失败: {sum(1 for item in test_results if item['status'] == 'FAIL')}")
    print(f"脚本验证: {'通过' if script_validation_passed else '未通过'}")

    print(f"\n生成的文件 ({OUTPUT_DIR}):")
    for file in sorted(OUTPUT_DIR.iterdir()):
        size = file.stat().st_size
        print(f"  - {file.name:<45} ({size:>8,} bytes)")

    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


def main() -> int:
    tests: list[tuple[str, Callable[[], None]]] = [
        ("创建类特征导出", test_creation_feature_export),
        ("高级建模特征导出", test_advanced_feature_export),
        ("生成和阵列特征导出", test_generation_pattern_export_v2),
        ("布尔特征导出", test_boolean_feature_export_v2),
        ("连接装配脚本导出", test_connected_assembly_export),
    ]

    for test_name, test_func in tests:
        run_test(test_name, test_func)

    script_validation_passed = validate_freecad_script_outputs()
    print_final_summary(script_validation_passed)

    if all_tests_passed and script_validation_passed:
        print("\n✓ 所有测试通过！")
        return 0

    print("\n✗ 部分测试失败")
    return 1


if __name__ == "__main__":
    sys.exit(main())
