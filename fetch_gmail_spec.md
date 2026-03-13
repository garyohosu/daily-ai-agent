# scripts/fetch_gmail.py 詳細仕様書
Project: バーチャル専門誌 日刊AIエージェント
Phase: 1-A
Status: Draft for Claude Code

---

## 1. 目的

`scripts/fetch_gmail.py` は、Gmail に届いた Grok タスク通知メールを
運用用途で取得し、`data/raw/` に保存する本番入口モジュールである。

Phase 0 の `poc_gmail_read.py` で「読める」ことを確認済みのため、
本スクリプトはその実証結果を踏まえて設計する。

---

## 2. スコープ

### 2.1 このスクリプトが行うこと
- Gmail API に接続する
- 条件に合う Grok メールを検索する
- `message_id` ベースで未取得メールだけを特定する
- 対象メールの詳細を取得する
- 本文・ヘッダー・URL を抽出する
- `data/raw/YYYY-MM-DD_<message_id>.json` に保存する
- 取得済み `message_id` を管理ファイルに記録する
- 実行ログを出力する

### 2.2 このスクリプトが行わないこと
- メール本文のアイテム単位解析（→ parse_mail.py の責務）
- 記事生成・公開
- Gmail ラベル変更・既読変更・削除
- 重複除去（→ dedupe_items.py の責務）
- AI による要約・分類

---

## 3. 前提条件

- Phase 0 PoC の成功を前提とする
- 対象 Gmail アカウントは `garyohosu@gmail.com`
- 送信元は `noreply@x.ai`
- OAuth2 認証（`credentials.json` / `token.json`）を使用する
- Python 3.10 以上

---

## 4. 認証方針

Phase 0 と同じ OAuth2 方式を継承する。

- `credentials.json` と `token.json` は `.gitignore` 対象
- 例外・ログにアクセストークンを出さない

---

## 5. 未処理判定方針

### 5.1 方式
`message_id` ベースで未取得かどうかを判定する。

既読状態（UNREAD ラベル）は使わない。
理由: Gmail の既読状態は操作により変わりやすく、信頼性が低い。

### 5.2 管理ファイル
取得済み `message_id` を以下のファイルで管理する。

- `data/fetched_ids.json`

形式:
```json
{
  "fetched_ids": [
    "19ce3f518bfa2eea",
    "19cdff95eae4377f"
  ]
}
```

### 5.3 判定ロジック
1. `data/fetched_ids.json` を読み込む（なければ空として扱う）
2. Gmail 検索で hit した `message_id` のうち、未記録のものだけ処理する
3. 保存成功後に `fetched_ids.json` へ追記する

---

## 6. 検索仕様

### 6.1 検索クエリ（Phase 0 と同じ優先順）

1. `from:noreply@x.ai to:garyohosu@gmail.com newer_than:7d`
2. `from:noreply@x.ai newer_than:7d`
3. `from:noreply@x.ai subject:"Claude Code" newer_than:7d`
4. `from:noreply@x.ai subject:AI newer_than:7d`
5. `from:noreply@x.ai subject:Grok newer_than:7d`
6. `from:noreply@x.ai subject:バズ newer_than:7d`

### 6.2 取得件数
- 最大 10 件（PoC の 5 件から拡張）

---

## 7. 出力ファイル仕様

### 7.1 raw データ保存先
```
data/raw/YYYY-MM-DD_<message_id>.json
```

日付は受信日時（`date` ヘッダー）の JST 日付とする。
パースできない場合は実行日付を使う。

### 7.2 JSON スキーマ

```json
{
  "fetched_at": "2026-03-13T12:46:03+09:00",
  "query_used": "from:noreply@x.ai to:garyohosu@gmail.com newer_than:7d",
  "message_id": "19ce3f518bfa2eea",
  "thread_id": "19ce3f518bfa2eea",
  "subject": "Claude Code新機能が急上昇",
  "from": "Grok <noreply@x.ai>",
  "to": "garyohosu@gmail.com",
  "date": "Thu, 12 Mar 2026 21:30:14 +0000 (UTC)",
  "snippet": "...",
  "plain_text_body": "...",
  "has_html_body": true,
  "label_ids": ["IMPORTANT", "CATEGORY_UPDATES", "INBOX"],
  "x_urls": ["https://x.com/..."],
  "other_urls": ["https://claude.com/..."],
  "parse_status": "unparsed"
}
```

### 7.3 `parse_status` 初期値
保存時は必ず `"unparsed"` とする。
`parse_mail.py` が処理後に `"parsed"` / `"parse_failed"` に更新する。

---

## 8. ログ仕様

### 8.1 保存先
```
logs/fetch-gmail-YYYY-MM-DD.log
```

