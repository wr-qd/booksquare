from __future__ import annotations

import os
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import Dict, List, Optional
from urllib.parse import quote

from bs4 import BeautifulSoup
from flask import Blueprint, jsonify, request, Response
import requests
import re

# 复用现有豆瓣爬虫实现（本项目 server/spider 下）
from spider.platforms.douban.client import DoubanClient
from spider.platforms.douban.parser import DoubanParser
from spider.platforms.douban.search import search_books_by_keyword

import jieba
from collections import Counter
from PIL import Image, ImageDraw, ImageFont
import random


_SEARCH_CACHE: Dict[str, tuple[float, List[Dict]]] = {}


def _cache_get(key: str) -> Optional[List[Dict]]:
    try:
        hit = _SEARCH_CACHE.get(key)
        if not hit:
            return None
        exp, val = hit
        if time.monotonic() > exp:
            _SEARCH_CACHE.pop(key, None)
            return None
        return val
    except Exception:
        return None


def _cache_set(key: str, val: List[Dict], ttl_sec: float = 120.0) -> None:
    try:
        # simple bounded cache
        if len(_SEARCH_CACHE) > 200:
            # drop arbitrary old entries
            for k in list(_SEARCH_CACHE.keys())[:50]:
                _SEARCH_CACHE.pop(k, None)
        _SEARCH_CACHE[key] = (time.monotonic() + max(5.0, float(ttl_sec)), val)
    except Exception:
        pass


books_bp = Blueprint("books", __name__, url_prefix="/api/books")


@books_bp.post('/douban/login')
def douban_login():
    """打开浏览器让用户手动登录豆瓣，并持久化 cookies 到 server/instance。

    默认非阻塞：立刻返回，前端/调用方可轮询 GET /api/books/douban/status。
    如需阻塞等待，可传 query 参数 wait=true。
    """
    try:
        from utils.douban_service import get_douban_service

        svc = get_douban_service()
        wait = (request.args.get('wait') or '').strip().lower() in ('1', 'true', 'yes')
        timeout = request.args.get('timeout')
        try:
            timeout_f = float(timeout) if timeout is not None else 240.0
        except Exception:
            timeout_f = 240.0
        timeout_f = max(30.0, min(timeout_f, 600.0))

        if svc.is_logged_in():
            return jsonify({'success': True, 'message': '豆瓣已登录', 'status': svc.status()})

        if wait:
            svc.login(timeout=timeout_f)
            return jsonify({'success': True, 'message': '豆瓣登录完成', 'status': svc.status()})

        svc.start_login(timeout=timeout_f)
        return jsonify({'success': True, 'message': '已打开浏览器，请完成豆瓣登录', 'status': svc.status()})
    except ModuleNotFoundError as e:
        return jsonify({'success': False, 'message': f'缺少依赖：{e}. 请安装 playwright 并执行 playwright install chromium'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'豆瓣登录失败：{e}'}), 500


@books_bp.get('/douban/status')
def douban_status():
    try:
        from utils.douban_service import get_douban_service

        svc = get_douban_service()
        return jsonify({'success': True, 'status': svc.status()})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取豆瓣登录状态失败：{e}'}), 500


@books_bp.post('/douban/logout')
def douban_logout():
    """清除本地保存的豆瓣 cookies。"""
    try:
        from utils.douban_service import get_douban_service

        svc = get_douban_service()
        svc.clear_cookies()
        return jsonify({'success': True, 'message': '已清除豆瓣登录态', 'status': svc.status()})
    except Exception as e:
        return jsonify({'success': False, 'message': f'清除豆瓣登录态失败：{e}'}), 500


@books_bp.post('/weibo/login')
def weibo_login():
    """打开浏览器让用户手动登录微博，并持久化 cookies 到 server/instance。

    默认非阻塞：立刻返回，调用方可轮询 GET /api/books/weibo/status。
    如需阻塞等待，可传 query 参数 wait=true。
    """
    try:
        from utils.weibo_service import get_weibo_service

        svc = get_weibo_service()
        wait = (request.args.get('wait') or '').strip().lower() in ('1', 'true', 'yes')
        timeout = request.args.get('timeout')
        try:
            timeout_f = float(timeout) if timeout is not None else 240.0
        except Exception:
            timeout_f = 240.0
        timeout_f = max(30.0, min(timeout_f, 600.0))

        if svc.is_logged_in():
            return jsonify({'success': True, 'message': '微博已登录', 'status': svc.status()})

        if wait:
            svc.login(timeout=timeout_f)
            return jsonify({'success': True, 'message': '微博登录完成', 'status': svc.status()})

        svc.start_login(timeout=timeout_f)
        return jsonify({'success': True, 'message': '已打开浏览器，请完成微博登录', 'status': svc.status()})
    except ModuleNotFoundError as e:
        return jsonify({'success': False, 'message': f'缺少依赖：{e}. 请安装 playwright 并执行 playwright install chromium'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'微博登录失败：{e}'}), 500


