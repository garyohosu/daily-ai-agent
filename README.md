# 日刊AIエージェント

Claude Code・Codex・Devin など開発者向け AI エージェントのトレンドを毎日お届けする専門誌。

**公開サイト**: https://garyohosu.github.io/daily-ai-agent/

---

## 概要

Grok が X 上から収集した AI エージェント関連の話題を、Gmail 経由で受け取り、
自動解析・記事化して GitHub Pages に公開するパイプライン。

```
Grok Task (06:30 JST)
  → Gmail 受信 (07:00〜07:30)
    → fetch_gmail → parse_mail → normalize_items → dedupe_items
      → compose_article → publish_site (git push)
        → GitHub Pages 公開
```

---

## セットアップ

### 依存パッケージのインストール

```bash
pip install beautifulsoup4 google-auth google-auth-oauthlib google-api-python-client
```

### Gmail API 認証

1. Google Cloud Console で Gmail API を有効化
2. OAuth 2.0 クライアント ID を作成し `credentials.json` をリポジトリルートに配置
3. 初回実行時にブラウザで認証 → `token.json` が自動生成される（以降は不要）

---

## 手動実行

```bash
# 全フェーズ実行（fetch → parse → normalize → dedupe → compose → publish）
python scripts/main.py

# Gmail 取得をスキップ（既存の raw データから処理）
python scripts/main.py --skip-fetch

# 記事生成まで行い、公開（git push）しない
python scripts/main.py --skip-publish

# index.json 更新のみ（git push しない）
python scripts/publish_site.py --dry-run
```

---

## OpenClaw からの実行

### Cron ジョブ登録

OpenClaw の Cron 設定に以下を登録する。

| 項目 | 値 |
|------|-----|
| **名前** | `daily-ai-agent daily` |
| **スケジュール** | `30 7 * * *`（毎朝 07:30 JST） |
| **タイムゾーン** | `Asia/Tokyo` |
| **メッセージ** | 下記参照 |

**メッセージ（コピー用）**:
```
作業ディレクトリ /home/garyo/daily-ai-agent で python scripts/main.py を実行してください。失敗時はエラーログ logs/main-YYYY-MM-DD.log を確認して報告してください。
```

### 実行タイミングの根拠

| 時刻 (JST) | イベント |
|------------|---------|
| 06:30 | Grok Task 実行 |
| 07:00〜07:30 | Grok メール Gmail 着信 |
| **07:30** | **OpenClaw Cron 起動（推奨）** |
| 07:30〜07:35 | パイプライン完了・GitHub Pages 更新 |

---

## 実行時間の目安

実機計測（2026-03-13、メール 2 通・アイテム 5 件）:

| フェーズ | 処理時間 |
|----------|---------|
| fetch_gmail（Gmail API 取得） | 約 1〜2 秒（token キャッシュ後） |
| parse_mail | < 0.1 秒 |
| normalize_items | < 0.1 秒 |
| dedupe_items | < 0.1 秒 |
| compose_article | < 0.1 秒 |
| publish_site（git push） | 約 2 秒 |
| **合計** | **通常 5〜10 秒** |

> 初回認証時（`token.json` 未生成）は、ブラウザでの OAuth 承認が必要なため手動実行が必要。

---

## ディレクトリ構成

```
daily-ai-agent/
  README.md
  SPEC.md
  credentials.json      # Gmail API 認証情報（Git 管理外）
  token.json            # OAuth トークン（Git 管理外）
  data/
    raw/                # Gmail から取得した生データ（JSON）
    processed/          # 解析・正規化済みデータ（JSON）
    draft/              # 記事化失敗時の下書き
    index.json          # 記事一覧インデックス
    dedupe_index.json   # 重複除去インデックス
  logs/                 # 実行ログ（日付別）
  scripts/
    main.py             # オーケストレータ（全フェーズを順次実行）
    fetch_gmail.py      # Gmail 取得
    parse_mail.py       # メール解析
    normalize_items.py  # データ正規化
    dedupe_items.py     # 重複除去
    compose_article.py  # 記事生成
    publish_site.py     # index 更新 & git push
  docs/                 # GitHub Pages 公開ルート
    _config.yml
    _layouts/
    _posts/             # 生成された記事 Markdown
    assets/
    index.html
    about.md
    categories.md
```

---

## ログ確認

```bash
# 今日のメインログ
cat logs/main-$(date +%Y-%m-%d).log

# Gmail 取得ログ
cat logs/fetch-gmail-$(date +%Y-%m-%d).log
```

---

## SPEC

詳細な設計仕様は [SPEC.md](SPEC.md) を参照。
