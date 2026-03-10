# PointCloud Renderer Skill

## Skill Overview

The PointCloud Renderer skill renders point cloud files into multi-view images, enabling visualization of 3D scanned data or point cloud datasets. This skill bridges the gap between raw point cloud data and visual feedback, allowing you to generate CAD models from point cloud inputs.

## Core Features

- **Multi-format Support**: Supports PLY, PCD, XYZ, PTS, and LAS/LAZ point cloud formats
- **Multi-view Rendering**: Automatically renders front, top, right, isometric, and perspective views
- **Customizable Visualization**: Configurable point size, color schemes, and background
- **Automatic Centering & Scaling**: Automatically centers and scales point clouds for optimal viewing
- **High Quality Output**: Supports custom resolution and rendering quality
- **Batch Processing**: Supports batch rendering of multiple point cloud files

## Supported Formats

| Format | Extension | Description |
|--------|-----------|-------------|
| PLY | `.ply` | Polygon File Format (ASCII/Binary) |
| PCD | `.pcd` | Point Cloud Data (PCL format) |
| XYZ | `.xyz` | Simple ASCII XYZ coordinates |
| PTS | `.pts` | Point Cloud ASCII format |
| LAS/LAZ | `.las`, `.laz` | LASer file format (LiDAR data) |

## Dependencies

### Required Dependencies

- `open3d` >= 0.16.0 - Core point cloud processing and rendering
- `numpy` >= 1.21.0 - Numerical operations
- `Pillow` >= 9.0.0 - Image processing (optional)

### Optional Dependencies

- `laspy` >= 2.3.0 - For LAS/LAZ file support (if working with LiDAR data)

### Install Dependencies

```bash
pip install open3d numpy Pillow laspy
```

Or use the provided installation script:

```bash
bash scripts/install.sh
```

## Usage

### Basic Usage

```bash
python scripts/render_pointcloud.py <pointcloud_file> [output_dir]
```

### Examples

```bash
# Render a single point cloud file
python scripts/render_pointcloud.py scan.ply

# Specify output directory
python scripts/render_pointcloud.py scan.ply ./output_images

# Use in Python scripts
from render_pointcloud import render_pointcloud_to_images

results = render_pointcloud_to_images("scan.ply", "./output")
for view_name, file_path in results:
    print(f"{view_name}: {file_path}")
```

### Python API

```python
from render_pointcloud import PointCloudRenderer

# Create renderer
renderer = PointCloudRenderer(
    pointcloud_file="scan.ply",
    output_dir="./output",
    image_width=1200,      # optional: default 800
    image_height=900,      # optional: default 600
    point_size=2.0,        # optional: default 1.5
                bg_color=[1.0, 1.0, 1.0]  # optional: background color (white)
)

# Render all standard views
results = renderer.render_multiple_views()

# Render specific view
renderer.render_view(
    view_name="custom",
    azimuth=60,      # azimuth angle (degrees)
    elevation=25,    # elevation angle (degrees)
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
<pointcloud_name>_<view_name>.png
```

Examples:
- `scan_data_front.png`
- `scan_data_top.png`
- `scan_data_isometric.png`

## Advanced Features

### Custom Rendering Parameters

```python
renderer = PointCloudRenderer("scan.ply")

# Set high quality rendering
renderer.image_width = 1920
renderer.image_height = 1080
renderer.point_size = 3.0  # Larger points for sparse clouds

# Custom view
renderer.render_view(
    view_name="detail",
    azimuth=75,
    elevation=40,
    zoom=1.5
)
```

### Custom Color Schemes

```python
from render_pointcloud import PointCloudRenderer, ColorScheme

# Use height-based coloring
renderer = PointCloudRenderer("scan.ply", color_scheme=ColorScheme.HEIGHT)

# Use intensity-based coloring (if available in point cloud)
renderer = PointCloudRenderer("scan.ply", color_scheme=ColorScheme.INTENSITY)

# Use custom uniform color
renderer = PointCloudRenderer("scan.ply", color_scheme=ColorScheme.UNIFORM)
renderer.uniform_color = [1.0, 0.5, 0.2]  # Orange
```

### Batch Rendering

```python
import glob
from render_pointcloud import render_pointcloud_to_images

# Render all PLY files in directory
pointcloud_files = glob.glob("*.ply")
for pc_file in pointcloud_files:
    render_pointcloud_to_images(pc_file, "./output")
```

## Integration with SimpleCAD

This skill can be integrated with SimpleCAD API for reverse engineering workflows:

```python
import simplecadapi as scad
from render_pointcloud import render_pointcloud_to_images

# Visualize point cloud first
images = render_pointcloud_to_images("scan.ply", "./preview")

# Analyze point cloud and create CAD model
# (Based on the visual feedback, determine modeling approach)

# Create reconstructed model
model = reconstruct_from_pointcloud("scan.ply")
scad.export_step(model, "reconstructed.step")
```

## Workflow Suggestions

### 1. Point Cloud to CAD Workflow

```python
# 1. Visualize point cloud from multiple angles
images = render_pointcloud_to_images("scan.ply", "./preview")

# 2. Review images to understand the geometry
# 3. Based on visual feedback, choose modeling strategy
# 4. Create CAD model
model = create_model_based_on_visual_analysis(...)

# 5. Export and validate
scad.export_step(model, "model.step")
```

### 2. Quality Control Loop

```python
# Compare point cloud with generated CAD model
pc_images = render_pointcloud_to_images("scan.ply", "./pc_views")
cad_images = render_step_to_images("model.step", "./cad_views")

# Visually compare corresponding views
```

## Troubleshooting

### Issue 1: Black Screen Rendering

**Cause**: Point cloud may be too small or too large for default camera

**Solution**: Adjust zoom or let the skill auto-scale

```python
renderer = PointCloudRenderer("scan.ply", auto_scale=True)
```

### Issue 2: Missing Dependencies

**Error Message**: `ModuleNotFoundError: No module named 'open3d'`

**Solution**: Install dependencies

```bash
pip install open3d
```

### Issue 3: LAS/LAZ File Loading Failure

**Cause**: Missing laspy dependency

**Solution**: Install laspy

```bash
pip install laspy
```

### Issue 4: Large Point Clouds (Memory Issues)

**Cause**: Point cloud with millions of points exceeds memory

**Solution**: Use voxel downsampling

```python
renderer = PointCloudRenderer("large_scan.ply")
renderer.downsample(voxel_size=0.01)  # Downsample before rendering
```

## File Structure

```
pointcloud-renderer/
├── SKILL.md                   # This document
├── scripts/
│   ├── render_pointcloud.py   # Main rendering script
│   └── install.sh             # Dependency installation script
└── references/
    ├── API.md                 # Detailed API documentation
    └── EXAMPLES.md            # More examples
```

## License

MIT License

## Version History

- v1.0.0 (2026-03-10): Initial version
  - Support PLY, PCD, XYZ, PTS, LAS/LAZ formats
  - Multi-view rendering (front, top, right, isometric, perspective)
  - Configurable point size and color schemes
  - Integration with SimpleCAD workflow
