import { askJson } from '../services/anthropic.js';
import { AthenaOutputSchema, type AthenaOutput } from '../types.js';
import { AiEmployee } from './base.js';

const SYSTEM_PROMPT = `あなたはEnso Letters社の海外市場リサーチャー「アテナ」です。
海外のGumroad/Medium/Substack市場をスキャンし、日本発コンテンツで売れる
トレンド・競合・市場ギャップを報告します。

【MVPモード】
現在は実際のWeb検索ツールが接続されていないため、あなたの訓練データと
ドメイン知識をもとに、最も蓋然性の高いトレンドレポートを生成してください。
今後、Brave Search / Tavily / Perplexity 等を接続予定です。

【出力】
実在する海外コンテンツクリエイター、実在するプラットフォーム、現実的な
価格帯で出力すること。捏造した統計や数字は避け、わからない値は省略。

必ず単一JSONオブジェクトで返すこと。`;

export interface AthenaInput {
  week: string; // e.g. "2026-W16"
  focusAreas?: string[]; // e.g. ["danshari", "shinrin-yoku"]
}

export class Athena extends AiEmployee<AthenaInput, AthenaOutput> {
  readonly name = 'Athena';
  readonly role = 'Market Researcher';

  async execute(input: AthenaInput): Promise<AthenaOutput> {
    const userPrompt = [
      `週：${input.week}`,
      input.focusAreas?.length
        ? `【重点分野】${input.focusAreas.join(', ')}`
        : '【重点分野】指定なし（全ジャンル横断）',
      '',
      '海外noteプラットフォーム（Gumroad/Medium/Substack/KaryaKarsa/Ghost/Steady/Ko-fi等）で、',
      '日本文化・日本発コンテンツに関するトレンド・競合・市場ギャップをレポートしてください。',
      '',
      '各 trending_concept は最低3件、各 top_competitors は最低2件、',
      'market_gaps は最低3件、recommended_focus_for_apollo は3件出力してください。',
    ].join('\n');

    return askJson({
      tier: 'production',
      systemPrompt: SYSTEM_PROMPT,
      userPrompt,
      schema: AthenaOutputSchema,
      employeeName: this.name,
      taskId: `athena-${input.week}`,
      maxTokens: 10000,
    });
  }
}
