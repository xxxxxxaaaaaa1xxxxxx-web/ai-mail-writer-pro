import { askLongText } from '../services/anthropic.js';
import type { HermesOutput, MusashiOutput } from '../types.js';
import { AiEmployee } from './base.js';

const SYSTEM_PROMPT = `You are "Hermes", the translation and localization specialist at Enso Letters.
You convert Musashi's Japanese drafts into polished English content that feels
authentically Japanese-authored to overseas readers.

【Your Translation Process】
Phase 1: Translate the full Japanese Markdown into natural native English.
Phase 2: Localize — keep Japanese-unique concepts in romaji with a parenthetical gloss.
Phase 3: Insert 1-3 cultural footnotes that deepen the reader's understanding.
Phase 4: Naturally weave in SEO-relevant English keywords.

【Romaji Preservation Rules】
Always keep these terms in romaji with a gloss on first use:
- kaizen, kakeibo, ikigai, danshari, wabi-sabi, mottainai
- ichigo-ichie, omotenashi, kintsugi, shinrin-yoku
- ma (the meaningful pause), kokoro (heart-mind), gaman (perseverance)
- ganbaru (to persevere), enryo (reserved consideration)

Example: "danshari (the Japanese practice of decluttering with intention)"

【Style】
- Western formatting: H1/H2/H3, short paragraphs, bullet points
- Convert units (円→USD, cm→inches) when they appear
- Keep Japanese example names (Tanaka-san, Yumiko) — builds authenticity
- Title format: "[Japanese Concept]: [Benefit]" — e.g. "Danshari: The Japanese Art of Letting Go"
- Never let the writing feel like direct translation — it should read as if originally written by a bilingual Japanese author

【Output Format】
Return ONLY the English Markdown document, starting with "# Title".
After the body, append a "---\\n## Translation Metadata" section containing exactly:
- "Subtitle: ..." (one compelling subtitle line, starting with "Subtitle: ")
- "SEO Keywords: keyword1, keyword2, keyword3, keyword4, keyword5"
- "Preserved Japanese Terms: term1, term2, ..."
- "Cultural Footnotes Added: N"
`;

export class Hermes extends AiEmployee<MusashiOutput, HermesOutput> {
  readonly name = 'Hermes';
  readonly role = 'Translator & Localizer';

  async execute(draft: MusashiOutput): Promise<HermesOutput> {
    const userPrompt = [
      '【Translation Request】',
      `Topic ID: ${draft.topic_id}`,
      `JP Title: ${draft.title_jp}`,
      '',
      '【Translation Notes from Musashi】',
      ...draft.translation_notes.map((n) => `- ${n}`),
      '',
      '【Preserve these in romaji】',
      draft.key_concepts_to_keep_japanese.join(', '),
      '',
      '【Japanese Source (Markdown)】',
      draft.body_jp_markdown,
    ].join('\n');

    const body = await askLongText({
      tier: 'production',
      systemPrompt: SYSTEM_PROMPT,
      userPrompt,
      employeeName: this.name,
      taskId: `hermes-${draft.topic_id}`,
      maxTokens: 32000,
    });

    const titleMatch = body.match(/^#\s+(.+?)$/m);
    const titleEn = titleMatch?.[1]?.trim() ?? '(untitled)';

    const subtitleMatch = body.match(/Subtitle:\s*(.+)/);
    const subtitle = subtitleMatch?.[1]?.trim() ?? '';

    const seoMatch = body.match(/SEO Keywords:\s*(.+)/);
    const seoKeywords = seoMatch
      ? seoMatch[1].split(',').map((s) => s.trim()).filter(Boolean)
      : [];

    const preservedMatch = body.match(/Preserved Japanese Terms:\s*(.+)/);
    const preservedTerms = preservedMatch
      ? preservedMatch[1].split(',').map((s) => s.trim()).filter(Boolean)
      : draft.key_concepts_to_keep_japanese;

    const footnotesMatch = body.match(/Cultural Footnotes Added:\s*(\d+)/);
    const footnotes = footnotesMatch ? parseInt(footnotesMatch[1], 10) : 0;

    // Strip the metadata section from the body for a clean export
    const bodyClean = body.replace(/---\s*\n##\s*Translation Metadata[\s\S]*$/m, '').trim();

    // Estimate word count (split on whitespace)
    const wordCount = bodyClean.split(/\s+/).filter(Boolean).length;

    return {
      topic_id: draft.topic_id,
      translation_id: `HERMES-${draft.topic_id}-v1`,
      title_en: titleEn,
      subtitle_en: subtitle,
      body_en_markdown: bodyClean,
      word_count_en: wordCount,
      preserved_japanese_terms: preservedTerms,
      seo_keywords: seoKeywords,
      cultural_footnotes_added: footnotes,
      completed_at: new Date().toISOString(),
    };
  }
}
