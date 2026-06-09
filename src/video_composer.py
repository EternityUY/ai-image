"""Video composer — creates a slideshow video from multiple images with transitions.

Uses FFmpeg xfade filter for transition effects between images.
Duration is automatically matched to the audio track length.
Supports Ken Burns zoom/pan effect and text watermark overlay.
"""

import glob
import logging
import os
import random
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_IS_WINDOWS = sys.platform == "win32"

# Well-known CJK font paths
_CJK_FONT_PATTERNS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK*.ttf",
    "/usr/share/fonts/opentype/noto/*.ttc",
    "/usr/share/fonts/truetype/wqy/*.ttc",
    "/usr/share/fonts/truetype/wqy/*.ttf",
    "/System/Library/Fonts/PingFang.ttc",
]

if _IS_WINDOWS:
    _CJK_FONT_PATTERNS += [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]

# Supported xfade transition styles
_TRANSITION_STYLES = {
    "fade": "fade",
    "fadeblack": "fadeblack",
    "fadewhite": "fadewhite",
    "dissolve": "dissolve",
    "slideleft": "slideleft",
    "slideright": "slideright",
    "slideup": "slideup",
    "slidedown": "slidedown",
    "smoothleft": "smoothleft",
    "smoothright": "smoothright",
    "smoothup": "smoothup",
    "smoothdown": "smoothdown",
    "circleopen": "circleopen",
    "circleclose": "circleclose",
    "rectopen": "rectopen",
    "rectclose": "rectclose",
    "pixelize": "pixelize",
    "radial": "radial",
    "hblur": "hblur",
    "wipetl": "wipetl",
    "wipe": "wipe",
    "zoomin": "zoomin",
    "hlslice": "hlslice",
}


