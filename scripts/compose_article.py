"""
scripts/compose_article.py
Phase 1-E: deduped データから Jekyll 用 Markdown 記事を生成

標準ライブラリのみで動作する。外部パッケージ不要。

出力先: docs/_posts/YYYY-MM-DD-daily-ai-agent.md
"""

import json
import logging
import re
from collections import Counter
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ---- 設定 ---------------------------------------------------------------
DATA_PROCESSED_DIR = Path("data/processed")
POSTS_DIR          = Path("docs/_posts")
LOGS_DIR           = Path("logs")

JST = ZoneInfo("Asia/Tokyo")
MIN_ITEMS_PER_DAY = 3


# ---- ログ設定 -------------------------------------------------------------
def setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = LOGS_DIR / f"compose-article-{today}.log"

    logger = logging.getLogger("compose_article")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


logger = setup_logging()


# ---- deduped ファイル読み込み & 日付グルーピング -------------------------
def _mail_date_to_jst(date_str: str) -> str:
    try:
        return parsedate_to_datetime(date_str).astimezone(JST).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(JST).strftime("%Y-%m-%d")


def load_deduped_files() -> dict[str, list[dict]]:
    """
    dedupe_status == "deduped" なファイルを読み込み、
    {YYYY-MM-DD: [{item, _source_file, _parse_type}, ...]} で返す。
    """
    by_date: dict[str, list[dict]] = {}

    for path in sorted(DATA_PROCESSED_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"読み込みスキップ: {path.name} — {e}")
            continue

        if data.get("dedupe_status") != "deduped":
            continue

        date_str = _mail_date_to_jst(data.get("date", ""))
        parse_type = data.get("parse_type", "")

        kept_items = [
            item for item in data.get("items", [])
            if item.get("dedupe_status") == "kept"
        ]

        if not kept_items:
            continue

        for item in kept_items:
            item["_parse_type"]  = parse_type
            item["_source_file"] = path.name

        by_date.setdefault(date_str, []).extend(kept_items)

    return by_date


# ---- カテゴリ集計 --------------------------------------------------------
def _collect_categories(items: list[dict]) -> list[str]:
    cats = [item["category"] for item in items if item.get("category")]
    counts = Counter(cats)
    return [cat for cat, _ in counts.most_common()]


# ---- リード文生成 --------------------------------------------------------
def _generate_lead(date_str: str, items: list[dict]) -> str:
    n = len(items)
    cats = _collect_categories(items)

    if cats:
        top = "・".join(cats[:3])
        return (
            f"本日 {date_str} は、{top} を中心に {n} 件のトピックをお届けします。"
            f"Grok が X 上から収集した最新の AI エージェント関連情報です。"
        )
    return (
        f"本日 {date_str} は、AI エージェント関連の注目トピック {n} 件をお届けします。"
        f"Grok が X 上から収集した最新情報です。"
    )


# ---- 今日の総括文生成 ---------------------------------------------------
def _generate_summary(items: list[dict]) -> str:
    cats = _collect_categories(items)
    high_conf = [
        item for item in items
        if item.get("confidence") and int(item["confidence"]) >= 80
    ]
    high_likes = sorted(
        [item for item in items if item.get("likes")],
        key=lambda x: x["likes"],
        reverse=True,
    )

    lines: list[str] = []

    if cats:
        lines.append(f"本日は **{cats[0]}** 関連の話題が目立ちました。")

    if high_conf:
        lines.append(
            f"信頼度 80 以上のトピックが {len(high_conf)} 件確認されています。"
        )

    if high_likes:
        top = high_likes[0]
        title = top.get("title", "")[:30]
        likes = top["likes"]
        lines.append(f"最もバズったのは「{title}」（Likes: {likes:,}）でした。")

    if not lines:
        lines.append("本日もさまざまな AI エージェント関連の動向が確認されました。")

    return " ".join(lines)


