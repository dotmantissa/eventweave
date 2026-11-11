import { beforeEach, expect, it, vi } from "vitest";
import { createHash } from "node:crypto";
import { canonical } from "@eventweave/protocol";
const state = vi.hoisted(() => ({
  rows: [] as Record<string, unknown>[],
  visited: [] as string[],
  nonce: 7,
  deployment: {
    registry: "0x1111111111111111111111111111111111111111",
    court: "0x1111111111111111111111111111111111111111",
    directory: "0x2222222222222222222222222222222222222222",
    signer: "owner",
  },
}));
vi.mock("../apps/api/src/db.js", () => ({
  sql:
    () =>
    async (strings: TemplateStringsArray, ...values: unknown[]) => {
      const query = strings.join("?");
      if (query.startsWith("SELECT COUNT"))
        return [
          {
            count: state.rows.filter(
              (r) =>
                r.signer === values[0] &&
                r.contract_address === values[1] &&
                r.method === "assess" &&
                JSON.stringify(r.args) === values[2] &&
                r.transaction_hash,
            ).length,
          },
        ];
      if (query.startsWith("SELECT *") && query.includes("next_reconcile_at"))
        return state.rows.filter((r) => !r.last_reconciled_at).slice(0, 8);
      if (query.startsWith("SELECT *") && query.includes("payload_digest"))
        return state.rows
          .filter(
            (r) =>
              r.user_id === values[0] &&
              r.signer === values[1] &&
              r.nonce === values[2] &&
              r.payload_digest === values[3] &&
              !r.transaction_hash,
          )
          .slice(0, 1);
      if (query.startsWith("SELECT *"))
        return state.rows.filter((r) => r.operation_id === values[0]);
      if (query.startsWith("INSERT")) {
        const [
          operation_id,
          user_id,
          signer,
          contract,
          contract_address,
          directory_address,
          method,
          args,
          payload_digest,
          nonce,
        ] = values;
        state.rows.push({
          operation_id,
          user_id,
          signer,
          contract,
          contract_address,
          directory_address,
          method,
          args: JSON.parse(String(args)),
          payload_digest,
          nonce,
        });
        return [];
      }
      if (query.includes("last_reconciled_at=now()")) {
        const row = state.rows.find((r) => r.operation_id === values[0])!;
        row.last_reconciled_at = true;
        return [];
      }
      return [];
    },
}));
vi.mock("../apps/api/src/chain.js", () => ({
  requireDeployment: () => state.deployment,
  hash: (v: unknown) => createHash("sha256").update(canonical(v)).digest("hex"),
  read: vi.fn(),
  chain: () => ({
    getCurrentNonce: async () => state.nonce,
    request: async ({ params }: { params: string[] }) => {
      state.visited.push(params[0]);
      return [];
    },
  }),
}));
vi.mock("../apps/api/src/indexer.js", () => ({ rebuildIndex: async () => 0 }));
import { prepareOperation } from "../apps/api/src/operations";
import { reconcile } from "../apps/api/src/worker";
beforeEach(() => {
  state.rows = [];
  state.visited = [];
  state.nonce = 7;
});
it("prebroadcast failures leave the nonce available for a different intent", async () => {
  const auth = {
    user_id: "user",
    signer: "0x3333333333333333333333333333333333333333" as `0x${string}`,
  };
  const first = await prepareOperation(
    {
      operation_id: "first",
      contract: "directory",
      method: "publish_alias",
      args: ["a"],
    },
    auth,
  );
  const retry = await prepareOperation(
    {
      operation_id: "retry",
      contract: "directory",
      method: "publish_alias",
      args: ["a"],
    },
    auth,
  );
  expect(retry.operation_id).toBe(first.operation_id);
  await prepareOperation(
    {
      operation_id: "different",
      contract: "directory",
      method: "publish_alias",
      args: ["b"],
    },
    auth,
  );
  expect(state.rows).toHaveLength(2);
  expect(state.rows.every((r) => r.nonce === 7)).toBe(true);
});
it("progresses beyond eight missing broadcasts on the next reconciliation pass", async () => {
  state.rows = Array.from({ length: 10 }, (_, i) => ({
    operation_id: String(i),
    signer: String(i),
    contract: "registry",
    nonce: i,
    args: [],
    transaction_hash: null,
  }));
  await reconcile();
  await reconcile();
  expect(state.visited).toEqual(
    Array.from({ length: 10 }, (_, i) => String(i)),
  );
});

it("abandoned assessment preparations do not spend the broadcast retry budget", async () => {
  const auth = {
    user_id: "user",
    signer: "0x3333333333333333333333333333333333333333" as `0x${string}`,
  };
  for (let nonce = 7; nonce < 12; nonce++) {
    state.nonce = nonce;
    await prepareOperation(
      {
        operation_id: "abandoned-" + nonce,
        contract: "court",
        method: "assess",
        args: ["request"],
      },
      auth,
    );
  }
  const input = {
    operation_id: "assessment",
    contract: "court" as const,
    method: "assess",
    args: ["request"],
  };
  await expect(prepareOperation(input, auth)).resolves.toHaveProperty(
    "nonce",
    11,
  );
  for (const row of state.rows.slice(0, 3))
    row.transaction_hash = "0x" + row.nonce;
  await expect(
    prepareOperation({ ...input, operation_id: "fourth" }, auth),
  ).rejects.toThrow("Three assessment attempts");
});
