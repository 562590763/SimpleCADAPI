# SimpleCADAPI 特征历史功能实现

## 概述

本实现为 SimpleCADAPI 添加了完整的特征历史（Feature History）追踪系统，允许用户：

1. **记录建模操作** - 自动追踪所有几何创建和修改操作
2. **查看特征树** - 以树形结构查看模型的构建历史
3. **导出历史数据** - 将特征历史导出为 JSON 格式
4. **生成 CAD 脚本** - 自动生成可重现模型的 CAD 脚本

## 核心组件

### 1. `feature_history.py`

特征历史系统的核心模块，包含：

- **`FeatureType` 枚举** - 定义所有支持的特征类型：
  - `PRIMITIVE` - 基础几何体（box, cylinder, sphere等）
  - `EXTRUDE` - 拉伸操作
  - `REVOLVE` - 旋转操作
  - `SWEEP`, `LOFT`, `FILLET`, `CHAMFER` 等

- **`Parameter` 类** - 表示特征的参数，支持：
  - 值存储
  - 表达式（如 `width * 2`）
  - 约束（min/max）

- **`Feature` 类** - 表示单个特征，包含：
  - 名称、操作类型、ID
  - 输入几何体引用
  - 参数集合
  - 输出几何体
  - 父子依赖关系

- **`FeatureHistory` 类** - 管理完整的特征历史：
  - 添加和管理特征
  - 维护特征依赖图
  - 支持序列化/反序列化
  - 生成特征树视图

### 2. `feature_export.py`

导出功能模块，包含：

- **`FeatureExporter` 类** - 导出特征树到多种格式：
  - `to_json()` - 导出为 JSON
  - `export_solid_with_history()` - 导出实体及历史
  - `generate_cad_script()` - 生成 CAD 脚本（支持 FreeCAD、SolidWorks、OpenCASCADE）

### 3. `core.py` 扩展

扩展 `Solid` 类以支持特征历史：

- **`set_feature()`** - 关联 Solid 与创建它的 Feature
- **`get_feature()`** - 获取创建该 Solid 的 Feature
- **`get_feature_id()`** - 获取 Feature ID
- **`get_feature_history()`** - 获取完整的历史链

### 4. `operations.py` 扩展

修改操作函数以自动记录特征：

- **`make_box_rsolid()`** - 记录 box 创建
- **`make_cylinder_rsolid()`** - 记录 cylinder 创建
- **`extrude_rsolid()`** - 记录拉伸操作（通过 `_record_extrude_feature()`）
- **`revolve_rsolid()`** - 记录旋转操作（通过 `_record_revolve_feature()`）

## 使用示例

### 基本使用

```python
import simplecadapi as scad
from simplecadapi.feature_history import create_new_history

# 创建新的历史记录
history = create_new_history("My Model")

# 创建几何体（自动记录特征）
box = scad.make_box_rsolid(100.0, 50.0, 30.0)
cylinder = scad.make_cylinder_rsolid(20.0, 60.0)

# 检查特征
feature = box.get_feature()
print(f"Feature: {feature.name}")
print(f"Type: {feature.feature_type.name}")
print(f"Parameters: {feature.parameters}")
```

### 查看特征历史

```python
# 获取完整的历史链
history_chain = box.get_feature_history()
for i, feat in enumerate(history_chain):
    print(f"[{i}] {feat.name} ({feat.operation})")
```

### 导出特征历史

```python
from simplecadapi.feature_export import FeatureExporter

# 创建导出器
exporter = FeatureExporter(history)

# 导出为 JSON
json_output = exporter.to_json("model_history.json")

# 导出实体及历史
result = exporter.export_solid_with_history(
    solid=box,
    filepath="model_export",
    include_step=True
)

# 生成 CAD 脚本
freecad_script = exporter.generate_cad_script("freecad", "freecad_script.py")
solidworks_macro = exporter.generate_cad_script("solidworks", "solidworks_macro.swp")
```

### 导入特征历史

```python
from simplecadapi.feature_history import FeatureHistory

# 从 JSON 文件加载
history = FeatureHistory.load_from_file("model_history.json")

# 或从 JSON 字符串加载
import json
with open("model_history.json") as f:
    history = FeatureHistory.from_json(f.read())
```

## 文件结构

```
src/simplecadapi/
├── __init__.py           # 更新导出
├── core.py               # 扩展 Solid 类
├── operations.py         # 添加特征记录
├── feature_history.py    # 核心特征历史模块
└── feature_export.py     # 导出功能模块

examples/
└── examples_feature_history.py  # 演示脚本

test/
├── test_feature_history.py      # 合并后的完整测试脚本
└── (已删除: test_feature_history_editable.py, test_feature_tree_fix.py)
```

## 依赖

- Python 3.8+
- simplecadapi (核心包)
- cadquery (用于几何操作)
- numpy (用于数学运算)

## 注意事项

1. **向后兼容**: 新功能是可选的，现有代码无需修改即可继续工作
2. **性能**: 特征历史记录会带来少量性能开销，但通常可忽略
3. **内存**: 大型模型的特征历史可能占用较多内存，建议定期保存并清理
4. **线程安全**: FeatureHistory 不是线程安全的，多线程环境需要外部同步

## 未来扩展

- [ ] 支持更多 CAD 格式导出（CATIA, NX, Inventor）
- [ ] 特征编辑功能（修改参数并重建）
- [ ] 版本控制和分支管理
- [ ] 协作功能（合并不同用户的特征历史）
- [ ] 可视化特征树浏览器

## 运行测试

合并后的测试文件 `test_feature_history.py` 包含完整的特征历史功能验证：

```bash
# 运行所有测试
uv run python test/test_feature_history.py
```

测试内容包括：
- 模块导入和初始化
- 特征历史创建和管理
- 基础几何体创建与特征自动记录
- 拉伸操作与特征关联
- **FreeCAD 脚本生成（修复版）**
- **Base object not found 问题修复验证**
- JSON 导出功能
- 布尔运算与复杂特征树
- 特征历史遍历

## 已知问题修复

### 2026-04-15 修复内容

1. **FreeCAD 脚本缺少 Gui 导入**
   - 问题：生成的脚本使用 `Gui` 但未导入 `FreeCADGui`
   - 修复：在 `_generate_freecad_script()` 中添加导入

2. **Base object not found 问题**
   - 问题：某些操作的基对象引用无法正确解析
   - 修复：改进 `_get_input_object_name()` 和 `_get_parent_object_names()` 方法

3. **测试文件合并**
   - 将 `test_feature_history_editable.py` 和 `test_feature_tree_fix.py` 合并为 `test_feature_history.py`

## 许可证

与 SimpleCADAPI 主项目相同（MIT License）

---

**作者**: SimpleCADAPI Team  
**版本**: 1.0.1  
**日期**: 2026-04-15