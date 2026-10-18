import { describe, it, expect } from "vitest";
import { parsePaymentWebhookBody, isValidPaymentSource } from "./payment.js";

describe("parsePaymentWebhookBody", () => {
  it("parses a valid Ko-fi payment", () => {
    const result = parsePaymentWebhookBody({
      amount: "5.00",
      source: "kofi",
      description: "Tip",
    });
    expect(result).toEqual({ amount_usd: 5.0, source: "kofi", description: "Tip" });
  });

  it("returns null if amount <= 0", () => {
    expect(parsePaymentWebhookBody({ amount: "0", source: "kofi" })).toBeNull();
  });

  it("returns null if source is invalid", () => {
    expect(parsePaymentWebhookBody({ amount: "5", source: "bitcoin" })).toBeNull();
  });

  it("returns null if amount is non-numeric", () => {
    expect(parsePaymentWebhookBody({ amount: "abc", source: "kofi" })).toBeNull();
  });
});

describe("isValidPaymentSource", () => {
  it("accepts kofi, paypal, stripe, onchain", () => {
    for (const s of ["kofi", "paypal", "stripe", "onchain"]) {
      expect(isValidPaymentSource(s)).toBe(true);
    }
  });

  it("rejects unknown values", () => {
    expect(isValidPaymentSource("bitcoin")).toBe(false);
  });
});
