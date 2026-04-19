import 'dotenv/config';

function required(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required env var: ${name}`);
  return v;
}

function optional(name: string, fallback = ''): string {
  return process.env[name] ?? fallback;
}

export const config = {
  anthropicApiKey: required('ANTHROPIC_API_KEY'),

  models: {
    strategic: optional('MODEL_STRATEGIC', 'claude-opus-4-7'),
    production: optional('MODEL_PRODUCTION', 'claude-sonnet-4-6'),
    operational: optional('MODEL_OPERATIONAL', 'claude-haiku-4-5'),
  },

  brand: {
    name: optional('BRAND_NAME', 'Enso Letters'),
    domain: optional('BRAND_DOMAIN', 'ensoletters.com'),
    personaName: optional('PERSONA_NAME', 'Haru Koyama'),
    personaEmail: optional('PERSONA_EMAIL', 'haru@ensoletters.com'),
  },

  output: {
    dir: optional('OUTPUT_DIR', './output'),
  },

  deepl: {
    apiKey: optional('DEEPL_API_KEY'),
  },

  openai: {
    apiKey: optional('OPENAI_API_KEY'),
  },

  platforms: {
    gumroadToken: optional('GUMROAD_ACCESS_TOKEN'),
    mediumToken: optional('MEDIUM_INTEGRATION_TOKEN'),
    substackCookie: optional('SUBSTACK_SESSION_COOKIE'),
  },

  notifications: {
    ceoEmail: optional('CEO_EMAIL'),
    ceoSlackWebhook: optional('CEO_SLACK_WEBHOOK'),
  },
} as const;

export type AppConfig = typeof config;
