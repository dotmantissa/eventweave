/** Real signed SDK calls. Independent application owners reserve authentic source records. */
import { config } from "dotenv";
import { readFileSync, writeFileSync, renameSync } from "node:fs";
import { createAccount, createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus, type TransactionHash } from "genlayer-js/types";
import "../apps/api/src/network";
import type { Deployment } from "@eventweave/protocol";
import { lifecycle } from "../apps/api/src/operations";
config({ path: ".secrets/consumer-owners.env", quiet: true });
const deployment = JSON.parse(
  readFileSync("deployments/studionet.json", "utf8"),
) as Deployment;
const path = `verification/signed-client-receipts.v${deployment.revision || 1}.json`;
const journal: Record<
  string,
  { transaction_hash: string; address: string; status?: string; ack?: unknown }
> = (() => {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return {};
  }
})();
const save = () => {
  writeFileSync(path + ".tmp", JSON.stringify(journal, null, 2) + "\n");
  renameSync(path + ".tmp", path);
};
const client = createClient({
  chain: studionet,
  account: createAccount(
    ("0x" +
      process.env.RELEASE_OWNER_PRIVATE_KEY!.replace(
        /^0x/,
        "",
      )) as `0x${string}`,
  ),
});
for (const id of ["nodejs.release.22.13.1", "nodejs.release.22.11.0"]) {
  const operation = "reference.release." + id;
  if (!journal[operation]) {
    const tx = await client.writeContract({
      address: deployment.release,
      functionName: "register_reference",
      args: [id, "release." + id],
      value: 0n,
    });
    journal[operation] = { transaction_hash: tx, address: deployment.release };
    save();
    console.log(operation, "broadcast", tx);
  }
  if (journal[operation].address !== deployment.release)
    throw new Error("The journal belongs to a different consumer deployment.");
  const receipt = await client.waitForTransactionReceipt({
    hash: journal[operation].transaction_hash as TransactionHash,
    status: TransactionStatus.FINALIZED,
    retries: 60,
    interval: 5000,
  });
  if (lifecycle(receipt as unknown as Record<string, unknown>) !== "finalized")
    throw new Error(
      "The signed reservation did not finalize with successful execution.",
    );
  const reference = await client.readContract({
    address: deployment.release,
    functionName: "get_reference",
    args: ["release." + id],
    jsonSafeReturn: true,
  });
  journal[operation].status = "finalized";
  journal[operation].ack = reference;
  save();
  console.log(operation, "reference confirmed");
}
