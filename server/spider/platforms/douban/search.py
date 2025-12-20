from typing import List, Dict, Optional
from urllib.parse import quote_plus
import json
import re
import requests

from bs4 import BeautifulSoup

from spider.platforms.douban.config import BASE_URL
from spider.platforms.douban.client import DoubanClient


_WINDOW_DATA_RE = re.compile(r"window\.__DATA__\s*=\s*(\{.*?\})\s*;", flags=re.S)


def _looks_like_blocked_page(html: str) -> bool:
    """Return True if Douban returned an anti-bot / sorry page (often HTTP 200)."""
    if not html:
        return False
    lower = html.lower()

    # Common anti-bot endpoints / markers
    if "douban.com/misc/sorry" in lower:
        return True
    if "sec.douban.com" in lower:
        return True

    # Title/body hints
    if "<title>禁止访问</title>" in html:
        return True
    if "访问豆瓣的行为异常" in html or "检测到有异常请求" in html:
        return True

    # Captcha / verification hints
    if ("captcha" in lower or "验证码" in html) and "douban" in lower:
        return True

    return False


def _parse_subject_search_items(html: str) -> List[Dict]:
    """Parse `search.douban.com/.../subject_search` HTML.

    The page is rendered by JS, but it embeds a JSON blob in `window.__DATA__`.
    We extract book items from there.
    """
    if not html:
        return []

    m = _WINDOW_DATA_RE.search(html)
    if not m:
        return []

    try:
        data = json.loads(m.group(1))
    except Exception:
        return []

    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []

    def normalize_rating(val):
        # window.__DATA__ often provides rating as an object like:
        # {"count": 10205, "rating_info": "", "star_count": 4.5, "value": 8.9}
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            s = val.strip()
            if not s:
                return None
            try:
                return float(s)
            except Exception:
                return s
        if isinstance(val, dict):
            # Prefer explicit numeric fields
            for k in ("value", "score", "rating", "avg"):
                if k in val:
                    return normalize_rating(val.get(k))
            ri = val.get("rating_info")
            if isinstance(ri, dict):
                for k in ("value", "score", "rating", "avg"):
                    if k in ri:
                        return normalize_rating(ri.get(k))
        return None

    out: List[Dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        url = (it.get("url") or "").strip()
        if "/subject/" not in url:
            continue

        book_id: Optional[str] = None
        try:
            m2 = re.search(r"/subject/(\d+)/", url)
            if m2:
                book_id = m2.group(1)
        except Exception:
            book_id = None
        if not book_id:
            continue

        title = it.get("title")
        if isinstance(title, str):
            title = title.strip() or None

        abstract = it.get("abstract")
        author = None
        if isinstance(abstract, str) and abstract.strip():
            # Common format: "作者 / 出版社 / 年份 / 价格"
            author = abstract.split("/")[0].strip() or None

        out.append(
            {
                "book_id": book_id,
                "title": title,
                "author": author,
                "cover_url": it.get("cover_url"),
                "rating": normalize_rating(it.get("rating") or it.get("score")),
                "detail_url": url or f"{BASE_URL}/subject/{book_id}/",
            }
        )
    return out


def search_books_by_keyword(keyword: str, top_n: int = 10) -> List[Dict]:
    """
    使用豆瓣搜索页面抓取 Top-N 候选书（返回 book_id/title/author/cover_url/rating/detail_url）
    优先使用 search.douban.com，若无结果再访问 book.douban.com 的搜索。
    """
    results: List[Dict] = []
    seen_ids = set()

    try:
        top_n_i = int(top_n)
    except Exception:
        top_n_i = 10
    top_n_i = max(1, top_n_i)

    # Search pages embed results in window.__DATA__ and support paging via start=
    page_size = 15
    max_pages = 12
    pages = min(max_pages, max(1, (top_n_i + page_size - 1) // page_size))

    client = DoubanClient()
    last_exc: Optional[Exception] = None
    try:
        for page in range(pages):
            start = page * page_size
            url = (
                "https://search.douban.com/book/subject_search"
                f"?search_text={quote_plus(keyword)}&start={start}"
            )
            html = None
            try:
                html = client.get(url, timeout=10, max_attempts=2, retry_on_403_429=False)
            except Exception as e:
                if last_exc is None:
                    last_exc = e
                html = None

            if not html:
                continue

            if _looks_like_blocked_page(html):
                raise RuntimeError("blocked: douban anti-bot page (禁止访问/misc/sorry)")

            parsed = _parse_subject_search_items(html)
            for r in parsed:
                book_id = r.get("book_id")
                if not book_id or book_id in seen_ids:
                    continue
                seen_ids.add(book_id)
                results.append(r)
                if len(results) >= top_n_i:
                    return results[:top_n_i]

        # 兜底：如果 subject_search 没拿到数据，再尝试解析 book.douban.com 的传统 DOM
        if len(results) < top_n_i:
            starts = [i * 15 for i in range(min(max_pages, max(1, (top_n_i + 14) // 15)))]
            urls = [f"{BASE_URL}/search?cat=1001&q={quote_plus(keyword)}&start={start}" for start in starts]
            for url in urls:
                html = None
                try:
                    html = client.get(url, timeout=10, max_attempts=2, retry_on_403_429=False)
                except Exception as e:
                    if last_exc is None:
                        last_exc = e
                    html = None
                if not html:
                    continue

                if _looks_like_blocked_page(html):
                    raise RuntimeError("blocked: douban anti-bot page (禁止访问/misc/sorry)")

                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("li.subject-item") or soup.select(".result") or []
                for item in items:
                    if len(results) >= top_n_i:
                        return results[:top_n_i]
                    a = item.select_one("h2 a") or item.select_one(".title a") or item.select_one("a")
                    if not a:
                        continue
                    href = (a.get("href") or "").strip()
                    m2 = re.search(r"/subject/(\d+)/", href)
                    book_id = m2.group(1) if m2 else None
                    if not book_id or book_id in seen_ids:
                        continue
                    seen_ids.add(book_id)

                    title = (a.get("title") or a.get_text(strip=True) or None)
                    cover_el = item.select_one(".pic img") or item.select_one("img")
                    cover = cover_el.get("src") if cover_el else None

                    pub_el = item.select_one(".pub") or item.select_one(".meta")
                    author = None
                    if pub_el:
                        txt = pub_el.get_text(separator=" ", strip=True)
                        if txt:
                            author = txt.split("/")[0].strip() or None

                    rating_el = item.select_one(".rating_nums") or item.select_one(".rate")
                    rating = rating_el.get_text(strip=True) if rating_el else None

                    results.append(
                        {
                            "book_id": book_id,
                            "title": title,
                            "author": author,
                            "cover_url": cover,
                            "rating": rating,
                            "detail_url": href or f"{BASE_URL}/subject/{book_id}/",
                        }
                    )

        if results:
            return results[:top_n_i]

        # If everything failed and we likely hit anti-bot, surface an error;
        # otherwise allow the caller to treat it as a normal empty result.
        if isinstance(last_exc, requests.HTTPError):
            code = getattr(getattr(last_exc, "response", None), "status_code", None)
            final_url = getattr(getattr(last_exc, "response", None), "url", "") or ""
            if code in (403, 429) or ("sec.douban.com" in final_url):
                raise last_exc
            return []

        if last_exc and ("sec.douban.com" in str(last_exc)):
            raise last_exc

        return []
    finally:
        try:
            client.close()
        except Exception:
            pass
