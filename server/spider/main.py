import asyncio
import argparse
from spider.platforms.douban.crawler import DoubanCrawler

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=["douban"], required=True)
    parser.add_argument("--type", default="comment")
    parser.add_argument("--book_id", required=True)
    args = parser.parse_args()

    if args.platform == "douban":
        crawler = DoubanCrawler(args.book_id, args.type)
        await crawler.start()

if __name__ == "__main__":
    asyncio.run(main())