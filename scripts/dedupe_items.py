"""
scripts/dedupe_items.py
Phase 1-D: 正規化済みアイテムの重複排除

標準ライブラリのみで動作する。外部パッケージ不要。

重複判定の優先順:
  1. x_url 完全一致
  2. related_source_url 完全一致
  3. title 類似度 (文字 bigram Jaccard >= TITLE_SIM_THRESHOLD)

重複時の勝者決定:
  - structured_label > bullet_summary
  - 同種の場合は先着優先（日付が古い方）

マージ:
  - 勝者の null フィールドに敗者の値を補完する
  - likes は最大値を採用

永続化:
  - data/dedupe_index.json に確認済みアイテムを蓄積
  - 再実行時は index と照合して重複検出する
"""

import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# ---- 設定 ---------------------------------------------------------------
DATA_PROCESSED_DIR = Path("data/processed")
DEDUPE_INDEX_PATH = Path("data/dedupe_index.json")
LOGS_DIR = Path("logs")

TITLE_SIM_THRESHOLD = 0.5   # bigram Jaccard 類似度の閾値

JST = timezone(datetime.now(timezone.utc).astimezone().utcoffset())


# ---- ログ設定 -------------------------------------------------------------
def setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = LOGS_DIR / f"dedupe-items-{today}.log"

    logger = logging.getLogger("dedupe_items")
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


# ---- dedupe_index 管理 ---------------------------------------------------
def load_dedupe_index() -> dict:
    if not DEDUPE_INDEX_PATH.exists():
        return {"last_updated": "", "items": []}
    try:
        return json.loads(DEDUPE_INDEX_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"dedupe_index.json 読み込み失敗: {e}")
        raise


def save_dedupe_index(index: dict) -> None:
    index["last_updated"] = datetime.now(JST).isoformat()
    DEDUPE_INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---- タイトル正規化 -------------------------------------------------------
def _normalize_title(title: str | None) -> str:
    if not title:
        return ""
    # Unicode 正規化（全角→半角等）
    text = unicodedata.normalize("NFKC", title)
    # 小文字化
    text = text.lower()
    # 記号・括弧を空白に置換
    text = re.sub(r"[「」『』【】()（）\[\]《》〈〉\.,\-_/\s]+", " ", text)
    return text.strip()


def _bigrams(text: str) -> set[str]:
    return {text[i:i+2] for i in range(len(text) - 1)}


def title_similarity(a: str | None, b: str | None) -> float:
    na = _normalize_title(a)
    nb = _normalize_title(b)
    if not na or not nb:
        return 0.0
    bg_a = _bigrams(na)
    bg_b = _bigrams(nb)
    if not bg_a and not bg_b:
        return 1.0
    union = len(bg_a | bg_b)
    return len(bg_a & bg_b) / union if union > 0 else 0.0


# ---- アイテムの重複チェック -----------------------------------------------
def find_duplicate(
    item: dict,
    index_items: list[dict],
) -> tuple[dict | None, str | None]:
    """
    index_items の中から item の重複を探す。
    戻り値: (一致したindex内アイテム, 判定理由) または (None, None)
    """
    item_x_url   = item.get("x_url")
    item_src_url = item.get("related_source_url")
    item_title   = item.get("title")

    for idx_item in index_items:
        # 1. x_url 完全一致
        if item_x_url and idx_item.get("x_url") == item_x_url:
            return idx_item, "x_url_match"

        # 2. related_source_url 完全一致
        if item_src_url and idx_item.get("related_source_url") == item_src_url:
            return idx_item, "source_url_match"

        # 3. title 類似度
        sim = title_similarity(item_title, idx_item.get("title"))
        if sim >= TITLE_SIM_THRESHOLD:
            return idx_item, f"title_similarity({sim:.2f})"

    return None, None


# ---- 勝者決定 & マージ ---------------------------------------------------
_PARSE_TYPE_RANK = {"structured_label": 1, "bullet_summary": 2, "fallback": 3}


def _parse_rank(entry: dict) -> int:
    return _PARSE_TYPE_RANK.get(entry.get("parse_type", "fallback"), 99)


def merge_items(winner: dict, loser: dict) -> dict:
    """
    loser の非 null フィールドで winner の null を補完する。
    likes は最大値を採用する。
    """
    merged = dict(winner)

    for key in ["summary", "why_trending", "related_source_url",
                "category_raw", "category", "confidence"]:
        if merged.get(key) is None and loser.get(key) is not None:
            merged[key] = loser[key]

    # likes: 最大値採用
    w_likes = winner.get("likes")
    l_likes = loser.get("likes")
    if w_likes is None:
        merged["likes"] = l_likes
    elif l_likes is not None:
        merged["likes"] = max(w_likes, l_likes)

    return merged


