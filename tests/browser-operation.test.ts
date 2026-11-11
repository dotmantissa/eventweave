import { beforeEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({
  wallet: {
    address: "0x1111111111111111111111111111111111111111",
    walletClientType: "privy",
    switchChain: vi.fn(),
    getEthereumProvider: vi.fn(),
  },
  request: vi.fn(),
  write: vi.fn(),
  order: [] as string[],
}));
vi.mock("react", () => ({ useState: (v: unknown) => [v, vi.fn()] }));
vi.mock("@privy-io/react-auth", () => ({
  usePrivy: () => ({
    authenticated: true,
    getAccessToken: async () => "token",
  }),
  useWallets: () => ({ wallets: [mocks.wallet] }),
}));
vi.mock("../apps/web/src/api", () => ({ request: mocks.request }));
vi.mock("@eventweave/client", () => ({
  signedClient: () => ({ writeContract: mocks.write }),
  boundSigningProvider: (p: unknown) => p,
}));
import { useOperation } from "../apps/web/src/use-operation";
beforeEach(() => {
  vi.clearAllMocks();
  mocks.order = [];
  mocks.wallet.switchChain.mockImplementation(async () => {
    mocks.order.push("chain");
  });
  mocks.wallet.getEthereumProvider.mockImplementation(async () => {
    mocks.order.push("provider");
    return {};
  });
  mocks.request.mockImplementation(async (path: string) => {
    mocks.order.push(path);
    return { operation_id: "resumed", address: mocks.wallet.address, nonce: 7 };
  });
  mocks.write.mockResolvedValue("hash");
});
it("obtains provider and switches chain before journal preparation", async () => {
  await useOperation().run("directory", "publish_alias", ["r"]);
  expect(mocks.order.slice(0, 3)).toEqual([
    "chain",
    "provider",
    "/operations/prepare",
  ]);
  expect(JSON.parse(mocks.request.mock.calls.at(-1)![1].body)).toEqual({
    operation_id: "resumed",
    transaction_hash: "hash",
  });
});
it("does not prepare an operation when the wallet cannot open", async () => {
  mocks.wallet.getEthereumProvider.mockRejectedValue(
    new Error("provider failed"),
  );
  await expect(
    useOperation().run("directory", "publish_alias", ["r"]),
  ).rejects.toThrow("provider failed");
  expect(mocks.request).not.toHaveBeenCalled();
});
