def make_article_html(page_title, body_text, sources_html, created_at, category):
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
    <div class="badge">{html.escape(category)}</div>
    <div class="meta">作成日時: {html.escape(created_at)}</div>

    <div class="content">{escaped_body}</div>

    <div class="box">
        <strong>参照元</strong><br>
        {sources_html}
    </div>

    <div class="box">
        <strong>注意</strong><br>
        本記事は海外の公開情報をもとにした要約・分析です。<br>
        報道機関の記事本文の転載を目的としたものではありません。<br>
        内容には推測を含む場合があり、今後の追加情報により変わる可能性があります。<br>
        一部ページには広告・アフィリエイトリンクを含むことがあります。
    </div>
</body>
</html>
"""