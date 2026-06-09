# 🎬 AI Image Video Generator

AI 图片生成 → 配乐 → 视频合成 → 快手发布 全自动管线

从配置好的提示词批量生成图片，随机挑选本地配乐，合成带有转场效果的短视频，并可自动发布到快手。

## ✨ 功能特性

- 🖼️ **批量生图** — 使用 MiniMax API 从配置文件中的提示词列表批量生成图片（数量可配，推荐 3-5 张）
- 🎵 **随机配乐** — 从本地文件夹中随机挑选音乐（支持 mp3/wav/flac/m4a）
- 🎬 **幻灯片视频** — 多张图片合成一个视频，时长自动匹配音乐长度
- 🔄 **丰富转场** — 支持 fade/dissolve/slide/wipe/zoom 等 20+ 种转场效果，全部可配置
- 🖌️ **标题水印** — 视频画面自动叠加标题水印，支持自定义字体/颜色/位置
- 📐 **多比例支持** — 16:9（横屏）和 9:16（竖屏/短视频）自由切换
- 📤 **快手发布** — 可选自动上传视频到快手（基于 Spreado 浏览器自动化）
- ⏰ **定时执行** — 支持每天固定时间自动运行
- 🧹 **自动清理** — 自动删除超过指定天数的旧输出文件夹

## 📋 系统要求

