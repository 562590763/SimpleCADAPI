---
name: simplecad-to-freecad-converter
description: |
  **USE THIS SKILL when converting SimpleCAD API code to FreeCAD macro code.**
  
  This skill provides comprehensive guidance for converting Python scripts that use the SimpleCAD API 
  (a thin wrapper around OpenCASCADE) into FreeCAD-compatible Python macros that generate visible 
  objects in FreeCAD's tree view.
  
  **When to use:**
  - Converting simplecadapi-based Python scripts to FreeCAD
  - Generating FreeCAD macros from SimpleCAD geometry code
  - Translating OCP/OpenCASCADE operations to FreeCAD's document-based model
  
  **Key concepts covered:**
  - API mapping between SimpleCAD and FreeCAD
  - Document object creation and management
  - Helper functions for common operations
  - Best practices for successful conversion
---

# SimpleCAD to FreeCAD Converter Guide

## Core Philosophy

### Understanding the Two APIs

**SimpleCAD (via OCP/OpenCASCADE):**
- Fluent/chainable API style
- Direct geometry manipulation (BRep, TopoDS_Shape)
- Stateless operations on shapes
- Returns raw geometric shapes

**FreeCAD:**
- Document-based object model
- Parametric feature-based modeling
- Objects must be added to documents to be visible
- Separates geometry (Shape) from document objects

### The Mental Model Shift

The key insight: **SimpleCAD operates on pure geometry, while FreeCAD operates on document objects that wrap geometry.**

When converting, you must:
1. Create the geometry (similar to SimpleCAD)
2. Wrap it in a FreeCAD document object
3. Add it to the document
4. Recompute and refresh the view

## API Mapping Reference

### Basic Shapes

| SimpleCAD | FreeCAD Equivalent |
|-----------|-------------------|
| `box(width, height, depth, center)` | `fc_make_box(width, height, depth, center, _name)` |
| `cylinder(radius, height, center, axis)` | `fc_make_cylinder(radius, height, center, axis, _name)` |
| `sphere(radius, center)` | `fc_make_sphere(radius, center, _name)` |
| `cone(radius1, radius2, height, center, axis)` | `fc_make_cone(r1, r2, height, center, axis, _name)` |
| `torus(radius1, radius2, center, axis)` | `fc_make_torus(r1, r2, center, axis, _name)` |
| `helix(pitch, height, radius, center, axis)` | `fc_make_helix(pitch, height, radius, center, axis, _name)` |
| `polygon(sides, radius, center, axis)` | `fc_make_polygon(sides, radius, center, axis, _name)` |
| `plane(length, width, center, axis)` | `fc_make_plane(length, width, center, axis, _name)` |

**Note:** FreeCAD functions take an optional `_name` parameter for object naming.

### Boolean Operations

| SimpleCAD | FreeCAD Equivalent |
|-----------|-------------------|
| `union(shape1, shape2, ...)` or `shape1 + shape2` | `fc_union_shapes(shape1, shape2, ..., _name)` |
| `cut(base, tool)` or `base - tool` | `fc_cut_shapes(base, tool, _name)` |
| `intersect(shape1, shape2)` or `shape1 & shape2` | `fc_intersect_shapes(shape1, shape2, _name)` |

### Transformations

| SimpleCAD | FreeCAD Equivalent |
|-----------|-------------------|
| `translate(shape, vector)` | `fc_translate_shape(shape, vector, _name)` |
| `rotate(shape, angle, axis, origin)` | `fc_rotate_shape(shape, angle, axis, origin, _name)` |
| `mirror(shape, plane_origin, plane_normal)` | `fc_mirror_shape(shape, plane_origin, plane_normal, _name)` |
| `scale(shape, factor, origin)` | `fc_scale_shape(shape, factor, origin, _name)` |

### Feature Operations

| SimpleCAD | FreeCAD Equivalent |
|-----------|-------------------|
| `fillet(shape, edges, radius)` | `fc_fillet_edges(shape, edges, radius, _name)` |
| `chamfer(shape, edges, distance)` | `fc_chamfer_edges(shape, edges, distance, _name)` |
| `shell(shape, faces, thickness)` | `fc_shell_faces(shape, faces, thickness, _name)` |
| `loft(profiles, ruled, closed)` | `fc_loft_profiles(profiles, ruled, closed, _name)` |
| `sweep(profile, path, fill)` | `fc_sweep_profile(profile, path, fill, _name)` |

### Sketch Operations

| SimpleCAD | FreeCAD Equivalent |
|-----------|-------------------|
| `sketch(plane)` | `fc_make_sketch(plane)` |
| `sketch.add_line(p1, p2)` | `sketch.addGeometry(Part.Line(p1, p2), False)` |
| `sketch.add_circle(center, radius)` | `sketch.addGeometry(Part.Circle(center, axis, radius), False)` |
| `extrude(sketch, distance, direction)` | `fc_extrude_sketch(sketch, distance, direction, _name)` |
| `revolve(sketch, axis, angle)` | `fc_revolve_sketch(sketch, axis, angle, _name)` |

