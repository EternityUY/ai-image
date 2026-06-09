"""Configuration loader — reads and validates config.json."""

import json
import os
from typing import Any

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

_DEFAULTS: dict[str, Any] = {
    "minmax": {
        "base_url": "https://api.minimaxi.com/v1",
    },
    "schedule": {
        "mode": "single",
        "daily_time": "02:00",
    },
    "generation": {
        "image_count": 4,
        "image_model": "image-01",
        "image_size": "1024x1024",
        "image_style": "水彩艺术插画",
        "extract_cover": True,
        "extract_cover_time": 3.0,
        "image_prompts": [
            "梦幻星空下的宁静湖面，水彩风格",
            "春日樱花飘落的街道，治愈系插画",
            "落日余晖洒在海面上，金色波浪",
            "森林深处的秘密花园，光影斑驳",
        ],
        "music_dir": "music",
        "video_aspect_ratio": "9:16",
        "title_overlay": True,
        "title_font_size": None,
        "title_position": "bottom",
        "title_font_path": "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "title_color": "white",
        "title_stroke_color": "black",
        "title_stroke_width": 2,
    },
    "video": {
        "fps": 24,
        "crf": 23,
        "preset": "veryfast",
        "transition": {
            "style": "fade",
            "duration": 1.0,
            "overlap": True,
        },
        "image_duration": 0,
        "background_music": {
            "volume": 0.8,
        },
    },
    "upload": {
        "enabled": False,
        "platform": "kuaishou",
        "cookies_path": "cookies",
        "video": {
            "title": "AI影像《{theme}》",
            "tags": "AI视频,AI生成,人工智能",
            "content": "AI自动生成的影像视频\n\n主题：{theme}\n\n#AI视频 #AI生成",
            "schedule": "",
        },
    },
    "cleanup": {
        "max_age_days": 7,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge override into base, mutating base."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(path: str | None = None) -> dict[str, Any]:
    """Load and validate config from JSON file, merged with defaults.

    Returns merged config dict. Raises FileNotFoundError or ValueError
    on missing file / invalid content.
    """
    cfg_path = path or _CONFIG_PATH
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(
            f"Config file not found: {cfg_path}. "
            f"Copy config.example.json to config.json and fill in your values."
        )

    with open(cfg_path, "r", encoding="utf-8") as f:
        try:
            user_cfg: dict = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {cfg_path}: {e}")

    if not isinstance(user_cfg, dict):
        raise ValueError(f"Config must be a JSON object, got {type(user_cfg).__name__}")

    cfg = _deep_merge(_DEFAULTS.copy(), user_cfg)

    # Validate — image prompts
    image_count = cfg.get("generation", {}).get("image_count", 4)
    prompts = cfg.get("generation", {}).get("image_prompts", [])
    if len(prompts) < image_count:
        raise ValueError(
            f"generation.image_prompts has {len(prompts)} item(s), "
            f"but image_count is {image_count}. Add more prompts."
        )

    # Validate — MiniMax API key (required if image generation is online)
    api_key = cfg.get("minmax", {}).get("api_key", "")
    if not api_key or api_key == "YOUR_MINIMAX_API_KEY":
        raise ValueError(
            "minmax.api_key is not set. Update config.json with your MiniMax API key."
        )

    # Validate — music directory
    music_dir = cfg.get("generation", {}).get("music_dir", "music")
    music_path = _resolve_music_dir(music_dir)
    if not os.path.isdir(music_path):
        raise ValueError(
            f"Music directory not found: {music_path}. "
            f"Please create it and add audio files (mp3/wav/flac/m4a)."
        )

    # Validate schedule mode
    mode = cfg.get("schedule", {}).get("mode", "single")
    if mode not in ("single", "daily"):
        raise ValueError(f"schedule.mode must be 'single' or 'daily', got '{mode}'")

    return cfg


def _resolve_music_dir(music_dir: str) -> str:
    """Resolve music directory path.

    If the path is relative, try resolving from project root first,
    then from the current working directory.
    """
    if os.path.isabs(music_dir):
        return music_dir
    project_root = os.path.dirname(os.path.dirname(__file__))
    candidate = os.path.join(project_root, music_dir)
    if os.path.isdir(candidate):
        return candidate
    return music_dir


_cache: dict | None = None


def get_config(path: str | None = None) -> dict[str, Any]:
    """Load config once and cache it."""
    global _cache
    if _cache is None or path is not None:
        _cache = load_config(path)
    return _cache
