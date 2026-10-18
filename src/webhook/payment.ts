type PaymentSource = "kofi" | "paypal" | "stripe" | "onchain";

export interface NewRevenueEvent {
  amount_usd: number;
  source: PaymentSource;
  description?: string;
}

/** Minimal interface — fulfilled by RevenueTracker from revenue-tracker.ts */
export interface RevenueRecorder {
  record(event: NewRevenueEvent): void;
}

export function isValidPaymentSource(s: unknown): s is PaymentSource {
  return ["kofi", "paypal", "stripe", "onchain"].includes(s as string);
}

export function parsePaymentWebhookBody(
  body: Record<string, unknown>,
): NewRevenueEvent | null {
  const amount = parseFloat(String(body.amount ?? "0"));
  if (!isFinite(amount) || amount <= 0) return null;
  if (!isValidPaymentSource(body.source)) return null;

  return {
    amount_usd: amount,
    source: body.source,
    description: typeof body.description === "string" ? body.description : undefined,
  };
}

/**
 * Handle an incoming payment webhook. Framework-agnostic — caller reads body and sends response.
 */
export function handlePaymentWebhook(
  body: Record<string, unknown>,
  recorder: RevenueRecorder,
  secret?: string,
  providedSecret?: string,
): { ok: boolean; status: 200 | 400; message: string } {
  if (secret && providedSecret !== secret) {
    return { ok: false, status: 400, message: "invalid signature" };
  }

  const event = parsePaymentWebhookBody(body);
  if (!event) {
    return { ok: false, status: 400, message: "invalid payload" };
  }

  recorder.record(event);
  return { ok: true, status: 200, message: "recorded" };
}
