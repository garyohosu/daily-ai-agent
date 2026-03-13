# SPEC.md
# バーチャル専門誌 日刊AIエージェント
Version: 0.2-draft
Status: Draft

---

## 1. 概要

本システムは、Grok のタスク機能を用いて X 上の「ユーザーの興味に強く合致する AI 関連バズ投稿」を定期収集し、
その結果が Gmail に届いたメールを起点として記事化し、
GitHub Pages 上で「バーチャル専門誌 日刊AIエージェント」として公開するものである。

本システムの目的は、一般的な AI ニュースサイトではなく、
以下のような分野に偏った、開発者向け専門誌を自動または半自動で成立させることである。

- Claude Code
- Codex
- Devin
- AI coding agents
- Agent Skills / .NET Skills
- Prompt Engineering
- Local LLM
- VS Code extensions
- Developer automation
- VLA
- Quantum-of-Thought
- 日本語環境での AI コーディング活用
- AI エージェント実務導入事例

---

## 2. システム目的

### 2.1 主目的
- X 上で話題になった AI エージェント系投稿を定期収集する
- ユーザーの趣味に合う話題に絞る
- Gmail に届いた Grok メールを直接読み取る
- メール本文を構造化データへ変換する
- 専門誌風の記事へ仕上げる
- GitHub Pages に日刊記事として公開する

### 2.2 副目的
- ユーザーの趣味に偏った情報収集を自動化する
- 「バーチャル専門誌」という世界観を持たせる
- 後で AI 編集部化できる構成にする
- 将来的にカテゴリ別記事や週刊まとめにも拡張可能にする

---

## 3. システム範囲

### 3.1 本システムに含むもの
- Grok タスクの指示文設計
- Grok タスクの実行タイミング設計
- Gmail 受信メールの取得
- メール本文の解析
- 記事データの生成
- GitHub Pages 用 Markdown / JSON の生成
- 記事一覧更新
- Gmail 直読可否の実証実験

### 3.2 本システムに含まないもの
- X API を直接使ったバズ判定
- 独自クローラによる X 監視
- Grok 側の内部アルゴリズム制御
- X 投稿の全文転載
- 完全自動の再投稿 bot
- X 上での自動返信や自動フォロー等の機能

---

## 4. 想定する完成イメージ

本システムは、毎日定時に以下を行う。

1. Grok が X 上の AI 関連バズ話題を収集する
2. 収集結果が Gmail に届く
3. Gmail から対象メールを取得する
4. メール本文を解析する
5. 構造化データを生成する
6. 記事本文を生成する
7. GitHub Pages 用の Markdown 記事を作る
8. サイトのトップとインデックスを更新する
9. 公開する

---

## 5. コンセプト

### 5.1 メディア名
- 日本語名: バーチャル専門誌 日刊AIエージェント
- リポジトリ名: daily-ai-agent

### 5.2 メディア方針
本メディアは、AI 全般の総合ニュースではなく、
AI コーディングエージェントや開発者向け AI 活用トレンドに特化した専門誌とする。

### 5.3 編集方針
- 元投稿の全文転載はしない
- 短い要約とリンク中心にする
- 必要に応じて編集コメントを付ける
- 一次ソースがある場合は併記する
- うわさ・未確認情報はその旨を明記する
- 単なるリンク集ではなく「日々の観測記録」として仕上げる

---

## 6. 重要設計方針

### 6.1 収集と公開を直結しない
Grok メールをそのまま公開してはならない。
必ず以下を挟む。

- 解析
- 正規化
- 重複除去
- 記事化

### 6.2 Gmail を一次保管庫とする
転送を必須とせず、Gmail を一次データの保管場所とする。
必要に応じて Gmail ラベルで対象メールを管理する。

### 6.3 生データを保存する
受信メール由来の抽出データを raw データとして保存し、
記事生成後の processed データと分離する。

### 6.4 半自動を前提とする
初期段階では、記事生成後に人が最終確認する運用を基本とする。
将来、十分安定した場合に限り全自動公開を検討する。

### 6.5 Gmail 直読の前に実証実験を行う
Gmail から本当に対象メールを取得できること、件名・本文・送信元・受信日時が安定して読めること、
HTML メールでも必要情報を抽出できることを、実装前に必ず実証実験で確認する。
この確認前に Gmail 直読前提で本実装へ進んではならない。

---

## 7. 想定ユーザー

### 7.1 主ユーザー
- 本システムの運営者本人

