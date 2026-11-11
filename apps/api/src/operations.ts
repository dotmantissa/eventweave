import {
  descriptorSchema,
  compareSchema,
  prepareSchema,
  type Operation,
  type Lifecycle,
} from "@eventweave/protocol";
import type { z } from "zod";
import { sql } from "./db.js";
import { chain, read, hash, requireDeployment } from "./chain.js";
import { HttpError } from "./auth.js";
import { abi } from "genlayer-js";
const methods: Record<string, string[]> = {
  registry: [
    "open_event",
    "register_schema",
    "register_authority",
    "quarantine_authority",
    "attest_source_revision",
  ],
  court: [
    "compare_records",
    "assess",
    "supersede_relation",
    "quarantine_request",
    "retry_delivery",
    "cancel_request",
  ],
  directory: [
    "propose_merge",
    "finalize_alias",
    "publish_alias",
    "recover_component",
    "retry_invalidation",
    "retry_notice",
  ],
  incident: ["register_reference", "release_hold"],
  release: ["register_reference", "release_hold"],
};
export async function prepareOperation(
  input: z.infer<typeof prepareSchema>,
  auth: { user_id: string; signer: `0x${string}` },
) {
  if (!methods[input.contract]?.includes(input.method))
    throw new HttpError(400, "This action is not a public client method.");
  const deployment = requireDeployment();
  if (input.method === "open_event")
    descriptorSchema.parse(JSON.parse(String(input.args[0])));
  if (input.method === "compare_records") {
    const request = compareSchema.parse(JSON.parse(String(input.args[0])));
    if (
      request.envelope.owner !== auth.signer ||
      !request.envelope.parties.includes(auth.signer)
    )
      throw new HttpError(
        403,
        "The comparison must be bound to your signing account.",
      );
  }
  if (["register_reference", "release_hold"].includes(input.method)) {
    const config = await read<{ owner: string }>(
      input.contract,
      "get_configuration",
    );
    if (config.owner !== auth.signer)
      throw new HttpError(
        403,
        "Only the independent application owner can change its references.",
      );
  }
  if (
    ["register_schema", "register_authority", "quarantine_authority"].includes(
      input.method,
    ) &&
    auth.signer !== deployment.signer.toLowerCase()
  )
    throw new HttpError(
      403,
      "Only the registry owner can change authority or policy configuration.",
    );
  const payload_digest = hash({
    address: deployment[input.contract],
    method: input.method,
    args: input.args,
  });
  const existing =
    await sql()`SELECT * FROM operation_journal WHERE operation_id=${input.operation_id}`;
  if (existing.length) {
    if (
      existing[0].user_id !== auth.user_id ||
      existing[0].payload_digest !== payload_digest
    )
      throw new HttpError(
        409,
        "This operation ID was already used for a different request.",
      );
    return {
      operation_id: input.operation_id,
      address: existing[0].contract_address || deployment[input.contract],
      nonce: Number(existing[0].nonce),
    };
  }
  if (input.method === "assess") {
    const prior =
      await sql()`SELECT COUNT(*)::integer AS count FROM operation_journal WHERE signer=${auth.signer} AND contract_address=${deployment[input.contract]} AND method='assess' AND args=${JSON.stringify(input.args)}::jsonb AND transaction_hash IS NOT NULL`;
    if (prior[0].count >= 3)
      throw new HttpError(
        409,
        "Three assessment attempts have been submitted. Use a successor request for recovery.",
      );
  }
  const nonce = await chain().getCurrentNonce({ address: auth.signer });
  // Unsigned preparation does not lock a chain nonce. Resume an identical intent.
  const resumable =
    await sql()`SELECT * FROM operation_journal WHERE user_id=${auth.user_id} AND signer=${auth.signer} AND nonce=${nonce} AND payload_digest=${payload_digest} AND transaction_hash IS NULL ORDER BY created_at DESC LIMIT 1`;
  if (resumable.length)
    return {
      operation_id: resumable[0].operation_id,
      address: resumable[0].contract_address,
      nonce: Number(resumable[0].nonce),
    };
  try {
    await sql()`INSERT INTO operation_journal(operation_id,user_id,signer,contract,contract_address,directory_address,method,args,payload_digest,nonce) VALUES(${input.operation_id},${auth.user_id},${auth.signer},${input.contract},${deployment[input.contract]},${deployment.directory},${input.method},${JSON.stringify(input.args)},${payload_digest},${nonce})`;
  } catch {
    throw new HttpError(
      409,
      "Another signed request is being prepared. Reconcile it in Activity before trying again.",
    );
  }
  return {
    operation_id: input.operation_id,
    address: deployment[input.contract],
    nonce: Number(nonce),
  };
}
function finalLeader(tx: Record<string, unknown>) {
  const consensus = tx.consensus_data as Record<string, unknown> | undefined;
  const receipts = consensus?.leader_receipt;
  const leaders = (
    Array.isArray(receipts) ? receipts : receipts ? [receipts] : []
  ) as Record<string, unknown>[];
  return leaders
    .filter(
      (l) =>
        !/execution cancel(?:led|ed) after quorum/i.test(JSON.stringify(l)),
    )
    .at(-1);
}
export function executionFailed(tx: Record<string, unknown>) {
  const outcome = String(tx.result_name ?? tx.result);
  if (["ERROR", "MAJORITY_DISAGREE", "7"].includes(outcome)) return true;
  const result = String(tx.txExecutionResultName);
  if (
    [
      "ERROR",
      "CONTRACT_ERROR",
      "INTERNAL_ERROR",
      "FINISHED_WITH_ERROR",
    ].includes(result)
  )
    return true;
  if (result === "FINISHED_WITH_RETURN") return false;
  return [
    "ERROR",
    "CONTRACT_ERROR",
    "INTERNAL_ERROR",
    "FINISHED_WITH_ERROR",
  ].includes(String(finalLeader(tx)?.execution_result));
}
export function executionSucceeded(tx: Record<string, unknown>) {
  if (executionFailed(tx)) return false;
  return (
    tx.txExecutionResultName === "FINISHED_WITH_RETURN" ||
    (["MAJORITY_AGREE", "6"].includes(String(tx.result_name ?? tx.result)) &&
      finalLeader(tx)?.execution_result === "SUCCESS")
  );
}
export function lifecycle(tx: Record<string, unknown>): Lifecycle {
  const status = String(
    tx.statusName || tx.status_name || tx.status,
  ).toUpperCase();
  if (executionFailed(tx)) return "delivery_failed";
  if (status === "FINALIZED" || status === "7")
    return executionSucceeded(tx) ? "finalized" : "unresolved";
  if (status === "ACCEPTED" || status === "5") return "accepted";
  if (
    [
      "UNDETERMINED",
      "6",
      "8",
      "CANCELED",
      "LEADER_TIMEOUT",
      "VALIDATORS_TIMEOUT",
      "12",
      "13",
    ].includes(status)
  )
    return "unresolved";
  return "pending";
}
export function matchesOperation(
  operation: Record<string, unknown>,
  tx: Record<string, unknown>,
  address: string,
) {
  const sender = String(
    tx.from_address || tx.from || tx.sender || "",
  ).toLowerCase();
  const recipient = String(
    tx.to_address || tx.to || tx.recipient || "",
  ).toLowerCase();
  if (
    sender !== String(operation.signer).toLowerCase() ||
    recipient !== address.toLowerCase() ||
    Number(tx.nonce) !== Number(operation.nonce)
  )
    return false;
  const data = tx.data as
    | {
        calldata?:
          | string
          | { base64?: string; raw?: number[]; readable?: string };
      }
    | undefined;
  try {
    const encoded = data?.calldata;
    let calldata: { method?: unknown; args?: unknown[] };
    if (typeof encoded === "string" || encoded?.base64 || encoded?.raw) {
      const bytes =
        typeof encoded === "string"
          ? Buffer.from(encoded, "base64")
          : encoded.base64
            ? Buffer.from(encoded.base64, "base64")
            : Uint8Array.from(encoded.raw!);
      if (bytes.length > 25600) return false;
      const decoded = abi.calldata.decode(bytes);
      if (
        !(decoded instanceof Map) ||
        [...decoded.keys()].some((key) => !["method", "args"].includes(key))
      )
        return false;
      const args = decoded.get("args") || [];
      if (!Array.isArray(args)) return false;
      calldata = {
        method: decoded.get("method"),
        args: args.map((value) => {
          if (typeof value === "bigint" && Number.isSafeInteger(Number(value)))
            return Number(value);
          if (["string", "number", "boolean"].includes(typeof value))
            return value;
          throw new Error("Unsupported signed argument");
        }),
      };
    } else calldata = JSON.parse(encoded?.readable || "{}");
    return (
      hash({ address, method: calldata.method, args: calldata.args || [] }) ===
      operation.payload_digest
    );
  } catch {
    return false;
  }
}
export async function attachBroadcast(
  operationId: string,
  transactionHash: `0x${string}`,
  auth: { user_id: string },
) {
  const rows =
    await sql()`SELECT * FROM operation_journal WHERE operation_id=${operationId} AND user_id=${auth.user_id}`;
  if (!rows.length)
    throw new HttpError(
      404,
      "This operation was not prepared by your account.",
    );
  const operation = rows[0];
  if (
    operation.transaction_hash &&
    operation.transaction_hash !== transactionHash
  )
    throw new HttpError(409, "A different broadcast is already recorded.");
  const transaction = (await chain().getTransaction({
    hash: transactionHash as import("genlayer-js/types").TransactionHash,
  })) as unknown as Record<string, unknown>;
  const address =
    operation.contract_address ||
    requireDeployment()[operation.contract as "registry"];
  if (!matchesOperation(operation, transaction, address))
    throw new HttpError(
      403,
      "The signed transaction does not match the prepared operation.",
    );
  await sql()`UPDATE operation_journal SET transaction_hash=${transactionHash},status=${lifecycle(transaction)},updated_at=now() WHERE operation_id=${operationId}`;
  return { operation_id: operationId, status: lifecycle(transaction) };
}
export async function userOperations(userId: string): Promise<Operation[]> {
  return (await sql()`SELECT operation_id,contract,method,args,transaction_hash,status,error,created_at,acknowledged FROM operation_journal WHERE user_id=${userId} ORDER BY created_at DESC LIMIT 50`) as Operation[];
}
