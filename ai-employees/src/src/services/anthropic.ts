import Anthropic from '@anthropic-ai/sdk';
import { z } from 'zod';
import { config } from '../config.js';
import { logger } from './logger.js';

const client = new Anthropic({ apiKey: config.anthropicApiKey });

export type Tier = 'strategic' | 'production' | 'operational';

function modelFor(tier: Tier): string {
  switch (tier) {
    case 'strategic':
      return config.models.strategic;
    case 'production':
      return config.models.production;
    case 'operational':
      return config.models.operational;
  }
}

/**
 * Build the optional parameters (thinking, effort) for a given model ID.
 * - Opus 4.7 / Opus 4.6 / Sonnet 4.6 support adaptive thinking + effort
 * - Haiku 4.5 supports neither (would 400 if we send them)
 */
function modelFeatures(modelId: string, tier: Tier): {
  thinking?: { type: 'adaptive' };
  output_config?: { effort: 'low' | 'medium' | 'high' | 'max' };
} {
  const supportsThinking =
    modelId.startsWith('claude-opus-4-') || modelId.startsWith('claude-sonnet-4-6');
  const supportsEffort = supportsThinking; // same model set

  if (!supportsThinking && !supportsEffort) return {};

  const effort =
    tier === 'strategic' ? ('high' as const) : ('medium' as const);

  return {
    ...(supportsThinking ? { thinking: { type: 'adaptive' as const } } : {}),
    ...(supportsEffort ? { output_config: { effort } } : {}),
  };
}

export interface AskJsonOptions<T> {
  tier: Tier;
  systemPrompt: string;
  userPrompt: string;
  schema: z.ZodSchema<T>;
  maxTokens?: number;
  employeeName: string;
  taskId: string;
}

/**
 * Call Claude with a cached system prompt and a user prompt, parse the
 * response as JSON, and validate against the provided Zod schema.
 *
 * Prompt caching: the system prompt carries cache_control: ephemeral so
 * repeated calls with the same system prompt are ~90% cheaper after the
 * first write.
 */
export async function askJson<T>(opts: AskJsonOptions<T>): Promise<T> {
  const model = modelFor(opts.tier);
  const features = modelFeatures(model, opts.tier);

  logger.info(
    {
      employee: opts.employeeName,
      task: opts.taskId,
      model,
      effort: features.output_config?.effort,
    },
    'Invoking Claude',
  );

  const response = await client.messages.create({
    model,
    max_tokens: opts.maxTokens ?? 16000,
    ...features,
    system: [
      {
        type: 'text',
        text: opts.systemPrompt,
        cache_control: { type: 'ephemeral' },
      },
    ],
    messages: [
      {
        role: 'user',
        content: `${opts.userPrompt}\n\nIMPORTANT: Reply with ONLY a single JSON object, no prose before or after, no markdown fences.`,
      },
    ],
  });

  logger.info(
    {
      employee: opts.employeeName,
      task: opts.taskId,
      usage: {
        input: response.usage.input_tokens,
        output: response.usage.output_tokens,
        cache_read: response.usage.cache_read_input_tokens,
        cache_create: response.usage.cache_creation_input_tokens,
      },
    },
    'Claude response received',
  );

  const textBlock = response.content.find((b) => b.type === 'text');
  if (!textBlock || textBlock.type !== 'text') {
    throw new Error(`${opts.employeeName}: Claude returned no text block`);
  }

  const raw = textBlock.text.trim();
  // Strip ```json ... ``` fences if the model added them despite instructions
  const cleaned = raw
    .replace(/^```(?:json)?\s*\n?/, '')
    .replace(/\n?```$/, '')
    .trim();

  let parsed: unknown;
  try {
    parsed = JSON.parse(cleaned);
  } catch {
    logger.error({ raw: cleaned.slice(0, 500) }, 'JSON parse failed');
    throw new Error(`${opts.employeeName}: invalid JSON from Claude`);
  }

  const result = opts.schema.safeParse(parsed);
  if (!result.success) {
    logger.error({ issues: result.error.issues }, 'Schema validation failed');
    throw new Error(
      `${opts.employeeName}: output failed schema validation — ${result.error.message}`,
    );
  }

  return result.data;
}

export interface AskLongTextOptions {
  tier: Tier;
  systemPrompt: string;
  userPrompt: string;
  maxTokens?: number;
  employeeName: string;
  taskId: string;
}

/**
 * Call Claude expecting long-form Markdown output. Streams the response to
 * avoid SDK HTTP timeouts on large max_tokens values, then collects the
 * final Message via stream.finalMessage().
 */
export async function askLongText(opts: AskLongTextOptions): Promise<string> {
  const model = modelFor(opts.tier);
  const features = modelFeatures(model, opts.tier);

  logger.info(
    { employee: opts.employeeName, task: opts.taskId, model },
    'Invoking Claude (streaming)',
  );

  const stream = client.messages.stream({
    model,
    max_tokens: opts.maxTokens ?? 32000,
    ...features,
    system: [
      {
        type: 'text',
        text: opts.systemPrompt,
        cache_control: { type: 'ephemeral' },
      },
    ],
    messages: [{ role: 'user', content: opts.userPrompt }],
  });

  const finalMessage = await stream.finalMessage();

  logger.info(
    {
      employee: opts.employeeName,
      task: opts.taskId,
      usage: {
        input: finalMessage.usage.input_tokens,
        output: finalMessage.usage.output_tokens,
        cache_read: finalMessage.usage.cache_read_input_tokens,
      },
    },
    'Claude streaming response completed',
  );

  const texts = finalMessage.content
    .filter((b): b is Anthropic.TextBlock => b.type === 'text')
    .map((b) => b.text);

  if (texts.length === 0) {
    throw new Error(`${opts.employeeName}: Claude returned no text blocks`);
  }

  return texts.join('\n\n');
}
