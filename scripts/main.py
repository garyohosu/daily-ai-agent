"""
scripts/main.py
オーケストレータ: 全フェーズを順番に実行する唯一の定義元

実行順序:
  1. fetch_gmail     — Gmail から Grok 通知メールを取得 → data/raw/
  2. parse_mail      — raw JSON を解析 → data/processed/
  3. normalize_items — processed を正規化 → (上書き)
  4. dedupe_items    — 重複除去 → data/dedupe_index.json 更新
  5. compose_article — 記事 Markdown 生成 → docs/_posts/
  6. publish_site    — index.json 更新 & git push

使い方:
  python scripts/main.py                  # 全フェーズ実行
  python scripts/main.py --dry-run        # git push を省略
  python scripts/main.py --skip-fetch     # Gmail 取得をスキップ (既存 raw のみで処理)
  python scripts/main.py --skip-publish   # 記事生成まで行い公開しない

各サブスクリプトは SystemExit(0) を「正常終了」、SystemExit(1) を「異常終了」として使う。
異常終了が発生した場合、以降のフェーズは実行しない。
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ---- 設定 ---------------------------------------------------------------
LOGS_DIR = Path("logs")
JST = ZoneInfo("Asia/Tokyo")


# ---- ログ設定 -------------------------------------------------------------
def setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(JST).strftime("%Y-%m-%d")
    log_path = LOGS_DIR / f"main-{today}.log"

    logger = logging.getLogger("main")
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


# ---- フェーズ実行ヘルパー -------------------------------------------------
def run_phase(name: str, fn) -> bool:
    """
    fn() を呼び出す。
    - 正常終了 (return / SystemExit(0)): True を返す
    - 異常終了 (SystemExit(1) / 例外)  : False を返す
    """
    logger.info(f"▶ {name} 開始")
    try:
        fn()
        logger.info(f"✓ {name} 完了")
        return True
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if code == 0:
            logger.info(f"✓ {name} 完了 (新規なし)")
            return True
        logger.error(f"✗ {name} 失敗 (exit {code})")
        return False
    except Exception as e:
        logger.exception(f"✗ {name} 例外: {e}")
        return False


# ---- メイン --------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="日刊AIエージェント オーケストレータ")
    parser.add_argument("--dry-run",      action="store_true", help="git push しない")
    parser.add_argument("--skip-fetch",   action="store_true", help="Gmail 取得をスキップ")
    parser.add_argument("--skip-publish", action="store_true", help="公開フェーズをスキップ")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("=== 日刊AIエージェント パイプライン 開始 ===")
    logger.info(f"    dry_run={args.dry_run}  skip_fetch={args.skip_fetch}  skip_publish={args.skip_publish}")
    logger.info("=" * 60)

    # --- Phase 1: Gmail 取得 ----------------------------------------------
    if not args.skip_fetch:
        import fetch_gmail
        ok = run_phase("fetch_gmail", fetch_gmail.main)
        if not ok:
            logger.error("fetch_gmail 失敗。以降のフェーズをスキップします")
            sys.exit(1)
    else:
        logger.info("-- fetch_gmail スキップ (--skip-fetch)")

    # --- Phase 2: メール解析 -----------------------------------------------
    import parse_mail
    ok = run_phase("parse_mail", parse_mail.main)
    if not ok:
        logger.error("parse_mail 失敗。以降のフェーズをスキップします")
        sys.exit(1)

    # --- Phase 3: 正規化 ---------------------------------------------------
    import normalize_items
    ok = run_phase("normalize_items", normalize_items.main)
    if not ok:
        logger.error("normalize_items 失敗。以降のフェーズをスキップします")
        sys.exit(1)

    # --- Phase 4: 重複除去 -------------------------------------------------
    import dedupe_items
    ok = run_phase("dedupe_items", dedupe_items.main)
    if not ok:
        logger.error("dedupe_items 失敗。以降のフェーズをスキップします")
        sys.exit(1)

    # --- Phase 5: 記事生成 -------------------------------------------------
    import compose_article
    ok = run_phase("compose_article", compose_article.main)
    if not ok:
        logger.error("compose_article 失敗。以降のフェーズをスキップします")
        sys.exit(1)

    # --- Phase 6: 公開 -----------------------------------------------------
    if not args.skip_publish:
        import publish_site

        if args.dry_run:
            sys.argv = [sys.argv[0], "--dry-run"]
        else:
            sys.argv = [sys.argv[0]]

        ok = run_phase("publish_site", publish_site.main)
        if not ok:
            logger.error("publish_site 失敗")
            sys.exit(1)
    else:
        logger.info("-- publish_site スキップ (--skip-publish)")

    logger.info("=" * 60)
    logger.info("=== パイプライン 完了 ===")
    logger.info("=" * 60)


if __name__ == "__main__":
    # scripts/ ディレクトリを sys.path に追加して各モジュールを import できるようにする
    import os
    scripts_dir = Path(__file__).parent
    repo_root   = scripts_dir.parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    # 作業ディレクトリをリポジトリルートに固定する
    os.chdir(repo_root)
    main()
