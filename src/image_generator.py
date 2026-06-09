"""Image generator — generates multiple images via MiniMax API from config prompts."""

import base64
import json
import logging
import os


import requests

logger = logging.getLogger(__name__)


class MinMaxError(Exception):
    """Raised on MinMax API errors."""

    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class ImageGenerator:
    """Generate images using MiniMax Image API."""

    IMAGE_URL = "/image_generation"

    def __init__(self, api_key: str, base_url: str = "https://api.minimaxi.com/v1"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        model: str = "image-01",
    ) -> bytes:
        """Generate a single image from a text prompt.

        Returns:
            Raw image bytes (png).
        """
        body = {
            "model": model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "response_format": "base64",
        }

        logger.info("Generating image for prompt: %s ...", prompt[:60])
        data = self._post(self.IMAGE_URL, body)

        image_base64_list = data.get("data", {}).get("image_base64") or []
        if image_base64_list:
            logger.info("Image generated, decoding base64 ...")
            return base64.b64decode(image_base64_list[0])

        image_urls = data.get("data", {}).get("image_urls") or []
        if image_urls:
            logger.info("Image generated, downloading from URL ...")
            return self._download(image_urls[0])

        raise MinMaxError(
            "No image data in response",
            response_body=json.dumps(data, ensure_ascii=False),
        )

    def generate_images(
        self,
        prompts: list[str],
        aspect_ratio: str = "1:1",
        model: str = "image-01",
        output_dir: str | None = None,
    ) -> list[str]:
        """Generate multiple images from a list of prompts.

        Args:
            prompts: List of text prompts (one per image).
            aspect_ratio: Aspect ratio for all images (e.g. "1:1", "16:9", "9:16").
            model: Image model name.
            output_dir: If set, save images here with numbered filenames.

        Returns:
            List of paths to generated image files (if output_dir set)
            or an empty list if no output_dir.
        """
        image_paths = []
        for i, prompt in enumerate(prompts):
            logger.info("Generating image %d/%d ...", i + 1, len(prompts))
            try:
                img_bytes = self.generate_image(
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    model=model,
                )
                if output_dir:
                    ext = "png"
                    filename = f"image_{i + 1:02d}.{ext}"
                    filepath = os.path.join(output_dir, filename)
                    with open(filepath, "wb") as f:
                        f.write(img_bytes)
                    logger.info("Saved image %d to: %s", i + 1, filepath)
                    image_paths.append(filepath)
            except Exception as e:
                logger.error("Failed to generate image %d: %s", i + 1, e)
                raise

        return image_paths

    def _post(self, endpoint: str, body: dict) -> dict:
        """POST JSON to endpoint, return parsed response."""
        url = f"{self.base_url}{endpoint}"
        logger.debug("POST %s", url)
        resp = self.session.post(url, json=body, timeout=120)
        try:
            data: dict = resp.json()
        except ValueError as e:
            raise MinMaxError(
                f"Non-JSON response from {endpoint}: {e}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

        base_resp = data.get("base_resp") or {}
        code = base_resp.get("status_code", 0)
        if code != 0:
            msg = base_resp.get("status_msg", "Unknown error")
            raise MinMaxError(
                f"API error ({code}): {msg}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

        return data

    def _download(self, url: str) -> bytes:
        """Download a file from a URL."""
        resp = self.session.get(url, timeout=120)
        resp.raise_for_status()
        return resp.content
