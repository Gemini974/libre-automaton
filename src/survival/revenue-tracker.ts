import type Database from "better-sqlite3";
import type { SurvivalTier } from "../types.js";

export interface NewRevenueEvent {
  amount_usd: number;
  source: "kofi" | "paypal" | "stripe" | "onchain";
  description?: string;
}

const HOURS_LOW_COMPUTE = 48;
const HOURS_CRITICAL = 72;
const HOURS_DEAD = 7 * 24;

export class RevenueTracker {
  constructor(private readonly db: Database.Database) {}

  record(event: NewRevenueEvent): void {
    this.db
      .prepare(
        `INSERT INTO revenue_events (amount_usd, source, description)
         VALUES (@amount_usd, @source, @description)`
      )
      .run({ description: null, ...event });
  }

  totalLastDays(days: number): number {
    const since = Math.floor(Date.now() / 1000) - days * 86400;
    const row = this.db
      .prepare(
        `SELECT COALESCE(SUM(amount_usd), 0) as total
         FROM revenue_events WHERE created_at >= ?`
      )
      .get(since) as { total: number };
    return row.total;
  }

  currentTier(ageBirthMs: number): SurvivalTier {
    const ageHours = (Date.now() - ageBirthMs) / 3_600_000;
    const recentRevenue = this.totalLastDays(7);

    if (recentRevenue > 0 || ageHours < HOURS_LOW_COMPUTE) return "normal";
    if (ageHours < HOURS_CRITICAL) return "low_compute";
    if (ageHours < HOURS_DEAD) return "critical";
    return "dead";
  }
}
