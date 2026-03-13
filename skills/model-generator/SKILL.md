---
name: model-generator
description: |
  Automated CAD model generation workflow. Trigger when users want to create 3D models, meshes, geometries, or CAD objects.
  
  Trigger scenarios include:
  - User says "create a xxx model", "generate xxx", "make xxx for me" / 用户说"创建一个xxx模型"、"生成xxx"、"帮我做xxx"
  - User mentions 3D modeling, CAD design, geometry generation / 用户提到3D建模、CAD设计、几何体生成
  - User wants to create models in FreeCAD, SolidWorks, Blender, or other CAD software / 用户想在FreeCAD、SolidWorks、Blender等软件中创建模型
  - User provides point cloud files or images to convert to 3D models / 用户提供了点云文件或图片，想要转换为3D模型
  - Any request involving "modeling", "model", "CAD", "3D", "mesh", "geometry" / 任何涉及"建模"、"model"、"CAD"、"3D"的请求
  
  This skill automatically completes: SimpleCAD model generation → visual-feedback validation → (optional) CAD software conversion & export → result saving
---

# Model Generator Skill

Automated complete CAD model generation workflow, from user description to final model delivery.

## Workflow Overview

### Step 1: Parse User Intent

Extract the following information:
1. **Model Description** - What the user wants to create (text description, image path, or point cloud file path)
2. **Target Software** (optional) - Whether a specific CAD software is specified (FreeCAD, SolidWorks, Blender, etc.)
3. **Output Location** - Directory to save results (default: `sandbox/{model_name}`)

### Step 2: Process Input

**If input is a point cloud file** (.pcd, .ply, .xyz, etc.):
- First call `pointcloud-renderer` skill to render the point cloud to an image
- Use the rendered image as input for simplecad-self-evolve

**If input is an image file**:
- Directly use the image as reference input for simplecad-self-evolve

**If input is a text description**:
- Directly use the description to call simplecad-self-evolve

### Step 3: Generate SimpleCAD Model

Call `simplecad-self-evolve` skill:
- Pass model description/image
- Generate SimpleCAD API script
- Execute script to verify model can be created successfully

### Step 4: Visual Feedback Validation

Call `visual-feedback` skill:
- Perform visual validation on the generated model
- Ensure model meets user expectations
- If validation fails, return to Step 3 to regenerate

### Step 5: CAD Software Export (Optional)

If user specified a target CAD software and corresponding MCP is available:

1. **FreeCAD**:
   - Convert SimpleCAD API to FreeCAD Python API
   - Use `freecad_create_document` and `freecad_create_object` to create the model
   - Save as .FCStd file

2. **Other Software** (SolidWorks, Blender, etc.):
   - If corresponding MCP is available, execute similar workflow
   - If not available, notify user and preserve SimpleCAD results

### Step 6: Save Results

All files saved to `sandbox/{model_name}/`:
```
sandbox/{model_name}/
├── simplecad_script.py       # SimpleCAD API script
├── model.png                 # Model preview image
├── visual_feedback_report.md # Validation report
├── freecad/                  # If exported to FreeCAD
│   ├── model.FCStd
│   └── freecad_script.py
└── README.md                 # Project documentation
```

## Usage Examples

### Chinese Examples (用户通常输入中文)

**User Input**: "创建一个齿轮模型"
```
1. Parse: model=gear, no target software specified
2. Call simplecad-self-evolve to generate gear
3. visual-feedback validation
4. Save to sandbox/gear/
```

**User Input**: "在FreeCAD中创建一个杯子的3D模型"
```
1. Parse: model=cup, target software=FreeCAD
2. Call simplecad-self-evolve to generate cup
3. visual-feedback validation
4. Convert to FreeCAD API
5. Use freecad MCP to create model
6. Save to sandbox/cup/
```

**User Input**: "把这个点云转换成模型：data/pointcloud.ply"
```
1. Parse: input=point cloud file
2. Call pointcloud-renderer to render to image
3. Use image to call simplecad-self-evolve
4. Continue with validation and saving workflow
```

### English Examples

**User Input**: "Generate a 3D cube model"
```
1. Parse: model=cube, no target software specified
2. Call simplecad-self-evolve to generate cube
3. visual-feedback validation
4. Save to sandbox/cube/
```

**User Input**: "Create a spiral using Blender"
```
1. Parse: model=spiral, target software=Blender
2. Call simplecad-self-evolve to generate spiral
3. visual-feedback validation
4. Convert to Blender API
5. Use blender MCP to create model
6. Save to sandbox/spiral/
```

## Input Type Detection

The skill automatically detects input types:

- **Point Cloud Extensions**: .pcd, .ply, .xyz, .pts, .las, .laz
- **Image Extensions**: .png, .jpg, .jpeg, .gif, .bmp, .tiff, .webp
- **Text Description**: Anything else (no file path detected)

## Target Software Detection

The skill automatically detects target CAD software from user input (支持中英文):

- **freecad**: "freecad", "free cad", "fc" / "在freecad中", "用freecad"
- **solidworks**: "solidworks", "solid works", "sw" / "在solidworks中", "用solidworks"
- **blender**: "blender", "bl" / "在blender中", "用blender"
- **fusion360**: "fusion", "fusion360", "f360" / "在fusion中"
- **autocad**: "autocad", "auto cad" / "在autocad中"
- **openscad**: "openscad", "open scad" / "在openscad中"

## Important Notes

- **MUST** execute visual-feedback validation, cannot be skipped
- Automatically detect input type (text/image/point cloud)
- Automatically detect target CAD software
- Save all intermediate results for user traceability
- If conversion to specific CAD software fails, preserve SimpleCAD results and notify user
- Always create sandbox directory structure before starting
- Generate meaningful model names from descriptions for folder naming
