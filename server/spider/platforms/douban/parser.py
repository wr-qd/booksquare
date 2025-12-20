from bs4 import BeautifulSoup
from typing import List, Dict
import re


class DoubanParser:
    def extract_book_detail(self, html: str) -> Dict:
        """从书籍详情页 HTML 中提取基本信息和评分等"""
        soup = BeautifulSoup(html, "html.parser")
        book = {}
        try:
            title_el = soup.select_one('h1 > span')
            book['title'] = title_el.text.strip() if title_el else None
            img_el = soup.select_one('#mainpic .nbg img')
            book['img_src'] = img_el['src'] if img_el and img_el.get('src') else None
            info = soup.select_one('#info')
            if info:
                def get_after(label):
                    el = info.find('span', class_='pl', string=re.compile(label))
                    if not el:
                        return None

                    # 文本通常在 el 的后续 sibling（常见为 ':' + 真实内容）或 el.parent 的子节点中
                    def pick_from_siblings():
                        cur = el.next_sibling
                        # 跳过 ':' / 空白
                        while cur is not None:
                            if isinstance(cur, str):
                                s = cur.strip()
                                if not s or s == ':' or s == '：':
                                    cur = cur.next_sibling if hasattr(cur, 'next_sibling') else None
                                    continue
                                return s
                            # Tag
                            txt = getattr(cur, 'get_text', lambda **_: '')(strip=True)
                            if txt:
                                return txt
                            cur = cur.next_sibling
                        return None

                    val = pick_from_siblings()
                    if val:
                        return val

                    # 作者常见为链接列表
                    parent = el.parent
                    if parent:
                        links = [a.get_text(strip=True) for a in parent.find_all('a')]
                        links = [x for x in links if x]
                        if links:
                            return ' / '.join(links)

                    # 最后兜底：从父节点文本中按 ':' 分割
                    text = el.parent.get_text(separator=' ', strip=True)
                    text = re.sub(r"\s+", " ", text)
                    parts = re.split(r"[:：]", text, maxsplit=1)
                    return parts[1].strip() if len(parts) > 1 else None

                book['author_name'] = get_after('作者')
                book['publisher'] = get_after('出版社')
                book['isbn'] = get_after('ISBN')
            rating_div = soup.select_one('#interest_sectl')
            if rating_div:
                r = rating_div.select_one('strong.rating_num')
                try:
                    book['rating'] = float(r.text.strip()) if r else None
                except Exception:
                    book['rating'] = None
        except Exception:
            pass
        return book

    def extract_comments(self, html: str) -> List[Dict]:
        """从评论页 HTML 中提取多个评论，返回列表，每项包含 id/user/content/rating/time/useful"""
        soup = BeautifulSoup(html, "html.parser")
        comments = []
        for item in soup.select('.comment-item'):
            try:
                cid = item.get('data-cid') or item.get('data-id') or None
                user_el = item.select_one('.comment-info a')
                user = user_el.text.strip() if user_el else None
                content_el = item.select_one('.comment-content')
                # 评论文本可能包含换行/空格
                content = content_el.text.strip() if content_el else ""
                # 评分类名中常见 allstarXX
                rating = None
                rating_el = item.select_one('.rating')
                if rating_el:
                    for cls in rating_el.get('class', []):
                        m = re.search(r'allstar(\d+)', cls)
                        if m:
                            try:
                                rating = int(m.group(1)) // 10
                            except Exception:
                                rating = None
                            break
                time_el = item.select_one('.comment-time')
                time_text = time_el.get('title') or time_el.text.strip() if time_el else None
                vote_el = item.select_one('.vote-count')
                useful = 0
                if vote_el:
                    try:
                        useful = int(vote_el.text.strip())
                    except Exception:
                        useful = 0
                comments.append({
                    "id": cid,
                    "user": user,
                    "content": content,
                    "rating": rating,
                    "time": time_text,
                    "useful": useful,
                })
            except Exception:
                continue
        return comments