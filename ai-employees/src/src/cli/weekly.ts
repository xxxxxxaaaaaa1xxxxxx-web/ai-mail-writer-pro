#!/usr/bin/env node
/**
 * Weekly strategy kickoff. Runs Athena + Apollo only, writes the week's
 * "genre briefing" without starting production. Use this on Sunday night
 * before the Monday production run.
 *
 * Usage:
 *   npm run weekly
 *   npm run weekly -- --week 2026-W16
 */
import { Apollo } from '../employees/apollo.js';
import { Athena } from '../employees/athena.js';
import { logger } from '../services/logger.js';
import { Storage } from '../services/storage.js';

function currentWeekLabel(): string {
  const d = new Date();
  const jan1 = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - jan1.getTime()) / (1000 * 60 * 60 * 24));
  const week = Math.ceil((days + jan1.getDay() + 1) / 7);
  return `${d.getFullYear()}-W${String(week).padStart(2, '0')}`;
}

async function main() {
  const weekArg = process.argv.find((a) => a.startsWith('--week='))?.split('=')[1];
  const week = weekArg ?? currentWeekLabel();

  logger.info({ week }, 'Weekly strategy briefing');

  const storage = new Storage();
  const athena = new Athena();
  const apollo = new Apollo();

  const report = await athena.run({ week });
  await storage.saveJson(week, '_research', 'athena', report);

  const plan = await apollo.run({ week, athenaReport: report });
  await storage.saveJson(week, '_strategy', 'apollo', plan);

  logger.info(
    {
      week,
      topics: plan.selected_topics.map((t) => ({
        id: t.topic_id,
        concept: t.concept_keyword,
        price: t.target_price,
      })),
    },
    '✨ Weekly plan complete',
  );
}

main().catch((err) => {
  logger.error({ err: err instanceof Error ? err.stack : err }, 'Fatal error');
  process.exit(1);
});
