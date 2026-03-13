# scripts/parse_mail.py 詳細仕様書
Project: バーチャル専門誌 日刊AIエージェント
Phase: 1-B
Status: Draft for Claude Code

---

## 1. 目的

`scripts/parse_mail.py` は、`fetch_gmail.py` が保存した raw JSON を読み込み、
メール本文をアイテム単位に解析して `data/processed/` に保存する。

Phase 0 の実機確認で、Grok 通知メールには2種類の本文形式があることが判明した。
本スクリプトはその両方を吸収できる2系統パーサを実装する。

---

## 2. 実機確認済みの本文形式

### 2.1 構造ラベル型（例: 「Claude Code新機能が急上昇」）

アイテムが番号付きで並び、各フィールドがラベルで明示される形式。

```
アイテム 1

Title: Claude Code「Code Review」新機能発表

Summary: PRオープン時にClaudeが...

Why it is trending: Anthropic公式発表＋...

X URL: https://x.com/claudeai/status/...

Related source URL: https://claude.com/blog/code-review

Category: 公式ガイダンス / 製品ローンチ

Confidence: 95
```

### 2.2 箇条書きまとめ型（例: 「AIバズまとめ3/10-11更新」）

ツイート単位で並ぶ自由形式。ラベルなし。

```
Anthropicのオーストラリア・ニュージーランド拡張発表
(Likes: 2365)

AnthropicがシドニーにAIのバズっていること。

リンク: https://x.com/AnthropicAI/status/...
```

---

## 3. スコープ

### 3.1 このスクリプトが行うこと
- `data/raw/` の `parse_status: "unparsed"` なファイルを読み込む
- 本文形式を自動判定する
- 該当パーサでアイテム単位に解析する
- `data/processed/YYYY-MM-DD_<message_id>.json` に保存する
- raw JSON の `parse_status` を `"parsed"` / `"parse_failed"` に更新する
- 実行ログを出力する

### 3.2 このスクリプトが行わないこと
- Gmail API 接続
- 重複除去（→ dedupe_items.py の責務）
- 記事生成・公開
- AI による要約・追加分類

---

## 4. 本文形式の自動判定

以下の順で判定する。

1. 本文に `Title:` と `Summary:` と `X URL:` が両方あれば → **構造ラベル型**
2. 本文に `リンク:` または `(Likes:` があれば → **箇条書きまとめ型**
3. どちらでもなければ → **フォールバック（本文そのままを1アイテムとして保持）**

---

## 5. 構造ラベル型パーサ仕様

### 5.1 アイテム分割
`アイテム N` または先頭の番号（`1.` `2.` 等）でブロックを分割する。

分割候補パターン:
```
アイテム \d+
^\d+\.\s
```

### 5.2 フィールド抽出

各ブロックから以下のラベルで抽出する。

| フィールド名 | ラベル |
|---|---|
| `title` | `Title:` |
| `summary` | `Summary:` |
| `why_trending` | `Why it is trending:` |
| `x_url` | `X URL:` |
| `related_source_url` | `Related source URL:` |
| `category` | `Category:` |
| `confidence` | `Confidence:` |

### 5.3 抽出ルール
- ラベルの後の値を取る（複数行にまたがる場合は次のラベルが来るまで継続）
- 前後の空白・改行を strip する
- 抽出できなかったフィールドは `null`
- `x_url` は URL 形式バリデーションを行う（`https?://` で始まるか）
- `confidence` は文字列のまま保持する（数値変換は後段の責務）

---

## 6. 箇条書きまとめ型パーサ仕様

### 6.1 アイテム分割
連続する見出し行 + Likes 行 + 本文行 + リンク行のブロックで分割する。

分割候補パターン:
- 前後を空行で区切られたブロック単位
- 各ブロックの先頭行をタイトルとして扱う

### 6.2 フィールド抽出

| フィールド名 | 抽出元 |
|---|---|
| `title` | ブロック先頭行 |
| `summary` | Likes 行の次の説明文 |
| `why_trending` | `null`（この形式では取得しない） |
| `x_url` | `リンク:` の後の URL |
| `related_source_url` | `null` |
| `category` | `null` |
| `confidence` | `null` |
| `likes` | `(Likes: NNN)` から抽出（この形式専用フィールド） |

### 6.3 抽出ルール
- `リンク:` の後の URL を x_url とする
- Likes 数は整数で保持する
- タイトルが取れない場合は先頭 30 文字を代替タイトルとする

---

## 7. フォールバック処理

構造判定ができなかった場合:

- アイテム数: 1
- `title`: subject をそのまま使う
- `summary`: 本文先頭 200 文字
- 他フィールド: すべて `null`
- `parse_type`: `"fallback"`

---

## 8. 出力ファイル仕様

### 8.1 保存先
```
data/processed/YYYY-MM-DD_<message_id>.json
```

### 8.2 JSON スキーマ

