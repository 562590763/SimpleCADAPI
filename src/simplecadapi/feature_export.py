"""
Feature export utilities for SimpleCADAPI.

This module provides functions to export feature history to various formats,
including JSON, STEP with metadata, and CAD software-specific formats.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .feature_history import FeatureHistory, Feature, FeatureType
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
    data = history.to_dict()

    # Remove or simplify geometry data if not needed
    if not include_geometry:
        for feature_data in data.get("features", []):
            # Remove bulky output data
            if "output" in feature_data:
                feature_data["output"] = "<geometry data omitted>"

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

    def to_json(self, filepath: str, indent: int = 2) -> str:
        """Export to JSON format."""
        return export_feature_history_to_json(self.history, filepath, indent)

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
            "import Part",
            "import Draft",
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

        for i, feature_id in enumerate(self.history.ordered_features):
            feature = self.history.features.get(feature_id)
            if not feature:
                continue

            obj_name = f"Feature_{i:03d}_{feature.name}"

            # Generate code based on operation type
            if feature.operation == "make_box":
                lines.extend(self._generate_freecad_box(feature, obj_name))
            elif feature.operation == "make_cylinder":
                lines.extend(self._generate_freecad_cylinder(feature, obj_name))
            elif feature.operation == "make_sphere":
                lines.extend(self._generate_freecad_sphere(feature, obj_name))
            elif feature.operation == "extrude":
                lines.extend(self._generate_freecad_extrude(feature, obj_name, created_objects))
            elif feature.operation == "revolve":
                lines.extend(self._generate_freecad_revolve(feature, obj_name, created_objects))
            elif feature.operation in ["boolean_union", "boolean_cut", "boolean_intersect"]:
                lines.extend(self._generate_freecad_boolean(feature, obj_name, created_objects))
            elif feature.operation == "fillet":
                lines.extend(self._generate_freecad_fillet(feature, obj_name, created_objects))
            elif feature.operation == "chamfer":
                lines.extend(self._generate_freecad_chamfer(feature, obj_name, created_objects))
            elif feature.operation in ["make_rectangle", "make_circle", "make_polygon"]:
                lines.extend(self._generate_freecad_sketch(feature, obj_name))
            else:
                lines.append(f"# Unknown operation: {feature.operation}")
                lines.append(f"# Feature: {feature.name}")
                lines.append("")
                continue

            created_objects[feature_id] = obj_name

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

    def _get_param_value(self, feature, param_name, default=None):
        """Get parameter value from feature."""
        param = feature.parameters.get(param_name)
        if param:
            return param.value
        return default

    def _generate_freecad_box(self, feature, obj_name: str) -> List[str]:
        """Generate FreeCAD code for box primitive."""
        width = self._get_param_value(feature, 'width', 10.0)
        height = self._get_param_value(feature, 'height', 10.0)
        depth = self._get_param_value(feature, 'depth', 10.0)

        return [
            f"# Box: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Box', '{obj_name}')",
            f"{obj_name}.Width = {width}",
            f"{obj_name}.Height = {height}",
            f"{obj_name}.Length = {depth}",
            "",
        ]

    def _generate_freecad_cylinder(self, feature, obj_name: str) -> List[str]:
        """Generate FreeCAD code for cylinder primitive."""
        radius = self._get_param_value(feature, 'radius', 5.0)
        height = self._get_param_value(feature, 'height', 10.0)

        return [
            f"# Cylinder: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Cylinder', '{obj_name}')",
            f"{obj_name}.Radius = {radius}",
            f"{obj_name}.Height = {height}",
            "",
        ]

    def _generate_freecad_sphere(self, feature, obj_name: str) -> List[str]:
        """Generate FreeCAD code for sphere primitive."""
        radius = self._get_param_value(feature, 'radius', 5.0)

        return [
            f"# Sphere: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Sphere', '{obj_name}')",
            f"{obj_name}.Radius = {radius}",
            "",
        ]

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

        dx, dy, dz = (0, 0, 1)
        if isinstance(direction, (list, tuple)) and len(direction) >= 3:
            dx, dy, dz = direction[0], direction[1], direction[2]

        lines = [
            f"# Extrude: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Extrusion', '{obj_name}')",
            f"{obj_name}.LengthFwd = {distance}",
            f"{obj_name}.Dir = ({dx}, {dy}, {dz})",
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

        lines = [
            f"# Revolve: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Revolution', '{obj_name}')",
            f"{obj_name}.Angle = {angle}",
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
        if tool_obj:
            lines.append(f"{obj_name}.Tool = {tool_obj}")

        lines.append("")
        return lines

    def _generate_freecad_fillet(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for fillet operation."""
        radius = self._get_param_value(feature, 'radius', 1.0)

        lines = [
            f"# Fillet: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Fillet', '{obj_name}')",
            f"{obj_name}.Radius = {radius}",
        ]

        base_obj = self._get_input_object_name(feature, created_objects)
        if base_obj:
            lines.append(f"{obj_name}.Base = {base_obj}")
            lines.append(f"{obj_name}.Edges = {base_obj}.Shape.Edges")

        lines.append("")
        return lines

    def _generate_freecad_chamfer(self, feature, obj_name: str, created_objects: dict) -> List[str]:
        """Generate FreeCAD code for chamfer operation."""
        distance = self._get_param_value(feature, 'distance', 1.0)

        lines = [
            f"# Chamfer: {feature.name}",
            f"{obj_name} = doc.addObject('Part::Chamfer', '{obj_name}')",
            f"{obj_name}.Size = {distance}",
        ]

        base_obj = self._get_input_object_name(feature, created_objects)
        if base_obj:
            lines.append(f"{obj_name}.Base = {base_obj}")
            lines.append(f"{obj_name}.Edges = {base_obj}.Shape.Edges")

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
        
        lines.append("")
        return lines