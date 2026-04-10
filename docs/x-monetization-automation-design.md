# X（Twitter）収益化自動化システム 設計書

> **Branch**: `claude/x-monetization-automation-lBcN4`
> **Status**: Design Draft v1
> **Scope**: API未所持を前提としたスクレイピングベース設計

---

## 0. 目的とゴール

X の収益化条件（Premium 登録 + 認証済みフォロワー 500 人 + 直近3ヶ月のインプレッション 500万 等）を、
**凍結・シャドウバン・収益化停止のリスクを最小化しながら** 半自動で達成するためのシステムを設計する。

参考資料（添付 LINE 画像）から抽出した核となる戦略：

1. **トレンド便乗投稿**：当日のトレンドワード/ニュースに乗ってインプを伸ばす
2. **ブルバ相互フォロー活用**：Premium 登録済みアカウント（ブルバ垢）を能動的にフォロー
3. **呼びかけ投稿は避ける**：`#ブルバ相互` 等のハッシュタグ投稿は engagement manipulation と判定されるリスクがあるため **フォローする側に回る**
4. **スピード重視**：規制が厳しくなる前に早期実施

---

## 1. ⚠️ リスクと ToS 上の注意

| リスク | 内容 | 緩和策 |
|---|---|---|
| ToS 違反 | X 開発者契約はスクレイピング・自動化を明示禁止 | 自己アカウントのみ対象・低レートで運用・ヒューマンライク挙動 |
| アカウント凍結 | Bot 判定・異常レート・フィンガープリント検知 | Playwright + Stealth、住宅用プロキシ固定、段階的ウォームアップ |
| 収益化停止 | Engagement manipulation 認定 | 呼びかけハッシュタグ投稿 NG、フォロー比率管理、コンテンツ品質担保 |
| シャドウバン | 過剰投稿・低品質・スパム検知 | インプ監視で早期検知 → 自動停止 |
| 法的リスク | 不正アクセス禁止法・著作権 | 公開情報のみ、スクレイプ対象を最小化、再配布しない |

**運用方針**：本システムは「人間のオペレーションを補助・スケジューリングする」位置付けとし、
完全無人運転ではなく **Human-in-the-loop（承認キュー）** を中核に置く。

---

## 2. 全体アーキテクチャ

```
                    ┌────────────────────────────┐
                    │  Control Panel (FastAPI)   │
                    │  - 承認キュー              │
                    │  - 健康状態ダッシュボード  │
                    │  - Kill Switch             │
                    └───────────┬────────────────┘
                                │
                    ┌───────────▼────────────────┐
                    │   Orchestrator / Scheduler │
                    │   - Circadian schedule     │
                    │   - Rate limiter (Redis)   │
                    │   - Jittered job dispatch  │
                    └───────────┬────────────────┘
                                │
     ┌───────────┬──────────────┼──────────────┬──────────────┐
     ▼           ▼              ▼              ▼              ▼
┌─────────┐ ┌─────────┐   ┌─────────┐    ┌─────────┐    ┌──────────┐
│ Trend   │ │ Content │   │ Posting │    │ Follow  │    │ Analytics│
│ Scout   │ │ Gen(LLM)│   │ Bot     │    │ Manager │    │ & Safety │
└────┬────┘ └────┬────┘   └────┬────┘    └────┬────┘    └─────┬────┘
     │           │             │              │               │
     └───────────┴─────────────┴──────────────┴───────────────┘
                                │
                ┌───────────────▼────────────────┐
                │   Browser Session Pool         │
                │   Playwright (undetected)      │
                │   - 1 profile per account      │
                │   - Residential proxy (固定)   │
                │   - Stealth fingerprint        │
                └───────────────┬────────────────┘
                                │
                ┌───────────────▼────────────────┐
                │   Storage Layer                │
                │   PostgreSQL + Redis + S3      │
                └────────────────────────────────┘
```

---

## 3. モジュール詳細

### 3.1 Browser Session Pool（ブラウザセッション層）

**目的**：HTTP 直叩きではなく「本物のブラウザ」で操作することで検知回避。

