"""
PointCloud rendering script
Renders point cloud files (PLY, PCD, XYZ, PTS, LAS/LAZ) into multi-view images
"""

import sys
import os
import math
from pathlib import Path
from enum import Enum
from typing import List, Tuple, Optional, Union
import numpy as np

try:
    import open3d as o3d
    import open3d.visualization.rendering as rendering
except ImportError as e:
    print("Error: Missing required library 'open3d'")
    print("Please run: pip install open3d")
    print(f"Details: {e}")
    sys.exit(1)


class ColorScheme(Enum):
    """Color scheme options for point cloud visualization"""
    UNIFORM = "uniform"      # Single uniform color
    HEIGHT = "height"        # Color by Z-coordinate (height)
    INTENSITY = "intensity"  # Color by intensity (if available)
    NORMAL = "normal"        # Color by normal vector


class PointCloudRenderer:
    """Point cloud file renderer supporting multiple formats"""

    # Supported file extensions
    SUPPORTED_FORMATS = {'.ply', '.pcd', '.xyz', '.pts', '.las', '.laz'}

    def __init__(
        self,
        pointcloud_file: Union[str, Path],
        output_dir: str = ".",
        image_width: int = 800,
        image_height: int = 600,
        point_size: float = 1.5,
        bg_color: List[float] = None,
        color_scheme: ColorScheme = ColorScheme.UNIFORM,
        uniform_color: List[float] = None,
        auto_scale: bool = True
    ):
        """
        Initialize point cloud renderer

        Parameters:
            pointcloud_file: Path to point cloud file (.ply, .pcd, .xyz, .pts, .las, .laz)
            output_dir: Output directory for rendered images
            image_width: Image width in pixels (default: 800)
            image_height: Image height in pixels (default: 600)
            point_size: Size of rendered points (default: 1.5)
            bg_color: Background color as RGB list [0-1] (default: [1.0, 1.0, 1.0] - white)
            color_scheme: Color scheme for points (default: UNIFORM)
            uniform_color: Uniform color for points [0-1] (default: [0.7, 0.7, 0.7])
            auto_scale: Automatically center and scale the point cloud (default: True)
        """
        self.pointcloud_file = Path(pointcloud_file)
        self.output_dir = Path(output_dir)
        self.image_width = image_width
        self.image_height = image_height
        self.point_size = point_size
        self.bg_color = bg_color or [1.0, 1.0, 1.0]
        self.color_scheme = color_scheme
        self.uniform_color = uniform_color or [0.7, 0.7, 0.7]
        self.auto_scale = auto_scale

        # Internal state
        self.pointcloud = None
        self.original_pointcloud = None  # Keep original for reset
        self.bounding_box = None

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Validate and load
        self._validate_file()
        self._load_pointcloud()

    def _validate_file(self):
        """Validate input file exists and format is supported"""
        if not self.pointcloud_file.exists():
            raise FileNotFoundError(f"Point cloud file not found: {self.pointcloud_file}")

        ext = self.pointcloud_file.suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported file format: {ext}\n"
                f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"
            )

    def _load_pointcloud(self):
        """Load point cloud from file"""
        ext = self.pointcloud_file.suffix.lower()
        print(f"Loading point cloud: {self.pointcloud_file}")

        try:
            if ext in ['.ply', '.pcd', '.xyz', '.pts']:
                # Open3D natively supports these formats
                self.pointcloud = o3d.io.read_point_cloud(str(self.pointcloud_file))
            elif ext in ['.las', '.laz']:
                # LAS/LAZ requires laspy
                self._load_las_file()
            else:
                raise ValueError(f"Unsupported format: {ext}")

            if self.pointcloud.is_empty():
                raise ValueError("Loaded point cloud is empty")

            # Store original
            self.original_pointcloud = self.pointcloud

            # Apply auto-scaling if enabled
            if self.auto_scale:
                self._center_and_scale()

            # Compute bounding box
            self.bounding_box = self.pointcloud.get_axis_aligned_bounding_box()

            num_points = len(self.pointcloud.points)
            print(f"Loaded {num_points:,} points")

            # Apply color scheme
            self._apply_color_scheme()

        except Exception as e:
            raise RuntimeError(f"Failed to load point cloud: {e}")

    def _load_las_file(self):
        """Load LAS/LAZ file using laspy"""
        try:
            import laspy
        except ImportError:
            raise ImportError(
                "laspy is required for LAS/LAZ support. "
                "Install with: pip install laspy"
            )

        # Read LAS file
        las = laspy.read(str(self.pointcloud_file))

        # Extract points
        points = np.vstack([las.x, las.y, las.z]).transpose()

        # Create Open3D point cloud
        self.pointcloud = o3d.geometry.PointCloud()
        self.pointcloud.points = o3d.utility.Vector3dVector(points)

        # Extract intensity if available
        if hasattr(las, 'intensity'):
            intensity = np.array(las.intensity).astype(np.float64)
            # Normalize intensity to 0-1
            if intensity.max() > 0:
                intensity = intensity / intensity.max()
            self.pointcloud.colors = o3d.utility.Vector3dVector(
                np.column_stack([intensity, intensity, intensity])
            )

    def _center_and_scale(self):
        """Center the point cloud at origin and normalize scale"""
        if self.pointcloud is None:
            return

        # Get bounding box
        bbox = self.pointcloud.get_axis_aligned_bounding_box()
        center = bbox.get_center()
        extent = bbox.get_extent()
        max_extent = np.max(extent)

        # Center at origin
        points = np.asarray(self.pointcloud.points)
        points = points - center

        # Scale to reasonable size (max extent = 2.0)
        if max_extent > 0:
            scale = 2.0 / max_extent
            points = points * scale

        self.pointcloud.points = o3d.utility.Vector3dVector(points)

        # Update bounding box
        self.bounding_box = self.pointcloud.get_axis_aligned_bounding_box()

    def _apply_color_scheme(self):
        """Apply selected color scheme to point cloud"""
        if self.pointcloud is None:
            return

        num_points = len(self.pointcloud.points)

        if self.color_scheme == ColorScheme.UNIFORM:
            # Apply uniform color
            colors = np.tile(self.uniform_color, (num_points, 1))
            self.pointcloud.colors = o3d.utility.Vector3dVector(colors)

        elif self.color_scheme == ColorScheme.HEIGHT:
            # Color by height (Z-coordinate)
            points = np.asarray(self.pointcloud.points)
            z_values = points[:, 2]
            z_min, z_max = z_values.min(), z_values.max()

            if z_max > z_min:
                normalized = (z_values - z_min) / (z_max - z_min)
            else:
                normalized = np.zeros(num_points)

            # Apply colormap (viridis-like: dark blue to yellow)
            colors = self._apply_colormap(normalized)
            self.pointcloud.colors = o3d.utility.Vector3dVector(colors)

        elif self.color_scheme == ColorScheme.INTENSITY:
            # Check if intensity colors already exist (from LAS file)
            if not self.pointcloud.has_colors():
                # Default to uniform if no intensity
                colors = np.tile(self.uniform_color, (num_points, 1))
                self.pointcloud.colors = o3d.utility.Vector3dVector(colors)

        elif self.color_scheme == ColorScheme.NORMAL:
            # Compute normals if not present
            if not self.pointcloud.has_normals():
                self.pointcloud.estimate_normals()

            # Color by normal direction (map -1,1 to 0,1)
            normals = np.asarray(self.pointcloud.normals)
            colors = (normals + 1.0) / 2.0
            self.pointcloud.colors = o3d.utility.Vector3dVector(colors)

    def _apply_colormap(self, values: np.ndarray) -> np.ndarray:
        """Apply viridis-like colormap to values in range [0, 1]"""
        # Simple viridis-like colormap
        colors = np.zeros((len(values), 3))

        for i, v in enumerate(values):
            if v < 0.25:
                # Blue to cyan
                t = v / 0.25
                colors[i] = [0.0, t, 1.0]
            elif v < 0.5:
                # Cyan to green
                t = (v - 0.25) / 0.25
                colors[i] = [0.0, 1.0, 1.0 - t]
            elif v < 0.75:
                # Green to yellow
                t = (v - 0.5) / 0.25
                colors[i] = [t, 1.0, 0.0]
            else:
                # Yellow to red
                t = (v - 0.75) / 0.25
                colors[i] = [1.0, 1.0 - t, 0.0]

        return colors

    def downsample(self, voxel_size: float = 0.01):
        """
        Downsample point cloud using voxel grid

        Parameters:
            voxel_size: Size of voxel for downsampling
        """
        if self.pointcloud is None:
            return

        print(f"Downsampling with voxel size: {voxel_size}")
        original_count = len(self.pointcloud.points)
        self.pointcloud = self.pointcloud.voxel_down_sample(voxel_size)
        new_count = len(self.pointcloud.points)
        print(f"Downsampled from {original_count:,} to {new_count:,} points")

        # Re-apply color scheme
        self._apply_color_scheme()

    def estimate_normals(self, radius: float = 0.1, max_nn: int = 30):
        """
        Estimate normals for the point cloud

        Parameters:
            radius: Search radius for normal estimation
            max_nn: Maximum number of nearest neighbors
        """
        if self.pointcloud is None:
            return

        print("Estimating normals...")
        self.pointcloud.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=radius,
                max_nn=max_nn
            )
        )
        self.pointcloud.orient_normals_consistent_tangent_plane(100)
        print("Normals estimated")

    def render_view(
        self,
        view_name: str,
        azimuth: float = 45,
        elevation: float = 30,
        zoom: float = 1.0
    ) -> Optional[str]:
        """
        Render point cloud from specified view

        Parameters:
            view_name: Name for the output file
            azimuth: Azimuth angle in degrees (rotation around Z axis)
            elevation: Elevation angle in degrees (rotation around X axis)
            zoom: Zoom ratio (1.0 = default)

        Returns:
            Path to rendered image file, or None if rendering failed
        """
        if self.pointcloud is None:
            raise RuntimeError("No point cloud loaded")

        output_file = self.output_dir / f"{self.pointcloud_file.stem}_{view_name}.png"

        print(f"Rendering view: {view_name} (azimuth={azimuth}°, elevation={elevation}°)")

        try:
            # Create visualizer
            vis = o3d.visualization.Visualizer()
            vis.create_window(
                width=self.image_width,
                height=self.image_height,
                visible=False  # Headless rendering
            )

            # Add point cloud
            vis.add_geometry(self.pointcloud)

            # Get render option
            render_opt = vis.get_render_option()
            render_opt.point_size = self.point_size
            render_opt.background_color = np.array(self.bg_color)
            render_opt.show_coordinate_frame = True

            # Set camera view
            ctr = vis.get_view_control()

            # Calculate camera position
            bbox = self.pointcloud.get_axis_aligned_bounding_box()
            center = bbox.get_center()
            extent = bbox.get_extent()
            max_extent = np.max(extent)

            # Distance based on zoom and extent
            distance = max_extent * 2.0 / zoom

            # Convert angles to radians
            azimuth_rad = math.radians(azimuth)
            elevation_rad = math.radians(elevation)

            # Calculate camera position
            x = distance * math.cos(elevation_rad) * math.cos(azimuth_rad)
            y = distance * math.cos(elevation_rad) * math.sin(azimuth_rad)
            z = distance * math.sin(elevation_rad)

            front = np.array([x, y, z])
            up = np.array([0, 0, 1])

            # Set camera
            ctr.set_lookat(center)
            ctr.set_front(front)
            ctr.set_up(up)
            ctr.set_zoom(zoom)

            # Update view
            vis.update_geometry(self.pointcloud)
            vis.poll_events()
            vis.update_renderer()

            # Capture image
            vis.capture_screen_image(str(output_file), do_render=True)

            # Clean up
            vis.destroy_window()

            print(f"  Saved image: {output_file}")
            return str(output_file)

        except Exception as e:
            print(f"  Rendering failed: {e}")
            return None

    def render_multiple_views(self) -> List[Tuple[str, str]]:
        """
        Render point cloud from multiple standard views

        Rendered views:
            - front: Front view
            - top: Top view
            - right: Right view
            - isometric: Isometric view
            - perspective: Perspective view

        Returns:
            List of tuples (view_name, file_path)
        """
        views = {
            'front': {'azimuth': 0, 'elevation': 0, 'zoom': 1.0},
            'top': {'azimuth': 0, 'elevation': 90, 'zoom': 1.0},
            'right': {'azimuth': 90, 'elevation': 0, 'zoom': 1.0},
            'isometric': {'azimuth': 45, 'elevation': 35, 'zoom': 1.0},
            'perspective': {'azimuth': 30, 'elevation': 20, 'zoom': 1.0},
        }

        print(f"\nRendering {len(views)} views...")

        results = []
        for view_name, params in views.items():
            output = self.render_view(view_name, **params)
            if output:
                results.append((view_name, output))

        print(f"\nSuccessfully rendered {len(results)} views")
        return results


