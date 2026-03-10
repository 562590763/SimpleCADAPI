# Visual Feedback Skill

## Skill Overview

The Visual Feedback skill renders STEP format CAD models into multi-view images, helping verify if the generated CAD models match the design intent.

## Core Features

- **Multi-view Rendering**: Automatically renders front, top, right, isometric, and perspective views
- **High Quality Output**: Supports custom resolution and rendering quality
- **Automated Workflow**: Seamless integration with CAD generation scripts
- **Batch Processing**: Supports batch rendering of multiple STEP files

## Dependencies

### Required Dependencies

- `cadquery` >= 2.5.2
- `vtk` >= 9.0.0
- `Pillow` >= 9.0.0 (optional, for image post-processing)

### Install Dependencies

```bash
pip install cadquery vtk Pillow
```

Or use the provided installation script:

```bash
bash scripts/install.sh
```

## Usage

### Basic Usage

```bash
python scripts/render_step.py <step_file> [output_dir]
```

### Examples

```bash
# Render a single STEP file
python scripts/render_step.py model.step

# Specify output directory
python scripts/render_step.py model.step ./output_images

# Use in Python scripts
from render_step import render_step_to_images

results = render_step_to_images("model.step", "./output")
for view_name, file_path in results:
    print(f"{view_name}: {file_path}")
```

### Python API

```python
from render_step import StepRenderer

# Create renderer
renderer = StepRenderer(
    step_file="model.step",
    output_dir="./output",
    image_width=1200,  # optional: default 800
    image_height=900   # optional: default 600
)

# Render all standard views
results = renderer.render_multiple_views()

# Render specific view
renderer.render_view(
    view_name="custom",
    azimuth=60,      # azimuth angle
    elevation=25,    # elevation angle
    zoom=1.2         # zoom ratio
)
```

## Rendering View Reference

| View Name | Azimuth | Elevation | Description |
|-----------|---------|-----------|-------------|
| front | 0° | 0° | Front view (XY plane) |
| top | 0° | 90° | Top view (from Z axis down) |
| right | 90° | 0° | Right view (YZ plane) |
| isometric | 45° | 35° | Isometric view |
| perspective | 30° | 20° | Perspective view |

## Output File Naming

Rendered images are named according to the following rules:

```
<model_name>_<view_name>.png
```

Examples:
- `gear_involute_v2_front.png`
- `gear_involute_v2_top.png`
- `gear_involute_v2_isometric.png`

## Advanced Features

### Custom Rendering Parameters

```python
renderer = StepRenderer("model.step")

# Set high quality rendering
renderer.image_width = 1920
renderer.image_height = 1080

# Custom view
renderer.render_view(
    view_name="detail",
    azimuth=75,
    elevation=40,
    zoom=1.5
)
```

### Batch Rendering

```python
import glob
from render_step import render_step_to_images

# Render all STEP files in directory
step_files = glob.glob("*.step")
for step_file in step_files:
    render_step_to_images(step_file, "./output")
```

## Integration with SimpleCAD

This skill can be seamlessly integrated with SimpleCAD API for model validation:

```python
import simplecadapi as scad
from render_step import render_step_to_images

# Create model
gear = scad.make_cylinder_rsolid(10.0, 5.0)
scad.export_step(gear, "model.step")

# Render validation
render_step_to_images("model.step", "./preview")
```

## Workflow Suggestions

### 1. Design-Verification Loop

```python
# 1. Create CAD model
gear = create_gear(...)

# 2. Export STEP file
scad.export_step(gear, "gear.step")

# 3. Render validation
render_step_to_images("gear.step", "./preview")

# 4. Review images, if not satisfied modify parameters and regenerate
```

### 2. Automated Testing

```python
def test_gear_geometry():
    gear = create_gear(num_teeth=24, module=2.0)
    scad.export_step(gear, "test_gear.step")
    
    # Render and check
    images = render_step_to_images("test_gear.step")
    
    # Can add automated check logic
    assert len(images) == 5  # Should generate 5 views
    assert all(os.path.exists(img) for _, img in images)
```

## Troubleshooting

### Issue 1: Black Screen Rendering

**Cause**: Model may be out of view or too small

**Solution**: Adjust camera parameters or use `zoom` parameter

```python
renderer.render_view("test", zoom=0.5)  # Zoom out
```

### Issue 2: Missing Dependencies

**Error Message**: `ModuleNotFoundError: No module named 'vtk'`

**Solution**: Install dependencies

```bash
pip install vtk
```

### Issue 3: STEP File Loading Failure

**Cause**: STEP file format is incorrect or corrupted

**Solution**: Check if STEP file can be opened in other CAD software

## File Structure

```
visual-feedback/
├── SKILL.md              # This document
├── scripts/
│   ├── render_step.py    # Main rendering script
│   └── install.sh        # Dependency installation script
└── references/
    ├── API.md            # Detailed API documentation
    └── EXAMPLES.md       # More examples
```

## License

MIT License

## Version History

- v1.0.0 (2026-03-09): Initial version
  - Support multi-view rendering
  - Support custom rendering parameters
  - Integrate SimpleCAD workflow
