"""
scripts/normalize_items.py
Phase 1-C: parsed データの共通スキーマ正規化

標準ライブラリのみで動作する。外部パッケージ不要。

正規化内容:
  - URL: 末尾ゴミ除去・形式バリデーション
  - category: キーワードマッピングで標準値へ統一（category_raw を保持）
  - confidence: 文字列 → int (0-100) または null
  - likes: int バリデーション
  - text フィールド: 前後空白除去・連続空白圧縮
"""

import json
import logging
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen, Request

# ---- 設定 ---------------------------------------------------------------
DATA_PROCESSED_DIR = Path("data/processed")
LOGS_DIR = Path("logs")

JST = timezone(datetime.now(timezone.utc).astimezone().utcoffset())

# ---- カテゴリ標準値 (SPEC.md 13.3) --------------------------------------
STANDARD_CATEGORIES = [
    "Claude Code",
    "Codex",
    "Devin",
    "AI Agents",
    "Skills",
    "Prompt Engineering",
    "Local LLM",
    "VS Code",
    "Enterprise",
    "Research",
    "Workflow",
    "Other",
]

# キーワード → 標準カテゴリ（上から順に評価、最初にマッチしたものを採用）
_CATEGORY_RULES: list[tuple[list[str], str]] = [
    (["claude code", "claude_code"],                         "Claude Code"),
    (["codex"],                                               "Codex"),
    (["devin"],                                               "Devin"),
    (["skill", "スキル"],                                     "Skills"),
    (["prompt engineering", "プロンプトエンジニアリング",
      "プロンプト"],                                           "Prompt Engineering"),
    (["local llm", "ローカルllm", "ローカル lm",
      "ローカルモデル", "local model"],                        "Local LLM"),
    (["vs code", "vscode", "vs_code"],                        "VS Code"),
    (["enterprise", "企業", "導入事例", "エンタープライズ"],   "Enterprise"),
    (["research", "研究", "論文", "アカデミック"],             "Research"),
    (["workflow", "ワークフロー", "自動化", "automation"],     "Workflow"),
    (["agent", "エージェント", "coding agent",
      "ai agent"],                                            "AI Agents"),
]


# ---- ログ設定 -------------------------------------------------------------
def setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = LOGS_DIR / f"normalize-items-{today}.log"

    logger = logging.getLogger("normalize_items")
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


# ---- 未正規化ファイル一覧 ------------------------------------------------
def load_unnormalized_files() -> list[Path]:
    files = []
    for path in sorted(DATA_PROCESSED_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("normalize_status") != "normalized":
                files.append(path)
        except Exception as e:
            logger.warning(f"読み込みスキップ: {path.name} — {e}")
    return files


# ---- URL 正規化 ----------------------------------------------------------
_URL_TRAILING_JUNK = re.compile(r"[)\]。、,\s。]+$")

def normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    url = _URL_TRAILING_JUNK.sub("", url)
    if not re.match(r"https?://\S+", url):
        return None
    return url


# ---- カテゴリ正規化 ------------------------------------------------------
def _match_category_rules(text: str) -> str | None:
    """キーワードルールで標準カテゴリを返す。マッチなしなら None。"""
    lower = text.lower()
    for std in STANDARD_CATEGORIES:
        if lower == std.lower():
            return std
    for keywords, std in _CATEGORY_RULES:
        if any(kw in lower for kw in keywords):
            return std
    return None


def normalize_category(
    raw: str | None,
    title: str | None = None,
    summary: str | None = None,
) -> str | None:
    """
    raw カテゴリ文字列を STANDARD_CATEGORIES のいずれかへマッピングする。
    raw がマッチしない場合は title → summary の順でフォールバック推論する。
    すべて null なら null のまま返す。
    """
    if raw is None and title is None and summary is None:
        return None

    for text in [raw, title, summary]:
        if not text:
            continue
        result = _match_category_rules(text)
        if result:
            return result

    # raw に何か値があるが分類不能 → "Other"
    if raw is not None:
        return "Other"

    return None


# ---- confidence 正規化 ---------------------------------------------------
def normalize_confidence(raw: str | int | None) -> int | None:
    """
    文字列 "95" / "95%" / "高" などを 0-100 の int へ変換する。
    変換不可なら null。
    """
    if raw is None:
        return None

    if isinstance(raw, int):
        return raw if 0 <= raw <= 100 else None

    s = str(raw).strip().rstrip("%").strip()

    # 数値文字列
    try:
        val = int(s)
        return val if 0 <= val <= 100 else None
    except ValueError:
        pass

    # 日本語・英語の定性表現 → 数値マッピング
    qualitative = {
        "very high": 95, "high": 80, "medium": 60,
        "low": 40, "very low": 20,
        "非常に高い": 95, "高": 80, "高い": 80,
        "中": 60, "中程度": 60,
        "低い": 40, "低": 40,
    }
    return qualitative.get(s.lower())


# ---- likes 正規化 --------------------------------------------------------
def normalize_likes(raw: int | None) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, int) and raw >= 0:
        return raw
    return None


