from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence, TypeVar

import anyio
from mcp.server.fastmcp import FastMCP

from xhs_mcp.configs import get_chrome_executable, get_cookies_path
from xhs_mcp.infra.browser import launch, new_context, pw
from xhs_mcp.infra.cookies import save_storage_state
from xhs_mcp.xhs.base import ActionContext
from xhs_mcp.xhs.comment import CommentAction
from xhs_mcp.xhs.feed_detail import FeedDetailAction
from xhs_mcp.xhs.feeds import Feed, FeedsListAction, SearchAction
from xhs_mcp.xhs.like_favorite import FavoriteAction, LikeAction
from xhs_mcp.xhs.login import check_login_status, fetch_qrcode_image, wait_for_login
from xhs_mcp.xhs.publish import (
    PublishImageAction,
    PublishImageContent,
    PublishVideoAction,
    PublishVideoContent,
)
from xhs_mcp.xhs.user_profile import UserProfileAction

from scripts import clean_array

T = TypeVar("T")


@dataclass
class ServerDefaults:
    profile: str | None = None
    cookies_path: str | None = None
    chrome_bin: str | None = None
    debug_dir: Path | None = None
    trace: bool = False


DEFAULTS = ServerDefaults()


def configure_defaults(
    *,
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | Path | None = None,
    trace: bool | None = None,
) -> None:
    """Allow CLI to set fallback values for tool parameters."""

    if profile is not None:
        DEFAULTS.profile = profile
    if cookies_path is not None:
        DEFAULTS.cookies_path = cookies_path
    if chrome_bin is not None:
        DEFAULTS.chrome_bin = chrome_bin
    if debug_dir is not None:
        DEFAULTS.debug_dir = _normalize_debug_dir(debug_dir)
    if trace is not None:
        DEFAULTS.trace = trace