### 7.2 読者
- Claude Code / Codex / Devin に関心がある人
- 開発者向け AI トレンドを追いたい人
- 日本語で AI エージェント情報を追いたい人
- ローカル LLM や開発自動化に関心がある人
- AI コーディング支援ツールの比較や運用に興味がある人

---

## 8. 情報収集対象

### 8.1 優先対象
- Claude Code
- Codex
- Devin
- AI coding agents
- Agent Skills
- .NET Skills
- Prompt Engineering
- Local LLM
- VS Code extensions
- developer automation
- VLA
- Quantum-of-Thought
- 企業導入事例
- 日本語対応 Tips
- 実務で役立つ運用知見
- 開発フロー変化の実例

### 8.2 優先度が低いもの
- 一般向け AI 雑談
- 画像生成だけの話題
- 極端な宣伝投稿
- 話題性が低い単なる個人メモ
- X リンクのない話題

---

## 9. Grok タスク仕様

### 9.1 役割
Grok タスクは、X 上の AI エージェント関連のバズ投稿を、
ユーザーの趣味に強く寄せて抽出し、Gmail へレポート形式で送る役割を持つ。

### 9.2 出力方針
Grok の出力は、後続のメール解析を容易にするため、できるだけ一定の構造を持つ必要がある。

### 9.3 推奨タスク指示文
以下を初期版の標準指示文とする。

#### Prompt-GROK-DAILY-v1
```text
Find AI-related topics on X that are getting unusually high engagement recently.

Focus strongly on the following topics:
- Claude Code
- Codex
- Devin
- AI coding agents
- Agent Skills / .NET Skills
- prompt engineering
- local LLM
- VS Code extensions
- developer automation
- VLA
- Quantum-of-Thought
- Japanese-language tips for coding agents
- enterprise adoption of coding agents

Prioritize:
- practical tips
- official guidance
- useful threads by developers
- product launches
- enterprise use cases
- side-by-side comparisons
- workflow changes caused by AI agents
- topics especially relevant to Japanese developers

Avoid:
- generic AI hype
- low-signal reposts
- pure memes without practical value
- duplicate items
- items without an original X post URL

For each item, output in this exact structure:

1. Title:
2. Summary:
3. Why it is trending:
4. X URL:
5. Related source URL:
6. Category:
7. Confidence:

Output in Japanese.
Keep each summary concise.
Prefer original posts over reposts.
If something is a rumor or uncertain, say so clearly.
Return 5 to 10 items in Markdown.
```

### 9.4 実行タイミング
Grok タスクの実行時刻は非常に重要である。
時間帯により拾える話題が偏るため、以下を推奨とする。

#### 推奨案A
- 毎朝 06:30 JST 実行
- 07:00〜07:30 の間に Gmail 到着想定
- 朝に記事化しやすい

#### 推奨案B
- 毎日 22:30 JST 実行
- 深夜までの話題を当日分として拾いやすい
- 翌朝に記事化できる

#### 初期推奨
本システム初期値は以下とする。

- 実行時刻: 毎朝 06:30 JST
- 記事日付: 実行日当日
- 記事公開目標: 07:30〜09:00 JST

### 9.5 時間に関する設計上の考慮
- 朝実行は「前日深夜〜当日早朝」の話題を拾いやすい
- 夜実行は「当日中の出来事」を拾いやすい
- 毎日一定時刻にすることで日刊記事との整合が取りやすい
- 将来的に朝版・夜版を分ける拡張も可能

---

## 10. Phase 0: Gmail 直読の実証実験

### 10.1 目的
本システムの前提となる「Gmail から Grok タスク通知メールを直接読めるか」を確認する。

### 10.2 実証内容
以下を確認する。

> **[2026-03-13 実機確認済み]**
> Gmail 受信トレイに `Grok <noreply@x.ai>` から件名「Claude Code新機能が急上昇」のメールが届き、
> 本文が `Title:` / `Summary:` / `Why it is trending:` / `X URL:` のラベル形式で構造化されていること、
> 受信時刻が 06:30 であることを目視で確認した。
> 以下の PoC スクリプトは、この構造を前提に受け入れ条件を設計する。

- 対象メールを検索条件で特定できるか
- 件名を取得できるか
- 送信元を取得できるか
- 受信日時を取得できるか
- 本文テキストを取得できるか
- HTML メールの場合でも必要情報を抽出できるか
- 同一スレッド内で最新メールを正しく取得できるか
- 対象メールに添付や余計な装飾があっても処理継続できるか

