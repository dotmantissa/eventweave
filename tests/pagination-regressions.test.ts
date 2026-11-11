import { expect, it, vi } from "vitest";
const mock = vi.hoisted(() => ({ readContract: vi.fn() }));
vi.mock("@eventweave/client", () => ({
  publicClient: () => ({ readContract: mock.readContract }),
}));
import { lexicalOrder, readPages } from "../apps/api/src/chain";
it("uses Python lexical record ordering for case-sensitive commitments", () => {
  expect(["a", "A", "aa", "Z"].sort(lexicalOrder)).toEqual([
    "A",
    "Z",
    "a",
    "aa",
  ]);
});
it("follows every contract page including later corrections", async () => {
  mock.readContract.mockImplementation(
    async ({ args }: { args: (string | number)[] }) => {
      const offset = Number(args.at(-2));
      return Array.from({ length: Math.min(50, 123 - offset) }, (_, i) => ({
        event_id: "target",
        operation: offset + i === 122 ? "corrected" : "original",
        index: offset + i,
      }));
    },
  );
  const result = await readPages<{ index: number; operation: string }>(
    "directory",
    "get_event_alias_history",
    ["target", "scope"],
  );
  expect(result).toHaveLength(123);
  expect(result.at(-1)?.operation).toBe("corrected");
  expect(mock.readContract.mock.calls.map((c) => c[0].args.at(-2))).toEqual([
    0, 50, 100,
  ]);
});
