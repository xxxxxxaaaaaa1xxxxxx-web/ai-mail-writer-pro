import pino from 'pino';

// Simple JSON logger. For pretty output in dev: npm i -D pino-pretty && pipe
// through `node dist/cli/produce.js | pino-pretty`.
export const logger = pino({
  level: process.env.LOG_LEVEL ?? 'info',
});