### 10.3 実験対象メール条件
例:
- From: `noreply@x.ai`（2026-03-13 実機受信で確認済み。正式採用候補）
- To: `garyohosu@gmail.com`
- 一次検索条件は `from:noreply@x.ai to:garyohosu@gmail.com newer_than:7d` を採用する
- Subject 条件は必須にせず、必要なら `Claude Code` `AI` `Grok` `バズ` を補助条件として使う
- 直近 7 日以内に受信したメール

### 10.4 成功条件
以下をすべて満たした場合、Gmail 直読可能と判定する。

- 目的のメールを少なくとも 1 通以上取得できる
- 件名・送信元・受信日時・本文の主要部を取得できる
- 本文中から少なくとも 1 件以上の X URL を抽出できる
- 同一条件で再実行しても同様に読める

加えて、以下を「構造確認」として追加成功条件とする。
2026-03-13 の実機確認により、Grok 通知メールは構造化フォーマットで届くことが判明したため。

- 本文に `Title:` ラベルが存在する
- 本文に `Summary:` ラベルが存在する
- 本文に `Why it is trending:` ラベルが存在する
- 本文に `X URL:` ラベルが存在する
- `https://x.com/` で始まる URL を抽出できる

「単に読めた」ではなく「構造を維持したまま読めた」まで確認することを PoC の受け入れ条件とする。

### 10.5 失敗条件
以下のいずれかに該当する場合、直読前提実装へ進まない。

- メール自体を検索できない
- 本文が取得できない
- HTML のみで必要情報抽出が困難
- 検索条件が不安定で別メールが大量混入する
- 再実行で結果が著しく揺れる

### 10.6 実験結果の扱い
- 成功時: Phase 1 へ進む
- 失敗時: Gmail フィルタの見直し、転送案、または別の取得手段を再検討する
- 実験ログは保存する

### 10.7 実験ログ保存先
- `logs/poc-gmail-read-YYYY-MM-DD.log`

---

## 11. Gmail 受信仕様

### 11.1 前提
Grok タスクの結果は Gmail に通知メールとして届くものとする。

### 11.2 Gmail 側設定
対象メールには Gmail フィルタで専用ラベルを付けることを推奨する。

例:
- ラベル名: `GROK_DAILY_AI_AGENT`

条件例:
- From: `noreply@x.ai`
- Subject 条件は任意。必要なら `Claude Code` `AI` `Grok` `バズ` を補助条件に使う
- 本文に `Title:` `Summary:` などの構造ラベルを含むことを補助確認に使ってよい

### 11.3 取得対象
システムは以下の条件でメールを取得する。

- ラベルが付いている
- まだ未処理である
- 受信日時が当日または直近24時間以内
- 送信元が想定内である

### 11.4 取得内容
取得する項目:
- message_id
- subject
- from
- date
- plain text body
- html body（必要なら）
- label list

### 11.5 本文優先ルール
- plain text body がある場合はそれを優先する
- なければ html body をテキスト化する
- 引用返信や署名は可能な限り除去する

---

## 12. メール解析仕様

### 12.1 目的
Grok メール本文を、記事生成しやすい構造化データに変換する。

### 12.2 解析対象要素
- タイトル
- 要約
- 話題化理由
- X URL
- 補足 URL
- カテゴリ
- 信頼度

### 12.3 解析戦略
2026-03-13 の実機確認により、Grok 通知メールは以下のラベル形式で構造化されていることを確認済み。
初期版の解析は、このラベル抽出を基本方式として採用する。

抽出対象ラベル:
- `Title:`
- `Summary:`
- `Why it is trending:`
- `X URL:`
- `Related source URL:`（存在する場合）
- `Category:`（存在する場合）
- `Confidence:`（存在する場合）

解析手順:
- 項目番号（`1.` `2.` 等）でニュース単位に分割する
- ラベル名ベースの正規表現で各フィールドを抽出する
- 抽出失敗時は部分データでも保持する

### 12.4 解析失敗時の扱い
- 1件だけ壊れていても全体処理は継続する
- 抽出不可項目は `null` とする
- 本文全体も raw として保持する

---

## 13. データ正規化仕様

### 13.1 目的
メール由来データを後工程で扱いやすい形に統一する。

### 13.2 正規化内容
- URL 前後の不要文字除去
- カテゴリ名の揺れ統一
- 余分な空白除去
- 改行整理
- 信頼度表現統一
- 日付フォーマット統一

### 13.3 カテゴリ標準値
カテゴリは以下に正規化する。

- Claude Code
- Codex
- Devin
- AI Agents
- Skills
- Prompt Engineering
- Local LLM
- VS Code
- Enterprise
- Research
- Workflow
- Other

---

## 14. 重複判定仕様