- **Playwright (Python)** + undetected プラグイン（`playwright-stealth` 相当）
- **アカウント毎に永続 `user_data_dir`**：Cookie / localStorage / IndexedDB を保持
- **アカウント毎に固定の住宅用プロキシ**（ローテーションしない = IP 履歴の一貫性）
- **Fingerprint 固定**：UA / viewport / WebGL / Canvas / Fonts / timezone / locale
- **ヒューマン模倣**：
  - タイピング速度ジッター（80〜250ms / key）
  - マウスカーブ移動（Bezier）
  - スクロール・停止・戻る等の「無目的な挙動」を挟む
- **セッション再開**：新規ログインは最小化、既存 Cookie を再利用

### 3.2 Trend Scout（トレンド収集）

**X のスクレイピング依存度を下げる** ため、外部ソースを主・X を従とする：

| ソース | 手段 | ToS |
|---|---|---|
| Google Trends Japan | 公式 `pytrends` または `google-trends-api` | OK |
| Yahoo! ニュース トピックス | RSS | OK |
| NHK ニュース | RSS | OK |
| はてブ ホットエントリ | RSS | OK |
| X トレンドタブ | Playwright で最小限 | グレー |

収集データは DB に蓄積し、**話題分類 + センシティブフィルタ**（政治・宗教・炎上系を除外）を通す。

### 3.3 Content Generator（投稿文生成）

- **Claude API (claude-sonnet-4-6)** で生成
- 入力：
  - トレンドワード
  - 過去のバズ投稿の「型」（事前スクレイプした匿名化サンプル）
  - アカウントのペルソナ設定（JSON）
- 出力：
  - 3 候補（短文 / 画像付き / 動画付き）
  - それぞれにリスクスコア（センシティブ・誤情報・薬機法・景表法）
- **画像生成**：
  - Stable Diffusion / DALL-E / Flux のいずれか
  - あるいは Unsplash / Pexels 等の CC0 から選定
- **重複チェック**：埋め込み（embedding）で過去投稿との類似度 >0.9 なら破棄
- **承認キューに投入**：自動投稿ではなく、人間が 1 タップ承認 → 予約投稿

### 3.4 Posting Bot（投稿実行）

- Playwright でブラウザ UI 経由
- 投稿タイミング：
  - アカウントの「過去のアクティブ時間」に合わせる
  - ±30 分のジッター
  - 1 日 3〜5 投稿まで（初期）、成熟後 8〜10 投稿まで
- 投稿失敗時：即時停止 → incident テーブルに記録 → 人間通知

### 3.5 Follow Manager（フォロー運用）

**方針：さしみ氏推奨の「フォローする側に回る」を厳守**。

- `#ブルバ相互` `#ブルバ100` 等のハッシュタグ投稿を検索 → 投稿者プロフィールを確認 → 条件を満たす相手をフォロー
- フォロー条件（ホワイトリスト）：
  - Premium 認証済み（青バッジ）
  - フォロー/フォロワー比率が健全
  - 過去投稿に規約違反の気配なし
- **呼びかけ投稿は絶対に投稿しない**
- レート上限（初期値、段階的緩和）：
  - Day 1〜3：5 follow / 日
  - Day 4〜7：10 follow / 日
  - Day 8〜14：20 follow / 日
  - Day 15〜：30 follow / 日（上限）
- **自動 unfollow**：7 日経過しても返フォローなしの相手を整理（比率保護）
- **比率ガード**：`following / followers > 1.1` で follow 動作を一時停止

### 3.6 Analytics & Safety Monitor（分析・安全監視）

- 自アカウントの Analytics ダッシュボードをスクレイプ
- KPI：
  - 認証済みフォロワー数（目標 500）
  - 3ヶ月累計インプレッション（目標 500万）
  - エンゲージメント率
- **異常検知**：
  - インプが直近ベースラインから -50% → シャドウバン疑い → 投稿停止 24h
  - ログインチャレンジ / CAPTCHA 検知 → **全アカウント即時停止**
  - `rate limited` / `unable to follow` 応答 → 対象アカウント 12h 停止
- **日次レポート** を LINE / Slack / Email で通知

### 3.7 Safety Guardrails（安全装置・横断機能）

