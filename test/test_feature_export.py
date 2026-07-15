"""
Comprehensive SimpleCADAPI feature-history and FreeCAD export validation.

This script focuses on grouped export scenarios instead of one-test-per-feature:
1. Creation features: primitives and sketch/profile construction
2. Advanced modeled features: extrude, revolve, fillet, chamfer, shell
3. Extended features: intersect, loft, sweep, helical sweep, patterns
4. Boolean composition flow: transforms + chained boolean modeling
5. Scalar-field flow: field graph + field-surface export
6. Hierarchical assembly flow: parent-child parts + solved placements
7. Assembly constraints flow: solved geometric constraints
8. QL selection flow: exportable topology/list selections and lambda snapshots

Run with:
    uv run python test/test_feature_export.py
"""

from __future__ import annotations

import json
import re
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

print("\n[Module Import]")
try:
    import simplecadapi as scad
    from simplecadapi import (
        FeatureExporter,
        create_new_history,
        export_feature_history_to_json,
        get_global_history,
    )

    print("All modules imported successfully")
except ImportError as exc:
    print(f"Import failed: {exc}")
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
            f"{json_path.name} is missing feature operations: {', '.join(missing)}; "
            f"current operations: {operations}"
        )


def assert_script_contains(script_path: Path, required_fragments: Sequence[str]) -> None:
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    missing = [fragment for fragment in required_fragments if fragment not in content]
    if missing:
        raise AssertionError(
            f"{script_path.name} is missing script fragments: {', '.join(missing)}"
        )


def export_history_bundle(
    base_name: str,
    *,
    include_geometry_json: bool = False,
) -> tuple:
    """Export current global history to JSON and a FreeCAD script."""
    history = get_global_history()
    if history is None:
        raise AssertionError("No feature history is currently available for export")

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
    print(f"  Feature count: {len(history.features)}")
    print(f"  JSON export: {json_path}")
    if geometry_json_path is not None:
        print(f"  Geometry JSON: {geometry_json_path}")
    print(f"  FreeCAD script: {script_path}")


def run_test(test_name: str, test_func: Callable[[], None]) -> None:
    """Run one test and record the result."""
    global all_tests_passed

    print(f"\n[Test: {test_name}]")
    try:
        test_func()
        print(f"PASS: {test_name}")
        test_results.append({"name": test_name, "status": "PASS"})
    except Exception as exc:
        print(f"FAIL: {test_name}: {exc}")
        traceback.print_exc()
        test_results.append({"name": test_name, "status": "FAIL", "error": str(exc)})
        all_tests_passed = False


# =============================================================================
# Test 1: Creation Feature Export
# =============================================================================
def test_creation_feature_export() -> None:
    create_new_history("Creation feature export test")

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

    print(f"  Box volume: {box.get_volume():.2f}")
    print(f"  Cylinder volume: {cylinder.get_volume():.2f}")
    print(f"  Sphere volume: {sphere.get_volume():.2f}")
    print(f"  Cone volume: {cone.get_volume():.2f}")
    print(f"  Torus volume: {torus.get_volume():.2f}")
    print(f"  Point created: {point}")
    print(f"  Segment edge created: {segment_edge}")
    print(f"  Segment wire created: {segment_wire}")
    print(f"  Circle face created: {circle_face}")
    print(f"  Rectangle face created: {rectangle_face}")
    print(f"  Face from wire created: {face_from_wire}")
    print(f"  Spline wire created: {spline_wire}")

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
            "Part.Vertex(",
            "Part.Wire([",
            "Part.Face(",
            "Part.BSplineCurve([",
        ],
    )

    print_export_summary(history, json_path, script_path)


