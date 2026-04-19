import { GumroadClient } from '../platforms/gumroad.js';
import { MediumClient } from '../platforms/medium.js';
import { SubstackClient } from '../platforms/substack.js';
import { logger } from '../services/logger.js';
import type { CarmenOutput, PublishedUrls, Topic } from '../types.js';
import { AiEmployee } from './base.js';

export interface JanusInput {
  topic: Topic;
  package: CarmenOutput;
  bodyEnMarkdown: string;
}

export interface JanusOutput {
  topic_id: string;
  publication_id: string;
  published_urls: PublishedUrls;
  publication_timestamps: Record<string, string>;
  errors: string[];
}

/**
 * Multi-platform publisher. Uses thin platform clients that currently run in
 * DRY-RUN mode until real tokens are configured. Each platform client returns
 * a placeholder URL you can later replace with the real publish call.
 */
export class Janus extends AiEmployee<JanusInput, JanusOutput> {
  readonly name = 'Janus';
  readonly role = 'Platform Operations';

  async execute(input: JanusInput): Promise<JanusOutput> {
    const urls: PublishedUrls = {};
    const timestamps: Record<string, string> = {};
    const errors: string[] = [];

    const gumroad = new GumroadClient();
    const medium = new MediumClient();
    const substack = new SubstackClient();

    try {
      const g = await gumroad.publish({
        title: input.package.platforms.gumroad.title,
        description: input.package.platforms.gumroad.lp_copy_markdown,
        priceCents: input.topic.target_price * 100,
        tags: input.package.platforms.gumroad.tags,
        bodyMarkdown: input.bodyEnMarkdown,
      });
      urls.gumroad = g.url;
      timestamps.gumroad = new Date().toISOString();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      errors.push(`gumroad: ${msg}`);
      logger.error({ err: msg }, 'Gumroad publish failed');
    }

    try {
      const m = await medium.publish({
        title: input.package.platforms.medium.title,
        subtitle: input.package.platforms.medium.subtitle,
        bodyMarkdown: input.bodyEnMarkdown,
        tags: input.package.platforms.medium.tags,
        publication: input.package.platforms.medium.publication_target,
        gumroadCta: input.package.platforms.medium.cta_to_gumroad,
        gumroadUrl: urls.gumroad,
      });
      urls.medium = m.url;
      timestamps.medium = new Date().toISOString();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      errors.push(`medium: ${msg}`);
      logger.error({ err: msg }, 'Medium publish failed');
    }

    try {
      const s = await substack.publish({
        title: input.package.platforms.substack.title,
        subtitle: input.package.platforms.substack.subtitle,
        bodyMarkdown: input.bodyEnMarkdown,
        freePreviewRatio: input.package.platforms.substack.free_preview_ratio,
        cta: input.package.platforms.substack.cta,
      });
      urls.substack = s.url;
      timestamps.substack = new Date().toISOString();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      errors.push(`substack: ${msg}`);
      logger.error({ err: msg }, 'Substack publish failed');
    }

    return {
      topic_id: input.topic.topic_id,
      publication_id: `JANUS-${input.topic.topic_id}-v1`,
      published_urls: urls,
      publication_timestamps: timestamps,
      errors,
    };
  }
}
