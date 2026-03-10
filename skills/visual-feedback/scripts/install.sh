#!/bin/bash
# Visual Feedback Skill - Dependency Installation Script

echo "========================================"
echo "Visual Feedback Skill - Dependency Installation"
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
$PYTHON_BIN -m pip install cadquery>=2.5.2
$PYTHON_BIN -m pip install vtk>=9.0.0
$PYTHON_BIN -m pip install Pillow>=9.0.0

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"

# Verify installation
echo ""
echo "Verifying installation..."

$PYTHON_BIN -c "import cadquery; print(f'cadquery: {cadquery.__version__}')" || echo "cadquery: installation failed"
$PYTHON_BIN -c "import vtk; print(f'vtk: {vtk.vtkVersion.GetVTKVersion()}')" || echo "vtk: installation failed"
$PYTHON_BIN -c "import PIL; print(f'Pillow: {PIL.__version__}')" || echo "Pillow: installation failed"

echo ""
echo "All dependencies installed successfully!"
