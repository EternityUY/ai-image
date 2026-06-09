"""Uploader — upload videos to Kuaishou via Spreado CLI.

Requires:  spreado (https://github.com/BadKid90s/Spreado)
Install:   pip install spreado
Login:     spreado login kuaishou   (interactive browser login)
"""

import logging
import os
import re
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def _find_spreado() -> str | None:
    """Locate the ``spreado`` binary on the system PATH."""
    return shutil.which("spreado")


def _parse_upload_output(stdout: str) -> dict[str, Any]:
    """Parse spreado CLI output for upload result.

    Spreado outputs lines like:
        ✓ 快手 上传成功

    Returns:
        Dict with keys: success (bool), platform (str), error (str|None)
    """
    result: dict[str, Any] = {"success": False, "platform": None, "error": None}

    # Check for success markers
    success_patterns = [
        r"上传成功",
        r"✓\s*快手",
        r"✓\s*kuaishou",
    ]
    for pattern in success_patterns:
        if re.search(pattern, stdout):
            result["success"] = True
            result["platform"] = "kuaishou"
            return result

    # Check for failure markers
    failure_patterns = [
        r"上传失败",
        r"✗\s*快手",
        r"Error",
        r"error",
    ]
    for pattern in failure_patterns:
        match = re.search(pattern, stdout)
        if match:
            result["error"] = match.group(0)
            return result

    # Fallback
    result["error"] = "Unknown upload result (unable to parse output)"
    return result


def upload_to_kuaishou(
    video_path: str,
    title: str = "",
    content: str = "",
    tags: str = "",
    cover_path: str | None = None,
    cookies_path: str = "cookies",
) -> dict[str, Any]:
    """Upload a video to Kuaishou using Spreado CLI.

    Args:
        video_path: Absolute path to the MP4 video file.
        title: Video title.
        content: Video description/content.
        tags: Comma-separated tags.
        cover_path: Optional path to cover image.
        cookies_path: Path to the cookies directory.

    Returns:
        Dict with keys: success (bool), platform (str|None), error (str|None),
        output (str), bvid (str|None).
    """
    if not os.path.isfile(video_path):
        return {"success": False, "error": f"Video file not found: {video_path}"}

    # Locate spreado binary
    spreado_path = _find_spreado()
    if spreado_path is None:
        logger.warning(
            "spreado is not installed. "
            "Install with: pip install spreado"
        )
        return {"success": False, "error": "spreado not found on PATH"}

    # Build the spreado command
    cmd: list[str] = [
        spreado_path,
        "upload",
        "kuaishou",
        "--video", video_path,
    ]

    if title:
        cmd.extend(["--title", title])
    if content:
        cmd.extend(["--content", content])
    if tags:
        cmd.extend(["--tags", tags])
    if cover_path and os.path.isfile(cover_path):
        cmd.extend(["--cover", cover_path])
    # Spreado --cookies expects a file path (the account.json), not a directory.
    # If cookies_path is a specific file, pass it; otherwise let Spreado use its default.
    if cookies_path:
        if os.path.isfile(cookies_path):
            cmd.extend(["--cookies", cookies_path])
        elif os.path.isdir(cookies_path):
            # Construct the default account.json path for kuaishou
            default_cookie_file = os.path.join(cookies_path, "kuaishou_uploader", "account.json")
            if os.path.isfile(default_cookie_file):
                cmd.extend(["--cookies", default_cookie_file])

    logger.info("Uploading video to Kuaishou via Spreado ...")
    logger.debug("Running: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        output_text = stdout + stderr
        logger.info("Spreado output:\n%s", output_text[:500])

        upload_result = _parse_upload_output(output_text)
        upload_result["output"] = output_text

        # Also try to extract BVID-like ID from output
        bv_match = re.search(r"(BV[\w]{10,})", output_text)
        upload_result["bvid"] = bv_match.group(0) if bv_match else None

        if upload_result["success"]:
            logger.info("Kuaishou upload successful!")
        else:
            logger.warning("Kuaishou upload failed: %s", upload_result.get("error", output_text[:200]))

        return upload_result

    except FileNotFoundError:
        return {"success": False, "error": "spreado binary not found (unexpected)"}
    except subprocess.TimeoutExpired:
        logger.warning("spreado upload timed out (600s)")
        return {"success": False, "error": "upload timed out (600s)"}
    except Exception as e:
        logger.exception("spreado upload failed with unexpected error")
        return {"success": False, "error": str(e)}


def upload_video(
    video_path: str,
    cover_path: str | None,
    title: str,
    content: str,
    tags: str,
    upload_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Generic upload entry point dispatched by platform config.

    Currently supports Kuaishou via Spreado.
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
    # Schedule is optionally supported via the --schedule flag

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
