---
name: blender-ops
description: Playbook for automated Blender 3D modeling, headless Python scripting (bpy), procedural scene setup, materials, and batch rendering.
keywords: blender, 3d, bpy, render, mesh, modeling, animation, cycles, eevee, gltf, obj, fbx, scene, texture, lighting, camera
---

# Blender 3D Modeling & Rendering (Headless bpy Playbook)

Follow this operational playbook whenever the user requests 3D modeling, procedural asset creation, animation, materials setup, or automated rendering via Blender.

## Core Rules & Execution Discipline
1. **HEADLESS BACKGROUND RUNS**: Never require a GUI window for automated jobs. Always run Blender in background mode:
   ```bash
   blender --background --python render_script.py
   # or shorthand:
   blender -b -P render_script.py
   ```
2. **CLEAN START**: Always clear existing scene objects (`bpy.ops.object.select_all(action='SELECT')`, `bpy.ops.object.delete()`) before building procedural assets.
3. **ENGINE SELECTION**:
   - **BLENDER_EEVEE / BLENDER_EEVEE_NEXT**: Ultra-fast preview and real-time rendering.
   - **CYCLES**: High-fidelity photorealistic rendering (use GPU compute if available: `cycles.device = 'GPU'`).
4. **CAMERA & LIGHTING ESSENTIALS**:
   - Every render requires at least one active Camera (`bpy.context.scene.camera = cam_obj`).
   - Use 3-point lighting setup (Key Light, Fill Light, Rim/Back Light) or an HDRI environment background.
5. **SAFE ASSET EXPORT / IMPORT**:
   - Standard export: GLTF/GLB (`bpy.ops.export_scene.gltf(...)`) for web/game engines.
   - OBJ / FBX export for universal 3D interchange.

## Standard Headless Blender Python Template (`render_script.py`)

```python
import bpy

# 1. Clean scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 2. Create procedural object (e.g. Smooth Cube or Sphere)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
obj = bpy.context.active_object
obj.name = "HeroAsset"

# 3. Create and assign metallic material
mat = bpy.data.materials.new(name="HeroMaterial")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = (0.1, 0.5, 0.9, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.8
    bsdf.inputs["Roughness"].default_value = 0.2
obj.data.materials.append(mat)

# 4. Add Sunlight
light_data = bpy.data.lights.new(name="SunLight", type='SUN')
light_data.energy = 5.0
light_obj = bpy.data.objects.new(name="SunLight", object_data=light_data)
bpy.context.collection.objects.link(light_obj)
light_obj.rotation_euler = (0.785, 0, 0.785)

# 5. Position Camera
cam_data = bpy.data.cameras.new(name="MainCamera")
cam_obj = bpy.data.objects.new(name="MainCamera", object_data=cam_data)
bpy.context.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj
cam_obj.location = (5, -5, 4)
cam_obj.rotation_euler = (1.1, 0, 0.785)

# 6. Configure Render Settings
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.filepath = "//render_output.png"

# 7. Render still image
bpy.ops.render.render(write_still=True)
print("Rendering finished successfully: render_output.png")
```
