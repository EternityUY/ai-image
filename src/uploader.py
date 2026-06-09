"""Uploader — upload videos to Kuaishou via Spreado Python API.

Spreado (https://github.com/BadKid90s/Spreado) is a Playwright-based
multi-platform video uploader. It supports Python API (not just CLI):

  Login (one-time, needs interactive browser):
      spreado login kuaishou

  Upload (headless, works in Docker):
      from spreado import PluginLoader
      uploader = PluginLoader().get_publisher('kuaishou')
      await uploader.upload_video_flow(file_path="video.mp4", ...)

Login must be done on a machine with a GUI browser first.
After cookies are saved, upload runs fully headless.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _resolve_cookie_file_path(cookies_path: str) -> Path | None:
    """Resolve the cookie file path from config's cookies_path.

    Spreado defaults to: cookies/kuaishou_uploader/account.json
    If a custom path is provided:
      - If cookies_path points directly to a file, use it
      - If cookies_path is a directory, look for kuaishou_uploader/account.json inside
    """
    if not cookies_path:
        return None  # Let Spreado use its own default

    p = Path(cookies_path)
    if p.suffix == ".json":
        return p.resolve()
    if p.is_dir():
        default_cookie = p / "kuaishou_uploader" / "account.json"
        if default_cookie.is_file():
            return default_cookie.resolve()
        # Fall back to just the directory (Spreado will auto-resolve)
        return None
    return None


async def _upload_to_kuaishou_async(
    video_path: str,
    title: str = "",
    content: str = "",
    tags: str = "",
    cover_path: str | None = None,
    cookie_file_path: Path | None = None,
) -> dict[str, Any]:
    """Call Spreado's KuaiShouUploader.upload_video_flow() asynchronously.

    This runs headless (no browser GUI needed) as long as valid cookies exist.

    Returns:
        Dict with keys: success (bool), error (str|None), platform (str).
    """
    from spreado import PluginLoader

    loader = PluginLoader()
    loader.load()
    uploader = loader.get_publisher("kuaishou")

    # Override cookie path if specified
    if cookie_file_path is not None:
        uploader.cookie_file_path = cookie_file_path

    # Parse tags into list
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # Build thumbnail path
    thumb = Path(cover_path) if cover_path and os.path.isfile(cover_path) else None

    logger.info(
        "Uploading to Kuaishou via Spreado Python API ... "
        "headless=True, cookie=%s",
        uploader.cookie_file_path,
    )

    try:
        ok = await uploader.upload_video_flow(
            file_path=video_path,
            title=title,
            content=content,
            tags=tag_list,
            thumbnail_path=thumb,
        )
        if ok:
            logger.info("Kuaishou upload successful!")
            return {"success": True, "platform": "kuaishou", "error": None}
        else:
            logger.warning("Kuaishou upload returned failure.")
            return {
                "success": False,
                "platform": "kuaishou",
                "error": "upload_video_flow returned False",
            }
    except RuntimeError as e:
        msg = str(e)
        if "cookie" in msg.lower():
            logger.warning(
                "Kuaishou upload failed: cookie invalid. "
                "Please re-login: spreado login kuaishou"
            )
        else:
            logger.warning("Kuaishou upload failed: %s", msg)
        return {"success": False, "platform": "kuaishou", "error": msg}
    except Exception as e:
        msg = str(e)[:300]
        logger.exception("Kuaishou upload failed: %s", msg)
        return {"success": False, "platform": "kuaishou", "error": msg}


def upload_to_kuaishou(
    video_path: str,
    title: str = "",
    content: str = "",
    tags: str = "",
    cover_path: str | None = None,
    cookies_path: str = "cookies",
) -> dict[str, Any]:
    """Synchronous wrapper for async Kuaishou upload.

    Args:
        video_path: Absolute path to the MP4 video file.
        title: Video title.
        content: Video description.
        tags: Comma-separated tags.
        cover_path: Optional path to cover image.
        cookies_path: Path to the cookies directory or file.

    Returns:
        Dict with keys: success (bool), platform (str|None), error (str|None).
    """
    if not os.path.isfile(video_path):
        return {"success": False, "error": f"Video file not found: {video_path}"}

    # Check spreado is importable
    try:
        import spreado  # noqa: F401
    except ImportError:
        return {
            "success": False,
            "error": "spreado is not installed. Install with: pip install spreado",
        }

    cookie_file = _resolve_cookie_file_path(cookies_path)

    return asyncio.run(
        _upload_to_kuaishou_async(
            video_path=video_path,
            title=title,
            content=content,
            tags=tags,
            cover_path=cover_path,
            cookie_file_path=cookie_file,
        )
    )


def upload_video(
    video_path: str,
    cover_path: str | None,
    title: str,
    content: str,
    tags: str,
    upload_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Generic upload entry point dispatched by platform config.

    Currently supports Kuaishou via Spreado Python API.
    """
    if not upload_cfg.get("enabled", False):
        logger.info("Upload is disabled (enabled=false).")
        return {"success": False, "error": "disabled by config"}

    platform = upload_cfg.get("platform", "kuaishou")
    cookies_path = upload_cfg.get("cookies_path", "cookies")
    video_cfg = upload_cfg.get("video", {})

    if not title:
        title = video_cfg.get("title", "")
    if not content:
        content = video_cfg.get("content", "")
    if not tags:
        tags = video_cfg.get("tags", "")

    if platform == "kuaishou":
        return upload_to_kuaishou(
            video_path=video_path,
            title=title,
            content=content,
            tags=tags,
            cover_path=cover_path,
            cookies_path=cookies_path,
        )
    else:
        return {"success": False, "error": f"Unsupported platform: {platform}"}
