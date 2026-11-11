import { describe, it, expect } from "vitest";
import {
  canonical,
  sourceSchema,
  envelopeSchema,
  limits,
} from "@eventweave/protocol";
import { hash } from "../apps/api/src/chain";
import { privateAddress } from "../apps/api/src/sources";
import { lifecycle, matchesOperation } from "../apps/api/src/operations";
import { abi } from "genlayer-js";

describe("canonical bindings", () => {
  it("hashes nested request fields in Python compatible order", () => {
    expect(canonical({ z: 1, a: { z: 1, a: 2 }, q: ["x", "y"] })).toBe(
      '{"a":{"a":2,"z":1},"q":["x","y"],"z":1}',
    );
    expect(hash({ a: 2, z: 1 })).toBe(
      "c2985c5ba6f7d2a55e768f92490ca09388e95bc4cccb9fdf11b15f4d42f93e73",
    );
  });
  it("rejects missing envelope fields and oversized complete sources", () => {
    expect(envelopeSchema.safeParse({ request_id: "r" }).success).toBe(false);
    expect(
      sourceSchema.safeParse({ byte_length: limits.sourceBytes + 1 }).success,
    ).toBe(false);
  });
});
describe("network and recovery boundaries", () => {
  it.each([
    "127.0.0.1",
    "10.0.0.1",
    "169.254.169.254",
    "192.168.1.1",
    "172.16.0.1",
    "100.64.0.1",
    "::1",
    "fd00::1",
    "::ffff:127.0.0.1",
  ])("rejects private source address %s", (ip) =>
    expect(privateAddress(ip)).toBe(true),
  );
  it("keeps public sources available", () =>
    expect(privateAddress("140.82.112.3")).toBe(false));
  it("does not mistake finalized execution errors for success", () =>
    expect(
      lifecycle({
        status_name: "FINALIZED",
        txExecutionResultName: "CONTRACT_ERROR",
      }),
    ).toBe("delivery_failed"));
  it.each([
    [5, "accepted"],
    [6, "unresolved"],
    [8, "unresolved"],
    [12, "unresolved"],
    [13, "unresolved"],
  ])("classifies Studio status %s as %s", (status, expected) => {
    expect(lifecycle({ status })).toBe(expected);
  });
  it("requires execution evidence before acknowledging finalization", () => {
    expect(lifecycle({ status: 7 })).toBe("unresolved");
    expect(
      lifecycle({
        status: 7,
        result: 6,
        consensus_data: { leader_receipt: [{ execution_result: "SUCCESS" }] },
      }),
    ).toBe("finalized");
    expect(
      lifecycle({
        status: 7,
        result: 6,
        consensus_data: { leader_receipt: [{ execution_result: "ERROR" }] },
      }),
    ).toBe("delivery_failed");
    expect(
      lifecycle({
        statusName: "FINALIZED",
        txExecutionResultName: "FINISHED_WITH_ERROR",
      }),
    ).toBe("delivery_failed");
  });
  it("reconciles only the exact signed operation and nonce", () => {
    const address = "0x" + "11".repeat(20),
      signer = "0x" + "22".repeat(20);
    const args = ["event.a", "reference.a"];
    const operation = {
      signer,
      nonce: 5,
      payload_digest: hash({ address, method: "register_reference", args }),
    };
    const tx = {
      from_address: signer,
      to_address: address,
      nonce: 5,
      data: {
        calldata: {
          readable: JSON.stringify({ method: "register_reference", args }),
        },
      },
    };
    expect(matchesOperation(operation, tx, address)).toBe(true);
    expect(matchesOperation(operation, { ...tx, nonce: 6 }, address)).toBe(
      false,
    );
    expect(
      matchesOperation(operation, { ...tx, from_address: address }, address),
    ).toBe(false);
    const bytes = abi.calldata.encode({ method: "register_reference", args });
    const base64 = Buffer.from(bytes).toString("base64");
    // Studio history returns binary calldata; the SDK's readable renderer is not JSON.
    expect(
      matchesOperation(
        operation,
        { ...tx, data: { calldata: base64 } },
        address,
      ),
    ).toBe(true);
    expect(
      matchesOperation(
        operation,
        { ...tx, data: { calldata: { base64, readable: "invalid JSON" } } },
        address,
      ),
    ).toBe(true);
    expect(
      matchesOperation(
        operation,
        { ...tx, data: { calldata: { raw: [...bytes] } } },
        address,
      ),
    ).toBe(true);
    const mismatches: Record<
      string,
      string | string[] | Record<string, string>
    >[] = [
      { method: "release_hold", args },
      { method: "register_reference", args: ["event.b", "reference.a"] },
      { method: "register_reference", args, kwargs: { owner: signer } },
    ];
    for (const payload of mismatches) {
      expect(
        matchesOperation(
          operation,
          {
            ...tx,
            data: {
              calldata: Buffer.from(abi.calldata.encode(payload)).toString(
                "base64",
              ),
            },
          },
          address,
        ),
      ).toBe(false);
    }
    expect(
      matchesOperation(operation, { ...tx, to_address: signer }, address),
    ).toBe(false);
    expect(
      matchesOperation(
        operation,
        { ...tx, data: { calldata: "broken" } },
        address,
      ),
    ).toBe(false);
  });
});