| 装置 | 内容 |
|---|---|
| Circadian Schedule | JST 02:00〜07:00 は全動作停止（睡眠時間） |
| Idle Session | 無目的スクロールのみのセッションをランダム挿入（1 日 2〜3 回） |
| Random Break | 30〜90 分の休憩を日中に挟む |
| Warm-up Curve | 新規アカウントは 2 週間の段階的ウォームアップ（読むのみ → Like → Follow → Post） |
| Kill Switch | 単一 API で全アカウント即停止 |
| Canary Account | 監視用ダミーアカウントからの Reply 可視性テスト（shadow-ban 早期検知） |
| Content Compliance Filter | 投稿前に X Rules / 日本法令ベースでチェック |

---

## 4. データベーススキーマ（抜粋）

```sql
-- アカウント情報
CREATE TABLE accounts (
  id              SERIAL PRIMARY KEY,
  handle          TEXT UNIQUE NOT NULL,
  persona_json    JSONB NOT NULL,
  proxy_url       TEXT NOT NULL,
  user_data_dir   TEXT NOT NULL,
  status          TEXT NOT NULL,          -- active | paused | suspended
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 投稿履歴
CREATE TABLE posts (
  id              SERIAL PRIMARY KEY,
  account_id      INT REFERENCES accounts(id),
  content         TEXT NOT NULL,
  media_s3_key    TEXT,
  trend_word      TEXT,
  risk_score      REAL,
  approved_by     TEXT,
  posted_at       TIMESTAMPTZ,
  x_status_id     TEXT,
  impressions     INT,
  likes           INT,
  retweets        INT,
  replies         INT
);

-- フォロー運用履歴
CREATE TABLE follows (
  id              SERIAL PRIMARY KEY,
  account_id      INT REFERENCES accounts(id),
  target_handle   TEXT NOT NULL,
  target_is_premium BOOL,
  followed_at     TIMESTAMPTZ,
  unfollowed_at   TIMESTAMPTZ,
  returned_follow BOOL
);

-- トレンド収集
CREATE TABLE trends (
  id              SERIAL PRIMARY KEY,
  source          TEXT NOT NULL,          -- google | yahoo | x | nhk ...
  word            TEXT NOT NULL,
  category        TEXT,
  sensitive       BOOL,
  rank            INT,
  collected_at    TIMESTAMPTZ
);

-- インシデント（凍結・CAPTCHA 等）
CREATE TABLE incidents (
  id              SERIAL PRIMARY KEY,
  account_id      INT REFERENCES accounts(id),
  kind            TEXT NOT NULL,          -- captcha | ratelimit | shadow_ban | login_challenge
  detail          JSONB,
  occurred_at     TIMESTAMPTZ DEFAULT NOW(),
  resolved        BOOL DEFAULT FALSE
);

-- 日次 KPI スナップショット
CREATE TABLE daily_kpi (
  account_id      INT REFERENCES accounts(id),
  date            DATE,
  premium_followers INT,
  total_impressions BIGINT,
  engagement_rate REAL,
  PRIMARY KEY (account_id, date)
);
```

---

## 5. 技術スタック

| レイヤー | 採用 |
|---|---|
| 言語 | Python 3.11 |
| ブラウザ自動化 | Playwright + playwright-stealth |
| スケジューラ | APScheduler または Celery beat |
| キュー | Redis (rq / celery) |
| API | FastAPI |
| DB | PostgreSQL 16 |
| オブジェクトストア | S3 互換（MinIO 可） |
| LLM | Claude API（`claude-sonnet-4-6`、長文は `claude-opus-4-6`） |
| 画像生成 | Stable Diffusion API / DALL-E 3 |
| 監視 | Prometheus + Grafana、通知は LINE Notify / Discord Webhook |
| デプロイ | Docker Compose（VPS）。住宅用プロキシ必須のため国内 VPS 推奨 |

---

## 6. 実装ロードマップ

### Phase 0：基盤（1〜2週間想定、作業量ベース）
- [ ] リポジトリ構造・CI
- [ ] Playwright Browser Session Pool（単一アカウント）
- [ ] Login + Cookie 永続化
- [ ] Kill Switch + 監視ダッシュボードの骨組み

### Phase 1：読み取り系
- [ ] Trend Scout（Google Trends / Yahoo / NHK / はてブ）
- [ ] Analytics Scraper（自アカウント KPI）
- [ ] DB スキーマ + Alembic マイグレーション

### Phase 2：コンテンツ生成
- [ ] Claude API 組み込み
- [ ] ペルソナ JSON 定義
- [ ] 承認キュー UI（FastAPI + 最小 HTML）
- [ ] コンプライアンス・フィルタ

