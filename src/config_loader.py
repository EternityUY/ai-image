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
        "image_count": 5,
        "image_model": "image-01",
        "image_size": "1024x1024",
        "image_style": "高清壁纸，精细画质，超高细节，色彩鲜艳",
        "extract_cover": True,
        "extract_cover_time": 3.0,
        "image_prompts": [
            "梦幻极光下的雪山湖泊，4K壁纸，深邃蓝紫调",
            "落日余晖中的城市天际线，暖金色调，城市壁纸",
            "清晨森林里的阳光洒落，丁达尔效应，自然壁纸",
            "深空星系与星云，绚烂色彩，宇宙壁纸",
            "赛博朋克风格雨夜霓虹街景，紫蓝粉调，氛围壁纸",
            "水墨山水画风格的山谷云海，青绿基调，国风壁纸",
            "粉色樱花飘落在古风建筑前，春日氛围，治愈壁纸",
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
        # 水印配置
        "watermark": {
            "enabled": True,
            "template": "精选壁纸《{id}》",
            "id": "",
            "font_size": None,
            "position": "bottom-right",
            "color": "white@0.6",
            "stroke_color": "black@0.8",
            "stroke_width": 1.5,
            "margin": 30,
        },
    },
    "video": {
        "fps": 24,
        "crf": 23,
        "preset": "veryfast",
        "transition": {
            "style": "smoothleft",
            "duration": 1.2,
            "overlap": True,
        },
        "image_duration": 0,
        "background_music": {
            "volume": 0.8,
        },
        # Ken Burns 镜头推拉效果 — 让静态壁纸产生动态感
        "ken_burns": {
            "enabled": True,
            "zoom": 0.03,       # 整体缩放比例 (0.02~0.05 推荐)
            "pan": "random",    # 平移方向: none / random / left / right / up / down
        },
    },
    "upload": {
        "enabled": False,
        "platform": "kuaishou",
        "cookies_path": "cookies",
        "video": {
            "title": "精选壁纸《{theme}》",
            "tags": "精选壁纸,手机壁纸,4K壁纸,AI壁纸,高清壁纸,壁纸推荐",
            "content": "✨ 精选高清壁纸推荐 ✨\n\n主题：{theme}\n\n每一张都是精挑细选的高清壁纸，适合手机锁屏和桌面使用。\n每天更新优质壁纸，喜欢的话关注不迷路～\n\n#精选壁纸 #手机壁纸 #4K壁纸 #AI壁纸 #壁纸推荐",
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
