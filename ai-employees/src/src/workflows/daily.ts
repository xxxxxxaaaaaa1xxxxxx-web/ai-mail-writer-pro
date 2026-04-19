import { Apollo } from '../employees/apollo.js';
import { Athena } from '../employees/athena.js';
import { Carmen } from '../employees/carmen.js';
import { Hades } from '../employees/hades.js';
import { Hermes } from '../employees/hermes.js';
import { Iris } from '../employees/iris.js';
import { Janus } from '../employees/janus.js';
import { Musashi } from '../employees/musashi.js';
import { logger } from '../services/logger.js';
import { Storage } from '../services/storage.js';
import type { Topic } from '../types.js';

export interface DailyRunOptions {
  /** ISO week label, e.g. "2026-W16" */
  week?: string;
  /** Limit to N topics (useful for testing). Default 3. */
  limit?: number;
  /** Skip publishing stage (just produce content). */
  dryRun?: boolean;
}

function currentWeekLabel(): string {
  const d = new Date();
  const jan1 = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor(
    (d.getTime() - jan1.getTime()) / (1000 * 60 * 60 * 24),
  );
  const week = Math.ceil((days + jan1.getDay() + 1) / 7);
  return `${d.getFullYear()}-W${String(week).padStart(2, '0')}`;
}

/**
 * End-to-end daily production pipeline:
 *   Athena → Apollo → (for each topic) Musashi → Hermes → Carmen → Janus → Iris
 *
 * All artifacts are persisted via Storage. Hades wraps errors and decides
 * whether to escalate to the CEO.
 */
export async function runDailyWorkflow(opts: DailyRunOptions = {}): Promise<{
  week: string;
  producedTopicIds: string[];
  errors: string[];
}> {
  const week = opts.week ?? currentWeekLabel();
  const storage = new Storage();
  const hades = new Hades();

  logger.info({ week, limit: opts.limit, dryRun: opts.dryRun }, 'Daily workflow starting');

  // === Stage 1: Market research (Athena) ===
  const athena = new Athena();
  const athenaReport = await athena.run({ week });
  await storage.saveJson(week, '_research', 'athena', athenaReport);

  // === Stage 2: Genre selection (Apollo) ===
  const apollo = new Apollo();
  const apolloOutput = await apollo.run({
    week,
    athenaReport,
    pastTopicsToAvoid: [], // TODO: populate from DB after first runs
  });
  await storage.saveJson(week, '_strategy', 'apollo', apolloOutput);

  const selectedTopics = apolloOutput.selected_topics.slice(0, opts.limit ?? 3);
  logger.info(
    { topics: selectedTopics.map((t) => t.concept_keyword) },
    `Apollo selected ${selectedTopics.length} topics`,
  );

  // === Stage 3-7: Per-topic production pipeline ===
  const musashi = new Musashi();
  const hermes = new Hermes();
  const carmen = new Carmen();
  const janus = new Janus();
  const iris = new Iris();

  const producedTopicIds: string[] = [];
  const errors: string[] = [];

  for (const topic of selectedTopics) {
    try {
      await produceOne(topic, week, storage, { musashi, hermes, carmen, janus, iris }, opts);
      producedTopicIds.push(topic.topic_id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      errors.push(`${topic.topic_id}: ${msg}`);
      logger.error({ topic: topic.topic_id, err: msg }, 'Topic production failed');

      await hades.run({
        event_type: 'topic_production_failure',
        context: `Topic ${topic.topic_id} (${topic.concept_keyword}) failed all retries`,
        recommendation: '翌日再実行。3日連続失敗なら該当テーマを撤退。',
      });
    }
  }

  logger.info(
    { producedCount: producedTopicIds.length, errors: errors.length },
    'Daily workflow complete',
  );

  return { week, producedTopicIds, errors };
}

async function produceOne(
  topic: Topic,
  week: string,
  storage: Storage,
  employees: {
    musashi: Musashi;
    hermes: Hermes;
    carmen: Carmen;
    janus: Janus;
    iris: Iris;
  },
  opts: DailyRunOptions,
): Promise<void> {
  logger.info({ topic: topic.topic_id }, '→ Musashi: writing Japanese draft');
  const draft = await employees.musashi.run(topic);
  await storage.saveJson(week, topic.topic_id, 'draft_musashi', draft);
  await storage.saveText(week, topic.topic_id, 'draft_jp.md', draft.body_jp_markdown);

  logger.info({ topic: topic.topic_id }, '→ Hermes: translating to English');
  const translation = await employees.hermes.run(draft);
  await storage.saveJson(week, topic.topic_id, 'translation_hermes', translation);
  await storage.saveText(week, topic.topic_id, 'body_en.md', translation.body_en_markdown);

  logger.info({ topic: topic.topic_id }, '→ Carmen: crafting sales package');
  const pkg = await employees.carmen.run({ topic, translation });
  await storage.saveJson(week, topic.topic_id, 'package_carmen', pkg);

  if (opts.dryRun) {
    logger.info({ topic: topic.topic_id }, 'Dry-run: skipping Janus + Iris');
    return;
  }

  logger.info({ topic: topic.topic_id }, '→ Janus: publishing to platforms');
  const publication = await employees.janus.run({
    topic,
    package: pkg,
    bodyEnMarkdown: translation.body_en_markdown,
  });
  await storage.saveJson(week, topic.topic_id, 'publication_janus', publication);

  logger.info({ topic: topic.topic_id }, '→ Iris: scheduling SNS posts');
  const sns = await employees.iris.run({
    dateUtc: new Date().toISOString().slice(0, 10),
    translation,
    gumroadUrl: publication.published_urls.gumroad,
    isLaunchDay: true,
  });
  await storage.saveJson(week, topic.topic_id, 'sns_iris', sns);

  logger.info({ topic: topic.topic_id }, '✓ Topic pipeline complete');
}
