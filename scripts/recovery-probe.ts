/** Authentic broadcast recovery exercise. This verifier exits after sending, before attaching the receipt. */
import { config } from "dotenv";
import { readFileSync, writeFileSync } from "node:fs";
import { createAccount, createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import type { Deployment } from "@eventweave/protocol";
import { prepareOperation } from "../apps/api/src/operations";
import { hash } from "../apps/api/src/chain";
config({ path: ".secrets/consumer-owners.env", quiet: true });
const deployment = JSON.parse(
  readFileSync("deployments/studionet.json", "utf8"),
) as Deployment;
const account = createAccount(
  ("0x" +
    process.env.RELEASE_OWNER_PRIVATE_KEY!.replace(/^0x/, "")) as `0x${string}`,
);
const operation_id = crypto.randomUUID();
const args = [
  "nodejs.release.22.13.1",
  "recovery." + operation_id.replaceAll("-", ""),
];
await prepareOperation(
  { operation_id, contract: "release", method: "register_reference", args },
  {
    user_id: "network:" + account.address.toLowerCase(),
    signer: account.address.toLowerCase() as `0x${string}`,
  },
);
const client = createClient({ chain: studionet, account });
const transaction = await client.writeContract({
  address: deployment.release,
  functionName: "register_reference",
  args,
  value: 0n,
});
writeFileSync(
  "verification/recovery-broadcast.json",
  JSON.stringify(
    {
      classification:
        "authentic signed broadcast recovery probe, not an email session",
      operation_id,
      transaction_hash: transaction,
      signer: account.address,
      payload_digest: hash({
        address: deployment.release,
        method: "register_reference",
        args,
      }),
      reference_id: args[1],
    },
    null,
    2,
  ) + "\n",
);
console.log(
  "Broadcast recorded outside the operation journal. Terminating verification process:",
  operation_id,
);
process.exit(0);
