import os
from typing import List, Optional
import jieba
from wordcloud import WordCloud

# 默认中文字体（如仓库中存在 docs/STZHONGS.TTF）
DEFAULT_FONT = "./docs/STZHONGS.TTF"


def generate_wordcloud_from_texts(texts: List[str], book_id: str, output_dir: str = "output") -> Optional[str]:
    if not texts:
        return None
    os.makedirs(output_dir, exist_ok=True)
    full = "\n".join(texts)
    seg = " ".join(jieba.cut(full, cut_all=False))
    font_path = DEFAULT_FONT if os.path.exists(DEFAULT_FONT) else None
    wc = WordCloud(font_path=font_path, width=900, height=500, background_color="white", max_words=200)
    wc.generate(seg)
    out_png = os.path.join(output_dir, f"book_{book_id}_wordcloud.png")
    wc.to_file(out_png)
    return out_png
