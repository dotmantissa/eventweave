import "dotenv/config";
import { applyMigrations } from "./migrations.js";
try {
  for (const filename of await applyMigrations()) {
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
