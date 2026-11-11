import { expect, it, vi } from "vitest";
import { boundSigningProvider } from "@eventweave/client";
it("refuses a changed nonce before requesting a wallet signature", async () => {
  const request = vi.fn().mockResolvedValue("hash");
  const account = "0x1111111111111111111111111111111111111111";
  const provider = boundSigningProvider({ request }, account, 7);
  await expect(
    provider.request({
      method: "eth_sendTransaction",
      params: [{ from: account, nonce: "0x8", chainId: "0xf22f" }],
    }),
  ).rejects.toThrow("changed while preparing");
  expect(request).not.toHaveBeenCalled();
  expect(
    await provider.request({
      method: "eth_sendTransaction",
      params: [{ from: account, nonce: "0x7", chainId: "0xf22f" }],
    }),
  ).toBe("hash");
});
