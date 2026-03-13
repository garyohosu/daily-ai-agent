# scripts/poc_gmail_read.py 詳細仕様書
Project: バーチャル専門誌 日刊AIエージェント
Phase: 0
Status: Draft for Claude Code

---

## 1. 目的

`scripts/poc_gmail_read.py` は、Gmail に届いた Grok タスク通知メールを直接読めるかどうかを検証するための実証実験用スクリプトである。

本スクリプトの目的は、記事生成や公開ではなく、以下を確認することに限定する。

- 対象メールを Gmail API で検索できるか
- 件名・送信元・受信日時を取得できるか
- 本文を取得できるか
- HTML メールでも必要情報を取り出せるか
- 本文中から X URL を抽出できるか
- 実験結果をログとして保存できるか

本スクリプトは、将来の `fetch_gmail.py` 実装前に行う Phase 0 の PoC とする。

---

## 2. スコープ

### 2.1 このスクリプトが行うこと
- Gmail API に接続する
- 条件に合う Grok メールを検索する
- 最新数件を取得する
- 必要なメタ情報を抽出する
- 本文をプレーンテキスト化する
- 本文から `https://x.com/...` URL を抽出する
- 結果をコンソールとログファイルへ出力する
- 必要であれば JSON サンプルも保存する

### 2.2 このスクリプトが行わないこと
- 記事生成
- Markdown 生成
- GitHub Pages 公開
- 重複判定
- AI による要約や分類
- Gmail ラベル変更
- メール削除や既読変更

---

## 3. 前提条件

- 対象 Gmail アカウントは `garyohosu@gmail.com`
- Grok からの通知メールがこのアカウントへ届いていること
- 送信元候補は `noreply@x.ai`
- Gmail API が利用可能であること
- OAuth2 クライアント認証を使用すること
- Python 3.10 以上で動作すること

---

## 4. 認証方針

### 4.1 採用方式
OAuth2 を採用する。

### 4.2 不採用方式
Service Account は採用しない。

理由:
- 対象が個人 Gmail アカウントである
- Google Workspace 管理者権限前提ではない
- PoC としては OAuth2 が自然である

### 4.3 資格情報ファイル
ローカルに以下を置く想定とする。

- `credentials.json`
- `token.json`

### 4.4 セキュリティ要件
- `credentials.json` と `token.json` は `.gitignore` に含める
- GitHub へコミットしてはならない
- 例外やログにアクセストークンを出力してはならない

---

## 5. 成功条件

以下をすべて満たした場合、本 PoC は成功とする。

1. 条件に合う対象メールを 1 通以上取得できる
2. 件名を取得できる
3. 送信元を取得できる
4. 受信日時を取得できる
5. 本文主要部を取得できる
6. 本文中から X URL を 1 件以上抽出できる
7. 実行ログを保存できる

---

## 6. 失敗条件

以下のいずれかに該当した場合、本 PoC は失敗とする。

- Gmail API 認証に失敗する
- 対象メールを検索できない
- 本文を取得できない
- HTML から必要情報を抽出できない
- 本文中の URL を安定して抽出できない
- ログ出力に失敗する

---

## 7. 入出力仕様

### 7.1 入力
外部入力は Gmail API 上のメールである。

### 7.2 コマンドライン引数
初期版では引数なしでよい。
必要なら今後以下を追加可能とする。

- `--max-results`
- `--query`
- `--days`
- `--save-json`

### 7.3 出力
以下を出力する。

#### コンソール
- 実行開始
- 検索条件
- 対象メール件数
- 各メールの要約
- URL 抽出結果
- 成功 / 失敗結果

#### ログファイル
- `logs/poc-gmail-read-YYYY-MM-DD.log`

#### JSON サンプル
- `data/raw/poc-gmail-sample-YYYY-MM-DD.json`

---

## 8. 検索仕様

### 8.1 基本検索条件
PoC の初期検索条件は以下とする。

- From: `noreply@x.ai`
- To: `garyohosu@gmail.com`
- 一次検索条件は `from:noreply@x.ai to:garyohosu@gmail.com newer_than:7d`
- 件名条件は必須にせず、必要なら `Claude Code` `AI` `Grok` `バズ` を補助条件に使う
- 直近 7 日以内

### 8.2 Gmail 検索クエリ例
```text
from:noreply@x.ai to:garyohosu@gmail.com newer_than:7d
```

必要に応じて以下の補助条件も候補とする。

```text
from:noreply@x.ai newer_than:7d
from:noreply@x.ai subject:"Claude Code" newer_than:7d
from:noreply@x.ai subject:AI newer_than:7d
from:noreply@x.ai subject:Grok newer_than:7d
from:noreply@x.ai subject:バズ newer_than:7d
```