# ---- トピックセクション生成 ---------------------------------------------
def _topic_section(item: dict, idx: int) -> str:
    title         = item.get("title") or "（タイトルなし）"
    summary       = item.get("summary")
    why_trending  = item.get("why_trending")
    category      = item.get("category")
    confidence    = item.get("confidence")
    likes         = item.get("likes")
    x_url         = item.get("x_url")
    related_url   = item.get("related_source_url")

    lines: list[str] = []

    # 見出し
    lines.append(f"### {idx}. {title}")
    lines.append("")

    # 要約
    if summary:
        lines.append(summary)
        lines.append("")

    # なぜ話題か
    if why_trending:
        lines.append(f"> **なぜ話題か**: {why_trending}")
        lines.append("")

    # メタ情報（存在するものだけ）
    meta: list[str] = []
    if category:
        meta.append(f"**カテゴリ**: {category}")
    if confidence is not None:
        meta.append(f"**信頼度**: {confidence}/100")
    if likes is not None:
        meta.append(f"**Likes**: {likes:,}")
    if x_url:
        meta.append(f"**X ポスト**: [{_shorten_url(x_url)}]({x_url})")
    if related_url:
        meta.append(f"**関連リンク**: [{_shorten_url(related_url)}]({related_url})")

    if meta:
        for m in meta:
            lines.append(f"- {m}")
        lines.append("")

    # 編集コメント（1行、存在する場合のみ）
    comment = _editorial_comment(item)
    if comment:
        lines.append(f"*編集コメント: {comment}*")
        lines.append("")

    return "\n".join(lines)


def _shorten_url(url: str) -> str:
    """表示用に URL を短縮する（ドメイン + パス先頭）。"""
    m = re.match(r"https?://([^/]+)(.*)", url)
    if not m:
        return url
    domain = m.group(1)
    path   = m.group(2)
    if len(path) > 30:
        path = path[:30] + "…"
    return domain + path


def _category_class(category: str | None) -> str:
    if not category:
        return "category--other"
    mapping = {
        "Claude Code": "category--claude-code",
        "Codex": "category--codex",
        "Enterprise": "category--enterprise",
        "Prompt Engineering": "category--prompt",
        "AI Agents": "category--agents",
        "Research": "category--research",
        "Skills": "category--skills",
    }
    return mapping.get(category, "category--other")


def _confidence_class(confidence: int | None) -> str:
    if confidence is None:
        return "confidence--unknown"
    if confidence >= 90:
        return "confidence--high"
    if confidence >= 80:
        return "confidence--midhigh"
    if confidence >= 70:
        return "confidence--mid"
    return "confidence--low"


def _render_story_card(item: dict, idx: int, variant: str = "brief") -> str:
    title = item.get("title") or "（タイトルなし）"
    summary = item.get("summary") or "要約なし"
    category = item.get("category") or "Other"
    confidence = item.get("confidence")
    x_url = item.get("x_url")
    related_url = item.get("related_source_url")
    comment = _editorial_comment(item)

    conf_text = "未確認" if confidence is None else f"{confidence}/100"
    links = []
    if x_url:
        links.append(f'<a href="{x_url}" target="_blank" rel="noopener">Xポスト</a>')
    if related_url:
        links.append(f'<a href="{related_url}" target="_blank" rel="noopener">関連リンク</a>')
    links_html = " ".join(links)

    return f"""
<article class="story-card {variant}">
  <div class="story-meta">
    <span class="story-rank">#{idx}</span>
    <span class="category-pill {_category_class(category)}">{category}</span>
    <span class="confidence-pill {_confidence_class(confidence)}">信頼度 {conf_text}</span>
  </div>
  <h3>{title}</h3>
  <p class="story-summary">{summary}</p>
  <div class="story-links">{links_html}</div>
  {f'<div class="editor-note"><span>Editor\'s Note</span>{comment}</div>' if comment else ''}
</article>
"""


# ---- 編集コメント生成 ---------------------------------------------------
_CATEGORY_COMMENTS: dict[str, str] = {
    "Claude Code":        "Claude Code ユーザー必見。実装・ワークフロー改善に直結する情報。",
    "Codex":              "Codex 関連。他エージェントとの比較検討に役立つかもしれない。",
    "Devin":              "Devin の最新動向。AI エンジニアリングの前線を追う話題。",
    "AI Agents":          "AI エージェント全般に影響しうるトピック。動向把握に。",
    "Skills":             "Agent Skills 関連。実装者向けの具体的な情報。",
    "Prompt Engineering": "プロンプト設計の改善ヒントになりうる話題。",
    "Local LLM":          "ローカル LLM 活用に関心がある方向けの情報。",
    "VS Code":            "VS Code ユーザーに直接関係する情報。拡張・設定の参考に。",
    "Enterprise":         "企業導入・業務活用を検討中の方に参考になる事例。",
    "Research":           "研究系のトピック。実用化には時間を要する可能性あり。",
    "Workflow":           "開発ワークフロー改善のヒントになりうる話題。",
}


