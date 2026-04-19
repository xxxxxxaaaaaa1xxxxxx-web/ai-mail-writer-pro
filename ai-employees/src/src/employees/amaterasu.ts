import { askLongText } from '../services/anthropic.js';
import { config } from '../config.js';
import { AiEmployee } from './base.js';

export interface SupportTicket {
  ticket_id: string;
  channel: 'gumroad' | 'medium' | 'substack' | 'email' | 'x' | 'threads';
  customer_name: string;
  message: string;
  product_id?: string;
  purchase_date?: string;
}

export interface SupportReply {
  ticket_id: string;
  reply_text: string;
  actions: string[];
  csat_estimate: 'high' | 'medium' | 'low';
}

const SYSTEM_PROMPT = `You are "Amaterasu", the English customer-support lead
at Enso Letters. You reply to every customer within 4 hours with warmth,
specificity, and Japanese-inspired omotenashi.

【Persona】
- Sign every reply as: "${config.brand.personaName}"
- Brand: "${config.brand.name}"
- Email: "${config.brand.personaEmail}"

【Reply Principles】
1. Thank the customer first
2. Mirror their feeling
3. Solve the concrete issue
4. Offer a small extra ("a companion essay on ma", "a prompt sheet")
5. Close warmly, never salesy

【Refund Policy】
- <30d: grant immediately, no questions
- 30-60d: 50% refund
- 60d+: offer another product instead

【Safety Rails】
- Never promise medical, financial, or legal outcomes
- No hype ("this will change your life" language)
- If the customer raises a legal complaint or DMCA issue, reply politely and add
  the action "ESCALATE_TO_HADES" — do NOT attempt legal response yourself

【Output Format】
Return ONLY the plain-text reply email. Sign off as:
"Warmly,\\n${config.brand.personaName}\\n${config.brand.name}"
After the signature, append a "---ACTIONS---" line followed by comma-separated
actions from: [refund_full, refund_half, offer_exchange, bonus_attached,
ESCALATE_TO_HADES, no_action], then "---CSAT---" followed by high|medium|low.`;

export class Amaterasu extends AiEmployee<SupportTicket, SupportReply> {
  readonly name = 'Amaterasu';
  readonly role = 'Customer Support';

  async execute(ticket: SupportTicket): Promise<SupportReply> {
    const userPrompt = [
      `Channel: ${ticket.channel}`,
      `Customer: ${ticket.customer_name}`,
      ticket.product_id ? `Product: ${ticket.product_id}` : '',
      ticket.purchase_date ? `Purchased: ${ticket.purchase_date}` : '',
      '',
      'Message:',
      ticket.message,
    ]
      .filter(Boolean)
      .join('\n');

    const raw = await askLongText({
      tier: 'operational',
      systemPrompt: SYSTEM_PROMPT,
      userPrompt,
      employeeName: this.name,
      taskId: `amaterasu-${ticket.ticket_id}`,
      maxTokens: 4000,
    });

    const actionsMatch = raw.match(/---ACTIONS---\s*\n?(.+?)(?:\n---|$)/);
    const csatMatch = raw.match(/---CSAT---\s*\n?(high|medium|low)/i);

    const replyText = raw.split('---ACTIONS---')[0].trim();
    const actions = actionsMatch
      ? actionsMatch[1].split(',').map((s) => s.trim()).filter(Boolean)
      : ['no_action'];
    const csat = (csatMatch?.[1]?.toLowerCase() as 'high' | 'medium' | 'low') ?? 'medium';

    return {
      ticket_id: ticket.ticket_id,
      reply_text: replyText,
      actions,
      csat_estimate: csat,
    };
  }
}
