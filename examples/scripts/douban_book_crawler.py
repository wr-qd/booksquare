import requests
from bs4 import BeautifulSoup
import time
import json
import re
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from collections import Counter
import jieba
import jieba.analyse
from typing import Dict, List, Optional
import os

class DoubanBookCrawler:
    """豆瓣图书爬虫类"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session = requests.Session()
        
    def search_book(self, book_name: str) -> List[Dict]:
        """
        搜索图书 - 使用豆瓣搜索
        :param book_name: 书名
        :return: 图书列表
        """
        # 使用豆瓣搜索页面（老版本）
        import urllib.parse
        encoded_name = urllib.parse.quote(book_name)
        search_url = f"https://www.douban.com/search?cat=1001&q={encoded_name}"
        
        try:
            response = self.session.get(search_url, headers=self.headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            books = []
            # 查找搜索结果
            items = soup.select('.result')
            
            for item in items:
                try:
                    # 确保是图书结果
                    if 'book.douban.com' not in item.get_text():
                        continue
                    
                    title_elem = item.select_one('.title h3 a')
                    if not title_elem:
                        continue
                    
                    url = title_elem['href']
                    # 确保是图书链接
                    if 'book.douban.com/subject/' not in url:
                        continue
                    
                    title = title_elem.text.strip()
                    
                    # 获取评分
                    rating_elem = item.select_one('.rating_nums')
                    rating = rating_elem.text.strip() if rating_elem else '暂无评分'
                    
                    # 获取简介
                    abstract = item.select_one('.abstract')
                    author = abstract.text.strip() if abstract else ''
                    
                    # 获取封面
                    img = item.select_one('img')
                    cover = img['src'] if img and 'src' in img.attrs else ''
                    
                    book_info = {
                        'title': title,
                        'cover': cover,
                        'url': url,
                        'rating': rating,
                        'author': author
                    }
                    books.append(book_info)
                except Exception as e:
                    print(f"解析项目失败: {e}")
                    continue
            
            # 如果搜索页面没有结果，尝试直接访问图书页面
            if not books:
                print("搜索页面未找到结果，尝试直接搜索...")
                # 尝试通过标签搜索
                tag_url = f"https://book.douban.com/tag/{encoded_name}"
                response2 = self.session.get(tag_url, headers=self.headers, timeout=10)
                response2.encoding = 'utf-8'
                soup2 = BeautifulSoup(response2.text, 'html.parser')
                
                tag_items = soup2.select('.subject-item')
                for item in tag_items[:5]:
                    try:
                        title_elem = item.select_one('.info h2 a')
                        url = title_elem['href']
                        title = title_elem['title']
                        
                        rating_elem = item.select_one('.rating_nums')
                        rating = rating_elem.text.strip() if rating_elem else '暂无评分'
                        
                        pub_elem = item.select_one('.pub')
                        author = pub_elem.text.strip() if pub_elem else ''
                        
                        img = item.select_one('img')
                        cover = img['src'] if img else ''
                        
                        books.append({
                            'title': title,
                            'cover': cover,
                            'url': url,
                            'rating': rating,
                            'author': author
                        })
                    except:
                        continue
                    
            return books
        except Exception as e:
            print(f"搜索失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def download_cover(self, cover_url: str, book_id: str) -> str:
        """
        下载图书封面
        :param cover_url: 封面URL
        :param book_id: 图书ID
        :return: 本地封面路径
        """
        if not cover_url:
            return None
        
        try:
            # 确保输出目录存在
            os.makedirs('output_covers', exist_ok=True)
            
            # 获取文件扩展名
            ext = os.path.splitext(cover_url.split('?')[0])[-1] or '.jpg'
            local_path = f'output_covers/cover_{book_id}{ext}'
            
            # 下载封面
            response = self.session.get(cover_url, timeout=10)
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            print(f"封面已下载至: {local_path}")
            return local_path
        except Exception as e:
            print(f"下载封面失败: {e}")
            return None
    
    def get_book_detail(self, book_url: str) -> Dict:
        """
        获取图书详情
        :param book_url: 图书URL
        :return: 图书详细信息
        """
        try:
            response = self.session.get(book_url, headers=self.headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取图书ID
            book_id = re.search(r'/subject/(\d+)', book_url).group(1)
            
            # 获取封面URL
            cover_url = soup.select_one('#mainpic img')['src'] if soup.select_one('#mainpic img') else ''
            
            detail = {
                'book_id': book_id,
                'title': soup.select_one('h1 span').text.strip() if soup.select_one('h1 span') else '',
                'cover': cover_url,
                'cover_local': None,  # 本地封面路径
                'rating': soup.select_one('.rating_num').text.strip() if soup.select_one('.rating_num') else '0',
                'rating_people': soup.select_one('.rating_people span').text.strip() if soup.select_one('.rating_people span') else '0',
                'author': '',
                'publisher': '',
                'publish_date': '',
                'price': '',
                'tags': [],
                'intro': ''
            }
            
            # 提取作者、出版社等信息
            info_div = soup.select_one('#info')
            if info_div:
                info_text = info_div.get_text()
                
                author_match = re.search(r'作者:(.*?)(?:\n|出版社)', info_text)
                if author_match:
                    detail['author'] = author_match.group(1).strip()
                
                publisher_match = re.search(r'出版社:(.*?)\n', info_text)
                if publisher_match:
                    detail['publisher'] = publisher_match.group(1).strip()
                
                date_match = re.search(r'出版年:(.*?)\n', info_text)
                if date_match:
                    detail['publish_date'] = date_match.group(1).strip()
                
                price_match = re.search(r'定价:(.*?)\n', info_text)
                if price_match:
                    detail['price'] = price_match.group(1).strip()
            
            # 提取标签
            tags = soup.select('.tag a')
            detail['tags'] = [tag.text.strip() for tag in tags[:10]]
            
            # 提取简介
            intro_div = soup.select_one('.intro .all')
            if not intro_div:
                intro_div = soup.select_one('.intro')
            if intro_div:
                detail['intro'] = intro_div.get_text().strip()
            
            # 下载封面
            if cover_url:
                detail['cover_local'] = self.download_cover(cover_url, book_id)
            
            return detail
            
        except Exception as e:
            print(f"获取详情失败: {e}")
            return {}
    
    def get_comments(self, book_id: str, page: int = 1, limit: int = 20) -> Dict:
        """
        获取图书评论
        :param book_id: 图书ID
        :param page: 页码
        :param limit: 每页数量
        :return: 评论数据
        """
        start = (page - 1) * limit
        # 参考原有爬虫代码的URL格式
        comment_url = f"https://book.douban.com/subject/{book_id}/comments/?start={start}&limit=20&status=P&sort=score"
        
        try:
            # 添加referer
            headers = self.headers.copy()
            headers['Referer'] = f"https://book.douban.com/subject/{book_id}/"
            
            response = self.session.get(comment_url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            comments = []
            comment_items = soup.select('.comment-item')
            
            for item in comment_items:
                try:
                    # 用户名
                    user_elem = item.select_one('.comment-info a')
                    user_name = user_elem.text.strip() if user_elem else '匿名'
                    
                    # 评分（星级）
                    rating_elem = item.select_one('.rating')
                    rating = 0
                    if rating_elem and 'class' in rating_elem.attrs:
                        classes = rating_elem['class']
                        for c in classes:
                            if 'allstar' in c:
                                rating = int(c.replace('allstar', '')) // 10
                                break
                    
                    # 时间
                    time_elem = item.select_one('.comment-time')
                    comment_time = time_elem['title'] if time_elem and 'title' in time_elem.attrs else (time_elem.text.strip() if time_elem else '')
                    
                    # 点赞数
                    vote_elem = item.select_one('.vote-count')
                    vote = vote_elem.text.strip() if vote_elem else '0'
                    
                    # 评论内容
                    content_elem = item.select_one('.short')
                    content = content_elem.text.strip() if content_elem else ''
                    
                    comment = {
                        'user_name': user_name,
                        'rating': rating,
                        'time': comment_time,
                        'vote': vote,
                        'content': content
                    }
                    comments.append(comment)
                except Exception as e:
                    print(f"解析评论失败: {e}")
                    continue
            
            # 计算总页数 - 优化查找逻辑
            total_pages = 1
            
            # 方法1: 查找分页器
            paginator = soup.select_one('.paginator')
            if paginator:
                # 查找所有页码链接
                page_links = paginator.select('a')
                for link in page_links:
                    try:
                        page_num = int(link.text.strip())
                        if page_num > total_pages:
                            total_pages = page_num
                    except:
                        continue
            
            # 方法2: 查找"后页"链接的start参数
            next_link = soup.select_one('a[href*="start="]')
            if next_link and total_pages == 1:
                try:
                    import re
                    all_starts = re.findall(r'start=(\d+)', str(soup))
                    if all_starts:
                        max_start = max([int(s) for s in all_starts])
                        total_pages = (max_start // limit) + 1
                except:
                    pass
            
            # 方法3: 如果有评论但没找到分页，可能只有一页或需要模拟更多页
            if comments and total_pages == 1:
                # 假设可能有更多页，允许继续爬取
                total_pages = 9999  # 设置一个大数，让调用者决定何时停止
            
            time.sleep(1)  # 避免请求过快
            
            return {
                'comments': comments,
                'current_page': page,
                'total_pages': total_pages,
                'total_comments': len(comments)
            }
            
        except Exception as e:
            print(f"获取评论失败: {e}")
            return {'comments': [], 'current_page': page, 'total_pages': 1}
    
    def get_all_comments(self, book_id: str, max_pages: int = 10) -> List[Dict]:
        """
        获取所有评论（多页）
        :param book_id: 图书ID
        :param max_pages: 最大页数
        :return: 所有评论列表
        """
        all_comments = []
        total_pages_info = None
        
        for page in range(1, max_pages + 1):
            result = self.get_comments(book_id, page)
            
            if not result['comments']:
                print(f"第 {page} 页没有评论，停止爬取")
                break
            
            # 显示进度
            if total_pages_info is None:
                total_pages_info = result['total_pages']
                actual_max = min(max_pages, total_pages_info)
                print(f"共有 {total_pages_info} 页评论，将爬取 {actual_max} 页")
            
            all_comments.extend(result['comments'])
            print(f"✓ 第 {page}/{min(max_pages, total_pages_info)} 页完成，已获取 {len(all_comments)} 条评论")
            
            if page >= result['total_pages']:
                print(f"已到达最后一页")
                break
            
            # 动态调整延迟，避免被封
            if page % 10 == 0:
                print("休息5秒...")
                time.sleep(5)
            else:
                time.sleep(2)
        
        return all_comments


class WordCloudGenerator:
    """词云生成器"""
    
    def __init__(self, font_path: str = None):
        # Windows系统中文字体路径
        if font_path is None:
            possible_fonts = [
                'C:\\Windows\\Fonts\\simhei.ttf',  # 黑体
                'C:\\Windows\\Fonts\\msyh.ttc',     # 微软雅黑
                'C:\\Windows\\Fonts\\simsun.ttc',   # 宋体
            ]
            for font in possible_fonts:
                if os.path.exists(font):
                    font_path = font
                    break
        
        self.font_path = font_path
        
        # 停用词
        self.stop_words = set([
            '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
            '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
            '自己', '这', '那', '里', '就是', '为', '能', '之', '与', '及', '对', '个', '能',
            '这本', '这本书', '作者', '书', '这个', '觉得', '感觉', '还是', '但是', '可以',
            '还', '比较', '非常', '更', '之后', '看到', '读', '读完', '阅读', '书中', '真的',
            '太', '让', '给', '把', '被', '从', '像', '又', '再', '才', '并', '却', '而',
            '已经', '已', '还有', '没', '么', '吗', '呢', '吧', '啊', '哦', '嗯'
        ])
    
    def extract_keywords(self, comments: List[Dict], top_k: int = 100) -> List[tuple]:
        """
        从评论中提取关键词
        :param comments: 评论列表
        :param top_k: 提取前k个关键词
        :return: 关键词列表 [(词, 权重), ...]
        """
        # 合并所有评论内容
        all_text = ' '.join([comment['content'] for comment in comments if comment['content']])
        
        # 使用jieba提取关键词
        keywords = jieba.analyse.extract_tags(all_text, topK=top_k, withWeight=True)
        
        # 过滤停用词
        filtered_keywords = [(word, weight) for word, weight in keywords 
                           if word not in self.stop_words and len(word) > 1]
        
        return filtered_keywords
    
    def generate_wordcloud(self, comments: List[Dict], output_path: str = 'wordcloud.png') -> str:
        """
        生成词云图片
        :param comments: 评论列表
        :param output_path: 输出路径
        :return: 输出路径
        """
        # 提取关键词
        keywords = self.extract_keywords(comments)
        
        if not keywords:
            print("没有足够的关键词生成词云")
            return None
        
        # 创建词频字典
        word_freq = dict(keywords)
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        
        # 生成词云
        try:
            if self.font_path and os.path.exists(self.font_path):
                wordcloud = WordCloud(
                    font_path=self.font_path,
                    width=800,
                    height=600,
                    background_color='white',
                    max_words=100,
                    relative_scaling=0.5,
                    colormap='viridis'
                ).generate_from_frequencies(word_freq)
            else:
                print("警告: 未找到中文字体，词云可能无法显示中文")
                wordcloud = WordCloud(
                    width=800,
                    height=600,
                    background_color='white',
                    max_words=100
                ).generate_from_frequencies(word_freq)
            
            # 保存图片
            plt.figure(figsize=(12, 8))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis('off')
            plt.tight_layout(pad=0)
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"词云已保存至: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"生成词云失败: {e}")
            return None


def main():
    """主函数示例"""
    # 确保输出目录存在
    os.makedirs('output_test', exist_ok=True)
    os.makedirs('output_wc', exist_ok=True)
    
    # 初始化爬虫
    crawler = DoubanBookCrawler()
    wc_generator = WordCloudGenerator()
    
    # 输入书名 - 使用sys.argv或input
    import sys
    if len(sys.argv) > 1:
        book_name = sys.argv[1]
        max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    else:
        book_name = input("请输入书名: ").strip()
        max_pages_input = input("请输入要爬取的页数（每页20条，输入0爬取全部，默认10页）: ").strip()
        max_pages = int(max_pages_input) if max_pages_input else 10
    
    # 1. 搜索图书
    print(f"\n正在搜索: {book_name}")
    books = crawler.search_book(book_name)
    
    if not books:
        print("未找到相关图书")
        return
    
    print(f"\n找到 {len(books)} 本相关图书:")
    for i, book in enumerate(books[:5]):
        print(f"{i+1}. {book['title']} - 评分: {book['rating']}")
    
    # 选择第一本书
    selected_book = books[0]
    book_url = selected_book['url']
    
    # 2. 获取图书详情
    print(f"\n正在获取《{selected_book['title']}》的详细信息...")
    detail = crawler.get_book_detail(book_url)
    
    print(f"\n=== 图书详情 ===")
    print(f"书名: {detail['title']}")
    print(f"作者: {detail['author']}")
    print(f"封面: {detail['cover']}")
    print(f"评分: {detail['rating']} ({detail['rating_people']}人评价)")
    print(f"出版社: {detail['publisher']}")
    print(f"出版时间: {detail['publish_date']}")
    print(f"价格: {detail['price']}")
    print(f"标签: {', '.join(detail['tags'])}")
    print(f"简介: {detail['intro'][:100]}..." if detail['intro'] else "简介: 暂无")
    
    # 3. 获取评论
    book_id = detail['book_id']
    print(f"\n正在获取评论...")
    if max_pages == 0:
        print("注意: 爬取全部评论可能需要很长时间，建议先测试少量页数")
        confirm = input("确认爬取全部评论？(y/n): ").strip().lower()
        if confirm != 'y':
            max_pages = 10
            print("已改为爬取10页")
    
    comments = crawler.get_all_comments(book_id, max_pages=max_pages if max_pages > 0 else 999)
    
    print(f"\n=== 评论列表 (共{len(comments)}条) ===")
    for i, comment in enumerate(comments[:10]):
        print(f"\n评论 {i+1}:")
        print(f"用户: {comment['user_name']}")
        print(f"评分: {'⭐' * comment['rating']}")
        print(f"时间: {comment['time']}")
        print(f"内容: {comment['content'][:100]}..." if len(comment['content']) > 100 else f"内容: {comment['content']}")
        print(f"点赞: {comment['vote']}")
    
    # 4. 生成词云
    wc_path = None
    if comments:
        print(f"\n正在生成词云...")
        output_path = f"output_wc/wordcloud_{book_id}.png"
        wc_path = wc_generator.generate_wordcloud(comments, output_path)
        
        if wc_path:
            print(f"词云生成成功!")
    
    # 5. 保存数据
    result = {
        'book_detail': detail,
        'comments': comments,
        'wordcloud_path': wc_path
    }
    
    output_file = f'output_test/book_{book_id}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n数据已保存至: {output_file}")
    print(f"\n=== 完成 ===")
    print(f"图书ID: {book_id}")
    print(f"评论数: {len(comments)}")
    print(f"数据文件: {output_file}")
    if wc_path:
        print(f"词云图片: {wc_path}")


if __name__ == '__main__':
    main()
