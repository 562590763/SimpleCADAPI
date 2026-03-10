# API Documentation

## StepRenderer Class

### Initialization

```python
StepRenderer(step_file, output_dir=".", image_width=800, image_height=600)
```

**Parameters:**
- `step_file` (str/Path): STEP file path
- `output_dir` (str/Path, optional): Output directory, defaults to current directory
- `image_width` (int, optional): Image width (pixels), default 800
- `image_height` (int, optional): Image height (pixels), default 600

**Example:**

```python
from render_step import StepRenderer

# Basic usage
renderer = StepRenderer("model.step")

# Custom parameters
renderer = StepRenderer(
    step_file="model.step",
    output_dir="./images",
    image_width=1920,
    image_height=1080
)
```

---

### render_view()

Renders an image for the specified view.

```python
render_view(view_name, azimuth=45, elevation=30, zoom=1.0)
```

**Parameters:**
- `view_name` (str): View name, used for generating filename
- `azimuth` (float): Azimuth angle (degrees), 0-360
- `elevation` (float): Elevation angle (degrees), -90 to 90
- `zoom` (float): Zoom ratio, default 1.0

**Returns:**
- str: Output file path, returns None on failure

**Example:**

```python
# Render isometric view
output = renderer.render_view(
    view_name="isometric",
    azimuth=45,
    elevation=35,
    zoom=1.0
)

# Render custom view
output = renderer.render_view(
    view_name="custom_view",
    azimuth=60,
    elevation=25,
    zoom=1.2
)
```

---

### render_multiple_views()

Renders images for multiple standard views.

```python
render_multiple_views()
```

**Returns:**
- List[Tuple[str, str]]: List of (view_name, file_path) tuples

**Standard Views:**

| View | Azimuth | Elevation | Description |
|------|---------|-----------|-------------|
| front | 0° | 0° | Front view |
| top | 0° | 90° | Top view |
| right | 90° | 0° | Right view |
| isometric | 45° | 35° | Isometric view |
| perspective | 30° | 20° | Perspective view |

**Example:**

```python
results = renderer.render_multiple_views()

for view_name, file_path in results:
    print(f"{view_name}: {file_path}")
```

---

## Helper Functions

### render_step_to_images()

Convenience function to render STEP file to multi-view images.

```python
render_step_to_images(step_file, output_dir=".", width=800, height=600)
```

**Parameters:**
- `step_file` (str/Path): STEP file path
- `output_dir` (str/Path, optional): Output directory
- `width` (int, optional): Image width
- `height` (int, optional): Image height

**Returns:**
- List[Tuple[str, str]]: List of rendering results

**Example:**

```python
from render_step import render_step_to_images

# Quick render
images = render_step_to_images("model.step", "./output")

# High resolution render
images = render_step_to_images(
    "model.step",
    "./output",
    width=1920,
    height=1080
)
```

---

## Exception Handling

### FileNotFoundError

Raised when STEP file does not exist.

```python
try:
    renderer = StepRenderer("nonexistent.step")
except FileNotFoundError as e:
    print(f"File not found: {e}")
```

### RuntimeError

Raised when loading or rendering STEP file fails.

```python
try:
    results = renderer.render_multiple_views()
except RuntimeError as e:
    print(f"Rendering failed: {e}")
```

---

## Advanced Usage

### Batch Rendering Multiple Files

```python
import glob
from render_step import render_step_to_images

# Get all STEP files
step_files = glob.glob("models/*.step")

# Batch render
for step_file in step_files:
    print(f"Rendering: {step_file}")
    images = render_step_to_images(step_file, "./output")
```

### Custom Rendering Workflow

```python
from render_step import StepRenderer

# Create renderer
renderer = StepRenderer("model.step", "./output")

# Modify resolution
renderer.image_width = 2560
renderer.image_height = 1440

# Render specific view combinations
custom_views = {
    'front_low': {'azimuth': 0, 'elevation': -15, 'zoom': 1.0},
    'back_high': {'azimuth': 180, 'elevation': 45, 'zoom': 1.0},
    'detail': {'azimuth': 75, 'elevation': 30, 'zoom': 2.0},
}

for view_name, params in custom_views.items():
    renderer.render_view(view_name, **params)
```

### Integration into Workflow

```python
import simplecadapi as scad
from render_step import render_step_to_images

def create_and_verify_model():
    # 1. Create model
    model = scad.make_cylinder_rsolid(10.0, 5.0)
    
    # 2. Export STEP
    scad.export_step(model, "model.step")
    
    # 3. Render validation
    images = render_step_to_images("model.step", "./preview")
    
    # 4. Return image paths for viewing
    return images

# Use
images = create_and_verify_model()
print("Generated preview images:", images)
```
