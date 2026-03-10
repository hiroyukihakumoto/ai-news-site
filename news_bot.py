import os
import sys
import json
import html
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

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
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_articles(data):
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def article_exists(existing_articles, source_url):
    return any(item.get("source_url") == source_url for item in existing_articles)


def make_article_html(page_title, body_text, source_name, source_url, created_at):
    escaped_title = html.escape(page_title)
    escaped_body = html.escape(body_text).replace("\n", "<br>\n")

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
            margin-bottom: 28px;
        }}
        .content {{
            font-size: 16px;
        }}
        .box {{
            background: #f7f7f7;
            border: 1px solid #ddd;
            padding: 16px;
            margin-top: 28px;
            border-radius: 8px;
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
    <div class="meta">作成日時: {html.escape(created_at)}</div>

    <div class="content">{escaped_body}</div>

    <div class="box">
        <strong>出典</strong><br>
        媒体名: {html.escape(source_name)}<br>
        原文URL:
        <a href="{html.escape(source_url)}" target="_blank" rel="noopener noreferrer">{html.escape(source_url)}</a>
    </div>

    <div class="box">
        <strong>注意</strong><br>
        本記事は公開情報をもとにした要約・分析です。<br>
        単一ソースに基づくため、今後の追加情報により内容が変わる可能性があります。<br>
        画像は掲載していません。利用する場合は自前またはライセンス確認済み素材のみを使用してください。
    </div>
</body>
</html>
"""


def make_index_html(articles):
    cards = []
    for item in articles:
        cards.append(f"""
        <article class="card">
            <h2><a href="{html.escape(item['file_name'])}">{html.escape(item['title'])}</a></h2>
            <div class="meta">作成日時: {html.escape(item['created_at'])}</div>
            <div class="meta">出典: {html.escape(item['source_name'])}</div>
            <p>{html.escape(item['summary'])}</p>
            <p><a href="{html.escape(item['file_name'])}">記事を読む</a></p>
        </article>
        """)

    articles_html = "\n".join(cards) if cards else "<p>まだ記事がありません。</p>"

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
        .card {{
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            background: #fafafa;
        }}
        .card h2 {{
            margin-top: 0;
            font-size: 24px;
            line-height: 1.5;
        }}
        .meta {{
            color: #666;
            font-size: 14px;
            margin-bottom: 10px;
        }}
        a {{
            color: #0066cc;
        }}
    </style>
</head>
<body>
    <h1>{html.escape(SITE_TITLE)}</h1>
    <p class="desc">{html.escape(SITE_DESCRIPTION)}</p>
    {articles_html}
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
        text = article.text[:3000].strip()

        if not text:
            continue
    except Exception as e:
        print(f"本文取得エラー: {e}")
        continue

    system_prompt = """
あなたは国際ニュースを日本語で整理して伝える編集者です。
次の公開ルールを必ず守ってください。

【公開ルール】
1. 1記事につき1ソースだけで断定しない
2. 見出しで煽りすぎない
3. 原文の丸写しは禁止
4. 事実・背景・見通しを分ける
5. 推測は推測と分かる表現にする
6. 軍事・戦争関連でも攻撃をあおる表現は避ける
7. 出典欄と注意欄は出力しない
8. 画像に言及しない
9. 中立的で読みやすい文章にする

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
- 400〜700文字程度
"""

    user_prompt = f"""
以下のニュース本文をもとに、日本語の記事を書いてください。

条件:
- タイトルは煽らず中立的にする
- 1つのソースしかないので断定しすぎない
- 事実と推測を分ける
- 原文の丸写しは禁止
- 出典欄や注意欄は書かない
- 画像は使わない前提
- 見出しは必ず「タイトル」「要点」「背景」「今後の見通し」を使う

参考タイトル:
{rss_title}

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

        file_path.write_text(
            make_article_html(article_title, ai_text, source_name, source_url, created_at),
            encoding="utf-8"
        )

        existing_articles.insert(0, {
            "title": article_title,
            "summary": make_summary(ai_text, 120),
            "source_name": source_name,
            "source_url": source_url,
            "created_at": created_at,
            "file_name": file_name
        })

        new_count += 1
        print(f"保存: {file_name}")

    except Exception as e:
        print(f"AI生成エラー: {e}")

save_articles(existing_articles)
(OUTPUT_DIR / "index.html").write_text(make_index_html(existing_articles), encoding="utf-8")

print(f"新規記事数: {new_count}")