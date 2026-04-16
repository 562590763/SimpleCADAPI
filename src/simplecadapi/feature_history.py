"""
Feature history tracking system for SimpleCADAPI.

This module provides classes and functions to record, manage, and export
the feature history of CAD models, enabling parametric editing and
interoperability with other CAD systems.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union, Callable, Set
from collections import defaultdict


class FeatureType(Enum):
    """Enumeration of feature operation types."""
    PRIMITIVE = auto()      # 基础几何体（box, cylinder, sphere等）
    EXTRUDE = auto()        # 拉伸
    REVOLVE = auto()        # 旋转
    SWEEP = auto()          # 扫掠
    LOFT = auto()           # 放样
    FILLET = auto()         # 圆角
    CHAMFER = auto()        # 倒角
    SHELL = auto()          # 抽壳
    BOOLEAN_UNION = auto()  # 布尔并集
    BOOLEAN_CUT = auto()    # 布尔差集
    BOOLEAN_INTERSECT = auto()  # 布尔交集
    PATTERN = auto()        # 阵列
    TRANSFORM = auto()      # 变换（平移、旋转、镜像）
    FIELD = auto()          # 场函数
    CUSTOM = auto()         # 自定义
    SKETCH = auto()         # 草图/轮廓 (用于Wire/Face等2D几何体)


@dataclass
class Parameter:
    """
    Represents a parameter in a feature.
    
    Parameters can have values, expressions, and constraints,
    enabling parametric design capabilities.
    """
    name: str
    value: Any
    type: str = "float"  # float, int, bool, str, list, tuple
    expression: Optional[str] = None  # 参数表达式，如 "width * 2"
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "value": self.value,
            "type": self.type,
            "expression": self.expression,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "description": self.description,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Parameter:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            value=data["value"],
            type=data.get("type", "float"),
            expression=data.get("expression"),
            min_value=data.get("min_value"),
            max_value=data.get("max_value"),
            description=data.get("description", ""),
        )


@dataclass
class Feature:
    """
    Represents a single feature in the CAD model history.
    
    A feature captures the operation, parameters, inputs, and outputs
    that define a step in the modeling process.
    """
    name: str
    operation: str  # 操作名称，如 "extrude", "revolve", "fillet"
    feature_type: FeatureType = FeatureType.CUSTOM
    feature_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    inputs: List[Any] = field(default_factory=list)
    input_ids: List[str] = field(default_factory=list)
    
    # 参数
    parameters: Dict[str, Parameter] = field(default_factory=dict)
    
    # 输出
    output: Any = None  # 输出几何体
    output_id: str = ""  # 输出特征ID
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    description: str = ""
    
    # 依赖关系
    parent_features: List[str] = field(default_factory=list)  # 父特征ID
    child_features: List[str] = field(default_factory=list)  # 子特征ID
    
    def add_parameter(self, name: str, value: Any, **kwargs) -> Parameter:
        """Add a parameter to the feature."""
        param = Parameter(name=name, value=value, **kwargs)
        self.parameters[name] = param
        return param
    
    def get_parameter(self, name: str) -> Optional[Parameter]:
        """Get a parameter by name."""
        return self.parameters.get(name)
    
    def set_output(self, output: Any, output_id: Optional[str] = None):
        """Set the output geometry."""
        self.output = output
        if output_id:
            self.output_id = output_id
        elif not self.output_id:
            self.output_id = f"{self.feature_id}_out"
    
    def add_parent(self, parent_id: str):
        """Add a parent feature dependency."""
        if parent_id not in self.parent_features:
            self.parent_features.append(parent_id)
    
    def add_child(self, child_id: str):
        """Add a child feature dependency."""
        if child_id not in self.child_features:
            self.child_features.append(child_id)
    
    def _serialize_output(self) -> Optional[Dict[str, Any]]:
        """Serialize lightweight output geometry metadata when requested."""
        if self.output is None:
            return None

        output_data: Dict[str, Any] = {
            "type": type(self.output).__name__,
        }

        tags = getattr(self.output, "_tags", None)
        if tags:
            output_data["tags"] = sorted(tags)

        metadata = getattr(self.output, "_metadata", None)
        if metadata:
            output_data["metadata"] = metadata

        try:
            if hasattr(self.output, "get_volume"):
                output_data["volume"] = self.output.get_volume()
        except Exception:
            pass

        return output_data

    def to_dict(self, include_geometry: bool = False) -> Dict[str, Any]:
        """Convert feature to dictionary for serialization."""
        data = {
            "name": self.name,
            "operation": self.operation,
            "feature_type": self.feature_type.name,
            "feature_id": self.feature_id,
            "inputs": self._serialize_inputs(),
            "input_ids": self.input_ids,
            "parameters": {k: v.to_dict() for k, v in self.parameters.items()},
            "output_id": self.output_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "description": self.description,
            "parent_features": self.parent_features,
            "child_features": self.child_features,
        }

        if include_geometry:
            data["output"] = self._serialize_output()

        return data
    
    def _serialize_inputs(self) -> List[str]:
        """Serialize input references."""
        refs = []
        for inp in self.inputs:
            if hasattr(inp, '_feature_id'):
                refs.append(inp._feature_id)
            elif hasattr(inp, 'feature_id'):
                refs.append(inp.feature_id)
            else:
                refs.append(str(type(inp).__name__))
        return refs
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Feature:
        """Create feature from dictionary."""
        feature = cls(
            name=data["name"],
            operation=data["operation"],
            feature_type=FeatureType[data.get("feature_type", "CUSTOM")],
            feature_id=data.get("feature_id", str(uuid.uuid4())[:8]),
            input_ids=data.get("input_ids", []),
            output_id=data.get("output_id", ""),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", time.time()),
            description=data.get("description", ""),
            parent_features=data.get("parent_features", []),
            child_features=data.get("child_features", []),
        )
        
        # Restore parameters
        for name, param_data in data.get("parameters", {}).items():
            feature.parameters[name] = Parameter.from_dict(param_data)
        
        return feature


class FeatureHistory:
    """
    Manages the complete feature history of a CAD model.
    
    This class maintains the feature tree, handles dependencies,
    and provides serialization/deserialization capabilities.
    """
    
    def __init__(self, name: str = "Unnamed Model"):
        self.name = name
        self.features: Dict[str, Feature] = {}  # feature_id -> Feature
        self.ordered_features: List[str] = []   # 按创建顺序排列的特征ID
        self.root_features: List[str] = []     # 没有父特征的根特征
        self._current_feature_id: Optional[str] = None
        
        # 统计信息
        self.created_at = time.time()
        self.modified_at = time.time()
        self.version = "1.0"
        
    def add_feature(
        self,
        name: str,
        operation: str,
        feature_type: FeatureType = FeatureType.CUSTOM,
        inputs: Optional[List[Any]] = None,
        input_ids: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        output: Optional[Any] = None,
        description: str = "",
        parent_ids: Optional[List[str]] = None,
    ) -> Feature:
        """Add a new feature to the history."""
        # 创建特征
        feature = Feature(
            name=name,
            operation=operation,
            feature_type=feature_type,
            inputs=inputs or [],
            input_ids=input_ids or [],
            description=description,
        )
        
        # 添加参数
        if parameters:
            for name, value in parameters.items():
                if isinstance(value, Parameter):
                    feature.parameters[name] = value
                else:
                    feature.add_parameter(name, value)
        
        # 设置输出
        if output is not None:
            feature.set_output(output)
            # 在输出对象上保存特征ID引用
            if hasattr(output, '_feature_id'):
                output._feature_id = feature.feature_id
        
        # 建立依赖关系
        if parent_ids:
            for parent_id in parent_ids:
                feature.add_parent(parent_id)
                if parent_id in self.features:
                    self.features[parent_id].add_child(feature.feature_id)
        else:
            # 没有父特征，作为根特征
            self.root_features.append(feature.feature_id)
        
        # 保存特征
        self.features[feature.feature_id] = feature
        self.ordered_features.append(feature.feature_id)
        self._current_feature_id = feature.feature_id
        
        # 更新时间戳
        self.modified_at = time.time()
        
        return feature
    
    def add_feature_from_solid(self, solid, operation: str = "imported", name: str = "") -> Feature:
        """
        Add a feature from a solid object.
        
        This is useful when reconstructing feature history from a solid
        that doesn't have complete feature tracking.
        
        Args:
            solid: The solid object to add as a feature
            operation: The operation type (default: "imported")
            name: The feature name (default: auto-generated)
            
        Returns:
            The created Feature object
        """
        if not name:
            name = f"Imported_{len(self.features)}"
            
        # Create a basic feature
        feature = Feature(
            name=name,
            operation=operation,
            feature_type=FeatureType.PRIMITIVE,
            output=solid,
            description=f"Imported solid: {operation}",
        )
        
        # Set feature reference on solid if possible
        if hasattr(solid, 'set_feature'):
            solid.set_feature(feature)
        elif hasattr(solid, '_feature'):
            solid._feature = feature
            
        # Register as root feature (no parents for imported solids)
        self.root_features.append(feature.feature_id)
        self.features[feature.feature_id] = feature
        self.ordered_features.append(feature.feature_id)
        self._current_feature_id = feature.feature_id
        self.modified_at = time.time()
        
        return feature

    def get_feature(self, feature_id: str) -> Optional[Feature]:
        """Get a feature by its ID."""
        return self.features.get(feature_id)
    
    def get_current_feature(self) -> Optional[Feature]:
        """Get the most recently added feature."""
        if self._current_feature_id:
            return self.features.get(self._current_feature_id)
        return None
    
    def get_feature_tree(self) -> Dict[str, Any]:
        """Get the feature tree structure."""
        def build_tree(feature_id: str, visited: Set[str] = None) -> Dict[str, Any]:
            if visited is None:
                visited = set()
            
            if feature_id in visited:
                return {"feature_id": feature_id, "circular": True}
            
            visited.add(feature_id)
            feature = self.features.get(feature_id)
            
            if not feature:
                return {"feature_id": feature_id, "missing": True}
            
            return {
                "feature_id": feature_id,
                "name": feature.name,
                "operation": feature.operation,
                "type": feature.feature_type.name,
                "children": [
                    build_tree(child_id, visited.copy())
                    for child_id in feature.child_features
                ],
            }
        
        return {
            "root_features": [
                build_tree(root_id) for root_id in self.root_features
            ],
            "feature_count": len(self.features),
        }
    
    def to_dict(self, include_geometry: bool = False) -> Dict[str, Any]:
        """Convert the entire history to a dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "feature_count": len(self.features),
            "features": [
                self.features[feat_id].to_dict(include_geometry=include_geometry)
                for feat_id in self.ordered_features
            ],
            "feature_tree": self.get_feature_tree(),
        }

    def to_json(self, indent: int = 2, include_geometry: bool = False) -> str:
        """Serialize the history to JSON string."""
        return json.dumps(
            self.to_dict(include_geometry=include_geometry),
            indent=indent,
            default=str,
        )
    
    def save_to_file(self, filepath: str, indent: int = 2) -> None:
        """Save the history to a JSON file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json(indent=indent))
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FeatureHistory:
        """Create a FeatureHistory from a dictionary."""
        history = cls(name=data.get("name", "Unnamed Model"))
        history.version = data.get("version", "1.0")
        history.created_at = data.get("created_at", time.time())
        history.modified_at = data.get("modified_at", time.time())
        
        # Restore features
        for feat_data in data.get("features", []):
            feature = Feature.from_dict(feat_data)
            history.features[feature.feature_id] = feature
            history.ordered_features.append(feature.feature_id)
            
            # Track root features
            if not feature.parent_features:
                history.root_features.append(feature.feature_id)
        
        # Update current feature ID
        if history.ordered_features:
            history._current_feature_id = history.ordered_features[-1]
        
        return history
    
    @classmethod
    def from_json(cls, json_str: str) -> FeatureHistory:
        """Create a FeatureHistory from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> FeatureHistory:
        """Load a FeatureHistory from a JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            return cls.from_json(f.read())


# Global feature history registry for tracking across operations
_global_history: Optional[FeatureHistory] = None


def get_global_history() -> Optional[FeatureHistory]:
    """Get the global feature history instance."""
    return _global_history


def set_global_history(history: Optional[FeatureHistory]) -> None:
    """Set the global feature history instance."""
    global _global_history
    _global_history = history


def create_new_history(name: str = "New Model") -> FeatureHistory:
    """Create and set a new global feature history."""
    history = FeatureHistory(name=name)
    set_global_history(history)
    return history


def clear_global_history() -> None:
    """Clear the global feature history."""
    set_global_history(None)