### 14.1 目的
同じ話題が複数回掲載されることを防ぐ。

### 14.2 判定基準
優先順位順に以下で判定する。

1. X URL が完全一致
2. Related source URL が一致
3. Title 類似度が高い
4. 直近数日内の同一話題判定

### 14.3 重複時の扱い
- 原則として後発を除外
- ただし「続報」と判断できる場合は別掲載可
- 続報判定ルールは将来追加

---

## 15. 記事化仕様

### 15.1 目的
構造化データを「日刊AIエージェント」の記事として仕上げる。

### 15.2 記事単位
- 原則として 1日1記事
- 1記事あたり 1〜10件の話題を掲載（初期版は少件数でも公開停止しない）

### 15.3 記事構成
記事は以下の順で構成する。

1. タイトル
2. リード文
3. 今日の総括
4. 各トピック
5. まとめ
6. 収集方針注記

### 15.4 記事タイトル
標準形式:
- `日刊AIエージェント YYYY-MM-DD`
- `日刊AIエージェント YYYY-MM-DD - 特集語句`

### 15.5 各トピックの表示項目
- 見出し
- 要約
- なぜ話題か
- 編集コメント
- X リンク
- 補足リンク
- カテゴリ
- 信頼度

### 15.6 編集コメント
編集コメントは以下のどちらかとする。

- ルールベースで短文生成
- AI による草稿生成後、人が確認

### 15.7 総括文
総括文は、当日の話題傾向を 1〜2 段落でまとめる。

例:
- 今日は Claude Code の小技と企業導入ニュースが目立った
- Skills 公開と実務ワークフロー論が同時に伸びた
- 日本語利用者向け Tips が強かった

---

## 16. 出力ファイル仕様

### 16.1 raw データ
保存先:
- `data/raw/YYYY-MM-DD.json`

内容:
- Gmail から抽出した元データ
- 抽出結果
- 生本文

### 16.2 processed データ
保存先:
- `data/processed/YYYY-MM-DD.json`

内容:
- 正規化済み
- 重複除去済み
- 記事用に整えたデータ

### 16.3 公開記事
保存先:
- `docs/_posts/YYYY-MM-DD-daily-ai-agent.md`

### 16.4 インデックス
保存先:
- `data/index.json`

内容:
- 過去記事一覧
- タイトル
- 日付
- URL
- タグ

---

## 17. サイト公開仕様

### 17.1 公開方式
- GitHub Pages で公開する
- 初期版は `main` ブランチの `/docs` を公開ソースとする

### 17.2 URL 例
- `https://garyohosu.github.io/daily-ai-agent/`

### 17.3 トップページ表示内容
画面構成および共通レイアウトの詳細は `UI.md` を参照する。
- 最新記事
- 最近の記事一覧
- カテゴリ一覧
- この専門誌について
- 収集・編集方針

### 17.4 記事ページ表示内容
- 記事本文
- カテゴリ表示
- 関連記事リンク
- 元情報の出典方針

---

## 18. 収集方針・透明性表示

サイト上には、以下の説明を掲載する。

- 本サイトは Grok による X 話題収集結果を元に構成している
- 元投稿をそのまま転載せず、要約とリンク中心で掲載している
- 必要に応じて編集コメントを加えている
- 情報の正確性には配慮するが、速報性ゆえ誤差がありうる
- 未確認情報は未確認であると明記する

---

## 19. 運用モード

### 19.1 手動モード
- Gmail でメール確認
- メール本文を入力として記事生成
- 人が確認して公開

### 19.2 半自動モード
- Gmail API で自動取得
- 記事草稿を自動生成
- 人が確認して公開

### 19.3 全自動モード
- Gmail API 取得
- 自動解析
- 自動記事化
- 自動 push
- 自動公開

### 19.4 初期採用モード
初期は半自動モードとする。

理由:
- メール書式変動に弱い
- AI の要約や分類に揺れがある
- 専門誌としての品質確保が必要
- まず Gmail 直読実験の結果を見て実装確度を確認する必要がある

### 19.5 運用モード移行基準

#### 手動 → 半自動
- Phase 0 Gmail 直読 PoC 成功後
- かつ 7 日以上の試験運用で、メール取得・解析・記事草稿生成の成功率が 90% 以上

#### 半自動 → 全自動
- 14 日以上の連続運用で、重大エラー 0 件
- 記事品質レビューによる公開差し止めが 1 件以下

---

## 20. エラー処理

### 20.1 Grok メール未着
- 当日の記事生成をスキップ
- ログに記録
- 必要なら前日記事なしとしてトップ更新

