// @ts-nocheck
// Shim: replaces better-sqlite3 with node:sqlite (built-in Node 24) for test environments.
// Uses createRequire to load node:sqlite lazily, preventing Vite from statically
// resolving it at transform time (Vite doesn't handle node: protocol in its bundler).
import { createRequire } from "module";

const _require = createRequire(import.meta.url);

function getSqlite() {
  return _require("node:sqlite");
}

function normalizeParams(params: unknown): unknown {
  if (params === null || params === undefined) return params;
  if (typeof params === "object" && !Array.isArray(params)) {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(params as Record<string, unknown>)) {
      out[k] = v === undefined ? null : v;
    }
    return out;
  }
  return params;
}

function wrapStmt(stmt: unknown) {
  return {
    run(...args: unknown[]) {
      if (args.length === 1 && args[0] !== null && typeof args[0] === "object" && !Array.isArray(args[0])) {
        return (stmt as any).run(normalizeParams(args[0]));
      }
      return (stmt as any).run(...args);
    },
    get(...args: unknown[]) {
      const result = args.length === 1 && args[0] !== null && typeof args[0] === "object" && !Array.isArray(args[0])
        ? (stmt as any).get(normalizeParams(args[0]))
        : (stmt as any).get(...args);
      return result ?? undefined;
    },
    all(...args: unknown[]) {
      if (args.length === 1 && args[0] !== null && typeof args[0] === "object" && !Array.isArray(args[0])) {
        return (stmt as any).all(normalizeParams(args[0]));
      }
      return (stmt as any).all(...args);
    },
  };
}

class Database {
  private _db: unknown;

  constructor(location: string) {
    const { DatabaseSync } = getSqlite();
    this._db = new DatabaseSync(location);
  }

  exec(sql: string): this {
    (this._db as any).exec(sql);
    return this;
  }

  prepare(sql: string) {
    return wrapStmt((this._db as any).prepare(sql));
  }

  close(): void {
    (this._db as any).close();
  }
}

export default Database;
