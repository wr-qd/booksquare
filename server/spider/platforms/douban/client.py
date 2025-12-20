import os
import requests
import time
import random
import threading
from spider.base.abstract_client import AbstractClient
from spider.platforms.douban.config import USER_AGENT


def _load_cookie_header_from_instance() -> str:
    """Load cookies saved by the interactive Douban login flow.

    Expected path: server/instance/douban_cookies.json
    """
    try:
        server_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        cookie_path = os.path.join(server_dir, "instance", "douban_cookies.json")
        if not os.path.exists(cookie_path):
            return ""
        import json

        with open(cookie_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        if not isinstance(cookies, list):
            return ""
        parts = []
        for c in cookies:
            if not isinstance(c, dict):
                continue
            name = c.get("name")
            value = c.get("value")
            if not name or value is None:
                continue
            parts.append(f"{name}={value}")
        return "; ".join(parts)
    except Exception:
        return ""

class DoubanClient(AbstractClient):
    _throttle_lock = threading.Lock()
    _last_request_ts = 0.0

    def __init__(self):
        self.session = requests.Session()
        # 默认头，后续请求会基于此合并
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "document",
        })

        # Optional: set cookies from environment to mitigate Douban anti-bot.
        # Use the raw Cookie header string, e.g. "a=1; b=2; ..."
        cookie_str = os.getenv("DOUBAN_COOKIE")
        if not cookie_str:
            cookie_str = _load_cookie_header_from_instance()
        if cookie_str:
            self.set_cookies_from_string(cookie_str)

    def get(
        self,
        url: str,
        extra_headers: dict = None,
        timeout: int = 10,
        max_attempts: int = 6,
        retry_on_403_429: bool = True,
    ) -> str:
        """GET 请求，支持额外 headers，内置重试与适当 Referer 设置。

        参数：
        - max_attempts: 最多尝试次数（包含第一次）。
        - retry_on_403_429: 是否对 403/429 进行退避重试。对评论深翻页建议关闭，避免阻塞太久。
        """
        headers = {}
        if extra_headers:
            headers.update(extra_headers)
        # 如果没有提供 Referer，尝试构造一个合理的 Referer（豆瓣偏好来自自身站点）
        if "Referer" not in headers:
            try:
                from urllib.parse import urlparse

                parsed = urlparse(url)
                if parsed.path.startswith("/subject/"):
                    headers["Referer"] = f"https://{parsed.netloc}/"
            except Exception:
                pass

        # 合并会话头
        req_headers = dict(self.session.headers)
        req_headers.update(headers)

        # ---- Global throttle ----
        # Douban is very sensitive to bursty traffic; enforce a minimum interval between
        # requests across the whole process.
        try:
            min_interval_ms = int(os.getenv("DOUBAN_MIN_INTERVAL_MS", "1200"))
        except Exception:
            min_interval_ms = 1200
        min_interval_ms = max(0, min(min_interval_ms, 10000))

        if min_interval_ms > 0:
            with DoubanClient._throttle_lock:
                now = time.monotonic()
                wait_s = (DoubanClient._last_request_ts + (min_interval_ms / 1000.0)) - now
                if wait_s > 0:
                    time.sleep(wait_s)
                DoubanClient._last_request_ts = time.monotonic()

        # 重试策略，处理临时 403/5xx
        last_exc = None
        rotate_ua = (os.getenv("DOUBAN_ROTATE_UA", "0") or "").strip().lower() in ("1", "true", "yes")
        ua_list = [
            USER_AGENT,
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Safari/605.1.15",
        ]
        max_attempts = max(1, int(max_attempts) if max_attempts else 1)
        for attempt in range(max_attempts):
            try:
                # 默认使用稳定 UA（更贴近“真实浏览器 + cookie”的一致性），可选开启轮换
                if rotate_ua:
                    req_headers['User-Agent'] = random.choice(ua_list)
                else:
                    req_headers['User-Agent'] = USER_AGENT
                resp = self.session.get(url, headers=req_headers, timeout=timeout)
                resp.raise_for_status()
                return resp.text
            except requests.HTTPError as e:
                last_exc = e
                code = getattr(e.response, 'status_code', None)
                # 对 403/429/5xx 采取退避重试
                if (retry_on_403_429 and code in (403, 429)) or (code and 500 <= code < 600):
                    backoff = min(30, (2 ** attempt)) + random.random()
                    time.sleep(backoff)
                    # 在重试时改变部分头，模拟浏览器
                    req_headers['Accept'] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
                    req_headers['Sec-Fetch-Mode'] = "navigate"
                    continue
                raise
            except Exception as e:
                last_exc = e
                time.sleep(0.5 + random.random())
                continue
        # 如果所有重试都失败，抛出最后的异常
        if last_exc:
            raise last_exc
        raise RuntimeError('请求失败但没有捕获到异常')

    def set_cookies_from_string(self, cookie_str: str):
        """接受浏览器复制的 Cookie header 字符串（例如 'a=1; b=2; ...'），将其加入 session."""
        try:
            parts = [p.strip() for p in cookie_str.split(';') if p.strip()]
            for p in parts:
                if '=' in p:
                    k, v = p.split('=', 1)
                    self.session.cookies.set(k.strip(), v.strip())
        except Exception:
            pass

    def close(self):
        self.session.close()