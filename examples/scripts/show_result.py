import json

# 读取JSON文件
with open('output_test/book_6082808.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 显示书籍信息
book = data['book_detail']
print("=" * 50)
print("📚 百年孤独 - 爬取结果")
print("=" * 50)
print(f"\n【书籍信息】")
print(f"书名: {book['title']}")
print(f"评分: {book['rating']} ({book['rating_people']})")
print(f"作者: {book.get('author', '暂无')}")
print(f"出版社: {book.get('publisher', '暂无')}")
print(f"出版时间: {book.get('publish_date', '暂无')}")
print(f"价格: {book.get('price', '暂无')}")
print(f"封面URL: {book['cover']}")
print(f"本地封面: {book['cover_local']}")
print(f"标签: {', '.join(book['tags']) if book['tags'] else '暂无'}")

# 显示评论统计
comments = data['comments']
print(f"\n【评论统计】")
print(f"评论总数: {len(comments)} 条")
print(f"词云路径: {data['wordcloud_path']}")

# 统计评分分布
rating_dist = {}
for c in comments:
    rating = c['rating']
    rating_dist[rating] = rating_dist.get(rating, 0) + 1

print(f"\n【评分分布】")
for rating in sorted(rating_dist.keys(), reverse=True):
    stars = '⭐' * rating if rating > 0 else '无评分'
    print(f"{stars}: {rating_dist[rating]} 条")

# 显示点赞最多的前10条评论
print(f"\n【点赞最多的前10条评论】")
sorted_comments = sorted(comments, key=lambda x: int(x['vote']), reverse=True)[:10]
for i, c in enumerate(sorted_comments, 1):
    print(f"\n{i}. {c['user_name']} (点赞 {c['vote']})")
    print(f"   评分: {'⭐' * c['rating']}")
    print(f"   内容: {c['content'][:80]}...")

print("\n" + "=" * 50)
print("✅ 数据爬取成功！")
print("=" * 50)
