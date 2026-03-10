# PointCloud Renderer API Documentation

## Table of Contents

- [PointCloudRenderer Class](#pointcloudrenderer-class)
- [ColorScheme Enum](#colorscheme-enum)
- [Convenience Functions](#convenience-functions)
- [Command Line Interface](#command-line-interface)
- [Examples](#examples)

---

## PointCloudRenderer Class

Main class for rendering point cloud files to images.

### Constructor

```python
PointCloudRenderer(
    pointcloud_file: Union[str, Path],
    output_dir: str = ".",
    image_width: int = 800,
    image_height: int = 600,
    point_size: float = 1.5,
    bg_color: List[float] = None,
    color_scheme: ColorScheme = ColorScheme.UNIFORM,
    uniform_color: List[float] = None,
    auto_scale: bool = True
)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pointcloud_file` | `str` or `Path` | required | Path to point cloud file |
| `output_dir` | `str` | `"."` | Output directory for rendered images |
| `image_width` | `int` | `800` | Image width in pixels |
| `image_height` | `int` | `600` | Image height in pixels |
| `point_size` | `float` | `1.5` | Size of rendered points |
| `bg_color` | `List[float]` | `[1.0, 1.0, 1.0]` | Background color RGB [0-1] |
| `color_scheme` | `ColorScheme` | `UNIFORM` | Color scheme for points |
| `uniform_color` | `List[float]` | `[0.7, 0.7, 0.7]` | Uniform color RGB [0-1] |
| `auto_scale` | `bool` | `True` | Auto-center and scale point cloud |

### Methods

#### `render_view(view_name, azimuth=45, elevation=30, zoom=1.0)`

Render the point cloud from a specific view angle.

**Parameters:**
- `view_name` (str): Name for the output file
- `azimuth` (float): Azimuth angle in degrees (rotation around Z axis)
- `elevation` (float): Elevation angle in degrees (rotation around X axis)
- `zoom` (float): Zoom ratio (1.0 = default)

**Returns:**
- `str`: Path to rendered image file, or `None` if failed

**Example:**
```python
renderer = PointCloudRenderer("scan.ply")
image_path = renderer.render_view("custom", azimuth=60, elevation=25, zoom=1.2)
```

#### `render_multiple_views()`

Render the point cloud from all standard views.

**Returns:**
- `List[Tuple[str, str]]`: List of `(view_name, file_path)` tuples

**Example:**
```python
renderer = PointCloudRenderer("scan.ply")
results = renderer.render_multiple_views()
for view_name, path in results:
    print(f"{view_name}: {path}")
```

#### `downsample(voxel_size=0.01)`

Downsample the point cloud using voxel grid.

**Parameters:**
- `voxel_size` (float): Size of voxel for downsampling (default: 0.01)

**Example:**
```python
renderer = PointCloudRenderer("large_scan.ply")
renderer.downsample(voxel_size=0.05)  # Reduce point density
renderer.render_multiple_views()
```

#### `estimate_normals(radius=0.1, max_nn=30)`

Estimate normals for the point cloud.

**Parameters:**
- `radius` (float): Search radius for normal estimation (default: 0.1)
- `max_nn` (int): Maximum number of nearest neighbors (default: 30)

**Example:**
```python
renderer = PointCloudRenderer("scan.ply")
renderer.estimate_normals()
renderer.render_multiple_views()  # Better shading with normals
```

---

## ColorScheme Enum

Enumeration of available color schemes.

| Value | Description |
|-------|-------------|
| `ColorScheme.UNIFORM` | Single uniform color (default: gray) |
| `ColorScheme.HEIGHT` | Color by Z-coordinate (height-based colormap) |
| `ColorScheme.INTENSITY` | Color by intensity values (if available) |
| `ColorScheme.NORMAL` | Color by normal vector direction |

**Example:**
```python
from render_pointcloud import PointCloudRenderer, ColorScheme

# Height-based coloring
renderer = PointCloudRenderer("terrain.ply", color_scheme=ColorScheme.HEIGHT)

# Normal-based coloring (shows surface orientation)
renderer = PointCloudRenderer("scan.ply", color_scheme=ColorScheme.NORMAL)
```

---

## Convenience Functions

### `render_pointcloud_to_images()`

Quick function to render a point cloud file to multiple views.

```python
render_pointcloud_to_images(
    pointcloud_file: Union[str, Path],
    output_dir: str = ".",
    width: int = 800,
    height: int = 600,
    point_size: float = 1.5,
    color_scheme: ColorScheme = ColorScheme.UNIFORM,
    auto_scale: bool = True
) -> List[Tuple[str, str]]
```

**Example:**
```python
from render_pointcloud import render_pointcloud_to_images

results = render_pointcloud_to_images(
    pointcloud_file="scan.ply",
    output_dir="./output",
    width=1200,
    height=900,
    point_size=2.0,
    color_scheme=ColorScheme.HEIGHT
)
```

---

## Command Line Interface

### Basic Usage

```bash
python scripts/render_pointcloud.py <pointcloud_file> [output_dir] [options]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `pointcloud_file` | Yes | Path to point cloud file |
| `output_dir` | No | Output directory (default: current directory) |

### Options

| Option | Description |
|--------|-------------|
| `--width <n>` | Image width (default: 800) |
| `--height <n>` | Image height (default: 600) |
| `--point-size <n>` | Point size (default: 1.5) |
| `--no-scale` | Disable auto-scaling |
| `--color <scheme>` | Color scheme: `uniform`, `height`, `normal` |

### Examples

```bash
# Basic usage
python scripts/render_pointcloud.py scan.ply

# With output directory
python scripts/render_pointcloud.py scan.ply ./output

# High resolution
python scripts/render_pointcloud.py scan.ply ./output --width 1920 --height 1080

# Height-based coloring
python scripts/render_pointcloud.py terrain.ply ./output --color height

# Custom point size
python scripts/render_pointcloud.py scan.ply ./output --point-size 3.0
```

---

## Examples

### Example 1: Basic Rendering

```python
from render_pointcloud import render_pointcloud_to_images

# Render with default settings
results = render_pointcloud_to_images("scan.ply", "./output")
for view_name, path in results:
    print(f"{view_name}: {path}")
```

### Example 2: Custom Settings

```python
from render_pointcloud import PointCloudRenderer, ColorScheme

# Create renderer with custom settings
renderer = PointCloudRenderer(
    pointcloud_file="scan.ply",
    output_dir="./output",
    image_width=1920,
    image_height=1080,
    point_size=2.5,
    color_scheme=ColorScheme.HEIGHT,
    bg_color=[1.0, 1.0, 1.0]  # White background
)

# Render specific view
renderer.render_view("front_detail", azimuth=0, elevation=0, zoom=2.0)

# Render all views
renderer.render_multiple_views()
```

### Example 3: Processing Large Point Clouds

```python
from render_pointcloud import PointCloudRenderer

# Load large point cloud
renderer = PointCloudRenderer("large_scan.ply")

# Downsample for faster rendering
renderer.downsample(voxel_size=0.05)

# Estimate normals for better visualization
renderer.estimate_normals(radius=0.1, max_nn=30)

# Render
results = renderer.render_multiple_views()
```

### Example 4: Batch Processing

```python
import glob
from render_pointcloud import render_pointcloud_to_images

# Process all PLY files in directory
for pc_file in glob.glob("*.ply"):
    print(f"Processing {pc_file}...")
    try:
        render_pointcloud_to_images(pc_file, "./output")
    except Exception as e:
        print(f"Failed: {e}")
```

### Example 5: Integration with SimpleCAD

```python
import simplecadapi as scad
from render_pointcloud import render_pointcloud_to_images

# 1. Visualize point cloud
pc_images = render_pointcloud_to_images("scan.ply", "./pc_preview")

# 2. Based on visualization, create CAD model
# (e.g., using primitive fitting or reconstruction)
model = reconstruct_from_pointcloud("scan.ply")

# 3. Export model
scad.export_step(model, "reconstructed.step")

# 4. Compare with visual-feedback skill
from render_step import render_step_to_images
cad_images = render_step_to_images("reconstructed.step", "./cad_preview")
```

---

## Error Handling

The API uses standard Python exceptions:

- `FileNotFoundError`: Point cloud file not found
- `ValueError`: Unsupported file format or invalid parameters
- `RuntimeError`: Rendering or loading failed
- `ImportError`: Missing required dependencies

**Example:**
```python
from render_pointcloud import PointCloudRenderer, ColorScheme

try:
    renderer = PointCloudRenderer("scan.ply")
    results = renderer.render_multiple_views()
except FileNotFoundError:
    print("File not found!")
except ValueError as e:
    print(f"Invalid input: {e}")
except RuntimeError as e:
    print(f"Rendering failed: {e}")
```
