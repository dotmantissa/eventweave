import { publicClient } from "@eventweave/client";
import {
  canonical,
  type Certificate,
  type Deployment,
  type Identity,
} from "@eventweave/protocol";
import { createHash } from "node:crypto";
import { configuration, deployment } from "./config.js";
import { HttpError } from "./auth.js";
export const hash = (value: unknown) =>
  createHash("sha256").update(canonical(value)).digest("hex");
export const chain = () => publicClient(configuration().GENLAYER_RPC_URL);
export function requireDeployment() {
  const value = deployment();
  if (!value) throw new HttpError(503, "Contracts are not deployed yet.");
  return value;
}
export async function read<T>(
  contract: keyof Pick<
    Deployment,
    "registry" | "court" | "directory" | "incident" | "release"
  >,
  method: string,
  args: (string | number | boolean)[] = [],
): Promise<T> {
  const addresses = requireDeployment();
  return (await chain().readContract({
    address: addresses[contract],
    functionName: method,
    args,
    jsonSafeReturn: true,
  })) as T;
}
export const policyScope = (
  scope: string,
  policy_id: string,
  policy_revision: number,
) => "scope:" + hash({ scope, policy_id, policy_revision });
export const pairId = (left: string, right: string, scope: string) =>
  "pair:" + hash({ scope, records: [left, right].sort() });
export async function identity(eventId: string): Promise<Identity> {
  const original = await read<Identity>("registry", "get_identity", [eventId]);
  const policy = await read<{ scope: string }>("registry", "get_schema", [
    original.schema_id,
    original.schema_revision,
  ]);
  const merged = await read<{
    canonical_id: string;
    members: string[];
    status: Identity["status"];
    generation: number;
  }>("directory", "get_identity", [
    eventId,
    policyScope(policy.scope, original.schema_id, original.schema_revision),
  ]);
  return { ...original, ...merged };
}
export async function relations(eventId: string): Promise<Certificate[]> {
  const history = await read<{ request_id?: string; operation: string }[]>(
    "directory",
    "get_history",
    [0, 50],
  );
  const ids = [
    ...new Set(
      history
        .filter((h) => h.operation === "certificate")
        .map((h) => h.request_id!),
    ),
  ];
  const result: Certificate[] = [];
  for (const id of ids) {
    const relation = await read<Certificate>("directory", "get_relation", [id]);
    if (relation.left === eventId || relation.right === eventId)
      result.push(relation);
  }
  return result;
}
