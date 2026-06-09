"""Pipeline — orchestrates the full image-to-video workflow."""

import logging
import os
import shutil
from datetime import datetime

from src.cleanup import clean_old_folders
from src.config_loader import get_config
from src.image_generator import ImageGenerator
from src.music_selector import select_random_music
from src.output_manager import create_output_folder, write_info_file
from src.uploader import upload_video
from src.video_composer import compose_slideshow

logger = logging.getLogger(__name__)


def run_pipeline() -> dict:
    """Execute one full generation cycle.

    Steps:
        1. Clean up old output folders (> max_age_days).
        2. Generate N images via MiniMax Image API from config prompts.
        3. Randomly select background music from configured folder.
        4. Compose slideshow video with transitions, duration matching music.
        5. Save all files + info.txt into a timestamped folder.
        6. (Optional) Upload video to Kuaishou if enabled in config.

    Returns:
        Dict with keys: status, folder_path, video_path, image_count, theme,
        upload_result (if upload was attempted).
    """
    cfg = get_config()
    mm_cfg = cfg["minmax"]
    gen_cfg = cfg["generation"]
    video_cfg = cfg["video"]
    upload_cfg = cfg["upload"]

    # ------------------------------------------------------------------
    # Step 0: Cleanup old folders
    # ------------------------------------------------------------------
    logger.info("Step 0: Cleaning old output folders ...")
    clean_old_folders(cfg)

    # ------------------------------------------------------------------
    # Step 1: Determine generation parameters
    # ------------------------------------------------------------------
    image_count = gen_cfg.get("image_count", 4)
    prompts = gen_cfg.get("image_prompts", [])[:image_count]
    image_style = gen_cfg.get("image_style", "水彩艺术插画")
    video_aspect = gen_cfg.get("video_aspect_ratio", "9:16")

    _ASPECT_TO_RATIO = {
        "16:9": "16:9",
        "9:16": "9:16",
        "1:1": "1:1",
        "4:3": "4:3",
        "3:4": "3:4",
    }
    aspect_ratio = _ASPECT_TO_RATIO.get(video_aspect, "9:16")

    _ASPECT_TO_SIZE = {
        "16:9": (1920, 1080),
        "9:16": (1080, 1920),
    }
    target_size = _ASPECT_TO_SIZE.get(video_aspect, (1080, 1920))

    # Create output directory early to store generated images
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    # Use first prompt as theme for folder naming
    theme = prompts[0][:40] if prompts else "ai_image_video"
    folder_path = create_output_folder(theme, output_dir)

    image_dir = os.path.join(folder_path, "images")
    os.makedirs(image_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 2: Generate images via MiniMax
    # ------------------------------------------------------------------
    logger.info("Step 1: Generating %d images via MiniMax API ...", image_count)
    client = ImageGenerator(api_key=mm_cfg["api_key"], base_url=mm_cfg["base_url"])

    # Add style to prompts
    styled_prompts = [f"{p}。{image_style}风格" for p in prompts]

    image_paths = client.generate_images(
        prompts=styled_prompts,
        aspect_ratio=aspect_ratio,
        model=gen_cfg.get("image_model", "image-01"),
        output_dir=image_dir,
    )

    logger.info("Generated %d image(s) in: %s", len(image_paths), image_dir)

    # ------------------------------------------------------------------
    # Step 3: Select random background music
    # ------------------------------------------------------------------
    logger.info("Step 2: Selecting background music ...")
    music_dir = gen_cfg.get("music_dir", "music")
    if not os.path.isabs(music_dir):
        project_root = os.path.dirname(os.path.dirname(__file__))
        abs_music_dir = os.path.join(project_root, music_dir)
        if os.path.isdir(abs_music_dir):
            music_dir = abs_music_dir

    music_path = select_random_music(music_dir)
    # Copy music to output folder
    music_filename = os.path.basename(music_path)
    music_output_path = os.path.join(folder_path, music_filename)
    shutil.copy2(music_path, music_output_path)

    # ------------------------------------------------------------------
    # Step 4: Compose slideshow video
    # ------------------------------------------------------------------
    logger.info("Step 3: Composing slideshow video ...")
    video_path = os.path.join(folder_path, "video.mp4")

    transition_cfg = video_cfg.get("transition", {})
    transition_style = transition_cfg.get("style", "fade")
    transition_duration = transition_cfg.get("duration", 1.0)

    image_duration = video_cfg.get("image_duration", 0)
    bgm_volume = video_cfg.get("background_music", {}).get("volume", 1.0)

    # Ken Burns effect
    ken_burns_config = video_cfg.get("ken_burns", {"enabled": False})

    # Watermark
    watermark_config = gen_cfg.get("watermark", {"enabled": False})

    # Title overlay
    title_overlay = gen_cfg.get("title_overlay", True)
    title_text = theme if title_overlay else None

    compose_slideshow(
        image_paths=image_paths,
        audio_path=music_output_path,
        output_path=video_path,
        target_size=target_size,
        title=title_text,
        title_config={
            "font_path": gen_cfg.get("title_font_path"),
            "font_size": gen_cfg.get("title_font_size"),
            "position": gen_cfg.get("title_position", "bottom"),
            "color": gen_cfg.get("title_color", "white"),
            "stroke_color": gen_cfg.get("title_stroke_color", "black"),
            "stroke_width": gen_cfg.get("title_stroke_width", 2),
        },
        transition_style=transition_style,
        transition_duration=transition_duration,
        fps=video_cfg.get("fps", 24),
        crf=video_cfg.get("crf", 23),
        preset=video_cfg.get("preset", "veryfast"),
        image_duration=image_duration,
        volume=bgm_volume,
        ken_burns_config=ken_burns_config,
        watermark_config=watermark_config,
    )

    # ------------------------------------------------------------------
    # Step 5: Generate cover.jpg from first image
    # ------------------------------------------------------------------
    cover_jpg_path = None
    if gen_cfg.get("extract_cover", True) and image_paths:
        cover_jpg_path = os.path.join(folder_path, "cover.jpg")
        try:
            from src.video_composer import _draw_title_on_image

            _draw_title_on_image(
                image_paths[0],
                cover_jpg_path,
                title_text if title_overlay else "",
                {
                    "font_path": gen_cfg.get("title_font_path"),
                    "font_size": gen_cfg.get("title_font_size"),
                    "position": "center",
                    "color": gen_cfg.get("title_color", "white"),
                    "stroke_color": gen_cfg.get("title_stroke_color", "black"),
                    "stroke_width": gen_cfg.get("title_stroke_width", 2),
                },
                target_size,
            )
            logger.info("Cover generated: %s", cover_jpg_path)
        except Exception as exc:
            logger.warning("Failed to generate cover: %s", exc)
            cover_jpg_path = None

    # ------------------------------------------------------------------
    # Step 6: Write info.txt
    # ------------------------------------------------------------------
    logger.info("Step 5: Writing info.txt ...")
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Get video duration
    try:
        from src.video_composer import _get_audio_duration
        video_duration = _get_audio_duration(video_path)
        video_duration_str = f"{video_duration:.1f}s"
    except Exception:
        video_duration_str = "N/A"

    info = {
        "theme": theme,
        "image_style": image_style,
        "image_count": image_count,
        "image_model": gen_cfg.get("image_model", "image-01"),
        "image_prompts": prompts,
        "music_file": music_filename,
        "transition_style": transition_style,
        "transition_duration": f"{transition_duration}s",
        "video_aspect_ratio": video_aspect,
        "video_resolution": f"{target_size[0]}x{target_size[1]}",
        "video_duration": video_duration_str,
        "title_overlay": title_overlay,
        "ken_burns": video_cfg.get("ken_burns", {}).get("enabled", False),
        "watermark": gen_cfg.get("watermark", {}).get("enabled", False),
        "created_at": created_at,
        "video_file": "video.mp4",
        "image_files": [os.path.basename(p) for p in image_paths],
        "cover_file": "cover.jpg" if cover_jpg_path else None,
    }
    info_path = write_info_file(folder_path, info)

    logger.info("Pipeline complete! Output: %s", folder_path)

    result = {
        "status": "success",
        "folder_path": folder_path,
        "video_path": video_path,
        "info_txt_path": info_path,
        "theme": theme,
        "image_count": image_count,
    }

    # ------------------------------------------------------------------
    # Step 7: Upload
    # ------------------------------------------------------------------
    if upload_cfg.get("enabled", False):
        logger.info("Step 6: Uploading video ...")
        video_cfg_upload = upload_cfg.get("video", {})
        upload_title = video_cfg_upload.get("title", "AI影像").replace("{theme}", theme)
        upload_content = video_cfg_upload.get("content", "").replace("{theme}", theme)
        upload_tags = video_cfg_upload.get("tags", "")

        upload_result = upload_video(
            video_path=video_path,
            cover_path=cover_jpg_path,
            title=upload_title,
            content=upload_content,
            tags=upload_tags,
            upload_cfg=upload_cfg,
        )
        result["upload_result"] = upload_result
        if upload_result.get("success"):
            logger.info("Upload successful!")
        else:
            logger.warning("Upload skipped/failed: %s", upload_result.get("error"))
    else:
        logger.info("Step 6: Skipping upload (disabled in config).")

    return result
