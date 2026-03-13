"""
scripts/parse_mail.py
Phase 1-B: Grok メール本文パーサ

標準ライブラリのみで動作する。外部パッケージ不要。
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

# ---- 設定 ---------------------------------------------------------------
DATA_RAW_DIR = Path("data/raw")
DATA_PROCESSED_DIR = Path("data/processed")
LOGS_DIR = Path("logs")

JST = timezone(datetime.now(timezone.utc).astimezone().utcoffset())


# ---- ログ設定 -------------------------------------------------------------
def setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = LOGS_DIR / f"parse-mail-{today}.log"

    logger = logging.getLogger("parse_mail")
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


# ---- 未処理ファイル一覧 --------------------------------------------------
def load_unparsed_files() -> list[Path]:
    files = []
    for path in sorted(DATA_RAW_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("parse_status") == "unparsed":
                files.append(path)
        except Exception as e:
            logger.warning(f"読み込みスキップ: {path.name} — {e}")
    return files


# ---- 本文形式の自動判定 --------------------------------------------------
def detect_parse_type(body: str) -> str:
    has_structured = bool(
        re.search(r"^Title:", body, re.MULTILINE)
        and re.search(r"^Summary:", body, re.MULTILINE)
        and re.search(r"^X URL:", body, re.MULTILINE)
    )
    if has_structured:
        return "structured_label"

    has_bullet = bool(
        re.search(r"^\(Likes:", body, re.MULTILINE)
        or re.search(r"^リンク:", body, re.MULTILINE)
    )
    if has_bullet:
        return "bullet_summary"

    return "fallback"


# ---- 構造ラベル型パーサ --------------------------------------------------
# 抽出対象ラベルと対応フィールド名
_STRUCTURED_LABELS = [
    ("title",              r"^Title:"),
    ("summary",            r"^Summary:"),
    ("why_trending",       r"^Why it is trending:"),
    ("x_url",              r"^X URL:"),
    ("related_source_url", r"^Related source URL:"),
    ("category",           r"^Category:"),
    ("confidence",         r"^Confidence:"),
]

# ラベル行の先頭にマッチする総合パターン（次ラベルの検出用）
_ANY_LABEL_RE = re.compile(
    r"^(?:Title|Summary|Why it is trending|X URL|Related source URL|Category|Confidence):",
    re.MULTILINE,
)


def _extract_field(block: str, label_re: str) -> str | None:
    """ブロック内からラベル行以降・次ラベル行手前までの値を取得する。"""
    lines = block.splitlines()
    capturing = False
    value_lines: list[str] = []

    for line in lines:
        if re.match(label_re, line):
            capturing = True
            # ラベル自体を除いた同一行の値
            value_part = re.sub(label_re, "", line).strip()
            if value_part:
                value_lines.append(value_part)
            continue

        if capturing:
            # 別のラベルが来たら終了
            if _ANY_LABEL_RE.match(line):
                break
            value_lines.append(line)

    if not capturing:
        return None

    text = "\n".join(value_lines).strip()
    return text if text else None


def _split_structured_blocks(body: str) -> list[str]:
    """「アイテム N」または「N.」でブロック分割する。"""
    parts = re.split(r"(?:^アイテム\s*\d+\s*$|^\d+\.\s)", _strip_footer(body), flags=re.MULTILINE)
    # 先頭のヘッダー部分（アイテム番号より前）は除く
    blocks = [p.strip() for p in parts if p.strip()]
    # Title: を含まないブロック（ヘッダー行等）を除外
    return [b for b in blocks if re.search(r"^Title:", b, re.MULTILINE)]


def parse_structured_label(body: str) -> list[dict]:
    blocks = _split_structured_blocks(body)
    items: list[dict] = []

    for block in blocks:
        item: dict = {}
        for field, label_re in _STRUCTURED_LABELS:
            item[field] = _extract_field(block, label_re)

        # x_url の簡易バリデーション
        if item.get("x_url") and not re.match(r"https?://", item["x_url"]):
            item["x_url"] = None

        item["likes"] = None
        items.append(item)

    return items


# ---- フッター除去 -------------------------------------------------------
_FOOTER_RE = re.compile(
    r"\n*(?:Continue reading|© \d{4} X\.AI LLC|Unsubscribe).*$",
    re.DOTALL,
)

def _strip_footer(text: str) -> str:
    return _FOOTER_RE.sub("", text).strip()


# ---- 箇条書きまとめ型パーサ ----------------------------------------------
def _parse_likes(line: str) -> int | None:
    m = re.search(r"\(Likes:\s*([\d,]+)", line)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def parse_bullet_summary(body: str) -> list[dict]:
    """
    ブロック構造（1アイテム = 連続した3ブロック）:
        [0] <タイトル行>\n(Likes: NNN)
        [1] <説明文>
        [2] リンク: <URL>
    各ブロックは空行（\n\n）で区切られる。
    """
    raw_blocks = [b.strip() for b in re.split(r"\n{2,}", _strip_footer(body))]
    raw_blocks = [b for b in raw_blocks if b]

    items: list[dict] = []
    i = 0

    while i < len(raw_blocks):
        block = raw_blocks[i]
        lines = [l.strip() for l in block.splitlines() if l.strip()]

        # (Likes: を含むブロックをアイテム先頭と判定
        likes_line_idx = next(
            (idx for idx, l in enumerate(lines) if re.match(r"\(Likes:", l)), None
        )
        if likes_line_idx is None:
            i += 1
            continue

        likes = _parse_likes(lines[likes_line_idx])
        title = lines[0] if likes_line_idx > 0 else None

        # 次ブロック: 説明文（リンク行でなければ）
        summary: str | None = None
        offset = 1
        if i + offset < len(raw_blocks):
            next_block = raw_blocks[i + offset]
            if not next_block.startswith("リンク:") and not re.match(r"\(Likes:", next_block):
                summary = next_block
                offset += 1

        # 次ブロック: リンク行
        x_url: str | None = None
        if i + offset < len(raw_blocks):
            link_block = raw_blocks[i + offset]
            if link_block.startswith("リンク:"):
                url_part = re.sub(r"^リンク:\s*", "", link_block).strip()
                if re.match(r"https?://", url_part):
                    x_url = url_part
                offset += 1

        items.append({
            "title": title,
            "summary": summary or None,
            "why_trending": None,
            "x_url": x_url,
            "related_source_url": None,
            "category": None,
            "confidence": None,
            "likes": likes,
        })
        i += offset

    return items


# ---- フォールバック -------------------------------------------------------
def parse_fallback(subject: str, body: str) -> list[dict]:
    return [{
        "title": subject,
        "summary": body[:200].strip() or None,
        "why_trending": None,
        "x_url": None,
        "related_source_url": None,
        "category": None,
        "confidence": None,
        "likes": None,
    }]


# ---- processed JSON 保存 -------------------------------------------------
def save_processed_json(data: dict, date_str: str, message_id: str) -> Path:
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_PROCESSED_DIR / f"{date_str}_{message_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---- raw の parse_status 更新 --------------------------------------------
def update_parse_status(raw_path: Path, status: str) -> None:
    try:
        data = json.loads(raw_path.read_text(encoding="utf-8"))
        data["parse_status"] = status
        raw_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"parse_status 更新失敗 {raw_path.name}: {e}")


# ---- メイン --------------------------------------------------------------
def main() -> None:
    logger.info("=== parse_mail.py 開始 ===")
    parsed_at = datetime.now(JST).isoformat()

    targets = load_unparsed_files()
    logger.info(f"処理対象: {len(targets)} 件")

    if not targets:
        logger.info("未処理ファイルなし。終了します")
        return

    success = 0
    failed = 0

    for raw_path in targets:
        logger.info(f"--- {raw_path.name}")
        try:
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"読み込み失敗: {e}")
            failed += 1
            continue

        body = raw.get("plain_text_body", "")
        subject = raw.get("subject", "")
        message_id = raw.get("message_id", "unknown")
        # ファイル名から日付を取得（YYYY-MM-DD_<id>.json）
        date_str = raw_path.stem.split("_")[0]

        parse_type = detect_parse_type(body)
        logger.info(f"  parse_type: {parse_type}")

        try:
            if parse_type == "structured_label":
                items = parse_structured_label(body)
            elif parse_type == "bullet_summary":
                items = parse_bullet_summary(body)
            else:
                items = parse_fallback(subject, body)
                logger.warning(f"  フォールバック適用: {raw_path.name}")
        except Exception as e:
            logger.warning(f"  解析例外 → フォールバック: {e}")
            items = parse_fallback(subject, body)
            parse_type = "fallback"

        logger.info(f"  アイテム数: {len(items)}")

        processed = {
            "source_message_id": message_id,
            "subject": subject,
            "from": raw.get("from", ""),
            "date": raw.get("date", ""),
            "fetched_at": raw.get("fetched_at", ""),
            "parsed_at": parsed_at,
            "parse_type": parse_type,
            "item_count": len(items),
            "items": items,
        }

        try:
            path = save_processed_json(processed, date_str, message_id)
            logger.info(f"  保存: {path}")
        except Exception as e:
            logger.error(f"  processed 保存失敗: {e}")
            update_parse_status(raw_path, "parse_failed")
            failed += 1
            continue

        update_parse_status(raw_path, "parsed")
        success += 1

        # アイテムサマリーをログに出す
        for idx, item in enumerate(items, 1):
            logger.info(f"  [{idx}] {item.get('title', '(no title)')[:50]}")
            if item.get("x_url"):
                logger.info(f"       x_url: {item['x_url']}")

    logger.info(f"=== 完了: 成功 {success} 件 / 失敗 {failed} 件 ===")


if __name__ == "__main__":
    main()
