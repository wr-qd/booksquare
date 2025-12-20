import os
import time
import random
import json
from typing import List, Dict
from spider.platforms.douban.client import DoubanClient
from spider.platforms.douban.parser import DoubanParser
from spider.platforms.douban.search import search_books_by_keyword
from spider.tools.wordcloud_generator import generate_wordcloud_from_texts


def fetch_with_playwright(url: str, timeout: int = 20000) -> str:
    """使用 Playwright 在 headless 浏览器中获取页面 HTML，作为对 403 的回退方案"""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        raise RuntimeError("Playwright 未安装或不可用，请安装 playwright 并配置浏览器")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()
        page.goto(url, wait_until='networkidle', timeout=timeout)
        content = page.content()
        try:
            context.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass
        return content


class DoubanSearchCrawler:
    """基于关键词的即搜即爬器：搜索 Top-N 候选并抓取详情及评论，生成词云并保存结果。"""

    def __init__(self):
        self.client = DoubanClient()
        self.parser = DoubanParser()

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass

    def crawl_by_keyword(self, keyword: str, top_n: int = 5, max_comments_per_book: int = 500, output_dir: str = "output") -> List[Dict]:
        os.makedirs(output_dir, exist_ok=True)
        candidates = search_books_by_keyword(keyword, top_n=top_n)
        results: List[Dict] = []
        for idx, book in enumerate(candidates, 1):
            book_id = book.get("book_id")
            if not book_id:
                continue
            print(f"[{idx}/{len(candidates)}] 抓取 book_id={book_id} 标题={book.get('title')}")
            # 详情
            detail_html = None
            detail = {}
            try:
                detail_html = self.client.get(f"https://book.douban.com/subject/{book_id}/")
                detail = self.parser.extract_book_detail(detail_html) or {}
            except Exception as e:
                print(f"  无法获取详情: {e}")

            # 评论分页抓取
            comments: List[Dict] = []
            page = 0
            per_page = 20
            prev_url = None
            while len(comments) < max_comments_per_book:
                start = page * per_page
                url = f"https://book.douban.com/subject/{book_id}/comments/?start={start}&limit={per_page}&status=P&sort=score"
                try:
                    # 为每一页设置合理的 Referer（首页为详情页，后续页为上一页评论）
                    extra = {}
                    if page == 0:
                        extra['Referer'] = f"https://book.douban.com/subject/{book_id}/"
                    elif prev_url:
                        extra['Referer'] = prev_url
                    html = self.client.get(url, extra_headers=extra)
                except Exception as e:
                    # 若请求被网站限制（如 403），尝试使用 Playwright 渲染页面获取 HTML
                    print(f"  评论页请求失败: {e}，尝试使用 Playwright 回退获取页面")
                    try:
                        html = fetch_with_playwright(url)
                    except Exception as e2:
                        print(f"  Playwright 回退失败: {e2}")
                        break
                page_comments = self.parser.extract_comments(html)
                if not page_comments:
                    break
                for c in page_comments:
                    c.setdefault("book_id", book_id)
                comments.extend(page_comments)
                if len(page_comments) < per_page:
                    break
                page += 1
                time.sleep(random.uniform(0.2, 1.0))
                # 记录本页 URL 作为下页的 Referer
                prev_url = url
                if len(comments) >= max_comments_per_book:
                    comments = comments[:max_comments_per_book]
                    break

            print(f"  获取评论 {len(comments)} 条")

            # 词云
            texts = [c.get("content", "") for c in comments if c.get("content")]
            wc_path = None
            if texts:
                wc_path = generate_wordcloud_from_texts(texts, book_id, output_dir=output_dir)

            nicknames = [c.get("user") for c in comments if c.get("user")]

            result = {
                "book_id": book_id,
                "title": detail.get("title") or book.get("title"),
                "author": detail.get("author_name") or book.get("author"),
                "rating": detail.get("rating") or book.get("rating"),
                "isbn": detail.get("isbn"),
                "cover_url": detail.get("img_src") or book.get("cover_url"),
                "comments_count": len(comments),
                "comments": comments,
                "commenter_nicknames": nicknames,
                "wordcloud_path": wc_path,
            }

            out_json = os.path.join(output_dir, f"book_{book_id}.json")
            try:
                with open(out_json, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"  保存 JSON 失败: {e}")

            results.append(result)
            time.sleep(random.uniform(0.2, 0.8))

        self.close()
        return results
