"""Video composer — creates a slideshow video from multiple images.

Follows the two-pass approach from ai-music:
  Pass 1: Encode pre-processed images via ffmpeg image2 demuxer → silent video
  Pass 2: Mux audio via stream copy (or re-encode if volume adjustment needed)

No xfade transitions — simple hard cuts between images. No Ken Burns zoompan.
Watermark and title overlays are drawn onto each image via PIL before encoding.
"""

import glob
import logging
import os
import shutil
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
        height_based = int(target_h * 0.04)
        max_by_width = int(target_w * 0.85 / max(1, len(str(title))))
        font_size = max(24, min(height_based, max_by_width))

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


def _draw_watermark(
    bg: Image.Image,
    watermark_config: dict | None,
    target_w: int,
    target_h: int,
) -> bool:
    """Draw watermark text onto bg via PIL (mutates in-place).

    Supports the same config options as the old `_build_watermark_filter()`
    but draws directly via PIL instead of using ffmpeg drawtext, eliminating
    the need for font file resolution in the ffmpeg command.

    Args:
        bg: RGBA image to draw on.
        watermark_config: Dict with enabled, template, id, font_size,
                          position, color, stroke_color, stroke_width, margin.
        target_w: Target video width.
        target_h: Target video height.

    Returns:
        True if watermark was drawn, False if skipped.
    """
    if not watermark_config or not watermark_config.get("enabled", False):
        return False

    font_path = _resolve_font(None)
    if font_path is None:
        logger.warning("Watermark SKIPPED — no CJK font available.")
        return False

    # Resolve text
    template = watermark_config.get("template", "精选壁纸《{id}》")
    wm_id = watermark_config.get("id", "")
    text = template.replace("{id}", wm_id)
    if not text.strip():
        return False

    font_size = watermark_config.get("font_size")
    if font_size is None:
        font_size = max(22, int(target_h * 0.025))
    stroke_width_wm = watermark_config.get("stroke_width", 1.5)
    margin = watermark_config.get("margin", 30)
    position = watermark_config.get("position", "bottom-right")
    color_raw = watermark_config.get("color", "white@0.6")
    stroke_color_raw = watermark_config.get("stroke_color", "black@0.8")

    # Parse "color@alpha" format (e.g. "white@0.6")
    def _parse_color(val: str) -> tuple[int, int, int, int]:
        if "@" in val:
            parts = val.split("@")
            name = parts[0]
            alpha = max(0, min(255, int(float(parts[1]) * 255)))
        else:
            name = val
            alpha = 255
        rgb_map = {
            "white": (255, 255, 255),
            "black": (0, 0, 0),
            "yellow": (255, 255, 0),
            "red": (255, 0, 0),
            "blue": (0, 0, 255),
            "green": (0, 255, 0),
        }
        r, g, b = rgb_map.get(name, (255, 255, 255))
        return (r, g, b, alpha)

    color = _parse_color(color_raw)
    stroke_color_pil = _parse_color(stroke_color_raw)

    try:
        font_obj = ImageFont.truetype(font_path, font_size)
    except Exception as exc:
        logger.warning("Failed to load font for watermark: %s", exc)
        return False

    # Measure text
    bbox = font_obj.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    sw = max(1, int(stroke_width_wm))
    pad = sw + 4
    canvas_w = text_w + pad * 2
    canvas_h = int((text_h + pad * 2) * 1.2)

    # ── Overflow guard: shrink font if watermark is too wide ──
    max_wm_width = target_w - margin * 2
    if canvas_w > max_wm_width:
        scale = max_wm_width / canvas_w
        new_font_size = max(16, int(font_size * scale))
        try:
            font_obj = ImageFont.truetype(font_path, new_font_size)
            bbox = font_obj.getbbox(text)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            canvas_w = text_w + pad * 2
            canvas_h = int((text_h + pad * 2) * 1.2)
        except Exception:
            pass

    # Render text on transparent canvas
    overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if sw > 0:
        for dx in range(-sw, sw + 1):
            for dy in range(-sw, sw + 1):
                if dx * dx + dy * dy <= sw * sw:
                    draw.text((pad + dx, pad + dy), text, font=font_obj, fill=stroke_color_pil)
    draw.text((pad, pad), text, font=font_obj, fill=color)

    # Position
    pos_map = {
        "bottom-right": (target_w - canvas_w - margin, target_h - canvas_h - margin),
        "bottom-left": (margin, target_h - canvas_h - margin),
        "top-right": (target_w - canvas_w - margin, margin),
        "top-left": (margin, margin),
        "center": ((target_w - canvas_w) // 2, (target_h - canvas_h) // 2),
        "bottom": ((target_w - canvas_w) // 2, target_h - canvas_h - margin),
        "top": ((target_w - canvas_w) // 2, margin),
    }
    x, y = pos_map.get(position, pos_map["bottom-right"])

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
    """Create a video slideshow from multiple images with hard cuts.

    Follows the ai-music two-pass approach:
      Pass 1 — Encode pre-processed PNGs via ffmpeg image2 demuxer
               into a silent video (with `-preset veryfast` and `-tune stillimage`).
      Pass 2 — Mux audio via stream copy (or re-encode if volume adjustment needed).

    Args:
        image_paths: List of paths to input images.
        audio_path: Path to the audio file (MP3/WAV).
        output_path: Output MP4 path.
        target_size: (width, height) of the output video.
        title: Optional title for overlay text.
        title_config: Dict with font_path, font_size, position, color, etc.
        transition_style: IGNORED (kept for API compatibility).
        transition_duration: IGNORED (kept for API compatibility).
        fps: Output video frame rate.
        crf: H.264 CRF value (lower = better quality).
        preset: IGNORED (pass 1 always uses ``veryfast``).
        image_duration: Seconds per image. 0 = auto-calculate from audio.
        volume: Background music volume (0.0~1.0).
        ken_burns_config: IGNORED (kept for API compatibility).
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

    # Calculate per-image display duration (simple division, no transitions)
    if image_duration > 0:
        display_duration = image_duration
        logger.info("Fixed image_duration=%.2fs", display_duration)
    else:
        display_duration = audio_duration / num_images
        logger.info(
            "Auto-calculated: display_duration=%.2fs (N=%d, audio=%.2fs)",
            display_duration, num_images, audio_duration,
        )

    target_w, target_h = target_size
    tmp_dir = tempfile.mkdtemp(prefix="slideshow_")
    processed_images: list[str] = []

    try:
        # ── Phase 1: Prepare images (PIL: scale + crop + title + watermark) ──
        for idx, img_path in enumerate(image_paths):
            if not os.path.isfile(img_path):
                raise FileNotFoundError(f"Image not found: {img_path}")

            img_title = str(title) if title and title_config else ""
            processed_path = os.path.join(tmp_dir, f"img_{idx:02d}.png")

            # Load, scale to fill, centre-crop
            bg_pil = Image.open(img_path).convert("RGBA")
            img_w, img_h = bg_pil.size
            scale = max(target_w / img_w, target_h / img_h)
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            bg_pil = bg_pil.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - target_w) // 2
            top = (new_h - target_h) // 2
            bg_pil = bg_pil.crop((left, top, left + target_w, top + target_h))

            # Draw title overlay (if configured)
            if img_title:
                _draw_title(bg_pil, img_title, title_config, target_w, target_h)

            # Draw watermark overlay (if configured)
            _draw_watermark(bg_pil, watermark_config, target_w, target_h)

            bg_pil = bg_pil.convert("RGB")
            bg_pil.save(processed_path, "PNG")
            processed_images.append(processed_path)
            logger.info("Processed image %d/%d: %s", idx + 1, num_images, img_path)

        # ── Phase 2 / Pass 1: Encode images → silent video ───────────────
        # Use the image2 demuxer with -framerate to set per-image duration.
        # Example: -framerate 1/3.5 = each image lasts 3.5 seconds.
        # This is the documented ffmpeg approach for still-image slideshows
        # and avoids the platform-dependent concat demuxer behavior with PNGs.
        input_pattern = os.path.join(tmp_dir, "img_%02d.png")
        silent_path = output_path + ".silent.mp4"

        cmd1 = [
            "ffmpeg", "-y",
            "-framerate", f"1/{display_duration}",
            "-start_number", "0",
            "-i", input_pattern,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-tune", "stillimage",
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-an",
            "-threads", "2",
            silent_path,
        ]
        logger.info(
            "Pass 1: Encoding silent slideshow (%d images at %.2f s each, "
            "%d fps, %dx%d)",
            num_images, display_duration, fps, target_w, target_h,
        )
        subprocess.run(cmd1, check=True, capture_output=True, text=True, timeout=600)

        s1_size = os.path.getsize(silent_path)
        logger.info("Pass 1 done: %s (%d bytes)", silent_path, s1_size)

        # ── Pass 2: Mux audio via stream copy (or re-encode if volume ≠ 1) ─
        cmd2 = [
            "ffmpeg", "-y",
            "-i", silent_path,
            "-i", audio_path,
            "-c", "copy",
            "-movflags", "+faststart",
            output_path,
        ]
        if abs(volume - 1.0) > 0.01:
            cmd2 = [
                "ffmpeg", "-y",
                "-i", silent_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-af", f"volume={volume}",
                "-movflags", "+faststart",
                output_path,
            ]
        logger.info("Pass 2: Muxing audio (volume=%.2f)", volume)
        subprocess.run(cmd2, check=True, capture_output=True, text=True, timeout=120)

        output_size = os.path.getsize(output_path)
        logger.info("Output: %s (%d bytes)", output_path, output_size)

        # ── Verify ─────────────────────────────────────────────────────────
        is_valid, details = _verify_mp4(output_path)
        if not is_valid:
            raise ValueError(f"Generated video is not playable: {details}")
        logger.info("Video verification passed: %s", details)

        return output_path

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip()[:2000] if e.stderr else str(e)
        if e.stderr and len(e.stderr) > 2000:
            logger.debug("Full ffmpeg stderr:\n%s", e.stderr)
        raise RuntimeError(f"ffmpeg failed (exit code {e.returncode}): {error_msg}") from e
    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg is not installed. Install it with: sudo apt install ffmpeg"
        ) from None
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg timed out (600s).") from None
    finally:
        # Clean up temp images and silent intermediate
        for p in processed_images:
            if os.path.isfile(p):
                os.unlink(p)
        silent_p = output_path + ".silent.mp4"
        if os.path.isfile(silent_p):
            os.unlink(silent_p)
        # Remove stale concat_list.txt (pre-image2 versions)
        _stale = os.path.join(tmp_dir, "concat_list.txt")
        if os.path.isfile(_stale):
            os.unlink(_stale)
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
