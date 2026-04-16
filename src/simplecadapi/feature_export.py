"""
Feature export utilities for SimpleCADAPI.

This module provides functions to export feature history to various formats,
including JSON, STEP with metadata, and CAD software-specific formats.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .feature_history import FeatureHistory
from .core import Solid


def export_feature_history_to_json(
    history: FeatureHistory,
    filepath: str,
    indent: int = 2,
    include_geometry: bool = False,
) -> str:
    """
    Export feature history to JSON file.

    Args:
        history: The feature history to export
        filepath: Output file path
        indent: JSON indentation level
        include_geometry: Whether to include geometry data (can be large)

    Returns:
        Path to the exported file
    """
    data = history.to_dict(include_geometry=include_geometry)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, default=str, ensure_ascii=False)

    return filepath


def export_solid_with_history(
    solid: Solid,
    step_filepath: str,
    json_filepath: Optional[str] = None,
) -> Dict[str, str]:
    """
    Export solid geometry and its feature history.

    Args:
        solid: The solid to export
        step_filepath: Path for STEP geometry export
        json_filepath: Optional path for feature history JSON export

    Returns:
        Dictionary with paths to exported files
    """
    from .operations import export_step

    results = {}

    # Export STEP geometry
    export_step(solid, step_filepath)
    results['step'] = step_filepath

    # Export feature history if available
    if solid._feature is not None:
        from .feature_history import get_global_history

        history = get_global_history()
        if history is None and hasattr(solid._feature, '_parent'):
            # Try to reconstruct minimal history
            history = FeatureHistory(name="Reconstructed Model")
            history.add_feature_from_solid(solid)

        if history is not None:
            if json_filepath is None:
                # Generate default filename
                base_path = Path(step_filepath).parent
                base_name = Path(step_filepath).stem
                json_filepath = str(base_path / f"{base_name}_features.json")

            export_feature_history_to_json(history, json_filepath)
            results['json'] = json_filepath

    return results


def generate_feature_report(history: FeatureHistory) -> str:
    """
    Generate a human-readable report of feature history.

    Args:
        history: The feature history to report on

    Returns:
        Formatted report string
    """
    lines = [
        "=" * 60,
        f"Feature History Report: {history.name}",
        "=" * 60,
        "",
    ]

    # Summary statistics
    total_features = len(history.features)
    type_counts: Dict[str, int] = {}

    for feature in history.features.values():
        type_name = feature.feature_type.name
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

    lines.extend([
        "Summary:",
        f"  Total Features: {total_features}",
        f"  Feature Types:",
    ])

    for type_name, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"    - {type_name}: {count}")

    lines.append("")

    # Detailed feature list
    if history.ordered_features:
        lines.extend([
            "Feature Details:",
            "-" * 60,
        ])

        for i, feature_id in enumerate(history.ordered_features, 1):
            feature = history.features.get(feature_id)
            if feature:
                lines.extend([
                    f"  {i}. {feature.name}",
                    f"      ID: {feature.feature_id}",
                    f"      Type: {feature.feature_type.name}",
                    f"      Operation: {feature.operation}",
                ])

                if feature.parameters:
                    lines.append(f"      Parameters:")
                    for param_name, param in feature.parameters.items():
                        lines.append(f"        - {param_name}: {param.value}")

                if feature.parent_features:
                    lines.append(f"      Parent Features: {', '.join(feature.parent_features)}")

                lines.append("")

    lines.extend([
        "-" * 60,
        "End of Report",
        "=" * 60,
    ])

    return "\n".join(lines)


def print_feature_report(history: FeatureHistory) -> None:
    """
    Print a feature history report to stdout.

    Args:
        history: The feature history to report on
    """
    print(generate_feature_report(history))


class FeatureExporter:
    """
    Main class for exporting features in various formats.

    This class provides a unified interface for exporting feature history
    to different formats and CAD software.
    """

    def __init__(self, history: FeatureHistory):
        """
        Initialize the exporter with a feature history.

        Args:
            history: The feature history to export
        """
        self.history = history

    def to_json(
        self,
        filepath: str,
        indent: int = 2,
        include_geometry: bool = False,
    ) -> str:
        """Export to JSON format."""
        return export_feature_history_to_json(
            self.history,
            filepath,
            indent,
            include_geometry=include_geometry,
        )

    def to_step_with_metadata(self, solid: Solid, filepath: str) -> str:
        """Export to STEP format with feature metadata."""
        from .operations import export_step

        # First export the STEP file
        export_step(solid, filepath)

        # Then export the feature history alongside it
        base_path = Path(filepath).parent
        base_name = Path(filepath).stem
        json_path = str(base_path / f"{base_name}_features.json")

        export_feature_history_to_json(self.history, json_path)

        return filepath

    def generate_report(self) -> str:
        """Generate a feature report."""
        return generate_feature_report(self.history)

    def print_report(self) -> None:
        """Print the feature report to stdout."""
        print(self.generate_report())

    def generate_cad_script(self, format_type: str, filepath: str) -> str:
        """
        Generate CAD script for various CAD software.

        Args:
            format_type: Target CAD software ("freecad", "solidworks")
            filepath: Output file path

        Returns:
            Path to the generated script file
        """
        if format_type.lower() == "freecad":
            script_content = self._generate_freecad_script()
        elif format_type.lower() == "solidworks":
            raise NotImplementedError("SolidWorks macro generation not yet implemented")
        else:
            raise ValueError(f"Unsupported CAD format: {format_type}")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(script_content)

        return filepath

    def _generate_freecad_script(self) -> str:
        """Generate FreeCAD Python script from feature history."""
        lines = [
            "# FreeCAD Python script generated by SimpleCADAPI",
            "# This script can be run in FreeCAD's Python console",
            "",
            "import FreeCAD as App",
            "import math",
            "import Part",
            "try:",
            "    import FreeCADGui as Gui",
            "except ImportError:",
            "    Gui = None  # No GUI available",
            "",
            "# Create a new document",
            "doc = App.newDocument()",
            "",
        ]

        # Track created objects for dependencies
        created_objects = {}
        tree_objects = {}
        terminal_feature_ids = set(self.history.ordered_features)

        for i, feature_id in enumerate(self.history.ordered_features):
            feature = self.history.features.get(feature_id)
            if not feature:
                continue

            obj_name = f"Feature_{i:03d}_{feature.name}"
            result_name = f"{obj_name}_Result"

            # Generate code based on operation type
            if feature.operation == "make_box":
                lines.extend(self._generate_freecad_box(feature, result_name))
            elif feature.operation == "make_cylinder":
                lines.extend(self._generate_freecad_cylinder(feature, result_name))
            elif feature.operation == "make_sphere":
                lines.extend(self._generate_freecad_sphere(feature, result_name))
            elif feature.operation == "extrude":
                lines.extend(self._generate_freecad_extrude(feature, result_name, created_objects))
            elif feature.operation == "revolve":
                lines.extend(self._generate_freecad_revolve(feature, result_name, created_objects))
            elif feature.operation in ["boolean_union", "boolean_cut", "boolean_intersect"]:
                lines.extend(self._generate_freecad_boolean(feature, result_name, created_objects))
            elif feature.operation == "fillet":
                lines.extend(self._generate_freecad_fillet(feature, result_name, created_objects))
            elif feature.operation == "chamfer":
                lines.extend(self._generate_freecad_chamfer(feature, result_name, created_objects))
            elif feature.operation == "shell":
                lines.extend(self._generate_freecad_shell(feature, result_name, created_objects))
            elif feature.operation == "make_cone":
                lines.extend(self._generate_freecad_cone(feature, result_name))
            elif feature.operation == "make_torus":
                lines.extend(self._generate_freecad_torus(feature, result_name))
            elif feature.operation in [
                "make_rectangle",
                "make_circle",
                "make_polygon",
                "make_line",
                "make_arc",
                "make_polyline",
                "make_helix",
            ]:
                lines.extend(self._generate_freecad_sketch(feature, result_name))
            elif feature.operation == "make_wire":
                lines.extend(self._generate_freecad_wire(feature, obj_name, created_objects, tree_objects))
            elif feature.operation == "make_face":
                lines.extend(self._generate_freecad_face(feature, obj_name, created_objects, tree_objects))
            elif feature.operation == "loft":
                lines.extend(self._generate_freecad_loft(feature, result_name, created_objects))
            elif feature.operation == "sweep":
                lines.extend(self._generate_freecad_sweep(feature, result_name, created_objects))
            elif feature.operation == "helical_sweep":
                lines.extend(self._generate_freecad_helical_sweep(feature, result_name, created_objects))
            elif feature.operation == "translate_shape":
                lines.extend(self._generate_freecad_translate(feature, result_name, created_objects))
            elif feature.operation == "rotate_shape":
                lines.extend(self._generate_freecad_rotate(feature, result_name, created_objects))
            elif feature.operation == "scale_shape":
                lines.extend(self._generate_freecad_scale(feature, result_name, created_objects))
            elif feature.operation == "mirror_shape":
                lines.extend(self._generate_freecad_mirror(feature, result_name, created_objects))
            elif feature.operation == "linear_pattern":
                lines.extend(self._generate_freecad_linear_pattern(feature, result_name, created_objects))
            elif feature.operation == "radial_pattern":
                lines.extend(self._generate_freecad_radial_pattern(feature, result_name, created_objects))
            else:
                lines.append(f"# Unknown operation: {feature.operation}")
                lines.append(f"# Feature: {feature.name}")
                lines.append("")
                continue

            if feature.operation in {"make_wire", "make_face"}:
                tree_objects[feature_id] = obj_name
                created_objects[feature_id] = f"{obj_name}_Result"
            else:
                lines.extend(self._wrap_feature_tree(feature, obj_name, result_name, tree_objects))
                tree_objects[feature_id] = obj_name
                created_objects[feature_id] = result_name

            for input_id in (getattr(feature, "input_ids", None) or []):
                terminal_feature_ids.discard(input_id)
            for parent_id in (getattr(feature, "parent_features", None) or []):
                terminal_feature_ids.discard(parent_id)

        if len(terminal_feature_ids) == 1:
            final_feature_id = next(iter(terminal_feature_ids))
            lines.extend([
                "# Show only the terminal result in the 3D view",
            ])
            for feature_id in self.history.ordered_features:
                result_object_name = created_objects.get(feature_id)
                if not result_object_name:
                    continue
                visible = feature_id == final_feature_id
                lines.extend([
                    f"if hasattr({result_object_name}, 'ViewObject') and hasattr({result_object_name}.ViewObject, 'Visibility'):",
                    f"    {result_object_name}.ViewObject.Visibility = {str(visible)}",
                ])
            lines.append("")

        # Add final recompute
        lines.extend([
            "",
            "# Recompute the document",
            "doc.recompute()",
            "",
            "# Switch to 3D view",
            "if App.Gui:",
            "    Gui.activeDocument().activeView().viewIsometric()",
            "    Gui.SendMsgToActiveView(\"ViewFit\")",
            "",
            f"print('Model imported successfully with {len(self.history.features)} features')",
            "",
        ])

        return "\n".join(lines)

    def _wrap_feature_tree(
        self,
        feature,
        group_name: str,
        result_name: str,
        tree_objects: dict,
    ) -> List[str]:
        """Wrap a result object and its input tree nodes into a single tree node."""
        input_tree_names: List[str] = []
        for feature_id in (getattr(feature, "input_ids", None) or []):
            tree_name = tree_objects.get(feature_id)
            if tree_name and tree_name not in input_tree_names:
                input_tree_names.append(tree_name)
        for feature_id in (getattr(feature, "parent_features", None) or []):
            tree_name = tree_objects.get(feature_id)
            if tree_name and tree_name not in input_tree_names:
                input_tree_names.append(tree_name)

        lines = [
            f"{group_name} = doc.addObject('App::Part', '{group_name}')",
            f"{group_name}.addObject({result_name})",
        ]
        for input_tree_name in input_tree_names:
            lines.append(f"{group_name}.addObject({input_tree_name})")
        lines.append("")
        return lines

    def _get_param_value(self, feature, param_name, default=None):
        """Get parameter value from feature."""
        param = feature.parameters.get(param_name)
        if param:
            return param.value
        return default

    def _to_vector_tuple(self, value: Any, default: Tuple[float, float, float]) -> Tuple[float, float, float]:
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            return (value[0], value[1], value[2])
        return default

    def _vector_expr(self, value: Any, default: Tuple[float, float, float] = (0, 0, 0)) -> str:
        x, y, z = self._to_vector_tuple(value, default)
        return f"App.Vector({x}, {y}, {z})"

    def _list_expr(self, values: Any) -> str:
        if isinstance(values, list):
            return repr(values)
        return "[]"

    def _placement_rotation_lines(self, obj_name: str, axis: Any) -> List[str]:
        axis_tuple = self._to_vector_tuple(axis, (0, 0, 1))
        if axis_tuple == (0, 0, 1):
            return []
        return [
            f"{obj_name}.Placement.Rotation = App.Rotation(App.Vector(0, 0, 1), {self._vector_expr(axis_tuple)})",
        ]

    def _rotation_expr(
        self,
        axis: Any,
        default: Tuple[float, float, float] = (0, 0, 1),
        angle: float = 0.0,
    ) -> str:
        return f"App.Rotation({self._vector_expr(axis, default)}, {angle})"

    def _placement_expr(
        self,
        base: Any = (0, 0, 0),
        axis: Any = (0, 0, 1),
        angle: float = 0.0,
        center: Optional[Any] = None,
    ) -> str:
        if center is None:
            return (
                f"App.Placement({self._vector_expr(base)}, "
                f"{self._rotation_expr(axis, angle=angle)})"
            )
        return (
            f"App.Placement({self._vector_expr(base)}, "
            f"{self._rotation_expr(axis, angle=angle)}, "
            f"{self._vector_expr(center)})"
        )

    def _generate_freecad_box(self, feature, obj_name: str) -> List[str]:
        """Generate FreeCAD code for box primitive."""
        width = self._get_param_value(feature, 'width', 10.0)
        height = self._get_param_value(feature, 'height', 10.0)
        depth = self._get_param_value(feature, 'depth', 10.0)
        bottom_face_center = self._get_param_value(feature, 'bottom_face_center', (0, 0, 0))
        origin = (
            bottom_face_center[0] - width / 2,
            bottom_face_center[1] - height / 2,
            bottom_face_center[2],
        )

        lines = [
            f"# Box: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Box', '{obj_name}')",
            f"{obj_name}.Length = {width}",
            f"{obj_name}.Width = {height}",
            f"{obj_name}.Height = {depth}",
        ]
        if self._to_vector_tuple(origin, (0, 0, 0)) != (0, 0, 0):
            lines.append(f"{obj_name}.Placement.Base = {self._vector_expr(origin)}")
        lines.append("")
        return lines

    def _generate_freecad_cylinder(self, feature, obj_name: str) -> List[str]:
        """Generate FreeCAD code for cylinder primitive."""
        radius = self._get_param_value(feature, 'radius', 5.0)
        height = self._get_param_value(feature, 'height', 10.0)
        bottom_face_center = self._get_param_value(feature, 'bottom_face_center', (0, 0, 0))
        axis = self._get_param_value(feature, 'axis', (0, 0, 1))

        lines = [
            f"# Cylinder: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Cylinder', '{obj_name}')",
            f"{obj_name}.Radius = {radius}",
            f"{obj_name}.Height = {height}",
            f"{obj_name}.Placement.Base = {self._vector_expr(bottom_face_center)}",
        ]
        lines.extend(self._placement_rotation_lines(obj_name, axis))
        lines.append("")
        return lines

    def _generate_freecad_sphere(self, feature, obj_name: str) -> List[str]:
        """Generate FreeCAD code for sphere primitive."""
        radius = self._get_param_value(feature, 'radius', 5.0)
        center = self._get_param_value(feature, 'center', (0, 0, 0))

        lines = [
            f"# Sphere: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Sphere', '{obj_name}')",
            f"{obj_name}.Radius = {radius}",
        ]
        if self._to_vector_tuple(center, (0, 0, 0)) != (0, 0, 0):
            lines.append(f"{obj_name}.Placement.Base = {self._vector_expr(center)}")
        lines.append("")
        return lines

    def _generate_freecad_cone(self, feature, obj_name: str) -> List[str]:
        """Generate FreeCAD code for cone primitive."""
        bottom_radius = self._get_param_value(feature, 'bottom_radius', 10.0)
        top_radius = self._get_param_value(feature, 'top_radius', 0.0)
        height = self._get_param_value(feature, 'height', 20.0)
        bottom_face_center = self._get_param_value(feature, 'bottom_face_center', (0, 0, 0))
        axis = self._get_param_value(feature, 'axis', (0, 0, 1))

        lines = [
            f"# Cone: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Cone', '{obj_name}')",
            f"{obj_name}.Radius1 = {bottom_radius}",
            f"{obj_name}.Radius2 = {top_radius}",
            f"{obj_name}.Height = {height}",
            f"{obj_name}.Placement.Base = {self._vector_expr(bottom_face_center)}",
        ]
        lines.extend(self._placement_rotation_lines(obj_name, axis))
        lines.append("")
        return lines

    def _generate_freecad_torus(self, feature, obj_name: str) -> List[str]:
        """Generate FreeCAD code for torus primitive."""
        major_radius = self._get_param_value(feature, 'radius1', 20.0)
        minor_radius = self._get_param_value(feature, 'radius2', 5.0)
        center = self._get_param_value(feature, 'center', (0, 0, 0))
        axis = self._get_param_value(feature, 'axis', (0, 0, 1))

        lines = [
            f"# Torus: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Torus', '{obj_name}')",
            f"{obj_name}.Radius1 = {major_radius}",
            f"{obj_name}.Radius2 = {minor_radius}",
            f"{obj_name}.Placement.Base = {self._vector_expr(center)}",
        ]
        lines.extend(self._placement_rotation_lines(obj_name, axis))
        lines.append("")
        return lines

    def _get_input_object_name(self, feature, created_objects: dict) -> Optional[str]:
        # 首先尝试 input_ids
        if hasattr(feature, 'input_ids') and feature.input_ids:
            for input_id in feature.input_ids:
                if input_id in created_objects:
                    return created_objects[input_id]
        
        # 然后尝试 parent_features
        if hasattr(feature, 'parent_features') and feature.parent_features:
            for parent_id in feature.parent_features:
                if parent_id in created_objects:
                    return created_objects[parent_id]
        
        # 最后尝试查找任何可用的父特征
        # 在特征树中，可能输入引用的是前一个特征
        if hasattr(feature, 'parent_features') and feature.parent_features:
            # 如果找不到对应的创建对象，可能是父特征还未被处理
            # 在这种情况下，返回 None 让调用者处理
            pass
        
        return None

    def _get_input_object_names(self, feature, created_objects: dict) -> List[str]:
        names: List[str] = []
        candidate_ids = []
        candidate_ids.extend(getattr(feature, "input_ids", None) or [])
        candidate_ids.extend(getattr(feature, "parent_features", None) or [])

        for feature_id in candidate_ids:
            obj_name = created_objects.get(feature_id)
            if obj_name and obj_name not in names:
                names.append(obj_name)

        return names

    def _get_input_tree_names(self, feature, tree_objects: dict) -> List[str]:
        names: List[str] = []
        candidate_ids = []
        candidate_ids.extend(getattr(feature, "input_ids", None) or [])
        candidate_ids.extend(getattr(feature, "parent_features", None) or [])

        for feature_id in candidate_ids:
            obj_name = tree_objects.get(feature_id)
            if obj_name and obj_name not in names:
                names.append(obj_name)

        return names

    def _get_parent_object_names(self, feature, created_objects: dict) -> tuple:
        parent_ids = getattr(feature, 'parent_features', None) or []
        
        if len(parent_ids) >= 2:
            base_name = created_objects.get(parent_ids[0], None)
            tool_name = created_objects.get(parent_ids[1], None)
            return base_name, tool_name
        
        return None, None

    def _generate_freecad_extrude(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for extrude operation."""
        direction = self._get_param_value(feature, 'direction', (0, 0, 1))
        distance = self._get_param_value(feature, 'distance', 10.0)

        lines = [
            f"# Extrude: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Extrusion', '{obj_name}')",
            f"{obj_name}.LengthFwd = {distance}",
            f"{obj_name}.Dir = {self._vector_expr(direction, (0, 0, 1))}",
        ]

        base_obj = self._get_input_object_name(feature, created_objects)
        if base_obj:
            lines.append(f"{obj_name}.Base = {base_obj}")
            lines.append(f"{obj_name}.Solid = True")
        else:
            lines.append(f"# Warning: Base object not found for extrusion")

        lines.append("")
        return lines

    def _generate_freecad_revolve(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for revolve operation."""
        axis = self._get_param_value(feature, 'axis', (0, 0, 1))
        angle = self._get_param_value(feature, 'angle', 360.0)
        origin = self._get_param_value(feature, 'origin', (0, 0, 0))

        lines = [
            f"# Revolve: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Revolution', '{obj_name}')",
            f"{obj_name}.Angle = {angle}",
            f"{obj_name}.Axis = {self._vector_expr(axis, (0, 0, 1))}",
            f"{obj_name}.Base = {self._vector_expr(origin)}",
            f"{obj_name}.Solid = True",
        ]

        base_obj = self._get_input_object_name(feature, created_objects)
        if base_obj:
            lines.append(f"{obj_name}.Source = {base_obj}")
        else:
            lines.append(f"# Warning: Base object not found for revolution")

        lines.append("")
        return lines

    def _generate_freecad_boolean(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for boolean operations."""
        bool_type_map = {
            'boolean_union': 'Part::Fuse',
            'boolean_cut': 'Part::Cut',
            'boolean_intersect': 'Part::Common',
        }
        fc_type = bool_type_map.get(feature.operation, 'Part::Fuse')

        lines = [
            f"# Boolean {feature.operation}: {feature.name}",
            f"{obj_name} = doc.addObject('{fc_type}', '{obj_name}')",
        ]

        # Get base and tool objects from parent features
        base_obj, tool_obj = self._get_parent_object_names(feature, created_objects)
        if base_obj:
            lines.append(f"{obj_name}.Base = {base_obj}")
        else:
            lines.append(f"# Warning: Base object not found for boolean operation")
        if tool_obj:
            lines.append(f"{obj_name}.Tool = {tool_obj}")
        else:
            lines.append(f"# Warning: Tool object not found for boolean operation")

        lines.append("")
        return lines

    def _generate_freecad_translate(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for translate operation."""
        offset = self._get_param_value(feature, 'vector', (0, 0, 0))
        
        lines = [
            f"# Translate: {feature.name}",
        ]
        
        base_obj = self._get_input_object_name(feature, created_objects)
        if base_obj:
            lines.extend([
                f"{obj_name} = doc.addObject('App::Link', '{obj_name}')",
                f"{obj_name}.LinkedObject = {base_obj}",
                f"{obj_name}.LinkTransform = True",
                f"{obj_name}.LinkPlacement = {self._placement_expr(base=offset)}",
            ])
        else:
            lines.append(f"# Warning: Base object not found for translate")
        
        lines.append("")
        return lines

    def _generate_freecad_rotate(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for rotate operation."""
        angle = self._get_param_value(feature, 'angle', 0.0)
        axis = self._get_param_value(feature, 'axis', (0, 0, 1))
        origin = self._get_param_value(feature, 'origin', (0, 0, 0))
        
        lines = [
            f"# Rotate: {feature.name}",
        ]
        
        base_obj = self._get_input_object_name(feature, created_objects)
        if base_obj:
            lines.extend([
                f"{obj_name} = doc.addObject('App::Link', '{obj_name}')",
                f"{obj_name}.LinkedObject = {base_obj}",
                f"{obj_name}.LinkTransform = True",
                f"{obj_name}.LinkPlacement = {self._placement_expr(axis=axis, angle=angle, center=origin)}",
            ])
        else:
            lines.append(f"# Warning: Base object not found for rotate")
        
        lines.append("")
        return lines

    def _generate_freecad_scale(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for scale operation."""
        scale = self._get_param_value(feature, 'scale', self._get_param_value(feature, 'factor', 1.0))
        center = self._get_param_value(feature, 'center', (0, 0, 0))
        
        lines = [
            f"# Scale: {feature.name}",
        ]
        
        base_obj = self._get_input_object_name(feature, created_objects)
        if base_obj:
            lines.extend([
                f"{obj_name} = doc.addObject('Part::Feature', '{obj_name}')",
                f"{obj_name}_shape = {base_obj}.Shape.copy()",
                f"{obj_name}_shape.scale({scale}, {self._vector_expr(center)})",
                f"{obj_name}.Shape = {obj_name}_shape",
            ])
        else:
            lines.append(f"# Warning: Base object not found for scale")
        
        lines.append("")
        return lines

    def _generate_freecad_mirror(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for mirror operation."""
        plane_origin = self._get_param_value(feature, 'plane_origin', (0, 0, 0))
        plane_normal = self._get_param_value(feature, 'plane_normal', (1, 0, 0))
        
        lines = [
            f"# Mirror: {feature.name}",
        ]
        
        base_obj = self._get_input_object_name(feature, created_objects)
        if base_obj:
            lines.extend([
                f"{obj_name} = doc.addObject('Part::Mirroring', '{obj_name}')",
                f"{obj_name}.Source = {base_obj}",
                f"{obj_name}.Base = {self._vector_expr(plane_origin)}",
                f"{obj_name}.Normal = {self._vector_expr(plane_normal, (1, 0, 0))}",
            ])
        else:
            lines.append(f"# Warning: Base object not found for mirror")
        
        lines.append("")
        return lines

    def _generate_freecad_loft(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for loft operation."""
        ruled = self._get_param_value(feature, 'ruled', False)
        input_objects = self._get_input_object_names(feature, created_objects)

        lines = [
            f"# Loft: {feature.name}",
        ]

        if input_objects and len(input_objects) >= 2:
            lines.extend([
                f"{obj_name} = doc.addObject('Part::Loft', '{obj_name}')",
                f"{obj_name}.Sections = [{', '.join(input_objects)}]",
                f"{obj_name}.Solid = True",
                f"{obj_name}.Ruled = {ruled}",
                f"{obj_name}.Closed = False",
            ])
        else:
            lines.append("# Warning: Loft sections not found")

        lines.append("")
        return lines

    def _generate_freecad_wire(
        self,
        feature,
        obj_name: str,
        created_objects: dict,
        tree_objects: dict,
    ) -> List[str]:
        """Generate FreeCAD code for wire creation from edges."""
        input_objects = self._get_input_object_names(feature, created_objects)
        input_tree_names = self._get_input_tree_names(feature, tree_objects)
        result_name = f"{obj_name}_Result"
        lines = [
            f"# Wire: {feature.name}",
        ]

        if input_objects:
            edge_exprs = [f"{name}.Shape.Edges[0]" for name in input_objects]
            lines.extend([
                f"{obj_name} = doc.addObject('App::Part', '{obj_name}')",
                f"{result_name} = doc.addObject('Part::Feature', '{result_name}')",
                f"{result_name}_edges = [{', '.join(edge_exprs)}]",
                f"{result_name}.Shape = Part.Wire({result_name}_edges)",
                f"{obj_name}.addObject({result_name})",
            ])
            for input_tree_name in input_tree_names:
                lines.append(f"{obj_name}.addObject({input_tree_name})")
        else:
            lines.append("# Warning: Wire edges not found")

        lines.append("")
        return lines

    def _generate_freecad_face(
        self,
        feature,
        obj_name: str,
        created_objects: dict,
        tree_objects: dict,
    ) -> List[str]:
        """Generate FreeCAD code for face creation from a wire."""
        base_obj = self._get_input_object_name(feature, created_objects)
        input_tree_names = self._get_input_tree_names(feature, tree_objects)
        result_name = f"{obj_name}_Result"
        lines = [
            f"# Face: {feature.name}",
        ]

        if base_obj:
            lines.extend([
                f"{obj_name} = doc.addObject('App::Part', '{obj_name}')",
                f"{result_name} = doc.addObject('Part::Feature', '{result_name}')",
                f"{result_name}_wire = {base_obj}.Shape.Wires[0] if len({base_obj}.Shape.Wires) else Part.Wire({base_obj}.Shape.Edges)",
                f"{result_name}.Shape = Part.Face({result_name}_wire)",
                f"{obj_name}.addObject({result_name})",
            ])
            for input_tree_name in input_tree_names:
                lines.append(f"{obj_name}.addObject({input_tree_name})")
        else:
            lines.append("# Warning: Base wire not found for face")

        lines.append("")
        return lines

    def _generate_freecad_sweep(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for sweep operation."""
        is_frenet = self._get_param_value(feature, 'is_frenet', False)
        input_objects = self._get_input_object_names(feature, created_objects)

        lines = [
            f"# Sweep: {feature.name}",
        ]

        if len(input_objects) >= 2:
            profile_obj, path_obj = input_objects[:2]
            lines.extend([
                f"{obj_name} = doc.addObject('Part::Sweep', '{obj_name}')",
                f"{obj_name}.Sections = [{profile_obj}]",
                f"{obj_name}.Spine = ({path_obj}, [])",
                f"{obj_name}.Solid = True",
                f"{obj_name}.Frenet = {is_frenet}",
                f"{obj_name}.Transition = 'Transformed'",
            ])
        else:
            lines.append("# Warning: Sweep profile/path not found")

        lines.append("")
        return lines

    def _generate_freecad_helical_sweep(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for helical sweep operation."""
        pitch = self._get_param_value(feature, 'pitch', 5.0)
        height = self._get_param_value(feature, 'height', 20.0)
        radius = self._get_param_value(feature, 'radius', 10.0)
        center = self._get_param_value(feature, 'center', (0, 0, 0))
        direction = self._get_param_value(feature, 'dir', (0, 0, 1))
        base_obj = self._get_input_object_name(feature, created_objects)

        lines = [
            f"# Helical Sweep: {feature.name}",
        ]

        if base_obj:
            spine_obj_name = f"{obj_name}_Spine"
            lines.extend([
                f"{spine_obj_name} = doc.addObject('Part::Helix', '{spine_obj_name}')",
                f"{spine_obj_name}.Pitch = {pitch}",
                f"{spine_obj_name}.Height = {height}",
                f"{spine_obj_name}.Radius = {radius}",
                f"{spine_obj_name}.Angle = 0",
                f"{spine_obj_name}.Placement = App.Placement({self._vector_expr(center)}, App.Rotation(App.Vector(0, 0, 1), {self._vector_expr(direction, (0, 0, 1))}))",
                f"{obj_name} = doc.addObject('Part::Sweep', '{obj_name}')",
                f"{obj_name}.Sections = [{base_obj}]",
                f"{obj_name}.Spine = ({spine_obj_name}, [])",
                f"{obj_name}.Solid = True",
                f"{obj_name}.Frenet = True",
                f"{obj_name}.Transition = 'Transformed'",
            ])
        else:
            lines.append("# Warning: Base object not found for helical sweep")

        lines.append("")
        return lines

    def _generate_freecad_linear_pattern(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for one linear pattern instance."""
        offset = self._get_param_value(feature, 'offset', (0, 0, 0))
        base_obj = self._get_input_object_name(feature, created_objects)

        lines = [
            f"# Linear Pattern: {feature.name}",
        ]

        if base_obj:
            lines.extend([
                f"{obj_name} = doc.addObject('App::Link', '{obj_name}')",
                f"{obj_name}.LinkedObject = {base_obj}",
                f"{obj_name}.LinkTransform = True",
                f"{obj_name}.LinkPlacement = {self._placement_expr(base=offset)}",
            ])
        else:
            lines.append("# Warning: Base object not found for linear pattern")

        lines.append("")
        return lines

    def _generate_freecad_radial_pattern(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for one radial pattern instance."""
        angle = self._get_param_value(feature, 'angle', 0.0)
        axis = self._get_param_value(feature, 'axis', (0, 0, 1))
        center = self._get_param_value(feature, 'center', (0, 0, 0))
        base_obj = self._get_input_object_name(feature, created_objects)

        lines = [
            f"# Radial Pattern: {feature.name}",
        ]

        if base_obj:
            lines.extend([
                f"{obj_name} = doc.addObject('App::Link', '{obj_name}')",
                f"{obj_name}.LinkedObject = {base_obj}",
                f"{obj_name}.LinkTransform = True",
                f"{obj_name}.LinkPlacement = {self._placement_expr(axis=axis, angle=angle, center=center)}",
            ])
        else:
            lines.append("# Warning: Base object not found for radial pattern")

        lines.append("")
        return lines

    def _generate_freecad_fillet(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for fillet operation."""
        radius = self._get_param_value(feature, 'radius', 1.0)
        edge_indices = self._get_param_value(feature, 'edge_indices', [])

        lines = [
            f"# Fillet: {feature.name}",
        ]

        base_obj = self._get_input_object_name(feature, created_objects)
        if base_obj:
            lines.extend([
                f"{obj_name} = doc.addObject('Part::Feature', '{obj_name}')",
                f"{obj_name}_edge_indices = {self._list_expr(edge_indices)}",
                f"{obj_name}_edges = [{base_obj}.Shape.Edges[i] for i in {obj_name}_edge_indices]",
                f"{obj_name}.Shape = {base_obj}.Shape.makeFillet({radius}, {obj_name}_edges)",
            ])
        else:
            lines.append(f"# Warning: Base object not found for fillet")

        lines.append("")
        return lines

    def _generate_freecad_chamfer(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for chamfer operation."""
        distance = self._get_param_value(feature, 'distance', 1.0)
        edge_indices = self._get_param_value(feature, 'edge_indices', [])

        lines = [
            f"# Chamfer: {feature.name}",
        ]

        base_obj = self._get_input_object_name(feature, created_objects)
        if base_obj:
            lines.extend([
                f"{obj_name} = doc.addObject('Part::Feature', '{obj_name}')",
                f"{obj_name}_edge_indices = {self._list_expr(edge_indices)}",
                f"{obj_name}_edges = [{base_obj}.Shape.Edges[i] for i in {obj_name}_edge_indices]",
                f"{obj_name}.Shape = {base_obj}.Shape.makeChamfer({distance}, {obj_name}_edges)",
            ])
        else:
            lines.append(f"# Warning: Base object not found for chamfer")

        lines.append("")
        return lines

    def _generate_freecad_shell(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for shell operation."""
        thickness = self._get_param_value(feature, 'thickness', 1.0)
        face_indices = self._get_param_value(feature, 'face_indices', [])

        lines = [
            f"# Shell: {feature.name}",
        ]

        base_obj = self._get_input_object_name(feature, created_objects)
        if base_obj:
            lines.extend([
                f"{obj_name} = doc.addObject('Part::Feature', '{obj_name}')",
                f"{obj_name}_face_indices = {self._list_expr(face_indices)}",
                f"{obj_name}_faces = [{base_obj}.Shape.Faces[i] for i in {obj_name}_face_indices]",
                f"{obj_name}.Shape = {base_obj}.Shape.makeThickness({obj_name}_faces, -{thickness}, 1e-3)",
            ])
        else:
            lines.append(f"# Warning: Base object not found for shell")

        lines.append("")
        return lines

    def _generate_freecad_sketch(self, feature, obj_name: str) -> List[str]:
        """Generate FreeCAD code for sketch/profile operations."""
        width = self._get_param_value(feature, 'width', 0.0)
        height = self._get_param_value(feature, 'height', 0.0)
        center = self._get_param_value(feature, 'center', (0, 0, 0))
        normal = self._get_param_value(feature, 'normal', (0, 0, 1))
        
        lines = [
            f"# Sketch: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Feature', '{obj_name}')",
        ]
        
        if "rectangle" in feature.operation.lower():
            cx, cy, cz = center
            half_w, half_h = width / 2, height / 2
            lines.extend([
                f"wire = Part.makePolygon([",
                f"    App.Vector({cx-half_w}, {cy-half_h}, {cz}),",
                f"    App.Vector({cx+half_w}, {cy-half_h}, {cz}),",
                f"    App.Vector({cx+half_w}, {cy+half_h}, {cz}),",
                f"    App.Vector({cx-half_w}, {cy+half_h}, {cz}),",
                f"    App.Vector({cx-half_w}, {cy-half_h}, {cz})",
                f"])",
                f"{obj_name}.Shape = Part.Face(wire)",
            ])
        elif "circle" in feature.operation.lower():
            cx, cy, cz = center
            radius = self._get_param_value(feature, 'radius', 10.0)
            lines.extend([
                f"circle = Part.makeCircle({radius}, App.Vector({cx}, {cy}, {cz}), App.Vector({normal[0]}, {normal[1]}, {normal[2]}))",
                f"wire = Part.Wire(circle)",
                f"{obj_name}.Shape = Part.Face(wire)",
            ])
        elif feature.operation == "make_line":
            start = self._get_param_value(feature, 'start', (0, 0, 0))
            end = self._get_param_value(feature, 'end', (10, 0, 0))
            lines.extend([
                f"{obj_name}.Shape = Part.makeLine({self._vector_expr(start)}, {self._vector_expr(end)})",
            ])
        elif feature.operation == "make_arc":
            start = self._get_param_value(feature, 'start')
            middle = self._get_param_value(feature, 'middle')
            end = self._get_param_value(feature, 'end')
            if start is not None and middle is not None and end is not None:
                lines.extend([
                    f"{obj_name}_arc = Part.Arc({self._vector_expr(start)}, {self._vector_expr(middle)}, {self._vector_expr(end)})",
                    f"{obj_name}.Shape = {obj_name}_arc.toShape()",
                ])
            else:
                center = self._get_param_value(feature, 'center', (0, 0, 0))
                radius = self._get_param_value(feature, 'radius', 10.0)
                start_angle = self._get_param_value(feature, 'start_angle', 0.0)
                end_angle = self._get_param_value(feature, 'end_angle', 90.0)
                lines.extend([
                    f"{obj_name}.Shape = Part.makeCircle({radius}, {self._vector_expr(center)}, {self._vector_expr(normal, (0, 0, 1))}, {start_angle}, {end_angle})",
                ])
        elif feature.operation == "make_polyline":
            points = self._get_param_value(feature, 'points', [])
            closed = self._get_param_value(feature, 'closed', False)
            point_exprs = [self._vector_expr(point) for point in points]
            if closed and point_exprs and point_exprs[0] != point_exprs[-1]:
                point_exprs.append(point_exprs[0])
            lines.extend([
                f"{obj_name}.Shape = Part.makePolygon([{', '.join(point_exprs)}])",
            ])
        elif feature.operation == "make_helix":
            pitch = self._get_param_value(feature, 'pitch', 5.0)
            height = self._get_param_value(feature, 'height', 20.0)
            radius = self._get_param_value(feature, 'radius', 10.0)
            direction = self._get_param_value(feature, 'dir', (0, 0, 1))
            lines.extend([
                f"{obj_name}_shape = Part.makeHelix({pitch}, {height}, {radius})",
                f"{obj_name}_dir = {self._vector_expr(direction, (0, 0, 1))}",
                f"{obj_name}_default_dir = App.Vector(0, 0, 1)",
                f"{obj_name}_rotation_axis = {obj_name}_default_dir.cross({obj_name}_dir)",
                f"{obj_name}_angle = math.degrees({obj_name}_default_dir.getAngle({obj_name}_dir)) if {obj_name}_dir.Length > 1e-9 else 0.0",
                f"if {obj_name}_rotation_axis.Length > 1e-9 and abs({obj_name}_angle) > 1e-9:",
                f"    {obj_name}_shape.rotate(App.Vector(0, 0, 0), {obj_name}_rotation_axis, {obj_name}_angle)",
                f"elif {obj_name}_dir.Length > 1e-9 and {obj_name}_dir.dot({obj_name}_default_dir) < 0:",
                f"    {obj_name}_shape.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 180)",
                f"{obj_name}_shape.translate({self._vector_expr(center)})",
                f"{obj_name}.Shape = {obj_name}_shape",
            ])

        lines.append("")
        return lines