- Python 3.9+
- FFmpeg 5.0+（需支持 xfade 滤镜）
- MiniMax API Key（[注册获取](https://platform.minimaxi.com)）
- （可选）Chrome/Edge 浏览器 — 用于快手发布

```bash
# 安装 FFmpeg
sudo apt install ffmpeg   # Ubuntu/Debian
brew install ffmpeg       # macOS
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp config.example.json config.json
```

编辑 `config.json`，至少需要填写：

- `minmax.api_key` — MiniMax API 密钥
- `generation.image_prompts` — 图片生成提示词列表（数量 >= image_count）

```json
{
  "minmax": { "api_key": "你的MiniMax API Key" },
  "generation": {
    "image_count": 4,
    "image_prompts": [
      "梦幻星空下的宁静湖面，水彩风格",
      "春日樱花飘落的街道，治愈系插画",
      "落日余晖洒在海面上，金色波浪",
      "森林深处的秘密花园，光影斑驳"
    ]
  }
}
```

### 3. 准备配乐

```bash
mkdir -p music
```

将 MP3/WAV/FLAC/M4A 格式的音频文件放入 `music/` 目录，脚本会随机挑选一首作为视频配乐。

### 4. 运行

```bash
python3 src/main.py
```

执行完成后，会在 `output/` 目录下生成一个带时间戳的文件夹：

```
output/
└── 2026-06-09_11-30-00_梦幻星空下的宁静湖面/
    ├── images/
    │   ├── image_01.png
    │   ├── image_02.png
    │   ├── image_03.png
    │   └── image_04.png
    ├── song.mp3            # 配乐文件
    ├── video.mp4           # 合成视频（图片+转场+配乐+标题水印）
    ├── cover.jpg           # 封面图
    └── info.txt            # 生成信息
```

## ⏱ 定时模式

设置 `config.json` 中的 `schedule.mode` 为 `"daily"`：

```json
{
  "schedule": {
    "mode": "daily",
    "daily_time": "02:00"
  }
}
```

进程会保持运行，每天凌晨 2 点自动执行一次。

## 🎬 转场效果

支持 20+ 种转场效果，在 `config.json` 中配置：

```json
{
  "video": {
    "transition": {
      "style": "fade",
      "duration": 1.0
    }
  }
}
```

| 分类 | 效果名 | 说明 |
|------|--------|------|
| 淡入淡出 | `fade` | 标准交叉淡变 |
| | `fadeblack` | 通过黑色过渡 |
| | `fadewhite` | 通过白色过渡 |
| 滑动 | `slideleft` / `slideright` | 左右滑动 |
| | `slideup` / `slidedown` | 上下滑动 |
| | `smoothleft` / `smoothright` | 平滑左右滑动 |
| | `smoothup` / `smoothdown` | 平滑上下滑动 |
| 形状 | `circleopen` / `circleclose` | 圆形展开/收拢 |
| | `rectopen` / `rectclose` | 矩形展开/收拢 |
| 特效 | `dissolve` | 溶解 |
| | `pixelize` | 像素化 |
| | `radial` | 放射状 |
| | `hblur` | 水平模糊 |
| | `wipe` / `wipetl` | 擦除 |
| | `zoomin` | 放大进入 |

## 📐 视频比例

| 比例 | 分辨率 | 适用场景 |
|------|--------|----------|
| `9:16` | 1080×1920 | **默认**，快手/抖音竖屏短视频 |
| `16:9` | 1920×1080 | 横屏视频 |

## 📤 快手自动发布

本管线使用 [Spreado](https://github.com/BadKid90s/Spreado) 进行快手发布（浏览器自动化方式）。

### 安装 Spreado

```bash
pip install spreado
```

### 登录快手（仅首次）

```bash
spreado login kuaishou
```

会打开浏览器窗口，扫码登录快手创作者平台。登录完成后 cookie 自动保存。

### 验证登录状态

```bash
spreado verify kuaishou
```

### 启用自动发布

在 `config.json` 中设置：

```json
{
  "upload": {
    "enabled": true,
    "platform": "kuaishou",
    "video": {
      "title": "AI影像《{theme}》",
      "tags": "AI视频,AI生成,人工智能",
      "content": "AI自动生成的影像视频\n\n主题：{theme}\n\n#AI视频 #AI生成"
    }
  }
}
```

> `{theme}` 变量会自动替换为第一个图片提示词。

## 🐳 Docker 部署

本项目完全支持在 **无 GUI 的 Linux 服务器 / Docker 容器** 中运行。上传功能通过 Spreado Python API 调用，**上传过程是 headless 的**，无需浏览器窗口。

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 系统依赖：FFmpeg + Playwright Chromium 所需库
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir spreado

# Playwright Chromium（headless 模式）
RUN python3 -m playwright install chromium

# 项目代码
COPY src/ ./src/

# 默认命令
CMD ["python3", "src/main.py"]
```

### 工作原理

| 步骤 | 需要图形界面？ | 说明 |
|---|---|---|
| **快手登录**（一次性） | ✅ **需要** | 在宿主机运行 `spreado login kuaishou`，弹出浏览器扫码登录 |
| **自动上传**（日常运行） | ❌ **不需要** | Headless 模式，仅需有效 cookie + Playwright Chromium |

### 快速部署

```bash
# 1. 宿主机上准备数据目录
mkdir -p ~/ai-image-data
cp config.json ~/ai-image-data/config.json
cp -r music ~/ai-image-data/music
mkdir -p ~/ai-image-data/output

# 2. 宿主机上快手登录（一次性，需要显示器）
pip install spreado
spreado login kuaishou
# 登录后将 cookies 目录拷贝到数据目录
cp -r cookies ~/ai-image-data/cookies

# 3. 构建镜像
docker build -t ai-image .

# 4. 运行容器
sudo docker run -d \
  --name ai-image \
  --restart unless-stopped \
  -v ~/ai-image-data/config.json:/app/config.json:ro \
  -v ~/ai-image-data/music:/app/music:ro \
  -v ~/ai-image-data/cookies:/app/cookies:ro \
  -v ~/ai-image-data/output:/app/output \
  ai-image

# 5. 查看日志
sudo docker logs -f ai-image
```

### 数据卷说明

| 挂载路径 | 宿主机目录 | 权限 | 说明 |
|---|---|---|---|
| `/app/config.json` | `~/ai-image-data/config.json` | `ro` 只读 | 配置文件（含 MiniMax API key） |
| `/app/music` | `~/ai-image-data/music` | `ro` 只读 | 背景音乐文件目录 |
| `/app/cookies` | `~/ai-image-data/cookies` | `ro` 只读 | Spreado 登录 cookie |
| `/app/output` | `~/ai-image-data/output` | `rw` 读写 | 生成的视频 / 图片 / 封面 |

### docker-compose 部署（可选）

```yaml
version: "3"
services:
  ai-image:
    build: .
    container_name: ai-image
    restart: unless-stopped
    volumes:
      - ~/ai-image-data/config.json:/app/config.json:ro
      - ~/ai-image-data/music:/app/music:ro
      - ~/ai-image-data/cookies:/app/cookies:ro
      - ~/ai-image-data/output:/app/output
```

### 定时任务模式

配置 `config.json` 中的 `schedule` 以实现每日定时生成：

```json
{
  "schedule": {
    "mode": "daily",
    "daily_time": "02:00"
  }
}
```

容器会一直在后台运行，每天凌晨 2:00 自动执行一次管线。

### 初次设置流程

**Step 1：宿主机上登录快手（一次性）**

```bash
pip install spreado
spreado login kuaishou
```

登录成功后 cookie 保存在 `cookies/kuaishou_uploader/account.json`。

**Step 2：拷贝 cookie 到容器数据目录**

```bash
cp -r cookies ~/ai-image-data/cookies
```

**Step 3：启动容器**

```bash
sudo docker run -d \
  --name ai-image \
  --restart unless-stopped \
  -v ~/ai-image-data/config.json:/app/config.json:ro \
  -v ~/ai-image-data/music:/app/music:ro \
  -v ~/ai-image-data/cookies:/app/cookies:ro \
  -v ~/ai-image-data/output:/app/output \
  ai-image
```

**Step 4：查看日志**

```bash
sudo docker logs -f ai-image
```

### 环境变量（可选）

| 变量 | 说明 |
|---|---|
| `SPREADO_BROWSER_PATH` | 指定浏览器可执行文件路径 |
| `SPREADO_BROWSER_CHANNEL` | 指定浏览器通道（`chrome` / `msedge`） |

一般不需要设置 — Spreado 会自动使用 Playwright 内置的 Chromium。

---

## ⚙️ 完整配置说明

### config.json

| 字段 | 说明 | 默认值 |
|------|------|--------|
| **MiniMax API** | | |
| `minmax.api_key` | API Key（必填） | — |
| `minmax.base_url` | API 地址 | `https://api.minimaxi.com/v1` |
| **调度** | | |
| `schedule.mode` | `"single"` / `"daily"` | `single` |
| `schedule.daily_time` | 每日执行时间 (HH:MM) | `02:00` |
| **图片生成** | | |
| `generation.image_count` | 生成图片数量 | `4` |
| `generation.image_prompts` | 图片提示词列表 | — |
| `generation.image_model` | 图片模型 | `image-01` |
| `generation.image_style` | 艺术风格（追加到提示词后） | `水彩艺术插画` |
| **配乐** | | |
| `generation.music_dir` | 配乐文件夹 | `music` |
| **视频** | | |
| `generation.video_aspect_ratio` | 视频比例 `16:9` / `9:16` | `9:16` |
| `video.fps` | 帧率 | `24` |
| `video.crf` | H.264 质量 (18-28) | `23` |
| `video.transition.style` | 转场效果 | `fade` |
| `video.transition.duration` | 转场时长（秒） | `1.0` |
| `video.image_duration` | 每张图片展示时长（0=自动） | `0` |
| **标题水印** | | |
| `generation.title_overlay` | 是否显示标题水印 | `true` |
| `generation.title_position` | 位置：bottom/top/center | `bottom` |
| **上传** | | |
| `upload.enabled` | 是否启用快手发布 | `false` |
| `upload.platform` | 上传平台 | `kuaishou` |
| **清理** | | |
| `cleanup.max_age_days` | 输出文件夹保留天数 | `7` |

## 📁 项目结构

```
├── config.json              # 用户配置（不提交到 git）
├── config.example.json      # 配置模板
├── requirements.txt         # Python 依赖
├── music/                   # 配乐文件夹（放入音频文件）
├── src/
│   ├── main.py              # 入口：单次 / 定时模式
│   ├── config_loader.py     # 配置加载与校验
│   ├── image_generator.py   # MiniMax 图片生成
│   ├── music_selector.py    # 随机配乐选择
│   ├── video_composer.py    # FFmpeg 视频合成 + 转场
│   ├── pipeline.py          # 流程编排（7 个步骤）
│   ├── output_manager.py    # 输出文件夹 + info.txt
│   ├── uploader.py          # 快手发布（调用 Spreado）
│   └── cleanup.py           # 过期文件夹清理
├── output/                  # 生成结果（不提交到 git）
├── cookies/                 # Spreado cookie（不提交到 git）
└── README.md
```

## 🔄 管线流程

```
                  +-----------+
                  | 清理旧文件  |
                  +-----------+
                       ↓
    +----------------------------------+
    | MiniMax API 批量生成 N 张图片     |
    | （从 config 中的 prompts 列表读取） |
    +----------------------------------+
                       ↓
    +----------------------------------+
    | 从 music/ 目录随机挑选一首配乐    |
    +----------------------------------+
                       ↓
    +----------------------------------+
    | FFmpeg 合成幻灯片视频             |
    | 每张图片缩放裁剪 → 叠加标题水印   |
    | → xfade 转场连接 → 匹配音乐时长   |
    +----------------------------------+
                       ↓
    +----------------------------------+
    | 保存到输出文件夹 + 生成 info.txt  |
    +----------------------------------+
                       ↓ (可选)
    +----------------------------------+
    | 通过 Spreado 发布到快手          |
    +----------------------------------+
```

## 🛠 技术栈

- **Python 3.9+**
- **MiniMax API** — 图片生成
- **FFmpeg + xfade** — 视频合成与转场
- **Pillow** — 图片处理与标题渲染
- **Spreado** — 快手浏览器自动化发布
- **schedule** — 定时任务调度

## 📜 License

MIT
