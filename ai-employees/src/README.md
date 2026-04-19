# Enso Letters — AI Orchestrator

11 AI社員が完全自律でコンテンツを生成・翻訳・販売する、海外note売上自動化システム。仕様は `../README.md` と `../employees/*.md` を参照。

## クイックスタート（5分で最初のコンテンツ生成）

### 1. 前提
- Node.js 20以上
- Anthropic API キー（必須）— https://console.anthropic.com で発行

### 2. セットアップ

```bash
cd ai-employees/src
npm install
cp .env.example .env
# .env を開いて ANTHROPIC_API_KEY を設定
```

### 3. 最初の1本を生成（ドライラン）

```bash
npm run produce -- --limit 1
```

これだけで以下が全自動で実行されます：
1. **アテナ**：海外market研究レポート生成
2. **アポロン**：売れるテーマ TOP3 を選定
3. **ムサシ**：日本語原稿を5,000-8,000字で執筆
4. **ヘルメス**：英訳＋ローカライズ
5. **カルメン**：Gumroad / Medium / Substack 用の販売素材生成
6. **ヤヌス**：各プラットフォームへ出品（この段階はDRY-RUN）
7. **イリス**：SNS投稿10本のスケジュール生成

完了後、`output/2026-W16/T001/` 配下に以下が生成されます：
- `draft_musashi.json` — ムサシ生成メタデータ
- `draft_jp.md` — 日本語原稿（Markdown）
- `translation_hermes.json` — 翻訳メタデータ
- `body_en.md` — 英語記事（Markdown）
- `package_carmen.json` — LP/タイトル/タグ一式
- `publication_janus.json` — 出品URL（ドライラン時は仮URL）
- `sns_iris.json` — SNS投稿10本

### 4. 実運用フェーズへ

実際にGumroad/Medium/Substackへ出品するには：

```bash
# .env に各プラットフォームのAPIトークンを設定
# GUMROAD_ACCESS_TOKEN=...
# MEDIUM_INTEGRATION_TOKEN=...

npm run produce -- --publish
```

（現状、プラットフォーム出品コードはDRY-RUNで返すのみ。実API呼び出しは `src/platforms/*.ts` 内の `TODO` 部分に追記してください。）

## CLIコマンド一覧

| コマンド | 用途 |
|---|---|
| `npm run produce` | 日次制作パイプラインを実行（3本） |
| `npm run produce -- --limit 1` | 1本だけテスト生成 |
| `npm run produce -- --publish` | 実際に各PFに出品 |
| `npm run weekly` | 週次戦略のみ（アテナ＋アポロン） |
| `npm run monthly` | 月次CEOレポート生成 |
| `npm run typecheck` | TypeScript型チェック |
| `npm run db:migrate` | Prisma DB マイグレーション |
| `npm run db:generate` | Prisma Client生成 |

## ディレクトリ構成

```
src/
├── package.json
├── tsconfig.json
├── .env.example
├── prisma/
│   └── schema.prisma          # SQLite スキーマ（売上・トピック・エスカレーション）
└── src/
    ├── config.ts              # 環境変数ローダー
    ├── types.ts               # 共有Zod型定義
    ├── services/
    │   ├── anthropic.ts       # Claude APIラッパー（プロンプトキャッシュ込み）
    │   ├── logger.ts          # pinoロガー
    │   └── storage.ts         # ファイル永続化（output/配下）
    ├── employees/             # 11名のAI社員実装
    │   ├── base.ts            # 基底クラス（リトライ・ロギング）
    │   ├── hades.ts           # CEO統括・エスカレーション
    │   ├── athena.ts          # 市場リサーチ（要Claude）
    │   ├── apollo.ts          # ジャンル戦略（要Claude）
    │   ├── musashi.ts         # 日本語ライター（要Claude）
    │   ├── hermes.ts          # 翻訳者（要Claude）
    │   ├── carmen.ts          # コピーライター（要Claude）
    │   ├── janus.ts           # プラットフォーム運用
    │   ├── cronos.ts          # 価格戦略（ルールベース、LLM不要）
    │   ├── iris.ts            # SNS運用（要Claude）
    │   ├── minerva.ts         # 売上分析（集計のみ、LLM不要）
    │   └── amaterasu.ts       # カスタマーサポート（要Claude）
    ├── platforms/
    │   ├── gumroad.ts         # Gumroad API（DRY-RUN）
    │   ├── medium.ts          # Medium API（DRY-RUN）
    │   └── substack.ts        # Substack（Playwright想定、DRY-RUN）
    ├── workflows/
    │   └── daily.ts           # 日次パイプライン
    └── cli/
        ├── produce.ts         # npm run produce
        ├── weekly.ts          # npm run weekly
        └── monthly.ts         # npm run monthly
```

## 使用モデル（コスト最適化）

| 役割 | デフォルト | 月コスト想定（100本/月） |
|---|---|---|
| 戦略判断（アポロン・ハデス） | `claude-opus-4-7` | ~$40 |
| 制作（ムサシ・ヘルメス・カルメン・アテナ・イリス） | `claude-sonnet-4-6` | ~$300 |
| 運用（アマテラス） | `claude-haiku-4-5` | ~$50 |

プロンプトキャッシュで実コストは上記の **20-30%** に収まる見込み。

## 設計上の重要事項

### Claude APIの活用
- **プロンプトキャッシュ**：システムプロンプトに `cache_control: ephemeral` を設定。同じ社員を1日3回呼ぶと2回目以降は90%割引。
- **Adaptive thinking**：Opus 4.7 / Sonnet 4.6 で有効化。戦略系は `effort: high`、制作系は `effort: medium`。
- **ストリーミング**：長文生成（ムサシ・ヘルメス）では必須。HTTPタイムアウト回避。
- **スキーマバリデーション**：全JSON出力はZodで検証。LLMの出力バグを早期検知。

### CEOの介入ポイント
通常時は **ゼロ**。以下のみ通知（`src/employees/hades.ts` 参照）：
- 法務リスク（DMCA等）
- 売上30%以上下落
- 月次承認事項（月1回・5分以内で完結）

## 次のTODO（実運用までの残作業）

1. **各プラットフォームの実API接続**（`src/platforms/*.ts` の TODO部分）
2. **Originality.ai 連携**でムサシ出力の重複チェック
3. **DALL·E 3 / Midjourney API** をカルメンに接続してサムネ生成
4. **X / Threads API** をイリスに接続して実投稿
5. **Prisma DB への永続化**（現状はJSONファイル）
6. **cron / systemd timer** での定時実行

## ライセンス

Private. すべてのAI生成コンテンツはオリジナル生成（パクリ厳禁）。
