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

IMPORTANT: This module does NOT call Spreado's upload_video_flow() directly.
Instead, it creates a SINGLE browser instance for both cookie verification and
upload, avoiding a double-browser-launch race condition that causes intermittent
hangs in Docker/resource-constrained environments.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from spreado.core.browser import StealthBrowser

logger = logging.getLogger(__name__)

# ── Monkey-patches: KuaiShouUploader methods ──────────────────────────────────
# Kuaishou's publish page has two issues that prevent Playwright clicks:
#   1. A react-joyride onboarding tour that renders overlays in
#      #react-joyride-portal, intercepting hit-tests.
#   2. The contenteditable #work-description-edit div re-renders during upload,
#      so Playwright's scroll-into-view for .click() stalls indefinitely.
# Fix: dismiss the joyride, use page.evaluate to focus elements, and use
# force=True only on real button clicks that aren't contenteditable.


async def _inject_joyride_killer(page):
    """Inject a MutationObserver that auto-removes #react-joyride-portal.

    Kuaishou's publish page includes a react-joyride onboarding tour that
    renders overlay/spotlight divs intercepting Playwright hit-tests.  This
    observer removes the entire joyride portal as soon as it appears in the
    DOM, covering ALL subsequent interactions without per-method patches.
    """
    await page.evaluate(
        """() => {
            const kill = () => {
                const el = document.getElementById('react-joyride-portal');
                if (el) el.remove();
            };
            kill();  // remove if already present
            const obs = new MutationObserver(() => kill());
            obs.observe(document.documentElement, { childList: true, subtree: true });
        }"""
    )
    logger.info("Injected joyride-killer MutationObserver.")


async def _patched_fill_video_info(
    self, page, title: str = "", content: str = "", tags: list[str] | None = None
) -> bool:
    """Fixed version of KuaiShouUploader._fill_video_info.

    The original uses .click() on the contenteditable div, which times out
    because Playwright's scroll-into-view action gets stuck when the page
    re-renders during upload processing.  Fix: use page.evaluate to focus
    the element directly, bypassing Playwright's click/scroll machinery.
    """
    try:
        # Wait for the description field to appear (upload must be done first)
        await page.wait_for_selector(
            "#work-description-edit",
            state="attached",
            timeout=60000,
        )
        await page.wait_for_timeout(500)  # let the render settle

        # Focus via JavaScript — avoids Playwright's click/scroll hit-test
        await page.evaluate(
            """document.getElementById('work-description-edit').focus()"""
        )
        await page.wait_for_timeout(200)

        text_content = f"{title}\n{content}\n"
        await page.keyboard.type(text_content)

        added_tags_count = 0
        if tags:
            for tag in tags:
                topic_name = tag.lstrip("#")
                try:
                    await page.keyboard.down("Shift")
                    await page.keyboard.press("Digit3")
                    await page.keyboard.up("Shift")
                    await page.wait_for_timeout(100)
                    await page.keyboard.type(topic_name, delay=50)
                    await page.wait_for_timeout(500)
                    await page.keyboard.press("Enter")
                    added_tags_count += 1
                except Exception as e:
                    logger.warning("添加标签 %s 失败: %s", topic_name, e)
                    continue

        logger.info("成功添加内容和Tag: %d/%d", added_tags_count, len(tags or []))
        return True
    except Exception as e:
        logger.error("填写视频信息时出错: %s", e)
        return False


async def _patched_set_thumbnail(
    self, page, thumbnail_path: str | None = None
) -> bool:
    """No-op: skip cover setting and use Kuaishou's default cover instead.

    Kuaishou's react-joyride onboarding tour overlays the '封面设置' button,
    and the cover-upload interaction is fragile (multiple force-clicks, modal
    waits, file input, confirm).  The platform provides a default cover
    automatically, so skip this step entirely.
    """
    logger.info("跳过封面上传，使用快手默认封面")
    return True


async def _patched_publish_video(
    self, page, publish_url: str | None = None
) -> bool:
    """Fixed version of KuaiShouUploader._publish_video.

    Uses force=True on button clicks to bypass any remaining react-joyride
    overlay (the MutationObserver should already remove it, but force=True
    provides defense-in-depth).
    """
    import re

    success_pattern = re.compile(r"/article/manage/video\?status=2&from=publish")
    max_retries = 10
    retry_count = 0

    while retry_count < max_retries:
        try:
            publish_button = page.get_by_text("发布", exact=True)
            if await publish_button.count() > 0:
                await publish_button.click(force=True, timeout=15000)

            await page.wait_for_timeout(500)
            confirm_button = page.get_by_text("确认发布")
            if await confirm_button.count() > 0:
                if await self._click_and_wait_for_url(
                    page, confirm_button, success_pattern, timeout=5000
                ):
                    logger.info("视频发布成功，已跳转到管理页面")
                    return True

        except Exception as e:
            logger.warning("发布视频时出错: %s", e)

        await page.wait_for_timeout(1000)
        retry_count += 1

    logger.error("超过最大重试次数，视频发布失败")
    return False