def _editorial_comment(item: dict) -> str | None:
    """category / confidence / likes から短い編集コメントを 1 行生成する。"""
    category   = item.get("category")
    confidence = item.get("confidence")   # int or None
    likes      = item.get("likes")        # int or None

    # 公式発表 × 高バズ
    if confidence is not None and confidence >= 90 and likes is not None and likes >= 5000:
        return "公式発表かつ高エンゲージメント。本日最注目のトピック。"

    # 高信頼度
    if confidence is not None and confidence >= 90:
        return "信頼度が非常に高い。一次ソースとして参照価値が高い。"

    if confidence is not None and confidence >= 70:
        return "比較的信頼度の高い情報。一次ソースの確認も推奨。"

    # 高 Likes
    if likes is not None and likes >= 10000:
        return f"X で爆発的にバズった話題（Likes: {likes:,}）。業界全体に影響しうる動向。"

    if likes is not None and likes >= 1000:
        return f"X で多くの関心を集めた話題（Likes: {likes:,}）。注目度高め。"

    # カテゴリベース
    if category and category in _CATEGORY_COMMENTS:
        return _CATEGORY_COMMENTS[category]

    # 低信頼度の警告
    if confidence is not None and confidence <= 40:
        return "信頼度が低め。未確認情報の可能性あり、一次ソース確認を推奨。"

    return None


# ---- front matter 生成 --------------------------------------------------
def _build_front_matter(date_str: str, items: list[dict]) -> str:
    cats = _collect_categories(items)
    tags_str = ", ".join(f'"{c}"' for c in cats) if cats else '"AI Agents"'
    topic_count = len(items)
    top_categories = cats[:3] if cats else ["AI Agents"]
    high_conf = len([i for i in items if (i.get("confidence") or 0) >= 80])
    hero_summary = f"{'・'.join(top_categories)} を中心に {topic_count} 件のトピック"

    top_categories_yaml = "\n".join([f"  - {c}" for c in top_categories])

    return f"""---
layout: post
title: "日刊AIエージェント {date_str}"
date: {date_str}
categories: [AI, エージェント]
tags: [{tags_str}]
hero_summary: "{hero_summary}"
topic_count: {topic_count}
top_categories:
{top_categories_yaml}
high_confidence_count: {high_conf}
source_name: "Grok / X"
lead_indices: [0, 1, 2]
---"""


# ---- まとめセクション生成 ------------------------------------------------
def _closing_section(items: list[dict]) -> str:
    cats = _collect_categories(items)
    cat_str = "・".join(cats) if cats else "AI エージェント全般"
    return (
        f"本日の日刊AIエージェントは以上です。\n"
        f"引き続き **{cat_str}** の動向に注目していきます。\n"
    )


# ---- 収集方針注記 --------------------------------------------------------
_COLLECTION_NOTE = """---

*本記事は [Grok](https://x.ai) による X 上のバズ投稿収集結果をもとに自動生成しています。*
*元投稿の全文転載は行わず、要約とリンク中心で掲載しています。*
*未確認情報には「未確認」と明記しています。情報の正確性にはご注意ください。*
"""


# ---- 記事全体の組み立て -------------------------------------------------
def _official_signal_score(item: dict) -> int:
    """
    公式/一次情報をざっくり点数化。
    """
    score = 0
    text = " ".join([
        str(item.get("title") or ""),
        str(item.get("summary") or ""),
        str(item.get("why_trending") or ""),
        str(item.get("category") or ""),
    ]).lower()
    x_url = (item.get("x_url") or "").lower()
    related = (item.get("related_source_url") or "").lower()

    # キーワード
    for kw in ["公式", "official", "release", "announc", "blog", "guide", "docs"]:
        if kw in text:
            score += 8

    # 公式ドメイン
    for dom in ["claude.com", "openai.com", "github.com", "google.com", "cloud.google.com", "microsoft.com", "anthropic.com"]:
        if dom in related:
            score += 12

    # 公式アカウントっぽいハンドル
    for handle in ["@claudeai", "@openai", "@github", "@googlecloud", "@microsoft", "@anthropicai"]:
        if handle in x_url:
            score += 10

    return score