### 8.3 検索戦略
検索は次の順で行う。

1. 一次検索条件 `from:noreply@x.ai to:garyohosu@gmail.com newer_than:7d` で検索
2. 結果 0 件なら `from:noreply@x.ai newer_than:7d` で再検索
3. それでも 0 件なら件名補助条件（`Claude Code` `AI` `Grok` `バズ`）で再検索
4. それでも 0 件なら失敗

### 8.4 取得件数
- 最大 5 件まで取得する
- 新しいメールを優先する

---

## 9. 取得対象データ

1 通ごとに以下を取得する。

- Gmail message id
- thread id
- subject
- from
- to
- date
- snippet
- plain text body
- html body の有無
- label ids
- 抽出した X URLs
- 抽出したその他 URLs

---

## 10. 本文抽出仕様

### 10.1 優先順位
本文は以下の順で取得する。

1. `text/plain`
2. `text/html` をテキスト変換したもの
3. どちらもなければ空文字

### 10.2 HTML の扱い
HTML 本文しかない場合は、タグ除去してプレーンテキスト化する。

### 10.3 除去対象
可能なら以下を除去する。

- 過剰な空白
- 連続改行
- 装飾用の文言
- フッターの不要部分

### 10.4 残してよいもの
- 件名相当の本文見出し
- 箇条書き
- URL
- AI バズ項目本文

---

## 11. URL 抽出仕様

### 11.1 主対象
本文中の X URL を抽出する。

対象例:
- `https://x.com/...`
- `http://x.com/...`

### 11.2 副対象
必要なら関連 URL も抽出する。

例:
- 企業サイト
- Qiita
- GitHub
- ブログ記事

### 11.3 抽出ルール
- 正規表現で抽出する
- 重複 URL は除去する
- 末尾の句読点やカッコを除去する

### 11.4 出力
- `x_urls`
- `other_urls`

---

## 12. ログ仕様

### 12.1 ログ保存先
- `logs/poc-gmail-read-YYYY-MM-DD.log`

### 12.2 ログ内容
- 実行日時
- Gmail クエリ
- 取得件数
- 各メールの subject / from / date
- 本文抽出成功可否
- X URL 件数
- 失敗時のエラー内容
- 最終判定

### 12.3 ログレベル
- INFO
- WARNING
- ERROR

---

## 13. JSON 保存仕様

### 13.1 保存条件
1 通以上取得できた場合に JSON サンプルを保存する。

### 13.2 保存先
- `data/raw/poc-gmail-sample-YYYY-MM-DD.json`

### 13.3 JSON 形式例
```json
{
  "run_at": "2026-03-12T08:30:00+09:00",
  "query": "from:noreply@x.ai to:garyohosu@gmail.com newer_than:7d",
  "message_count": 1,
  "messages": [
    {
      "message_id": "xxx",
      "thread_id": "yyy",
      "subject": "AIバズまとめ3/10-11更新",
      "from": "Grok <noreply@x.ai>",
      "to": "garyohosu@gmail.com",
      "date": "Wed, 12 Mar 2026 06:35:00 +0900",
      "snippet": "AIバズ＆新機能まとめ...",
      "plain_text_body": "....",
      "has_html_body": true,
      "x_urls": [
        "https://x.com/...."
      ],
      "other_urls": []
    }
  ]
}
```

---

## 14. 実行結果判定仕様

### 14.1 SUCCESS
以下を満たす場合。

- メール 1 通以上取得
- subject / from / date が取得できる
- 本文が空でない
- `x_urls` が 1 件以上ある

### 14.2 PARTIAL_SUCCESS
以下を満たす場合。

- メールは取得できた
- メタ情報も取れた
- ただし本文抽出か URL 抽出に不完全さがある

### 14.3 FAILURE
以下の場合。

- メール取得 0 件
- 認証失敗
- 本文取得不能
- 例外で処理継続不能

---

## 15. エラー処理仕様

### 15.1 認証失敗
- エラーログを出す
- 即時終了
- 終了コードは非 0

### 15.2 検索 0 件
- WARNING ログを出す
- 緩和クエリで再検索
- それでも 0 件なら FAILURE

### 15.3 本文抽出失敗
- HTML / plain の存在状況をログに出す
- 可能なら snippet を代替記録
- PARTIAL_SUCCESS とする

### 15.4 JSON 保存失敗
- ERROR ログを出す
- コンソール出力は継続
- 判定自体は本文取得成否に従う

---

## 16. 再試行仕様

