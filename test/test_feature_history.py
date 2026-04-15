"""
测试 SimpleCADAPI 特征历史功能

用于验证特征历史记录的完整功能，包括：
- 特征创建和记录
- 特征树结构
- 导出功能（JSON、FreeCAD脚本）

运行方式:
    uv run python test/test_feature_history.py
"""

import os
import sys
import json
from pathlib import Path

# 确保 src 目录在路径中
# 获取测试文件所在目录，然后找到项目根目录
test_dir = Path(__file__).parent
project_root = test_dir.parent
src_dir = project_root / 'src'

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("=" * 70)
print("测试 SimpleCADAPI 特征历史功能")
print("=" * 70)

# =============================================================================
# 测试 1: 导入模块
# =============================================================================
print("\n【测试 1】模块导入...")
try:
    import simplecadapi as scad
    print("   ✓ simplecadapi 导入成功")
    
    from simplecadapi.feature_history import (
        create_new_history,
        get_global_history,
        FeatureHistory,
        FeatureType
    )
    print("   ✓ feature_history 模块导入成功")
    
    from simplecadapi.feature_export import (
        export_feature_history_to_json,
        print_feature_report,
        FeatureExporter
    )
    print("   ✓ feature_export 模块导入成功")
    
except ImportError as e:
    print(f"   ✗ 导入失败: {e}")
    sys.exit(1)

# =============================================================================
# 测试 2: 创建特征历史
# =============================================================================
print("\n【测试 2】特征历史创建...")
try:
    history = create_new_history("测试模型")
    print(f"   ✓ 特征历史创建成功: {history.name}")
    print(f"   - 初始特征数量: {len(history.features)}")
except Exception as e:
    print(f"   ✗ 创建失败: {e}")
    sys.exit(1)

# =============================================================================
# 测试 3: 基础几何体创建与特征记录
# =============================================================================
print("\n【测试 3】基础几何体创建...")
try:
    # 创建立方体
    box = scad.make_box_rsolid(width=10, height=20, depth=30)
    print(f"   ✓ 立方体创建成功 (体积: {box.get_volume():.2f})")
    
    # 检查特征是否被记录
    current_history = get_global_history()
    if current_history and len(current_history.features) > 0:
        print(f"   ✓ 特征已自动记录 (共 {len(current_history.features)} 个)")
    else:
        print("   ! 警告: 特征记录可能未启用")
    
    # 创建圆柱
    cylinder = scad.make_cylinder_rsolid(radius=5, height=15)
    print(f"   ✓ 圆柱创建成功 (体积: {cylinder.get_volume():.2f})")
    
