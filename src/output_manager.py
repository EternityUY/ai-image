"""Output manager — create timestamped output folders and write info.txt."""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


def _slug(text: str, max_len: int = 30) -> str:
    """Create a short filesystem-safe slug from text."""
    cleaned = re.sub(r"[^\w一-鿿\-]", "_", text)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip("_")
    return cleaned or "generated"


def create_output_folder(theme: str, output_dir: str | None = None) -> str:
    """Create a timestamped output folder and return its path.

    Folder name: YYYY-MM-DD_HH-MM-SS_<theme-slug>
    """
    base = Path(output_dir or _OUTPUT_DIR)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    slug = _slug(theme)
    folder_name = f"{timestamp}_{slug}"
    folder_path = base / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)
    return str(folder_path)


def write_info_file(folder_path: str, info: dict[str, Any]) -> str:
    """Write info.txt into the output folder with generation metadata."""
    lines = [
        "=" * 40,
        "  AI Image Video - Generation Info",
        "=" * 40,
        "",
        f"主题 (Theme):     {info.get('theme', 'N/A')}",
        f"图片风格:         {info.get('image_style', 'N/A')}",
        f"图片数量:         {info.get('image_count', 'N/A')}",
        f"图片模型:         {info.get('image_model', 'N/A')}",
        f"音乐文件:         {info.get('music_file', 'N/A')}",
        f"转场效果:         {info.get('transition_style', 'N/A')}",
        f"转场时长:         {info.get('transition_duration', 'N/A')}",
        f"视频比例:         {info.get('video_aspect_ratio', '9:16')}",
        f"视频分辨率:       {info.get('video_resolution', 'N/A')}",
        f"视频时长:         {info.get('video_duration', 'N/A')}",
        f"标题水印:         {'是' if info.get('title_overlay') else '否'}",
        f"生成时间:         {info.get('created_at', 'N/A')}",
        "",
        "-" * 40,
        "  图片提示词",
        "-" * 40,
        "",
    ]

    prompts = info.get("image_prompts", [])
    for i, prompt in enumerate(prompts):
        lines.append(f"  Image {i + 1}: {prompt}")
    lines.append("")

    if info.get("lyrics"):
        lines.extend([
            "-" * 40,
            "  描述/歌词",
            "-" * 40,
            "",
            info.get("lyrics", ""),
            "",
        ])

    lines.extend([
        "-" * 40,
        "  文件清单",
        "-" * 40,
        "",
    ])

    lines.append(f"  {info.get('video_file', 'video.mp4')}      - 合成视频")
    for fname in info.get("image_files", []):
        lines.append(f"  {fname}    - 生成图片")
    lines.append(f"  {info.get('music_file', '')}    - 配乐文件")

    lines.extend([
        "",
        "=" * 40,
    ])

    info_path = os.path.join(folder_path, "info.txt")
    with open(info_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return info_path
