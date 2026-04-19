import { z } from 'zod';

// ========== Apollo (Genre Strategist) ==========
export const TopicSchema = z.object({
  topic_id: z.string(),
  title_jp_draft: z.string(),
  title_en_seed: z.string(),
  concept_keyword: z.string(),
  target_persona: z.string(),
  selling_angle: z.string(),
  target_price: z.number().int().min(9).max(99),
  expected_sales_first_week: z.number().int().min(0),
  platform_priority: z.array(z.string()),
  competitor_avg_price: z.number().int().optional(),
  expected_word_count_jp: z.number().int().min(3000).max(12000),
  deadline_jp_draft: z.string(),
});
export type Topic = z.infer<typeof TopicSchema>;

export const ApolloOutputSchema = z.object({
  week: z.string(),
  selected_topics: z.array(TopicSchema).length(3),
  rationale: z.string(),
  deprecated_topics: z.array(z.string()),
});
export type ApolloOutput = z.infer<typeof ApolloOutputSchema>;

// ========== Musashi (JP Writer) ==========
export const MusashiOutputSchema = z.object({
  topic_id: z.string(),
  draft_id: z.string(),
  title_jp: z.string(),
  body_jp_markdown: z.string(),
  word_count: z.number().int(),
  translation_notes: z.array(z.string()),
  key_concepts_to_keep_japanese: z.array(z.string()),
  completed_at: z.string(),
});
export type MusashiOutput = z.infer<typeof MusashiOutputSchema>;

// ========== Hermes (Translator) ==========
export const HermesOutputSchema = z.object({
  topic_id: z.string(),
  translation_id: z.string(),
  title_en: z.string(),
  subtitle_en: z.string(),
  body_en_markdown: z.string(),
  word_count_en: z.number().int(),
  preserved_japanese_terms: z.array(z.string()),
  seo_keywords: z.array(z.string()),
  cultural_footnotes_added: z.number().int(),
  completed_at: z.string(),
});
export type HermesOutput = z.infer<typeof HermesOutputSchema>;

// ========== Carmen (Copywriter) ==========
export const GumroadPackageSchema = z.object({
  title: z.string(),
  subtitle: z.string(),
  lp_copy_markdown: z.string(),
  preview_excerpt: z.string(),
  cta: z.string(),
  tags: z.array(z.string()).max(5),
});

export const MediumPackageSchema = z.object({
  title: z.string(),
  subtitle: z.string(),
  publication_target: z.string(),
  tags: z.array(z.string()).max(5),
  paywall_position: z.string(),
  cta_to_gumroad: z.string(),
});

export const SubstackPackageSchema = z.object({
  title: z.string(),
  subtitle: z.string(),
  free_preview_ratio: z.number().min(0.1).max(0.5),
  cta: z.string(),
});

export const CarmenOutputSchema = z.object({
  topic_id: z.string(),
  package_id: z.string(),
  platforms: z.object({
    gumroad: GumroadPackageSchema,
    medium: MediumPackageSchema,
    substack: SubstackPackageSchema,
  }),
  image_generation_prompt: z.string(),
  completed_at: z.string(),
});
export type CarmenOutput = z.infer<typeof CarmenOutputSchema>;

// ========== Athena (Researcher) ==========
export const AthenaOutputSchema = z.object({
  report_id: z.string(),
  scan_date: z.string(),
  trending_concepts: z.array(z.object({
    concept: z.string(),
    english_volume_change: z.string(),
    evidence_urls: z.array(z.string()),
    demand_signal: z.enum(['HIGH', 'MEDIUM', 'LOW']),
    monetization_potential: z.number().min(1).max(10),
  })),
  top_competitors: z.array(z.object({
    creator: z.string(),
    platform: z.string(),
    best_seller: z.string(),
    estimated_monthly_sales_usd: z.number().optional(),
    price: z.number(),
  })),
  market_gaps: z.array(z.string()),
  recommended_focus_for_apollo: z.array(z.string()),
});
export type AthenaOutput = z.infer<typeof AthenaOutputSchema>;

// ========== Publication ==========
export interface PublishedUrls {
  gumroad?: string;
  medium?: string;
  substack?: string;
  [key: string]: string | undefined;
}
