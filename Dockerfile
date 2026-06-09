FROM python:3.12-slim

WORKDIR /app

# System deps: FFmpeg for video + Playwright Chromium dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir spreado

# Playwright Chromium (headless)
RUN python3 -m playwright install chromium

# Project code
COPY src/ ./src/

# Default command
CMD ["python3", "src/main.py"]
