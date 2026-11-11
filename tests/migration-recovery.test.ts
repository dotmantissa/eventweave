import { expect, it, vi } from "vitest";
vi.mock("../apps/api/src/db.js", () => ({ sql: vi.fn() }));
import { applyMigrations } from "../scripts/migrations";

it("skips applied schema changes after unsigned drafts share a nonce", async () => {
  const versions = new Set<number>();
  const state = { uniqueNonce: false, duplicateDrafts: false };
  const queries: string[] = [];
  const database = {
    query: (query: string) => {
      if (query.startsWith("CREATE TABLE IF NOT EXISTS schema_migrations"))
        return Promise.resolve([]);
      if (query === "SELECT version FROM schema_migrations")
        return Promise.resolve([...versions].map((version) => ({ version })));
      return query;
    },
    transaction: async (statements: string[]) => {
      for (const statement of await Promise.all(statements)) {
        if (typeof statement !== "string") continue;
        queries.push(statement);
        if (
          statement.includes(
            "CREATE UNIQUE INDEX IF NOT EXISTS operation_journal_nonce",
          )
        ) {
          if (state.duplicateDrafts)
            throw new Error("Duplicate nonce violates obsolete index");
          state.uniqueNonce = true;
        }
        if (statement.includes("DROP INDEX IF EXISTS operation_journal_nonce"))
          state.uniqueNonce = false;
        const version = statement.match(
          /INSERT INTO schema_migrations\(version\) VALUES \((\d+)\)/,
        )?.[1];
        if (version) versions.add(Number(version));
      }
    },
  };
  const completed = await applyMigrations(
    database as unknown as Parameters<typeof applyMigrations>[0],
  );
  expect(completed).toHaveLength(3);
  expect(state.uniqueNonce).toBe(false);
  state.duplicateDrafts = true;
  const count = queries.length;
  await expect(
    applyMigrations(
      database as unknown as Parameters<typeof applyMigrations>[0],
    ),
  ).resolves.toEqual([]);
  expect(queries).toHaveLength(count);
});
