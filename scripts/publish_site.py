"""
scripts/publish_site.py
Phase 1-F: data/index.json 更新 & GitHub Pages 公開

標準ライブラリのみで動作する。外部パッケージ不要。

処理内容:
  1. docs/_posts/*.md の front matter を解析して index.json を再生成
  2. git add / commit / push を実行して GitHub Pages へ反映

使い方:
  python scripts/publish_site.py           # index 更新 + git push
  python scripts/publish_site.py --dry-run # index 更新のみ (git push しない)
"""

import argparse
import json
import logging
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ---- 設定 ---------------------------------------------------------------
POSTS_DIR      = Path("docs/_posts")
INDEX_PATH     = Path("data/index.json")
LOGS_DIR       = Path("logs")
BASEURL        = "https://garyohosu.github.io/daily-ai-agent"

JST = ZoneInfo("Asia/Tokyo")


# ---- ログ設定 -------------------------------------------------------------
def setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(JST).strftime("%Y-%m-%d")
    log_path = LOGS_DIR / f"publish-site-{today}.log"

    logger = logging.getLogger("publish_site")
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


# ---- front matter 解析 ---------------------------------------------------
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_LIST_VAL_RE = re.compile(r"\[([^\]]*)\]")
_QUOTED_RE   = re.compile(r'"([^"]*)"')


def _parse_yaml_value(raw: str):
    """最小限の YAML 値パーサ。リスト・クォート文字列・プレーン文字列を処理。"""
    raw = raw.strip()
    m = _LIST_VAL_RE.match(raw)
    if m:
        items = [s.strip().strip('"').strip("'") for s in m.group(1).split(",") if s.strip()]
        return items
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    return raw


def parse_front_matter(text: str) -> dict:
    m = _FM_RE.match(text)
    if not m:
        return {}
    result: dict = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        result[key.strip()] = _parse_yaml_value(val)
    return result


# ---- 記事 URL 生成 -------------------------------------------------------
def post_url(date_str: str) -> str:
    return f"{BASEURL}/{date_str}-daily-ai-agent/"


# ---- index.json 生成 -----------------------------------------------------
def build_index() -> list[dict]:
    entries: list[dict] = []
    for md_path in sorted(POSTS_DIR.glob("*.md")):
        try:
            text = md_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"読み込み失敗 {md_path}: {e}")
            continue

        fm = parse_front_matter(text)
        date_str = str(fm.get("date", "")).strip()
        if not date_str:
            # ファイル名から推定
            m = re.match(r"(\d{4}-\d{2}-\d{2})", md_path.name)
            date_str = m.group(1) if m else ""

        title = fm.get("title", f"日刊AIエージェント {date_str}")
        tags  = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        entries.append({
            "date":  date_str,
            "title": title,
            "url":   post_url(date_str),
            "tags":  tags,
            "file":  md_path.name,
        })

    # 日付降順でソート
    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries


def save_index(entries: list[dict]) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps({"articles": entries, "updated_at": datetime.now(JST).isoformat()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"index.json 更新: {len(entries)} 件 → {INDEX_PATH}")


# ---- git 操作 ------------------------------------------------------------
def _run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git"] + args
    logger.debug(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip():
        logger.debug(result.stdout.strip())
    if result.stderr.strip():
        logger.debug(result.stderr.strip())
    if check and result.returncode != 0:
        raise RuntimeError(f"git {args[0]} 失敗: {result.stderr.strip()}")
    return result


def git_publish(date_str: str) -> None:
    """変更ファイルを add → commit → push する。"""
    # ステータス確認
    status = _run_git(["status", "--porcelain"]).stdout.strip()
    if not status:
        logger.info("変更なし。git push をスキップします")
        return

    logger.info(f"変更ファイル:\n{status}")

    # add
    _run_git(["add", str(POSTS_DIR), str(INDEX_PATH)])

    # commit
    msg = f"feat: 日刊AIエージェント {date_str} 記事公開"
    _run_git(["commit", "-m", msg])
    logger.info(f"コミット: {msg}")

    # push
    _run_git(["push"])
    logger.info("push 完了")


# ---- メイン --------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="publish_site.py: index 更新 & GitHub Pages 公開")
    parser.add_argument("--dry-run", action="store_true", help="index 更新のみ。git push しない")
    args = parser.parse_args()

    logger.info("=== publish_site.py 開始 ===")

    # index 生成
    entries = build_index()
    if not entries:
        logger.warning("記事が 0 件。index のみ更新します")

    save_index(entries)

    if args.dry_run:
        logger.info("--dry-run のため git push をスキップします")
        logger.info("=== 完了 (dry-run) ===")
        return

    # 最新記事の日付でコミットメッセージを作る
    date_str = entries[0]["date"] if entries else datetime.now(JST).strftime("%Y-%m-%d")

    try:
        git_publish(date_str)
    except RuntimeError as e:
        logger.error(f"git 操作失敗: {e}")
        sys.exit(1)

    logger.info("=== 完了 ===")


if __name__ == "__main__":
    main()