@books_bp.get('/weibo/status')
def weibo_status():
    try:
        from utils.weibo_service import get_weibo_service

        svc = get_weibo_service()
        return jsonify({'success': True, 'status': svc.status()})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取微博登录状态失败：{e}'}), 500


@books_bp.post('/weibo/logout')
def weibo_logout():
    """清除本地保存的微博 cookies。"""
    try:
        from utils.weibo_service import get_weibo_service

        svc = get_weibo_service()
        svc.clear_cookies()
        return jsonify({'success': True, 'message': '已清除微博登录态', 'status': svc.status()})
    except Exception as e:
        return jsonify({'success': False, 'message': f'清除微博登录态失败：{e}'}), 500


@books_bp.get('/bilibili/search')
def bilibili_search():
    """B站专栏（图文）搜索：使用 B站搜索接口获取专栏列表，并尽量补齐正文 HTML/图片。

    需求侧：固定返回前 5 篇（图文格式）。
    """

    q = (request.args.get('q') or request.args.get('keyword') or '').strip()
    if not q:
        return jsonify({'success': False, 'message': 'q 不能为空'}), 400

    limit = request.args.get('limit', 5)
    try:
        limit_i = int(limit)
    except Exception:
        limit_i = 5
    limit_i = max(1, min(limit_i, 5))

    # 爬虫层建议使用“书名 + 书评”作为关键词
    keyword = q

    try:
        from utils.bilibili_search import ExternalSearchError, search_bilibili_articles

        data = search_bilibili_articles(keyword, limit=limit_i)
        return jsonify({'success': True, 'data': data})
    except ExternalSearchError as e:
        return jsonify({'success': False, 'message': str(e)}), 502
    except Exception as e:
        return jsonify({'success': False, 'message': f'B站搜索失败：{e}'}), 500


@books_bp.get('/bilibili/article')
def bilibili_article():
    """B站专栏详情：按 cv id 获取正文 HTML/图片等。"""
    raw_id = (request.args.get('id') or '').strip()
    if not raw_id:
        return jsonify({'success': False, 'message': 'id 不能为空'}), 400
    try:
        article_id = int(str(raw_id).lstrip('cv'))
    except Exception:
        return jsonify({'success': False, 'message': 'id 必须是数字或 cv123 格式'}), 400

    try:
        from utils.bilibili_search import ExternalSearchError, get_bilibili_article

        data = get_bilibili_article(article_id, timeout_sec=15.0)
        return jsonify({'success': True, 'data': data})
    except ExternalSearchError as e:
        return jsonify({'success': False, 'message': str(e)}), 502
    except Exception as e:
        return jsonify({'success': False, 'message': f'B站详情失败：{e}'}), 500


@books_bp.get('/bilibili/image')
def bilibili_image_proxy():
    """B站图片代理：解决部分图片直接访问 404/防盗链等问题。"""
    url = (request.args.get('url') or '').strip()
    if not url:
        return jsonify({'success': False, 'message': 'url 不能为空'}), 400

    # Only allow http(s) to avoid SSRF surprises.
    if not (url.startswith('http://') or url.startswith('https://') or url.startswith('//')):
        return jsonify({'success': False, 'message': 'url 必须是 http(s)'}), 400

    if url.startswith('//'):
        url = 'https:' + url
    if url.startswith('http://'):
        url = 'https://' + url[len('http://'):]

    try:
        import requests
        resp = requests.get(
            url,
            timeout=10,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
            },
            stream=True,
        )
        if resp.status_code != 200:
            return jsonify({'success': False, 'message': f'图片拉取失败：HTTP {resp.status_code}'}), 502

        from flask import Response

        content_type = resp.headers.get('Content-Type') or 'application/octet-stream'
        return Response(resp.content, content_type=content_type)
    except Exception as e:
        return jsonify({'success': False, 'message': f'图片代理失败：{e}'}), 502


