"""
Blender Engine for Universal Agent HP.
Automates 3D modeling, scene generation, material setup, and headless background rendering via Blender Python (bpy).
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


class BlenderEngine:
    """Automates headless Blender 3D modeling and rendering workflows."""

    COMMON_BLENDER_PATHS: tuple[str, ...] = (
        r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender\blender.exe",
        r"C:\ProgramData\chocolatey\bin\blender.exe",
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/usr/bin/blender",
        "/usr/local/bin/blender",
    )

    @classmethod
    def locate_blender(cls) -> str | None:
        """Locates the Blender executable on the host system."""
        found = shutil.which("blender")
        if found:
            return found

        # Search glob in Program Files
        windows_glob = glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe")
        if windows_glob:
            return windows_glob[-1]  # Return highest version found

        for candidate in cls.COMMON_BLENDER_PATHS:
            if os.path.exists(candidate):
                return candidate
        return None

    @classmethod
    def generate_procedural_scene_script(
        cls,
        primitive: str = "cube",
        output_image: str = "render_output.png",
        color_rgb: tuple = (0.2, 0.6, 1.0),
        metallic: float = 0.8,
        roughness: float = 0.2,
        engine: str = "BLENDER_EEVEE",
        resolution: tuple = (1920, 1080),
    ) -> str:
        """Generates a complete headless Blender Python script (bpy) to build and render a scene."""
        prim = primitive.lower()
        if prim == "sphere":
            add_mesh = "bpy.ops.mesh.primitive_uv_sphere_add(radius=1.5, location=(0, 0, 1.5))"
        elif prim == "cylinder":
            add_mesh = "bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=2, location=(0, 0, 1))"
        elif prim == "torus":
            add_mesh = "bpy.ops.mesh.primitive_torus_add(location=(0, 0, 1))"
        else:
            add_mesh = "bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))"

        safe_output_image = str(output_image).replace("\\", "/")

        script = f"""import bpy

# 1. Clean existing scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 2. Add 3D Procedural Mesh
{add_mesh}
obj = bpy.context.active_object
obj.name = "GeneratedAsset"

# 3. Create and assign PBR material
mat = bpy.data.materials.new(name="PBRMaterial")
mat.use_nodes = True
nodes = mat.node_tree.nodes
bsdf = nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = ({color_rgb[0]}, {color_rgb[1]}, {color_rgb[2]}, 1.0)
    bsdf.inputs["Metallic"].default_value = {metallic}
    bsdf.inputs["Roughness"].default_value = {roughness}
obj.data.materials.append(mat)

# 4. Add Studio Lighting (Key Light + Fill Light)
key_light_data = bpy.data.lights.new(name="KeyLight", type='SUN')
key_light_data.energy = 5.0
key_light_obj = bpy.data.objects.new(name="KeyLight", object_data=key_light_data)
bpy.context.collection.objects.link(key_light_obj)
key_light_obj.rotation_euler = (0.785, 0, 0.785)

fill_light_data = bpy.data.lights.new(name="FillLight", type='POINT')
fill_light_data.energy = 100.0
fill_light_obj = bpy.data.objects.new(name="FillLight", object_data=fill_light_data)
bpy.context.collection.objects.link(fill_light_obj)
fill_light_obj.location = (-4, -4, 3)

# 5. Position Camera
cam_data = bpy.data.cameras.new(name="MainCamera")
cam_obj = bpy.data.objects.new(name="MainCamera", object_data=cam_data)
bpy.context.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj
cam_obj.location = (5, -5, 4)
cam_obj.rotation_euler = (1.1, 0, 0.785)

# 6. Configure Render Settings
scene = bpy.context.scene
scene.render.engine = '{engine}'
scene.render.resolution_x = {resolution[0]}
scene.render.resolution_y = {resolution[1]}
scene.render.filepath = "{safe_output_image}"

# 7. Render Still Image
bpy.ops.render.render(write_still=True)
print("SUCCESS: Rendered {safe_output_image}")
"""
        return script

    @classmethod
    def execute_blender_script(cls, script_path: str) -> dict[str, Any]:
        """Executes a Python script inside Blender in headless background mode."""
        blender_bin = cls.locate_blender()
        s_path = Path(script_path).resolve()

        if not s_path.exists():
            return {"error": f"Script not found: {script_path}", "success": False}

        if not blender_bin:
            return {
                "success": False,
                "error": "Blender executable not found in PATH or standard installation directories.",
                "notice": "Install Blender via: winget install BlenderFoundation.Blender (Windows) or brew install blender (Mac)",
                "script_path": str(s_path),
                "command_to_run": f"blender --background --python {s_path}",
            }

        cmd = [blender_bin, "--background", "--python", str(s_path)]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
            return {
                "success": res.returncode == 0,
                "blender_path": blender_bin,
                "returncode": res.returncode,
                "stdout_tail": "\n".join(res.stdout.splitlines()[-10:]),
                "stderr_tail": "\n".join(res.stderr.splitlines()[-10:]),
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Blender render process timed out (120s limit)."}
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": str(e)}
