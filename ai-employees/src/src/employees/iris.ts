import { askJson } from '../services/anthropic.js';
import { z } from 'zod';
import type { HermesOutput, PublishedUrls } from '../types.js';
import { AiEmployee } from './base.js';

const PostsSchema = z.object({
  posts: z.array(
    z.object({
      platform: z.enum(['x', 'threads', 'linkedin', 'pinterest']),
      pattern: z.enum([
        'launch',
        'educational_tip',
        'storytelling',
        'data_stat',
        'cta',
      ]),
      content: z.string().max(280),
      hashtags: z.array(z.string()).max(6),
      scheduled_utc: z.string(),
    }),
  ).length(10),
});

const SYSTEM_PROMPT = `You are "Iris", the SNS marketing lead at Enso Letters.
You generate a 10-post daily social media schedule that drives overseas
readers to our Gumroad storefront. You write in confident, warm English —
never hype, never fabricated stats.

【Time zones for timing】
- 06:00 UTC — European morning
- 12:00 / 17:00 UTC — US East Coast morning → West Coast morning
- 22:00 UTC — US evening
- 02:00 UTC — SEA morning

【Post patterns (must use all 5 in balance)】
1. launch — announce the new drop, include URL
2. educational_tip — bite-sized wisdom with a concrete micro-action
3. storytelling — "My grandmother in Kyoto..." style, no fabrications
4. data_stat — ONLY real, cite-able data (cite the source); otherwise omit
5. cta — gentle call-to-action with URL

【Rules】
- Each post ≤ 280 characters (X constraint)
- No false statistics. No "1000+ readers" unless we have proof.
- Include the Gumroad URL on launch and cta posts only
- Hashtags: max 6, lowercase

【Output】
Return a single JSON object {"posts": [...]} with exactly 10 posts.
Spread posts across the time zones above.`;

export interface IrisInput {
  dateUtc: string;
  translation: HermesOutput;
  gumroadUrl?: string;
  isLaunchDay: boolean;
}

export type IrisOutput = z.infer<typeof PostsSchema>;

export class Iris extends AiEmployee<IrisInput, IrisOutput> {
  readonly name = 'Iris';
  readonly role = 'Social Media Marketer';

  async execute(input: IrisInput): Promise<IrisOutput> {
    const userPrompt = [
      `Date: ${input.dateUtc}`,
      `Launch day: ${input.isLaunchDay ? 'YES' : 'NO (continuity marketing)'}`,
      `Gumroad URL: ${input.gumroadUrl ?? '(not yet available)'}`,
      '',
      'Title:',
      input.translation.title_en,
      '',
      'Subtitle:',
      input.translation.subtitle_en,
      '',
      'Preserved Japanese terms to anchor around:',
      input.translation.preserved_japanese_terms.join(', '),
      '',
      'SEO keywords:',
      input.translation.seo_keywords.join(', '),
      '',
      'First 1500 chars of the article for context:',
      input.translation.body_en_markdown.slice(0, 1500),
    ].join('\n');

    return askJson({
      tier: 'production',
      systemPrompt: SYSTEM_PROMPT,
      userPrompt,
      schema: PostsSchema,
      employeeName: this.name,
      taskId: `iris-${input.dateUtc}`,
      maxTokens: 6000,
    });
  }
}

// For publishing: add real X/Threads/etc clients later.
export interface SnsPublishResult {
  posted: number;
  failed: number;
  urls: PublishedUrls;
}
