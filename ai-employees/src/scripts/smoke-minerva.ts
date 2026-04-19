import { Minerva } from '../src/employees/minerva.js';

async function main() {
  const minerva = new Minerva();
  const result = await minerva.run({
    reportDate: '2026-04-19',
    sales: [
      { product_id: 'danshari', platform: 'gumroad', price_usd: 29, sold_at: '2026-04-19T10:00:00Z', customer_country: 'US' },
      { product_id: 'danshari', platform: 'gumroad', price_usd: 29, sold_at: '2026-04-19T11:00:00Z', customer_country: 'US' },
      { product_id: 'zen', platform: 'gumroad', price_usd: 49, sold_at: '2026-04-19T14:00:00Z', customer_country: 'UK' },
      { product_id: 'ikigai', platform: 'medium', price_usd: 5, sold_at: '2026-04-19T18:00:00Z', customer_country: 'DE' },
      { product_id: 'kakeibo', platform: 'substack', price_usd: 5, sold_at: '2026-04-19T20:00:00Z', customer_country: 'CA' },
    ],
  });
  console.log(JSON.stringify(result, null, 2));
}

main().catch((e) => { console.error(e); process.exit(1); });
