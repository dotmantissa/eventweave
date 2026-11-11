import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import type { Deployment } from "@eventweave/protocol";
export const publicClient = (endpoint = studionet.rpcUrls.default.http[0]) =>
  createClient({ chain: studionet, endpoint });
export const signedClient = (
  account: `0x${string}`,
  provider: {
    request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
  },
) => createClient({ chain: studionet, account, provider });
export class EventWeaveClient {
  constructor(
    readonly deployment: Deployment,
    readonly client = publicClient(),
  ) {}
  identity(eventId: string) {
    return this.client.readContract({
      address: this.deployment.registry,
      functionName: "get_identity",
      args: [eventId],
      jsonSafeReturn: true,
    });
  }
  relation(requestId: string) {
    return this.client.readContract({
      address: this.deployment.directory,
      functionName: "get_relation",
      args: [requestId],
      jsonSafeReturn: true,
    });
  }
  acknowledgement(operationId: string) {
    return this.client.readContract({
      address: this.deployment.directory,
      functionName: "get_consumer_ack",
      args: [operationId],
      jsonSafeReturn: true,
    });
  }
  notice(operationId: string) {
    return this.client.readContract({
      address: this.deployment.directory,
      functionName: "get_notice",
      args: [operationId],
      jsonSafeReturn: true,
    });
  }
  retryNotice(operationId: string) {
    return this.client.writeContract({
      address: this.deployment.directory,
      functionName: "retry_notice",
      args: [operationId],
      value: 0n,
    });
  }
  compare(requestJson: string) {
    return this.client.writeContract({
      address: this.deployment.court,
      functionName: "compare_records",
      args: [requestJson],
      value: 0n,
    });
  }
  assess(requestId: string) {
    return this.client.writeContract({
      address: this.deployment.court,
      functionName: "assess",
      args: [requestId],
      value: 0n,
    });
  }
  proposeMerge(proofJson: string) {
    return this.client.writeContract({
      address: this.deployment.directory,
      functionName: "propose_merge",
      args: [proofJson],
      value: 0n,
    });
  }
  finalizeAlias(operationId: string) {
    return this.client.writeContract({
      address: this.deployment.directory,
      functionName: "finalize_alias",
      args: [operationId],
      value: 0n,
    });
  }
  publishAlias(requestId: string) {
    return this.client.writeContract({
      address: this.deployment.directory,
      functionName: "publish_alias",
      args: [requestId],
      value: 0n,
    });
  }
}

export function boundSigningProvider(
  provider: {
    request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
  },
  account: string,
  nonce: number,
) {
  return {
    request: async (args: { method: string; params?: unknown[] }) => {
      if (args.method === "eth_sendTransaction") {
        const tx = args.params?.[0] as
          | { from?: string; nonce?: string; chainId?: string }
          | undefined;
        if (
          !tx ||
          tx.from?.toLowerCase() !== account.toLowerCase() ||
          tx.nonce === undefined ||
          BigInt(tx.nonce) !== BigInt(nonce) ||
          BigInt(tx.chainId || 0) !== 61999n
        ) {
          throw new Error(
            "Your signing account changed while preparing. Try again to prepare a fresh request.",
          );
        }
      }
      return provider.request(args);
    },
  };
}