# =============================================================================
# Test 2: Advanced Feature Export
# =============================================================================
def test_advanced_feature_export() -> None:
    create_new_history("Advanced feature export test")

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

    print("  Created rectangular profile and extruded it")
    print(f"  Extruded volume: {extruded.get_volume():.2f}")
    print("  Created circular profile and revolved it")
    print(f"  Revolved volume: {revolved.get_volume():.2f}")
    print(f"  Wire after non-solid transforms: {mirrored_wire}")
    print(f"  Base body volume: {base_body.get_volume():.2f}")
    print(f"  Filleted volume: {filleted.get_volume():.2f}")
    print(f"  Chamfered volume: {chamfered.get_volume():.2f}")
    print(f"  Shelled volume: {shelled.get_volume():.2f}")

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
# Test 3: Scalar Field History Export
# =============================================================================
def test_scalarfield_history_export() -> None:
    create_new_history("Scalar field history export test")

    sphere = scad.field.make_sphere_rscalarfield((0.0, 0.0, 0.0), 10.0)
    box = scad.field.make_box_rscalarfield((0.0, 0.0, 0.0), (18.0, 18.0, 18.0))
    translated = scad.field.translate_rscalarfield(sphere, (2.0, 0.0, 0.0))
    rotated = scad.field.rotate_rscalarfield(translated, (0.0, 0.0, 1.0), 30.0)
    blended = scad.field.smooth_union_rscalarfield(rotated, box, 2.5)
    scaled = scad.field.scale_rscalarfield(blended, (1.0, 1.2, 0.8))
    field_solid = scad.make_field_surface_rsolid(
        scaled,
        bounds=((-12.0, -12.0, -12.0), (12.0, 12.0, 12.0)),
        resolution=(10, 10, 10),
        iso=0.0,
    )

    print(f"  scalar field solid volume: {field_solid.get_volume():.2f}")

    history, json_path, script_path, geometry_json_path = export_history_bundle(
        "test_scalarfield_feature_export",
        include_geometry_json=True,
    )

    assert_feature_operations(
        json_path,
        [
            "make_sphere_field",
            "make_box_field",
            "translate_field",
            "rotate_field",
            "smooth_union_field",
            "scale_field",
            "make_field_surface",
        ],
    )
    assert_script_contains(
        script_path,
        [
            "# Scalar Field:",
            "_scad_make_sphere_field(",
            "_scad_smooth_union_field(",
            "_scad_scale_field(",
            "# Field Surface:",
            "importBrepFromString",
        ],
    )

    if geometry_json_path is None:
        raise AssertionError("Scalar field export missing geometry JSON")

    geometry_data = load_json_file(geometry_json_path)
    field_features = [
        feature for feature in geometry_data.get("features", [])
        if feature.get("operation", "").endswith("_field")
    ]
    if not field_features:
        raise AssertionError("Scalar field features were not exported to geometry JSON")

    print_export_summary(history, json_path, script_path, geometry_json_path)


