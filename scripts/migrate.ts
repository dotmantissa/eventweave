import "dotenv/config";
import { readFile, readdir } from "node:fs/promises";
import { sql } from "../apps/api/src/db";
try {
  const directory = new URL("../apps/api/migrations/", import.meta.url);
  for (const filename of (await readdir(directory))
    .filter((name) => name.endsWith(".sql"))
    .sort()) {
    const source = await readFile(new URL(filename, directory), "utf8");
    for (const statement of source.split(";").filter((s) => s.trim()))
      await sql().query(statement);
    console.log("EventWeave migration applied:", filename);
  }
} catch (error) {
  console.error(
    "Database migration failed:",
    error && typeof error === "object" && "code" in error
      ? error.code
      : "connection unavailable",
  );
  process.exitCode = 1;
}
