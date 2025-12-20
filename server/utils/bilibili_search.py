from __future__ import annotations

from typing import Any, Dict, List, Optional
import html
import json
import re
from urllib.parse import quote

import requests


class ExternalSearchError(RuntimeError):
    pass


def _get_code(payload: Dict[str, Any]) -> int:
    """B站 JSON 通常为 {code: 0, message: '0'}，注意 code=0 是合法值。"""
    try:
        code = payload.get("code")
        return int(code) if code is not None else -1
    except Exception:
        return -1


def _clean_text(s: str) -> str:
    return " ".join((s or "").replace("\u200b", " ").split()).strip()


def _strip_html(s: str) -> str:
    if not s:
        return ""
    s = html.unescape(str(s))
    s = re.sub(r"<\s*br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return _clean_text(s)


def _normalize_url(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    u = str(u)
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://"):]
    return u


def _normalize_article_html(content_html: str) -> str:
    """Normalize common Bilibili article HTML image URL patterns.

    Fixes cases like src="//i0.hdslb.com/..." or src="http://..." which can lead
    to mixed-content blocks or 404s in the browser.
    """
    if not content_html:
        return ""
    s = str(content_html)
    # Normalize protocol-relative and http URLs.
    s = re.sub(r"\bsrc=(['\"])//", r"src=\1https://", s, flags=re.I)
    s = re.sub(r"\bdata-src=(['\"])//", r"data-src=\1https://", s, flags=re.I)
    s = re.sub(r"\bsrc=(['\"])http://", r"src=\1https://", s, flags=re.I)
    s = re.sub(r"\bdata-src=(['\"])http://", r"data-src=\1https://", s, flags=re.I)
    return s


def _try_delta_json_to_html(content_like: str) -> Optional[str]:
    """Convert Bilibili article delta JSON (Quill-like ops/insert) to HTML.

    Some endpoints may return content as a JSON string like {"ops":[{"insert":"...\n"}]}
    instead of HTML. In that case we convert it to safe HTML with <br> line breaks.
    """
    if not content_like:
        return None

    s = str(content_like).strip()
    if not (s.startswith("{") and "\"ops\"" in s and "\"insert\"" in s):
        return None

    try:
        payload = json.loads(s)
    except Exception:
        return None

    ops = payload.get("ops") if isinstance(payload, dict) else None
    if not isinstance(ops, list) or not ops:
        return None

    parts: List[str] = []
    for op in ops:
        if not isinstance(op, dict):
            continue
        ins = op.get("insert")
        if isinstance(ins, str) and ins:
            parts.append(ins)

    if not parts:
        return None

    text = "".join(parts)
    safe = html.escape(text)
    # Preserve line breaks for display.
    safe = safe.replace("\r\n", "\n").replace("\r", "\n")
    return safe.replace("\n", "<br/>")


def _normalize_article_content(content_html: str) -> str:
    """Normalize Bilibili article content to browser-friendly HTML."""
    if not content_html:
        return ""
    converted = _try_delta_json_to_html(content_html)
    s = converted if converted is not None else str(content_html)
    return _normalize_article_html(s)


def get_bilibili_article(
    article_id: int,
    *,
    timeout_sec: float = 15.0,
    cookie_header: str = "",
) -> Dict[str, Any]:
    """Fetch a single Bilibili article (专栏) by cv id.

    Returns: {title, author, url, text, content_html, images, source}
    """
    aid = int(article_id)
    timeout_sec_f = max(3.0, float(timeout_sec))
    session = _requests_session(cookie_header=cookie_header)

    # Warm-up to improve success rate under some networks.
    try:
        session.get("https://www.bilibili.com", timeout=min(6.0, timeout_sec_f))
    except Exception:
        pass

    detail = _try_fetch_article_content_via_api(session, aid, timeout_sec=min(10.0, timeout_sec_f))
    if not detail:
        detail = _try_fetch_article_content_via_web(session, aid, timeout_sec=min(12.0, timeout_sec_f))
    if not detail:
        raise ExternalSearchError("B站专栏详情获取失败（可能被拦截/限流），请稍后重试")

    url = f"https://www.bilibili.com/read/cv{aid}"
    content_html = _normalize_article_content(str(detail.get("content_html") or ""))
    images = [u for u in (_normalize_url(x) for x in (detail.get("images") or [])) if u]
    text_plain = _strip_html(content_html) if content_html else _strip_html(detail.get("text") or "")

    return {
        "source": "bilibili",
        "title": _strip_html(detail.get("title") or ""),
        "author": _strip_html(detail.get("author") or ""),
        "url": url,
        "text": text_plain,
        "content_html": content_html,
        "images": images,
    }


def _extract_images_from_html(content_html: str, *, limit: int = 30) -> List[str]:
    if not content_html:
        return []
    urls: List[str] = []
    for m in re.finditer(r"<img[^>]+src=['\"]([^'\"]+)['\"][^>]*>", content_html, flags=re.I):
        if len(urls) >= limit:
            break
        u = _normalize_url(m.group(1))
        if not u:
            continue
        if u not in urls:
            urls.append(u)
    return urls


def _requests_session(*, cookie_header: str = "") -> requests.Session:
    s = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    s.headers.update(headers)
    return s


def _try_fetch_article_content_via_api(session: requests.Session, article_id: int, *, timeout_sec: float) -> Optional[Dict[str, Any]]:
    """Best-effort: fetch article HTML via public bilibili API.

    Returns a dict with keys: content_html, text_plain, images, author, title, url.
    """
    endpoints = [
        "https://api.bilibili.com/x/article/view",
        "https://api.bilibili.com/x/article/viewinfo",
    ]

    for url in endpoints:
        try:
            resp = session.get(url, params={"id": int(article_id)}, timeout=timeout_sec)
        except Exception:
            continue
        if resp.status_code != 200:
            continue
        try:
            payload = resp.json()
        except Exception:
            continue
        if _get_code(payload) != 0:
            continue
        data = payload.get("data") or {}

        content_html = data.get("content") or data.get("article") or ""
        if isinstance(content_html, dict):
            content_html = content_html.get("content") or ""
        content_html = str(content_html or "")
        converted = _try_delta_json_to_html(content_html)
        if converted is not None:
            content_html = converted
        if not content_html:
            continue

        title = _strip_html(data.get("title") or "")

        raw_author = data.get("author_name") or data.get("author") or ""
        if isinstance(raw_author, dict):
            raw_author = raw_author.get("name") or raw_author.get("uname") or raw_author.get("author_name") or ""
        author = _strip_html(raw_author)
        images = _extract_images_from_html(content_html)
        text_plain = _strip_html(content_html)
        return {
            "title": title,
            "author": author,
            "content_html": content_html,
            "text": text_plain,
            "images": images,
        }

    return None


def _try_fetch_article_content_via_web(session: requests.Session, article_id: int, *, timeout_sec: float) -> Optional[Dict[str, Any]]:
    """Fallback: fetch https://www.bilibili.com/read/cv{id} and parse basic content."""
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return None

    url = f"https://www.bilibili.com/read/cv{int(article_id)}"
    try:
        resp = session.get(url, timeout=timeout_sec, headers={"Referer": "https://search.bilibili.com/"})
    except Exception:
        return None
    if resp.status_code != 200:
        return None

    html_text = resp.text or ""
    soup = BeautifulSoup(html_text, "html.parser")

    # Common containers for article body.
    body = (
        soup.select_one("div#article-content")
        or soup.select_one("div.article-content")
        or soup.select_one("div.article-holder")
        or soup.select_one("div.read-container")
    )
    if not body:
        return None

    content_html = str(body)
    images: List[str] = []
    for img in body.select("img"):
        u = _normalize_url(img.get("src") or img.get("data-src"))
        if not u:
            continue
        if u not in images:
            images.append(u)
        if len(images) >= 30:
            break

    text_plain = _clean_text(body.get_text("\n", strip=True))
    return {
        "content_html": content_html,
        "text": text_plain,
        "images": images,
    }


def search_bilibili_articles(
    keyword: str,
    *,
    limit: int = 5,
    timeout_sec: float = 15.0,
    cookie_header: str = "",
) -> List[Dict[str, Any]]:
    """Search Bilibili articles (专栏图文) by keyword.

    Implementation approach (MediaCrawler-like direction):
    - Prefer official/public JSON API for search.
    - Best-effort fetch full richtext HTML for top results (API first, web fallback).

    Returns items with: title, author, url, text, content_html, images, source.
    """

    q = (keyword or "").strip()
    if not q:
        return []

    limit_i = max(1, min(int(limit or 5), 5))
    timeout_sec_f = max(3.0, float(timeout_sec))

    session = _requests_session(cookie_header=cookie_header)

    # B站在部分网络/环境下会对直接调用 api.bilibili.com 触发 412。
    # 实测：先访问一次主站拿到基础 cookie（buvid3 等），再请求搜索 API，成功率会显著提升。
    try:
        session.get("https://www.bilibili.com", timeout=min(6.0, timeout_sec_f))
    except Exception:
        pass

    result: List[Dict[str, Any]] = []

    # 1) Prefer direct JSON API search (fast path). Some networks/IPs may trigger 412.
    search_url = "https://api.bilibili.com/x/web-interface/search/type"
    params = {
        "search_type": "article",
        "keyword": q,
        "page": 1,
        "page_size": max(10, limit_i),
        "order": "totalrank",
    }

    try:
        resp = session.get(
            search_url,
            params=params,
            timeout=min(timeout_sec_f, 10.0),
            headers={"Referer": f"https://search.bilibili.com/article?keyword={quote(q)}"},
        )
    except Exception as e:
        raise ExternalSearchError(f"B站搜索失败：{e}")

    if resp.status_code in (412, 418, 429, 403):
        raise ExternalSearchError("B站搜索被拦截/限流：请稍后重试或更换网络")

    if resp.status_code != 200:
        raise ExternalSearchError(f"B站搜索失败：HTTP {resp.status_code}")

    try:
        payload = resp.json()
    except Exception:
        raise ExternalSearchError("B站搜索失败：返回非 JSON（可能被拦截）")

    if _get_code(payload) != 0:
        msg = payload.get("message") or "未知错误"
        raise ExternalSearchError(f"B站搜索失败：{msg}")

    data = payload.get("data") or {}
    raw = data.get("result") or []
    if not isinstance(raw, list) or not raw:
        return []

    result = raw

    items: List[Dict[str, Any]] = []

    for r in result:
        if len(items) >= limit_i:
            break
        if not isinstance(r, dict):
            continue

        raw_id = r.get("id") or r.get("aid") or r.get("article_id")
        try:
            article_id = int(str(raw_id).lstrip("cv"))
        except Exception:
            continue

        title = _strip_html(r.get("title") or "")
        desc = _strip_html(r.get("desc") or r.get("description") or "")
        author = _strip_html(r.get("author") or r.get("uname") or "")
        url = r.get("arcurl") or r.get("url")
        if not url:
            url = f"https://www.bilibili.com/read/cv{article_id}"
        url = _normalize_url(url) or f"https://www.bilibili.com/read/cv{article_id}"

        cover = _normalize_url(r.get("pic"))

        content_detail = _try_fetch_article_content_via_api(session, article_id, timeout_sec=min(8.0, timeout_sec_f))
        if not content_detail:
            content_detail = _try_fetch_article_content_via_web(session, article_id, timeout_sec=min(10.0, timeout_sec_f))

        content_html = _normalize_article_content(str((content_detail or {}).get("content_html") or ""))
        text_plain = (content_detail or {}).get("text") or desc
        images = (content_detail or {}).get("images") or ([] if not cover else [cover])

        items.append(
            {
                "source": "bilibili",
                "title": title or (text_plain[:80] + "…" if len(text_plain) > 80 else text_plain),
                "author": author,
                "url": url,
                "text": text_plain,
                "content_html": content_html,
                "images": images,
                "cover": cover,
            }
        )

    return items
