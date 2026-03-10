# Usage Examples

## Example 1: Basic Rendering

Render multiple views of a single STEP file.

```python
from render_step import render_step_to_images

# Render STEP file
images = render_step_to_images("model.step", "./output")

# View results
for view_name, file_path in images:
    print(f"{view_name}: {file_path}")
```

**Output:**
```
front: ./output/model_front.png
top: ./output/model_top.png
right: ./output/model_right.png
isometric: ./output/model_isometric.png
perspective: ./output/model_perspective.png
```

---

## Example 2: Custom Views

Create custom view renderings.

```python
from render_step import StepRenderer

# Create renderer
renderer = StepRenderer("gear.step", "./images")

# Render specific custom views
views = {
    'top_front': {'azimuth': 45, 'elevation': 60, 'zoom': 1.0},
    'bottom_view': {'azimuth': 0, 'elevation': -30, 'zoom': 1.0},
    'close_up': {'azimuth': 30, 'elevation': 15, 'zoom': 2.0},
}

for view_name, params in views.items():
    result = renderer.render_view(view_name, **params)
    if result:
        print(f"Rendered: {result}")
```

---

## Example 3: High Resolution Rendering

Create high resolution images for presentation or printing.

```python
from render_step import StepRenderer

# Create high resolution renderer
renderer = StepRenderer(
    "model.step",
    output_dir="./high_res",
    image_width=3840,  # 4K
    image_height=2160
)

# Render all views
results = renderer.render_multiple_views()

print(f"Generated {len(results)} 4K images")
```

---

## Example 4: Integration with SimpleCAD

Complete CAD design-verification workflow.

```python
import simplecadapi as scad
from render_step import render_step_to_images

def design_and_verify():
    """Design gear and generate preview"""
    
    # 1. Design parameters
    num_teeth = 24
    module = 2.0
    
    # 2. Create gear
    print("Creating gear...")
    pitch_radius = (num_teeth * module) / 2
    gear = scad.make_cylinder_rsolid(pitch_radius + module, 8.0)
    
    # Add center hole
    bore = scad.make_cylinder_rsolid(6.0, 10.0)
    gear = scad.cut_rsolidlist(gear, bore)[0]
    
    # 3. Export STEP
    print("Exporting STEP file...")
    step_file = "gear_design.step"
    scad.export_step(gear, step_file)
    
    # 4. Render preview
    print("Generating preview images...")
    images = render_step_to_images(step_file, "./preview")
    
    # 5. Return results
    return {
        'step_file': step_file,
        'preview_images': images,
        'volume': gear.get_volume()
    }

# Execute
result = design_and_verify()
print(f"\nDesign complete!")
print(f"STEP file: {result['step_file']}")
print(f"Volume: {result['volume']:.2f} mm³")
print(f"Preview images: {len(result['preview_images'])} files")
```

---

## Example 5: Batch Processing

Batch render all STEP files in a directory.

```python
import os
import glob
from render_step import render_step_to_images
from pathlib import Path

def batch_render(input_dir, output_dir):
    """Batch render STEP files"""
    
    # Find all STEP files
    step_files = glob.glob(f"{input_dir}/*.step") + glob.glob(f"{input_dir}/*.STEP")
    
    print(f"Found {len(step_files)} STEP files")
    
    results = {}
    for i, step_file in enumerate(step_files, 1):
        print(f"\nProcessing [{i}/{len(step_files)}]: {step_file}")
        
        try:
            # Create separate output directory for each file
            model_name = Path(step_file).stem
            model_output = f"{output_dir}/{model_name}"
            
            # Render
            images = render_step_to_images(step_file, model_output)
            results[step_file] = images
            
            print(f"  Success: {len(images)} images")
            
        except Exception as e:
            print(f"  Failed: {e}")
            results[step_file] = None
    
    return results

# Use
results = batch_render("./models", "./output")

# Statistics
success = sum(1 for v in results.values() if v is not None)
print(f"\nProcessing complete: {success}/{len(results)} successful")
```