### Import/Export

| SimpleCAD | FreeCAD Equivalent |
|-----------|-------------------|
| `export_stl(shape, file_path)` | `fc_export_stl(shape, file_path, doc_name, object_name)` |
| `export_step(shape, file_path)` | `fc_export_step(shape, file_path, doc_name, object_name)` |
| `import_stl(file_path)` | `fc_import_stl(file_path)` |
| `import_step(file_path)` | `fc_import_step(file_path)` |

## Conversion Workflow

### Step 1: Analyze the SimpleCAD Code

Read the SimpleCAD script and identify:
1. All imports (remove simplecadapi imports)
2. All function calls and their arguments
3. Variable assignments and dependencies
4. Export calls (export_stl, export_step)

### Step 2: Map to FreeCAD API

For each SimpleCAD function call:
1. Find the corresponding FreeCAD function from the mapping tables
2. Note any parameter differences (e.g., `_name` parameter in FreeCAD)
3. Handle coordinate system differences if any

### Step 3: Generate the FreeCAD Code

Structure your generated code as follows:

```python
# 1. Imports and setup
import math
from pathlib import Path

try:
    import FreeCAD as App
    import Part
except ImportError as exc:
    raise RuntimeError(
        "This generated script must run inside FreeCAD's Python environment."
    ) from exc

# 2. Helper functions (include from the reference above)
DEFAULT_DOC_NAME = "ConvertedModel"

# ... helper functions ...

# 3. Converted model code
# (Your converted SimpleCAD code using fc_* functions)

# 4. Main execution
def main():
    obj = run({}, DEFAULT_DOC_NAME)

if __name__ == '__main__':
    main()
```

## Common Pitfalls and Solutions

### 1. Coordinate System Differences

**Issue:** SimpleCAD and FreeCAD may use different coordinate conventions.

**Solution:** Always verify coordinate transformations. Most primitives match directly, but some may require axis swapping or rotation.

### 2. Object Visibility

**Issue:** Objects created in FreeCAD but not visible in the tree view.

**Solution:** Ensure you are:
1. Creating objects via `doc.addObject()` or helper functions
2. Calling `doc.recompute()` after changes
3. Using `_refresh_view()` to update the GUI

### 3. Shape vs Object Confusion

**Issue:** Trying to use a raw shape where a document object is expected.

**Solution:** Remember the distinction:
- **Shape:** Raw geometry (vertices, edges, faces)
- **Object:** Document container that wraps a Shape

Use `_create_feature_from_shape()` to wrap shapes in objects.

### 4. Boolean Operation Failures

**Issue:** Boolean operations (union, cut) fail or produce unexpected results.

**Solution:**
1. Ensure shapes are valid solids (not just surfaces)
2. Check for self-intersections
3. Try using FreeCAD's built-in boolean features (Part::Fuse, Part::Cut) instead of low-level shape operations

### 5. Export Path Issues

**Issue:** Export functions fail with path errors.

**Solution:** Always use `_resolve_output_path()` to handle:
- Relative vs absolute paths
- Directory creation
- Cross-platform path separators

## Best Practices

### 1. Always Provide Object Names

While the `_name` parameter is optional, providing meaningful names makes debugging and organization easier:

```python
# Good
base_plate = fc_make_box(100, 50, 10, _name="BasePlate")

# Less helpful
base_plate = fc_make_box(100, 50, 10)
```

### 2. Use Descriptive Variable Names

Maintain clear naming conventions that reflect the geometry:

```python
# Good
mounting_hole_diameter = 5
flange_thickness = 8

# Avoid
mh_d = 5
ft = 8
```

### 3. Organize Code by Feature

Group related operations together and add comments:

```python
# --- Base Plate ---
base = fc_make_box(100, 50, 10, _name="BasePlate")

# --- Mounting Holes ---
hole1 = fc_make_cylinder(2.5, 15, center=(20, 15, -2.5), _name="Hole1")
hole2 = fc_make_cylinder(2.5, 15, center=(80, 15, -2.5), _name="Hole2")

# --- Assembly ---
plate_with_holes = fc_cut_shapes(base, hole1, hole2, _name="BaseWithHoles")
```

### 4. Validate Geometry When Possible

Add checks to ensure geometry is valid:

```python
result = fc_union_shapes(part1, part2)

# Verify the result is valid
if hasattr(result, 'Shape'):
    if not result.Shape.isValid():
        print("Warning: Resulting shape is not valid!")
```

### 5. Handle Errors Gracefully

Wrap operations in try-except blocks when dealing with user input or file operations:

```python
try:
    fc_export_step(final_part, output_path)
    print(f"Successfully exported to {output_path}")
except Exception as e:
    print(f"Export failed: {e}")
```
