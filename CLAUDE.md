# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ai-image** — Automated AI image-to-video generation pipeline. Generates multiple images via MiniMax API using configurable prompts, randomly selects background music from a local folder, and composes them into a video slideshow with transitions (via FFmpeg xfade). Optionally uploads to Kuaishou via Spreado CLI.

Reference projects:
- [ai-music](https://github.com/EternityUY/ai-music) — single-image-to-video with Bilibili upload (architectural reference)
- [Spreado](https://github.com/BadKid90s/Spreado) — Playwright-based multi-platform video upload (used for Kuaishou upload)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Install Spreado for Kuaishou upload (optional, for upload feature)
pip install spreado

# Copy and edit config
cp config.example.json config.json
# Then edit config.json — fill in minmax.api_key and verify image_prompts

# Prepare music directory and add audio files
mkdir -p music
# Put .mp3/.wav/.flac/.m4a files in music/

# Login to Kuaishou (one-time, for upload feature)
spreado login kuaishou

# Run the pipeline
python3 src/main.py
```

## Common Commands

```bash
# Run the pipeline (single mode)
python3 src/main.py

# Import check
python3 -c "from src.config_loader import get_config; from src.image_generator import ImageGenerator; from src.music_selector import select_random_music; from src.video_composer import compose_slideshow; from src.output_manager import create_output_folder, write_info_file; from src.uploader import upload_video; from src.cleanup import clean_old_folders; print('OK')"

# Lint
pip install ruff && ruff check src/
```

## Project Structure

```
├── config.json                 # User config (gitignored) — API key, prompts, video params
├── config.example.json         # Config template with full documentation
├── requirements.txt            # Python deps: requests, schedule, Pillow
├── music/                      # Music directory — user puts .mp3/.wav here
├── cookies/                    # Spreado cookies (gitignored)
├── .gitignore
├── src/
│   ├── main.py                 # Entry point — dispatches single or daily mode
│   ├── config_loader.py        # Loads & validates config.json, merges defaults
│   ├── image_generator.py      # MiniMax Image API — generates N images from prompts
│   ├── music_selector.py       # Randomly selects audio file from music dir
│   ├── video_composer.py       # FFmpeg slideshow: multiple images + transitions + audio
│   ├── pipeline.py             # Orchestrates the full workflow (7 steps)
│   ├── output_manager.py       # Creates timestamp output folders, writes info.txt
│   ├── uploader.py             # Kuaishou upload via Spreado CLI
│   └── cleanup.py              # Deletes output folders older than max_age_days
├── output/                     # Generated videos, images, info files (gitignored)
└── CLAUDE.md
```

## Pipeline Flow (src/pipeline.py)

1. **Cleanup** — `cleanup.py` removes output folders older than `cleanup.max_age_days`
2. **Image Generation** — `image_generator.py` calls MiniMax Image API for each prompt in `generation.image_prompts` (up to `generation.image_count` images). Each prompt is augmented with the configured `image_style`.
3. **Music Selection** — `music_selector.py` randomly picks an audio file from `generation.music_dir`
4. **Video Composition** — `video_composer.py` uses FFmpeg xfade filter to create a slideshow:
   - Each image is scaled + center-cropped to target resolution
   - Optional title overlay rendered via Pillow on each frame
   - Transitions between images (configurable: fade, slide, dissolve, etc.)
   - Total duration auto-matched to audio track length
5. **Cover** — Generates `cover.jpg` from the first image with centered title
6. **Output** — `output_manager.py` saves everything into `output/YYYY-MM-DD_HH-MM-SS_<slug>/` with `info.txt`
7. **Upload** (optional) — `uploader.py` calls `spreado upload kuaishou` CLI to publish video

## Configuration (config.json)

### Generation
| Field | Type | Default | Description |
|---|---|---|---|
| `minmax.api_key` | string | — | **(必填)** MiniMax API key |
| `generation.image_count` | int | `4` | 生成图片数量 (3-5 recommended) |
| `generation.image_prompts` | string[] | — | 图片提示词列表，数量 >= image_count |
| `generation.image_model` | string | `image-01` | MiniMax 图片模型 |
| `generation.image_style` | string | `水彩艺术插画` | 图片艺术风格（追加到每个提示词后） |
| `generation.image_size` | string | `1024x1024` | 图片尺寸 (用于API请求) |
| `generation.music_dir` | string | `music` | 配乐文件夹路径 |
| `generation.video_aspect_ratio` | string | `9:16` | 视频比例 (`16:9` / `9:16`) |

### Video Transitions
| Field | Type | Default | Description |
|---|---|---|---|
| `video.transition.style` | string | `fade` | 转场效果: `fade`, `fadeblack`, `fadewhite`, `dissolve`, `slideleft`, `slideright`, `slideup`, `slidedown`, `smoothleft`, `smoothright`, `circleopen`, `circleclose`, `pixelize`, `radial`, `hblur`, `wipe`, `zoomin` 等 |
| `video.transition.duration` | float | `1.0` | 转场时长（秒） |
| `video.fps` | int | `24` | 视频帧率 |
| `video.crf` | int | `23` | H.264 CRF (18-28, 越小质量越好) |
| `video.preset` | string | `veryfast` | x264 preset (ultrafast/superfast/veryfast/faster/fast/medium) |
| `video.image_duration` | float | `0` | 每张图片展示时长(秒)。0 = 自动按音乐时长均分 |
| `video.background_music.volume` | float | `1.0` | 背景音乐音量 (0.0~1.0) |

### Upload (Kuaishou via Spreado)
| Field | Type | Default | Description |
|---|---|---|---|
| `upload.enabled` | bool | `false` | 是否启用自动上传到快手 |
| `upload.platform` | string | `kuaishou` | 上传平台 (当前仅支持 kuaishou) |
| `upload.cookies_path` | string | `cookies` | Spreado cookie 目录 |
| `upload.video.title` | string | `AI影像《{theme}》` | 视频标题，支持 `{theme}` 变量 |
| `upload.video.tags` | string | — | 逗号分隔的标签 |
| `upload.video.content` | string | — | 视频描述，支持 `{theme}` 变量 |

### Transitions Reference
Available FFmpeg xfade transition styles: `fade`, `fadeblack`, `fadewhite`, `dissolve`, `slideleft`, `slideright`, `slideup`, `slidedown`, `smoothleft`, `smoothright`, `smoothup`, `smoothdown`, `circleopen`, `circleclose`, `rectopen`, `rectclose`, `pixelize`, `radial`, `hblur`, `wipetl`, `wipe`, `zoomin`, `hlslice`

## Upload Setup (Kuaishou)

This project uses [Spreado](https://github.com/BadKid90s/Spreado) for Kuaishou upload:

```bash
# 1. Install Spreado
pip install spreado

# 2. Login to Kuaishou (one-time, interactive browser)
spreado login kuaishou

# 3. Verify login status
spreado verify kuaishou

# 4. Enable upload in config.json
# "upload": { "enabled": true, "platform": "kuaishou" }
```

Requirements for Spreado: Playwright with browser support (auto-detects Chrome/Edge, or falls back to Playwright Chromium).

## Scheduling

- **`"single"` mode** (default): Runs the pipeline once, then exits.
- **`"daily"` mode**: Runs once on startup, then schedules at `schedule.daily_time` via the `schedule` library.

## Dependencies

- **Python 3.9+**
- **MiniMax API** — Image generation
- **FFmpeg** (with xfade filter support, FFmpeg 5.0+) — Video composition + transitions
- **Pillow** — Image processing + title overlay
- **requests** — HTTP client for MiniMax API
- **schedule** — Daily task scheduling
- **Spreado** (optional) — Kuaishou video upload
