"""Tests for Multimedia Skills and Tools (Video Editing & Blender 3D Engine)."""
import ast
import tempfile
from pathlib import Path

import pytest

from titan_agent.core.multimedia.blender_engine import BlenderEngine
from titan_agent.core.multimedia.video_engine import VideoEngine
from titan_agent.skills import SkillRegistry
from titan_agent.tools import ToolRegistry


def test_skills_loaded():
    """Verify SkillRegistry discovers both video-editing and blender-ops skills."""
    registry = SkillRegistry()
    skills = registry.list_skills()
    skill_names = {s["name"] for s in skills}

    assert "video-editing" in skill_names
    assert "blender-ops" in skill_names

    v_skill = registry.get_skill("video-editing")
    assert v_skill is not None
    assert "ffmpeg" in v_skill.keywords
    assert "montage" in v_skill.keywords
    assert "reels" in v_skill.keywords

    b_skill = registry.get_skill("blender-ops")
    assert b_skill is not None
    assert "3d" in b_skill.keywords
    assert "bpy" in b_skill.keywords
    assert "render" in b_skill.keywords

    # Keyword matching
    v_matches = [s.name for s in registry.find_matches("video montaj ffmpeg")]
    assert "video-editing" in v_matches

    b_matches = [s.name for s in registry.find_matches("blender 3d scene render")]
    assert "blender-ops" in b_matches


def test_video_engine_montage_commands():
    """Verify VideoEngine generates correct FFmpeg command lines for all operations."""
    # 1. Trim operation
    trim_res = VideoEngine.generate_montage_command(
        operation="trim",
        input_video="input.mp4",
        output_video="trimmed.mp4",
        start_time="00:00:10",
        duration="00:00:30",
    )
    assert "error" not in trim_res
    cmd = trim_res["command"]
    assert "-ss" in cmd
    assert "00:00:10" in cmd
    assert "-t" in cmd
    assert "00:00:30" in cmd
    assert "-c" in cmd
    assert "copy" in cmd

    # 2. Vertical crop operation (9:16 for Shorts / Reels)
    crop_res = VideoEngine.generate_montage_command(
        operation="crop_vertical",
        input_video="raw.mp4",
        output_video="vertical.mp4",
    )
    assert "error" not in crop_res
    assert any("crop=ih*(9/16):ih" in str(arg) for arg in crop_res["command"])

    # 3. Audio merge operation
    audio_res = VideoEngine.generate_montage_command(
        operation="merge_audio",
        input_video="video.mp4",
        output_video="merged.mp4",
        audio_track="bgm.mp3",
    )
    assert "error" not in audio_res
    assert any("amix=" in str(arg) for arg in audio_res["command"])

    # 4. Speed adjustment operation
    speed_res = VideoEngine.generate_montage_command(
        operation="speed",
        input_video="video.mp4",
        output_video="fast.mp4",
        speed=2.0,
    )
    assert "error" not in speed_res
    assert any("atempo=2.0" in str(arg) for arg in speed_res["command"])

    # 5. Invalid operation
    bad_res = VideoEngine.generate_montage_command(
        operation="unknown_op",
        input_video="a.mp4",
        output_video="b.mp4",
    )
    assert "error" in bad_res


def test_video_engine_probe_nonexistent():
    """Verify VideoEngine handles missing media gracefully."""
    res = VideoEngine.probe_media("nonexistent_video_path_12345.mp4")
    assert "error" in res or res.get("exists") is False


def test_blender_engine_script_generation():
    """Verify BlenderEngine generates syntactically valid Python bpy scripts."""
    # Test cube scene
    cube_script = BlenderEngine.generate_procedural_scene_script(
        primitive="cube",
        output_image="output_cube.png",
        engine="BLENDER_EEVEE",
    )
    assert "import bpy" in cube_script
    assert "primitive_cube_add" in cube_script
    assert "output_cube.png" in cube_script
    # Validate Python syntax via AST
    ast.parse(cube_script)

    # Test sphere scene
    sphere_script = BlenderEngine.generate_procedural_scene_script(
        primitive="sphere",
        output_image="output_sphere.png",
        engine="CYCLES",
    )
    assert "primitive_uv_sphere_add" in sphere_script
    assert "output_sphere.png" in sphere_script
    ast.parse(sphere_script)

    # Test cylinder scene
    cyl_script = BlenderEngine.generate_procedural_scene_script(
        primitive="cylinder",
        output_image="cylinder.png",
    )
    assert "primitive_cylinder_add" in cyl_script
    ast.parse(cyl_script)


def test_blender_engine_execution_fallback():
    """Verify BlenderEngine handles missing files or absent binaries gracefully."""
    res = BlenderEngine.execute_blender_script("non_existent_blender_script.py")
    assert res.get("success") is False
    assert "not found" in res.get("error", "").lower()


@pytest.mark.asyncio
async def test_tool_registry_multimedia_integration():
    """Verify ToolRegistry exposes and executes all multimedia tools."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        registry = ToolRegistry(workspace=tmp_path)
        defs = registry.get_tool_definitions()
        names = {d["function"]["name"] for d in defs}

        assert "video_probe" in names
        assert "video_montage_command" in names
        assert "blender_generate_scene" in names
        assert "blender_execute_script" in names

        # Test video_montage_command execution
        montage_output = await registry.execute_tool(
            "video_montage_command",
            {
                "operation": "crop_vertical",
                "input_video": "raw_input.mp4",
                "output_video": "vertical_output.mp4",
            },
        )
        assert "Video Montage Command (crop_vertical)" in montage_output
        assert "ffmpeg" in montage_output.lower()

        # Test blender_generate_scene with save_path
        script_file = tmp_path / "scene.py"
        blender_output = await registry.execute_tool(
            "blender_generate_scene",
            {
                "primitive": "torus",
                "output_image": "torus_render.png",
                "save_path": str(script_file),
            },
        )
        assert "generated and saved" in blender_output
        assert script_file.exists()
        content = script_file.read_text(encoding="utf-8")
        assert "primitive_torus_add" in content
        ast.parse(content)

        # Test video_probe error handling
        probe_output = await registry.execute_tool(
            "video_probe",
            {"file_path": "missing_video.mp4"},
        )
        assert "Probe Failed" in probe_output or "missing_video.mp4" in probe_output

        # Test blender_execute_script missing file handling
        exec_output = await registry.execute_tool(
            "blender_execute_script",
            {"script_path": "non_existent_script.py"},
        )
        assert "not found" in exec_output.lower()
