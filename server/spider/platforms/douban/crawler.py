import time
import random
from spider.base.abstract_crawler import AbstractCrawler
from spider.platforms.douban.client import DoubanClient
from spider.platforms.douban.parser import DoubanParser
from spider.data.store import DoubanStore
from spider.base.utils import random_delay
from typing import List, Dict

class DoubanCrawler(AbstractCrawler):
    def __init__(self, book_id: str, crawl_type: str):
        super().__init__()
        self.book_id = book_id
        self.crawl_type = crawl_type  # "detail" 或 "comment"
        self.client = DoubanClient()
        self.parser = DoubanParser()
        self.store = DoubanStore()

    async def start(self):
        self.login()
        if self.crawl_type == "detail":
            raw_detail = self.fetch_book_detail(self.book_id)
            if raw_detail:
                parsed = self.parse_book_detail(raw_detail)
                self.save_book_detail(parsed)
                print(f"图书详情爬取完成: {parsed['title']}")
        elif self.crawl_type == "comment":
            raw_comments = self.fetch_comments(self.book_id)
            print(f"获取到 {len(raw_comments)} 条评论")
            for raw in raw_comments:
                parsed = self.parse_comment(raw)
                await self.save_comment(parsed)
            print("评论爬取完成")
        self.close()

    def login(self):
        # 豆瓣无需登录
        pass

    def fetch_book_detail(self, book_id: str) -> Dict:
        url = f"https://book.douban.com/subject/{book_id}/"
        html = self.client.get(url)
        return self.parser.extract_book_detail(html)

    def fetch_comments(self, book_id: str) -> List[Dict]:
        comments = []
        page = 0
        comments_per_page = 20
        max_comments = 30
        while len(comments) < max_comments:
            start = page * comments_per_page
            url = f"https://book.douban.com/subject/{book_id}/comments/?start={start}&limit=20&status=P&sort=score"
            html = self.client.get(url)
            page_comments = self.parser.extract_comments(html)
            if not page_comments:
                break
            comments.extend(page_comments)
            if len(comments) >= max_comments:
                comments = comments[:max_comments]
                break
            page += 1
            time.sleep(random.uniform(0.1, 2))
        return comments

    def parse_book_detail(self, raw_data: Dict) -> Dict:
        # 转换为统一Book格式
        return {
            "book_id": self.book_id,
            "title": raw_data.get("title"),
            "author": raw_data.get("author_name"),
            "cover_url": raw_data.get("img_src"),
            "rating": raw_data.get("rating"),
            "platform": "douban",
            "tags": [],  # 可扩展
        }

    def parse_comment(self, raw_data: Dict) -> Dict:
        # 转换为统一Comment格式
        return {
            "comment_id": raw_data["id"],
            "book_id": self.book_id,
            "content": raw_data["content"],
            "rating": raw_data.get("rating"),
            "user": raw_data["user"],
            "platform": "douban",
            "timestamp": raw_data["time"],
        }

    def save_book_detail(self, parsed_data: Dict):
        self.store.save_book(parsed_data)
        random_delay(1, 3)

    async def save_comment(self, parsed_data: Dict):
        self.store.save_comment(parsed_data)
        random_delay(1, 3)

    def close(self):
        self.client.close()