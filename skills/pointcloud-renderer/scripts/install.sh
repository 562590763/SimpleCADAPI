#!/bin/bash
# PointCloud Renderer Skill - Dependency Installation Script

echo "========================================"
echo "PointCloud Renderer Skill - Dependency Installation"
echo "========================================"

# Detect Python interpreter
PYTHON_BIN="${PYTHON_BIN:-python}"

echo "Using Python interpreter: $PYTHON_BIN"

# Check Python version
PYTHON_VERSION=$($PYTHON_BIN --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Check pip
if ! command -v pip &> /dev/null; then
    echo "Error: pip not found"
    echo "Please install pip first: https://pip.pypa.io/en/stable/installation/"
    exit 1
fi

echo ""
echo "Installing dependencies..."

# Install core dependencies
$PYTHON_BIN -m pip install --upgrade pip
$PYTHON_BIN -m pip install open3d>=0.16.0
$PYTHON_BIN -m pip install numpy>=1.21.0
$PYTHON_BIN -m pip install Pillow>=9.0.0

# Install optional dependencies
echo ""
echo "Installing optional dependencies (for LAS/LAZ support)..."
$PYTHON_BIN -m pip install laspy>=2.3.0

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"

# Verify installation
echo ""
echo "Verifying installation..."

$PYTHON_BIN -c "import open3d; print(f'open3d: {open3d.__version__}')" || echo "open3d: installation failed"
$PYTHON_BIN -c "import numpy; print(f'numpy: {numpy.__version__}')" || echo "numpy: installation failed"
$PYTHON_BIN -c "import PIL; print(f'Pillow: {PIL.__version__}')" || echo "Pillow: installation failed"
$PYTHON_BIN -c "import laspy; print(f'laspy: {laspy.__version__}')" || echo "laspy: installation failed (optional)"

echo ""
echo "All core dependencies installed successfully!"