### Phase 3：投稿・フォロー実行
- [ ] Posting Bot（1 日 3 投稿から開始）
- [ ] Follow Manager（Day 1〜3 の 5 follow から開始）
- [ ] Incident Detector（CAPTCHA / rate limit / shadow ban）

### Phase 4：安全装置と成熟化
- [ ] Circadian / Idle Session / Break
- [ ] Warm-up Curve
- [ ] Canary Account による shadow-ban 検知
- [ ] A/B テスト

### Phase 5：多アカウント化（任意）
- [ ] Fingerprint 完全分離
- [ ] プロキシ管理
- [ ] 多アカウント比較ダッシュボード

---

## 7. 追加提案（あったら良いと思う仕組み）

参考資料で触れられていない、凍結リスク低減と ROI 向上に効くと考えた追加機能：

### 7.1 本物の価値提供 70%：トレンド便乗 30% のコンテンツミックス
- スパム認定を避けるには **自然な価値提供が主、便乗が従** の配分が必須
- アカウントのジャンル（例：IT・副業・ダイエット）に沿った evergreen 投稿プールを事前生成
- Bot はトレンドが弱い日はプールから自動選択

### 7.2 Shadow-ban Canary
- 監視専用の別アカウント（別端末・別 IP）を用意
- 本番アカウントの Reply が canary のタイムラインに表示されるかを定期確認
- 表示されない = shadow ban → 即時投稿停止 & 人間通知

### 7.3 AI 品質スコア + Human Approval Queue
- Claude に投稿を自己評価させる（バズ度 / 炎上リスク / ブランド適合度）
- スコア上位のみ承認キューへ
- 人間は 1 タップで承認 / 修正 / 却下

### 7.4 バズ投稿の「型」抽出バッチ
- トレンドワード検索で上位投稿の構文パターンを LLM で抽象化
- プロンプトテンプレートに自動マージ
- 「パクリではなく型を借りる」をシステム化（さしみ氏の言及に対応）

### 7.5 エンゲージメント返礼 Bot（慎重に）
- 自投稿への Reply に対して、LLM 生成の返信を承認キュー経由で返す
- 会話継続 = エンゲージメント率向上 + インプ押し上げ
- ただし全自動返信は絶対 NG、必ず人間承認

### 7.6 ハッシュタグ投稿の自動削除
- さしみ氏の警告どおり、万一ハッシュタグ投稿をした場合は収益化条件達成後に一括削除
- 本設計では「そもそも投稿しない」が原則のため、この機能は「過去投稿の監査 & 削除提案」として限定実装

### 7.7 アカウント健康スコア
- 各アカウントの「健康度」を 0〜100 で可視化
- 要素：incident 頻度、shadow-ban 疑い、比率、投稿多様性、インプ推移
- 閾値を下回ったら自動で活動レベルを 1 段階下げる

### 7.8 費用対効果ダッシュボード
- 収益化達成までの見込み / 実際の X Premium 収益 vs LLM 呼び出しコスト・プロキシ費用・VPS 費用
- ROI がマイナスなら警告

### 7.9 段階的ウォームアップ Wizard
- 新規アカウントを迎える際の 14 日ウォームアッププランを自動生成
- Day 1〜3：読むだけ、Day 4〜6：Like のみ、Day 7〜9：Like + 1 follow/日、Day 10〜14：軽い投稿、Day 15〜：本格稼働

### 7.10 インシデントから学習する自動チューナー
- CAPTCHA / ratelimit 発生時の行動パターンを特徴量化
- 次回以降、類似パターンを発火前に回避（例：特定時間帯の follow 連打で頻発 → その時間帯の follow 禁止）

---

## 8. 非目標（やらないこと）

明確に **しない** ことを宣言しておく：

- ❌ 他人のアカウントの乗っ取り / 代行
- ❌ 購入フォロワー / ボットフォロワー利用
- ❌ `#ブルバ相互` 系の呼びかけハッシュタグ投稿
- ❌ 他ユーザーへの無差別 DM / Reply スパム
- ❌ 完全無人運用（Human-in-the-loop を維持）
- ❌ 収益化規約のグレーな直接違反（インプ水増し等）
- ❌ 複数アカウントでの自作自演 Like / RT

---

## 9. リスクレベル別まとめ

