import { pathToFileURL } from "node:url";
import { chain, requireDeployment } from "./chain.js";
import { sql } from "./db.js";
import { lifecycle, matchesOperation } from "./operations.js";
import { rebuildIndex } from "./indexer.js";
export async function reconcile() {
  const deployment = requireDeployment();
  const rows =
    await sql()`SELECT * FROM operation_journal WHERE status IN ('pending','accepted','finalized','delivery_failed') AND acknowledged=false ORDER BY created_at LIMIT 8`;
  let completed = 0;
  for (const row of rows) {
    try {
      let hash = row.transaction_hash as `0x${string}` | null;
      if (!hash) {
        const candidates = (await chain().request({
          method: "sim_getTransactionsForAddress",
          params: [row.signer],
        })) as Record<string, unknown>[];
        const found = candidates.find((tx) =>
          matchesOperation(
            row,
            tx,
            row.contract_address || deployment[row.contract as "registry"],
          ),
        );
        if (found) {
          hash = String(found.hash) as `0x${string}`;
          await sql()`UPDATE operation_journal SET transaction_hash=${hash},updated_at=now() WHERE operation_id=${row.operation_id}`;
        }
      }
      if (!hash) continue;
      const tx = (await chain().getTransaction({
        hash: hash as import("genlayer-js/types").TransactionHash,
      })) as unknown as Record<string, unknown>;
      const status = lifecycle(tx);
      let acknowledged = false;
      if (
        status === "finalized" &&
        ["apply_identity", "publish_alias"].includes(row.method)
      ) {
        const requestId = (row.args as string[])[0];
        const ack = (await chain().readContract({
          address: (row.directory_address ||
            deployment.directory) as `0x${string}`,
          functionName: "get_consumer_ack",
          args: ["delivery:" + requestId],
          jsonSafeReturn: true,
        })) as Record<string, unknown>;
        acknowledged = Boolean(ack.request_id);
      } else acknowledged = status === "finalized";
      await sql()`UPDATE operation_journal SET status=${status},acknowledged=${acknowledged},error=${status === "delivery_failed" ? "The network finalized an execution failure. Inspect the receipt before retrying." : null},updated_at=now() WHERE operation_id=${row.operation_id}`;
      if (acknowledged) completed++;
    } catch {
      await sql()`UPDATE operation_journal SET error='The network could not be reached. The broadcast journal is retained.',updated_at=now() WHERE operation_id=${row.operation_id}`;
    }
  }
  await rebuildIndex();
  return completed;
}
if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const run = async () => {
    try {
      console.log("Reconciled operations:", await reconcile());
    } catch {
      console.error(
        "Reconciliation unavailable. Check server configuration and network.",
      );
    }
  };
  await run();
  setInterval(run, 30000);
}
