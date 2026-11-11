import { chain } from "../apps/api/src/chain";
import { readFileSync } from "node:fs";
const probe = JSON.parse(
  readFileSync("verification/recovery-broadcast.json", "utf8"),
);
const candidates = await chain().request({
  method: "sim_getTransactionsForAddress",
  params: [probe.signer],
});
console.log(
  "Candidate container:",
  Array.isArray(candidates) ? "array" : typeof candidates,
  "count:",
  Array.isArray(candidates) ? candidates.length : 0,
);
if (Array.isArray(candidates)) {
  const found = candidates.find((tx) =>
    JSON.stringify(tx).includes(probe.transaction_hash),
  );
  console.log(
    "Known broadcast candidate field names:",
    found ? Object.keys(found) : "not found",
  );
  if (found)
    console.log(
      JSON.stringify({
        from: found.from_address,
        to: found.to_address,
        nonce: found.nonce,
        data: found.data,
      }),
    );
}
const tx = await chain().getTransaction({ hash: probe.transaction_hash });
console.log("Decoded transaction fields:", Object.keys(tx));
console.log(
  JSON.stringify({
    from: tx.from_address,
    to: tx.to_address,
    nonce: tx.nonce,
    data: tx.data,
    status: tx.status,
  }),
);