# =============================================================================
# Test 4: Assembly History Export
# =============================================================================
def test_assembly_history_export() -> None:
    create_new_history("Assembly history export test")

    base = scad.make_box_rsolid(100, 60, 10)
    arm = scad.make_box_rsolid(50, 10, 10)
    pin = scad.make_cylinder_rsolid(radius=4, height=20)

    assembly = scad.make_assembly_rassembly(
        [("base", base), ("arm", arm), ("pin", pin)],
        parents={"arm": "base", "pin": "base"},
        local_transforms={
            "arm": [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 20.0],
                [0.0, 0.0, 1.0, 10.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            "pin": [
                [1.0, 0.0, 0.0, 20.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 10.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
        },
        name="history_assembly",
    )
    assembly = scad.translate_part_rassembly(assembly, "arm", (5.0, 0.0, 0.0))
    assembly = scad.rotate_part_rassembly(assembly, "arm", 15.0, axis="z", frame="local")
    assembly = scad.stack(
        assembly,
        ["base", "pin"],
        axis="x",
        gap=5.0,
        align="center",
        justify="start",
    )
    assembly = scad.constrain_offset_rassembly(
        assembly,
        assembly.part("base").bbox("top"),
        assembly.part("arm").bbox("bottom"),
        0.0,
        axis="z",
    )
    result = scad.solve_assembly_rresult(assembly)

    print(f"  assembly converged: {result.report.converged}")
    print(f"  assembly part count: {len(result.part_names())}")

    history, json_path, script_path, _ = export_history_bundle("test_assembly_feature_export")

    assert_feature_operations(
        json_path,
        [
            "make_box",
            "make_cylinder",
            "make_assembly",
            "translate_part",
            "rotate_part",
            "stack_parts",
            "constrain_offset",
            "solve_assembly",
        ],
    )
    assert_script_contains(
        script_path,
        [
            "# Assembly Step: make_assembly",
            "# Assembly Step: translate_part",
            "# Assembly Step: rotate_part",
            "# Assembly Step: stack_parts",
            "# Assembly Step: constrain_offset",
            "_scad_make_assembly(",
            "_scad_translate_part(",
            "_scad_rotate_part(",
            "_scad_stack_parts(",
            "_scad_add_constraint(",
            "# Solve Assembly:",
            "# Assembly Part: base",
            "# Assembly Part: arm",
            "# Assembly Part: pin",
            "importBrepFromString",
        ],
    )

    print_export_summary(history, json_path, script_path)


# =============================================================================
# Test 5: Assembly Constraints Export
# =============================================================================
def test_assembly_constraints_export() -> None:
    create_new_history("Assembly constraints export test")

    base = scad.make_box_rsolid(120, 60, 12)
    sleeve = scad.make_cylinder_rsolid(radius=10, height=30)
    rod = scad.make_cylinder_rsolid(radius=4, height=18)
    cap = scad.make_box_rsolid(20, 20, 8)
    gauge = scad.make_box_rsolid(12, 12, 12)

    assembly = scad.make_assembly_rassembly(
        [("base", base), ("sleeve", sleeve), ("rod", rod), ("cap", cap), ("gauge", gauge)],
        name="constraint_assembly",
    )
    assembly = scad.translate_part_rassembly(assembly, "sleeve", (0.0, 0.0, 12.0))
    assembly = scad.translate_part_rassembly(assembly, "rod", (18.0, 6.0, 20.0))
    assembly = scad.translate_part_rassembly(assembly, "cap", (26.0, 0.0, 0.0))
    assembly = scad.translate_part_rassembly(assembly, "gauge", (42.0, 0.0, 18.0))
    assembly = scad.constrain_concentric_rassembly(
        assembly,
        assembly.part("sleeve").axis("z"),
        assembly.part("rod").axis("z"),
    )
    assembly = scad.constrain_offset_rassembly(
        assembly,
        assembly.part("sleeve").bbox("bottom"),
        assembly.part("rod").bbox("bottom"),
        6.0,
        axis="z",
    )
    assembly = scad.constrain_coincident_rassembly(
        assembly,
        assembly.part("base").bbox("top"),
        assembly.part("cap").bbox("bottom"),
    )
    assembly = scad.constrain_distance_rassembly(
        assembly,
        assembly.part("sleeve").bbox("center"),
        assembly.part("gauge").bbox("center"),
        35.0,
        fallback_axis="x",
    )
    result = scad.solve_assembly_rresult(assembly)

    print(f"  constrained assembly converged: {result.report.converged}")
    print(f"  constrained assembly part count: {len(result.part_names())}")
    if not result.report.converged:
        raise AssertionError("Constraint-focused assembly did not converge")

    history, json_path, script_path, _ = export_history_bundle(
        "test_assembly_constraints_export"
    )

    assert_feature_operations(
        json_path,
        [
            "make_box",
            "make_cylinder",
            "make_assembly",
            "translate_part",
            "constrain_concentric",
            "constrain_offset",
            "constrain_coincident",
            "constrain_distance",
            "solve_assembly",
        ],
    )
    assert_script_contains(
        script_path,
        [
            "# Assembly Step: make_assembly",
            "# Assembly Step: translate_part",
            "# Assembly Step: constrain_concentric",
            "# Assembly Step: constrain_offset",
            "# Assembly Step: constrain_coincident",
            "# Assembly Step: constrain_distance",
            "_scad_make_assembly(",
            "_scad_translate_part(",
            "_scad_add_constraint(",
            "# Solve Assembly:",
            "# Assembly Part: base",
            "# Assembly Part: sleeve",
            "# Assembly Part: rod",
            "# Assembly Part: cap",
            "# Assembly Part: gauge",
            "importBrepFromString",
        ],
    )

    print_export_summary(history, json_path, script_path)


# =============================================================================
# Test 6: Extended Feature Export
# =============================================================================
def test_generation_pattern_export() -> None:
    create_new_history("Generation and pattern export test")

    intersect_a = scad.make_box_rsolid(40, 40, 40)
    intersect_b = scad.make_box_rsolid(40, 40, 40, bottom_face_center=(15, 15, 10))
    intersect_result = scad.intersect_rsolidlist(intersect_a, intersect_b)
    if not intersect_result:
        raise AssertionError("intersect_rsolidlist did not produce a result")

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

    print(f"  Intersect volume: {intersect_result[0].get_volume():.2f}")
    print(f"  Loft volume: {lofted.get_volume():.2f}")
    print(f"  Sweep volume: {swept.get_volume():.2f}")
    print(f"  Helical sweep volume: {helical.get_volume():.2f}")
    print(f"  Linear pattern count: {len(linear_pattern)}")
    print(f"  Radial pattern count: {len(radial_pattern)}")

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
            "Part::Common",
            "App::Link",
        ],
    )

    if geometry_json_path is None:
        raise AssertionError("Generation export missing geometry JSON")

    geometry_data = load_json_file(geometry_json_path)
    if not any("output" in feature for feature in geometry_data.get("features", [])):
        raise AssertionError("include_geometry=True did not export output data")

    print_export_summary(history, json_path, script_path, geometry_json_path)


# =============================================================================
# Test 7: Boolean Composition Export
# =============================================================================
def test_boolean_feature_export() -> None:
    create_new_history("Boolean feature export test")

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

    multi_cut_base = scad.make_box_rsolid(40, 24, 12)
    multi_cut_tool_a = scad.make_cylinder_rsolid(
        radius=4,
        height=14,
        bottom_face_center=(-8, 0, -1),
    )
    multi_cut_tool_b = scad.make_cylinder_rsolid(
        radius=4,
        height=14,
        bottom_face_center=(8, 0, -1),
    )
    multi_cut_result = scad.cut_rsolidlist(
        multi_cut_base,
        multi_cut_tool_a,
        multi_cut_tool_b,
    )
    if not multi_cut_result:
        raise AssertionError("Multi-tool boolean cut failed")

    print(f"  union volume: {step2[0].get_volume():.2f}")
    print(f"  cut volume: {final_result[0].get_volume():.2f}")

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
            "Part::Fuse",
            "Part::Cut",
            "_Tools = doc.addObject('Part::MultiFuse'",
            "Visibility = True",
            "Visibility = False",
        ],
    )

    script_content = script_path.read_text(encoding="utf-8")
    multi_cut_match = re.search(
        r"(?P<tools>Feature_\d+_Boolean_boolean_cut_Result_Tools) = "
        r"doc\.addObject\('Part::MultiFuse'.*?"
        r"\.Tool = (?P=tools)",
        script_content,
        flags=re.DOTALL,
    )
    if multi_cut_match is None:
        raise AssertionError("Multi-tool cut does not reference its exported tool collection")

    print_export_summary(history, json_path, script_path)


