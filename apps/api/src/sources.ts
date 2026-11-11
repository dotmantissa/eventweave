import { createHash } from "node:crypto";
import { lookup } from "node:dns/promises";
import { isIP } from "node:net";
import { z } from "zod";
import { attributes, limits, type Source } from "@eventweave/protocol";
import { read } from "./chain.js";
import { HttpError } from "./auth.js";
export const sourceInput = z
  .object({
    url: z.url().max(2048),
    authority_id: z.string().min(1).max(128),
    record_id: z.string().min(1).max(128),
    revision: z.string().min(1).max(128),
  })
  .strict();
export function privateAddress(ip: string) {
  if (ip.includes(":"))
    return (
      ip === "::1" ||
      ip === "::" ||
      /^f[cd]/i.test(ip) ||
      /^fe[89ab]/i.test(ip) ||
      ip.toLowerCase().startsWith("::ffff:")
    );
  const parts = ip.split(".").map(Number);
  return (
    parts[0] === 0 ||
    parts[0] === 10 ||
    parts[0] === 127 ||
    parts[0] >= 224 ||
    (parts[0] === 169 && parts[1] === 254) ||
    (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) ||
    (parts[0] === 192 && parts[1] === 168) ||
    (parts[0] === 100 && parts[1] >= 64 && parts[1] <= 127)
  );
}
export async function commitSource(
  input: z.infer<typeof sourceInput>,
  signer: string,
): Promise<Source> {
  const authority = await read<{
    principal: string;
    url_prefix: string;
    channel: string;
    scope: string;
  }>("registry", "get_authority", [input.authority_id]);
  if (authority.principal !== signer)
    throw new HttpError(
      403,
      "Your signing account is not the configured principal for this authority.",
    );
  const url = new URL(input.url);
  const prefix = new URL(authority.url_prefix);
  if (
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    (url.port && url.port !== "443") ||
    url.hostname !== prefix.hostname ||
    !url.pathname.startsWith(prefix.pathname) ||
    !input.url.startsWith(authority.url_prefix)
  )
    throw new HttpError(
      400,
      "Use a public HTTPS URL within the configured authority channel.",
    );
  const addresses = isIP(url.hostname)
    ? [{ address: url.hostname }]
    : await lookup(url.hostname, { all: true });
  if (!addresses.length || addresses.some((a) => privateAddress(a.address)))
    throw new HttpError(400, "Private network sources are not accepted.");
  const response = await fetch(url, {
    redirect: "error",
    signal: AbortSignal.timeout(12000),
    headers: { Accept: "text/plain,application/json,text/html" },
  });
  if (!response.ok)
    throw new HttpError(422, "The public source is unavailable.");
  if (Number(response.headers.get("content-length")) > limits.sourceBytes)
    throw new HttpError(413, "The complete source exceeds 48 KiB.");
  if (!response.body)
    throw new HttpError(422, "The source has no readable body.");
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      length += chunk.value.length;
      if (length > limits.sourceBytes)
        throw new HttpError(
          413,
          "The complete source exceeds 48 KiB. It cannot be truncated.",
        );
      chunks.push(chunk.value);
    }
  } finally {
    await reader.cancel();
  }
  const raw = Buffer.concat(chunks);
  let decoded: string;
  try {
    decoded = new TextDecoder("utf-8", { fatal: true }).decode(raw);
  } catch {
    throw new HttpError(422, "The source is not valid UTF 8 text.");
  }
  if (!length || decoded.length > limits.decodedChars)
    throw new HttpError(
      413,
      "The complete source is empty or exceeds the text budget.",
    );
  const raw_hash = createHash("sha256").update(raw).digest("hex");
  return {
    ...input,
    channel: authority.channel,
    scope: authority.scope,
    raw_hash,
    byte_length: length,
    spans: attributes.map((attribute) => ({
      span_id: input.record_id + "." + attribute,
      attribute,
      start: 0,
      end: length,
      raw_hash,
    })),
  };
}
