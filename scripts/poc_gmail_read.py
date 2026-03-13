"""
scripts/poc_gmail_read.py
Phase 0: Gmail 直読実証実験スクリプト

Required packages:
    google-auth
    google-auth-oauthlib
    google-api-python-client
    beautifulsoup4
"""

import base64
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ---- 設定 ---------------------------------------------------------------
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS_PATH = Path("credentials.json")
TOKEN_PATH = Path("token.json")
LOGS_DIR = Path("logs")
DATA_RAW_DIR = Path("data/raw")
MAX_RESULTS = 5
RETRY_MAX = 3
RETRY_INTERVAL = 3  # 秒


# ---- ログ設定 -------------------------------------------------------------
def setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = LOGS_DIR / f"poc-gmail-read-{today}.log"

    logger = logging.getLogger("poc_gmail_read")
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


# ---- 認証 ----------------------------------------------------------------
def load_gmail_service():
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(f"credentials.json が見つかりません: {CREDENTIALS_PATH.resolve()}")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        logger.info("token.json を保存しました")

    service = build("gmail", "v1", credentials=creds)
    logger.info("Gmail API 認証成功")
    return service


# ---- 検索クエリ -----------------------------------------------------------
def build_search_queries() -> list[str]:
    return [
        "from:noreply@x.ai to:garyohosu@gmail.com newer_than:7d",
        "from:noreply@x.ai newer_than:7d",
        "from:noreply@x.ai subject:\"Claude Code\" newer_than:7d",
        "from:noreply@x.ai subject:AI newer_than:7d",
        "from:noreply@x.ai subject:Grok newer_than:7d",
        "from:noreply@x.ai subject:バズ newer_than:7d",
    ]


# ---- Gmail API 呼び出し（リトライ付き）------------------------------------
def _call_with_retry(fn, *args, **kwargs):
    last_exc = None
    for attempt in range(1, RETRY_MAX + 1):
        try:
            return fn(*args, **kwargs)
        except HttpError as e:
            if e.resp.status in (429, 500, 502, 503, 504):
                logger.warning(f"API エラー {e.resp.status}、{RETRY_INTERVAL}秒後にリトライ ({attempt}/{RETRY_MAX})")
                time.sleep(RETRY_INTERVAL)
                last_exc = e
            else:
                raise
    raise last_exc


# ---- メッセージ検索 -------------------------------------------------------
def search_messages(service, query: str, max_results: int) -> list[dict]:
    result = _call_with_retry(
        service.users().messages().list(userId="me", q=query, maxResults=max_results).execute
    )
    messages = result.get("messages", [])
    logger.info(f"クエリ '{query}' → {len(messages)} 件")
    return messages


# ---- メッセージ詳細取得 ---------------------------------------------------
def get_message_detail(service, message_id: str) -> dict:
    return _call_with_retry(
        service.users().messages().get(userId="me", id=message_id, format="full").execute
    )


# ---- ヘッダー抽出 ---------------------------------------------------------
def extract_headers(payload_headers: list[dict]) -> dict:
    target = {"Subject": "subject", "From": "from", "To": "to", "Date": "date"}
    result = {v: "" for v in target.values()}
    for h in payload_headers:
        key = h.get("name", "")
        if key in target:
            result[target[key]] = h.get("value", "")
    return result


# ---- 本文抽出 -------------------------------------------------------------
def _decode_part(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    except Exception:
        return ""


def _find_body_parts(payload: dict, plain_parts: list, html_parts: list) -> None:
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime == "text/plain" and body_data:
        plain_parts.append(_decode_part(body_data))
    elif mime == "text/html" and body_data:
        html_parts.append(_decode_part(body_data))
    else:
        for part in payload.get("parts", []):
            _find_body_parts(part, plain_parts, html_parts)


def extract_body(payload: dict) -> tuple[str, bool]:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    _find_body_parts(payload, plain_parts, html_parts)

    if plain_parts:
        return normalize_text("".join(plain_parts)), bool(html_parts)

    if html_parts:
        raw_html = "".join(html_parts)
        soup = BeautifulSoup(raw_html, "html.parser")
        text = soup.get_text(separator="\n")
        return normalize_text(text), True

    return "", False


# ---- テキスト正規化 -------------------------------------------------------
def normalize_text(text: str) -> str:
    # 連続空白を1つに
    text = re.sub(r"[ \t]+", " ", text)
    # 3行超の連続改行を2行に
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 各行の前後空白除去
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


# ---- URL 抽出 -------------------------------------------------------------
def extract_urls(text: str) -> tuple[list[str], list[str]]:
    raw = re.findall(r"https?://[^\s\)\]\「\」、。,]+", text)
    # 末尾の句読点・括弧を除去
    cleaned = [re.sub(r"[)\]。、,]+$", "", u) for u in raw]
    seen: set[str] = set()
    x_urls: list[str] = []
    other_urls: list[str] = []
    for u in cleaned:
        if u in seen:
            continue
        seen.add(u)
        if re.match(r"https?://(www\.)?x\.com/", u):
            x_urls.append(u)
        else:
            other_urls.append(u)
    return x_urls, other_urls


# ---- JSON 保存 -----------------------------------------------------------
def save_json_sample(data: dict) -> None:
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = DATA_RAW_DIR / f"poc-gmail-sample-{today}.json"
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"JSON サンプル保存: {path}")
    except Exception as e:
        logger.error(f"JSON 保存失敗: {e}")


