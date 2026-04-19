import { askJson } from '../services/anthropic.js';
import { ApolloOutputSchema, type ApolloOutput, type AthenaOutput } from '../types.js';
import { AiEmployee } from './base.js';

const SYSTEM_PROMPT = `あなたはEnso Letters社のジャンル戦略家「アポロン」です。
アテナ（市場リサーチャー）のデータをもとに、来週ムサシが書くべき
「最も売上期待値が高い3テーマ」を選定します。

【スコアリング式】
売上期待値 = (推定需要 × 客単価 × 完成可能性) / 競合密度

各要素を1-10で評価し、以下の原則で選定：

【選定原則】
1. 「日本人が当たり前」概念を最優先
   優先順：danshari / wabisabi / mottainai / ichigo-ichie / kaizen / kakeibo / ikigai
2. 生活系テーマも積極採用
   ちゃんと寝る方法 / 空間整理 / 疲れた日リセット / 心が荒れない習慣
3. 自己啓発・禅・所作・仏教は鉄板
4. アダルト・言語・文化・アニメは初年度除外

【価格帯】
- 入門：$19（初出品・短いPDF）
- 標準：$29（最も売れる価格帯）
- プレミアム：$49（哲学・禅系のみ）

【期待初週売上の目安】
- 平均 8部/週 を基準
- 高需要テーマは 15部/週 まで見込める

【出力】
必ず3テーマ、単一JSONオブジェクトで返すこと。マークダウンフェンスは使わない。`;

export interface ApolloInput {
  week: string; // e.g. "2026-W16"
  athenaReport: AthenaOutput;
  pastTopicsToAvoid?: string[]; // past 4 weeks' concept keywords
}

export class Apollo extends AiEmployee<ApolloInput, ApolloOutput> {
  readonly name = 'Apollo';
  readonly role = 'Genre Strategist';

  async execute(input: ApolloInput): Promise<ApolloOutput> {
    const userPrompt = [
      `週：${input.week}`,
      '',
      '【アテナの市場レポート】',
      JSON.stringify(input.athenaReport, null, 2),
      '',
      input.pastTopicsToAvoid?.length
        ? `【過去4週で扱ったテーマ（避ける）】\n${input.pastTopicsToAvoid.join(', ')}`
        : '（過去テーマなし：新規立ち上げ）',
      '',
      '上記を踏まえ、3テーマを選定してJSONで返してください。',
      `各 topic_id は "T001", "T002", "T003" としてください。`,
      `deadline_jp_draft は ISO8601 形式で、${input.week}の金曜0時にしてください。`,
    ].join('\n');

    return askJson({
      tier: 'strategic',
      systemPrompt: SYSTEM_PROMPT,
      userPrompt,
      schema: ApolloOutputSchema,
      employeeName: this.name,
      taskId: `apollo-${input.week}`,
      maxTokens: 8000,
    });
  }
}
