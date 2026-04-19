import { config } from '../config.js';
import { logger } from '../services/logger.js';
import { AiEmployee } from './base.js';

export type EscalationLevel = 'INTERNAL' | 'MONTHLY' | 'URGENT';

export interface EscalationEvent {
  event_type: string;
  severity?: number; // 0..1
  context: string;
  recommendation: string;
}

export interface EscalationDecision {
  level: EscalationLevel;
  should_notify_ceo: boolean;
  reason: string;
}

/**
 * Hades is the AI CEO/dispatcher. This first pass exposes only the
 * escalation-rules engine — the most load-bearing piece. Workflow-level
 * orchestration lives in src/workflows/*, and each workflow reports back
 * through Hades so the CEO sees one notification per incident max.
 */
export class Hades extends AiEmployee<EscalationEvent, EscalationDecision> {
  readonly name = 'Hades';
  readonly role = 'AI CEO / Dispatcher';

  async execute(event: EscalationEvent): Promise<EscalationDecision> {
    const d = this.classify(event);

    if (d.should_notify_ceo) {
      await this.notifyCeo(event, d);
    }

    return d;
  }

  private classify(event: EscalationEvent): EscalationDecision {
    const urgentTypes = new Set([
      'dmca_notice',
      'legal_notice',
      'account_ban',
      'data_breach',
      'payment_failure',
      'ethical_complaint',
    ]);
    if (urgentTypes.has(event.event_type)) {
      return {
        level: 'URGENT',
        should_notify_ceo: true,
        reason: '法務・運用クリティカル事象 — 即時CEO通知',
      };
    }

    if (event.event_type === 'revenue_drop' && (event.severity ?? 0) > 0.3) {
      return {
        level: 'URGENT',
        should_notify_ceo: true,
        reason: `売上が前月比${Math.round((event.severity ?? 0) * 100)}%下落 — 即時CEO通知`,
      };
    }

    const monthlyTypes = new Set([
      'new_platform_proposal',
      'new_genre_proposal',
      'model_change_proposal',
      'partnership_proposal',
      'subscription_service_proposal',
    ]);
    if (monthlyTypes.has(event.event_type)) {
      return {
        level: 'MONTHLY',
        should_notify_ceo: false, // 月次レポート内でまとめて通知
        reason: '月次レポートでCEO承認を仰ぐ',
      };
    }

    return {
      level: 'INTERNAL',
      should_notify_ceo: false,
      reason: 'ハデス内で自動判断、CEO関与不要',
    };
  }

  private async notifyCeo(
    event: EscalationEvent,
    decision: EscalationDecision,
  ): Promise<void> {
    const body = [
      `🚨 [${decision.level}] ${event.event_type}`,
      '',
      `発生：${new Date().toISOString()}`,
      `内容：${event.context}`,
      `推奨対応：${event.recommendation}`,
    ].join('\n');

    logger.warn({ event_type: event.event_type, level: decision.level }, body);

    if (config.notifications.ceoSlackWebhook) {
      try {
        await fetch(config.notifications.ceoSlackWebhook, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: body }),
        });
      } catch (err) {
        logger.error({ err }, 'Slack notification failed');
      }
    }

    // TODO: email notification via SES/Resend/Postmark when CEO_EMAIL is set
  }
}
