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
# Kuaishou's publish page includes a react-joyride onboarding tour that renders
# overlays/spotlights in #react-joyride-portal, intercepting Playwright hit-tests.
# Fix: dismiss the joyride before all interactions, and use force=True on clicks
# to bypass any remaining overlay.  See: https://playwright.dev/docs/api/class-locator#locator-click-option-force


async def _dismiss_joyride(page) -> bool:
    """Remove the react-joyride portal from the DOM if present."""
    removed = await page.evaluate(
        """() => {
            const el = document.getElementById('react-joyride-portal');
            if (el) {
                el.remove();
                return true;
            }
            return false;
        }"""
    )
    if removed:
        logger.info("Dismissed react-joyride onboarding overlay.")
    return removed


async def _patched_fill_video_info(
    self, page, title: str = "", content: str = "", tags: list[str] | None = None
) -> bool:
    """Fixed version of KuaiShouUploader._fill_video_info.

    Uses force=True on the initial click to bypass floating overlays that
    intercept Playwright's hit-test on Kuaishou's publish page.
    """
    try:
        await _dismiss_joyride(page)
        await page.locator("#work-description-edit").click(force=True, timeout=15000)

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
    """Fixed version of KuaiShouUploader._set_thumbnail.

    Kuaishou's react-joyride onboarding tour overlays the '封面设置' button
    with spotlight/overlay divs that intercept Playwright's hit-test.
    Fix: dismiss the joyride and use force=True on all clicks.
    """
    if not thumbnail_path:
        logger.info("未指定封面路径，跳过封面设置")
        return True

    from pathlib import Path as _Path
    if not _Path(thumbnail_path).exists():
        logger.warning("封面文件不存在: %s，跳过封面设置", thumbnail_path)
        return True

    try:
        logger.info("正在设置视频封面...")

        await _dismiss_joyride(page)

        # Click "封面设置" button (force=True to bypass overlapping elements)
        cover_setting_button = page.get_by_text("封面设置").nth(1)
        await cover_setting_button.wait_for(state="visible", timeout=10000)
        await cover_setting_button.click(force=True, timeout=15000)
        logger.info("Clicked 封面设置")

        # Wait for the cover-upload modal
        await page.wait_for_selector(
            "div.ant-modal-body",
            timeout=10000,
            state="visible",
        )

        # Click "上传封面" button
        upload_cover_button = page.get_by_text("上传封面")
        await upload_cover_button.wait_for(state="visible", timeout=10000)
        await upload_cover_button.click(force=True, timeout=15000)
        logger.info("Clicked 上传封面")

        # Wait for and set the file input
        file_input_selector = "div[class*='upload'] input[type='file']"
        await page.wait_for_selector(
            file_input_selector, timeout=10000, state="attached"
        )
        file_input = page.locator(file_input_selector)
        await file_input.set_input_files(str(thumbnail_path))
        logger.info("封面图片已上传")

        # Wait for the confirm button and click it
        confirm_button = page.get_by_role("button", name="确认")
        await confirm_button.wait_for(state="visible", timeout=10000)
        await confirm_button.click(force=True, timeout=15000)
        logger.info("Clicked 确认")

        # Verify cover was set by checking the cover image URL changes
        # Re-locate the cover element
        cover_el = page.get_by_text("封面设置").nth(1)
        cover_img = cover_el.locator("xpath=following::img").first
        try:
            await cover_img.wait_for(state="visible", timeout=5000)
        except Exception:
            pass
        original_src = await cover_img.get_attribute("src") or ""

        for _ in range(20):
            await page.wait_for_timeout(500)
            current_src = await cover_img.get_attribute("src") or ""
            if current_src and current_src != original_src:
                logger.info("封面设置成功！")
                return True

        logger.warning("封面图片URL未发生变化，封面设置可能未成功")
        return False
    except Exception as e:
        logger.error("设置封面时出错: %s", e)
        return False


def _apply_patches():
    """Apply monkey-patches to KuaiShouUploader methods."""
    try:
        from spreado.plugins.kuaishou.uploader import KuaiShouUploader

        if hasattr(KuaiShouUploader, "_fill_video_info"):
            KuaiShouUploader._fill_video_info = _patched_fill_video_info
            logger.info(
                "Patch: KuaiShouUploader._fill_video_info -> force=True"
            )

        if hasattr(KuaiShouUploader, "_set_thumbnail"):
            KuaiShouUploader._set_thumbnail = _patched_set_thumbnail
            logger.info(
                "Patch: KuaiShouUploader._set_thumbnail -> dismiss joyride + force=True"
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
