# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

**ai-image** — 自动 AI 壁纸推荐视频生成管线。通过 MiniMax API 生成多张高清壁纸图片，随机选取本地配乐，使用 FFmpeg 合成带转场效果的视频 slideshow，可选择上传到快手。

功能亮点：
- 🖼️ MiniMax AI 图片生成（高清壁纸风格）
- 🎬 Ken Burns 镜头推拉效果（静态壁纸动态化）
- ✨ FFmpeg xfade 多转场效果
- 💧 视频水印叠加
- 📤 自动上传快手（通过 Spreado）
- ⏰ 每日定时任务

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt

# 如果需要快手上传功能
pip install spreado

# 需要 FFmpeg 5.0+（xfade 滤镜支持）
sudo apt install ffmpeg      # Ubuntu/Debian
# brew install ffmpeg         # macOS
```

### 2. 配置 MiniMax API

前往 [MiniMax 开放平台](https://platform.minimaxi.com) 注册并创建 API key：

1. 登录 [platform.minimaxi.com](https://platform.minimaxi.com)
2. 进入 **API Keys** 管理页面
3. 点击 **创建新的 API Key**
4. 复制生成的 key（格式如 `eyJ...`）

### 3. 准备配置文件

```bash
cp config.example.json config.json
# 编辑 config.json，填入你的 API key 和图片提示词
```

最小配置只需要修改 `minmax.api_key`：

```json
{
  "minmax": {
    "api_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

### 4. 准备配乐

```bash
mkdir -p music
# 将 .mp3/.wav/.flac/.m4a 格式的音频文件放入 music/ 目录
```

### 5. 运行管线

```bash
python3 src/main.py
```

---

## 配置详解 (config.json)

所有配置项均有默认值，只需填写必须项并按需覆盖。

### `minmax` — MiniMax API 配置

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `api_key` | string | — | **（必填）** MiniMax API key，从 [platform.minimaxi.com](https://platform.minimaxi.com) 获取 |
| `base_url` | string | `https://api.minimaxi.com/v1` | API 基础地址（一般不需要改） |

### `generation` — 图片生成 & 水印

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `image_count` | int | `5` | 生成图片数量（每批生成 N 张，建议 3~7） |
| `image_prompts` | string[] | — | 图片提示词列表，数量必须 >= `image_count`，程序取前 N 个 |
| `image_model` | string | `image-01` | MiniMax 图片模型 |
| `image_style` | string | `高清壁纸，精细画质，超高细节，色彩鲜艳` | 艺术风格描述，自动追加到每个提示词末尾 |
| `image_size` | string | `1024x1024` | 图片尺寸（API 请求参数） |
| `music_dir` | string | `music` | 配乐文件夹路径（相对或绝对路径） |
| `video_aspect_ratio` | string | `9:16` | 视频比例：`9:16`（竖屏/手机）或 `16:9`（横屏/桌面） |
| `title_overlay` | bool | `true` | 是否在图片上叠加主题文字 |
| `title_font_path` | string | — | 中文字体路径（自动检测系统字体，通常不需要设置） |
| `title_font_size` | int | `auto` | 字体大小，默认按视频高度 6% 自动计算 |
| `title_position` | string | `bottom` | 标题位置：`bottom` / `top` / `center` |
| `title_color` | string | `white` | 标题颜色 |
| `title_stroke_color` | string | `black` | 描边颜色 |
| `title_stroke_width` | int | `2` | 描边宽度 |

#### `watermark` — 视频水印

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `true` | 是否启用视频水印 |
| `template` | string | `精选壁纸《{id}》` | 水印文字模板，`{id}` 会被替换为 `id` 字段的值 |
| `id` | string | `""` | 水印编号/标识符，置空则显示为 `精选壁纸《》` |
| `font_size` | int | `32` | 水印字号 |
| `position` | string | `bottom-right` | 位置：`bottom-right` / `bottom-left` / `top-right` / `top-left` / `bottom` / `top` / `center` |
| `color` | string | `white@0.6` | 颜色及透明度，`@` 后为 alpha 值（0~1），如 `white@0.5`=半透明白 |
| `stroke_color` | string | `black@0.8` | 文字描边颜色+透明度 |
| `stroke_width` | float | `1.5` | 描边宽度 |
| `margin` | int | `30` | 边距（像素），仅对非 `center` 位置有效 |

### `video` — 视频合成参数

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `fps` | int | `24` | 视频帧率 |
| `crf` | int | `20` | H.264 质量控制 (18~28，**越小质量越好，文件越大**)。18=无损级，20=高质量，23=默认，28=较小文件 |
| `preset` | string | `medium` | x264 编码预设。编码速度从快到慢：`ultrafast` → `superfast` → `veryfast` → `faster` → `fast` → `medium` → `slow` → `slower` → `veryslow`。越慢压缩率越高、文件越小 |
| `image_duration` | float | `0` | 每张图片展示时长（秒）。`0` = 自动按音乐时长均分 |

#### `transition` — 转场效果

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `style` | string | `smoothleft` | 转场风格：`fade`(淡入淡出), `fadeblack`(黑场过渡), `fadewhite`(白场过渡), `dissolve`(溶解), `slideleft`(左滑), `slideright`(右滑), `slideup`(上滑), `slidedown`(下滑), `smoothleft`(平滑左推), `smoothright`(平滑右推), `circleopen`(圆形展开), `circleclose`(圆形收拢), `pixelize`(像素化), `radial`(径向), `hblur`(模糊), `wipe`(擦拭), `zoomin`(放大), `hlslice`(水平切片) |
| `duration` | float | `1.2` | 转场时长（秒），建议 0.5~2.0 |

#### `ken_burns` — 镜头推拉效果

让静态壁纸图片产生缓慢缩放+平移的动态感。

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `true` | 是否启用 Ken Burns 运镜 |
| `zoom` | float | `0.03` | 缩放比例（终值 = 1.0 + zoom）。如 `0.03` = 从 100% 缓慢放大到 103%。建议 `0.02`~`0.05`，太大容易晕 |
| `pan` | string | `random` | 平移方向：`none`(无平移，仅缩放), `random`(每张图随机方向), `left` / `right` / `up` / `down` |

注意：启用 Ken Burns 后视频编码会变慢（因为需要对每帧做 zoompan 计算）。如果只需要简单的静态 slideshow，可设为 `"enabled": false`。

#### `background_music`

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `volume` | float | `0.8` | 背景音乐音量 (0.0~1.0)，`0.8`=80% |

### `upload` — 快手上传配置

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `false` | 是否启用自动上传 |
| `platform` | string | `kuaishou` | 上传平台（当前仅支持 `kuaishou`） |
| `cookies_path` | string | `cookies` | Spreado 登录 cookie 保存目录 |

#### `video` — 视频标题/描述/标签

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `title` | string | `精选壁纸《{theme}》` | 视频标题，支持 `{theme}` 变量（自动替换为当前主题） |
| `tags` | string | `精选壁纸,手机壁纸,4K壁纸,AI壁纸,高清壁纸,壁纸推荐` | 逗号分隔的标签 |
| `content` | string | — | 视频描述/简介，支持 `{theme}` 变量。可使用 `\n` 换行 |
| `schedule` | string | `""` | 定时发布（留空立即发布），格式取决于平台 |

### `cleanup` — 自动清理

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `max_age_days` | int | `7` | 超过 N 天的旧输出文件夹自动删除 |

### `schedule` — 运行模式

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `mode` | string | `single` | `single` = 单次运行，`daily` = 每日定时任务 |
| `daily_time` | string | `02:00` | 每日定时时间（仅 `mode=daily` 时有效），24小时制 HH:MM |

---

## 转场效果参考

FFmpeg xfade 支持的全部转场效果：

| 分类 | 效果 |
|---|---|
| 淡入淡出 | `fade`, `fadeblack`, `fadewhite` |
| 滑动 | `slideleft`, `slideright`, `slideup`, `slidedown` |
| 平滑滑动 | `smoothleft`, `smoothright`, `smoothup`, `smoothdown` |
| 圆形 | `circleopen`, `circleclose` |
| 矩形 | `rectopen`, `rectclose` |
| 溶解/像素 | `dissolve`, `pixelize` |
| 径向/模糊 | `radial`, `hblur` |
| 擦除/缩放 | `wipetl`, `wipe`, `zoomin` |
| 切片 | `hlslice` |

---

## 快手上传设置 (Kuaishou)

本工程使用 [Spreado](https://github.com/BadKid90s/Spreado) 实现快手视频自动上传。

### 1. 安装 Spreado

```bash
pip install spreado
```

Spreado 基于 Playwright，会自动检测系统中已安装的 Chrome/Edge 浏览器。如无可用的浏览器，Playwright 会自动下载内置 Chromium。

### 2. 快手登录（首次使用）

运行以下命令，会弹出浏览器窗口进行快手登录：

```bash
spreado login kuaishou
```

登录成功后会保存 cookie 到本地目录（默认为当前目录下的 `cookies/`）。**cookie 有效期通常为几天到几周**，过期后需要重新登录。

```bash
# 验证登录状态
spreado verify kuaishou
```

### 3. 配置上传参数

在 `config.json` 中启用上传并设置视频信息：

```json
{
  "upload": {
    "enabled": true,
    "platform": "kuaishou",
    "cookies_path": "cookies",
    "video": {
      "title": "精选壁纸《{theme}》",
      "tags": "精选壁纸,手机壁纸,AI壁纸",
      "content": "✨ 精选高清壁纸推荐 ✨\n\n主题：{theme}\n\n#精选壁纸 #手机壁纸",
      "schedule": ""
    }
  }
}
```

#### 上传配置技巧

- **`{theme}` 变量**：在 title/content 中使用 `{theme}`，程序会自动替换为当前图片的主题（第一个提示词的前40个字符）
- **`title`**：快手标题有限制（通常 ≤ 30 字），建议简洁
- **`tags`**：逗号分隔，用于视频分类和搜索推荐
- **`content`**：可包含换行符 `\n` 和话题标签 `#标签`
- **`schedule`**：留空立即发布；如需定时发布，填写平台支持的时间格式

### 4. 配置示例

以下是一个完整的 `config.json` 示例：

```json
{
  "minmax": {
    "api_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "base_url": "https://api.minimaxi.com/v1"
  },
  "generation": {
    "image_count": 5,
    "image_prompts": [
      "梦幻极光下的雪山湖泊，4K壁纸，深邃蓝紫调",
      "赛博朋克风格雨夜霓虹街景，紫蓝粉调，氛围壁纸"
    ],
    "image_style": "高清壁纸，精细画质，超高细节，色彩鲜艳",
    "music_dir": "music",
    "watermark": {
      "enabled": true,
      "template": "精选壁纸《{id}》",
      "id": "001",
      "position": "bottom-right"
    }
  },
  "video": {
    "crf": 20,
    "preset": "medium",
    "transition": {
      "style": "smoothleft",
      "duration": 1.2
    },
    "ken_burns": {
      "enabled": true,
      "zoom": 0.03,
      "pan": "random"
    }
  },
  "upload": {
    "enabled": true,
    "cookies_path": "cookies",
    "video": {
      "title": "精选壁纸《极光雪山》",
      "tags": "精选壁纸,手机壁纸,4K壁纸,AI壁纸",
      "content": "✨ 精选高清壁纸推荐 ✨\n\n#精选壁纸 #手机壁纸"
    }
  }
}
```

---

## 常见问题

### API Key 问题

- **错误信息** `minmax.api_key is not set`：没有在 config.json 中填写 API key
- **错误信息** `API error (xxx)`：API key 无效或过期，请前往 [MiniMax 平台](https://platform.minimaxi.com) 重新生成
- **MiniMax API 免费额度**：注册 MiniMax 有免费额度，具体请查看官网定价

### 上传失败

- **Spreado 未安装**：`pip install spreado`
- **未登录快手**：运行 `spreado login kuaishou`
- **Cookie 过期**：重新运行 `spreado login kuaishou`
- **上传超时**：视频文件过大或网络问题，检查视频大小和网络连接
- **浏览器问题**：确保安装了 Chrome/Edge 或 Playwright 可下载 Chromium

### FFmpeg 问题

- **xfade 滤镜不存在**：需要 FFmpeg 5.0+，运行 `ffmpeg -version` 检查版本
- **编码很慢**：降低 `crf`（至 23~25）或改用 `faster`/`veryfast` preset
- **视频过大**：提高 `crf`（至 23~28）或使用更快的 `preset`

### Ken Burns 效果

- **编码明显变慢**：这是正常的，`zoompan` 滤镜需要逐帧计算。如果不需要，设置为 `"enabled": false`
- **缩放太剧烈**：降低 `zoom` 值（推荐 0.02~0.03）

---

## 项目结构

```
├── config.json                 # 用户配置（需手动创建，gitignored）
├── config.example.json         # 配置模板（含完整注释）
├── requirements.txt            # Python 依赖
├── music/                      # 配乐目录（用户放入 .mp3/.wav 文件）
├── cookies/                    # Spreado 登录 cookie（gitignored）
├── .gitignore
├── src/
│   ├── main.py                 # 入口 — 单次/每日模式调度
│   ├── config_loader.py        # 读取 & 校验 config.json，合并默认值
│   ├── image_generator.py      # MiniMax 图片 API 调用
│   ├── music_selector.py       # 随机选取配乐文件
│   ├── video_composer.py       # FFmpeg 视频合成（xfade 转场 + Ken Burns + 水印）
│   ├── pipeline.py             # 完整工作流编排（7 个步骤）
│   ├── output_manager.py       # 创建时间戳文件夹，写入 info.txt
│   ├── uploader.py             # Spreado CLI 调用的快手上传
│   └── cleanup.py              # 清理过期输出文件夹
├── output/                     # 生成结果（视频/图片/封面，gitignored）
└── CLAUDE.md
```

## 管线流程 (src/pipeline.py)

1. **Cleanup** — `cleanup.py` 删除超过 `cleanup.max_age_days` 天的旧输出文件夹
2. **图片生成** — MiniMax API 为每个提示词生成一张壁纸图片
3. **配乐选择** — 从 `music_dir` 随机选取一个音频文件
4. **视频合成** — `video_composer.py` 合成视频：
   - 每张图片按目标比例缩放 + 居中裁切
   - 可选标题文字叠加（Pillow 渲染）
   - **Ken Burns 效果**（可选）：zoompan 滤镜实现缓慢缩放平移
   - **转场**：xfade 滤镜实现多效果切换
   - **水印**（可选）：drawtext 滤镜叠加文字水印
   - 视频总时长自动匹配音频长度
5. **封面** — 用第一张图片生成 `cover.jpg`（带居中标题）
6. **输出** — 保存到 `output/YYYY-MM-DD_HH-MM-SS_<slug>/`，写入 `info.txt`
7. **上传**（可选）— 如果 `upload.enabled=true`，通过 Spreado 上传到快手

---

## 常用命令

```bash
# 运行管线（单次模式）
python3 src/main.py

# 导入检查
python3 -c "from src.config_loader import get_config; from src.image_generator import ImageGenerator; from src.music_selector import select_random_music; from src.video_composer import compose_slideshow; from src.output_manager import create_output_folder, write_info_file; from src.uploader import upload_video; from src.cleanup import clean_old_folders; print('OK')"

# 检查 FFmpeg 是否支持 xfade
ffmpeg -filters | grep xfade

# 代码检查
pip install ruff && ruff check src/
```