def choose_winner(new_item: dict, existing_entry: dict) -> tuple[dict, dict]:
    """
    new_item と existing_entry(index 内)を比べ (winner, loser) を返す。
    parse_type のランクが低いほど優先。同ランクは既存優先（先着）。
    """
    new_rank = _parse_rank(new_item)
    ex_rank  = _parse_rank(existing_entry)

    if new_rank < ex_rank:
        # new が勝者
        winner = merge_items(new_item, existing_entry)
        loser  = existing_entry
    else:
        # existing が勝者（同ランク含む）
        winner = merge_items(existing_entry, new_item)
        loser  = new_item

    return winner, loser


# ---- 正規化済みファイルの読み込み ----------------------------------------
def load_normalized_files() -> list[tuple[Path, dict]]:
    results = []
    for path in sorted(DATA_PROCESSED_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("normalize_status") == "normalized":
                results.append((path, data))
        except Exception as e:
            logger.warning(f"読み込みスキップ: {path.name} — {e}")
    return results


# ---- メイン --------------------------------------------------------------
def main() -> None:
    logger.info("=== dedupe_items.py 開始 ===")

    # dedupe_index 読み込み
    try:
        index = load_dedupe_index()
    except Exception:
        logger.error("dedupe_index.json の読み込みに失敗したため中断します")
        raise SystemExit(1)

    index_items: list[dict] = index.get("items", [])
    logger.info(f"index 既存アイテム数: {len(index_items)}")

    # normalized ファイル読み込み
    file_entries = load_normalized_files()
    logger.info(f"処理対象ファイル: {len(file_entries)} 件")

    if not file_entries:
        logger.info("対象なし。終了します")
        return

    kept_count = 0
    dup_count  = 0

    for path, data in file_entries:
        logger.info(f"--- {path.name}  (parse_type={data['parse_type']})")
        items = data.get("items", [])
        updated_items = []

        for item in items:
            # parse_type をアイテムに付与（勝者判定に使う）
            item_with_meta = dict(item)
            item_with_meta["parse_type"]        = data["parse_type"]
            item_with_meta["source_message_id"] = data["source_message_id"]

            dup_entry, reason = find_duplicate(item_with_meta, index_items)

            if dup_entry is not None:
                # 重複あり → 勝者を決めてマージ
                winner, loser = choose_winner(item_with_meta, dup_entry)

                # index を更新（winner で上書き）
                for i, idx_item in enumerate(index_items):
                    if idx_item is dup_entry:
                        index_items[i] = winner
                        break

                # アイテムに重複判定結果を付与
                item_result = dict(item)
                is_new_winner = (winner.get("source_message_id") ==
                                 item_with_meta.get("source_message_id"))

                if is_new_winner:
                    item_result["dedupe_status"]    = "kept"
                    item_result["duplicate_reason"] = reason
                    item_result["duplicate_of"]     = dup_entry.get("source_message_id")
                    # マージされた値を反映
                    for k in ["summary", "why_trending", "related_source_url",
                               "category_raw", "category", "confidence", "likes"]:
                        item_result[k] = winner.get(k)
                    kept_count += 1
                    logger.info(
                        f"  KEPT (merged winner) title={item.get('title', '')[:40]!r}"
                        f" reason={reason}"
                    )
                else:
                    item_result["dedupe_status"]    = "duplicate"
                    item_result["duplicate_reason"] = reason
                    item_result["duplicate_of"]     = winner.get("source_message_id")
                    dup_count += 1
                    logger.info(
                        f"  DUPLICATE title={item.get('title', '')[:40]!r}"
                        f" reason={reason}"
                        f" → kept={winner.get('source_message_id')}"
                    )

                updated_items.append(item_result)

            else:
                # 新規アイテム → index に追加
                index_items.append(item_with_meta)
                item_result = dict(item)
                item_result["dedupe_status"]    = "kept"
                item_result["duplicate_reason"] = None
                item_result["duplicate_of"]     = None
                updated_items.append(item_result)
                kept_count += 1
                logger.info(f"  NEW title={item.get('title', '')[:40]!r}")

        # processed ファイルを更新
        data["items"] = updated_items
        data["dedupe_status"] = "deduped"
        data["deduped_at"] = datetime.now(JST).isoformat()
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"  更新保存: {path.name}")
        except Exception as e:
            logger.error(f"  保存失敗 {path.name}: {e}")

    # dedupe_index 保存
    index["items"] = index_items
    try:
        save_dedupe_index(index)
        logger.info(f"dedupe_index.json 保存 (合計 {len(index_items)} アイテム)")
    except Exception as e:
        logger.error(f"dedupe_index.json 保存失敗: {e}")

    logger.info(f"=== 完了: kept={kept_count}  duplicate={dup_count} ===")


if __name__ == "__main__":
    main()
