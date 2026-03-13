---
name: model-generator
description: Automated CAD model generation workflow using SimpleCAD as intermediate layer. Generates models via simplecad-self-evolve, validates with visual-feedback, optionally exports to target CAD software. All results saved to sandbox/{model_name}/.
---

# Model Generator Skill

**Architecture: SimpleCAD as Intermediate Layer**

```
User Input → SimpleCAD API (Intermediate) → Visual Validation → Target CAD Software (Optional)
                 ↓
            sandbox/{model_name}/
            ├── simplecad_script.py
            ├── model.step
            ├── visual_feedback/
            └── {target_software}/
```

## CRITICAL RULES - MUST FOLLOW

### Rule 1: ALWAYS Create Sandbox First
**BEFORE doing anything else**, create the sandbox directory structure:

```python
import os
from pathlib import Path

# Extract model name from user input
model_name = extract_model_name(user_input)  # e.g., "gear", "cup"
sandbox_dir = Path("sandbox") / model_name
sandbox_dir.mkdir(parents=True, exist_ok=True)

# Create subdirectories
(sandbox_dir / "visual_feedback").mkdir(exist_ok=True)
```

### Rule 2: SimpleCAD is the ONLY First Step
**NEVER** generate target CAD software code (FreeCAD, Blender, etc.) directly!

**CORRECT workflow:**
1. Generate SimpleCAD API code FIRST
2. Execute it to create model.step
3. Then optionally convert to target software

**WRONG workflow:**
❌ Directly generating FreeCAD Python code as the first step

### Rule 3: Mandatory Visual Feedback
**MUST** run visual-feedback after generating SimpleCAD model.
If validation fails, regenerate the SimpleCAD code.

## Step-by-Step Workflow

### Phase 1: Setup (MANDATORY)

```python
# 1. Parse user input
model_description = extract_description(user_input)
target_software = detect_target_software(user_input)  # Optional
input_type, file_path = detect_input_type(user_input)  # text/image/pointcloud

# 2. Create sandbox directory
model_name = generate_model_name(model_description)
sandbox_dir = Path("sandbox") / model_name
sandbox_dir.mkdir(parents=True, exist_ok=True)
(sandbox_dir / "visual_feedback").mkdir(exist_ok=True)
if target_software:
    (sandbox_dir / target_software).mkdir(exist_ok=True)
```

### Phase 2: Generate SimpleCAD Model (MANDATORY)

```python
# 1. Call simplecad-self-evolve skill
# Input: model_description or image
# Output: simplecad_script.py in sandbox_dir

# 2. Execute the SimpleCAD script
# This generates model.step in sandbox_dir

# 3. Save files:
# - sandbox/{model_name}/simplecad_script.py
# - sandbox/{model_name}/model.step
```

### Phase 3: Visual Validation (MANDATORY)

```python
# Call visual-feedback skill on model.step
# Save renderings to: sandbox/{model_name}/visual_feedback/
# Views: front.png, top.png, right.png, isometric.png, perspective.png

# If validation fails:
# - Report issues to user
# - Return to Phase 2 to regenerate
```

### Phase 4: Export to Target Software (OPTIONAL)

Only if user specified target software AND MCP is available:

```python
# Convert SimpleCAD API to target software API
# Example: FreeCAD

# 1. Read simplecad_script.py
# 2. Convert SimpleCAD calls to FreeCAD Python API
# 3. Save converted script: sandbox/{model_name}/freecad/freecad_script.py
# 4. Execute via FreeCAD MCP:
#    - freecad_create_document
#    - freecad_create_object (for each shape)
# 5. Save FreeCAD file: sandbox/{model_name}/freecad/model.FCStd
```

### Phase 5: Documentation

```python
# Generate README.md in sandbox_dir:
# - Model description
# - File structure
# - How to view results
```

## Directory Structure

```
sandbox/{model_name}/
├── simplecad_script.py          # REQUIRED: SimpleCAD API code
├── model.step                   # REQUIRED: Generated STEP file
├── README.md                    # Project documentation
├── visual_feedback/             # REQUIRED: Validation images
│   ├── front.png
│   ├── top.png
│   ├── right.png
│   ├── isometric.png
│   └── perspective.png
└── {target_software}/           # OPTIONAL: e.g., freecad/
    ├── {target_software}_script.py  # Converted API code
    └── model.{ext}                  # e.g., model.FCStd
```

## SimpleCAD API Reference