@books_bp.get('/weibo/search')
def weibo_search():
    """微博搜索（Playwright 渲染页面抓取），返回前 N 条结果。"""
    q = (request.args.get('q') or request.args.get('keyword') or '').strip()
    if not q:
        return jsonify({'success': False, 'message': 'q 不能为空'}), 400

    limit = request.args.get('limit', 5)
    try:
        limit_i = int(limit)
    except Exception:
        limit_i = 5
    # 产品侧需求：微博取约 30 条评价（以搜索结果近似）
    limit_i = max(1, min(limit_i, 30))

    # Hard-timeout the whole request to avoid the UI hanging when DNS/anti-bot blocks.
    # (requests' timeout doesn't cover DNS resolution reliably on all platforms.)
    import threading

    try:
        from utils.weibo_service import get_weibo_service
        from utils.weibo_search import ExternalSearchError, search_weibo

        svc = get_weibo_service()
        cookies = svc.load_cookies()

        result: dict = {}
        err: dict = {}

        def _worker():
            try:
                result['data'] = search_weibo(q, limit=limit_i, cookies=cookies, timeout_sec=12.0)
            except ExternalSearchError as e:
                err['external'] = str(e)
            except Exception as e:
                err['internal'] = str(e)

        t = threading.Thread(target=_worker, name='weibo-search', daemon=True)
        t.start()
        t.join(timeout=13.0)

        if t.is_alive():
            return jsonify({'success': False, 'message': '微博搜索超时（可能被风控/网络不佳），请稍后重试或更换网络'}), 502
        if 'external' in err:
            return jsonify({'success': False, 'message': err['external']}), 502
        if 'internal' in err:
            return jsonify({'success': False, 'message': f"微博搜索失败：{err['internal']}"}), 500

        return jsonify({'success': True, 'data': result.get('data') or []})
    except ModuleNotFoundError as e:
        return jsonify({'success': False, 'message': f'缺少依赖：{e}. 请安装 playwright 并执行 playwright install chromium'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'微博搜索失败：{e}'}), 500


_MOOD_KEYWORDS = [
    # 常见“情绪/氛围”词（按优先级/常用程度）
    "治愈",
    "温暖",
    "治愈系",
    "松弛",
    "轻松",
    "解压",
    "欢乐",
    "搞笑",
    "热血",
    "燃",
    "励志",
    "成长",
    "感动",
    "催泪",
    "悲伤",
    "丧",
    "致郁",
    "温柔",
    "浪漫",
    "甜",
    "治愈温暖",
    "悬疑",
    "推理",
    "烧脑",
    "惊悚",
    "恐怖",
    "黑暗",
    "现实",
    "治愈",
]


def _extract_mood_keywords(text: str, max_n: int = 3) -> List[str]:
    """从用户输入文本中提取情绪/氛围关键词。

    规则：优先匹配固定词表；若未命中则用分词取少量候选兜底。
    """
    if not text:
        return []
    t = str(text).strip()
    if not t:
        return []

    found: List[str] = []
    for kw in _MOOD_KEYWORDS:
        if kw and kw in t and kw not in found:
            found.append(kw)
        if len(found) >= max_n:
            return found

    # 兜底：分词取 2~3 个“看起来像情绪/意图”的词
    try:
        toks = [w.strip() for w in jieba.cut(t) if w and len(w.strip()) >= 2]
        stop = {"想看", "想要", "推荐", "一本", "这种", "感觉", "风格", "题材", "类型", "比较", "一些", "最好", "不要"}
        for w in toks:
            if w in stop:
                continue
            if re.fullmatch(r"[A-Za-z0-9]{2,}", w):
                # 英文/数字词太泛，除非用户确实输入英文情绪
                continue
            if w not in found:
                found.append(w)
            if len(found) >= max_n:
                break
    except Exception:
        pass
    return found[:max_n]


def _extract_book_titles_from_text(text: str) -> List[str]:
    if not text:
        return []
    t = str(text)
    out: List[str] = []

    # 《书名》是最可靠的模式
    for m in re.findall(r"《([^《》]{2,40})》", t):
        s = m.strip()
        if s:
            out.append(s)

    # 兜底：书名：xxx / 书名 xxx
    for m in re.findall(r"(?:书名|推荐|安利)\s*[:：]?\s*([A-Za-z0-9\u4e00-\u9fa5·\-\s]{2,40})", t):
        s = m.strip().strip('"\'“”‘’')
        if s and ' ' in s:
            # 太长的句子容易误判，含空格时稍微收紧
            s = " ".join(s.split())
        if s and len(s) <= 40:
            out.append(s)

    # 去重 + 简单过滤
    seen = set()
    cleaned: List[str] = []
    for x in out:
        x2 = x.strip()
        if not x2:
            continue
        if any(bad in x2 for bad in ("笔记", "评论", "合集", "推荐", "安利")):
            continue
        if x2 in seen:
            continue
        seen.add(x2)
        cleaned.append(x2)
    return cleaned


