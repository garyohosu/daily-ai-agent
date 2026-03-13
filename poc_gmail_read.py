# poc_gmail_read.py
# Phase 0 PoC: Gmail から Grok タスク通知メールを読み取る実証実験スクリプト
#
# 必要パッケージ:
#   pip install google-auth google-auth-oauthlib google-api-python-client beautifulsoup4

from __future__ import annotations

import base64
import json
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup
import urllib.request

# --- 定数 ---
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS_FILE = Path("credentials.json")
TOKEN_FILE = Path("token.json")
MAX_RESULTS = 5
MAX_BODY_CHARS = 20_000
RETRY_COUNT = 3
RETRY_INTERVAL_SEC = 30
JST = timezone(timedelta(hours=9))

# URL 抽出パターン
_URL_PATTERN = re.compile(
    r'https?://[^\s\)\]\>\"\'<,。、]+',
)


# --- 認証 ---

def load_gmail_service() -> Any:
    """OAuth2 認証を行い Gmail API service オブジェクトを返す。"""
    creds: Credentials | None = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"{CREDENTIALS_FILE} が見つかりません。"
                    " Google Cloud Console からダウンロードしてください。"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    service = build("gmail", "v1", credentials=creds)
    return service


# --- 検索クエリ ---

def build_search_queries() -> list[str]:
    """段階的に緩和する Gmail 検索クエリリストを返す。"""
    return [
        "from:noreply@x.ai to:garyohosu@gmail.com newer_than:7d",
        "from:noreply@x.ai newer_than:7d",
        "from:noreply@x.ai (subject:AI OR subject:Grok OR subject:バズ) newer_than:14d",
    ]


# --- Gmail API 呼び出し (再試行付き) ---

def _call_with_retry(fn, logger: logging.Logger) -> Any:
    """429 / 5xx 系エラーに対してリトライする汎用ラッパー。"""
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            return fn()
        except HttpError as e:
            status = e.resp.status
            if status in (429,) or status >= 500:
                logger.warning(
                    "HTTP %d — %d/%d 回目のリトライ待機 %d 秒",
                    status, attempt, RETRY_COUNT, RETRY_INTERVAL_SEC,
                )
                if attempt < RETRY_COUNT:
                    time.sleep(RETRY_INTERVAL_SEC)
                else:
                    raise
            else:
                raise
    return None  # unreachable


def search_messages(
    service: Any, query: str, max_results: int, logger: logging.Logger
) -> list[dict]:
    """条件に合う message id 一覧を取得する。"""
    def _call():
        return (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )

    result = _call_with_retry(_call, logger)
    return result.get("messages", [])


