#!/usr/bin/env node
/**
 * Monthly CEO report generator. Aggregates all sales rows from the past
 * 30 days and writes a 1-page Markdown summary.
 *
 * MVP: reads sales from output/_sales/*.json (swap to Prisma later).
 *
 * Usage:
 *   npm run monthly
 */
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { config } from '../config.js';
import { Minerva, type MinervaOutput, type SalesRow } from '../employees/minerva.js';
import { logger } from '../services/logger.js';

async function loadRecentSales(days = 30): Promise<SalesRow[]> {
  const salesDir = path.join(config.output.dir, '_sales');
  try {
    const files = await fs.readdir(salesDir);
    const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
    const all: SalesRow[] = [];
    for (const f of files) {
      if (!f.endsWith('.json')) continue;
      const raw = await fs.readFile(path.join(salesDir, f), 'utf8');
      const rows: SalesRow[] = JSON.parse(raw);
      for (const r of rows) {
        if (new Date(r.sold_at).getTime() >= cutoff) all.push(r);
      }
    }
    return all;
  } catch {
    logger.warn({ salesDir }, 'No sales data found — returning empty list');
    return [];
  }
}

function formatReport(report: MinervaOutput, month: string): string {
  const lines = [
    `# 【月次】${config.brand.name} — ${month}度`,
    '',
    `📊 売上：$${report.total_revenue_usd.toFixed(2)}`,
    `👥 販売数：${report.total_sales_count}部`,
    '',
    '## 🏆 商品TOP5',
    ...report.top_products.slice(0, 5).map(
      (p, i) => `${i + 1}. ${p.product_id} — $${p.revenue_usd.toFixed(2)} (${p.count}部)`,
    ),
    '',
    '## 🌍 プラットフォーム別',
    ...Object.entries(report.by_platform).map(
      ([platform, v]) => `- ${platform}: $${v.revenue_usd.toFixed(2)} (${v.count}部)`,
    ),
    '',
    '## 📈 インサイト',
    ...(report.insights.length > 0 ? report.insights.map((i) => `- ${i}`) : ['- （特記なし）']),
    '',
    '## ⚠️ 異常',
    ...(report.anomalies.length > 0 ? report.anomalies.map((a) => `- ${a}`) : ['- なし']),
    '',
    '## ⚠️ CEO承認お願い事項',
    '_なし（全てAI内決裁完了）_',
    '',
    '---',
    'ハデスより 🌑',
  ];
  return lines.join('\n');
}

async function main() {
  const sales = await loadRecentSales(30);
  logger.info({ salesCount: sales.length }, 'Loaded sales data');

  const minerva = new Minerva();
  const today = new Date().toISOString().slice(0, 10);
  const report = await minerva.run({ sales, reportDate: today });

  const month = new Date().toISOString().slice(0, 7); // YYYY-MM
  const markdown = formatReport(report, month);

  const outDir = path.join(config.output.dir, '_monthly');
  await fs.mkdir(outDir, { recursive: true });
  const outFile = path.join(outDir, `${month}.md`);
  await fs.writeFile(outFile, markdown, 'utf8');

  logger.info({ outFile }, '✨ Monthly CEO report generated');
  console.log('\n' + markdown + '\n');
}

main().catch((err) => {
  logger.error({ err: err instanceof Error ? err.stack : err }, 'Fatal error');
  process.exit(1);
});