@books_bp.post('/advanced-search')
def advanced_search():
    """高级推荐：用户文本提取情绪词 + 体裁（小说/散文等） -> 直接豆瓣搜索 -> 返回最多50本。

    兼容旧前端：仍接受 {genre, mood}，其中 mood 会视为 text。
    """
    data = request.get_json(silent=True) or {}
    genre = (data.get('genre') or '').strip()
    text = (data.get('text') or '').strip()
    mood = (data.get('mood') or '').strip()  # 旧字段

    limit = data.get('limit', 20)
    try:
        limit_i = int(limit)
    except Exception:
        limit_i = 20
    limit_i = max(1, min(limit_i, 50))

    # 兼容：如果新 text 为空但旧 mood 有值，则使用 mood 作为 text
    if not text and mood:
        text = mood

    if not genre or not text:
        return jsonify({'success': False, 'message': 'genre 和 text 不能为空'}), 400

    try:
        moods = _extract_mood_keywords(text, max_n=3)

        # 主查询：情绪词 + 体裁
        primary_parts = [p for p in moods if p] + [genre]
        primary_keyword = " ".join(primary_parts).strip()
        if not primary_keyword:
            primary_keyword = genre

        cards = _douban_search_cards(primary_keyword, limit_i)

        # 兜底：主查询过于收紧导致结果偏少时，用“体裁”补齐（仍然保持与用户选择的类型一致）
        if len(cards) < limit_i:
            fallback = _douban_search_cards(genre, limit_i)
            seen = {c.get("book_id") for c in cards if c.get("book_id")}
            for c in fallback:
                bid = c.get("book_id")
                if not bid or bid in seen:
                    continue
                seen.add(bid)
                cards.append(c)
                if len(cards) >= limit_i:
                    break

        return jsonify({'success': True, 'data': cards[:limit_i], 'meta': {'keyword': primary_keyword, 'moods': moods}})
    except Exception as e:
        # 豆瓣经常返回 403/跳转到 sec.douban.com 风控页；不要误导为“搜不到”
        if _is_retryable_http_error(e) or ("sec.douban.com" in str(e)):
            return jsonify({'success': False, 'message': f'豆瓣搜索被风控/限流（{e}）。请稍后重试或更换网络。'}), 502
        return jsonify({'success': False, 'message': f'高级推荐失败：{e}'}), 500


def _douban_search_cards(q: str, limit: int) -> List[Dict]:
    """统一的豆瓣搜索卡片构建：最多返回 limit（<=50），自动过滤/补齐无标题项。"""
    q = (q or "").strip()
    if not q:
        return []
    limit = max(1, min(int(limit or 50), 50))

    cache_key = f"douban_search:{q}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached[:limit]

    # 过高的 top_n 会导致翻页请求变多，更容易触发限流；这里做保守上限。
    fetch_n = min(140, max(70, limit * 2))
    results = search_books_by_keyword(q, top_n=fetch_n) or []

    def normalize_rating(v):
        if isinstance(v, str):
            try:
                return float(v)
            except Exception:
                return v
        return v

    cards: List[Dict] = []
    seen_book_ids = set()
    missing_title_ids: List[str] = []

    for r in results:
        book_id = r.get("book_id")
        if not book_id or book_id in seen_book_ids:
            continue
        seen_book_ids.add(book_id)

        title = r.get("title")
        author = r.get("author")
        rating = normalize_rating(r.get("rating"))
        cover_url = r.get("cover_url")

        if isinstance(title, str):
            title = title.strip() or None
        if isinstance(author, str):
            author = author.strip() or None

        if not title:
            missing_title_ids.append(book_id)
            continue

        cards.append(
            {
                "book_id": book_id,
                "title": title,
                "author": author,
                "rating": rating,
                "cover_url": cover_url,
                "platform": "douban",
            }
        )
        if len(cards) >= limit:
            break

    needed = limit - len(cards)
    if needed <= 0 or not missing_title_ids:
        out = cards[:limit]
        _cache_set(cache_key, out, ttl_sec=120.0)
        return out

    to_backfill = missing_title_ids[: min(len(missing_title_ids), needed * 3)]

    def backfill_one(book_id: str) -> Optional[Dict]:
        try:
            url = f"https://book.douban.com/subject/{book_id}/"
            client = DoubanClient()
            try:
                html = client.get(url, timeout=8, max_attempts=2, retry_on_403_429=False)
            finally:
                try:
                    client.close()
                except Exception:
                    pass
            if not html:
                return None

            parser = DoubanParser()
            detail = parser.extract_book_detail(html) or {}
            title = detail.get("title")
            if isinstance(title, str):
                title = title.strip() or None
            if not title:
                return None
            author = detail.get("author_name")
            if isinstance(author, str):
                author = author.strip() or None
            return {
                "book_id": book_id,
                "title": title,
                "author": author,
                "rating": normalize_rating(detail.get("rating")),
                "cover_url": detail.get("img_src"),
                "platform": "douban",
            }
        except Exception:
            return None

    filled: List[Dict] = []
    # 限制并发，避免补全标题时对详情页产生突发请求
    ex = ThreadPoolExecutor(max_workers=2)
    futures = [ex.submit(backfill_one, bid) for bid in to_backfill]
    try:
        budget_sec = 2.2
        start = time.monotonic()
        try:
            for fut in as_completed(futures, timeout=budget_sec):
                item = fut.result()
                if not item:
                    continue
                t = item.get("title")
                if not isinstance(t, str) or not t.strip():
                    continue
                filled.append(item)
                if len(filled) >= needed:
                    break
                if time.monotonic() - start >= budget_sec:
                    break
        except Exception:
            pass
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

    cards.extend(filled)
    out = cards[:limit]
    _cache_set(cache_key, out, ttl_sec=120.0)
    return out