# ---- 結果判定 -------------------------------------------------------------
def judge_result(messages: list[dict]) -> str:
    if not messages:
        return "FAILURE"

    has_body = any(m.get("plain_text_body") for m in messages)
    has_x_url = any(m.get("x_urls") for m in messages)

    if has_body and has_x_url:
        return "SUCCESS"
    if has_body or any(m.get("subject") for m in messages):
        return "PARTIAL_SUCCESS"
    return "FAILURE"


# ---- メイン --------------------------------------------------------------
def main() -> None:
    logger.info("=== poc_gmail_read.py 開始 ===")
    run_at = datetime.now(timezone.utc).astimezone().isoformat()

    # 認証
    try:
        service = load_gmail_service()
    except Exception as e:
        logger.error(f"Gmail 認証失敗: {e}")
        raise SystemExit(1)

    # 検索
    queries = build_search_queries()
    raw_messages: list[dict] = []
    used_query = ""

    for query in queries:
        logger.info(f"検索クエリ: {query}")
        try:
            hits = search_messages(service, query, MAX_RESULTS)
        except Exception as e:
            logger.error(f"検索エラー: {e}")
            continue
        if hits:
            raw_messages = hits
            used_query = query
            break
        logger.warning(f"0 件。次のクエリへ")

    if not raw_messages:
        logger.error("全クエリで 0 件。FAILURE")
        raise SystemExit(1)

    logger.info(f"取得対象: {len(raw_messages)} 件 (クエリ: {used_query})")

    # 詳細取得・抽出
    extracted: list[dict] = []
    for item in raw_messages:
        mid = item["id"]
        try:
            detail = get_message_detail(service, mid)
        except Exception as e:
            logger.error(f"メッセージ取得失敗 id={mid}: {e}")
            continue

        payload = detail.get("payload", {})
        headers = extract_headers(payload.get("headers", []))
        body_text, has_html = extract_body(payload)
        x_urls, other_urls = extract_urls(body_text)

        msg: dict[str, Any] = {
            "message_id": mid,
            "thread_id": detail.get("threadId", ""),
            "subject": headers["subject"],
            "from": headers["from"],
            "to": headers["to"],
            "date": headers["date"],
            "snippet": detail.get("snippet", ""),
            "plain_text_body": body_text,
            "has_html_body": has_html,
            "label_ids": detail.get("labelIds", []),
            "x_urls": x_urls,
            "other_urls": other_urls,
        }
        extracted.append(msg)

        logger.info(f"  subject : {headers['subject']}")
        logger.info(f"  from    : {headers['from']}")
        logger.info(f"  date    : {headers['date']}")
        logger.info(f"  body    : {len(body_text)} 文字")
        logger.info(f"  x_urls  : {len(x_urls)} 件 {x_urls[:3]}")

    # 構造確認
    for msg in extracted:
        body = msg.get("plain_text_body", "")
        labels_found = [lbl for lbl in ["Title:", "Summary:", "Why it is trending:", "X URL:"] if lbl in body]
        logger.info(f"  構造ラベル確認: {labels_found}")

    # 結果判定
    verdict = judge_result(extracted)
    logger.info(f"=== 判定: {verdict} ===")

    # JSON 保存
    if extracted:
        save_json_sample({
            "run_at": run_at,
            "query": used_query,
            "message_count": len(extracted),
            "messages": extracted,
        })

    if verdict == "FAILURE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
