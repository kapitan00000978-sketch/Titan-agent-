---
name: video-editing
description: Playbook for automated video montage, cutting, audio sync, subtitles, transcode, and FFmpeg/MoviePy pipelines.
keywords: video, montage, edit, ffmpeg, moviepy, audio, subtitles, cut, trim, concat, clip, render, mp4, reels, shorts, tiktok
---

# Video Editing & Montage (FFmpeg & MoviePy Playbook)

Follow this operational playbook whenever the user requests video editing, montage creation, clipping, audio sync, or video transformations.

## Core Rules & Principles
1. **PROBE BEFORE MUTATING**: Always inspect media duration, resolution, codec, and audio channels using `ffprobe` or `video_probe` before running heavy rendering jobs.
2. **STREAM COPY WHEN POSSIBLE**: For simple cuts and trims without re-encoding, use `-c copy` with FFmpeg to achieve instantaneous (0ms) lossless processing.
3. **AUDIO NORMALIZATION**: Always ensure audio tracks are normalized (`loudnorm` filter or `-af "volume=1.5"`) to prevent clipping or muted audio.
4. **ASPECT RATIO AWARENESS**:
   - Landscape (YouTube / Standard): `1920x1080` (16:9)
   - Vertical (Reels / Shorts / TikTok): `1080x1920` (9:16)
   - Square (Feed / Instagram): `1080x1080` (1:1)
5. **HERMETIC SCRIPTS**: When complex multi-track montage is required, write a self-contained Python script using `moviepy` or an automated FFmpeg batch file with explicit paths.

## Common FFmpeg Recipes

### 1. Instant Cut / Trim (No Re-encoding)
```bash
ffmpeg -ss 00:00:10 -to 00:00:45 -i input.mp4 -c copy output_clip.mp4
```

### 2. Vertical Format Conversion for Reels / TikTok (Crop to 9:16)
```bash
ffmpeg -i input.mp4 -vf "crop=ih*(9/16):ih,scale=1080:1920" -c:a copy output_vertical.mp4
```

### 3. Add Background Music with Audio Ducking
```bash
ffmpeg -i video.mp4 -i music.mp3 -filter_complex "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[a]" -map 0:v -map "[a]" -c:v copy output_montage.mp4
```

### 4. Fast Motion / Speed Up Video
```bash
ffmpeg -i input.mp4 -filter_complex "[0:v]setpts=0.5*PTS[v];[0:a]atempo=2.0[a]" -map "[v]" -map "[a]" output_2x.mp4
```

### 5. Concatenate Multiple Clips
Create `clips.txt`:
```
file 'clip1.mp4'
file 'clip2.mp4'
file 'clip3.mp4'
```
Execute:
```bash
ffmpeg -f concat -safe 0 -i clips.txt -c copy final_montage.mp4
```