def _is_retryable_http_error(exc: Exception) -> bool:
    try:
        if isinstance(exc, requests.HTTPError):
            code = getattr(exc.response, "status_code", None)
            return code in (403, 429) or (isinstance(code, int) and 500 <= code < 600)
    except Exception:
        return False
    return False


def _looks_like_douban_blocked_html(html: str) -> bool:
    """Detect Douban anti-bot / sorry pages which are often returned as HTTP 200."""
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


def _is_allowed_cover_url(url: str) -> bool:
    if not url:
        return False
    u = url.strip().lower()
    if not (u.startswith("http://") or u.startswith("https://")):
        return False
    # 限制为豆瓣/豆瓣图片域名，避免变成任意代理
    return ("doubanio.com" in u) or ("douban.com" in u)


@books_bp.get("/cover")
def cover_proxy():
    url = (request.args.get("url") or "").strip()
    if not _is_allowed_cover_url(url):
        return jsonify({"success": False, "message": "invalid cover url"}), 400

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Referer": "https://book.douban.com/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200 or not r.content:
            return jsonify({"success": False, "message": "failed to fetch cover"}), 502
        content_type = r.headers.get("Content-Type") or "image/jpeg"
        return Response(r.content, status=200, mimetype=content_type)
    except Exception:
        return jsonify({"success": False, "message": "failed to fetch cover"}), 502


def _safe_int(v: str | None, default: int) -> int:
    try:
        return int(v) if v is not None else default
    except Exception:
        return default


