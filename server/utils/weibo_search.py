from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote
import html
import re
import time

import requests


class ExternalSearchError(RuntimeError):
    pass


def _clean_text(s: str) -> str:
    return " ".join((s or "").replace("\u200b", " ").split()).strip()


def _strip_html(s: str) -> str:
    if not s:
        return ""
    # Weibo `text` fields often contain HTML tags.
    s = html.unescape(str(s))
    s = re.sub(r"<\s*br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return _clean_text(s)


def _cookies_to_header(cookies: Optional[List[Dict[str, Any]]]) -> str:
    if not cookies:
        return ""
    parts: List[str] = []
    for c in cookies:
        if not isinstance(c, dict):
            continue
        name = c.get("name")
        value = c.get("value")
        if not name or value is None:
            continue
        parts.append(f"{name}={value}")
    return "; ".join(parts)


def _filter_weibo_cn_cookies(cookies: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Keep only cookies relevant to the mobile domain.

    MediaCrawler explicitly uses cookies(urls=["https://m.weibo.cn"]) to avoid
    mixing PC and mobile cookies, which improves stability for m.weibo.cn APIs.
    """
    if not cookies:
        return []
    kept: List[Dict[str, Any]] = []
    for c in cookies:
        if not isinstance(c, dict):
            continue
        domain = str(c.get("domain") or "").lstrip(".")
        if not domain:
            continue
        if domain.endswith("weibo.cn"):
            kept.append(c)
    return kept


def _build_mobile_headers(cookie_header: str) -> Dict[str, str]:
    # Mobile UA tends to be more compatible with m.weibo.cn APIs than a desktop UA.
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        "Origin": "https://m.weibo.cn",
        "Referer": "https://m.weibo.cn/",
        "Content-Type": "application/json;charset=UTF-8",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    return headers


def _warm_up_mobile(session: requests.Session, *, timeout: float) -> None:
    """Touch m.weibo.cn once to refresh H5 cookies.

    This is a lightweight analogue of MediaCrawler's strategy: when search returns
    432/invalid JSON, navigate to the mobile homepage to refresh cookies, then retry.
    """
    try:
        session.get("https://m.weibo.cn/api/config", timeout=max(1.0, timeout))
    except Exception:
        pass


def _extract_from_mweibo_search(json_data: Dict[str, Any], results: List[Dict[str, Any]], *, limit: int) -> None:
    """Extract search results from `m.weibo.cn/api/container/getIndex` response."""
    data = json_data.get("data") or {}
    cards = data.get("cards") or []
    for card in cards:
        if len(results) >= limit:
            return
        if not isinstance(card, dict):
            continue
        # Search results are typically grouped in `card_group`.
        groups = card.get("card_group")
        if isinstance(groups, list):
            for g in groups:
                if len(results) >= limit:
                    return
                if not isinstance(g, dict):
                    continue
                if g.get("card_type") != 9:
                    continue
                mblog = g.get("mblog") or {}
                mid = mblog.get("mid") or mblog.get("id")
                raw_text = mblog.get("text") or ""
                text = _strip_html(raw_text)
                user = (mblog.get("user") or {})
                author = _clean_text(user.get("screen_name") or "")
                url = f"https://m.weibo.cn/detail/{mid}" if mid else None
                if not text and not url:
                    continue
                results.append(
                    {
                        "title": (text[:80] + "…") if len(text) > 80 else text,
                        "text": text,
                        "author": author,
                        "url": url,
                        "source": "weibo",
                    }
                )
        else:
            # Some cards are directly a feed item.
            if card.get("card_type") != 9:
                continue
            mblog = card.get("mblog") or {}
            mid = mblog.get("mid") or mblog.get("id")
            raw_text = mblog.get("text") or ""
            text = _strip_html(raw_text)
            user = (mblog.get("user") or {})
            author = _clean_text(user.get("screen_name") or "")
            url = f"https://m.weibo.cn/detail/{mid}" if mid else None
            if not text and not url:
                continue
            results.append(
                {
                    "title": (text[:80] + "…") if len(text) > 80 else text,
                    "text": text,
                    "author": author,
                    "url": url,
                    "source": "weibo",
                }
            )


def search_weibo(
    keyword: str,
    *,
    limit: int = 5,
    cookies: Optional[List[Dict[str, Any]]] = None,
    timeout_sec: float = 20.0,
) -> List[Dict[str, Any]]:
    """Search Weibo via a real browser (Playwright) and extract top results."""

    q = (keyword or "").strip()
    if not q:
        return []

    limit_i = max(1, min(int(limit or 5), 30))
    timeout_sec_f = max(3.0, float(timeout_sec))
    deadline = time.monotonic() + timeout_sec_f

    def _remaining_sec() -> float:
        return max(0.0, deadline - time.monotonic())

    timeout_ms = int(timeout_sec_f * 1000)

    try:
        # 1) Prefer mobile API (MediaCrawler-like). Much less likely to hit s.weibo.com captcha.
        # NOTE: Some environments receive HTML/empty payloads even with HTTP 200.
        # In those cases we should fall back to Playwright instead of hard-failing.
        results: List[Dict[str, Any]] = []

        mobile_cookies = _filter_weibo_cn_cookies(cookies)
        cookie_header = _cookies_to_header(mobile_cookies)
        headers = _build_mobile_headers(cookie_header)

        session = requests.Session()
        session.headers.update(headers)
        # Load cookies into a real cookie jar so Set-Cookie updates are retained.
        for c in mobile_cookies:
            try:
                session.cookies.set(
                    name=str(c.get("name")),
                    value=str(c.get("value")),
                    domain=str(c.get("domain")) or None,
                    path=str(c.get("path")) or "/",
                )
            except Exception:
                continue

        # `containerid` format comes from Weibo mobile search.
        containerid = f"100103type=1&q={q}"
        # Each mobile search page is ~10 items. Limit pages based on desired count.
        # Each page is ~10 items; keep pagination bounded for responsiveness.
        max_pages = min(3, max(1, (limit_i + 9) // 10 + 1))
        mobile_api_hard_failed = False
        warmed_once = False

        # Warm up once up-front if we still have enough budget.
        remaining = _remaining_sec()
        if remaining > 1.5:
            _warm_up_mobile(session, timeout=min(2.5, remaining))
            warmed_once = True

        for page in range(1, max_pages + 1):
            if len(results) >= limit_i:
                break

            remaining = _remaining_sec()
            if remaining <= 0.0:
                mobile_api_hard_failed = True
                break

            before_len = len(results)
            params = {
                "containerid": containerid,
                "page_type": "searchall",
                "page": page,
            }

            resp = session.get(
                "https://m.weibo.cn/api/container/getIndex",
                params=params,
                timeout=min(4.0, max(1.0, remaining)),
            )

            # Some environments return 432 with non-JSON bodies; refresh H5 cookies once then retry.
            if resp.status_code == 432 and not warmed_once and _remaining_sec() > 1.5:
                _warm_up_mobile(session, timeout=min(2.5, _remaining_sec()))
                warmed_once = True
                resp = session.get(
                    "https://m.weibo.cn/api/container/getIndex",
                    params=params,
                    timeout=min(4.0, max(1.0, _remaining_sec())),
                )
            if resp.status_code in (418, 432, 403):
                raise ExternalSearchError(
                    "微博搜索被风控/需要登录：请先在详情页点“微博-登录”，完成登录后再刷新；若仍提示风控，通常需要验证码或更换网络"
                )
            if resp.status_code != 200:
                raise ExternalSearchError(f"微博搜索失败：HTTP {resp.status_code}")

            try:
                data = resp.json()
            except Exception:
                # Try one cookie refresh then retry once.
                if not warmed_once and _remaining_sec() > 1.5:
                    _warm_up_mobile(session, timeout=min(2.5, _remaining_sec()))
                    warmed_once = True
                    try:
                        resp = session.get(
                            "https://m.weibo.cn/api/container/getIndex",
                            params=params,
                            timeout=min(4.0, max(1.0, _remaining_sec())),
                        )
                        data = resp.json()
                    except Exception:
                        mobile_api_hard_failed = True
                        break
                else:
                    mobile_api_hard_failed = True
                    break

            if int(data.get("ok") or 0) != 1:
                # If mobile API returns ok=0, try refreshing H5 cookies once; otherwise fall back.
                if not warmed_once and _remaining_sec() > 1.5:
                    _warm_up_mobile(session, timeout=min(2.5, _remaining_sec()))
                    warmed_once = True
                    try:
                        resp = session.get(
                            "https://m.weibo.cn/api/container/getIndex",
                            params=params,
                            timeout=min(4.0, max(1.0, _remaining_sec())),
                        )
                        data = resp.json()
                    except Exception:
                        mobile_api_hard_failed = True
                        break
                    if int(data.get("ok") or 0) != 1:
                        mobile_api_hard_failed = True
                        break
                else:
                    mobile_api_hard_failed = True
                    break

            _extract_from_mweibo_search(data, results, limit=limit_i)

            # stop early if no new items were extracted
            if len(results) == before_len:
                break

            # stop early if no cards
            cards = (data.get("data") or {}).get("cards")
            if not cards:
                break

        if results:
            return results[:limit_i]

        # If mobile API hard-failed, try the Playwright fallback instead of raising.
        # (Playwright uses a browser context and can sometimes pass where requests can't.)
        _ = mobile_api_hard_failed

        # 2) Fallback to Playwright page parsing.
        from playwright.sync_api import TimeoutError as PWTimeoutError
        from playwright.sync_api import sync_playwright

        remaining = _remaining_sec()
        if remaining < 2.5:
            raise ExternalSearchError("微博搜索超时（可能被风控/需要登录/网络不佳），请稍后重试或更换网络")

        with sync_playwright() as p:
            remaining_ms = int(max(1000.0, _remaining_sec() * 1000.0))
            browser = p.chromium.launch(headless=True, timeout=remaining_ms)
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=headers["User-Agent"],
                locale="zh-CN",
            )

            if cookies:
                try:
                    context.add_cookies(cookies)
                except Exception:
                    pass

            page = context.new_page()
            url = f"https://s.weibo.com/weibo?q={quote(q)}"
            try:
                remaining_ms = int(max(1000.0, _remaining_sec() * 1000.0))
                page.goto(url, wait_until="domcontentloaded", timeout=remaining_ms)
            except PWTimeoutError:
                raise ExternalSearchError("微博搜索超时（可能被风控/需要登录/网络不佳），请稍后重试或更换网络")

            try:
                remaining_ms = int(max(1000.0, _remaining_sec() * 1000.0))
                page.wait_for_selector("div.card-wrap", timeout=remaining_ms)
            except PWTimeoutError:
                html_text = page.content()
                if "验证" in html_text or "captcha" in html_text:
                    raise ExternalSearchError(
                        "微博触发验证/风控：建议先用移动端接口（点登录后重试）；若仍不行，通常需要验证码或更换网络"
                    )
                raise ExternalSearchError("微博搜索页面未出现结果列表（可能被风控/需要登录）")

            wraps = page.locator("div.card-wrap")
            results2: List[Dict[str, Any]] = []

            for i in range(wraps.count()):
                if len(results2) >= limit_i:
                    break

                card = wraps.nth(i)
                try:
                    if card.get_attribute("action-type") != "feed_list_item":
                        continue
                except Exception:
                    pass

                text = ""
                author = ""
                post_url = None

                try:
                    text = _clean_text(card.locator("p.txt").first.inner_text(timeout=800))
                except Exception:
                    text = ""

                try:
                    a = card.locator("a.name").first
                    author = _clean_text(a.get_attribute("nick-name") or a.inner_text(timeout=600))
                except Exception:
                    author = ""

                try:
                    a2 = card.locator("p.from a").first
                    post_url = a2.get_attribute("href")
                    if post_url and post_url.startswith("/"):
                        post_url = "https://s.weibo.com" + post_url
                except Exception:
                    post_url = None

                if not text and not post_url:
                    continue

                results2.append(
                    {
                        "title": (text[:80] + "…") if len(text) > 80 else text,
                        "text": text,
                        "author": author,
                        "url": post_url,
                        "source": "weibo",
                    }
                )

            try:
                browser.close()
            except Exception:
                pass

            return results2

    except ExternalSearchError:
        raise
    except Exception as e:
        raise ExternalSearchError(f"微博搜索失败：{e}")
