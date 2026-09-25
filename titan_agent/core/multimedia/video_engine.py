"""
Video Engine for Universal Agent HP.
Automates video montage, trimming, cropping, audio merging, and format transcoding.
Supports FFmpeg CLI and MoviePy pipelines.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


class VideoEngine:
    """Automates video editing and montage operations via FFmpeg & Python."""

    COMMON_FFMPEG_PATHS: tuple[str, ...] = (
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
        r"C:\tools\ffmpeg\bin\ffmpeg.exe",
    )

    COMMON_FFPROBE_PATHS: tuple[str, ...] = (
        r"C:\ffmpeg\bin\ffprobe.exe",
        r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
        r"C:\ProgramData\chocolatey\bin\ffprobe.exe",
        r"C:\tools\ffmpeg\bin\ffprobe.exe",
    )

    @classmethod
    def locate_ffmpeg(cls) -> str | None:
        """Locates the ffmpeg executable on the host system."""
        found = shutil.which("ffmpeg")
        if found:
            return found
        for candidate in cls.COMMON_FFMPEG_PATHS:
            if os.path.exists(candidate):
                return candidate
        return None

    @classmethod
    def locate_ffprobe(cls) -> str | None:
        """Locates the ffprobe executable on the host system."""
        found = shutil.which("ffprobe")
        if found:
            return found
        for candidate in cls.COMMON_FFPROBE_PATHS:
            if os.path.exists(candidate):
                return candidate
        return None

    @classmethod
    def probe_media(cls, file_path: str) -> dict[str, Any]:
        """Inspects video metadata (resolution, duration, codec, bitrate)."""
        ffprobe_bin = cls.locate_ffprobe()
        path = Path(file_path).resolve()

        if not path.exists():
            return {"error": f"File not found: {file_path}", "exists": False}

        if not ffprobe_bin:
            size_mb = round(path.stat().st_size / (1024 * 1024), 2)
            return {
                "file": str(path),
                "exists": True,
                "size_mb": size_mb,
                "notice": "ffprobe not found in PATH. Install ffmpeg (e.g. winget install Gyan.FFmpeg) for full codec inspection.",
            }

        cmd = [
            ffprobe_bin,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                streams = data.get("streams", [])
                v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
                a_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
                fmt = data.get("format", {})

                return {
                    "file": str(path),
                    "exists": True,
                    "duration_sec": float(fmt.get("duration", 0)),
                    "format_name": fmt.get("format_name"),
                    "size_mb": round(float(fmt.get("size", 0)) / (1024 * 1024), 2),
                    "video": {
                        "codec": v_stream.get("codec_name"),
                        "width": v_stream.get("width"),
                        "height": v_stream.get("height"),
                        "fps": eval(v_stream.get("r_frame_rate", "30/1")) if "/" in v_stream.get("r_frame_rate", "") else None,
                    },
                    "audio": {
                        "codec": a_stream.get("codec_name"),
                        "channels": a_stream.get("channels"),
                        "sample_rate": a_stream.get("sample_rate"),
                    }
                }
            return {"error": res.stderr.strip() or "ffprobe failed"}
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

    @classmethod
    def generate_montage_command(
        cls,
        operation: str,
        input_video: str,
        output_video: str,
        start_time: str | None = None,
        duration: str | None = None,
        audio_track: str | None = None,
        aspect_ratio: str | None = None,
        speed: float = 1.0,
    ) -> dict[str, Any]:
        """Generates the optimal FFmpeg command for the requested montage operation."""
        ffmpeg_bin = cls.locate_ffmpeg() or "ffmpeg"
        cmd = [ffmpeg_bin]

        if operation == "trim":
            if start_time:
                cmd.extend(["-ss", start_time])
            if duration:
                cmd.extend(["-t", duration])
            cmd.extend(["-i", input_video, "-c", "copy", output_video])

        elif operation == "crop_vertical":
            # Crop to 9:16 for Reels/Shorts/TikTok
            cmd.extend([
                "-i", input_video,
                "-vf", "crop=ih*(9/16):ih,scale=1080:1920",
                "-c:a", "copy",
                output_video
            ])

        elif operation == "merge_audio":
            if not audio_track:
                return {"error": "audio_track is required for merge_audio operation"}
            cmd.extend([
                "-i", input_video,
                "-i", audio_track,
                "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[a]",
                "-map", "0:v",
                "-map", "[a]",
                "-c:v", "copy",
                output_video
            ])

        elif operation == "speed":
            pts = 1.0 / speed
            cmd.extend([
                "-i", input_video,
                "-filter_complex", f"[0:v]setpts={pts}*PTS[v];[0:a]atempo={speed}[a]",
                "-map", "[v]",
                "-map", "[a]",
                output_video
            ])

        else:
            return {"error": f"Unknown operation: {operation}"}

        command_str = " ".join(cmd)
        return {
            "operation": operation,
            "command": cmd,
            "command_str": command_str,
            "ffmpeg_available": cls.locate_ffmpeg() is not None,
        }