# =============================================================================
# Test 8: QL Selection Export
# =============================================================================
def test_ql_selection_feature_export() -> None:
    create_new_history("QL selection feature export test")

    base_profile = scad.make_circle_rface((0.0, 0.0, 0.0), 5.0)
    cylinder = scad.extrude_rsolid(base_profile, (0.0, 0.0, 1.0), 10.0)
    top_face = scad.ql_select_one(
        cylinder,
        "faces",
        scad.ql.query()
            .where(scad.ql.tag("extrusion end face"))
            .take(1)
            .exactly(1),
        name="Selected_Extrusion_Top_Face",
    )

    path = scad.make_helix_rwire(2.0, 18.0, 7.0, center=(0.0, 0.0, 10.0))
    swept = scad.sweep_rsolid(top_face, path, is_frenet=True)

    small_box = scad.make_box_rsolid(4, 4, 4, bottom_face_center=(30, 0, 0))
    large_box = scad.make_box_rsolid(8, 8, 8, bottom_face_center=(45, 0, 0))
    largest_part = scad.ql_select_one_from(
        [small_box, large_box],
        scad.ql.query().order_by(scad.ql.geo("volume"), desc=True).take(1).exactly(1),
        name="Largest_Box_By_Volume",
    )

    left_plate = scad.make_box_rsolid(10, 5, 2, bottom_face_center=(-30, 0, 0))
    right_plate = scad.make_box_rsolid(12, 6, 2, bottom_face_center=(-45, 0, 0))
    largest_face = scad.ql_select_one_from_topology(
        [(left_plate, "faces"), (right_plate, "faces")],
        scad.ql.query().order_by(scad.ql.geo("area"), desc=True).take(1).exactly(1),
        name="Largest_Face_Across_Plates",
    )

    lambda_edges = scad.ql_select(
        large_box,
        "edges",
        lambda edge: edge.get_length() >= 8.0,
        name="Runtime_Lambda_Edge_Snapshots",
    )

    print(f"  QL selected top face tags: {top_face.get_tags()}")
    print(f"  Sweep from QL face volume: {swept.get_volume():.2f}")
    print(f"  Largest part volume: {largest_part.get_volume():.2f}")
    print(f"  Largest face area: {largest_face.get_area():.2f}")
    print(f"  Lambda edge snapshot count: {len(lambda_edges)}")

    history, json_path, script_path, _ = export_history_bundle("test_ql_selection_export")

    assert_feature_operations(
        json_path,
        [
            "make_circle",
            "extrude",
            "ql_select",
            "sweep",
            "make_box",
            "ql_select_from",
            "ql_select_from_topology",
        ],
    )
    assert_script_contains(
        script_path,
        [
            "# QL Select: Selected_Extrusion_Top_Face",
            "# QL Select From List: Largest_Box_By_Volume",
            "# QL Select From Topology: Largest_Face_Across_Plates",
            "# QL Select: Runtime_Lambda_Edge_Snapshots",
            "_scad_match_topology_by_signature",
            ".Sections = [Feature_002_Selected_Extrusion_Top_Face_Result]",
            "Part.Face(",
            "Part.Compound([item.Shape",
        ],
    )

    print_export_summary(history, json_path, script_path)


