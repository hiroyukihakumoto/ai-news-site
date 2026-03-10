import os
import sys
import json
import html
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from collections import defaultdict

import feedparser
from newspaper import Article
from openai import OpenAI

RSS_URL = "https://feeds.bbci.co.uk/news/world/rss.xml"
MAX_ARTICLES = 3

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR
DATA_FILE = BASE_DIR / "articles.json"

SITE_TITLE = "AI News Site"
SITE_DESCRIPTION = "公開情報をもとにした要約・分析記事"

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("OPENAI_API_KEY が見つかりません。")
    sys.exit(1)

client = OpenAI(api_key=api_key)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_filename(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[\\/:*?\"<>|]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text[:80] if text else "article"


def load_articles():
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            return []
    return []


def save_articles(data):
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def normalize_sources(item):
    """
    旧形式:
      source_name, source_url
    新形式:
      sources = [{name, url, type}]
    """
    if "sources" in item and isinstance(item["sources"], list):
        return item["sources"]

    source_name = item.get("source_name", "unknown")
    source_url = item.get("source_url", "")
    if source_url:
        return [{
            "name": source_name,
            "url": source_url,
            "type": "secondary"
        }]
    return []


def article_exists(existing_articles, source_url):
    for item in existing_articles:
        sources = normalize_sources(item)
        for src in sources:
            if src.get("url") == source_url:
                return True
    return False


def detect_category(text: str) -> str:
    t = text.lower()

    if any(k in t for k in ["sanction", "sanctions", "embargo", "tariff", "制裁", "関税"]):
        return "外交 / 制裁"

    if any(k in t for k in ["oil", "gas", "lng", "energy", "pipeline", "原油", "天然ガス", "電力", "エネルギー"]):
        return "資源 / エネルギー"

    if any(k in t for k in ["military", "troops", "missile", "ceasefire", "war", "conflict", "軍", "停戦", "戦闘", "戦争"]):
        return "安全保障 / 戦争"

    if any(k in t for k in ["inflation", "interest rate", "gdp", "recession", "economy", "物価", "金利", "景気", "経済"]):
        return "経済 / 景気"

    if any(k in t for k in ["japan", "yen", "日本", "円", "国内"]):
        return "日本への影響"

    if any(k in t for k in ["prepare", "preparedness", "備え", "対策", "stockpile", "evacuation", "防災"]):
        return "対策 / 備え"

    return "その他"


def make_sources_html(sources):
    if not sources:
        return "参照元情報はありません。"

    rows = []
    for src in sources:
        name = html.escape(src.get("name", "unknown"))
        url = html.escape(src.get("url", ""))
        src_type = html.escape(src.get("type", "unknown"))

        rows.append(
            f"""
            <div class="source-item">
                <strong>{name}</strong> ({src_type})<br>
                <a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>
            </div>
            """
        )
    return "\n".join(rows)


def make_article_html(page_title, body_text, sources, created_at, category):
    escaped_title = html.escape(page_title)
    escaped_body = html.escape(body_text).replace("\n", "<br>\n")
    sources_html = make_sources_html(sources)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escaped_title}</title>
    <style>
        body {{
            font-family: sans-serif;
            line-height: 1.9;
            max-width: 860px;
            margin: 40px auto;
            padding: 0 20px;
            color: #222;
            background: #fff;
        }}
        h1 {{
            font-size: 30px;
            margin-bottom: 12px;
            line-height: 1.5;
        }}
        .meta {{
            color: #666;
            font-size: 14px;
            margin-bottom: 10px;
        }}
        .badge {{
            display: inline-block;
            background: #eef4ff;
            color: #234;
            border: 1px solid #cdd9ee;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 13px;
            margin-bottom: 18px;
        }}
        .content {{
            font-size: 16px;
            margin-top: 20px;
        }}
        .box {{
            background: #f7f7f7;
            border: 1px solid #ddd;
            padding: 16px;
            margin-top: 28px;
            border-radius: 8px;
        }}
        .source-item {{
            margin-bottom: 12px;
        }}
        a {{
            color: #0066cc;
            word-break: break-all;
        }}
        .toplink {{
            display: inline-block;
            margin-top: 20px;
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <a class="toplink" href="index.html">← 記事一覧へ戻る</a>
    <h1>{escaped_title}</h1>
    <div class="badge">{html.escape(category)}</div>
    <div class="meta">作成日時: {html.escape(created_at)}</div>

    <div class="content">{escaped_body}</div>

    <div class="box">
        <strong>参照元</strong><br>
        {sources_html}
    </div>

    <div class="box">
        <strong>注意</strong><br>
        本記事は公開情報をもとにした要約・分析です。<br>
        報道機関の記事本文の転載を目的としたものではありません。<br>
        内容には推測を含む場合があり、今後の追加情報により変わる可能性があります。<br>
        一部ページには広告・アフィリエイトリンクを含むことがあります。
    </div>
</body>
</html>
"""


def make_index_html(articles):
    grouped = defaultdict(list)

    for item in articles:
        category = item.get("category", "その他")
        grouped[category].append(item)

    category_order = [
        "安全保障 / 戦争",
        "外交 / 制裁",
        "資源 / エネルギー",
        "経済 / 景気",
        "日本への影響",
        "対策 / 備え",
        "その他",
    ]

    sections = []

    for category in category_order:
        items = grouped.get(category, [])
        if not items:
            continue

        cards = []
        for item in items:
            sources = normalize_sources(item)
            source_names = ", ".join([s.get("name", "unknown") for s in sources]) if sources else "unknown"

            cards.append(f"""
            <article class="card">
                <h3><a href="{html.escape(item['file_name'])}">{html.escape(item['title'])}</a></h3>
                <div class="meta">作成日時: {html.escape(item.get('created_at', ''))}</div>
                <div class="meta">カテゴリ: {html.escape(item.get('category', 'その他'))}</div>
                <div class="meta">参照元: {html.escape(source_names)}</div>
                <p>{html.escape(item.get('summary', ''))}</p>
                <p><a href="{html.escape(item['file_name'])}">記事を読む</a></p>
            </article>
            """)

        sections.append(f"""
        <section class="category-section">
            <h2>{html.escape(category)}</h2>
            {''.join(cards)}
        </section>
        """)

    content = "\n".join(sections) if sections else "<p>まだ記事がありません。</p>"

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(SITE_TITLE)}</title>
    <style>
        body {{
            font-family: sans-serif;
            line-height: 1.8;
            max-width: 960px;
            margin: 40px auto;
            padding: 0 20px;
            color: #222;
            background: #fff;
        }}
        h1 {{
            font-size: 34px;
            margin-bottom: 8px;
        }}
        .desc {{
            color: #666;
            margin-bottom: 32px;
        }}
        .category-section {{
            margin-bottom: 40px;
        }}
        .category-section h2 {{
            font-size: 24px;
            border-bottom: 2px solid #ddd;
            padding-bottom: 8px;
            margin-bottom: 20px;
        }}
        .card {{
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            background: #fafafa;
        }}
        .card h3 {{
            margin-top: 0;
            font-size: 22px;
            line-height: 1.5;
        }}
        .meta {{
            color: #666;
            font-size: 14px;
            margin-bottom: 8px;
        }}
        a {{
            color: #0066cc;
        }}
    </style>
</head>
<body>
    <h1>{html.escape(SITE_TITLE)}</h1>
    <p class="desc">{html.escape(SITE_DESCRIPTION)}</p>
    {content}
</body>
</html>
"""


def make_summary(text: str, max_len: int = 120) -> str:
    text = text.replace("\n", " ").strip()
    return text[:max_len] + ("..." if len(text) > max_len else "")


def extract_title_from_ai_text(ai_text: str, fallback_title: str) -> str:
    lines = [line.strip() for line in ai_text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if line == "タイトル" and i + 1 < len(lines):
            return lines[i + 1]
        if line.startswith("タイトル:"):
            return line.replace("タイトル:", "").strip()
    return fallback_title


existing_articles = load_articles()

feed = feedparser.parse(RSS_URL)
if not feed.entries:
    print("RSSから記事を取得できませんでした。")
    sys.exit(1)

new_count = 0

for i, entry in enumerate(feed.entries[:MAX_ARTICLES], start=1):
    source_url = entry.link.strip()
    source_name = urlparse(source_url).netloc or "unknown"
    rss_title = entry.title.strip()

    print(f"[{i}] {rss_title}")

    if article_exists(existing_articles, source_url):
        print("既存記事のためスキップ")
        continue

    try:
        article = Article(source_url)
        article.download()
        article.parse()

        raw_text = article.text.strip()
        text = raw_text[:800]

        if not text:
            print("本文が空のためスキップ")
            continue
    except Exception as e:
        print(f"本文取得エラー: {e}")
        continue

    category = detect_category(f"{rss_title}\n{text}")

    system_prompt = """
あなたは国際ニュースを日本語で整理して伝える編集者です。
次の公開ルールを必ず守ってください。

【公開ルール】
1. 1記事につき1ソースだけで断定しない
2. 見出しで煽りすぎない
3. 原文の丸写しや近い言い換えを避ける
4. 事実・背景・見通しを分ける
5. 推測は推測と分かる表現にする
6. 軍事・戦争関連でも攻撃をあおる表現は避ける
7. 出典欄と注意欄は出力しない
8. 画像に言及しない
9. 中立的で読みやすい文章にする
10. 不明な情報を補完しすぎない
11. 入力にない具体的な数値・発言・日時を作らない

【出力形式】
タイトル
要点
背景
今後の見通し

【文体】
- 日本語
- 中立的
- 煽らない
- 分かりやすい
- 350〜600文字程度
"""

    user_prompt = f"""
以下のニュース本文をもとに、日本語の記事を書いてください。

条件:
- タイトルは煽らず中立的にする
- 1つのソースしかないので断定しすぎない
- 事実と推測を分ける
- 原文の丸写しや近い言い換えは禁止
- 出典欄や注意欄は書かない
- 画像は使わない前提
- 見出しは必ず「タイトル」「要点」「背景」「今後の見通し」を使う

参考タイトル:
{rss_title}

推定カテゴリ:
{category}

ニュース本文:
{text}
"""

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        ai_text = response.output_text.strip()
        article_title = extract_title_from_ai_text(ai_text, rss_title)
        created_at = now_str()

        filename_base = safe_filename(article_title)
        file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename_base}.html"
        file_path = OUTPUT_DIR / file_name

        sources = [
            {
                "name": source_name,
                "url": source_url,
                "type": "secondary"
            }
        ]

        file_path.write_text(
            make_article_html(
                article_title,
                ai_text,
                sources,
                created_at,
                category
            ),
            encoding="utf-8"
        )

        existing_articles.insert(0, {
            "title": article_title,
            "summary": make_summary(ai_text, 120),
            "created_at": created_at,
            "file_name": file_name,
            "category": category,
            "article_type": "analysis",
            "sources": sources
        })

        new_count += 1
        print(f"保存: {file_name}")

    except Exception as e:
        print(f"AI生成エラー: {e}")

save_articles(existing_articles)
(OUTPUT_DIR / "index.html").write_text(make_index_html(existing_articles), encoding="utf-8")

print(f"新規記事数: {new_count}")