### 16.1 Gmail API 呼び出し
- 最大 3 回
- 間隔 3 秒
- 429 / 5xx 系のみ再試行対象

### 16.2 認証エラー
- 自動再試行しない
- ユーザー操作を促す

---

## 17. ディレクトリ前提

```text
daily-ai-agent/
  credentials.json
  token.json
  scripts/
    poc_gmail_read.py
  logs/
  data/
    raw/
```

---

## 18. 推奨使用ライブラリ

- `google-auth`
- `google-auth-oauthlib`
- `google-api-python-client`
- `beautifulsoup4` または標準ライブラリで HTML 除去
- `pathlib`
- `logging`
- `json`
- `re`
- `base64`
- `datetime`

---

## 19. 関数設計

以下の関数構成を推奨する。

### 19.1 `load_gmail_service()`
責務:
- OAuth2 認証
- Gmail service オブジェクト生成

戻り値:
- Gmail API service

### 19.2 `build_search_queries()`
責務:
- 優先順の Gmail 検索クエリを返す

戻り値:
- `list[str]`

### 19.3 `search_messages(service, query, max_results)`
責務:
- 条件に合う message id 一覧を取る

戻り値:
- `list[dict]`

### 19.4 `get_message_detail(service, message_id)`
責務:
- 対象メールの詳細を取得する

戻り値:
- Gmail メッセージ詳細 dict

### 19.5 `extract_headers(payload_headers)`
責務:
- subject / from / to / date を抽出する

戻り値:
- `dict`

### 19.6 `extract_body(payload)`
責務:
- plain text 優先で本文を抽出する
- 必要なら HTML をテキスト変換する

戻り値:
- `str`

### 19.7 `extract_urls(text)`
責務:
- URL を抽出し、X URL とその他 URL に分ける

戻り値:
- `tuple[list[str], list[str]]`

### 19.8 `normalize_text(text)`
責務:
- 改行や空白を整形する

戻り値:
- `str`

### 19.9 `save_log(...)`
責務:
- ログ出力

### 19.10 `save_json_sample(data)`
責務:
- JSON サンプル保存

### 19.11 `judge_result(messages)`
責務:
- SUCCESS / PARTIAL_SUCCESS / FAILURE を判定する

戻り値:
- `str`

### 19.12 `main()`
責務:
- 全体制御

---

## 20. 実装上の注意

- Gmail API のレスポンスは multipart 構造になり得るため、再帰的に body part を探索すること
- HTML のみのメールに備えること
- ログや標準出力に認証情報を出さないこと
- URL 抽出時に末尾の `)` `]` `。` `,` を誤って含めないこと
- 1 通取得できたら終わりではなく、最大 5 件までは読んで傾向確認できるようにすること
- 実装は PoC 用であり、後の本番実装へ流用しやすい構造にすること

---

## 21. Claude Code への実装指示

以下の方針で実装すること。

1. まずは単一ファイル `scripts/poc_gmail_read.py` として実装する
2. クラス化は不要、関数分割で可読性を確保する
3. 型ヒントを付ける
4. `if __name__ == "__main__": main()` を使う
5. 例外処理を入れる
6. ログファイルと JSON サンプル保存まで実装する
7. 記事生成や公開処理は入れない
8. コード内コメントは必要最低限にする
9. 実行に必要なパッケージ一覧を冒頭コメントまたは README 用に併記する
10. 将来 `scripts/fetch_gmail.py` へ流用しやすい関数名にする

---

## 22. 受け入れテスト観点

最低限、以下を確認できること。

- 初回 OAuth 認証が通る
- 2 回目以降は `token.json` が使われる
- `from:noreply@x.ai` 条件でメールが見つかる
- subject / from / date が表示される
- 本文の先頭数百文字が表示される
- `https://x.com/...` が 1 件以上抽出される
- `logs/` にログが出る
- `data/raw/` に JSON サンプルが出る

---

## 23. 将来の接続先

この PoC 成功後は、以下へ接続する。

- `scripts/fetch_gmail.py`
- `scripts/parse_mail.py`
- `scripts/normalize_items.py`
- `scripts/compose_article.py`
上記はすべて `scripts/` 配下に置く前提とする。

本スクリプトは、その最初の検証用である。

---

## 24. 完了条件

以下を満たしたら `scripts/poc_gmail_read.py` 実装完了とする。

- スクリプトがローカルで起動する
- Gmail 認証が通る
- 対象メールを 1 通以上取得する
- 本文を取り出せる
- X URL を抽出できる
- ログファイルを出力できる
- JSON サンプルを保存できる
- 実装内容が後続の本番コードへ流用できる構造になっている