Common SimpleCAD operations (from simplecadapi):

```python
import simplecadapi as scad

# Basic shapes
cube = scad.make_box(l, w, h)
sphere = scad.make_sphere(radius)
cylinder = scad.make_cylinder(radius, height)

# Transformations
translated = scad.translate(shape, x, y, z)
rotated = scad.rotate(shape, x_angle, y_angle, z_angle)
scaled = scad.scale(shape, x_factor, y_factor, z_factor)

# Boolean operations
union = scad.union(shape1, shape2)
difference = scad.difference(shape1, shape2)
intersection = scad.intersection(shape1, shape2)

# Export
scad.export_step(shape, "model.step")
scad.export_stl(shape, "model.stl")
```

## Target Software Conversion Examples

### FreeCAD Conversion

SimpleCAD code:
```python
import simplecadapi as scad
cube = scad.make_box(10, 10, 10)
scad.export_step(cube, "model.step")
```

Converted to FreeCAD:
```python
import FreeCAD as App
import Part

doc = App.newDocument("Model")
cube = doc.addObject("Part::Box", "Box")
cube.Length = 10
cube.Width = 10
cube.Height = 10
doc.recompute()
doc.saveAs("model.FCStd")
```

### Blender Conversion

SimpleCAD code:
```python
import simplecadapi as scad
cube = scad.make_box(10, 10, 10)
```

Converted to Blender Python:
```python
import bpy
bpy.ops.mesh.primitive_cube_add(size=10, location=(0, 0, 0))
```

## Input Processing

### Text Description
Directly pass to simplecad-self-evolve.

### Image Reference
```
User: "Create a model like this: reference.png"
→ simplecad-self-evolve uses image as reference
→ Generate SimpleCAD code based on visual analysis
```

### Point Cloud
```
User: "Convert this point cloud: scan.ply"
1. pointcloud-renderer → scan_{view}.png
2. simplecad-self-evolve uses rendered images
3. Generate SimpleCAD code
```

## Error Handling

### If SimpleCAD generation fails:
- Report error to user
- Do NOT proceed to visual feedback
- Do NOT attempt target software conversion

### If visual feedback fails:
- Show validation images to user
- Ask if they want to regenerate
- If yes, return to Phase 2
- If no, proceed with current model

### If target software conversion fails:
- Preserve SimpleCAD results
- Notify user of conversion failure
- Suggest using SimpleCAD output directly

## Usage Examples

### Example 1: Simple Text Description
**User**: "创建一个齿轮模型"

**Process**:
1. Create `sandbox/gear/`
2. Call simplecad-self-evolve → `sandbox/gear/simplecad_script.py`
3. Execute → `sandbox/gear/model.step`
4. visual-feedback → `sandbox/gear/visual_feedback/*.png`
5. No target software specified → Done

### Example 2: With Target Software
**User**: "在FreeCAD中创建一个杯子"

**Process**:
1. Create `sandbox/cup/`, `sandbox/cup/freecad/`
2. Call simplecad-self-evolve → `sandbox/cup/simplecad_script.py`
3. Execute → `sandbox/cup/model.step`
4. visual-feedback → `sandbox/cup/visual_feedback/*.png`
5. Convert SimpleCAD → FreeCAD API
6. Execute via MCP → `sandbox/cup/freecad/model.FCStd`

### Example 3: From Point Cloud
**User**: "把这个点云转换成模型：data/scan.ply"

**Process**:
1. pointcloud-renderer → `data/scan_*.png`
2. Create `sandbox/scan_model/`
3. simplecad-self-evolve (using images) → `simplecad_script.py`
4. Execute → `model.step`
5. visual-feedback → validation images

## Anti-Patterns (NEVER DO)

❌ **Direct target software code generation**
```python
# WRONG: Directly writing this as first step
import FreeCAD as App  # ❌ Never do this first!
```

❌ **Skip sandbox creation**
```python
# WRONG: Writing files to current directory
with open("script.py", "w") as f:  # ❌ Always use sandbox!
```

❌ **Skip visual feedback**
```python
# WRONG: Not validating before exporting
generate_model() → export_to_freecad()  # ❌ Must validate first!
```

## Summary

1. **ALWAYS** create sandbox/{model_name}/ first
2. **ALWAYS** generate SimpleCAD code as intermediate layer
3. **ALWAYS** validate with visual-feedback
4. **OPTIONALLY** convert to target CAD software
5. **NEVER** skip steps 1-3
