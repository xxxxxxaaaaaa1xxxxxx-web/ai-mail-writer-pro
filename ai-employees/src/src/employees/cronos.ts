import { AiEmployee } from './base.js';
import { logger } from '../services/logger.js';

export interface ProductSalesRecord {
  product_id: string;
  current_price: number;
  pv_24h: number;
  sales_24h: number;
  pv_30d: number;
  sales_30d: number;
  weeks_since_launch: number;
}

export interface PricingDecision {
  product_id: string;
  current_price: number;
  new_price: number;
  change_reason: string;
  action: 'raise' | 'lower' | 'hold' | 'retire';
}

export interface CronosInput {
  products: ProductSalesRecord[];
}

export interface CronosOutput {
  decisions: PricingDecision[];
}

/**
 * Deterministic pricing engine — no LLM needed. Implements the rules in
 * playbooks/pricing-formula.md. Runs in under 10ms for 1000 products.
 */
export class Cronos extends AiEmployee<CronosInput, CronosOutput> {
  readonly name = 'Cronos';
  readonly role = 'Pricing Strategist';

  async execute(input: CronosInput): Promise<CronosOutput> {
    const decisions: PricingDecision[] = [];

    for (const p of input.products) {
      const cvr30d = p.pv_30d > 0 ? p.sales_30d / p.pv_30d : 0;

      // Retirement criteria
      if (p.sales_30d === 0 && p.weeks_since_launch >= 3) {
        decisions.push({
          product_id: p.product_id,
          current_price: p.current_price,
          new_price: p.current_price,
          change_reason: '3週間以上売上ゼロ — 非公開＋リブランド検討をアポロンへ',
          action: 'retire',
        });
        continue;
      }

      // Raise price: strong CVR
      if (cvr30d >= 0.05 && p.current_price < 49) {
        const newPrice = Math.min(p.current_price + 10, 49);
        decisions.push({
          product_id: p.product_id,
          current_price: p.current_price,
          new_price: newPrice,
          change_reason: `CVR ${(cvr30d * 100).toFixed(2)}% は健全、$${newPrice}へ値上げテスト`,
          action: 'raise',
        });
        continue;
      }

      // Lower price: poor CVR with enough traffic
      if (cvr30d < 0.01 && p.pv_30d > 100 && p.current_price > 19) {
        const newPrice = Math.max(p.current_price - 10, 19);
        decisions.push({
          product_id: p.product_id,
          current_price: p.current_price,
          new_price: newPrice,
          change_reason: `CVR ${(cvr30d * 100).toFixed(2)}% 低迷、$${newPrice}へ値下げテスト`,
          action: 'lower',
        });
        continue;
      }

      decisions.push({
        product_id: p.product_id,
        current_price: p.current_price,
        new_price: p.current_price,
        change_reason: '価格は現状維持が最適',
        action: 'hold',
      });
    }

    logger.info(
      {
        employee: this.name,
        total: decisions.length,
        raised: decisions.filter((d) => d.action === 'raise').length,
        lowered: decisions.filter((d) => d.action === 'lower').length,
        retired: decisions.filter((d) => d.action === 'retire').length,
      },
      'Cronos pricing decisions computed',
    );

    return { decisions };
  }
}
