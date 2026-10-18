import { defineConfig } from "vitest/config";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      // On Windows without VS C++ build tools, better-sqlite3 can't compile its
      // native module. Use the node:sqlite built-in (Node 24) as a drop-in for tests.
      "better-sqlite3": path.resolve(__dirname, "src/__mocks__/better-sqlite3.ts"),
    },
  },
  test: {
    testTimeout: 30_000,
    teardownTimeout: 5_000,
    include: ["src/**/*.test.ts", "src/__tests__/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.ts"],
      exclude: [
        "src/__tests__/**",
        "src/types.ts",
        "node_modules/**",
      ],
      thresholds: {
        statements: 60,
        branches: 50,
        functions: 55,
        lines: 60,
      },
      reporter: ["text", "text-summary", "json-summary"],
    },
  },
});