### 20.2 Gmail 取得失敗
- 再試行
- 失敗時は処理停止
- 既存公開物は変更しない

### 20.3 メール解析失敗
- raw 保存は実施
- 抽出可能な範囲で processed 生成
- 記事生成不可なら draft 扱い（保存先: `data/draft/YYYY-MM-DD_<message_id>.json`）
- draft には失敗元データ・失敗理由・途中生成物・タイムスタンプを含める
- `message_id` を使えない場合のみ `data/draft/YYYY-MM-DD_HHMMSS.json` を代替名とする
- 再処理は運営者本人が手動で行う。初期版では自動再処理は行わない

### 20.4 記事生成失敗
- processed まで保存
- 公開処理しない
- エラーをログ化

### 20.5 公開失敗
- 記事ファイルは残す
- インデックス更新をロールバック可能にする

---

## 21. ログ仕様

### 21.1 保存対象
- Grok メール受信確認
- Gmail 取得結果
- 解析結果件数
- 重複除去件数
- 記事生成結果
- 公開結果
- エラー内容
- Gmail 直読実証実験の結果

### 21.2 保存先例
- `logs/YYYY-MM-DD.log`

---

## 22. 非機能要件

### 22.1 可読性
- 記事は人間が読んで理解しやすいこと
- リンク先が明確であること

### 22.2 保守性
- メール解析部分を独立モジュールにする
- カテゴリや重複判定を設定化しやすくする

### 22.3 拡張性
- 将来、週刊版やカテゴリ別ページへ拡張できること
- 編集 AI の導入を妨げないこと

### 22.4 透明性
- 自動収集・編集であることを読者に明示できること

---

## 23. ディレクトリ構成案

```text
daily-ai-agent/
  README.md
  SPEC.md
  data/
    raw/
    processed/
    draft/
    index.json
    dedupe_index.json
  logs/
  scripts/
    main.py               # オーケストレータ（実行順序の唯一の定義元）
    poc_gmail_read.py
    fetch_gmail.py
    parse_mail.py
    normalize_items.py
    dedupe_items.py
    compose_article.py
    publish_site.py
  docs/                   # GitHub Pages 公開ルート（main ブランチ /docs）
    _config.yml           # Jekyll 設定（title / baseurl / url / permalink 等）
    _posts/
    _drafts/
    index.html
    about.md
    categories.md
    assets/
      ogp/
        default.png       # OGP デフォルト画像
```

- GitHub Pages の初期公開方式は `main` ブランチの `/docs` を正式採用とする

---

## 24. 今後の拡張案

- 朝刊 / 夕刊の二部制
- 週刊まとめ自動生成
- Claude Code 専用欄
- Codex / Devin 比較欄
- ローカル LLM 専用欄
- 企業導入ウォッチ欄
- バーチャル編集長コメント
- AI 記者 / AI 校閲 / AI 分類担当の導入

---

## 25. 初期実装優先順位

### Phase 0
- Gmail 直読実証実験
- 対象メール検索条件の確定
- 件名・送信元・日時・本文・URL 抽出確認
- ログ保存

### Phase 1
- Grok タスク運用
- Gmail 受信
- メール本文の手動保存
- Markdown 記事生成

### Phase 2
- Gmail API 自動取得
- raw / processed 保存
- 自動記事草稿生成

### Phase 3
- GitHub Pages 自動公開
- 重複除去高度化
- 総括文自動生成

---

## 26. 結論

本システムは、
Grok による「ユーザーの趣味に偏った AI エージェント系バズ投稿収集」を起点に、
Gmail を一次保管庫として記事化し、
GitHub Pages にて日刊専門誌として公開する。

ただし、成功の前提条件として、まず Gmail から対象メールを安定して読めることを実証しなければならない。
そのため、本システムは Phase 0 として Gmail 直読実証実験を必須とする。

成功の鍵は以下である。

- Grok の指示文を固定し、構造化しやすい出力に寄せること
- Grok の実行時刻を日刊運用に合うよう固定すること
- Gmail 受信から公開までに、解析・正規化・編集を挟むこと
- Gmail 直読が安定することを先に検証すること
- 半自動運用で専門誌としての品質を確保すること

### 将来要件: 広告・デザイン拡張
- Google AdSense は将来導入候補とするが、初期公開の必須要件には含めない
- 広告導入時は、共通レイアウト、広告表示方針、プライバシー告知、必要な説明文を別途定義する
- デザインは初期版ではシンプルな技術ブログ風とし、CDN や CSS フレームワークの採用は後段で決定する
