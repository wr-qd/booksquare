from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from bs4 import BeautifulSoup

from spider.platforms.douban.client import DoubanClient
from spider.platforms.douban.parser import DoubanParser


@dataclass(frozen=True)
class DoubanBookCard:
    book_id: str
    title: str
    author: str
    cover_url: str
    rating: str
    summary: str

    def to_dict(self) -> Dict:
        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "cover_url": self.cover_url,
            "rating": self.rating,
            "summary": self.summary,
            "platform": "douban",
        }


def looks_like_douban_blocked_html(html: str) -> bool:
    if not html:
        return False
    lower = html.lower()
    if "douban.com/misc/sorry" in lower:
        return True
    if "sec.douban.com" in lower:
        return True
    if "<title>禁止访问</title>" in html:
        return True
    if "访问豆瓣的行为异常" in html or "检测到有异常请求" in html:
        return True
    if ("captcha" in lower or "验证码" in html) and "douban" in lower:
        return True
    return False


def extract_summary(detail_html: str, max_len: int = 900) -> str:
    if not detail_html:
        return ""

    soup = BeautifulSoup(detail_html, "html.parser")
    candidates = [
        "#link-report .intro",
        "#link-report span.all.hidden .intro",
        "#link-report .indent .intro",
        "div.related_info .indent .intro",
    ]

    texts: List[str] = []
    for sel in candidates:
        for node in soup.select(sel):
            t = node.get_text("\n", strip=True)
            if t:
                texts.append(t)

    if not texts:
        node = soup.find(id="link-report")
        if node:
            t = node.get_text("\n", strip=True)
            if t:
                texts.append(t)

    def clean(t: str) -> str:
        t = t.replace("(展开全部)", "").replace("展开全部", "")
        lines = [ln.strip() for ln in t.splitlines()]
        lines = [ln for ln in lines if ln]
        return "\n".join(lines)

    for t in texts:
        t2 = clean(t)
        if len(t2) >= 20:
            return (t2[:max_len] + "…") if len(t2) > max_len else t2

    return ""


def extract_related_subjects(detail_html: str, *, max_n: int = 24) -> List[Tuple[str, str]]:
    """Extract (subject_id, title) from '喜欢读...的人也喜欢' section."""
    if not detail_html:
        return []

    soup = BeautifulSoup(detail_html, "html.parser")

    candidates: List[Tuple[str, str]] = []

    def add_from_scope(scope) -> None:
        nonlocal candidates
        if not scope:
            return
        for a in scope.select("a[href]"):
            href = (a.get("href") or "").strip()
            m = re.search(r"/subject/(\d+)/", href)
            if not m:
                continue
            sid = m.group(1)
            title = a.get_text(strip=True)
            if not title:
                continue
            candidates.append((sid, title))
            if len(candidates) >= max_n:
                return

    # Prefer explicit section id.
    for sel in ("#db-rec-section", "#recommendations", ".recommendations", "div#db-rec-section .content"):
        node = soup.select_one(sel)
        if node:
            add_from_scope(node)
            if candidates:
                break

    # Fallback: find heading text containing '也喜欢' and use its container.
    if not candidates:
        for h in soup.find_all(["h2", "h3"]):
            t = h.get_text(" ", strip=True)
            if "也喜欢" in t and "喜欢" in t:
                container = h.parent
                add_from_scope(container)
                if candidates:
                    break

    # Final fallback: any subject links on the page (very loose, last resort).
    if not candidates:
        add_from_scope(soup)

    # De-dup while keeping order
    seen = set()
    out: List[Tuple[str, str]] = []
    for sid, title in candidates:
        if sid in seen:
            continue
        seen.add(sid)
        out.append((sid, title))
        if len(out) >= max_n:
            break
    return out


def fetch_book_card(subject_id: str, *, client: Optional[DoubanClient] = None) -> DoubanBookCard:
    sid = str(subject_id).strip()
    if not sid.isdigit():
        raise RuntimeError("subject_id must be numeric")

    own = client is None
    c = client or DoubanClient()
    parser = DoubanParser()

    try:
        url = f"https://book.douban.com/subject/{sid}/"
        html = c.get(url)
        if looks_like_douban_blocked_html(html):
            raise RuntimeError("blocked: douban anti-bot page")
        data = parser.extract_book_detail(html) or {}

        def _s(v) -> str:
            if v is None:
                return ""
            if isinstance(v, str):
                return v.strip()
            return str(v).strip()

        title = _s(data.get("title"))
        if not title:
            raise RuntimeError("failed to parse title")

        author = _s(data.get("author_name"))
        cover_url = _s(data.get("img_src"))
        rating = _s(data.get("rating"))
        summary = extract_summary(html)

        return DoubanBookCard(
            book_id=sid,
            title=title,
            author=author,
            cover_url=cover_url,
            rating=rating,
            summary=summary,
        )
    finally:
        if own:
            try:
                c.close()
            except Exception:
                pass


def pick_recommendation_from_shelf(
    shelf_book_ids: Sequence[str],
    *,
    already_recommended: Sequence[str],
    max_attempts: int = 6,
) -> Tuple[str, DoubanBookCard]:
    """Pick (source_book_id, recommended_book_card) using Douban related list."""
    numeric_ids = [str(x) for x in shelf_book_ids if str(x).isdigit()]
    if not numeric_ids:
        raise RuntimeError("bookshelf has no douban books")

    already = {str(x) for x in already_recommended}
    shelf_set = set(numeric_ids)

    client = DoubanClient()
    try:
        for _ in range(max_attempts):
            source_id = random.choice(numeric_ids)
            source_url = f"https://book.douban.com/subject/{source_id}/"
            source_html = client.get(source_url)
            if looks_like_douban_blocked_html(source_html):
                continue

            related = extract_related_subjects(source_html, max_n=30)
            cand_ids = [sid for (sid, _title) in related]

            # Filter: not self, not already recommended today, and (prefer) not already on shelf.
            filtered = [sid for sid in cand_ids if sid != source_id and sid not in already and sid not in shelf_set]
            if not filtered:
                filtered = [sid for sid in cand_ids if sid != source_id and sid not in already]

            if not filtered:
                continue

            rec_id = random.choice(filtered)
            card = fetch_book_card(rec_id, client=client)
            return source_id, card

        raise RuntimeError("failed to pick a recommendation")
    finally:
        try:
            client.close()
        except Exception:
            pass
