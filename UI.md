# UI.md - サイト構成・レイアウト設計
Version: 0.1
作成: 2026-03-12

---

## 1. サイト構成図 (Site Map)

サイト全体のページ遷移と階層構造を示します。

```mermaid
graph TD
    Top["トップページ (index.html)<br/>最新記事 + 過去記事リスト"]
    About["このサイトについて (about.md)<br/>目的・編集方針"]
    Categories["カテゴリ一覧 (categories.md)"]
    Article["記事詳細ページ (_posts/YYYY-MM-DD-*.md)"]
    Policy["収集・透明性表示 (about.md内または独立)"]

    Top --> Article
    Top --> About
    Top --> Categories
    Article --> Categories
    Article --> Policy
    Categories --> Article
```

---

## 2. 共通レイアウト (Global Layout)

すべてのページに適用される基本レイアウト構成です。

```mermaid
graph TD
    subgraph Layout ["共通レイアウト構造 (default.html)"]
        H["ヘッダー<br/>(サイト名 / ナビゲーション)"]
        M["メインコンテンツエリア<br/>({{ content }})"]
        F["フッター<br/>(収集方針リンク / 著作権表示 / SNS)"]
        
        H --> M
        M --> F
    end
```

### 構成要素
- **Header**: 
  - サイトロゴ/タイトル（「日刊AIエージェント」）
  - メインナビゲーション（Home, Categories, About）
- **Footer**:
  - 著作権表示 (© 2026 daily-ai-agent)
  - 収集・編集方針へのクイックリンク
  - 免責事項へのリンク
  - SNS（X等）へのリンク：情報共有用（サイト内コメント機能の代替）

---

## 3. ページ別詳細レイアウト

### 3.1 トップページ (Top Page Layout)

最新の記事をメインに据え、過去記事へのアクセスを提供します。**トップページはダイジェスト（要約・リンク）を中心とし、詳細は個別記事ページへ誘導する構成とする。**

```mermaid
graph TD
    subgraph TopPage ["トップページ構成"]
        Hero["最新記事セクション<br/>(最新日のタイトル・日付)"]
        TodaySummary["今日の総括<br/>(全体傾向の要約)"]
        TopicList["トピックダイジェスト (5-10件)<br/>(各記事へのアンカー)"]
        ArchiveList["過去の記事一覧<br/>(逆時系列リスト)"]

        Hero --> TodaySummary
        TodaySummary --> TopicList
        TopicList --> ArchiveList
    end
```

### 3.2 記事ページ (Article Page Layout)

個別のニュース項目を構造化して表示します。**当日の全トピックについて、詳細情報（理由、コメント、リンク等）を網羅する。**

```mermaid
graph TD
    subgraph ArticlePage ["記事詳細ページ構成"]
        Title["記事タイトル<br/>(日刊AIエージェント YYYY-MM-DD)"]
        Lead["リード文 / 今日の総括"]
        
        subgraph Topics ["トピックセクション (繰り返し)"]
            T_Head["トピック見出し (カテゴリ・信頼度)"]
            T_Summary["要約"]
            T_Reason["話題化理由"]
            T_Comment["編集コメント"]
            T_Links["リンク集 (X URL / 補足URL)"]
            
            T_Head --> T_Summary --> T_Reason --> T_Comment --> T_Links
        end
        
        Conclusion["まとめ"]
        SourcePolicy["収集方針・透明性注記"]

        Title --> Lead --> Topics --> Conclusion --> SourcePolicy
    end
```

---

## 4. UIコンポーネント仕様

### 4.1 トピックカード (Topic Card)
各ニュース項目の表示ユニットです。

- **タグ**: カテゴリ (Claude Code, Devin等) を色分け表示
- **信頼度表示**: 星数またはテキスト（例: High, Medium, Low）
- **アクション**: 「元投稿を見る (X)」ボタン

### 4.2 ナビゲーションバー
- モバイル表示時はハンバーガーメニューに折り畳まれるレスポンシブ対応（Phase 2以降）
- アクティブなページを強調表示

---

## 5. デザイン方針 (Visual Style)

- **テーマ**: シンプル、清潔、技術専門誌風
- **フォント**: 日本語はゴシック体、英数字は等幅フォント（Monospace）を適宜使用
- **配色**: 
  - ベース: 白・オフホワイト
  - テキスト: 濃いグレー
  - アクセント: AIを想起させる青や紫、またはコーディングエージェント風の緑
- **レイアウト**: 読みやすさを重視した1カラム中心の構成（最大幅を制限）
