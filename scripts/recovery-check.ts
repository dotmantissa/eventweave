import { reconcile } from "../apps/api/src/worker";
import { sql } from "../apps/api/src/db";
import { readFileSync, writeFileSync } from "node:fs";
const probe = JSON.parse(
  readFileSync("verification/recovery-broadcast.json", "utf8"),
);
await reconcile();
const rows =
  await sql()`SELECT operation_id,transaction_hash,status,acknowledged,error FROM operation_journal WHERE operation_id=${probe.operation_id}`;
writeFileSync(
  "verification/recovery-result.json",
  JSON.stringify(rows, null, 2) + "\n",
);
console.log(
  "Recovered broadcast:",
  rows[0]?.transaction_hash === probe.transaction_hash,
  "status:",
  rows[0]?.status,
  "acknowledged:",
  rows[0]?.acknowledged,
);
if (
  rows[0]?.transaction_hash !== probe.transaction_hash ||
  !rows[0]?.acknowledged
)
  process.exitCode = 1;