def compose_article(date_str: str, items: list[dict]) -> str:
    # 公式優先 + 信頼度 + likes の重み付け
    def rank_score(item: dict) -> float:
        conf = float(item.get("confidence") or 0)
        likes = float(item.get("likes") or 0)
        official = float(_official_signal_score(item))
        # 信頼度を最優先、次に公式性、最後にlikes
        return conf * 2.0 + official * 1.5 + min(likes, 20000) / 500.0

    sorted_items = sorted(items, key=rank_score, reverse=True)
    lead_items = sorted_items[:3]
    other_items = sorted_items[3:]

    front_matter = _build_front_matter(date_str, sorted_items)
    lead = _generate_lead(date_str, sorted_items)
    overview = _generate_summary(sorted_items)
    cats = _collect_categories(sorted_items)
    main_cat = cats[0] if cats else "AI Agents"
    high_conf = len([i for i in sorted_items if (i.get("confidence") or 0) >= 80])

    lead_html = ""
    if lead_items:
        first = _render_story_card(lead_items[0], 1, "lead")
        secondary = "\n".join(_render_story_card(it, i + 2, "secondary") for i, it in enumerate(lead_items[1:]))
        lead_html = f"""
<section class="top-stories">
  <h2>Featured Stories</h2>
  <div class="lead-grid">
    {first}
    <div class="secondary-grid">{secondary}</div>
  </div>
</section>
"""

    briefs_html = ""
    if other_items:
        cards = "\n".join(_render_story_card(it, i + 4, "brief") for i, it in enumerate(other_items))
        briefs_html = f"""
<section class="news-briefs">
  <h2>News Briefs</h2>
  <div class="brief-grid">{cards}</div>
</section>
"""

    article = f"""{front_matter}

<section class="mag-hero">
  <div class="hero-main">
    <p class="hero-kicker">本日のカバーストーリー</p>
    <h1>{main_cat} が主役の {len(sorted_items)} 本</h1>
    <p class="hero-sub">{date_str}号 — {'・'.join(cats[:3]) if cats else 'AI Agents'} を中心に、実装に効く話題を編集</p>
    <p class="hero-lead">{lead}</p>
  </div>
  <div class="hero-stats">
    <div class="stat-card"><span>Topics</span><strong>{len(sorted_items)}</strong></div>
    <div class="stat-card"><span>High Confidence</span><strong>{high_conf}</strong></div>
    <div class="stat-card"><span>Main Category</span><strong>{main_cat}</strong></div>
    <div class="stat-card"><span>Source</span><strong>Grok / X</strong></div>
  </div>
</section>

<section class="editor-overview">
  <h2>本日の総括</h2>
  <p>{overview}</p>
</section>

{lead_html}

{briefs_html}

<section class="closing-notes">
  <h2>本日のまとめ</h2>
  <p>{_closing_section(sorted_items)}</p>
</section>

{_COLLECTION_NOTE}"""

    return article


# ---- ファイル保存 -------------------------------------------------------
def save_article(date_str: str, content: str) -> Path:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    path = POSTS_DIR / f"{date_str}-daily-ai-agent.md"
    path.write_text(content, encoding="utf-8")
    return path


# ---- processed ファイルの compose_status 更新 ---------------------------
def _update_compose_status(date_str: str, file_entries: dict[str, list[dict]]) -> None:
    composed_at = datetime.now(JST).isoformat()
    # 更新対象のファイル名を収集
    target_files: set[str] = set()
    for item in file_entries.get(date_str, []):
        target_files.add(item.get("_source_file", ""))

    for fname in target_files:
        path = DATA_PROCESSED_DIR / fname
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["compose_status"] = "composed"
            data["composed_at"]    = composed_at
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"compose_status 更新失敗 {fname}: {e}")


# ---- メイン --------------------------------------------------------------
def main() -> None:
    logger.info("=== compose_article.py 開始 ===")

    by_date = load_deduped_files()

    if not by_date:
        logger.info("対象なし。終了します")
        return

    logger.info(f"対象日: {sorted(by_date.keys())}")

    had_error = False
    today_jst = datetime.now(JST).strftime("%Y-%m-%d")

    for date_str in sorted(by_date.keys()):
        items = by_date[date_str]
        logger.info(f"--- {date_str}  アイテム数={len(items)}")

        if date_str == today_jst and len(items) < MIN_ITEMS_PER_DAY:
            logger.error(
                f"{date_str}: アイテム数不足 ({len(items)}件)。"
                f"メール本文が途中で切れている可能性あり（Continue reading）。"
            )
            had_error = True
            continue

        article = compose_article(date_str, items)

        try:
            path = save_article(date_str, article)
            logger.info(f"  保存: {path}")
        except Exception as e:
            logger.error(f"  保存失敗 {date_str}: {e}")
            continue

        _update_compose_status(date_str, by_date)

        for i, item in enumerate(items, 1):
            logger.info(
                f"  [{i}] {item.get('title', '')[:40]}"
                f"  cat={item.get('category')}  likes={item.get('likes')}"
            )

    if had_error:
        logger.error("最低件数を満たさない日があるため失敗終了します")
        raise SystemExit(1)

    logger.info("=== 完了 ===")


if __name__ == "__main__":
    main()
