import { Cronos } from '../src/employees/cronos.js';

async function main() {
  const cronos = new Cronos();
  const result = await cronos.run({
    products: [
      {
        product_id: 'danshari-7days',
        current_price: 29,
        pv_24h: 50,
        sales_24h: 3,
        pv_30d: 300,
        sales_30d: 20, // CVR = 6.67% → raise
        weeks_since_launch: 8,
      },
      {
        product_id: 'renai-comm',
        current_price: 29,
        pv_24h: 20,
        sales_24h: 0,
        pv_30d: 200,
        sales_30d: 1, // CVR = 0.5% → lower
        weeks_since_launch: 4,
      },
      {
        product_id: 'dead-topic',
        current_price: 29,
        pv_24h: 0,
        sales_24h: 0,
        pv_30d: 10,
        sales_30d: 0, // retire
        weeks_since_launch: 4,
      },
    ],
  });
  console.log(JSON.stringify(result, null, 2));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
