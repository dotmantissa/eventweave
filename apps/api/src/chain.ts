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
export const lexicalOrder = (a: string, b: string) =>
  a < b ? -1 : a > b ? 1 : 0;
export async function readPages<T>(
  contract: Parameters<typeof read>[0],
  method: string,
  args: (string | number | boolean)[] = [],
): Promise<T[]> {
  const result: T[] = [];
  for (let offset = 0; ; offset += 50) {
    const items = await read<T[]>(contract, method, [...args, offset, 50]);
    result.push(...items);
    if (items.length < 50) return result;
  }
}
export async function eventScope(eventId: string) {
  const original = await read<Identity>("registry", "get_identity", [eventId]);
  const policy = await read<{ scope: string }>("registry", "get_schema", [
    original.schema_id,
    original.schema_revision,
  ]);
  return policyScope(
    policy.scope,
    original.schema_id,
    original.schema_revision,
  );
}
export async function relations(eventId: string): Promise<Certificate[]> {
  return readPages<Certificate>("directory", "get_event_relations", [
    eventId,
    await eventScope(eventId),
  ]);
}
