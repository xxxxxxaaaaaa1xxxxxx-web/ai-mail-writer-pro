import { AiEmployee } from './base.js';
import { logger } from '../services/logger.js';

export interface SalesRow {
  product_id: string;
  platform: string;
  price_usd: number;
  sold_at: string;
  customer_country?: string;
}

export interface MinervaInput {
  sales: SalesRow[];
  reportDate: string; // ISO date
}

export interface MinervaOutput {
  report_id: string;
  total_revenue_usd: number;
  total_sales_count: number;
  by_platform: Record<string, { count: number; revenue_usd: number }>;
  by_country: Record<string, number>;
  top_products: Array<{ product_id: string; revenue_usd: number; count: number }>;
  anomalies: string[];
  insights: string[];
}

/**
 * Deterministic daily rollup. No LLM needed for aggregation; LLM can be layered
 * on top later for narrative summaries, but the primitive stays fast and cheap.
 */
export class Minerva extends AiEmployee<MinervaInput, MinervaOutput> {
  readonly name = 'Minerva';
  readonly role = 'Data Analyst';

  async execute(input: MinervaInput): Promise<MinervaOutput> {
    const byPlatform: Record<string, { count: number; revenue_usd: number }> = {};
    const byCountry: Record<string, number> = {};
    const byProduct: Record<string, { revenue_usd: number; count: number }> = {};

    let totalRevenue = 0;
    let totalCount = 0;

    for (const s of input.sales) {
      totalRevenue += s.price_usd;
      totalCount += 1;

      const p = (byPlatform[s.platform] ??= { count: 0, revenue_usd: 0 });
      p.count += 1;
      p.revenue_usd += s.price_usd;

      if (s.customer_country) {
        byCountry[s.customer_country] = (byCountry[s.customer_country] ?? 0) + 1;
      }

      const pr = (byProduct[s.product_id] ??= { revenue_usd: 0, count: 0 });
      pr.revenue_usd += s.price_usd;
      pr.count += 1;
    }

    const topProducts = Object.entries(byProduct)
      .map(([product_id, v]) => ({ product_id, ...v }))
      .sort((a, b) => b.revenue_usd - a.revenue_usd)
      .slice(0, 10);

    const anomalies: string[] = [];
    const insights: string[] = [];

    if (totalCount === 0) {
      anomalies.push('今日の売上ゼロ — 要調査');
    }
    if (totalCount > 0 && totalRevenue / totalCount > 40) {
      insights.push(`平均単価が$${(totalRevenue / totalCount).toFixed(2)} — 高単価戦略が効いている`);
    }

    const gumroadShare =
      (byPlatform.gumroad?.revenue_usd ?? 0) / (totalRevenue || 1);
    if (gumroadShare < 0.4 && totalRevenue > 100) {
      insights.push(
        `Gumroadシェアが${(gumroadShare * 100).toFixed(0)}% — 他PFが伸びている（好機）`,
      );
    }

    logger.info(
      {
        employee: this.name,
        revenue_usd: totalRevenue.toFixed(2),
        sales_count: totalCount,
      },
      'Minerva daily rollup complete',
    );

    return {
      report_id: `MIN-DAILY-${input.reportDate}`,
      total_revenue_usd: Number(totalRevenue.toFixed(2)),
      total_sales_count: totalCount,
      by_platform: byPlatform,
      by_country: byCountry,
      top_products: topProducts,
      anomalies,
      insights,
    };
  }
}