def _pick_cn_font() -> Optional[str]:
    candidates = [
        r"C:\\Windows\\Fonts\\msyh.ttc",
        r"C:\\Windows\\Fonts\\simhei.ttf",
        r"C:\\Windows\\Fonts\\simsun.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _extract_tags(detail_html: str, top_n: int = 12) -> List[str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    tags = [a.get_text(strip=True) for a in soup.select(".tag a")]
    seen = set()
    out: List[str] = []
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= top_n:
            break
    return out


def _extract_summary(detail_html: str, max_len: int = 900) -> Optional[str]:
    """从豆瓣图书详情页提取“内容简介”。

    结构在豆瓣会变动，这里用多个 selector 兜底，提取到第一段有意义文本即可。
    """
    if not detail_html:
        return None

    soup = BeautifulSoup(detail_html, "html.parser")

    # 常见：#link-report 下的 .intro（有时还有 span.all.hidden 里）
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

    # 兜底：寻找“内容简介”标题附近
    if not texts:
        header = soup.find(id="link-report")
        if header:
            t = header.get_text("\n", strip=True)
            if t:
                texts.append(t)

    def clean(t: str) -> str:
        t = t.replace("(展开全部)", "").replace("展开全部", "")
        # 清理多余空行
        lines = [ln.strip() for ln in t.splitlines()]
        lines = [ln for ln in lines if ln]
        return "\n".join(lines)

    for t in texts:
        t2 = clean(t)
        if len(t2) >= 20:
            return (t2[:max_len] + "…") if len(t2) > max_len else t2

    return None


def _wordcloud_data_url(texts: List[str]) -> Optional[str]:
    texts = [t.strip() for t in texts if t and t.strip()]
    if not texts:
        return None

    tokens: List[str] = []
    for t in texts:
        tokens.extend([w.strip() for w in jieba.cut(t) if w and len(w.strip()) > 1])

    if not tokens:
        return None

    counts = Counter(tokens)
    items = counts.most_common(90)
    if not items:
        return None

    # 图太大在详情页会显得空；这里生成更小的 PNG，前端也会再限制展示尺寸
    width, height = 600, 360
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    font_path = _pick_cn_font()
    max_freq = items[0][1]
    min_freq = items[-1][1]
    if max_freq == min_freq:
        max_freq += 1

    def scale(freq: int) -> int:
        # 16..72
        return int(16 + (freq - min_freq) * (72 - 16) / (max_freq - min_freq))

    placed: List[tuple[int, int, int, int]] = []
    palette = [
        (29, 61, 205),
        (102, 126, 234),
        (118, 75, 162),
        (34, 139, 230),
        (20, 80, 120),
    ]

    for word, freq in items:
        size = scale(freq)
        try:
            font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        # 尝试找一个不太重叠的位置
        for _ in range(30):
            x = random.randint(8, max(8, width - 8))
            y = random.randint(8, max(8, height - 8))
            bbox = draw.textbbox((x, y), word, font=font)
            if not bbox:
                continue
            x0, y0, x1, y1 = bbox
            if x1 >= width - 8 or y1 >= height - 8:
                continue
            ok = True
            for px0, py0, px1, py1 in placed:
                # 简单相交检测
                if not (x1 < px0 or x0 > px1 or y1 < py0 or y0 > py1):
                    ok = False
                    break
            if ok:
                color = random.choice(palette)
                draw.text((x, y), word, fill=color, font=font)
                placed.append((x0, y0, x1, y1))
                break

    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = __import__("base64").b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"

    def _fetch_douban_basic(book_id: str):
        client = DoubanClient()
        parser = DoubanParser()
        detail_html = ""
        detail_url = f"https://book.douban.com/subject/{book_id}/"
        try:
            detail_html = client.get(detail_url)
            detail_data = parser.extract_book_detail(detail_html) or {}

            # 若初次解析失败，做一次兜底重拉
            if not detail_data.get("title"):
                try:
                    headers = {
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                        ),
                        "Referer": "https://book.douban.com/",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                    }
                    resp = requests.get(detail_url, headers=headers, timeout=8)
                    if resp.status_code == 200 and resp.text:
                        alt_html = resp.text
                        alt_data = parser.extract_book_detail(alt_html) or {}
                        if alt_data.get("title"):
                            detail_html = alt_html
                            detail_data = alt_data
                except Exception:
                    pass

            if not detail_data.get("title") and _looks_like_douban_blocked_html(detail_html):
                raise RuntimeError("blocked: douban anti-bot page (book detail)")

            tags = _extract_tags(detail_html, top_n=12)
            summary = _extract_summary(detail_html)

            book = {
                "book_id": book_id,
                "title": detail_data.get("title"),
                "author": detail_data.get("author_name"),
                "publisher": detail_data.get("publisher"),
                "isbn": detail_data.get("isbn"),
                "rating": detail_data.get("rating"),
                "cover_url": detail_data.get("img_src"),
                "cover_proxy_url": (
                    f"/api/books/cover?url={quote(detail_data.get('img_src') or '')}"
                    if detail_data.get("img_src")
                    else None
                ),
                "tags": tags,
                "summary": summary,
                "platform": "douban",
            }
            return book
        finally:
            try:
                client.close()
            except Exception:
                pass


    def _fetch_comments_for_wordcloud(book_id: str, wc_max_comments: int) -> str:
        wc_max_comments = max(20, min(wc_max_comments, 500))

        client = DoubanClient()
        parser = DoubanParser()
        detail_url = f"https://book.douban.com/subject/{book_id}/"

        comments: List[Dict] = []
        page = 0
        per_page = 20
        prev_url: Optional[str] = None

        try:
            while len(comments) < wc_max_comments:
                start = page * per_page
                url = (
                    f"https://book.douban.com/subject/{book_id}/comments/"
                    f"?start={start}&limit={per_page}&status=P&sort=score"
                )

                extra_headers: Dict[str, str] = {}
                if page == 0:
                    extra_headers["Referer"] = detail_url
                elif prev_url:
                    extra_headers["Referer"] = prev_url

                try:
                    html = client.get(
                        url,
                        extra_headers=extra_headers,
                        timeout=8,
                        max_attempts=2,
                        retry_on_403_429=False,
                    )
                    if _looks_like_douban_blocked_html(html):
                        raise RuntimeError("blocked: douban anti-bot page (comments)")
                    page_comments = parser.extract_comments(html) or []
                except Exception as e:
                    if _is_retryable_http_error(e):
                        break
                    raise

                if page == 0 and not page_comments:
                    try:
                        fallback_url = (
                            f"https://book.douban.com/subject/{book_id}/comments/"
                            f"?start={start}&limit={per_page}&status=P"
                        )
                        html2 = client.get(
                            fallback_url,
                            extra_headers=extra_headers,
                            timeout=8,
                            max_attempts=2,
                            retry_on_403_429=False,
                        )
                        page_comments = parser.extract_comments(html2) or []
                        if page_comments:
                            html = html2
                            url = fallback_url
                    except Exception:
                        pass
                if not page_comments:
                    break

                comments.extend(page_comments)
                if len(page_comments) < per_page:
                    break

                prev_url = url
                page += 1

            comments = comments[:wc_max_comments]
            return _wordcloud_data_url([c.get("content", "") for c in comments])
        finally:
            try:
                client.close()
            except Exception:
                pass