def get_message_detail(
    service: Any, message_id: str, logger: logging.Logger
) -> dict:
    """対象メールの詳細を取得する。"""
    def _call():
        return (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

    return _call_with_retry(_call, logger)


# --- データ抽出 ---

def extract_headers(payload_headers: list[dict]) -> dict[str, str]:
    """subject / from / to / date を抽出する。"""
    want = {"Subject", "From", "To", "Date"}
    result: dict[str, str] = {}
    for h in payload_headers:
        name = h.get("name", "")
        if name in want:
            result[name.lower()] = h.get("value", "")
    return result


def _decode_part(data: str) -> str:
    """base64url エンコードされた本文をデコードする。"""
    padded = data + "=" * (4 - len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _find_parts(payload: dict, mime_type: str) -> list[str]:
    """再帰的に指定 MIME タイプの本文パーツを探索する。"""
    results: list[str] = []
    if payload.get("mimeType") == mime_type:
        data = payload.get("body", {}).get("data", "")
        if data:
            results.append(_decode_part(data))
    for part in payload.get("parts", []):
        results.extend(_find_parts(part, mime_type))
    return results


def extract_body(payload: dict) -> tuple[str, bool]:
    """plain text 優先で本文を抽出する。HTML のみの場合はテキスト変換する。

    Returns:
        (本文テキスト, has_html_body)
    """
    plain_parts = _find_parts(payload, "text/plain")
    html_parts = _find_parts(payload, "text/html")
    has_html = bool(html_parts)

    if plain_parts:
        body = "\n".join(plain_parts)
    elif html_parts:
        soup = BeautifulSoup("\n".join(html_parts), "html.parser")
        body = soup.get_text(separator="\n")
    else:
        body = ""

    return body, has_html


def normalize_text(text: str) -> str:
    """改行や空白を整形する。"""
    # 連続する空白行を最大 1 行に圧縮
    lines = [line.rstrip() for line in text.splitlines()]
    normalized: list[str] = []
    blank_count = 0
    for line in lines:
        if line == "":
            blank_count += 1
            if blank_count <= 1:
                normalized.append(line)
        else:
            blank_count = 0
            normalized.append(line)
    return "\n".join(normalized).strip()


def extract_urls(text: str) -> tuple[list[str], list[str]]:
    """URL を抽出し x_urls と other_urls に分けて返す。重複は除去する。"""
    raw_urls = _URL_PATTERN.findall(text)
    # 末尾の句読点・括弧を除去
    cleaned: list[str] = []
    for u in raw_urls:
        u = u.rstrip(")].>,。、）")
        cleaned.append(u)

    seen: set[str] = set()
    x_urls: list[str] = []
    other_urls: list[str] = []
    for u in cleaned:
        if u in seen:
            continue
        seen.add(u)
        if re.match(r'https?://(x\.com|t\.co)/', u):
            x_urls.append(u)
        else:
            other_urls.append(u)

    return x_urls, other_urls


def resolve_tco_urls(x_urls: list[str], logger: logging.Logger) -> dict[str, str]:
    """t.co URL をリダイレクト先へ展開する。失敗しても PoC は継続する。"""
    resolved: dict[str, str] = {}
    for url in x_urls:
        if not url.startswith("https://t.co/") and not url.startswith("http://t.co/"):
            continue
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0")
            with urllib.request.urlopen(req, timeout=5) as resp:
                resolved[url] = resp.url
        except Exception as exc:
            logger.warning("t.co 展開失敗 %s: %s", url, exc)
    return resolved


# --- ログ ---

def setup_logger(log_path: Path) -> logging.Logger:
    """ログ設定を初期化し Logger を返す。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("poc_gmail_read")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def log_message_summary(logger: logging.Logger, message: dict) -> None:
    """各メールの subject / from / date / URL 件数をログ出力する。"""
    logger.info(
        "  subject : %s", message.get("subject", "(なし)")
    )
    logger.info(
        "  from    : %s", message.get("from", "(なし)")
    )
    logger.info(
        "  date    : %s", message.get("date", "(なし)")
    )
    logger.info(
        "  x_urls  : %d 件", len(message.get("x_urls", []))
    )
    logger.info(
        "  other_urls: %d 件", len(message.get("other_urls", []))
    )


# --- JSON 保存 ---

def save_json_sample(data: dict, logger: logging.Logger) -> None:
    """JSON サンプルを data/raw/ へ保存する。"""
    today = datetime.now(JST).strftime("%Y-%m-%d")
    out_path = Path("data/raw") / f"poc-gmail-sample-{today}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("JSON サンプル保存: %s", out_path)
    except Exception as exc:
        logger.error("JSON 保存失敗: %s", exc)


# --- 結果判定 ---

def judge_result(messages: list[dict]) -> str:
    """SUCCESS / PARTIAL_SUCCESS / FAILURE を判定する。"""
    if not messages:
        return "FAILURE"

    has_meta = all(
        m.get("subject") and m.get("from") and m.get("date")
        for m in messages
    )
    has_body = all(m.get("plain_text_body") for m in messages)
    has_xurl = any(m.get("x_urls") for m in messages)

    if has_meta and has_body and has_xurl:
        return "SUCCESS"
    if has_meta:
        return "PARTIAL_SUCCESS"
    return "FAILURE"


# --- メイン ---

def main() -> None:
    today = datetime.now(JST).strftime("%Y-%m-%d")
    log_path = Path("logs") / f"poc-gmail-read-{today}.log"
    logger = setup_logger(log_path)

    logger.info("=== poc_gmail_read.py 開始 ===")
    logger.info("実行日時: %s", datetime.now(JST).isoformat())

    # 認証
    try:
        service = load_gmail_service()
        logger.info("Gmail 認証成功")
    except Exception as exc:
        logger.error("Gmail 認証失敗: %s", exc)
        raise SystemExit(1)

    # 検索
    queries = build_search_queries()
    raw_messages: list[dict] = []
    used_query = ""

    for query in queries:
        logger.info("検索クエリ: %s", query)
        try:
            hits = search_messages(service, query, MAX_RESULTS, logger)
        except Exception as exc:
            logger.error("検索エラー: %s", exc)
            hits = []

        if hits:
            logger.info("  %d 件ヒット", len(hits))
            used_query = query
            # 詳細取得
            for item in hits:
                msg_id = item["id"]
                try:
                    detail = get_message_detail(service, msg_id, logger)
                except Exception as exc:
                    logger.warning("メッセージ詳細取得失敗 %s: %s", msg_id, exc)
                    continue

                payload = detail.get("payload", {})
                headers = extract_headers(payload.get("headers", []))
                body_raw, has_html = extract_body(payload)
                body = normalize_text(body_raw)

                # 本文切り詰め
                truncated = len(body) > MAX_BODY_CHARS
                body_stored = body[:MAX_BODY_CHARS] if truncated else body

                x_urls, other_urls = extract_urls(body)
                resolved = resolve_tco_urls(x_urls, logger)

                msg_data = {
                    "message_id": detail.get("id"),
                    "thread_id": detail.get("threadId"),
                    "subject": headers.get("subject", ""),
                    "from": headers.get("from", ""),
                    "to": headers.get("to", ""),
                    "date": headers.get("date", ""),
                    "snippet": detail.get("snippet", ""),
                    "plain_text_body": body_stored,
                    "body_truncated": truncated,
                    "has_html_body": has_html,
                    "x_urls": x_urls,
                    "resolved_urls": resolved,
                    "other_urls": other_urls,
                }
                raw_messages.append(msg_data)

                logger.info("--- メッセージ ---")
                log_message_summary(logger, msg_data)
                if body_stored:
                    logger.info("  本文先頭500文字:\n%s", body_stored[:500])

            break  # ヒットしたのでクエリ緩和不要
        else:
            logger.warning("  0 件 — 次のクエリへ")

    if not raw_messages:
        logger.error("全クエリで対象メールが見つかりませんでした (FAILURE)")
        raise SystemExit(1)

    # 判定
    result = judge_result(raw_messages)
    logger.info("=== 判定結果: %s ===", result)

    # JSON 保存
    output = {
        "run_at": datetime.now(JST).isoformat(),
        "query": used_query,
        "message_count": len(raw_messages),
        "messages": raw_messages,
    }
    save_json_sample(output, logger)

    logger.info("=== poc_gmail_read.py 終了 ===")

    if result == "FAILURE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
