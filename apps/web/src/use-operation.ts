import { useState } from "react";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { request } from "./api";
import type { Deployment } from "@eventweave/protocol";
export function useOperation() {
  const { authenticated, login, getAccessToken } = usePrivy();
  const { wallets } = useWallets();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function run(
    contract: keyof Pick<
      Deployment,
      "registry" | "court" | "directory" | "incident" | "release"
    >,
    method: string,
    args: (string | number | boolean)[],
  ) {
    if (!authenticated) {
      login();
      throw new Error("Sign in with your email to continue.");
    }
    setBusy(true);
    setMessage("Preparing your request…");
    try {
      const token = await getAccessToken();
      if (!token)
        throw new Error("Your session has expired. Please sign in again.");
      const wallet = wallets.find((w) => w.walletClientType === "privy");
      if (!wallet)
        throw new Error(
          "Your secure signing account is still opening. Give it a moment.",
        );
      await wallet.switchChain(61999);
      const provider = await wallet.getEthereumProvider();
      const { signedClient, boundSigningProvider } = await import(
        "@eventweave/client"
      );
      const headers = { Authorization: "Bearer " + token };
      const prepared = await request<{
        address: `0x${string}`;
        operation_id: string;
        nonce: number;
      }>("/operations/prepare", {
        method: "POST",
        headers,
        body: JSON.stringify({
          operation_id: crypto.randomUUID(),
          contract,
          method,
          args,
        }),
      });
      const operation_id = prepared.operation_id;
      const client = signedClient(
        wallet.address as `0x${string}`,
        boundSigningProvider(provider, wallet.address, prepared.nonce),
      );
      setMessage("Sending your signed request…");
      const hash = await client.writeContract({
        address: prepared.address,
        functionName: method,
        args,
        value: 0n,
      });
      await request("/operations/broadcast", {
        method: "POST",
        headers,
        body: JSON.stringify({ operation_id, transaction_hash: hash }),
      });
      setMessage("Request received. You can follow it in Activity.");
      return { operation_id, hash };
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "This request could not be sent.",
      );
      throw error;
    } finally {
      setBusy(false);
    }
  }
  return { run, busy, message, setMessage };
}
