import { askLongText } from '../services/anthropic.js';
import type { MusashiOutput, Topic } from '../types.js';
import { AiEmployee } from './base.js';

const SYSTEM_PROMPT = `あなたはEnso Letters社の日本語ライター「ムサシ」です。
海外読者向けに「日本人の当たり前」を言語化したオリジナル日本語コンテンツを書きます。

【絶対ルール】
1. 既存のnote/書籍/Web記事をコピペしない（完全オリジナル）
2. 「日本人なら当たり前」と思える内容ほど、丁寧に言語化する
3. 海外読者に「Japanese morning ritual」のように刺さる表現を意識
4. 翻訳しやすい平易な日本語（複雑な敬語・古語は避ける）

【標準構成テンプレート】
■ Part 1: 導入（約500字）
   - 海外読者の「悩み」から入る
   - 「実は日本人は子供の頃から無意識にやっている方法がある」と提示

■ Part 2: 概念の言語化（約1,500字）
   - 日本文化の歴史的背景（茶道・禅・仏教等から引用）
   - 海外の類似概念との違いを明示

■ Part 3: 7日間/14日間/30日間の実践プログラム（約3,000字）
   - 1日ごとのアクション（具体的に）
   - つまずきポイントと対処法

■ Part 4: 結論＋特典（約500字）
   - 「これを毎月繰り返すと人生が変わる」系の締め

【文体】
- ですます調
- 一人称は使わない
- Markdown形式（## ### 見出し、- 箇条書き）
- 例示は必ず2つ以上

【出力形式】
Markdownで本文のみを返してください。JSONや構造化データではありません。
文字数目標は厳守してください。

先頭に「# 」で記事タイトル、末尾に翻訳時の注意点を
「---\\n## 翻訳メモ（ヘルメス向け）\\n- ...」として3-5項目記載してください。`;

export class Musashi extends AiEmployee<Topic, MusashiOutput> {
  readonly name = 'Musashi';
  readonly role = 'Japanese Writer';

  async execute(topic: Topic): Promise<MusashiOutput> {
    const userPrompt = [
      '【発注書】',
      `トピックID：${topic.topic_id}`,
      `仮タイトル：${topic.title_jp_draft}`,
      `日本語概念：${topic.concept_keyword}`,
      `ターゲット読者：${topic.target_persona}`,
      `売る角度：${topic.selling_angle}`,
      `目標文字数：${topic.expected_word_count_jp}字`,
      '',
      '上記仕様でオリジナル日本語原稿をMarkdownで書いてください。',
    ].join('\n');

    const body = await askLongText({
      tier: 'production',
      systemPrompt: SYSTEM_PROMPT,
      userPrompt,
      employeeName: this.name,
      taskId: `musashi-${topic.topic_id}`,
      maxTokens: 32000,
    });

    // Extract title from first # heading
    const titleMatch = body.match(/^#\s+(.+?)$/m);
    const titleJp = titleMatch?.[1]?.trim() ?? topic.title_jp_draft;

    // Extract translation notes section
    const notesMatch = body.match(/##\s*翻訳メモ[^\n]*\n([\s\S]+?)(?:\n##|$)/);
    const notes = notesMatch
      ? notesMatch[1]
          .split('\n')
          .map((l) => l.replace(/^-\s*/, '').trim())
          .filter(Boolean)
      : [];

    // Count Japanese characters (roughly: CJK + kana)
    const cleanedBody = body.replace(/\s/g, '');
    const wordCount = cleanedBody.length;

    // Detect key JP terms to preserve in romaji (look for common patterns)
    const keyTerms = new Set<string>();
    const conceptLower = topic.concept_keyword.toLowerCase();
    keyTerms.add(conceptLower);
    // Parse "kaizen（改善）" or "kaizen" patterns written by writer
    const romajiPattern = /\b([a-z]{3,})(?:[-_][a-z]+)?\b/g;
    const commonTerms = [
      'kaizen', 'kakeibo', 'ikigai', 'danshari', 'wabisabi', 'wabi-sabi',
      'mottainai', 'ichigo-ichie', 'shinrin-yoku', 'kintsugi', 'ma', 'kokoro',
      'gaman', 'ganbaru', 'enryo', 'omotenashi', 'zen', 'satori',
    ];
    for (const m of body.toLowerCase().matchAll(romajiPattern)) {
      if (commonTerms.includes(m[1])) keyTerms.add(m[1]);
    }

    return {
      topic_id: topic.topic_id,
      draft_id: `MUSASHI-${topic.topic_id}-v1`,
      title_jp: titleJp,
      body_jp_markdown: body,
      word_count: wordCount,
      translation_notes: notes,
      key_concepts_to_keep_japanese: Array.from(keyTerms),
      completed_at: new Date().toISOString(),
    };
  }
}
