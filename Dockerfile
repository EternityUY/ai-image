FROM python:3.12-slim

WORKDIR /app

# System deps: FFmpeg for video + Playwright Chromium + CJK fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-noto-cjk \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir spreado

# Playwright Chromium (headless)
RUN python3 -m playwright install chromium

# Project code
COPY src/ ./src/

# Ensure output directory exists at runtime
RUN mkdir -p output

# Default command (unbuffered for real-time docker logs)
CMD ["python", "-u", "-m", "src.main"]