def _resolve_font(configured_path: str | None) -> str | None:
    """Find an available CJK font file on the system."""
    candidates: list[str] = []

    if configured_path and os.path.isfile(configured_path):
        candidates.append(configured_path)

    for pattern in _CJK_FONT_PATTERNS:
        if "*" in pattern or "?" in pattern:
            candidates.extend(sorted(glob.glob(pattern)))
        elif os.path.isfile(pattern):
            candidates.append(pattern)

    if not _IS_WINDOWS:
        try:
            result = subprocess.run(
                ["fc-list", ":lang=zh", "file"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    file_path = line.split(":")[0].strip()
                    if file_path and os.path.isfile(file_path):
                        candidates.append(file_path)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    seen: set[str] = set()
    unique: list[str] = []
    for p in candidates:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    _TEST_FONT_SIZE = 16
    _MIN_CJK_WIDTH = 14
    for path in unique:
        try:
            f = ImageFont.truetype(path, _TEST_FONT_SIZE)
            bbox = f.getbbox("中")
            if bbox and (bbox[2] - bbox[0]) >= _MIN_CJK_WIDTH:
                logger.info("Resolved title font: %s", path)
                return path
        except Exception:
            continue

    return None


def _draw_title_on_image(
    image_path: str,
    output_path: str,
    title_text: str,
    title_config: dict,
    target_size: tuple[int, int],
) -> str:
    """Load an image, optionally draw a title overlay, and save.

    Args:
        image_path: Source image path.
        output_path: Where to save the processed image.
        title_text: Title text to overlay.
        title_config: Dict with font_path, font_size, position, color, etc.
        target_size: (width, height) of the output video frame.

    Returns:
        Path to the processed image.
    """
    target_w, target_h = target_size
    bg_pil = Image.open(image_path).convert("RGBA")
    img_w, img_h = bg_pil.size
    scale = max(target_w / img_w, target_h / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    bg_pil = bg_pil.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    bg_pil = bg_pil.crop((left, top, left + target_w, top + target_h))

    if title_text:
        _draw_title(bg_pil, title_text, title_config, target_w, target_h)

    bg_pil = bg_pil.convert("RGB")
    bg_pil.save(output_path, "PNG")
    return output_path


def _draw_title(
    bg: Image.Image,
    title: str,
    title_config: dict,
    target_w: int,
    target_h: int,
) -> bool:
    """Draw title overlay onto bg (mutates in-place)."""
    font_path = _resolve_font(title_config.get("font_path"))
    if font_path is None:
        logger.warning("Title overlay SKIPPED — no CJK font found.")
        return False

    font_size = title_config.get("font_size")
    if font_size is None:
        font_size = max(16, int(target_h * 0.06))

    color = title_config.get("color", "white")
    stroke_color = title_config.get("stroke_color", "black")
    stroke_width = title_config.get("stroke_width", 2)
    position = title_config.get("position", "bottom")

    if position == "bottom":
        y_pos = int(target_h * 0.88)
    elif position == "top":
        y_pos = int(target_h * 0.04)
    else:
        y_pos = target_h // 2

    overlay_text = str(title)
    logger.info("Adding title overlay: %s (font_size=%d, y=%d)",
                overlay_text, font_size, y_pos)

    try:
        font_obj = ImageFont.truetype(font_path, font_size)
    except Exception as exc:
        logger.warning("Failed to load font: %s; skipping title.", exc)
        return False

    bbox = font_obj.getbbox(overlay_text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad = stroke_width + 4
    canvas_w = text_w + pad * 2
    canvas_h = int((text_h + pad * 2) * 1.2)

    overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if stroke_width > 0 and stroke_color:
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                if dx * dx + dy * dy <= stroke_width * stroke_width:
                    draw.text((pad + dx, pad + dy), overlay_text, font=font_obj, fill=stroke_color)
    draw.text((pad, pad), overlay_text, font=font_obj, fill=color)

    x = (target_w - canvas_w) // 2
    y = y_pos - canvas_h // 2
    bg.paste(overlay, (x, y), overlay)
    return True


def _get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise ValueError(f"ffprobe failed on {audio_path}: {result.stderr.strip()[:200]}")
    try:
        return float(result.stdout.strip())
    except ValueError:
        raise ValueError(f"Cannot parse audio duration from ffprobe output: {result.stdout!r}")


def _verify_mp4(path: str) -> tuple[bool, str]:
    """Verify MP4 file has video + audio streams."""
    if not os.path.isfile(path):
        return False, "File does not exist"
    if os.path.getsize(path) == 0:
        return False, "File is empty"

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "stream=codec_type,codec_name",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return False, f"ffprobe error: {result.stderr.strip()[:200]}"
        streams = [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
        has_video = any("video" in s for s in streams)
        has_audio = any("audio" in s for s in streams)
        details = f"{len(streams)} stream(s): {', '.join(streams)}"
        if not has_video:
            return False, f"No video stream — {details}"
        if not has_audio:
            return False, f"No audio stream — {details}"
        return True, details
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return True, "unverified (ffprobe unavailable)"


def _build_zoompan_filter(
    target_w: int,
    target_h: int,
    display_duration: float,
    fps: int,
    image_index: int,
    zoom: float = 0.03,
    pan: str = "random",
) -> str:
    """Build a zoompan filter string for Ken Burns effect on one image.

    Creates a slow zoom-in with optional pan, making static wallpapers
    feel dynamic. Returns a filter string like:
      zoompan=z='...':x='...':y='...':d=120:s=1080x1920:fps=24

    Args:
        target_w: Output width.
        target_h: Output height.
        display_duration: How long this image appears (seconds).
        fps: Output frame rate.
        image_index: Used to seed random pan direction (deterministic per image).
        zoom: Zoom amount (0.03 = 3% zoom-in over the duration).
        pan: Direction — "random", "none", "left", "right", "up", "down".

    Returns:
        Full zoompan filter string.
    """
    n_frames = int(display_duration * fps)
    if n_frames <= 1:
        n_frames = 2  # avoid division by zero

    # Resolve pan direction
    if pan == "random":
        dirs = ["left", "right", "up", "down", "none"]
        rng = random.Random(image_index)
        pan = rng.choice(dirs)

    pan_frac = 0.02  # 2% of image dimension

    # Expression: linearly interpolate zoom from 1.0 to 1.0+zoom
    z_expr = f"1.0+{zoom}*(on-1)/({n_frames}-1)"

    # Expression: optional pan
    if pan == "none":
        x_expr, y_expr = "iw/2", "ih/2"
    elif pan == "left":
        x_expr = f"iw/2-{pan_frac}*iw*(on-1)/({n_frames}-1)"
        y_expr = "ih/2"
    elif pan == "right":
        x_expr = f"iw/2+{pan_frac}*iw*(on-1)/({n_frames}-1)"
        y_expr = "ih/2"
    elif pan == "up":
        x_expr = "iw/2"
        y_expr = f"ih/2-{pan_frac}*ih*(on-1)/({n_frames}-1)"
    elif pan == "down":
        x_expr = "iw/2"
        y_expr = f"ih/2+{pan_frac}*ih*(on-1)/({n_frames}-1)"
    else:
        x_expr, y_expr = "iw/2", "ih/2"

    return (
        f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':"
        f"d={n_frames}:s={target_w}x{target_h}:fps={fps}"
    )


def _build_watermark_filter(
    font_path: str | None,
    watermark_config: dict | None,
    target_w: int,
    target_h: int,
) -> str | None:
    """Build a drawtext filter string for watermark overlay.

    Returns a filter string fragment, or None if watermark is disabled
    or no font is available.

    Example output:
      drawtext=text='精选壁纸《1234》':fontfile=/path/to/font.ttf:...
    """
    if not watermark_config or not watermark_config.get("enabled", False):
        return None

    if font_path is None:
        font_path = _resolve_font(None)
        if font_path is None:
            logger.warning("Watermark SKIPPED — no CJK font available for drawtext.")
            return None

    # Resolve text
    template = watermark_config.get("template", "精选壁纸《{id}》")
    wm_id = watermark_config.get("id", "")
    text = template.replace("{id}", wm_id)
    if not text.strip():
        return None

    font_size = watermark_config.get("font_size", 32)
    color_raw = watermark_config.get("color", "white@0.6")
    stroke_color_raw = watermark_config.get("stroke_color", "black@0.8")
    stroke_width = watermark_config.get("stroke_width", 1.5)
    margin = watermark_config.get("margin", 30)
    position = watermark_config.get("position", "bottom-right")

    # Parse color:alpha format (e.g. "white@0.6")
    def _parse_color(val: str) -> str:
        if "@" in val:
            parts = val.split("@")
            return f"{parts[0]}@{parts[1]}"
        return val

    color = _parse_color(color_raw)
    stroke_color = _parse_color(stroke_color_raw)

    # Position
    pos_map = {
        "bottom-right": f"x=W-tw-{margin}:y=H-th-{margin}",
        "bottom-left": f"x={margin}:y=H-th-{margin}",
        "top-right": f"x=W-tw-{margin}:y={margin}",
        "top-left": f"x={margin}:y={margin}",
        "center": "x=(W-tw)/2:y=(H-th)/2",
        "bottom": f"x=(W-tw)/2:y=H-th-{margin}",
        "top": f"x=(W-tw)/2:y={margin}",
    }
    pos_str = pos_map.get(position, pos_map["bottom-right"])

    return (
        f"drawtext=text='{text}':"
        f"fontfile={font_path}:"
        f"fontsize={font_size}:"
        f"fontcolor={color}:"
        f"borderw={stroke_width}:"
        f"bordercolor={stroke_color}:"
        f"{pos_str}:"
        f"box=0"
    )


def compose_slideshow(
    image_paths: list[str],
    audio_path: str,
    output_path: str,
    target_size: tuple[int, int] = (1080, 1920),
    title: str | None = None,
    title_config: dict | None = None,
    transition_style: str = "fade",
    transition_duration: float = 1.0,
    fps: int = 24,
    crf: int = 23,
    preset: str = "veryfast",
    image_duration: float = 0,
    volume: float = 1.0,
    ken_burns_config: dict | None = None,
    watermark_config: dict | None = None,
) -> str:
    """Create a video slideshow from multiple images with transitions.

    Images are processed (scaled + cropped to target, optional title overlay)
    and then stitched together with FFmpeg xfade transitions. The total video
    duration matches the audio track.

    Args:
        image_paths: List of paths to input images.
        audio_path: Path to the audio file (MP3/WAV).
        output_path: Output MP4 path.
        target_size: (width, height) of the output video.
        title: Optional title for overlay text.
        title_config: Dict with font_path, font_size, position, color, etc.
        transition_style: FFmpeg xfade transition name (fade, slideleft, etc.)
        transition_duration: Duration of each transition in seconds.
        fps: Output frame rate.
        crf: H.264 CRV value (lower = better quality).
        preset: x264 preset.
        image_duration: Seconds per image. 0 = auto-calculate from audio.
        volume: Background music volume (0.0~1.0).
        ken_burns_config: Dict with enabled, zoom, pan keys for Ken Burns effect.
        watermark_config: Dict with enabled, template, id, font_size, position, etc.

    Returns:
        Path to the generated video file.

    Raises:
        ValueError: If no images or audio provided.
        RuntimeError: If FFmpeg fails or is not installed.
    """
    if not image_paths:
        raise ValueError("At least one image is required")
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    num_images = len(image_paths)
    audio_duration = _get_audio_duration(audio_path)
    logger.info("Audio duration: %.2f s", audio_duration)

    if audio_duration <= 0:
        raise ValueError(f"Audio has invalid duration ({audio_duration}s)")

    # Calculate display duration per image
    if image_duration <= 0:
        # Auto-calculate: (audio_duration - (num_images - 1) * transition_duration) / num_images
        total_overlap = (num_images - 1) * transition_duration
        if total_overlap >= audio_duration:
            logger.warning(
                "Transition overlap (%f s) >= audio duration (%f s). "
                "Reducing transition_duration.",
                total_overlap, audio_duration,
            )
            transition_duration = audio_duration / (num_images + 1) * 0.5
            total_overlap = (num_images - 1) * transition_duration
        display_duration = (audio_duration - total_overlap) / num_images
        logger.info(
            "Auto-calculated: display_duration=%.2fs (N=%d, audio=%.2fs, overlap=%.2fs)",
            display_duration, num_images, audio_duration, total_overlap,
        )
    else:
        display_duration = image_duration
        expected = num_images * display_duration - (num_images - 1) * transition_duration
        logger.info(
            "Fixed image_duration=%.2fs (expected total=%.2fs, audio=%.2fs)",
            display_duration, expected, audio_duration,
        )

    target_w, target_h = target_size

    # Normalize transition style
    style = _TRANSITION_STYLES.get(transition_style, transition_style)

    # Prepare a temp directory for processed images (with title overlay)
    tmp_dir = tempfile.mkdtemp(prefix="slideshow_")
    processed_images: list[str] = []

    try:
        # Process each image: scale + center-crop + optional title
        for idx, img_path in enumerate(image_paths):
            if not os.path.isfile(img_path):
                raise FileNotFoundError(f"Image not found: {img_path}")

            # Generate title overlay for each image
            if title and title_config:
                img_title = f"{title}"  # Could also do f"{title} - {idx+1}" for sequential variety
            else:
                img_title = ""

            processed_path = os.path.join(tmp_dir, f"img_{idx:02d}.png")
            _draw_title_on_image(img_path, processed_path, img_title, title_config or {}, target_size)
            processed_images.append(processed_path)
            logger.info("Processed image %d/%d: %s", idx + 1, num_images, img_path)

        # Build the FFmpeg filter_complex for slideshow with xfade
        # Each image is an input, looped for display_duration seconds
        filter_parts: list[str] = []
        input_parts: list[str] = []
        extra_map: list[str] = []

        # Determine whether to apply Ken Burns zoom/pan effect
        kb_enabled = ken_burns_config and ken_burns_config.get("enabled", False)
        kb_zoom = (ken_burns_config or {}).get("zoom", 0.03) if kb_enabled else 0

        for i in range(num_images):
            if kb_enabled and kb_zoom > 0:
                # Single-frame input + zoompan for Ken Burns effect
                input_parts.extend(["-i", processed_images[i]])
                zp = _build_zoompan_filter(
                    target_w, target_h, display_duration, fps, i,
                    zoom=kb_zoom,
                    pan=(ken_burns_config or {}).get("pan", "random"),
                )
                filter_parts.append(f"[{i}:v]{zp},format=rgba[label_v{i}]")
            else:
                # Looped input (static image)
                input_parts.extend(["-loop", "1", "-t", str(display_duration), "-i", processed_images[i]])
                filter_parts.append(f"[{i}:v]setpts=PTS-STARTPTS,format=rgba[label_v{i}]")

        # Chain xfade transitions between consecutive images
        if num_images == 1:
            final_label = "label_v0"
        else:
            current_label = "label_v0"
            for i in range(1, num_images):
                next_label = f"label_v{i}"
                xfade_offset = i * (display_duration - transition_duration)
                result_label = f"xf{i}" if i < num_images - 1 else "xfaded"
                filter_parts.append(
                    f"[{current_label}][{next_label}]xfade=transition={style}:duration={transition_duration}:offset={xfade_offset}[{result_label}]"
                )
                current_label = result_label
            final_label = "xfaded"

        # Apply watermark (drawtext) on the final video stream
        wm_filter_str = _build_watermark_filter(
            _resolve_font(title_config.get("font_path") if title_config else None),
            watermark_config,
            target_w,
            target_h,
        )
        if wm_filter_str:
            logger.info("Adding watermark overlay")
            filter_parts.append(
                f"[{final_label}]format=yuv420p,{wm_filter_str}[video]"
            )
        else:
            filter_parts.append(
                f"[{final_label}]format=yuv420p[video]"
            )

        filter_complex = "; ".join(filter_parts)

        # Build the FFmpeg command
        cmd = [
            "ffmpeg", "-y",
            *input_parts,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "[video]",
            "-map", f"{num_images}:a",
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", str(crf),
            "-c:a", "aac",
            "-b:a", "192k",
        ]

        # Apply volume filter if not 1.0
        if abs(volume - 1.0) > 0.01:
            cmd.extend(["-af", f"volume={volume}"])

        cmd.extend([
            "-shortest",
            "-movflags", "+faststart",
            "-max_muxing_queue_size", "1024",
            output_path,
        ])

        logger.info("Encoding video with %d images and '%s' transitions ...",
                     num_images, style)
        logger.debug("ffmpeg command: %s", " ".join(cmd))

        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)

        output_size = os.path.getsize(output_path)
        logger.info("Output file size: %d bytes", output_size)

        # Verify output
        is_valid, details = _verify_mp4(output_path)
        if not is_valid:
            raise ValueError(f"Generated video is not playable: {details}")
        logger.info("Video verification passed: %s", details)

        return output_path

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip()[:500] if e.stderr else str(e)
        raise RuntimeError(f"ffmpeg failed (exit code {e.returncode}): {error_msg}") from e
    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg is not installed. Install it with: sudo apt install ffmpeg"
        ) from None
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg timed out (600s).") from None
    finally:
        # Clean up temp images
        for p in processed_images:
            if os.path.isfile(p):
                os.unlink(p)
        if os.path.isdir(tmp_dir):
            os.rmdir(tmp_dir)