| 機能 | 凍結リスク | 収益化停止リスク | 効果 |
|---|---|---|---|
| トレンド便乗投稿（品質あり） | 低 | 低 | 高 |
| ブルバ垢への能動フォロー | 中 | 低 | 高 |
| 呼びかけハッシュタグ投稿 | 中 | **高** | 中 |
| AI 生成画像付き投稿 | 低 | 低 | 中〜高 |
| 自動 Reply 返信 | 中 | 中 | 中 |
| 自動 Like スパム | 高 | 高 | 低 |

→ **緑（低リスク）×高効果** の機能を中心に構成する。
中リスク以上は原則 Human-in-the-loop、ただし §10 の Full Auto Mode 条件を満たす場合に限り自動化可。

---

## 10. Full Auto Mode（完全自動投稿モード）

> **結論：技術的には可能。ただし Human-in-the-loop 版と比べて凍結・炎上・収益化停止のリスクが上がるため、
> 以下の「二重三重の安全装置」をすべて満たしたうえで、段階的自律化カリキュラムに沿って有効化する。**

### 10.1 Full Auto にすることで増えるリスク

| リスク | 原因 | 対策 |
|---|---|---|
| 炎上コンテンツ誤投稿 | LLM が空気読めない | Multi-stage LLM Critic |
| 薬機法・景表法違反 | LLM の誇張表現 | Compliance LLM + 正規表現ブラックリスト |
| センシティブ便乗 | 訃報・災害・政治トレンドに乗ってしまう | Trend Blacklist + Sentiment Filter |
| 事実誤認・誤情報 | LLM ハルシネーション | 事実系カテゴリの自動投稿を禁止 |
| パターン検知 | 生成文の文体一貫性 | スタイルランダマイザ + embedding 距離ガード |
| 連鎖炎上 | 1 投稿の炎上が他アカウントに波及 | 即時自動削除 + 他アカウント一時停止 |

### 10.2 Full Auto Pipeline（多段パイプライン）

承認キューの代わりに、**LLM を多段で相互監査** させて人間の代替とする。

```
[Trend Scout]
     │
     ▼
[Trend Blacklist Filter]           ← 訃報 / 災害 / 政治 / 薬機 / ブランド / 有名人個人名 を除外
     │
     ▼
[Sentiment & Category Classifier]  ← negative / political / medical をブロック
     │
     ▼
[Content Generator (claude-sonnet-4-6)]
     │ 3 candidates
     ▼
[Critic LLM (claude-opus-4-6)]     ← 炎上度 / ブランド適合 / 自然さ を評価、0-100
     │ pass if score >= 85
     ▼
[Compliance LLM + Regex]           ← 薬機法 / 景表法 / 誹謗中傷 / 商標
     │
     ▼
[Duplication Guard]                 ← 過去 N 投稿との embedding 距離 >= 0.35
     │
     ▼
[Safety Gate]                       ← アカウント健康スコア・ウォームアップ段階・レート上限
     │
     ▼
[Post Executor]                     ← Playwright で投稿
     │
     ▼
[Post-hoc Monitor]                  ← 投稿後 30 / 60 / 120 分のシグナル監視
     │
     ▼
[Auto Rollback?]                    ← 閾値超過で自動削除
```

**パイプラインの特徴**：
- 任意の 1 段でも reject → その候補は破棄、次候補を試す
- 全候補が reject → その日の投稿はスキップ（無理に投稿しない）
- 全段の判定ログを DB に残す（後で人間がレビュー・調整可能）

### 10.3 Trend Blacklist（自動投稿禁止カテゴリ）

以下のカテゴリにマッチするトレンドワードは **Full Auto では絶対に投稿しない**：

- 訃報・追悼・死去・自殺
- 災害・地震・火災・事故・事件
- 政治・選挙・政党・政治家
- 宗教
- 医療・薬・診断・治療（薬機法リスク）
- 特定の有名人・企業・ブランドを主語にする（名誉毀損・商標リスク）
- 差別・ジェンダー・国籍関連の論争
- 訴訟・逮捕・不祥事

→ これらは **Human-in-the-loop モードでのみ** 扱う（Full Auto とは別の経路）。

### 10.4 Auto Rollback（自動削除）

投稿後に以下のシグナルが出たら **自動削除**：