### 8.2 記録内容
- 実行日時
- 使用クエリ
- 検索 hit 件数
- 未取得として処理した件数
- 各メールの subject / from / date
- 保存ファイルパス
- 失敗時のエラー内容
- 最終件数サマリー

---

## 9. エラー処理仕様

### 9.1 認証失敗
- エラーログを出す
- 即時終了（終了コード非 0）

### 9.2 検索 0 件（全クエリ）
- WARNING ログ
- 正常終了（メール未着は異常ではない）
- 終了コード 0

### 9.3 個別メール取得失敗
- ERROR ログ（当該 message_id を記録）
- 他のメールの処理は継続する
- `fetched_ids.json` への追記はしない

### 9.4 JSON 保存失敗
- ERROR ログ
- `fetched_ids.json` への追記はしない（再取得可能にする）

### 9.5 `fetched_ids.json` 読み書き失敗
- ERROR ログ
- 安全のため処理を中断する（誤って重複取得しないように）

---

## 10. 再試行仕様

- Gmail API 呼び出し: 最大 3 回、間隔 3 秒（429 / 5xx のみ）
- 認証エラー: 自動再試行しない

---

## 11. ディレクトリ前提

```
daily-ai-agent/
  credentials.json      # .gitignore 対象
  token.json            # .gitignore 対象
  scripts/
    fetch_gmail.py
  data/
    raw/                # 出力先（.gitignore 対象）
    fetched_ids.json    # 取得済み ID 管理（.gitignore 対象）
  logs/                 # .gitignore 対象
```

`data/fetched_ids.json` は `.gitignore` 対象とする（個人メール ID を含むため）。

---

## 12. 推奨使用ライブラリ

Phase 0 と同じ:
- `google-auth`
- `google-auth-oauthlib`
- `google-api-python-client`
- `beautifulsoup4`
- `pathlib`, `logging`, `json`, `re`, `base64`, `datetime`

---

## 13. 関数設計

Phase 0 の関数を継承・拡張する。

### 13.1 `load_gmail_service()`
Phase 0 と同じ。

### 13.2 `build_search_queries() -> list[str]`
Phase 0 と同じ。

### 13.3 `load_fetched_ids() -> set[str]`
責務:
- `data/fetched_ids.json` を読み込み、取得済み ID の set を返す
- ファイルがなければ空 set を返す

### 13.4 `save_fetched_id(message_id: str) -> None`
責務:
- `data/fetched_ids.json` に message_id を追記する
- アトミックに書き込む（読み込み→更新→書き込みの順）

### 13.5 `search_messages(service, query, max_results) -> list[dict]`
Phase 0 と同じ。

### 13.6 `get_message_detail(service, message_id) -> dict`
Phase 0 と同じ。

### 13.7 `extract_headers(payload_headers) -> dict`
Phase 0 と同じ。

### 13.8 `extract_body(payload) -> tuple[str, bool]`
Phase 0 と同じ。

### 13.9 `extract_urls(text) -> tuple[list[str], list[str]]`
Phase 0 と同じ。

### 13.10 `normalize_text(text) -> str`
Phase 0 と同じ。

### 13.11 `parse_date_to_jst(date_str) -> str`
責務:
- メールの Date ヘッダーを JST の `YYYY-MM-DD` 形式に変換する
- パース失敗時は実行日付を返す

### 13.12 `save_raw_json(data: dict, date_str: str, message_id: str) -> Path`
責務:
- `data/raw/YYYY-MM-DD_<message_id>.json` に保存する
- 保存した Path を返す

### 13.13 `main() -> None`
全体制御。

---

## 14. 実装上の注意

- `poc_gmail_read.py` の関数を直接コピー・改変して使ってよい
- `fetched_ids.json` の読み書きは必ず try/except で囲む
- `parse_status: "unparsed"` は保存時に必ず付ける
- ログや出力に認証情報を含めない
- 1 件取得できなくても、他の件は継続する

---

## 15. 受け入れテスト観点

- 初回実行で未取得メールを全件保存する
- 2 回目実行で重複取得しない（0 件処理）
- `data/raw/YYYY-MM-DD_<message_id>.json` が正しく生成される
- `parse_status` が `"unparsed"` になっている
- `data/fetched_ids.json` に message_id が記録されている
- ログが `logs/fetch-gmail-YYYY-MM-DD.log` に出力される

---

## 16. 将来の接続先

本スクリプトの出力（`data/raw/*.json`）は `scripts/parse_mail.py` が読み込む。

---

## 17. 完了条件

- スクリプトがローカルで起動する
- 未取得メールを `data/raw/` に保存できる
- 再実行時に重複取得しない
- `fetched_ids.json` が更新される
- ログが出力される
