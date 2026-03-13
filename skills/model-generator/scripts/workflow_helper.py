#!/usr/bin/env python3
"""
Model Generator Workflow Helper Script
Handles input parsing, directory management, file type detection, etc.
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple


def detect_input_type(user_input: str) -> Tuple[str, Optional[str]]:
    """
    Detect the type of user input
    
    Returns:
        (input_type, extracted_path)
        input_type: 'text' | 'image' | 'pointcloud'
    """
    # Point cloud file extensions
    pointcloud_extensions = ['.pcd', '.ply', '.xyz', '.pts', '.las', '.laz']
    # Image file extensions
    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp']
    
    # Find file paths in input
    path_pattern = r'[\w\-./\]+\.[\w]+'
    matches = re.findall(path_pattern, user_input)
    
    for match in matches:
        ext = os.path.splitext(match.lower())[1]
        if ext in pointcloud_extensions:
            return 'pointcloud', match
        elif ext in image_extensions:
            return 'image', match
    
    return 'text', None


def detect_target_software(user_input: str) -> Optional[str]:
    """
    Detect if user specified a target CAD software (supports Chinese keywords)
    
    Returns:
        Software name or None
    """
    software_patterns = {
        'freecad': ['freecad', 'free cad', 'fc', '在freecad', '用freecad'],
        'solidworks': ['solidworks', 'solid works', 'sw', '在solidworks', '用solidworks'],
        'blender': ['blender', 'bl', '在blender', '用blender'],
        'fusion360': ['fusion', 'fusion360', 'f360', '在fusion'],
        'autocad': ['autocad', 'auto cad', '在autocad', '用autocad'],
        'openscad': ['openscad', 'open scad', '在openscad', '用openscad'],
    }
    
    user_lower = user_input.lower()
    
    for software, patterns in software_patterns.items():
        for pattern in patterns:
            if pattern in user_lower:
                return software
    
    return None


def extract_model_description(user_input: str) -> str:
    """
    Extract model description (remove file paths and software names)
    """
    # Remove file paths
    cleaned = re.sub(r'[\w\-./\\]+\.[\w]+', '', user_input)
    
    software_names = [
        'freecad', 'free cad', 'solidworks', 'solid works',
        'blender', 'fusion', 'fusion360', 'autocad', 'openscad',
        'in', 'using', 'with', 'create', 'make', 'generate', 'build',
        '在', '用', '使用', '中', '里', '一个', '模型', '的'
    ]
    
    for name in software_names:
        cleaned = cleaned.replace(name, '').replace(name.upper(), '').replace(name.lower(), '')
    
    # Clean up extra whitespace
    cleaned = ' '.join(cleaned.split())
    
    return cleaned.strip()


def generate_model_name(description: str) -> str:
    """
    Generate model name from description (for folder naming)
    """
    # Take first 3 keywords
    words = description.lower().split()
    keywords = [w for w in words if len(w) > 2][:3]
    
    if not keywords:
        return "unnamed_model"
    
    return '_'.join(keywords)


def create_sandbox_dir(model_name: str) -> Path:
    """
    Create sandbox directory structure
    """
    base_dir = Path('sandbox') / model_name
    
    # Create subdirectories
    (base_dir / 'freecad').mkdir(parents=True, exist_ok=True)
    (base_dir / 'blender').mkdir(parents=True, exist_ok=True)
    
    return base_dir


def main():
    """
    CLI entry point
    """
    if len(sys.argv) < 2:
        print("Usage: python workflow_helper.py <user_input>")
        sys.exit(1)
    
    user_input = ' '.join(sys.argv[1:])
    
    # Detect input type
    input_type, file_path = detect_input_type(user_input)
    print(f"INPUT_TYPE: {input_type}")
    if file_path:
        print(f"FILE_PATH: {file_path}")
    
    # Detect target software
    target_software = detect_target_software(user_input)
    if target_software:
        print(f"TARGET_SOFTWARE: {target_software}")
    
    # Extract description
    description = extract_model_description(user_input)
    print(f"DESCRIPTION: {description}")
    
    # Generate model name
    model_name = generate_model_name(description)
    print(f"MODEL_NAME: {model_name}")
    
    # Create directory
    sandbox_dir = create_sandbox_dir(model_name)
    print(f"SANDBOX_DIR: {sandbox_dir}")


if __name__ == '__main__':
    main()