---

## Example 6: Automated Testing

Use rendering for automated geometry verification.

```python
import simplecadapi as scad
from render_step import render_step_to_images
import os

def test_gear_geometry():
    """Test if gear geometry is correct"""
    
    # Create test gear
    gear = scad.make_cylinder_rsolid(26.0, 8.0)
    bore = scad.make_cylinder_rsolid(6.0, 10.0)
    gear = scad.cut_rsolidlist(gear, bore)[0]
    
    # Export
    test_file = "test_gear.step"
    scad.export_step(gear, test_file)
    
    # Render validation
    images = render_step_to_images(test_file, "./test_output")
    
    # Verification
    assert len(images) == 5, "Should generate 5 views"
    assert all(os.path.exists(img) for _, img in images), "All images should exist"
    
    # Check file sizes (simple validation)
    for view_name, img_path in images:
        size = os.path.getsize(img_path)
        assert size > 1000, f"{view_name} image too small, rendering may have failed"
        print(f"  {view_name}: {size/1024:.1f} KB")
    
    print("✓ Geometry validation passed")
    return True

# Run test
test_gear_geometry()
```

---

## Example 7: Command Line Batch Rendering

Create a command line script for batch rendering.

```python
#!/usr/bin/env python
"""
batch_render.py - Batch render STEP files
"""

import sys
import glob
from render_step import render_step_to_images
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: python batch_render.py <input_dir> [output_dir]")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./rendered"
    
    # Find STEP files
    step_files = glob.glob(f"{input_dir}/*.step") + glob.glob(f"{input_dir}/*.STEP")
    
    if not step_files:
        print(f"Error: No STEP files found in {input_dir}")
        sys.exit(1)
    
    print(f"Found {len(step_files)} STEP files")
    
    # Batch render
    for i, step_file in enumerate(step_files, 1):
        print(f"\n[{i}/{len(step_files)}] {Path(step_file).name}")
        
        model_name = Path(step_file).stem
        model_output = f"{output_dir}/{model_name}"
        
        images = render_step_to_images(step_file, model_output)
        print(f"  Rendered: {len(images)} images")
    
    print("\nComplete!")

if __name__ == "__main__":
    main()
```

**Usage:**

```bash
# Render all STEP files
python batch_render.py ./models ./output

# Results
./output/
├── gear_1/
│   ├── gear_1_front.png
│   ├── gear_1_top.png
│   └── ...
├── gear_2/
│   └── ...
```

---

## Example 8: Quality Check Workflow

```python
from render_step import render_step_to_images
import simplecadapi as scad

def quality_check_model(model, model_name):
    """
    Quality check workflow:
    1. Export STEP
    2. Render preview
    3. Check geometry
    4. Generate report
    """
    
    report = {
        'name': model_name,
        'status': 'unknown',
        'images': [],
        'volume': None,
        'errors': []
    }
    
    try:
        # 1. Check volume
        volume = model.get_volume()
        report['volume'] = volume
        
        if volume <= 0:
            report['errors'].append("Volume is zero or negative")
            report['status'] = 'failed'
            return report
        
        # 2. Export STEP
        step_file = f"{model_name}.step"
        scad.export_step(model, step_file)
        
        # 3. Render preview
        images = render_step_to_images(step_file, f"./qc/{model_name}")
        report['images'] = images
        
        # 4. Check rendering results
        if len(images) < 5:
            report['errors'].append(f"Only rendered {len(images)} views")
            report['status'] = 'warning'
        else:
            report['status'] = 'passed'
        
    except Exception as e:
        report['errors'].append(str(e))
        report['status'] = 'failed'
    
    return report

# Use
model = scad.make_box_rsolid(10, 10, 10)
report = quality_check_model(model, "test_box")

print(f"Status: {report['status']}")
print(f"Volume: {report['volume']}")
print(f"Images: {len(report['images'])} files")
if report['errors']:
    print(f"Errors: {report['errors']}")
```
