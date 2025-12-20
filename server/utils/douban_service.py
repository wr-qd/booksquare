from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional


def _instance_cookie_path() -> str:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    instance_dir = os.path.join(base_dir, "instance")
    os.makedirs(instance_dir, exist_ok=True)
    return os.path.join(instance_dir, "douban_cookies.json")


def _has_login_cookies(cookies: List[Dict[str, Any]]) -> bool:
    # Very rough heuristic: Douban logged-in sessions typically include `dbcl2` and `ck`.
    names = {c.get("name") for c in cookies if isinstance(c, dict)}
    return ("dbcl2" in names) and ("ck" in names)


def _cookies_to_header(cookies: List[Dict[str, Any]]) -> str:
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


class DoubanService:
    """Open a real browser for the user to log in to Douban, then persist cookies.

    This is intended for local development: user logs in interactively in Chromium,
    then we reuse the cookies for subsequent requests via `DOUBAN_COOKIE`.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

        self._login_running = False
        self._last_error: Optional[str] = None
        self._logged_in = False
        self._cookie_path = _instance_cookie_path()

    def is_logged_in(self) -> bool:
        # Prefer in-memory flag; fallback to persisted cookie presence.
        if self._logged_in:
            return True
        try:
            cookies = self.load_cookies()
            return _has_login_cookies(cookies)
        except Exception:
            return False

    def status(self) -> Dict[str, Any]:
        return {
            "logged_in": self.is_logged_in(),
            "login_running": bool(self._login_running),
            "last_error": self._last_error,
            "cookie_path": self._cookie_path,
        }

    def load_cookies(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self._cookie_path):
            return []
        with open(self._cookie_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        return []

    def save_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(self._cookie_path), exist_ok=True)
        with open(self._cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

    def clear_cookies(self) -> None:
        self._logged_in = False
        try:
            if os.path.exists(self._cookie_path):
                os.remove(self._cookie_path)
        except Exception:
            pass

    def export_cookie_header(self) -> str:
        cookies = self.load_cookies()
        return _cookies_to_header(cookies)

    def start_login(self, timeout: float = 240.0) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._last_error = None
            self._login_running = True
            self._logged_in = False

            t = threading.Thread(target=self._login_worker, args=(timeout,), name="douban-login", daemon=True)
            self._thread = t
            t.start()

    def login(self, timeout: float = 240.0) -> None:
        self.start_login(timeout=timeout)
        t = self._thread
        if not t:
            raise RuntimeError("DOUBAN_LOGIN_NOT_STARTED")
        t.join(timeout=timeout + 30)
        if self._login_running:
            raise TimeoutError("Douban login timeout")
        if self._last_error:
            raise RuntimeError(self._last_error)

    def _login_worker(self, timeout: float) -> None:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(viewport={"width": 1280, "height": 720})

                # Load existing cookies (if any) to keep session.
                try:
                    existing = self.load_cookies()
                    if existing:
                        context.add_cookies(existing)
                except Exception:
                    pass

                page = context.new_page()
                # Direct user to Douban login page.
                page.goto("https://accounts.douban.com/passport/login", wait_until="domcontentloaded", timeout=60000)

                start = time.monotonic()
                while True:
                    cookies = context.cookies()
                    if _has_login_cookies(cookies):
                        self.save_cookies(cookies)
                        self._logged_in = True
                        break
                    if (time.monotonic() - start) >= float(timeout):
                        raise TimeoutError("Douban login timeout")
                    time.sleep(1)

                try:
                    browser.close()
                except Exception:
                    pass

            self._last_error = None
        except Exception as e:
            self._last_error = str(e)
        finally:
            self._login_running = False


_singleton: Optional[DoubanService] = None


def get_douban_service() -> DoubanService:
    global _singleton
    if _singleton is None:
        _singleton = DoubanService()
    return _singleton
