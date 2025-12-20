from __future__ import annotations

from playwright.sync_api import sync_playwright

URL = "https://search.bilibili.com/article?keyword=%E4%B8%89%E4%BD%93%20%E4%B9%A6%E8%AF%84"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(locale="zh-CN")
        page = context.new_page()

        hits: list[tuple[int, str]] = []

        def on_response(r):
            u = r.url or ""
            if "bilibili.com" in u and ("search" in u or "wbi" in u):
                try:
                    hits.append((int(r.status), u))
                except Exception:
                    hits.append((0, u))

        page.on("response", on_response)
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)

        print("title=", page.title())
        print("hit_count=", len(hits))
        for st, u in hits[:50]:
            print(st, u)

        browser.close()


if __name__ == "__main__":
    main()
