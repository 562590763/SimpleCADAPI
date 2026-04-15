"""
Feature History System for SimpleCADAPI - Implementation Summary

This implementation adds feature history tracking to SimpleCADAPI, allowing
CAD models to retain their construction history for parametric editing and
export to other CAD systems.

## Files Created/Modified:

### 1. src/simplecadapi/feature_history.py (NEW)
Core feature history tracking system with:
- FeatureType enum: EXTRUDE, REVOLVE, PRIMITIVE, etc.
- Parameter class: Stores parametric values with expressions
- Feature class: Represents a single modeling operation
- FeatureHistory class: Manages complete model history
- Global history registry for tracking across operations

### 2. src/simplecadapi/feature_export.py (NEW)
Export utilities for feature history:
- export_feature_history_to_json(): Export to JSON format
- export_solid_with_history(): Export geometry + history
- generate_feature_report(): Human-readable report
- FeatureExporter class: Unified export interface

### 3. src/simplecadapi/core.py (MODIFIED)
Extended Solid class with feature history support:
- _feature: Reference to creating Feature
- _feature_id: Feature identifier
- set_feature(): Associate with feature
- get_feature_history(): Get complete history chain
- add_parent_feature()/add_child_feature(): Dependency tracking

### 4. src/simplecadapi/operations.py (MODIFIED)
Modified key functions to record feature history:
- extrude_rsolid(): Records EXTRUDE feature
- revolve_rsolid(): Records REVOLVE feature
- make_box_rsolid(): Records PRIMITIVE feature
- _record_extrude_feature(): Helper for extrusion recording
- _record_revolve_feature(): Helper for revolution recording
- _record_primitive_feature(): Helper for primitive recording

## Usage Example:

```python
import simplecadapi as scad
from simplecadapi.feature_history import create_new_history
from simplecadapi.feature_export import export_solid_with_history

# Create new history (auto-creates if not set)
create_new_history("My Model")

# Create geometry - features auto-recorded
box = scad.make_box_rsolid(10, 20, 30)
cylinder = scad.make_cylinder_rsolid(5, 15)

# Extrude operation - recorded as feature
profile = scad.make_rectangle_rwire(50, 30)
extruded = scad.extrude_rsolid(profile, (0, 0, 1), 20)

# Export with history
export_solid_with_history(extruded, "model.step", "features.json")
```

## Feature History JSON Format:

```json
{
  "name": "My Model",
  "version": "1.0",
  "feature_count": 3,
  "features": [
    {
      "name": "Box_Primitive",
      "operation": "make_box",
      "feature_type": "PRIMITIVE",
      "feature_id": "a1b2c3d4",
      "parameters": {
        "width": {"name": "width", "value": 10.0, "type": "float"},
        "height": {"name": "height", "value": 20.0, "type": "float"},
        "depth": {"name": "depth", "value": 30.0, "type": "float"}
      },
      "description": "Created box primitive"
    },
    {
      "name": "Extrude_Profile",
      "operation": "extrude",
      "feature_type": "EXTRUDE",
      "feature_id": "e5f6g7h8",
      "input_ids": ["profile_id"],
      "parameters": {
        "direction": {"value": [0, 0, 1]},
        "distance": {"value": 20.0}
      },
      "description": "Extruded profile by 20 units"
    }
  ],
  "feature_tree": {
    "root_features": [...],
    "feature_count": 3
  }
}
```

## Benefits:

1. **Parametric Editing**: Modify parameters to rebuild geometry
2. **CAD Interoperability**: Export history to SolidWorks, CATIA, etc.
3. **Design Intent**: Capture why geometry was created, not just what
4. **Version Control**: Track design evolution through feature history
5. **Automation**: Script parametric variations using history

## Future Enhancements:

- SolidWorks/VBA macro generation
- CATIA V5 script export
- Feature editing and regeneration
- Dependency graph visualization
- Real-time parametric updates

## 修复记录

### 2026-04-15 修复

#### 修复 1: FreeCAD 脚本缺少 Gui 导入
**问题**: 生成的 FreeCAD 脚本使用了 `Gui` 对象（如 `Gui.activeDocument()`），但没有导入 `FreeCADGui` 模块。

**修复**: 在 `_generate_freecad_script()` 方法中添加了对 `FreeCADGui` 的导入：
```python
try:
    import FreeCADGui as Gui
except ImportError:
    Gui = None  # No GUI available
```

#### 修复 2: Base object not found 问题
**问题**: 在生成 FreeCAD 脚本时，某些操作的基对象引用无法正确解析，导致生成 "Base object not found" 的警告。

**修复**: 改进了 `_get_input_object_name()` 和 `_get_parent_object_names()` 方法，添加了更完善的输入对象查找逻辑：
- 首先尝试从 `input_ids` 查找
- 然后尝试从 `parent_features` 查找
- 添加了更好的回退处理

#### 修复 3: 测试文件合并
**问题**: `test_feature_history_editable.py` 和 `test_feature_tree_fix.py` 两个测试文件有重叠功能。

**修复**: 将两个文件合并为统一的 `test_feature_history.py`，包含：
- 模块导入测试
- 特征历史创建测试
- 基础几何体创建与特征记录
- 拉伸操作与特征关联
- FreeCAD 脚本生成与验证
- JSON 导出功能
- 布尔运算与复杂特征树
- 特征历史遍历
- 修复问题验证

**运行方式**:
```bash
uv run python test/test_feature_history.py
```