```json
{
  "source_message_id": "19ce3f518bfa2eea",
  "subject": "Claude Code新機能が急上昇",
  "from": "Grok <noreply@x.ai>",
  "date": "Thu, 12 Mar 2026 21:30:14 +0000 (UTC)",
  "fetched_at": "2026-03-13T12:46:03+09:00",
  "parsed_at": "2026-03-13T12:50:00+09:00",
  "parse_type": "structured_label",
  "item_count": 2,
  "items": [
    {
      "title": "Claude Code「Code Review」新機能発表",
      "summary": "PRオープン時にClaudeが...",
      "why_trending": "Anthropic公式発表＋...",
      "x_url": "https://x.com/claudeai/status/2031088171262554195",
      "related_source_url": "https://claude.com/blog/code-review",
      "category": "公式ガイダンス / 製品ローンチ",
      "confidence": "95",
      "likes": null
    }
  ]
}
```

### 8.3 `parse_type` の値

| 値 | 意味 |
|---|---|
| `"structured_label"` | 構造ラベル型パーサで処理 |
| `"bullet_summary"` | 箇条書きまとめ型パーサで処理 |
| `"fallback"` | フォールバック処理 |

---

## 9. raw JSON の `parse_status` 更新

処理完了後、対応する `data/raw/YYYY-MM-DD_<message_id>.json` の
`parse_status` を更新する。

| 結果 | 更新値 |
|---|---|
| processed 保存成功 | `"parsed"` |
| 解析失敗・保存失敗 | `"parse_failed"` |

---

## 10. ログ仕様

### 10.1 保存先
```
logs/parse-mail-YYYY-MM-DD.log
```

### 10.2 記録内容
- 実行日時
- 処理対象ファイル数
- 各ファイルの subject / parse_type / item_count
- 失敗時のエラー内容
- 最終サマリー（成功N件 / 失敗N件）

---

## 11. エラー処理仕様

### 11.1 raw ファイル読み込み失敗
- ERROR ログ
- 当該ファイルをスキップして次へ継続

### 11.2 本文解析失敗
- WARNING ログ
- フォールバック処理を適用する

### 11.3 processed 保存失敗
- ERROR ログ
- raw の `parse_status` を `"parse_failed"` に更新する

### 11.4 raw `parse_status` 更新失敗
- WARNING ログ（処理継続）

---

## 12. ディレクトリ前提

```
daily-ai-agent/
  scripts/
    parse_mail.py
  data/
    raw/                # 入力元
    processed/          # 出力先
  logs/
```

---

## 13. 推奨使用ライブラリ

- `pathlib`, `logging`, `json`, `re`, `datetime`
- 標準ライブラリのみで実装する（外部ライブラリ不要）

---

## 14. 関数設計

### 14.1 `load_unparsed_files() -> list[Path]`
責務:
- `data/raw/` を走査し、`parse_status: "unparsed"` のファイルを返す

### 14.2 `detect_parse_type(body: str) -> str`
責務:
- 本文を見て `"structured_label"` / `"bullet_summary"` / `"fallback"` を返す

### 14.3 `parse_structured_label(body: str) -> list[dict]`
責務:
- 構造ラベル型パーサ
- アイテムリストを返す

### 14.4 `parse_bullet_summary(body: str) -> list[dict]`
責務:
- 箇条書きまとめ型パーサ
- アイテムリストを返す

### 14.5 `parse_fallback(subject: str, body: str) -> list[dict]`
責務:
- フォールバック処理
- 1アイテムのリストを返す

### 14.6 `save_processed_json(data: dict, date_str: str, message_id: str) -> Path`
責務:
- `data/processed/YYYY-MM-DD_<message_id>.json` に保存する

### 14.7 `update_parse_status(raw_path: Path, status: str) -> None`
責務:
- raw JSON の `parse_status` を更新する

### 14.8 `main() -> None`
全体制御。

---

## 15. 実装上の注意

- アイテム分割は正規表現で行う（日本語混在に注意）
- `null` 許容を徹底する（1フィールド欠損で全体を失敗にしない）
- raw ファイルは書き換え最小限（`parse_status` フィールドのみ更新）
- `parse_type` を必ず記録し、後段でのデバッグを容易にする
- 箇条書き型の `likes` フィールドは `null` 許容

---

## 16. 受け入れテスト観点

- `parse_status: "unparsed"` のファイルだけ処理する
- 構造ラベル型メールで全フィールドが抽出される
- 箇条書きまとめ型メールで title / x_url / likes が抽出される
- 解析失敗時にフォールバック処理が動く
- `data/processed/` に正しく保存される
- raw の `parse_status` が `"parsed"` に更新される
- ログが出力される

---

## 17. 将来の接続先

本スクリプトの出力（`data/processed/*.json`）は
`scripts/normalize_items.py` および `scripts/dedupe_items.py` が読み込む。

---

## 18. 完了条件

- 構造ラベル型メールを正しくアイテム分割・フィールド抽出できる
- 箇条書きまとめ型メールを正しく処理できる
- `data/processed/` に保存できる
- raw の `parse_status` を更新できる
- ログが出力される