# ---- テキスト正規化 ------------------------------------------------------
def normalize_text(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text if text else None


def fetch_x_summary_from_oembed(x_url: str | None) -> str | None:
    """X URL から oEmbed を使って本文要約候補を取得する（失敗時は None）。"""
    if not x_url:
        return None
    try:
        endpoint = "https://publish.twitter.com/oembed?omit_script=1&url=" + quote(x_url, safe="")
        req = Request(endpoint, headers={"User-Agent": "daily-ai-agent/1.0"})
        with urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        html = data.get("html", "")
        text = re.sub(r"<[^>]+>", " ", html)
        text = normalize_text(unescape(text))
        if not text:
            return None
        return text[:180]
    except Exception:
        return None


# ---- アイテム1件の正規化 -------------------------------------------------
def normalize_item(item: dict) -> dict:
    category_raw = item.get("category")
    title   = normalize_text(item.get("title"))
    x_url   = normalize_url(item.get("x_url"))
    summary = normalize_text(item.get("summary"))
    if not summary:
        summary = fetch_x_summary_from_oembed(x_url)

    return {
        "title":               title,
        "summary":             summary,
        "why_trending":        normalize_text(item.get("why_trending")),
        "x_url":               x_url,
        "related_source_url":  normalize_url(item.get("related_source_url")),
        "category_raw":        category_raw,
        "category":            normalize_category(category_raw, title, summary),
        "confidence":          normalize_confidence(item.get("confidence")),
        "likes":               normalize_likes(item.get("likes")),
    }


# ---- processed JSON 上書き保存 ------------------------------------------
def save_normalized(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---- メイン --------------------------------------------------------------
def main() -> None:
    logger.info("=== normalize_items.py 開始 ===")
    normalized_at = datetime.now(JST).isoformat()

    targets = load_unnormalized_files()
    logger.info(f"処理対象: {len(targets)} 件")

    if not targets:
        logger.info("未正規化ファイルなし。終了します")
        return

    success = 0
    failed = 0

    for path in targets:
        logger.info(f"--- {path.name}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"読み込み失敗: {e}")
            failed += 1
            continue

        original_items = data.get("items", [])
        normalized_items = [normalize_item(item) for item in original_items]

        data["items"] = normalized_items
        data["item_count"] = len(normalized_items)
        data["normalized_at"] = normalized_at
        data["normalize_status"] = "normalized"

        try:
            save_normalized(path, data)
            logger.info(f"  保存: {path} ({len(normalized_items)} items)")
        except Exception as e:
            logger.error(f"  保存失敗: {e}")
            failed += 1
            continue

        # サマリーログ
        for idx, item in enumerate(normalized_items, 1):
            title = (item.get("title") or "(no title)")[:45]
            cat   = item.get("category") or "-"
            conf  = item.get("confidence")
            likes = item.get("likes")
            x_url = item.get("x_url") or "-"
            logger.info(f"  [{idx}] {title}")
            logger.info(f"       category={cat}  confidence={conf}  likes={likes}")
            logger.info(f"       x_url={x_url}")

        success += 1

    logger.info(f"=== 完了: 成功 {success} 件 / 失敗 {failed} 件 ===")


if __name__ == "__main__":
    main()