@books_bp.get("/search")
def search():
    # 兼容：keyword 也可作为查询参数（部分旧脚本使用 keyword）
    q = (request.args.get("q") or request.args.get("keyword") or "").strip()
    limit = _safe_int(request.args.get("limit"), 50)
    limit = max(1, min(limit, 50))

    if not q:
        return jsonify({"success": False, "message": "q 不能为空"}), 400

    try:
        cards = _douban_search_cards(q, limit)
        return jsonify({"success": True, "data": cards})
    except Exception as e:
        if _is_retryable_http_error(e) or ("sec.douban.com" in str(e)) or ("blocked" in str(e).lower()):
            return jsonify({"success": False, "message": f"豆瓣搜索被风控/限流（{e}）。请稍后重试或更换网络。"}), 502
        return jsonify({"success": False, "message": f"搜索失败：{e}"}), 500


@books_bp.get("/<book_id>")
def detail(book_id: str):
    wc_max_comments = _safe_int(request.args.get("wc_max_comments"), 200)
    wc_max_comments = max(20, min(wc_max_comments, 500))

    preview_comments = _safe_int(request.args.get("preview_comments"), 20)
    preview_comments = max(0, min(preview_comments, 50))

    client = DoubanClient()
    parser = DoubanParser()
    detail_html = ""
    try:
        detail_url = f"https://book.douban.com/subject/{book_id}/"
        detail_html = client.get(detail_url)
        detail_data = parser.extract_book_detail(detail_html) or {}

        # 有时豆瓣会返回 200 但内容是风控/异常请求页，导致解析全为空；做一次轻量兜底重拉
        if not detail_data.get("title"):
            try:
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://book.douban.com/",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                }
                resp = requests.get(detail_url, headers=headers, timeout=8)
                if resp.status_code == 200 and resp.text:
                    alt_html = resp.text
                    alt_data = parser.extract_book_detail(alt_html) or {}
                    if alt_data.get("title"):
                        detail_html = alt_html
                        detail_data = alt_data
            except Exception:
                pass

        # 若仍拿不到标题且页面是风控/验证码页，明确报错，避免前端误以为“空数据”。
        if not detail_data.get("title") and _looks_like_douban_blocked_html(detail_html):
            raise RuntimeError("blocked: douban anti-bot page (book detail)")

        tags = _extract_tags(detail_html, top_n=12)
        summary = _extract_summary(detail_html)

        comments: List[Dict] = []
        page = 0
        per_page = 20
        prev_url: Optional[str] = None

        while len(comments) < wc_max_comments:
            start = page * per_page
            url = (
                f"https://book.douban.com/subject/{book_id}/comments/"
                f"?start={start}&limit={per_page}&status=P&sort=score"
            )

            extra_headers: Dict[str, str] = {}
            if page == 0:
                extra_headers["Referer"] = detail_url
            elif prev_url:
                extra_headers["Referer"] = prev_url

            try:
                html = client.get(
                    url,
                    extra_headers=extra_headers,
                    timeout=8,
                    max_attempts=2,
                    retry_on_403_429=False,
                )
                if _looks_like_douban_blocked_html(html):
                    raise RuntimeError("blocked: douban anti-bot page (comments)")
                page_comments = parser.extract_comments(html) or []
            except Exception as e:
                # 豆瓣经常在翻到更深页时 403/429；此处降级：停止继续翻页，返回已抓到的评论
                if _is_retryable_http_error(e):
                    break
                raise

            # 有些书在 sort=score 下第一页会返回空；做一次降级兜底
            if page == 0 and not page_comments:
                try:
                    fallback_url = (
                        f"https://book.douban.com/subject/{book_id}/comments/"
                        f"?start={start}&limit={per_page}&status=P"
                    )
                    html2 = client.get(
                        fallback_url,
                        extra_headers=extra_headers,
                        timeout=8,
                        max_attempts=2,
                        retry_on_403_429=False,
                    )
                    page_comments = parser.extract_comments(html2) or []
                    if page_comments:
                        html = html2
                        url = fallback_url
                except Exception:
                    pass
            if not page_comments:
                break

            comments.extend(page_comments)
            if len(page_comments) < per_page:
                break

            prev_url = url
            page += 1

        comments = comments[:wc_max_comments]
        wc_data_url = _wordcloud_data_url([c.get("content", "") for c in comments])

        return jsonify(
            {
                "success": True,
                "data": {
                    "book": {
                        "book_id": book_id,
                        "title": detail_data.get("title"),
                        "author": detail_data.get("author_name"),
                        "publisher": detail_data.get("publisher"),
                        "isbn": detail_data.get("isbn"),
                        "rating": detail_data.get("rating"),
                        "cover_url": detail_data.get("img_src"),
                        "cover_proxy_url": (
                            f"/api/books/cover?url={quote(detail_data.get('img_src') or '')}"
                            if detail_data.get("img_src")
                            else None
                        ),
                        "tags": tags,
                        "summary": summary,
                        "platform": "douban",
                    },
                    "preview_comments": comments[:preview_comments],
                    "wordcloud_data_url": wc_data_url,
                },
            }
        )
    except Exception as e:
        if _is_retryable_http_error(e) or ("sec.douban.com" in str(e)) or ("blocked" in str(e).lower()):
            return jsonify({"success": False, "message": f"豆瓣详情被风控/限流（{e}）。请稍后重试或更换网络。"}), 502
        return jsonify({"success": False, "message": f"详情加载失败：{e}"}), 500
    finally:
        try:
            client.close()
        except Exception:
            pass


