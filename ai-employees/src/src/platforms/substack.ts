import { config } from '../config.js';
import { logger } from '../services/logger.js';

export interface SubstackPublishInput {
  title: string;
  subtitle: string;
  bodyMarkdown: string;
  freePreviewRatio: number;
  cta: string;
}

export interface SubstackPublishResult {
  url: string;
  postId: string;
  dryRun: boolean;
}

/**
 * Substack has no official public API for publishing as of 2026. Real usage
 * requires either:
 *   1. Browser automation (Playwright) against https://substack.com/publish
 *      with an authenticated SUBSTACK_SESSION_COOKIE; or
 *   2. Manual export to Substack's import tool.
 *
 * This client runs in DRY-RUN until one of those integrations is added.
 */
export class SubstackClient {
  async publish(input: SubstackPublishInput): Promise<SubstackPublishResult> {
    if (!config.platforms.substackCookie) {
      logger.info({ platform: 'substack', dryRun: true }, 'Substack DRY-RUN');
      const slug = input.title
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
        .slice(0, 60);
      return {
        url: `https://ensoletters.substack.com/p/${slug}`,
        postId: `dryrun-${Date.now()}`,
        dryRun: true,
      };
    }

    // TODO: implement Playwright-driven publish flow using SUBSTACK_SESSION_COOKIE
    throw new Error('Substack publish not yet implemented — Playwright flow required');
  }
}
