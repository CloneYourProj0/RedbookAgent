from __future__ import annotations

from playwright.sync_api import Page, TimeoutError

from .base import PlaywrightAction


class CommentAction(PlaywrightAction):
    def post_comment(self, feed_id: str, xsec_token: str, content: str) -> None:
        page: Page = self.page
        url = f"https://www.xiaohongshu.com/explore/{feed_id}?xsec_token={xsec_token}&xsec_source=pc_feed"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2_000)

        editor = self._locate_editor(page)
        editor.click()
        editor.fill("")
        editor.type(content)

        submit = self._locate_submit(page)
        submit.click()
        page.wait_for_timeout(1_000)

    def _locate_editor(self, page: Page):
        selectors = [
            "div.input-box div.content-edit p.content-input",
            "div.input-box div.content-edit span",
            "textarea",
            "div[contenteditable='true']",
        ]
        last_error: TimeoutError | None = None
        for selector in selectors:
            locator = page.locator(selector)
            if locator.count() == 0:
                continue
            try:
                locator.first.wait_for(state="visible", timeout=30_000)
                return locator.first
            except TimeoutError as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        raise TimeoutError("Comment editor not found")

    def _locate_submit(self, page: Page):
        candidates = [
            "div.bottom button.submit",
            "button:has-text('发送')",
            "button:has-text('评论')",
        ]
        for selector in candidates:
            locator = page.locator(selector)
            if locator.count() == 0:
                continue
            try:
                locator.first.wait_for(state="attached", timeout=10_000)
                return locator.first
            except TimeoutError:
                continue
        fallback = page.locator("button")
        if fallback.count() == 0:
            raise TimeoutError("Comment submit button not found")
        fallback.first.wait_for(state="attached", timeout=5_000)
        return fallback.first