SCRIPT_SPECIFIC_FRAGMENTS: dict[str, list[str]] = {
    "test_creation_feature_export.fcstd.py": [
        "# Box:",
        "# Cylinder:",
        "# Sphere:",
        "# Face:",
        "Part.Vertex(",
        "Part.Wire([",
        "Part.Face(",
        "Part.BSplineCurve([",
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
        "Part::Common",
        "App::Link",
    ],
    "test_boolean_composition_export.fcstd.py": [
        "# Translate:",
        "# Boolean boolean_union:",
        "# Boolean boolean_cut:",
        "Part::Fuse",
        "Part::Cut",
        "Visibility = True",
        "Visibility = False",
    ],
    "test_ql_selection_export.fcstd.py": [
        "# QL Select: Selected_Extrusion_Top_Face",
        "# QL Select From List: Largest_Box_By_Volume",
        "# QL Select From Topology: Largest_Face_Across_Plates",
        "# QL Select: Runtime_Lambda_Edge_Snapshots",
        "_scad_match_topology_by_signature",
        ".Sections = [Feature_002_Selected_Extrusion_Top_Face_Result]",
        "Part.Face(",
        "Part.Compound([item.Shape",
    ],
    "test_scalarfield_feature_export.fcstd.py": [
        "# Scalar Field:",
        "_scad_make_sphere_field(",
        "_scad_smooth_union_field(",
        "_scad_scale_field(",
        "# Field Surface:",
        "importBrepFromString",
    ],
    "test_assembly_feature_export.fcstd.py": [
        "# Assembly Step: make_assembly",
        "# Assembly Step: translate_part",
        "# Assembly Step: rotate_part",
        "# Assembly Step: stack_parts",
        "# Assembly Step: constrain_offset",
        "_scad_make_assembly(",
        "_scad_translate_part(",
        "_scad_rotate_part(",
        "_scad_stack_parts(",
        "_scad_add_constraint(",
        "# Solve Assembly:",
        "# Assembly Part: base",
        "# Assembly Part: arm",
        "# Assembly Part: pin",
        "importBrepFromString",
    ],
    "test_assembly_constraints_export.fcstd.py": [
        "# Assembly Step: make_assembly",
        "# Assembly Step: translate_part",
        "# Assembly Step: constrain_concentric",
        "# Assembly Step: constrain_offset",
        "# Assembly Step: constrain_coincident",
        "# Assembly Step: constrain_distance",
        "_scad_make_assembly(",
        "_scad_translate_part(",
        "_scad_add_constraint(",
        "# Solve Assembly:",
        "# Assembly Part: base",
        "# Assembly Part: sleeve",
        "# Assembly Part: rod",
        "# Assembly Part: cap",
        "# Assembly Part: gauge",
        "importBrepFromString",
    ],
}


