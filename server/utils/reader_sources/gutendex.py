from __future__ import annotations

import time
import re
from dataclasses import dataclass
from typing import Any
from typing import Dict, List, Optional

import requests


_GUTENDEX_API = "https://gutendex.com/books"
_ALLOWED_DOWNLOAD_DOMAINS = {
    "www.gutenberg.org",
    "gutenberg.org",
}


# Simple in-process cache to reduce repeated calls during UI refresh.
# Keyed by (query, limit). TTL is short; safe for dev usage.
_CACHE: Dict[tuple[str, int], tuple[float, List["SourceItem"]]] = {}
_CACHE_TTL_SECONDS = 60.0


class GutendexTemporaryError(RuntimeError):
    """Transient network/service error when calling Gutendex."""



@dataclass(frozen=True)
class DownloadOption:
    format: str  # txt | epub
    mime: str
    url: str

    def to_dict(self) -> Dict:
        return {"format": self.format, "mime": self.mime, "url": self.url}


@dataclass(frozen=True)
class SourceItem:
    source: str  # gutendex
    source_id: str
    title: str
    author: str
    downloads: List[DownloadOption]

    def to_dict(self) -> Dict:
        return {
            "source": self.source,
            "source_id": self.source_id,
            "title": self.title,
            "author": self.author,
            "downloads": [d.to_dict() for d in self.downloads],
        }


def _pick_author(authors: object) -> str:
    if not isinstance(authors, list) or not authors:
        return ""
    a0 = authors[0] if authors else {}
    if isinstance(a0, dict):
        return (a0.get("name") or "").strip()
    return str(a0).strip()


def _normalize_downloads(formats: Dict[str, str]) -> List[DownloadOption]:
    """Map Gutendex formats to a small set we support."""
    out: List[DownloadOption] = []
    if not isinstance(formats, dict):
        return out

    def add(fmt: str, mime: str) -> None:
        url = formats.get(mime)
        if not url or not isinstance(url, str):
            return
        out.append(DownloadOption(format=fmt, mime=mime, url=url))

    # Prefer UTF-8 text when available.
    add("txt", "text/plain; charset=utf-8")
    add("txt", "text/plain")

    # EPUB
    add("epub", "application/epub+zip")

    # De-dup by (format,url)
    seen = set()
    dedup: List[DownloadOption] = []
    for d in out:
        k = (d.format, d.url)
        if k in seen:
            continue
        seen.add(k)
        dedup.append(d)
    return dedup


def _get_json_with_retry(url: str, *, params: Dict[str, str], timeout: Any) -> Dict:
    headers = {
        "Accept": "application/json",
        "User-Agent": "book-review-system/1.0 (+https://localhost)"
    }

    # Retry a couple times on timeouts / transient network errors.
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_exc = e
            # small exponential backoff
            time.sleep(0.4 * (2 ** attempt))
        except Exception as e:
            # Non-transient errors: raise as-is
            raise

    raise GutendexTemporaryError(f"Gutendex 暂时不可用，请稍后重试（{last_exc}）")


def search_gutendex(query: str, *, limit: int = 8, timeout: Any = (5, 25)) -> List[SourceItem]:
    q = (query or "").strip()
    if not q:
        return []

    limit = max(1, min(int(limit), 20))

    ck = (q, limit)
    now = time.time()
    cached = _CACHE.get(ck)
    if cached and (now - cached[0]) <= _CACHE_TTL_SECONDS:
        return cached[1]

    data = _get_json_with_retry(_GUTENDEX_API, params={"search": q}, timeout=timeout)

    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return []

    items: List[SourceItem] = []
    for it in results[:limit]:
        if not isinstance(it, dict):
            continue
        gid = str(it.get("id") or "").strip()
        title = str(it.get("title") or "").strip()
        author = _pick_author(it.get("authors"))
        downloads = _normalize_downloads(it.get("formats") or {})
        if not gid or not title or not downloads:
            continue
        items.append(SourceItem(source="gutendex", source_id=gid, title=title, author=author, downloads=downloads))

    _CACHE[ck] = (now, items)
    return items


def is_allowed_gutenberg_download(url: str) -> bool:
    if not url:
        return False
    u = url.strip()
    # Gutendex returns direct links to gutenberg.org or mirrors; we strictly allow the main domain.
    m = re.match(r"^https?://([^/]+)/", u, re.I)
    if not m:
        return False
    host = m.group(1).lower()
    return host in _ALLOWED_DOWNLOAD_DOMAINS
