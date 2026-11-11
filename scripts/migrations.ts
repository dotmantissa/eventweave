import { readFile, readdir } from "node:fs/promises";
import { sql } from "../apps/api/src/db.js";

export async function applyMigrations(database = sql()) {
  await database.query(
    "CREATE TABLE IF NOT EXISTS schema_migrations (version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())",
  );
  const applied = new Set(
    (await database.query("SELECT version FROM schema_migrations")).map((row) =>
      Number(row.version),
    ),
  );
  const directory = new URL("../apps/api/migrations/", import.meta.url);
  const completed: string[] = [];
  for (const filename of (await readdir(directory))
    .filter((name) => name.endsWith(".sql"))
    .sort()) {
    const version = Number(filename.match(/^(\d+)_/)?.[1]);
    if (!Number.isSafeInteger(version) || version < 1)
      throw new Error("Invalid migration version");
    if (applied.has(version)) continue;
    const source = await readFile(new URL(filename, directory), "utf8");
    // Schema changes and their version marker commit together.
    await database.transaction(
      source
        .split(";")
        .filter((statement) => statement.trim())
        .map((statement) => database.query(statement)),
    );
    applied.add(version);
    completed.push(filename);
  }
  return completed;
}