def _normalize_debug_dir(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    return Path(value).expanduser().resolve()


def _resolve_bool(value: bool | None, default: bool) -> bool:
    return default if value is None else bool(value)


def _effective_str(provided: str | None, fallback: str | None) -> str | None:
    return provided if provided is not None else fallback


def _resolve_invocation_args(
    profile: str | None,
    cookies_path: str | None,
    chrome_bin: str | None,
    debug_dir: str | None,
    trace: bool | None,
) -> tuple[str | None, str | None, str | None, Path | None, bool]:
    profile_eff = _effective_str(profile, DEFAULTS.profile)
    cookies_eff = _effective_str(cookies_path, DEFAULTS.cookies_path)
    chrome_eff = _effective_str(chrome_bin, DEFAULTS.chrome_bin)
    debug_eff = _normalize_debug_dir(debug_dir) if debug_dir is not None else DEFAULTS.debug_dir
    trace_eff = _resolve_bool(trace, DEFAULTS.trace)
    return profile_eff, cookies_eff, chrome_eff, debug_eff, trace_eff


def _run_with_page_sync(
    *,
    profile: str | None,
    cookies_path: str | None,
    chrome_bin: str | None,
    debug_dir: Path | None,
    trace: bool,
    handler: Callable[[ActionContext, Path], T],
) -> T:
    cookies_file = get_cookies_path(cookies_path, profile)
    chrome_exe = get_chrome_executable(chrome_bin)

    debug_dir_path = debug_dir
    console_logs: list[str] = []

    with pw() as playwright:
        with launch(playwright, chrome_bin=chrome_exe) as browser:
            with new_context(browser, cookies_file) as context:
                if trace and debug_dir_path:
                    context.tracing.start(screenshots=True, snapshots=True, sources=True)

                page = context.new_page()

                if debug_dir_path is not None:
                    page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

                try:
                    return handler(ActionContext(page), cookies_file)
                finally:
                    if debug_dir_path is not None:
                        debug_dir_path.mkdir(parents=True, exist_ok=True)
                        (debug_dir_path / "dom.html").write_text(page.content(), encoding="utf-8")

                        screenshot_path = debug_dir_path / "page.png"
                        try:
                            page.screenshot(path=str(screenshot_path), full_page=True)
                        except Exception as exc:
                            (debug_dir_path / "screenshot-error.log").write_text(str(exc), encoding="utf-8")

                        (debug_dir_path / "console.log").write_text("\n".join(console_logs), encoding="utf-8")

                    if trace and debug_dir_path:
                        trace_path = debug_dir_path / "trace.zip"
                        context.tracing.stop(path=str(trace_path))


async def _run_with_page(
    *,
    profile: str | None,
    cookies_path: str | None,
    chrome_bin: str | None,
    debug_dir: Path | None,
    trace: bool,
    handler: Callable[[ActionContext, Path], T],
) -> T:
    return await anyio.to_thread.run_sync(
        partial(
            _run_with_page_sync,
            profile=profile,
            cookies_path=cookies_path,
            chrome_bin=chrome_bin,
            debug_dir=debug_dir,
            trace=trace,
            handler=handler,
        )
    )


mcp = FastMCP("Xiaohongshu")


@mcp.tool()
async def feeds_list(
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> list[dict[str, Any]]:
    """Fetch homepage feed entries.使用前请先登录，无需要其他参数"""

    profile_eff, cookies_eff, chrome_eff, debug_eff, trace_eff = _resolve_invocation_args(
        profile, cookies_path, chrome_bin, debug_dir, trace
    )

    def handler(ctx: ActionContext, _cookies: Path) -> list[dict[str, Any]]:
        action = FeedsListAction(ctx)
        feeds: list[Feed] = action.get_feeds()
        return clean_array.clean_xsec_tokens([feed.raw for feed in feeds])

    return await _run_with_page(
        profile=profile_eff,
        cookies_path=cookies_eff,
        chrome_bin=chrome_eff,
        debug_dir=debug_eff,
        trace=trace_eff,
        handler=handler,
    )


@mcp.tool()
async def search_feeds(
    keyword: str,
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> list[dict[str, Any]]:
    """Search feeds for a keyword."""

    profile_eff, cookies_eff, chrome_eff, debug_eff, trace_eff = _resolve_invocation_args(
        profile, cookies_path, chrome_bin, debug_dir, trace
    )

    def handler(ctx: ActionContext, _cookies: Path) -> list[dict[str, Any]]:
        action = SearchAction(ctx)
        feeds = action.search(keyword)
        return clean_array.clean_xsec_tokens([feed.raw for feed in feeds])

    return await _run_with_page(
        profile=profile_eff,
        cookies_path=cookies_eff,
        chrome_bin=chrome_eff,
        debug_dir=debug_eff,
        trace=trace_eff,
        handler=handler,
    )


@mcp.tool()
async def feed_detail(
    feed_id: str,
    xsec_token: str,
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> dict[str, Any]:
    """Return note detail and comments."""

    profile_eff, cookies_eff, chrome_eff, debug_eff, trace_eff = _resolve_invocation_args(
        profile, cookies_path, chrome_bin, debug_dir, trace
    )

    def handler(ctx: ActionContext, _cookies: Path) -> dict[str, Any]:
        action = FeedDetailAction(ctx)
        detail = action.get_detail(feed_id, xsec_token)
        return {"note": detail.data, "comments": detail.comments}

    return await _run_with_page(
        profile=profile_eff,
        cookies_path=cookies_eff,
        chrome_bin=chrome_eff,
        debug_dir=debug_eff,
        trace=trace_eff,
        handler=handler,
    )


def _normalize_tags(tags: Iterable[str] | None) -> list[str]:
    if not tags:
        return []
    return [tag.lstrip("#") for tag in tags if tag]


@mcp.tool()
async def publish_image(
    title: str,
    content: str,
    image_paths: Sequence[str],
    tags: Sequence[str] | None = None,
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> dict[str, str]:
    """Publish an image note."""

    if not image_paths:
        raise ValueError("image_paths must contain at least one file")

    profile_eff, cookies_eff, chrome_eff, debug_eff, trace_eff = _resolve_invocation_args(
        profile, cookies_path, chrome_bin, debug_dir, trace
    )

    normalized_tags = _normalize_tags(tags)
    normalized_images = [str(Path(path).expanduser()) for path in image_paths]

    def handler(ctx: ActionContext, _cookies: Path) -> dict[str, str]:
        action = PublishImageAction(ctx)
        payload = PublishImageContent(
            title=title,
            content=content,
            image_paths=normalized_images,
            tags=normalized_tags,
        )
        action.publish(payload)
        return {"status": "submitted"}

    return await _run_with_page(
        profile=profile_eff,
        cookies_path=cookies_eff,
        chrome_bin=chrome_eff,
        debug_dir=debug_eff,
        trace=trace_eff,
        handler=handler,
    )


@mcp.tool()
async def publish_video(
    title: str,
    content: str,
    video_path: str,
    tags: Sequence[str] | None = None,
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> dict[str, str]:
    """Publish a video note."""

    profile_eff, cookies_eff, chrome_eff, debug_eff, trace_eff = _resolve_invocation_args(
        profile, cookies_path, chrome_bin, debug_dir, trace
    )

    normalized_tags = _normalize_tags(tags)
    normalized_video = str(Path(video_path).expanduser())

    def handler(ctx: ActionContext, _cookies: Path) -> dict[str, str]:
        action = PublishVideoAction(ctx)
        payload = PublishVideoContent(
            title=title,
            content=content,
            video_path=normalized_video,
            tags=normalized_tags,
        )
        action.publish(payload)
        return {"status": "submitted"}

    return await _run_with_page(
        profile=profile_eff,
        cookies_path=cookies_eff,
        chrome_bin=chrome_eff,
        debug_dir=debug_eff,
        trace=trace_eff,
        handler=handler,
    )


@mcp.tool()
async def post_comment(
    feed_id: str,
    xsec_token: str,
    content: str,
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> dict[str, str]:
    """Post a comment under a feed."""

    profile_eff, cookies_eff, chrome_eff, debug_eff, trace_eff = _resolve_invocation_args(
        profile, cookies_path, chrome_bin, debug_dir, trace
    )

    def handler(ctx: ActionContext, _cookies: Path) -> dict[str, str]:
        action = CommentAction(ctx)
        action.post_comment(feed_id, xsec_token, content)
        return {"status": "submitted"}

    return await _run_with_page(
        profile=profile_eff,
        cookies_path=cookies_eff,
        chrome_bin=chrome_eff,
        debug_dir=debug_eff,
        trace=trace_eff,
        handler=handler,
    )


async def _interact_common(
    *,
    feed_id: str,
    xsec_token: str,
    profile: str | None,
    cookies_path: str | None,
    chrome_bin: str | None,
    debug_dir: str | None,
    trace: bool | None,
    executor: Callable[[ActionContext], None],
) -> dict[str, str]:
    profile_eff, cookies_eff, chrome_eff, debug_eff, trace_eff = _resolve_invocation_args(
        profile, cookies_path, chrome_bin, debug_dir, trace
    )

    def handler(ctx: ActionContext, _cookies: Path) -> dict[str, str]:
        executor(ctx)
        return {"status": "submitted"}

    return await _run_with_page(
        profile=profile_eff,
        cookies_path=cookies_eff,
        chrome_bin=chrome_eff,
        debug_dir=debug_eff,
        trace=trace_eff,
        handler=handler,
    )


@mcp.tool()
async def like_feed(
    feed_id: str,
    xsec_token: str,
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> dict[str, str]:
    """Like a feed."""

    return await _interact_common(
        feed_id=feed_id,
        xsec_token=xsec_token,
        profile=profile,
        cookies_path=cookies_path,
        chrome_bin=chrome_bin,
        debug_dir=debug_dir,
        trace=trace,
        executor=lambda ctx: LikeAction(ctx).like(feed_id, xsec_token),
    )


@mcp.tool()
async def unlike_feed(
    feed_id: str,
    xsec_token: str,
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> dict[str, str]:
    """Cancel a like."""

    return await _interact_common(
        feed_id=feed_id,
        xsec_token=xsec_token,
        profile=profile,
        cookies_path=cookies_path,
        chrome_bin=chrome_bin,
        debug_dir=debug_dir,
        trace=trace,
        executor=lambda ctx: LikeAction(ctx).unlike(feed_id, xsec_token),
    )


@mcp.tool()
async def favorite_feed(
    feed_id: str,
    xsec_token: str,
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> dict[str, str]:
    """Collect a feed."""

    return await _interact_common(
        feed_id=feed_id,
        xsec_token=xsec_token,
        profile=profile,
        cookies_path=cookies_path,
        chrome_bin=chrome_bin,
        debug_dir=debug_dir,
        trace=trace,
        executor=lambda ctx: FavoriteAction(ctx).favorite(feed_id, xsec_token),
    )


@mcp.tool()
async def unfavorite_feed(
    feed_id: str,
    xsec_token: str,
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> dict[str, str]:
    """Cancel a collect."""

    return await _interact_common(
        feed_id=feed_id,
        xsec_token=xsec_token,
        profile=profile,
        cookies_path=cookies_path,
        chrome_bin=chrome_bin,
        debug_dir=debug_dir,
        trace=trace,
        executor=lambda ctx: FavoriteAction(ctx).unfavorite(feed_id, xsec_token),
    )


@mcp.tool()
async def user_profile(
    user_id: str,
    xsec_token: str,
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> dict[str, Any]:
    """Fetch user profile information."""

    profile_eff, cookies_eff, chrome_eff, debug_eff, trace_eff = _resolve_invocation_args(
        profile, cookies_path, chrome_bin, debug_dir, trace
    )

    def handler(ctx: ActionContext, _cookies: Path) -> dict[str, Any]:
        action = UserProfileAction(ctx)
        profile_data = action.user_profile(user_id, xsec_token)
        return {
            "basic_info": profile_data.basic_info,
            "interactions": profile_data.interactions,
            "feeds": profile_data.feeds,
        }

    return await _run_with_page(
        profile=profile_eff,
        cookies_path=cookies_eff,
        chrome_bin=chrome_eff,
        debug_dir=debug_eff,
        trace=trace_eff,
        handler=handler,
    )


@mcp.tool()
async def my_profile(
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> dict[str, Any]:
    """Fetch currently logged-in user's profile."""

    profile_eff, cookies_eff, chrome_eff, debug_eff, trace_eff = _resolve_invocation_args(
        profile, cookies_path, chrome_bin, debug_dir, trace
    )

    def handler(ctx: ActionContext, _cookies: Path) -> dict[str, Any]:
        action = UserProfileAction(ctx)
        profile_data = action.get_my_profile_via_sidebar()
        return {
            "basic_info": profile_data.basic_info,
            "interactions": profile_data.interactions,
            "feeds": profile_data.feeds,
        }

    return await _run_with_page(
        profile=profile_eff,
        cookies_path=cookies_eff,
        chrome_bin=chrome_eff,
        debug_dir=debug_eff,
        trace=trace_eff,
        handler=handler,
    )


@mcp.tool()
async def check_login(
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> dict[str, bool]:
    """Check if current cookies correspond to a logged-in session."""

    profile_eff, cookies_eff, chrome_eff, debug_eff, trace_eff = _resolve_invocation_args(
        profile, cookies_path, chrome_bin, debug_dir, trace
    )

    def handler(ctx: ActionContext, _cookies: Path) -> dict[str, bool]:
        logged = check_login_status(ctx.page)
        return {"logged_in": logged}

    return await _run_with_page(
        profile=profile_eff,
        cookies_path=cookies_eff,
        chrome_bin=chrome_eff,
        debug_dir=debug_eff,
        trace=trace_eff,
        handler=handler,
    )


@mcp.tool()
async def get_login_qrcode(
    timeout: int = 240,
    poll_interval: float = 0.5,
    reload_interval: float = 10.0,
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> dict[str, Any]:
    """Fetch login QR code image source."""

    profile_eff, cookies_eff, chrome_eff, debug_eff, trace_eff = _resolve_invocation_args(
        profile, cookies_path, chrome_bin, debug_dir, trace
    )

    def handler(ctx: ActionContext, _cookies: Path) -> dict[str, Any]:
        src, logged = fetch_qrcode_image(
            ctx.page,
            timeout_seconds=timeout,
            poll_interval=poll_interval,
            reload_interval=reload_interval,
            verbose=False,
        )
        return {"logged_in": logged, "qrcode": src}

    return await _run_with_page(
        profile=profile_eff,
        cookies_path=cookies_eff,
        chrome_bin=chrome_eff,
        debug_dir=debug_eff,
        trace=trace_eff,
        handler=handler,
    )


@mcp.tool()
async def wait_for_login_complete(
    timeout: int = 240,
    poll_interval: float = 0.5,
    profile: str | None = None,
    cookies_path: str | None = None,
    chrome_bin: str | None = None,
    debug_dir: str | None = None,
    trace: bool | None = None,
) -> dict[str, Any]:
    """Wait for QR login to succeed and persist cookies."""

    profile_eff, cookies_eff, chrome_eff, debug_eff, trace_eff = _resolve_invocation_args(
        profile, cookies_path, chrome_bin, debug_dir, trace
    )

    def handler(ctx: ActionContext, cookies_file: Path) -> dict[str, Any]:
        success = wait_for_login(
            ctx.page,
            timeout_seconds=timeout,
            poll_interval=poll_interval,
            verbose=False,
        )
        if not success:
            raise RuntimeError("Login timed out.")
        state = ctx.page.context.storage_state()
        save_storage_state(cookies_file, state)
        return {"status": "logged_in", "cookies_path": str(cookies_file)}

    return await _run_with_page(
        profile=profile_eff,
        cookies_path=cookies_eff,
        chrome_bin=chrome_eff,
        debug_dir=debug_eff,
        trace=trace_eff,
        handler=handler,
    )


def create_server() -> FastMCP:
    """Return the configured FastMCP server instance."""

    return mcp