def validate_freecad_script_outputs() -> bool:
    print("\n[FreeCAD Script Validation]")

    validation_errors: list[str] = []
    script_files = list(generated_script_paths)
    print(f"  Found {len(script_files)} script files")

    for script_file in script_files:
        print(f"\n  Checking: {script_file.name}")

        with open(script_file, "r", encoding="utf-8") as f:
            script_content = f.read()

        if "import FreeCAD" not in script_content:
            validation_errors.append(f"{script_file.name}: missing FreeCAD import")
            print("    Missing FreeCAD import")
        else:
            print("    Includes FreeCAD import")

        if "import Part" not in script_content:
            validation_errors.append(f"{script_file.name}: missing Part import")
            print("    Missing Part import")
        else:
            print("    Includes Part import")

        if "doc.recompute()" not in script_content:
            validation_errors.append(f"{script_file.name}: missing doc.recompute()")
            print("    Missing doc.recompute()")
        else:
            print("    Includes doc.recompute()")

        if ".Length =" in script_content and ".LengthFwd =" not in script_content:
            if "Part::Extrusion" in script_content:
                validation_errors.append(f"{script_file.name}: possible Length property issue")
                print("    Warning: possible Length property issue")
            else:
                print("    Length is used on the correct object type")
        else:
            print("    Length usage looks correct")

        base_not_found_count = script_content.count("Base object not found")
        if base_not_found_count > 0:
            print(f"    Warning: found {base_not_found_count} 'Base object not found' messages")
        else:
            print("    No 'Base object not found' warnings")

        required_fragments = SCRIPT_SPECIFIC_FRAGMENTS.get(script_file.name, [])
        if required_fragments:
            missing_fragments = [
                fragment for fragment in required_fragments if fragment not in script_content
            ]
            if missing_fragments:
                validation_errors.append(
                    f"{script_file.name}: missing script fragments {', '.join(missing_fragments)}"
                )
                print(f"    Missing script fragments: {', '.join(missing_fragments)}")
            else:
                print("    Includes expected export fragments")

        print(f"    Line count: {len(script_content.splitlines())}")

    print("\n" + "=" * 80)
    print("FreeCAD Script Validation Summary")
    print("=" * 80)

    if validation_errors:
        print(f"\nFound {len(validation_errors)} validation issues")
        for index, error in enumerate(validation_errors, 1):
            print(f"  {index}. {error}")
        return False

    print("\nAll script validations passed")
    print(f"  - Checked {len(script_files)} script files")
    print("  - All scripts include the required imports and calls")
    return True


def print_final_summary(script_validation_passed: bool) -> None:
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)

    print(f"\nTotal tests: {len(test_results)}")
    print(f"Passed: {sum(1 for item in test_results if item['status'] == 'PASS')}")
    print(f"Failed: {sum(1 for item in test_results if item['status'] == 'FAIL')}")
    print(f"Script validation: {'passed' if script_validation_passed else 'failed'}")

    print(f"\nGenerated files ({OUTPUT_DIR}):")
    for file in sorted(OUTPUT_DIR.iterdir()):
        size = file.stat().st_size
        print(f"  - {file.name:<45} ({size:>8,} bytes)")

    print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


def main() -> int:
    tests: list[tuple[str, Callable[[], None]]] = [
        ("Creation feature export", test_creation_feature_export),
        ("Advanced feature export", test_advanced_feature_export),
        ("Generation and pattern export", test_generation_pattern_export),
        ("Boolean feature export", test_boolean_feature_export),
        ("QL selection export", test_ql_selection_feature_export),
        ("Scalar field feature export", test_scalarfield_history_export),
        ("Assembly history export", test_assembly_history_export),
        ("Assembly constraints export", test_assembly_constraints_export),
    ]

    for test_name, test_func in tests:
        run_test(test_name, test_func)

    script_validation_passed = validate_freecad_script_outputs()
    print_final_summary(script_validation_passed)

    if all_tests_passed and script_validation_passed:
        print("\nAll tests passed")
        return 0

    print("\nSome tests failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
