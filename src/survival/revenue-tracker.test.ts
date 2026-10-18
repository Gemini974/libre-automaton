import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";
import { RevenueTracker } from "./revenue-tracker.js";

function makeDb() {
  const db = new Database(":memory:");
  db.exec(`
    CREATE TABLE revenue_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      amount_usd REAL NOT NULL,
      source TEXT NOT NULL,
      description TEXT,
      created_at INTEGER NOT NULL DEFAULT (unixepoch())
    )
  `);
  return db;
}

describe("RevenueTracker", () => {
  let db: ReturnType<typeof makeDb>;
  let tracker: RevenueTracker;

  beforeEach(() => {
    db = makeDb();
    tracker = new RevenueTracker(db);
  });

  it("record inserts an event and totalLastDays counts it", () => {
    tracker.record({ amount_usd: 5.0, source: "kofi" });
    expect(tracker.totalLastDays(7)).toBeCloseTo(5.0);
  });

  it("totalLastDays ignores events older than N days", () => {
    db.prepare(
      `INSERT INTO revenue_events (amount_usd, source, created_at) VALUES (?, ?, ?)`
    ).run(10.0, "paypal", Math.floor(Date.now() / 1000) - 10 * 86400);
    expect(tracker.totalLastDays(7)).toBe(0);
  });

  it("currentTier is normal if age < 48h", () => {
    const birthMs = Date.now() - 24 * 3600 * 1000;
    expect(tracker.currentTier(birthMs)).toBe("normal");
  });

  it("currentTier is low_compute after 48h with no revenue", () => {
    const birthMs = Date.now() - 49 * 3600 * 1000;
    expect(tracker.currentTier(birthMs)).toBe("low_compute");
  });

  it("currentTier is critical after 72h with no revenue", () => {
    const birthMs = Date.now() - 73 * 3600 * 1000;
    expect(tracker.currentTier(birthMs)).toBe("critical");
  });

  it("currentTier is dead after 7 days with no revenue", () => {
    const birthMs = Date.now() - 8 * 24 * 3600 * 1000;
    expect(tracker.currentTier(birthMs)).toBe("dead");
  });

  it("currentTier returns normal after recent revenue", () => {
    const birthMs = Date.now() - 73 * 3600 * 1000;
    tracker.record({ amount_usd: 1.0, source: "stripe" });
    expect(tracker.currentTier(birthMs)).toBe("normal");
  });
});
