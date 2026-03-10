"""
STEP file rendering script
Renders STEP format CAD models into multi-view images
"""

import sys
import os
import math
from pathlib import Path

try:
    import cadquery as cq
    from cadquery import exporters
    import vtk
    from vtk.util.colors import white, black, light_grey
except ImportError as e:
    print("Error: Missing required libraries")
    print("Please run: pip install cadquery vtk")
    print(f"Details: {e}")
    sys.exit(1)


class StepRenderer:
    """STEP file renderer"""
    
    def __init__(self, step_file, output_dir=".", image_width=800, image_height=600):
        """
        Initialize renderer
        
        Parameters:
            step_file: STEP file path
            output_dir: Output directory
            image_width: Image width (pixels)
            image_height: Image height (pixels)
        """
        self.step_file = Path(step_file)
        self.output_dir = Path(output_dir)
        self.image_width = image_width
        self.image_height = image_height
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load STEP file
        self.shape = None
        self._load_step()
    
    def _load_step(self):
        """Load STEP file"""
        if not self.step_file.exists():
            raise FileNotFoundError(f"STEP file not found: {self.step_file}")
        
        print(f"Loading STEP file: {self.step_file}")
        
        try:
            # Import STEP file using cadquery
            self.shape = cq.importers.importStep(str(self.step_file))
            print("STEP file loaded successfully")
        except Exception as e:
            raise RuntimeError(f"Failed to load STEP file: {e}")
    
    def render_view(self, view_name, azimuth=45, elevation=30, zoom=1.0):
        """
        Render image for specified view
        
        Parameters:
            view_name: View name
            azimuth: Azimuth angle (degrees)
            elevation: Elevation angle (degrees)
            zoom: Zoom ratio
        
        Returns:
            Output file path
        """
        output_file = self.output_dir / f"{self.step_file.stem}_{view_name}.png"
        
        print(f"Rendering view: {view_name} (azimuth={azimuth}°, elevation={elevation}°)")
        
        try:
            # Use VTK for rendering
            renderer = vtk.vtkRenderer()
            render_window = vtk.vtkRenderWindow()
            render_window.SetOffScreenRendering(1)
            render_window.AddRenderer(renderer)
            render_window.SetSize(self.image_width, self.image_height)
            
            # Create converter from CAD model to VTK
            # Using simplified method: export to STL then render
            temp_stl = self.output_dir / f"{self.step_file.stem}_temp.stl"
            
            # Export to STL
            exporters.export(self.shape, str(temp_stl), exportType='STL')
            
            # Read STL file
            reader = vtk.vtkSTLReader()
            reader.SetFileName(str(temp_stl))
            reader.Update()
            
            # Create mapper
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(reader.GetOutputPort())
            
            # Create actor
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(0.7, 0.7, 0.7)  # Light gray
            actor.GetProperty().SetSpecular(0.5)
            actor.GetProperty().SetSpecularPower(20)
            
            # Add to renderer
            renderer.AddActor(actor)
            renderer.SetBackground(0.9, 0.9, 0.95)  # Light background
            
            # Set camera
            camera = renderer.GetActiveCamera()
            camera.Azimuth(azimuth)
            camera.Elevation(elevation)
            camera.Zoom(zoom)
            
            # Reset camera
            renderer.ResetCamera()
            
            # Render
            render_window.Render()
            
            # Save image
            window_to_image = vtk.vtkWindowToImageFilter()
            window_to_image.SetInput(render_window)
            window_to_image.Update()
            
            writer = vtk.vtkPNGWriter()
            writer.SetFileName(str(output_file))
            writer.SetInputConnection(window_to_image.GetOutputPort())
            writer.Write()
            
            # Clean up temp file
            if temp_stl.exists():
                temp_stl.unlink()
            
            print(f"  Saved image: {output_file}")
            return str(output_file)
            
        except Exception as e:
            print(f"  Rendering failed: {e}")
            return None
    
    def render_multiple_views(self):
        """
        Render images for multiple standard views
        
        Rendered views:
            - front: Front view
            - top: Top view
            - right: Right view
            - isometric: Isometric view
            - perspective: Perspective view
        """
        views = {
            'front': {'azimuth': 0, 'elevation': 0, 'zoom': 1.0},
            'top': {'azimuth': 0, 'elevation': 90, 'zoom': 1.0},
            'right': {'azimuth': 90, 'elevation': 0, 'zoom': 1.0},
            'isometric': {'azimuth': 45, 'elevation': 35, 'zoom': 1.0},
            'perspective': {'azimuth': 30, 'elevation': 20, 'zoom': 1.0},
        }
        
        print(f"\nRendering multiple views...")
        
        results = []
        for view_name, params in views.items():
            output = self.render_view(view_name, **params)
            if output:
                results.append((view_name, output))
        
        print(f"\nSuccessfully rendered {len(results)} views")
        return results


def render_step_to_images(step_file, output_dir=".", width=800, height=600):
    """
    Render STEP file to multi-view images
    
    Parameters:
        step_file: STEP file path
        output_dir: Output directory
        width: Image width
        height: Image height
    
    Returns:
        List of rendered image paths
    """
    renderer = StepRenderer(step_file, output_dir, width, height)
    return renderer.render_multiple_views()


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python render_step.py <step_file> [output_dir]")
        print("Example: python render_step.py model.step ./output")
        sys.exit(1)
    
    step_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    
    print("=" * 60)
    print("STEP File Visual Feedback")
    print("=" * 60)
    
    try:
        results = render_step_to_images(step_file, output_dir)
        
        print("\n" + "=" * 60)
        print("Rendering complete!")
        print("=" * 60)
        print("\nGenerated images:")
        for view_name, file_path in results:
            print(f"  - {view_name}: {file_path}")
        
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