| トリガー | 閾値 | 判定タイミング |
|---|---|---|
| 通報バッジ検出 | 1 件以上 | 5 分毎にチェック |
| ネガティブ Reply 比率 | 全 Reply の 40% 以上 | 30 / 60 / 120 分 |
| インプに対する Like 率 | ベースラインの 10% 以下 | 60 分 |
| 「不快」「気持ち悪い」「炎上」「通報」等キーワード Reply | 3 件以上 | 随時 |
| Reply が急増（ベースラインの 10 倍） | — | 15 分毎 |

ロールバック発動時：
1. 投稿を削除
2. incident テーブルに記録
3. 同アカウントの Full Auto を 24 時間停止
4. 原因トレンドワードをブラックリストに追加
5. 人間に通知

### 10.5 段階的自律化カリキュラム（Progressive Autonomy）

いきなり 100% 自動にせず、**承認率の実績に応じて段階的に自律度を上げる**。

| ステージ | 期間 | 自動化率 | 条件 |
|---|---|---|---|
| S0：Shadow | 7 日 | 0%（生成するが投稿しない、人間レビューのみ） | 常時 |
| S1：Review | 14 日 | 0%（全件承認キュー） | S0 で 85% 以上 pass |
| S2：Semi-Auto | 14 日 | 50%（ランダム半分を自動、残り承認） | S1 で炎上 0 件 |
| S3：Auto | ∞ | 100%（ただし §10.3 の安全装置すべて稼働） | S2 で炎上 0 件、ロールバック 1%以下 |

**降格条件**（どのステージからも即座に 1 段階下がる）：
- 自動ロールバック発動
- インシデント発生（CAPTCHA / rate limit / shadow ban）
- アカウント健康スコア 70 未満
- 人間が手動で「これは投稿すべきでなかった」とフラグを立てた

### 10.6 Full Auto 時の投稿レート

自動化すると「投稿しすぎ」の誘惑が増すため、**Human 版より厳しめ** に設定：

| 項目 | Human 版 | Full Auto 版 |
|---|---|---|
| 初期の 1 日投稿数 | 3〜5 | **2〜3** |
| 成熟後の 1 日投稿数 | 8〜10 | **5〜6** |
| 投稿間隔の最小値 | 90 分 | **120 分** |
| Circadian 停止時間 | 02:00〜07:00 | **01:00〜08:00** |
| 連続投稿 | なし | **絶対禁止（必ず jitter）** |

### 10.7 Full Auto では「やらない」こと

自動化しても以下は引き続き Human-in-the-loop：

- ❌ Reply への返信（会話の文脈判断はまだ LLM に任せきれない）
- ❌ センシティブカテゴリ（§10.3）のトレンド便乗
- ❌ 引用 RT（他人の投稿を主語にするため炎上リスクが非対称）
- ❌ 画像に人物写真を含む投稿（肖像権）
- ❌ 新規アカウントのウォームアップ期間中（Day 1〜14）

### 10.8 実装フラグ

アカウント毎に設定を持ち、いつでも Human 版に戻せるようにする：

```yaml
# accounts/sashimi_test.yml
handle: sashimi_test
mode: full_auto        # human_approval | semi_auto | full_auto | shadow
stage: S2              # S0 | S1 | S2 | S3
daily_post_quota: 3
circadian_start: "01:00"
circadian_end: "08:00"
rollback_enabled: true
blacklist_version: v3
critic_threshold: 85
duplication_threshold: 0.35
```

→ **いつでも 1 コマンドで `mode: human_approval` に戻せる** こと自体が最大の安全装置。

---

## 11. 次のアクション

1. 本設計レビュー & 方針確定（Full Auto Mode の採否含む）
2. Phase 0（基盤）の PoC 実装（別 PR）
3. 単一アカウントでの 2 週間ドライラン（Shadow ステージ = 生成のみ投稿なし）
4. ログを人間レビュー → critic_threshold / blacklist の調整
5. S1 → S2 → S3 と段階的に自律化
6. 定期的にインシデント振り返り、パイプライン改善

---

**改訂履歴**

| Ver | Date | 内容 |
|---|---|---|
| 0.1 | 2026-04-10 | 初版 |
| 0.2 | 2026-04-10 | Full Auto Mode（§10）を追加。多段 LLM パイプライン、自動ロールバック、段階的自律化カリキュラムを定義 |