@books_bp.get("/<book_id>/basic")
def detail_basic(book_id: str):
    try:
        book = _fetch_douban_basic(book_id)
        return jsonify({"success": True, "data": {"book": book}})
    except Exception as e:
        if _is_retryable_http_error(e) or ("sec.douban.com" in str(e)) or ("blocked" in str(e).lower()):
            return jsonify({"success": False, "message": f"豆瓣详情被风控/限流（{e}）。请稍后重试或更换网络。"}), 502
        return jsonify({"success": False, "message": f"详情加载失败：{e}"}), 500


@books_bp.get("/<book_id>/wordcloud")
def detail_wordcloud(book_id: str):
    wc_max_comments = _safe_int(request.args.get("wc_max_comments"), 200)
    wc_max_comments = max(20, min(wc_max_comments, 500))

    try:
        url = _fetch_comments_for_wordcloud(book_id, wc_max_comments)
        return jsonify({"success": True, "data": {"wordcloud_data_url": url}})
    except Exception as e:
        if _is_retryable_http_error(e) or ("sec.douban.com" in str(e)) or ("blocked" in str(e).lower()):
            return jsonify({"success": False, "message": f"豆瓣词云被风控/限流（{e}）。请稍后重试或更换网络。"}), 502
        return jsonify({"success": False, "message": f"词云生成失败：{e}"}), 500


@books_bp.get("/<book_id>/comments")
def comments(book_id: str):
    page = max(1, _safe_int(request.args.get("page"), 1))
    limit = max(1, min(_safe_int(request.args.get("limit"), 20), 50))

    client = DoubanClient()
    parser = DoubanParser()

    try:
        start = (page - 1) * limit
        detail_url = f"https://book.douban.com/subject/{book_id}/"
        url = (
            f"https://book.douban.com/subject/{book_id}/comments/"
            f"?start={start}&limit={limit}&status=P&sort=score"
        )
        try:
            html = client.get(
                url,
                extra_headers={"Referer": detail_url},
                timeout=8,
                max_attempts=2,
                retry_on_403_429=False,
            )
            if _looks_like_douban_blocked_html(html):
                raise RuntimeError("blocked: douban anti-bot page (comments)")
            items = parser.extract_comments(html) or []
        except Exception as e:
            if _is_retryable_http_error(e):
                return jsonify(
                    {
                        "success": True,
                        "data": {"page": page, "limit": limit, "total": None, "items": []},
                        "message": "douban rate limited",
                    }
                )
            raise
        # 有些条目在带 sort=score 时会返回空，做一次降级
        if page == 1 and not items:
            try:
                fallback_url = (
                    f"https://book.douban.com/subject/{book_id}/comments/"
                    f"?start={start}&limit={limit}&status=P"
                )
                html2 = client.get(
                    fallback_url,
                    extra_headers={"Referer": detail_url},
                    timeout=8,
                    max_attempts=2,
                    retry_on_403_429=False,
                )
                if _looks_like_douban_blocked_html(html2):
                    raise RuntimeError("blocked: douban anti-bot page (comments)")
                items = parser.extract_comments(html2) or []
                if items:
                    html = html2
            except Exception:
                pass

        total = None
        try:
            soup = BeautifulSoup(html, "html.parser")
            paginator = soup.select_one("#paginator") or soup.select_one(".paginator")
            if paginator:
                total_attr = paginator.get("data-total")
                if total_attr and str(total_attr).isdigit():
                    total = int(total_attr)
        except Exception:
            total = None

        return jsonify({"success": True, "data": {"page": page, "limit": limit, "total": total, "items": items}})
    except Exception as e:
        if _is_retryable_http_error(e) or ("sec.douban.com" in str(e)) or ("blocked" in str(e).lower()):
            return jsonify({"success": False, "message": f"豆瓣评论被风控/限流（{e}）。请稍后重试或更换网络。"}), 502
        return jsonify({"success": False, "message": f"评论加载失败：{e}"}), 500
    finally:
        try:
            client.close()
        except Exception:
            pass