def _apply_patches():
    """Apply monkey-patches to KuaiShouUploader methods."""
    try:
        from spreado.plugins.kuaishou.uploader import KuaiShouUploader

        if hasattr(KuaiShouUploader, "_fill_video_info"):
            KuaiShouUploader._fill_video_info = _patched_fill_video_info
            logger.info(
                "Patch: KuaiShouUploader._fill_video_info -> evaluate focus + keyboard type"
            )

        if hasattr(KuaiShouUploader, "_set_thumbnail"):
            KuaiShouUploader._set_thumbnail = _patched_set_thumbnail
            logger.info(
                "Patch: KuaiShouUploader._set_thumbnail -> no-op (skip)"
            )

        if hasattr(KuaiShouUploader, "_publish_video"):
            KuaiShouUploader._publish_video = _patched_publish_video
            logger.info(
                "Patch: KuaiShouUploader._publish_video -> force=True on click"
            )
    except ImportError:
        pass  # spreado not installed, will be caught later


_apply_patches()


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
    upload_timeout: int = 600,
) -> dict[str, Any]:
    """Upload video to Kuaishou with a single browser session.

    Creates ONE browser for both cookie verification and upload, avoiding the
    double-browser-launch race that causes intermittent hangs in Spreado's
    upload_video_flow().

    Args:
        video_path: Absolute path to the MP4 video file.
        title: Video title.
        content: Video description.
        tags: Comma-separated tags.
        cover_path: Optional path to cover image.
        cookie_file_path: Path to the cookie file.
        upload_timeout: Max seconds to wait for upload (default 600s=10min).

    Returns:
        Dict with keys: success (bool), error (str|None), platform (str).
    """
    from spreado import PluginLoader
    from spreado.plugins.kuaishou.uploader import KuaiShouUploader

    loader = PluginLoader()
    loader.load()
    uploader: KuaiShouUploader = loader.get_publisher("kuaishou")

    # Override cookie path if specified
    if cookie_file_path is not None:
        uploader.cookie_file_path = cookie_file_path

    # Parse tags into list
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # Build thumbnail path
    thumb = Path(cover_path) if cover_path and os.path.isfile(cover_path) else None

    logger.info(
        "Uploading to Kuaishou via single-browser session ... "
        "cookie=%s, timeout=%ds",
        uploader.cookie_file_path,
        upload_timeout,
    )

    if not uploader.cookie_file_path.exists():
        return {
            "success": False,
            "platform": "kuaishou",
            "error": f"Cookie file not found: {uploader.cookie_file_path}",
        }

    try:
        async with await StealthBrowser.create(headless=True) as browser:
            await browser.load_cookies_from_file(uploader.cookie_file_path)
            async with await browser.new_page() as page:
                # Navigate to publish page
                logger.info("Navigating to Kuaishou publish page ...")
                await asyncio.wait_for(
                    page.goto(uploader.publish_url),
                    timeout=30,
                )

                # Inject MutationObserver to auto-remove react-joyride overlays
                await _inject_joyride_killer(page)

                # Quick cookie check: if login elements appear, cookie is bad
                if await uploader._check_login_required(page):
                    logger.warning(
                        "Cookie invalid (redirected to login). "
                        "Please re-login: spreado login kuaishou"
                    )
                    return {
                        "success": False,
                        "platform": "kuaishou",
                        "error": "cookie invalid",
                    }

                logger.info("Cookie valid, starting upload ...")

                # Upload with timeout
                ok = await asyncio.wait_for(
                    uploader._upload_video(
                        page=page,
                        file_path=video_path,
                        title=title,
                        content=content,
                        tags=tag_list,
                        thumbnail_path=thumb,
                    ),
                    timeout=upload_timeout,
                )

                if ok:
                    logger.info("Kuaishou upload successful!")
                    return {"success": True, "platform": "kuaishou", "error": None}
                else:
                    logger.warning("Kuaishou upload returned failure.")
                    return {
                        "success": False,
                        "platform": "kuaishou",
                        "error": "_upload_video returned False",
                    }
    except asyncio.TimeoutError:
        logger.warning("Kuaishou upload timed out after %d seconds.", upload_timeout)
        return {
            "success": False,
            "platform": "kuaishou",
            "error": f"upload timed out after {upload_timeout}s",
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
    upload_timeout: int = 600,
) -> dict[str, Any]:
    """Synchronous wrapper for async Kuaishou upload.

    Args:
        video_path: Absolute path to the MP4 video file.
        title: Video title.
        content: Video description.
        tags: Comma-separated tags.
        cover_path: Optional path to cover image.
        cookies_path: Path to the cookies directory or file.
        upload_timeout: Max seconds to wait for upload (default 600s=10min).

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
            upload_timeout=upload_timeout,
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
        upload_timeout = upload_cfg.get("timeout", 600)
        return upload_to_kuaishou(
            video_path=video_path,
            title=title,
            content=content,
            tags=tags,
            cover_path=cover_path,
            cookies_path=cookies_path,
            upload_timeout=upload_timeout,
        )
    else:
        return {"success": False, "error": f"Unsupported platform: {platform}"}
