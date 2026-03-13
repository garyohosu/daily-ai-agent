"""
scripts/fetch_gmail.py
Phase 1-A: Gmail 取得本番モジュール

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
from email.utils import parsedate_to_datetime
from pathlib import Path

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
FETCHED_IDS_PATH = Path("data/fetched_ids.json")
MAX_RESULTS = 10
RETRY_MAX = 3
RETRY_INTERVAL = 3  # 秒

JST = timezone(datetime.now(timezone.utc).astimezone().utcoffset())


# ---- ログ設定 -------------------------------------------------------------
def setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = LOGS_DIR / f"fetch-gmail-{today}.log"

    logger = logging.getLogger("fetch_gmail")
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
        'from:noreply@x.ai subject:"Claude Code" newer_than:7d',
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


# ---- 取得済み ID 管理 ----------------------------------------------------
def load_fetched_ids() -> set[str]:
    if not FETCHED_IDS_PATH.exists():
        return set()
    try:
        data = json.loads(FETCHED_IDS_PATH.read_text(encoding="utf-8"))
        return set(data.get("fetched_ids", []))
    except Exception as e:
        logger.error(f"fetched_ids.json 読み込み失敗: {e}")
        raise


def save_fetched_id(message_id: str) -> None:
    try:
        if FETCHED_IDS_PATH.exists():
            data = json.loads(FETCHED_IDS_PATH.read_text(encoding="utf-8"))
        else:
            data = {"fetched_ids": []}

        if message_id not in data["fetched_ids"]:
            data["fetched_ids"].append(message_id)

        FETCHED_IDS_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        logger.error(f"fetched_ids.json 書き込み失敗 id={message_id}: {e}")
        raise


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
        soup = BeautifulSoup("".join(html_parts), "html.parser")
        return normalize_text(soup.get_text(separator="\n")), True

    return "", False


# ---- テキスト正規化 -------------------------------------------------------
def normalize_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


# ---- URL 抽出 -------------------------------------------------------------
def extract_urls(text: str) -> tuple[list[str], list[str]]:
    raw = re.findall(r"https?://[^\s\)\]\「\」、。,]+", text)
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


# ---- 受信日時 → JST 日付文字列 ------------------------------------------
def parse_date_to_jst(date_str: str) -> str:
    try:
        dt = parsedate_to_datetime(date_str).astimezone(JST)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(JST).strftime("%Y-%m-%d")


# ---- raw JSON 保存 -------------------------------------------------------
def save_raw_json(data: dict, date_str: str, message_id: str) -> Path:
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_RAW_DIR / f"{date_str}_{message_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---- メイン --------------------------------------------------------------
def main() -> None:
    logger.info("=== fetch_gmail.py 開始 ===")
    fetched_at = datetime.now(JST).isoformat()

    # 認証
    try:
        service = load_gmail_service()
    except Exception as e:
        logger.error(f"Gmail 認証失敗: {e}")
        raise SystemExit(1)

    # 取得済み ID 読み込み
    try:
        fetched_ids = load_fetched_ids()
    except Exception:
        logger.error("fetched_ids.json の読み込みに失敗したため中断します")
        raise SystemExit(1)

    logger.info(f"取得済み ID: {len(fetched_ids)} 件")

    # 検索
    hit_messages: list[dict] = []
    used_query = ""

    for query in build_search_queries():
        logger.info(f"検索クエリ: {query}")
        try:
            hits = search_messages(service, query, MAX_RESULTS)
        except Exception as e:
            logger.error(f"検索エラー: {e}")
            continue
        if hits:
            hit_messages = hits
            used_query = query
            break
        logger.warning("0 件。次のクエリへ")

    if not hit_messages:
        logger.warning("全クエリで 0 件。メール未着のため正常終了します")
        raise SystemExit(0)

    # 未取得フィルタ
    new_messages = [m for m in hit_messages if m["id"] not in fetched_ids]
    logger.info(f"検索 {len(hit_messages)} 件中、未取得: {len(new_messages)} 件")

    if not new_messages:
        logger.info("新規メールなし。終了します")
        raise SystemExit(0)

    # 詳細取得・保存
    saved = 0
    skipped = 0

    for item in new_messages:
        mid = item["id"]

        try:
            detail = get_message_detail(service, mid)
        except Exception as e:
            logger.error(f"メッセージ取得失敗 id={mid}: {e}")
            skipped += 1
            continue

        payload = detail.get("payload", {})
        headers = extract_headers(payload.get("headers", []))
        body_text, has_html = extract_body(payload)
        x_urls, other_urls = extract_urls(body_text)
        date_jst = parse_date_to_jst(headers["date"])

        raw_data = {
            "fetched_at": fetched_at,
            "query_used": used_query,
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
            "parse_status": "unparsed",
        }

        try:
            path = save_raw_json(raw_data, date_jst, mid)
            logger.info(f"  保存: {path}")
        except Exception as e:
            logger.error(f"JSON 保存失敗 id={mid}: {e}")
            skipped += 1
            continue

        try:
            save_fetched_id(mid)
        except Exception:
            logger.error(f"fetched_ids.json 更新失敗 id={mid} — 次回重複取得の可能性あり")
            skipped += 1
            continue

        logger.info(f"  subject : {headers['subject']}")
        logger.info(f"  from    : {headers['from']}")
        logger.info(f"  date    : {headers['date']}")
        logger.info(f"  body    : {len(body_text)} 文字 / x_urls: {len(x_urls)} 件")
        saved += 1

    logger.info(f"=== 完了: 保存 {saved} 件 / スキップ {skipped} 件 ===")


if __name__ == "__main__":
    main()
