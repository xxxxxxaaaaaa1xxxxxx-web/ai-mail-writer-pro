import { config } from '../config.js';
import { logger } from '../services/logger.js';

export interface GumroadPublishInput {
  title: string;
  description: string;
  priceCents: number;
  tags: string[];
  bodyMarkdown: string;
}

export interface GumroadPublishResult {
  url: string;
  productId: string;
  dryRun: boolean;
}

/**
 * Thin Gumroad client. Runs in DRY-RUN mode unless GUMROAD_ACCESS_TOKEN is set.
 * API reference: https://app.gumroad.com/api
 *
 * When GUMROAD_ACCESS_TOKEN is set, swap the dry-run block for:
 *   POST https://api.gumroad.com/v2/products
 *     headers: Authorization: Bearer {token}
 *     body: { name, price, description, tags, ... }
 *
 * Publishing a PDF additionally requires:
 *   POST /v2/products/{id}/variants  (for file upload)
 */
export class GumroadClient {
  async publish(input: GumroadPublishInput): Promise<GumroadPublishResult> {
    if (!config.platforms.gumroadToken) {
      logger.info({ platform: 'gumroad', dryRun: true }, 'Gumroad DRY-RUN');
      const slug = input.title
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
        .slice(0, 40);
      return {
        url: `https://ensoletters.gumroad.com/l/${slug}`,
        productId: `dryrun-${Date.now()}`,
        dryRun: true,
      };
    }

    // TODO: real publish
    // const res = await fetch('https://api.gumroad.com/v2/products', {
    //   method: 'POST',
    //   headers: {
    //     Authorization: `Bearer ${config.platforms.gumroadToken}`,
    //     'Content-Type': 'application/x-www-form-urlencoded',
    //   },
    //   body: new URLSearchParams({
    //     name: input.title,
    //     price: String(input.priceCents),
    //     description: input.description,
    //     tags: input.tags.join(','),
    //   }),
    // });
    // const data = await res.json();
    // return { url: data.product.short_url, productId: data.product.id, dryRun: false };

    throw new Error('Gumroad publish not yet implemented (token is set but API call is stubbed)');
  }
}