def render_pointcloud_to_images(
    pointcloud_file: Union[str, Path],
    output_dir: str = ".",
    width: int = 800,
    height: int = 600,
    point_size: float = 1.5,
    color_scheme: ColorScheme = ColorScheme.UNIFORM,
    auto_scale: bool = True
) -> List[Tuple[str, str]]:
    """
    Convenience function to render point cloud to multi-view images

    Parameters:
        pointcloud_file: Path to point cloud file
        output_dir: Output directory
        width: Image width
        height: Image height
        point_size: Size of rendered points
        color_scheme: Color scheme for visualization
        auto_scale: Automatically center and scale point cloud

    Returns:
        List of tuples (view_name, file_path)
    """
    renderer = PointCloudRenderer(
        pointcloud_file=pointcloud_file,
        output_dir=output_dir,
        image_width=width,
        image_height=height,
        point_size=point_size,
        color_scheme=color_scheme,
        auto_scale=auto_scale
    )
    return renderer.render_multiple_views()


def main():
    """Main entry point for command-line usage"""
    if len(sys.argv) < 2:
        print("Usage: python render_pointcloud.py <pointcloud_file> [output_dir]")
        print("       python render_pointcloud.py <pointcloud_file> [output_dir] [options]")
        print("\nSupported formats: .ply, .pcd, .xyz, .pts, .las, .laz")
        print("\nOptions:")
        print("  --width <n>      Image width (default: 800)")
        print("  --height <n>     Image height (default: 600)")
        print("  --point-size <n> Point size (default: 1.5)")
        print("  --no-scale       Disable auto-scaling")
        print("  --color <scheme> Color scheme: uniform, height, normal (default: uniform)")
        print("\nExample:")
        print("  python render_pointcloud.py scan.ply ./output --width 1200 --height 900")
        sys.exit(1)

    pointcloud_file = sys.argv[1]
    output_dir = "."
    width = 800
    height = 600
    point_size = 1.5
    auto_scale = True
    color_scheme = ColorScheme.UNIFORM

    # Parse optional arguments
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--width' and i + 1 < len(sys.argv):
            width = int(sys.argv[i + 1])
            i += 2
        elif arg == '--height' and i + 1 < len(sys.argv):
            height = int(sys.argv[i + 1])
            i += 2
        elif arg == '--point-size' and i + 1 < len(sys.argv):
            point_size = float(sys.argv[i + 1])
            i += 2
        elif arg == '--no-scale':
            auto_scale = False
            i += 1
        elif arg == '--color' and i + 1 < len(sys.argv):
            scheme = sys.argv[i + 1].lower()
            if scheme == 'height':
                color_scheme = ColorScheme.HEIGHT
            elif scheme == 'normal':
                color_scheme = ColorScheme.NORMAL
            else:
                color_scheme = ColorScheme.UNIFORM
            i += 2
        elif not arg.startswith('--'):
            output_dir = arg
            i += 1
        else:
            i += 1

    print("=" * 60)
    print("PointCloud Renderer")
    print("=" * 60)
    print(f"Input file: {pointcloud_file}")
    print(f"Output directory: {output_dir}")
    print(f"Image size: {width}x{height}")
    print(f"Point size: {point_size}")
    print(f"Color scheme: {color_scheme.value}")
    print(f"Auto-scale: {auto_scale}")
    print("=" * 60)

    try:
        results = render_pointcloud_to_images(
            pointcloud_file=pointcloud_file,
            output_dir=output_dir,
            width=width,
            height=height,
            point_size=point_size,
            color_scheme=color_scheme,
            auto_scale=auto_scale
        )

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
