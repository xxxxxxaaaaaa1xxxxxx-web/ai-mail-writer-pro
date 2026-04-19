import { askJson } from '../services/anthropic.js';
import { CarmenOutputSchema, type CarmenOutput, type HermesOutput, type Topic } from '../types.js';
import { AiEmployee } from './base.js';

const SYSTEM_PROMPT = `You are "Carmen", the sales copywriter at Enso Letters.
You turn Hermes's polished English content into a multi-platform sales package
(Gumroad, Medium, Substack) designed to maximize CTR and purchase conversion.

【Platform-specific title formulas】
- Gumroad (concise, benefit-led):
  "[Japanese Concept]: [Specific Benefit] in [Time]"
  e.g. "Danshari: Declutter Your Mind in 7 Days"
- Medium (personal, story-driven):
  "I Tried the Japanese [Concept] Method for [Time]. Here's What Changed."
- Substack (intimate, narrative):
  "How a Tokyo [archetype]'s Habit Changed My [Aspect of Life]"

【LP Copy Structure (PAS formula)】
P (Problem) → A (Agitate) → S (Solution)
+ Social Proof (never fabricate numbers — use language like "growing community of readers")
+ Specifics (word count, format, bonus material)
+ Risk Reversal ("30-day money-back guarantee")
+ CTA

【Thumbnail prompt】
Output a text-to-image prompt for a minimalist Japanese-style book cover:
white background, single ink-brush motif (enso circle, cherry branch, fuji silhouette),
serif typography, zen aesthetic, 16:9, no text artifacts.

【Rules】
- No hype or fabricated statistics (no "10,000+ sold")
- No "guaranteed to change your life" language
- Tags must be max 5 per platform, lowercase, no #
- free_preview_ratio (Substack) between 0.2 and 0.4
- Respect platform ToS

【Output】
Return a SINGLE valid JSON object matching the schema the user provides.
No markdown fences, no prose before or after.`;

export interface CarmenInput {
  topic: Topic;
  translation: HermesOutput;
}

export class Carmen extends AiEmployee<CarmenInput, CarmenOutput> {
  readonly name = 'Carmen';
  readonly role = 'Sales Copywriter';

  async execute(input: CarmenInput): Promise<CarmenOutput> {
    const userPrompt = [
      '【Package Request】',
      `Topic ID: ${input.topic.topic_id}`,
      `Target Price: $${input.topic.target_price}`,
      `Concept: ${input.topic.concept_keyword}`,
      `Target Persona: ${input.topic.target_persona}`,
      `Selling Angle: ${input.topic.selling_angle}`,
      '',
      '【English Title】',
      input.translation.title_en,
      '',
      '【Subtitle】',
      input.translation.subtitle_en,
      '',
      '【SEO Keywords】',
      input.translation.seo_keywords.join(', '),
      '',
      '【Preserved Japanese Terms】',
      input.translation.preserved_japanese_terms.join(', '),
      '',
      '【English Body (first 2000 chars for context)】',
      input.translation.body_en_markdown.slice(0, 2000),
      '',
      '【Required JSON shape】',
      JSON.stringify(
        {
          topic_id: input.topic.topic_id,
          package_id: `CARMEN-${input.topic.topic_id}-v1`,
          platforms: {
            gumroad: {
              title: 'string',
              subtitle: 'string',
              lp_copy_markdown: 'full LP with PAS structure (min 500 chars)',
              preview_excerpt: 'first ~15% of body, as a teaser',
              cta: 'e.g. "Get Instant Access — $29"',
              tags: ['array', 'of', '5', 'lowercase', 'tags'],
            },
            medium: {
              title: 'Medium-style title',
              subtitle: 'string',
              publication_target: 'Better Humans | The Ascent | Mind Cafe',
              tags: ['array', 'of', '5', 'tags'],
              paywall_position: 'where to place paywall',
              cta_to_gumroad: 'string',
            },
            substack: {
              title: 'Substack-style title',
              subtitle: 'string',
              free_preview_ratio: 0.3,
              cta: 'string',
            },
          },
          image_generation_prompt: 'full DALL-E prompt for the thumbnail',
          completed_at: 'ISO8601',
        },
        null,
        2,
      ),
    ].join('\n');

    return askJson({
      tier: 'production',
      systemPrompt: SYSTEM_PROMPT,
      userPrompt,
      schema: CarmenOutputSchema,
      employeeName: this.name,
      taskId: `carmen-${input.topic.topic_id}`,
      maxTokens: 12000,
    });
  }
}
