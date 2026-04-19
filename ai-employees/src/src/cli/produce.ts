#!/usr/bin/env node
/**
 * Daily production CLI.
 *
 * Usage:
 *   npm run produce                 # produce 3 topics for the current week (dry-run publish)
 *   npm run produce -- --limit 1    # produce just 1 topic (fastest smoke test)
 *   npm run produce -- --publish    # actually publish to platforms (requires tokens)
 *   npm run produce -- --week 2026-W16
 */
import { runDailyWorkflow } from '../workflows/daily.js';
import { logger } from '../services/logger.js';

function parseArgs(argv: string[]): {
  week?: string;
  limit?: number;
  dryRun: boolean;
} {
  const out: { week?: string; limit?: number; dryRun: boolean } = { dryRun: true };

  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--week' && argv[i + 1]) {
      out.week = argv[++i];
    } else if (a === '--limit' && argv[i + 1]) {
      out.limit = parseInt(argv[++i], 10);
    } else if (a === '--publish') {
      out.dryRun = false;
    }
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  logger.info({ args }, 'Enso Letters — daily production');

  const result = await runDailyWorkflow(args);

  logger.info(
    {
      week: result.week,
      produced: result.producedTopicIds,
      errors: result.errors,
    },
    '✨ Daily run finished',
  );

  if (result.errors.length > 0) {
    process.exit(1);
  }
}

main().catch((err) => {
  logger.error({ err: err instanceof Error ? err.stack : err }, 'Fatal error');
  process.exit(1);
});