except Exception as e:
    print(f"   ✗ 创建失败: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# 测试 4: 拉伸操作与特征关联
# =============================================================================
print("\n【测试 4】拉伸操作...")
try:
    # 创建轮廓
    profile = scad.make_rectangle_rwire(width=50, height=30)
    print(f"   ✓ 矩形轮廓创建成功")
    
    # 拉伸
    extruded = scad.extrude_rsolid(profile, direction=(0, 0, 1), distance=20)
    print(f"   ✓ 拉伸成功 (体积: {extruded.get_volume():.2f})")
    
    # 检查特征
    feature = extruded.get_feature()
    if feature:
        print(f"   ✓ 特征关联成功: {feature.name}")
        print(f"   - 操作: {feature.operation}")
        print(f"   - 类型: {feature.feature_type.name}")
        print(f"   - input_ids: {feature.input_ids}")
        print(f"   - parent_features: {feature.parent_features}")
    else:
        print("   ! 警告: 特征未关联")
    
except Exception as e:
    print(f"   ✗ 操作失败: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# 测试 5: FreeCAD 脚本生成与 Base object not found 问题修复验证
# =============================================================================
print("\n【测试 5】FreeCAD 脚本生成与 Base object not found 修复验证...")
try:
    from pathlib import Path
    
    # 创建导出器
    history = get_global_history()
    if not history:
        print("   ✗ 错误: 历史记录为空")
        sys.exit(1)
    
    exporter = FeatureExporter(history)
    
    # 生成 FreeCAD 脚本
    script = exporter._generate_freecad_script()
    print(f"   ✓ 脚本生成成功 ({len(script.split(chr(10)))} 行)")
    
    # 检查关键导入
    if "import FreeCADGui as Gui" in script:
        print("   ✓ Gui 导入已包含")
    else:
        print("   ! 警告: Gui 导入缺失")
    
    # 检查 Base object not found 问题修复
    warnings = [line for line in script.split('\n') if 'Base object not found' in line]
    print(f"   - 'Base object not found' 警告数量: {len(warnings)}")
    
    if len(warnings) == 0:
        print("   ✓ Base object not found 问题已修复!")
    else:
        print(f"   ✗ 仍有 {len(warnings)} 个 Base object not found 警告")
        print("\n   警告详情 (前3个):")
        for i, w in enumerate(warnings[:3], 1):
            print(f"      {i}. {w.strip()}")
    
    # 保存脚本用于检查
    output_dir = Path("./sandbox/output")
    output_dir.mkdir(exist_ok=True)
    script_path = output_dir / "test_feature_history.fcstd.py"
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script)
    print(f"\n   ✓ 脚本已保存到: {script_path}")
    
except Exception as e:
    print(f"   ✗ 生成失败: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# 测试 6: JSON 导出功能
# =============================================================================
print("\n【测试 6】JSON 导出功能...")
try:
    from pathlib import Path
    
    # 创建输出目录
    output_dir = Path("./sandbox/output")
    output_dir.mkdir(exist_ok=True)
    
    # 导出特征历史到 JSON
    history = get_global_history()
    if history:
        json_path = output_dir / "feature_history.json"
        export_feature_history_to_json(history, str(json_path))
        print(f"   ✓ 特征历史导出成功: {json_path}")
        
        # 验证 JSON 内容
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"   - 模型名称: {data.get('name')}")
        print(f"   - 特征数量: {data.get('feature_count')}")
        print(f"   - 根特征数: {len(data.get('feature_tree', {}).get('root_features', []))}")
        
        # 打印报告
        print("\n" + "=" * 60)
        print("特征历史报告:")
        print("=" * 60)
        print_feature_report(history)
    else:
        print("   ! 警告: 没有特征历史可导出")
    
except Exception as e:
    print(f"   ✗ 导出失败: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# 测试 7: 布尔运算与复杂特征树
# =============================================================================
print("\n【测试 7】布尔运算与复杂特征树...")
try:
    # 创建立方体和圆柱
    box = scad.make_box_rsolid(50, 50, 10)
    cyl = scad.make_cylinder_rsolid(15, 20)
    cyl = scad.translate_shape(cyl, (25, 25, -5))
    
    # 布尔减运算
    result_list = scad.cut_rsolidlist(box, cyl)
    result = result_list[0] if result_list else None
    
    if result:
        print(f"   ✓ 布尔减运算成功")
        
        # 检查布尔特征
        if hasattr(result, '_feature') and result._feature:
            feat = result._feature
            print(f"   - 布尔特征名称: {feat.name}")
            print(f"   - 操作类型: {feat.operation}")
            print(f"   - parent_features: {feat.parent_features}")
            print(f"   - input_ids: {feat.input_ids}")
    else:
        print("   ! 警告: 布尔运算结果为空")
    
    # 重新生成脚本并检查布尔运算
    history = get_global_history()
    if history:
        exporter = FeatureExporter(history)
        script = exporter._generate_freecad_script()
        
        # 检查是否有布尔运算相关的代码
        if "Part::Cut" in script or "Part::Fuse" in script or "Part::Common" in script:
            print("   ✓ 布尔运算已正确生成到脚本中")
        else:
            print("   ! 警告: 脚本中未找到布尔运算代码")
    
except Exception as e:
    print(f"   ✗ 布尔运算测试失败: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# 测试 8: 特征历史遍历
# =============================================================================
print("\n【测试 8】特征历史遍历...")
try:
    # 创建新的拉伸体
    extruded_solid = scad.extrude_rsolid(
        scad.make_rectangle_rwire(30, 20), 
        (0, 0, 1), 
        10
    )
    
    # 获取特征历史链
    history_chain = extruded_solid.get_feature_history()
    if history_chain:
        print(f"   ✓ 找到 {len(history_chain)} 个特征:")
        for i, feat in enumerate(history_chain, 1):
            print(f"     {i}. {feat.name} ({feat.feature_type.name})")
    else:
        print("   ! 警告: 未找到特征历史")
    
except Exception as e:
    print(f"   ✗ 遍历失败: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# 测试 9: 验证修复的问题
# =============================================================================
print("\n【测试 9】验证修复的问题...")
try:
    history = get_global_history()
    if history:
        exporter = FeatureExporter(history)
        script = exporter._generate_freecad_script()
        
        issues_found = []
        
        # 检查 1: Gui 导入
        if "import FreeCADGui as Gui" not in script:
            issues_found.append("缺少 FreeCADGui 导入")
        
        # 检查 2: Base object not found 警告
        base_not_found_count = script.count("Base object not found")
        if base_not_found_count > 0:
            issues_found.append(f"存在 {base_not_found_count} 个 'Base object not found' 警告")
        
        # 检查 3: 脚本完整性
        if "doc.recompute()" not in script:
            issues_found.append("缺少 doc.recompute()")
        
        if "doc.newDocument()" not in script and "App.newDocument()" not in script:
            issues_found.append("缺少 newDocument 调用")
        
        # 报告结果
        if issues_found:
            print(f"   ✗ 发现 {len(issues_found)} 个问题:")
            for i, issue in enumerate(issues_found, 1):
                print(f"      {i}. {issue}")
        else:
            print("   ✓ 所有检查通过! 问题已修复:")
            print("     - Gui 导入已添加")
            print("     - Base object not found 问题已解决")
            print("     - 脚本结构完整")
        
        # 显示脚本统计
        lines = script.split('\n')
        print(f"\n   脚本统计:")
        print(f"   - 总行数: {len(lines)}")
        print(f"   - 特征数量: {len(history.features)}")
    
except Exception as e:
    print(f"   ✗ 验证失败: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# 测试完成
# =============================================================================
print("\n" + "=" * 70)
print("测试完成!")
print("=" * 70)

# 最终统计
history = get_global_history()
if history:
    print(f"\n最终统计:")
    print(f"  - 模型名称: {history.name}")
    print(f"  - 总特征数: {len(history.features)}")
    print(f"  - 根特征数: {len(history.root_features)}")
    print(f"  - 有序特征数: {len(history.ordered_features)}")

print("\n" + "=" * 70)
print("所有测试已执行完成。请检查上方输出以确认功能正常。")
print("=" * 70)
