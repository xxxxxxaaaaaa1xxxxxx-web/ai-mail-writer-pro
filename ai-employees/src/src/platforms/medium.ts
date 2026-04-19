import { config } from '../config.js';
import { logger } from '../services/logger.js';

export interface MediumPublishInput {
  title: string;
  subtitle: string;
  bodyMarkdown: string;
  tags: string[];
  publication?: string;
  gumroadCta?: string;
  gumroadUrl?: string;
}

export interface MediumPublishResult {
  url: string;
  postId: string;
  dryRun: boolean;
}

/**
 * Thin Medium client. Runs in DRY-RUN mode unless MEDIUM_INTEGRATION_TOKEN
 * is set.
 *
 * Medium API: https://github.com/Medium/medium-api-docs
 *
 * To publish:
 *   1. GET https://api.medium.com/v1/me  → user.id
 *   2. POST https://api.medium.com/v1/users/{id}/posts
 *      headers: Authorization: Bearer {token}
 *      body: { title, contentFormat: "markdown", content, tags, publishStatus }
 *
 * Note: Medium's API does NOT support posting to a publication you don't own
 * directly. For "Better Humans" / "The Ascent" etc., submit via email to the
 * publication editor (out of scope for MVP).
 */
export class MediumClient {
  async publish(input: MediumPublishInput): Promise<MediumPublishResult> {
    if (!config.platforms.mediumToken) {
      logger.info({ platform: 'medium', dryRun: true }, 'Medium DRY-RUN');
      const slug = input.title
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
        .slice(0, 60);
      return {
        url: `https://medium.com/@ensoletters/${slug}`,
        postId: `dryrun-${Date.now()}`,
        dryRun: true,
      };
    }

    // Append Gumroad CTA at the end if provided
    const content = input.gumroadUrl
      ? `${input.bodyMarkdown}\n\n---\n\n**${input.gumroadCta ?? 'Read the full guide'}** → [${input.gumroadUrl}](${input.gumroadUrl})`
      : input.bodyMarkdown;

    // TODO: real publish
    throw new Error('Medium publish not yet implemented');
  }
}
